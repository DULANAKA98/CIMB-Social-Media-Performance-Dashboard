import os
import unittest

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

from data_processor import process_data  # noqa: E402

EMPTY = pd.DataFrame()


def facebook(rows):
    return process_data(pd.DataFrame(rows), EMPTY, EMPTY, EMPTY, EMPTY, ig_story=EMPTY)


BASE = {"Publish time": "10/01/2026 10:00", "Permalink": "https://www.facebook.com/x/posts/1",
        "Views": "1000", "Reactions, comments and shares": "50", "Comments": "5", "Shares": "5"}


class FacebookUploadTests(unittest.TestCase):
    def test_new_export_uses_viewers_and_boosted_views(self):
        records = facebook([
            {**BASE, "Viewers": "800", "Views from Boosted posts": "3893762", "Funded content status": ""},
            {**BASE, "Permalink": "https://www.facebook.com/x/posts/2", "Viewers": "600",
             "Views from Boosted posts": "0", "Funded content status": ""},
        ])
        self.assertEqual([r["reach"] for r in records], [800, 600])
        self.assertEqual([r["is_organic"] for r in records], [False, True])

    def test_old_export_keeps_reach_split_rule(self):
        records = facebook([
            {**BASE, "Reach": "900", "Reach from Organic posts": "900", "Lifetime Post Paid Reach": "0"},
            {**BASE, "Permalink": "https://www.facebook.com/x/posts/2", "Reach": "900",
             "Reach from Organic posts": "300", "Lifetime Post Paid Reach": "600"},
        ])
        self.assertEqual([r["reach"] for r in records], [900, 900])
        self.assertEqual([r["is_organic"] for r in records], [True, False])

    def test_organic_paid_column_overrides_everything(self):
        records = facebook([{**BASE, "Viewers": "800", "Views from Boosted posts": "5000", "Organic/Paid": "Organic"}])
        self.assertTrue(records[0]["is_organic"])


if __name__ == "__main__":
    unittest.main()
