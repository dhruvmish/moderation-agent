import os, asyncio, traceback
import discord
from discord import app_commands
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import init_db, SessionLocal, Incident
from app.archivist import (
    generate_report_for_channel,
    bump_and_maybe_rolling_report,
    generate_user_report,
)
from app.policy import (
    anon_user_id,

    record_violation,
    has_been_warned,
    mark_warned,
)
from app.utils_time import now_local
from app.graph_pipeline import app_graph  # Sentinel→Triage→Responder

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
TZ = os.getenv("TZ", "Asia/Kolkata")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

init_db()
scheduler = AsyncIOScheduler(timezone=TZ)

async def run_daily_reports():
    # Build daily report per channel since last report
    with SessionLocal() as s:
        channels = {row[0] for row in s.query(Incident.channel_id).distinct()}
    for ch in channels:
        path = generate_report_for_channel(ch)
        if path:
            print(f"[REPORT] Daily report generated for {ch}: {path}")

@client.event
async def on_ready():
    print(f"Logged in as {client.user} | Local time: {now_local()}")
    await tree.sync()
    # Daily at 23:59 IST
    scheduler.add_job(run_daily_reports, CronTrigger(hour=23, minute=59))
    scheduler.start()

# /report: on-demand channel report
@tree.command(name="report", description="Generate a report since the last one for this channel")
async def report_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ch = str(interaction.channel_id)
    path = generate_report_for_channel(ch)
    if path:
        await interaction.followup.send(file=discord.File(path), ephemeral=True)
    else:
        await interaction.followup.send("No new incidents since last report.", ephemeral=True)

async def redact_message(message: discord.Message) -> bool:
    """Delete the offending message; fallback to edit if delete not permitted."""
    try:
        await message.delete()
        print(f"[REDACT] Deleted message {message.id}")
        return True
    except discord.Forbidden:
        try:
            await message.edit(content="[message redacted by moderator bot]")
            print(f"[REDACT] Edited content for message {message.id}")
            return True
        except Exception as e:
            print(f"[REDACT] Failed to redact message {message.id}: {e}")
            return False
    except Exception as e:
        print(f"[REDACT] Unexpected error: {e}")
        return False

@client.event
async def on_message(message: discord.Message):
    # Ignore bot/self and empty content
    if message.author.bot or not message.content:
        return

    try:
        text = message.content
        channel_id = str(getattr(message.channel, "id", ""))
        user_hash = anon_user_id(str(message.author.id))  # keep anon for DB; no owner DMs

        # ---- RUN THE GRAPH (this was missing) ----
        state = {
            "text": text,
            "user_id": str(message.author.id),
            "channel_id": channel_id,
            "sarcasm": 0.0,
            "tox_max": 0.0,
            "seriousness": 0.0,
            "action": "none",
            "reply": "",
        }
        result = app_graph.invoke(state)  # sync call
        action_raw = (result or {}).get("action", "none")
        reply = (result or {}).get("reply", "")

        sarcasm = float((result or {}).get("sarcasm", 0.0))
        tox_max = float((result or {}).get("tox_max", 0.0))
        seriousness = float((result or {}).get("seriousness", 0.0))

        # Normalize action labels from graph
        action = "none"
        severity = None
        if action_raw in {"serious", "serious_dm"}:
            action, severity = "serious", "serious"
        elif action_raw in {"crisis", "crisis_dm"}:
            action, severity = "crisis", "crisis"

        # Only act on serious/crisis (no sarcasm-only)
        if action == "none":
            return

        # # Severity-based cooldown (uses anon hash)
        # if not can_dm(user_hash, severity=severity):
        #     print(f"[COOLDOWN] Suppressing DM to user {user_hash} ({severity})")
        #     return

        # Redact the message now
        redacted = await redact_message(message)
        if not redacted:
            print("[WARN] Redaction failed (check bot permissions: Manage Messages).")

        # Persist violation incident
        with SessionLocal() as s:
            s.add(Incident(
                platform="discord",
                channel_id=channel_id,
                user_id_hash=user_hash,
                message_id=str(message.id),
                text_excerpt=text[:240],
                sarcasm=sarcasm,
                tox_max=tox_max,
                seriousness=seriousness,
                action=action,
                reply=reply,
            ))
            s.commit()

        # DM the sender (serious/crisis message)
        if reply:
            try:
                await message.author.send(reply)
            except discord.Forbidden:
                print(f"[DM] DM blocked by user {user_hash}; skipping.")

        # Violation counting & special user report (saved to outputs only)
        vcount = record_violation(user_hash)
        if vcount > 5 and not has_been_warned(user_hash):
            try:
                await message.author.send(
                    "This is a final warning. Continued violations may lead to removal from the group."
                )
                await message.channel.send(
                    f"<@{message.author.id}> has reached 5 violations. This is their final warning. "
                    "Continued violations may lead to removal."
                )

            except discord.Forbidden:
                pass
            path = generate_user_report(user_hash)  # just save; no DM to owner/mods
            if path:
                print(f"[USER-REPORT] Saved special report for {user_hash}: {path}")
            mark_warned(user_hash)

        # Rolling channel report bump
        rpath = bump_and_maybe_rolling_report(channel_id)
        if rpath:
            print(f"[REPORT] Rolling report generated for {channel_id}: {rpath}")

    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set.")
    client.run(TOKEN)