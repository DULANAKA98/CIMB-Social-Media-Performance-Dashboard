import os
import unittest
from datetime import date
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from database import Base, FollowerHistory  # noqa: E402
from main import FOLLOWER_PLATFORMS, get_metricool_follower_growth  # noqa: E402


def metricool(youtube_days):
    result = {platform: [] for platform in FOLLOWER_PLATFORMS}
    result["YouTube"] = [{"month": day, "month_label": day, "followers": value, "provider": "Metricool",
                          "observed_at": f"{day}T12:00:00+08:00"} for day, value in youtube_days]
    return result, {"Instagram": "no data"}


class FollowerHistoryTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        for day, value in ((date(2025, 1, 1), 65604), (date(2025, 1, 2), 65613), (date(2026, 6, 1), 1)):
            self.db.add(FollowerHistory(platform="YouTube", day=day, followers=value, source="YouTube Studio"))
        self.db.commit()

    @patch("main._fetch_metricool_follower_history")
    def test_imported_history_wins_up_to_its_last_day_then_metricool(self, fetch):
        fetch.return_value = metricool([("2026-05-31", 69700), ("2026-06-01", 69800), ("2026-06-02", 69810)])
        result = get_metricool_follower_growth("2025-01-01", "2026-06-30", self.db)
        youtube = result["YouTube"]
        self.assertEqual([row["month"] for row in youtube], ["2025-01-01", "2025-01-02", "2026-06-01", "2026-06-02"])
        self.assertEqual(youtube[2]["followers"], 1)       # the imported value on its own last day
        self.assertEqual(youtube[-1]["provider"], "Metricool")  # Metricool only after the import ends
        self.assertEqual(youtube[0]["provider"], "YouTube Studio")
        self.assertEqual(result["Facebook"], [])

    @patch("main._fetch_metricool_follower_history")
    def test_history_alone_is_enough_when_metricool_has_nothing(self, fetch):
        fetch.return_value = metricool([])
        result = get_metricool_follower_growth("2025-01-01", "2025-01-31", self.db)
        self.assertEqual([row["followers"] for row in result["YouTube"]], [65604, 65613])
        self.assertEqual(result["_meta"]["coverage"], 1)


if __name__ == "__main__":
    unittest.main()
