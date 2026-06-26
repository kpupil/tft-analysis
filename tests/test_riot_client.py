import unittest
from unittest.mock import AsyncMock

from app.core.riot_client import RiotClient


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_match_requests_use_platform_routing(self):
        client = RiotClient()
        client._get = AsyncMock(return_value=[])
        try:
            cases = {
                "kr": "asia",
                "euw1": "europe",
                "na1": "americas",
            }
            for platform, routing in cases.items():
                await client.matches_by_puuid("player", platform, count=5)
                url = client._get.await_args.args[0]
                self.assertTrue(url.startswith(f"https://{routing}.api.riotgames.com/"))
        finally:
            await client.close()

