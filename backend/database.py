"""
database.py — SQLAlchemy setup and table definitions.
"""
from sqlalchemy import create_engine, Column, String, Float, Boolean, Date, DateTime, Text, Integer, BigInteger, UniqueConstraint, text
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
    collab       = Column(Text, default="")
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
    campaign     = Column(Text, nullable=True, index=True)   # campaigns.name; empty when not in a campaign
    external_id  = Column(Text, nullable=True, index=True)   # platform's own post ID (Meta "Post ID" for Facebook)
    created_at   = Column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(Text, nullable=False, unique=True)
    hashtag    = Column(Text, default="")      # stored without '#', matched case-insensitively in captions
    image      = Column(Text, default="")      # data:image/... URL, resized in the browser before upload
    created_at = Column(DateTime, default=datetime.utcnow)


class YoutubeFormat(Base):
    """Whether a YouTube video is a Short, as decided by youtube.com/shorts/<id>; checked once per video."""
    __tablename__ = "youtube_formats"

    video_id   = Column(String, primary_key=True)
    format     = Column(String, nullable=False)   # 'Shorts' or 'Video'
    checked_at = Column(DateTime, default=datetime.utcnow)


class AiReport(Base):
    __tablename__ = "ai_reports"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    report_type     = Column(String, nullable=False, index=True)   # 'executive', 'strategy'
    start_date      = Column(String)
    end_date        = Column(String)
    content         = Column(Text, nullable=False)                  # JSON string
    created_at      = Column(DateTime, default=datetime.utcnow)


class FollowerSnapshot(Base):
    __tablename__ = "follower_snapshots"
    __table_args__ = (UniqueConstraint("platform", "snapshot_date", name="uq_follower_platform_date"),)

    id            = Column(BigInteger, primary_key=True, autoincrement=True)
    platform      = Column(String, nullable=False)
    followers     = Column(Integer, nullable=False)
    provider      = Column(String, nullable=False)
    snapshot_date = Column(Date, nullable=False, index=True)
    observed_at   = Column(DateTime(timezone=True), nullable=False)
    refreshed_at  = Column(DateTime(timezone=True), nullable=False)


def init_db():
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS collab TEXT DEFAULT ''"))
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS campaign TEXT"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_campaign ON posts (campaign)"))
        connection.execute(text("ALTER TABLE posts ADD COLUMN IF NOT EXISTS external_id TEXT"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_posts_external_id ON posts (external_id)"))


def get_db():
    """FastAPI dependency — yields a DB session and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
