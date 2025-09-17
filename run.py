import os, csv, json, sqlite3, datetime as dt, argparse
from pathlib import Path
from collections import defaultdict, deque
from typing import List, Dict

from policy import compute_seriousness, decide, redact_text
from toxicity_infer import ToxicModel
from sarcasm_infer import SarcasmModel

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "moderation.db"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True, parents=True)

def read_csv(path: Path) -> List[Dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if not r.get("text"): continue
            out.append({
                "timestamp": r.get("timestamp") or "",
                "user_id":   r.get("user_id") or "",
                "channel":   r.get("channel") or "",
                "text":      r["text"].strip(),
            })
    return out

def read_ndjson(path: Path) -> List[Dict]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except: continue
            if not obj.get("text"): continue
            out.append({
                "timestamp": obj.get("timestamp") or "",
                "user_id":   obj.get("user_id") or "",
                "channel":   obj.get("channel") or "",
                "text":      str(obj["text"]).strip(),
            })
    return out

def db_init(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, user_id TEXT, channel TEXT, text TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS predictions(
        message_id INTEGER, label TEXT, prob REAL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS decisions(
        message_id INTEGER, severity REAL, seriousness REAL,
        sarcasm_prob REAL, actions_json TEXT, redacted_text TEXT)""")
    conn.commit()

def db_insert(conn, msg, probs, sev, ser, p_sar, actions, redacted):
    cur = conn.cursor()
    cur.execute("INSERT INTO messages(timestamp,user_id,channel,text) VALUES(?,?,?,?)",
                (msg["timestamp"], msg["user_id"], msg["channel"], msg["text"]))
    mid = cur.lastrowid
    for k,v in probs.items():
        cur.execute("INSERT INTO predictions(message_id,label,prob) VALUES(?,?,?)", (mid, k, float(v)))
    cur.execute("INSERT INTO decisions(message_id,severity,seriousness,sarcasm_prob,actions_json,redacted_text) "
                "VALUES(?,?,?,?,?,?)",
                (mid, float(sev), float(ser), float(p_sar), json.dumps(actions), redacted))
    conn.commit()
    return mid

def write_digest(rows: List[Dict]):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    path = OUT_DIR / "moderation_report.md"
    total = len(rows)
    flagged = sum(1 for r in rows if any(a in ("warn","escalate") for a in r["actions"]))
    escalated = sum(1 for r in rows if "escalate" in r["actions"])

    # counts by top labels
    counts = defaultdict(int)
    for r in rows:
        for lab, p in sorted(r["probs"].items(), key=lambda kv:-kv[1])[:2]:
            if p >= r["thresholds"].get(lab,0.5): counts[lab]+=1

    lines = []
    lines.append(f"# Moderation Report — {now}")
    lines.append(f"Total messages: {total}  |  Flagged: {flagged}  |  Escalated: {escalated}\n")

    lines.append("## Counts by label")
    for k in r["probs"].keys():
        lines.append(f"- {k}: {counts.get(k,0)}")
    lines.append("")

    # top escalations
    top_escalations = [r for r in rows if "escalate" in r["actions"]]
    top_escalations.sort(key=lambda x: -x["seriousness"])
    lines.append("## Escalated (top 5 by seriousness)")
    for i, r in enumerate(top_escalations[:5], 1):
        txt = r["text"]
        lines.append(f"{i}) [{r['channel']}] {r['user_id']} — \"{txt[:100]}\" "
                     f"(threat={r['probs'].get('threat',0):.2f}, severe={r['probs'].get('severe_toxic',0):.2f}, seriousness={r['seriousness']:.2f})")
    lines.append("")

    # recent warnings (redacted)
    warns = [r for r in rows if "warn" in r["actions"]]
    lines.append("## Recent warnings (redacted)")
    for r in warns[:10]:
        lines.append(f"- {r['user_id']}: \"{r['redacted']}\"")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="path to CSV or NDJSON (.jsonl)")
    args = ap.parse_args()
    in_path = Path(args.input)
    assert in_path.exists(), f"not found: {in_path}"

    # load data
    if in_path.suffix.lower() == ".csv":
        messages = read_csv(in_path)
    elif in_path.suffix.lower() in (".jsonl", ".ndjson"):
        messages = read_ndjson(in_path)
    else:
        raise SystemExit("input must be .csv or .jsonl/.ndjson")

    tox = ToxicModel()
    sar = SarcasmModel()

    # rolling context
    K = 5
    hist_user = defaultdict(lambda: deque(maxlen=K))
    hist_chan = defaultdict(lambda: deque(maxlen=K))

    conn = sqlite3.connect(DB_PATH)
    db_init(conn)

    results = []
    for m in messages:
        p = tox.probs(m["text"])
        p_s = sar.prob(m["text"])
        sev, ser = compute_seriousness(p, p_s, list(hist_user[m["user_id"]]), list(hist_chan[m["channel"]]))
        actions = decide(p, ser)
        redacted = redact_text(m["text"]) if "redact" in actions else m["text"]

        # update context
        hist_user[m["user_id"]].append(sev)
        hist_chan[m["channel"]].append(sev)

        db_insert(conn, m, p, sev, ser, p_s, actions, redacted)
        result = {
            "timestamp": m["timestamp"], "user_id": m["user_id"], "channel": m["channel"],
            "text": m["text"], "probs": p, "sarcasm": p_s, "severity": sev, "seriousness": ser,
            "actions": actions, "redacted": redacted, "thresholds": tox.thresholds
        }
        results.append(result)

        # pretty print small summary
        tops = ", ".join([f"{k}={v:.2f}{'✓' if v>=tox.thresholds.get(k,0.5) else ''}"
                          for k,v in sorted(p.items(), key=lambda kv:-kv[1])[:3]])
        print(f"[{m['channel']}] {m['user_id']} — {m['text']}")
        print(f"  tox: {tops}")
        print(f"  sarcasm: {p_s:.2f} | severity: {sev:.2f} | seriousness: {ser:.2f} → actions: {actions}\n")

    write_digest(results)
    conn.close()

if __name__ == "__main__":
    main()
