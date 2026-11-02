import os
import tempfile
import unittest
from datetime import datetime

_db_dir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_db_dir, 'campaigns_test.db')}"

from fastapi.testclient import TestClient  # noqa: E402

import campaigns as helpers  # noqa: E402
from database import Base, Post, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402


def _post(post_id, platform, title, link, organic=True, **metrics):
    defaults = {"reach": 0, "views": 0, "impressions": 0, "engagement": 0, "engagement_rate": 0}
    return Post(id=post_id, platform=platform, format=metrics.pop("format", "Video"), title=title, link=link,
                date=metrics.pop("date", datetime(2026, 10, 5)), is_organic=organic, **{**defaults, **metrics})


class CampaignHelperTests(unittest.TestCase):
    def test_hashtag_matches_whole_tag_only(self):
        self.assertTrue(helpers.caption_has_hashtag("Jom! #HmmmDulu.", "hmmmdulu"))
        self.assertFalse(helpers.caption_has_hashtag("#hmmmdulu2024", "hmmmdulu"))
        self.assertEqual(helpers.normalize_hashtag(" #HmmmDulu "), "hmmmdulu")
        self.assertEqual(helpers.normalize_hashtag("two words"), "")

    def test_link_variants_match_and_page_ids_do_not(self):
        same = [
            ("https://www.instagram.com/reel/C9abc_12/?igsh=x", "instagram.com/p/C9abc_12"),
            ("https://youtu.be/dQw4w9WgXcQ", "https://www.youtube.com/shorts/dQw4w9WgXcQ"),
            ("https://www.facebook.com/100064123456/videos/987654321012/", "https://www.facebook.com/watch/?v=987654321012"),
        ]
        for left, right in same:
            self.assertTrue(helpers.post_link_keys(left) & helpers.post_link_keys(right), left)
        different = ("https://www.facebook.com/permalink.php?story_fbid=111111&id=100064",
                     "https://www.facebook.com/permalink.php?story_fbid=222222&id=100064")
        self.assertFalse(helpers.post_link_keys(different[0]) & helpers.post_link_keys(different[1]))

    def test_summary_uses_platform_exposure_and_post_level_er(self):
        summary = helpers.summarize([
            {"platform": "TikTok", "views": 100, "reach": 5, "engagement": 10, "engagement_rate": 10, "is_organic": True},
            {"platform": "Facebook", "reach": 50, "views": 80, "engagement": 5, "engagement_rate": 4, "is_organic": False},
        ])
        self.assertEqual(summary["reach"], 150)
        self.assertEqual(summary["avg_er"], 7)
        self.assertEqual(summary["paid_reach"], 50)
        self.assertIsNone(helpers.summarize([])["avg_er"])


class CampaignApiTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        db.add_all([
            _post("fb1", "Facebook", "Raya mood #HmmmDulu", "https://www.facebook.com/cimb/posts/111111", reach=1000, engagement=50),
            _post("ig1", "Instagram", "Same vibe #hmmmdulu!", "https://www.instagram.com/p/AAA111/", organic=False, reach=500, engagement=40),
            _post("tt1", "TikTok", "No tag here", "https://www.tiktok.com/@cimb/video/7400000000000000001", views=2000, engagement=100, engagement_rate=5),
            _post("tt2", "TikTok", "Other #hmmmdulu2024", "https://www.tiktok.com/@cimb/video/7400000000000000002", views=10, engagement=1, engagement_rate=10),
        ])
        db.commit()
        db.close()
        self.client = TestClient(app)

    def test_create_matches_hashtag_then_adds_by_link(self):
        created = self.client.post("/api/campaigns", json={"name": "Hmmm Dulu", "hashtag": "#HmmmDulu"})
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["matched"], 2)
        campaign = created.json()["campaign"]
        self.assertEqual(campaign["posts"], 2)
        self.assertEqual(campaign["paid_posts"], 1)

        added = self.client.post(f"/api/campaigns/{campaign['id']}/posts",
                                 json={"links": ["tiktok.com/@cimb/video/7400000000000000001?lang=en", "https://example.com/nope"]})
        self.assertEqual([row["id"] for row in added.json()["added"]], ["tt1"])
        self.assertEqual(added.json()["not_found"], ["https://example.com/nope"])

        detail = self.client.get(f"/api/campaigns/{campaign['id']}/posts").json()
        self.assertEqual({row["id"] for row in detail["posts"]}, {"fb1", "ig1", "tt1"})
        self.assertEqual(detail["campaign"]["reach"], 1000 + 500 + 2000)  # TikTok counts views

        listed = self.client.get("/api/campaigns", params={"platform": "TikTok"}).json()["campaigns"][0]
        self.assertEqual(listed["posts"], 1)

    def test_rename_moves_posts_and_delete_releases_them(self):
        campaign = self.client.post("/api/campaigns", json={"name": "Hmmm Dulu", "hashtag": "hmmmdulu"}).json()["campaign"]
        self.assertEqual(self.client.post("/api/campaigns", json={"name": "hmmm dulu", "hashtag": "x"}).status_code, 409)
        renamed = self.client.patch(f"/api/campaigns/{campaign['id']}", json={"name": "Raya 2026"}).json()
        self.assertEqual(renamed["campaign"]["posts"], 2)
        posts = self.client.get("/api/posts").json()["posts"]
        self.assertEqual({p["id"] for p in posts if p["campaign"] == "Raya 2026"}, {"fb1", "ig1"})

        self.assertEqual(self.client.delete(f"/api/campaigns/{campaign['id']}").json()["released_posts"], 2)
        self.assertTrue(all(p["campaign"] is None for p in self.client.get("/api/posts").json()["posts"]))

    def test_existing_assignment_is_not_overwritten(self):
        first = self.client.post("/api/campaigns", json={"name": "First", "hashtag": "hmmmdulu"}).json()
        second = self.client.post("/api/campaigns", json={"name": "Second", "hashtag": "hmmmdulu"}).json()
        self.assertEqual(first["matched"], 2)
        self.assertEqual(second["matched"], 0)
        self.assertEqual(second["in_other_campaigns"], 2)


if __name__ == "__main__":
    unittest.main()
