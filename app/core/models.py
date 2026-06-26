"""Collector database models.

This layer intentionally stores only acquisition state and raw Riot payloads.
Analysis tables can be added later without changing the fetch pipeline.
"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SeedPlayer(Base):
    __tablename__ = "seed_players"

    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    puuid: Mapped[str] = mapped_column(String(128), primary_key=True)
    tier: Mapped[str] = mapped_column(String(32), nullable=False)
    division: Mapped[str] = mapped_column(String(8), nullable=False, default="I")
    league_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minimum_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MatchDiscovery(Base):
    __tablename__ = "match_discovery"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    routing: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    discovered_from_puuid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class RawMatch(Base):
    __tablename__ = "raw_matches"

    match_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    routing: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    queue_id: Mapped[int | None] = mapped_column(Integer, index=True)
    tft_set_number: Mapped[int | None] = mapped_column(Integer, index=True)
    tft_set_core_name: Mapped[str | None] = mapped_column(String(64), index=True)
    game_version: Mapped[str | None] = mapped_column(Text)
    patch: Mapped[str | None] = mapped_column(String(32), index=True)
    game_datetime: Mapped[int | None] = mapped_column(BigInteger, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
