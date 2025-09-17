from __future__ import annotations
import os, datetime as dt
from sqlalchemy import select, func
from .db import SessionLocal, Incident, ReportMeta
from .utils_time import now_local

OUT_DIR = os.path.join(os.getcwd(), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

ROLLING_LIMIT = int(os.getenv("ROLLING_REPORT_EVERY", 50))


def _sparkline(counts):
    glyphs = "▁▂▃▄▅▆▇█"
    if not counts: return ""
    m = max(counts) or 1
    return "".join(glyphs[int(c/m*(len(glyphs)-1))] for c in counts)


def generate_report_for_channel(channel_id: str) -> str:
    with SessionLocal() as s:
        meta = s.execute(select(ReportMeta).where(ReportMeta.channel_id == channel_id)).scalar_one_or_none()
        if not meta:
            meta = ReportMeta(channel_id=channel_id)
            s.add(meta); s.commit()
        since = meta.last_report_at
        incidents = s.execute(
            select(Incident).where(Incident.channel_id == channel_id, Incident.created_at > since).order_by(Incident.created_at)
        ).scalars().all()
        if not incidents:
            return ""

        serious = [i for i in incidents if i.action == "serious"]
        crisis = [i for i in incidents if i.action == "crisis"]
        total = len(incidents)

        # Hourly buckets (UTC)
        buckets = [0]*24
        for i in incidents:
            buckets[i.created_at.hour] += 1

        start = incidents[0].created_at; end = incidents[-1].created_at
        title = f"report_{channel_id}_{end.strftime('%Y%m%d_%H%M')}.md"
        path = os.path.join(OUT_DIR, title)

        lines = []
        lines.append(f"# Peer Support — Channel Report\n")
        lines.append(f"**Channel:** {channel_id}\n")
        lines.append(f"**Window (UTC):** {start} → {end}\n")
        lines.append(f"**Generated (local):** {now_local()}\n\n")
        lines.append(f"**Incidents:** {total}  |  **Serious DMs:** {len(serious)}  |  **Crisis DMs:** {len(crisis)}\n")
        lines.append(f"**Hourly trend:** {_sparkline(buckets)}\n")
        lines.append("\n---\n\n## Notable Incidents (anonymized)\n")
        for i in incidents[:10]:
            excerpt = i.text_excerpt.replace("\n"," ")[:180]
            lines.append(
                f"- **{i.created_at}** — `user:{i.user_id_hash}` — *{i.action}* — sarcasm={i.sarcasm:.2f}, tox_max={i.tox_max:.2f}, seriousness={i.seriousness:.2f}\n  \- _excerpt:_ {excerpt}\n"
            )
        lines.append("\n---\n\n## Suggestions\n")
        lines.append("- If repeated serious incidents, consider a temporary channel reminder on guidelines.\n")
        lines.append("- Encourage `/pause 10` when spikes cluster near deadlines.\n")
        lines.append("- Review redaction rights to ensure timely removal of harmful content.\n")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        meta.last_report_at = end; meta.flagged_since_last = 0; s.commit()
        return path


def bump_and_maybe_rolling_report(channel_id: str) -> str:
    with SessionLocal() as s:
        meta = s.execute(select(ReportMeta).where(ReportMeta.channel_id == channel_id)).scalar_one_or_none()
        if not meta:
            meta = ReportMeta(channel_id=channel_id, flagged_since_last=1)
            s.add(meta); s.commit(); return ""
        meta.flagged_since_last += 1; s.commit()
        if meta.flagged_since_last >= ROLLING_LIMIT:
            return generate_report_for_channel(channel_id)
        return ""

# Special per-user report for moderators

def generate_user_report(user_id_hash: str) -> str:
    with SessionLocal() as s:
        incidents = s.execute(
            select(Incident).where(Incident.user_id_hash == user_id_hash).order_by(Incident.created_at)
        ).scalars().all()
    if not incidents:
        return ""
    start = incidents[0].created_at; end = incidents[-1].created_at
    title = f"user_report_{user_id_hash}_{end.strftime('%Y%m%d_%H%M')}.md"
    path = os.path.join(OUT_DIR, title)
    lines = [
        f"# User Special Report\n",
        f"**User (anon):** {user_id_hash}\n",
        f"**Window (UTC):** {start} → {end}\n\n",
        "## Violations\n",
    ]
    for i in incidents:
        if i.action in {"serious","crisis"}:
            excerpt = i.text_excerpt.replace("\n"," ")[:200]
            lines.append(f"- {i.created_at} — action={i.action} — s={i.sarcasm:.2f}, tox={i.tox_max:.2f}, ser={i.seriousness:.2f}\n  \- _excerpt:_ {excerpt}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
