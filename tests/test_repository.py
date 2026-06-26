import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.collector.repository import (
    enqueue_match_ids,
    extract_patch,
    load_fetch_candidates,
    save_raw_match,
    upsert_seed_players,
)
from app.core.database import Base
from app.core.models import MatchDiscovery, RawMatch, SeedPlayer


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    def test_seed_upsert_and_match_queue_dedupe(self):
        with self.Session() as session:
            saved = upsert_seed_players(
                session,
                "kr",
                "GRANDMASTER",
                [{"puuid": "p1", "tier": "CHALLENGER", "league_points": 1000}],
            )
            self.assertEqual(saved, 1)
            self.assertEqual(session.query(SeedPlayer).count(), 1)

            inserted = enqueue_match_ids(session, "kr", "p1", ["KR_1", "KR_1", "KR_2"])
            self.assertEqual(inserted, 2)
            self.assertEqual(session.query(MatchDiscovery).count(), 2)

            inserted_again = enqueue_match_ids(session, "kr", "p1", ["KR_1"])
            self.assertEqual(inserted_again, 0)

    def test_save_raw_match_marks_discovery_fetched(self):
        detail = {
            "metadata": {"match_id": "KR_1"},
            "info": {
                "queue_id": 1100,
                "tft_set_number": 17,
                "tft_set_core_name": "TFTSet17",
                "game_version": "Linux Version x [PUBLIC] <Releases/16.12>",
                "game_datetime": 1782235524365,
            },
        }
        with self.Session() as session:
            enqueue_match_ids(session, "kr", "p1", ["KR_1"])
            discovery = load_fetch_candidates(session, 10)[0]

            save_raw_match(session, discovery, detail)

            raw = session.get(RawMatch, "KR_1")
            self.assertEqual(raw.patch, "16.12")
            self.assertEqual(raw.queue_id, 1100)
            self.assertEqual(session.get(MatchDiscovery, "KR_1").status, "fetched")

    def test_extract_patch_handles_missing_release_marker(self):
        self.assertEqual(extract_patch("abc <Releases/16.12> def"), "16.12")
        self.assertIsNone(extract_patch("abc"))
        self.assertIsNone(extract_patch(None))


if __name__ == "__main__":
    unittest.main()
