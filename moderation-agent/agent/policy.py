# Simple severity/seriousness + policy decisions
from typing import Dict, List, Tuple

def compute_seriousness(p: Dict[str, float], p_sarcasm: float,
                        recent_user: List[float], recent_chan: List[float]) -> Tuple[float, float]:
    # base severity from toxicity only
    severity = max(
        0.80 * p.get("threat", 0.0),
        0.75 * p.get("severe_toxic", 0.0),
        0.70 * p.get("identity_hate", 0.0),
        0.55 * p.get("toxic", 0.0),
        0.50 * p.get("insult", 0.0),
        0.45 * p.get("obscene", 0.0),
    )
    u = sum(recent_user) / max(1, len(recent_user))
    c = sum(recent_chan) / max(1, len(recent_chan))
    banter_relief = 0.25 * p_sarcasm
    seriousness = max(0.0, min(1.0, severity + 0.10*u + 0.05*c - banter_relief))
    # safety overrides
    if p.get("threat", 0.0) >= 0.50 or p.get("severe_toxic", 0.0) >= 0.60:
        seriousness = max(seriousness, 0.80)
    return severity, seriousness

def decide(p: Dict[str, float], seriousness: float):
    if p.get("threat", 0.0) >= 0.50 or p.get("severe_toxic", 0.0) >= 0.60 or seriousness >= 0.65:
        return ["escalate", "redact"]
    if seriousness >= 0.45:
        return ["warn", "redact"]
    return ["log_only"]

def redact_text(text: str) -> str:
    # simple, safe redaction: mask vowels to remove sting without changing meaning too much
    trans = str.maketrans("aeiouAEIOU", "*"*10)
    return text.translate(trans)
