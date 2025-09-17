from __future__ import annotations
import os, datetime as dt, hashlib, re
from sqlalchemy import select
from .db import SessionLocal, UserStats

THRESHOLDS = {
    "tox_high": float(os.getenv("TOX_HIGH", 0.65)),
    "sarcasm_low": float(os.getenv("SARCASM_LOW", 0.10)),
    "seriousness_high": float(os.getenv("SERIOUSNESS_HIGH", 0.30)),
}



CRISIS_PATTERNS = [
    r"\bi (?:want|going|plan) to (?:kill|hurt) (?:myself|me|him|her|them)\b",
    r"\b(?:suicide|kill myself|end my life)\b",
    r"\b(?:i(?:'m| am) (?:done|hopeless)|i can't go on)\b",
]
CRISIS_RE = re.compile("|".join(CRISIS_PATTERNS), re.IGNORECASE)


def seriousness_score(tox_max: float,sarcasm: float) -> float:
    return max(0.0, min(1.0, float(tox_max)))

# *(1.0 - float(sarcasm) )

# *


def anon_user_id(user_id: str, salt: str = "peer_salt") -> str:
    return hashlib.sha256(f"{user_id}|{salt}".encode()).hexdigest()[:16]





def record_violation(user_id_hash: str) -> int:
    with SessionLocal() as s:
        st = s.execute(select(UserStats).where(UserStats.user_id_hash == user_id_hash)).scalar_one_or_none()
        if not st:
            st = UserStats(user_id_hash=user_id_hash, violations=1)
            s.add(st); s.commit(); return st.violations
        st.violations += 1
        s.commit(); return st.violations


def mark_warned(user_id_hash: str):
    with SessionLocal() as s:
        st = s.execute(select(UserStats).where(UserStats.user_id_hash == user_id_hash)).scalar_one_or_none()
        if st and not st.warned:
            st.warned = True; s.commit()


def has_been_warned(user_id_hash: str) -> bool:
    with SessionLocal() as s:
        st = s.execute(select(UserStats).where(UserStats.user_id_hash == user_id_hash)).scalar_one_or_none()
        return bool(st and st.warned)


def is_crisis(text: str) -> bool:
    return bool(CRISIS_RE.search(text or ""))