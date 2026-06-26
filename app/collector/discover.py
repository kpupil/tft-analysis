"""Match discovery: seed PUUIDs -> queued match ids."""
import asyncio

from app.collector.repository import enqueue_match_ids, load_seed_puuids
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.riot_client import RiotClient


async def discover_matches() -> None:
    init_db()
    client = RiotClient()
    try:
        for platform in settings.region_list:
            with SessionLocal() as session:
                puuids = load_seed_puuids(session, platform)
            if not puuids:
                print(f"[discover] {platform}: 没有种子玩家，先跑 seed.py")
                continue

            inserted = discovered = 0
            for puuid in puuids:
                match_ids = await client.matches_by_puuid(
                    puuid,
                    platform,
                    count=settings.max_matches_per_player,
                )
                discovered += len(match_ids)
                with SessionLocal() as session:
                    inserted += enqueue_match_ids(session, platform, puuid, match_ids)

            print(
                f"[discover] {platform}: 种子 {len(puuids)} 人 | "
                f"发现 {discovered} 个 match id | 新入队 {inserted}"
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(discover_matches())
