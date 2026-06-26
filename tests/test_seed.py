import unittest

from app.collector.seed import _grandmaster_plus


class FakeLeagueClient:
    async def challenger_league(self, platform):
        return {"entries": [{"puuid": "c", "leaguePoints": 900}]}

    async def grandmaster_league(self, platform):
        return {"entries": [{"puuid": "gm", "leaguePoints": 500}]}

class GrandmasterPlusTests(unittest.IsolatedAsyncioTestCase):
    async def test_collects_all_tiers_and_deduplicates(self):
        players = await _grandmaster_plus(FakeLeagueClient(), "kr")

        self.assertEqual([p["puuid"] for p in players], ["c", "gm"])
        self.assertEqual(players[1]["tier"], "GRANDMASTER")
