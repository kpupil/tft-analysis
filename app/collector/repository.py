"""Database operations for the acquisition pipeline."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import MatchDiscovery, RawMatch, SeedPlayer
from app.core.riot_client import PLATFORM_TO_ROUTING

PATCH_RE = re.compile(r"<Releases/([^>]+)>")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def extract_patch(game_version: str | None) -> str | None:
    if not game_version:
        return None
    match = PATCH_RE.search(game_version)
    if match:
        return match.group(1)
    return None


def upsert_seed_players(
    session: Session,
    platform: str,
    minimum_tier: str,
    players: Iterable[dict],
) -> int:
    snapshot_at = now_utc()
    count = 0
    for player in players:
        puuid = player["puuid"]
        row = session.get(SeedPlayer, {"platform": platform, "puuid": puuid})
        if row is None:
            row = SeedPlayer(platform=platform, puuid=puuid, minimum_tier=minimum_tier)
            session.add(row)
        row.tier = player["tier"]
        row.division = player.get("division") or "I"
        row.league_points = player.get("league_points", 0)
        row.wins = player.get("wins", 0)
        row.losses = player.get("losses", 0)
        row.minimum_tier = minimum_tier
        row.last_seen_at = snapshot_at
        row.source_snapshot_at = snapshot_at
        count += 1
    session.commit()
    return count


def load_seed_puuids(session: Session, platform: str) -> list[str]:
    stmt = (
        select(SeedPlayer.puuid)
        .where(SeedPlayer.platform == platform)
        .order_by(SeedPlayer.tier, SeedPlayer.league_points.desc(), SeedPlayer.puuid)
    )
    return list(session.scalars(stmt))


def enqueue_match_ids(
    session: Session,
    platform: str,
    discovered_from_puuid: str,
    match_ids: Iterable[str],
) -> int:
    routing = PLATFORM_TO_ROUTING[platform]
    inserted = 0
    seen = set(match_ids)
    for match_id in seen:
        if session.get(RawMatch, match_id) is not None:
            continue
        if session.get(MatchDiscovery, match_id) is not None:
            continue
        session.add(
            MatchDiscovery(
                match_id=match_id,
                platform=platform,
                routing=routing,
                discovered_from_puuid=discovered_from_puuid,
            )
        )
        inserted += 1
    session.commit()
    return inserted


def load_fetch_candidates(session: Session, limit: int) -> list[MatchDiscovery]:
    now = now_utc()
    stmt = (
        select(MatchDiscovery)
        .where(
            MatchDiscovery.status.in_(("pending", "retry")),
            (MatchDiscovery.next_retry_at.is_(None) | (MatchDiscovery.next_retry_at <= now)),
        )
        .order_by(MatchDiscovery.discovered_at)
        .limit(limit)
    )
    return list(session.scalars(stmt))


def save_raw_match(
    session: Session,
    discovery: MatchDiscovery,
    detail: dict,
) -> None:
    save_raw_payload(
        session,
        match_id=discovery.match_id,
        platform=discovery.platform,
        routing=discovery.routing,
        detail=detail,
    )
    discovery.status = "fetched"
    discovery.last_error = None
    discovery.next_retry_at = None
    discovery.updated_at = now_utc()
    session.commit()


def save_raw_payload(
    session: Session,
    match_id: str,
    platform: str,
    routing: str,
    detail: dict,
) -> None:
    info = detail.get("info", {})
    queue_id = info.get("queue_id", info.get("queueId"))
    game_version = info.get("game_version")
    raw = RawMatch(
        match_id=match_id,
        platform=platform,
        routing=routing,
        queue_id=queue_id,
        tft_set_number=info.get("tft_set_number"),
        tft_set_core_name=info.get("tft_set_core_name"),
        game_version=game_version,
        patch=extract_patch(game_version),
        game_datetime=info.get("game_datetime") or info.get("gameCreation"),
        raw_json=detail,
    )
    session.merge(raw)


def mark_skipped(session: Session, discovery: MatchDiscovery, reason: str) -> None:
    discovery.status = "skipped"
    discovery.last_error = reason
    discovery.next_retry_at = None
    discovery.updated_at = now_utc()
    session.commit()


def mark_failed(session: Session, discovery: MatchDiscovery, error: str) -> None:
    discovery.attempts += 1
    discovery.last_error = error[:4000]
    discovery.updated_at = now_utc()
    if discovery.attempts >= 5:
        discovery.status = "failed"
        discovery.next_retry_at = None
    else:
        discovery.status = "retry"
        discovery.next_retry_at = now_utc() + timedelta(minutes=2 * discovery.attempts)
    session.commit()
