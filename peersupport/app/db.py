from __future__ import annotations
import os, datetime as dt
from sqlalchemy import create_engine, Integer, String, Float, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Mapped, mapped_column

DB_URL = os.getenv("DATABASE_URL", "sqlite:///peersupport.db")
engine = create_engine(DB_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()

class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(16), default="discord")
    channel_id: Mapped[str] = mapped_column(String(64))
    user_id_hash: Mapped[str] = mapped_column(String(32))  # anonymized
    message_id: Mapped[str] = mapped_column(String(64))
    text_excerpt: Mapped[str] = mapped_column(Text)
    sarcasm: Mapped[float] = mapped_column(Float)
    tox_max: Mapped[float] = mapped_column(Float)
    seriousness: Mapped[float] = mapped_column(Float)
    action: Mapped[str] = mapped_column(String(16))  # serious|crisis|none
    reply: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.utcnow())

class ReportMeta(Base):
    __tablename__ = "report_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(64), unique=True)
    last_report_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.fromtimestamp(0))
    flagged_since_last: Mapped[int] = mapped_column(Integer, default=0)

class Cooldown(Base):
    __tablename__ = "cooldowns"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id_hash: Mapped[str] = mapped_column(String(32), unique=True)
    last_dm_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.fromtimestamp(0))

class UserStats(Base):
    __tablename__ = "user_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id_hash: Mapped[str] = mapped_column(String(32), unique=True)
    violations: Mapped[int] = mapped_column(Integer, default=0)
    warned: Mapped[bool] = mapped_column(Boolean, default=False)


def init_db():
    Base.metadata.create_all(engine)
