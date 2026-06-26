"""Riot API 异步客户端。dev/prod 通用——只读 config 的 key 与限流参数。

封装了：限流(acquire) + 重试(429/5xx 指数退避) + 路由。
TFT 相关端点：tft-league-v1 / account-v1 / tft-match-v1。
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.core.rate_limiter import limiter

# region(平台) → match-v1 大区路由
PLATFORM_TO_ROUTING = {
    "na1": "americas", "br1": "americas", "la1": "americas", "la2": "americas",
    "euw1": "europe", "eun1": "europe", "tr1": "europe", "ru": "europe",
    "kr": "asia", "jp1": "asia",
    "oc1": "sea", "ph2": "sea", "sg2": "sea", "th2": "sea", "tw2": "sea", "vn2": "sea",
}


class RiotClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            timeout=15,
            headers={"X-Riot-Token": settings.riot_api_key},
        )

    async def close(self):
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _get(self, url: str) -> dict | list:
        await limiter.acquire()
        resp = await self._client.get(url)
        if resp.status_code == 429:
            # 尊重 Retry-After，再交给 tenacity 退避重试
            raise httpx.HTTPStatusError("rate limited", request=resp.request, response=resp)
        resp.raise_for_status()
        return resp.json()

    # --- tft-league-v1：拿榜单种子 ---
    async def challenger_league(self, platform: str) -> dict:
        url = f"https://{platform}.api.riotgames.com/tft/league/v1/challenger"
        return await self._get(url)

    async def grandmaster_league(self, platform: str) -> dict:
        url = f"https://{platform}.api.riotgames.com/tft/league/v1/grandmaster"
        return await self._get(url)

    async def master_league(self, platform: str) -> dict:
        url = f"https://{platform}.api.riotgames.com/tft/league/v1/master"
        return await self._get(url)

    async def league_entries(
        self, platform: str, tier: str, division: str, page: int = 1
    ) -> list[dict]:
        url = (f"https://{platform}.api.riotgames.com/tft/league/v1/entries/"
               f"{tier}/{division}?page={page}")
        return await self._get(url)

    # --- tft-summoner / account：summonerId/PUUID 互转（按需）---
    async def matches_by_puuid(
        self, puuid: str, platform: str, count: int = 20
    ) -> list[str]:
        routing = PLATFORM_TO_ROUTING[platform]
        url = (f"https://{routing}.api.riotgames.com/tft/match/v1/matches/"
               f"by-puuid/{puuid}/ids?count={count}")
        return await self._get(url)

    # --- tft-match-v1：单局详情 ---
    async def match_detail(self, match_id: str, platform: str) -> dict:
        routing = PLATFORM_TO_ROUTING[platform]
        url = f"https://{routing}.api.riotgames.com/tft/match/v1/matches/{match_id}"
        return await self._get(url)
