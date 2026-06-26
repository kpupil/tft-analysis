"""种子玩家采集：从各区域宗师和王者榜单拿 PUUID。

对应 tftchamp 的「榜单种子」思路：高分段对局质量高，meta 信号最干净。
种子直接写入数据库，后续 discovery 从数据库读取。
"""
import asyncio

from app.collector.repository import upsert_seed_players
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.riot_client import RiotClient

TOP_TIER_LOADERS = (
    ("CHALLENGER", "challenger_league"),
    ("GRANDMASTER", "grandmaster_league"),
)
TIER_ORDER = {"CHALLENGER": 0, "GRANDMASTER": 1}


def _player(entry: dict, tier: str, division: str = "I") -> dict | None:
    puuid = entry.get("puuid")
    if not puuid:
        return None
    return {
        "puuid": puuid,
        "tier": tier,
        "division": entry.get("rank") or division,
        "league_points": entry.get("leaguePoints", 0),
        "wins": entry.get("wins", 0),
        "losses": entry.get("losses", 0),
    }


async def _grandmaster_plus(client: RiotClient, platform: str) -> list[dict]:
    """拉取宗师和王者，并保留段位元数据。"""
    players: dict[str, dict] = {}

    for tier, method_name in TOP_TIER_LOADERS:
        league = await getattr(client, method_name)(platform)
        for entry in league.get("entries", []):
            player = _player(entry, tier)
            if player:
                # 榜单在采集期间可能发生晋级；保留先拉到的更高段位。
                players.setdefault(player["puuid"], player)

    return sorted(
        players.values(),
        key=lambda p: (TIER_ORDER[p["tier"]], -p["league_points"], p["puuid"]),
    )


async def collect_seeds() -> None:
    if settings.min_tier.upper() != "GRANDMASTER":
        raise ValueError("MIN_TIER 目前只支持 GRANDMASTER")

    init_db()
    client = RiotClient()
    try:
        for platform in settings.region_list:
            players = await _grandmaster_plus(client, platform)
            with SessionLocal() as session:
                saved = upsert_seed_players(
                    session,
                    platform=platform,
                    minimum_tier="GRANDMASTER",
                    players=players,
                )
            counts = {
                tier: sum(p["tier"] == tier for p in players)
                for tier in TIER_ORDER
            }
            print(
                f"[seed] {platform}: 写入种子 {saved} 人 | "
                f"C {counts['CHALLENGER']} / GM {counts['GRANDMASTER']}"
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(collect_seeds())
