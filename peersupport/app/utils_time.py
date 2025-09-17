import os, datetime as dt, pytz
TZ = pytz.timezone(os.getenv("TZ", "Asia/Kolkata"))

def now_utc() -> dt.datetime:
    return dt.datetime.utcnow()

def now_local() -> dt.datetime:
    return dt.datetime.now(TZ)
