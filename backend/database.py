"""
database.py — SQLAlchemy setup and table definitions.
"""
from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, Text, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Post(Base):
    __tablename__ = "posts"

    id           = Column(String, primary_key=True, index=True)
    platform     = Column(String, nullable=False, index=True)
    format       = Column(String)
    date         = Column(DateTime, index=True)
    title        = Column(Text)
    link         = Column(Text)
    reach        = Column(Float, default=0)
    views        = Column(Float, default=0)
    engagement   = Column(Float, default=0)
    likes        = Column(Float, default=0)
    comments     = Column(Float, default=0)
    shares       = Column(Float, default=0)
    favorites    = Column(Float, default=0)
    reposts      = Column(Float, default=0)
    impressions  = Column(Float, default=0)
    watch_time_hours = Column(Float, default=0)
    engagement_rate = Column(Float, default=0)
    is_organic   = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class AiReport(Base):
    __tablename__ = "ai_reports"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    report_type     = Column(String, nullable=False, index=True)   # 'executive', 'strategy'
    start_date      = Column(String)
    end_date        = Column(String)
    content         = Column(Text, nullable=False)                  # JSON string
    created_at      = Column(DateTime, default=datetime.utcnow)


def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a DB session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
