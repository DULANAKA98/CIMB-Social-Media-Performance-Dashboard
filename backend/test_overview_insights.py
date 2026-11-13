import json
import os
import unittest
from unittest.mock import Mock, patch

import pandas as pd

os.environ.setdefault("DATABASE_URL", "sqlite://")

import overview_insights  # noqa: E402
from main import get_executive_summary  # noqa: E402

ENV = {"CIMB_INSIGHTS_URL": "https://example.com/insights/cimb", "CIMB_INSIGHTS_KEY": "test-key"}


def row(platform, day, reach, engagement, rate, organic=True, fmt="IG reel", title="A post", collab=""):
    return {"platform": platform, "format": fmt, "date": pd.Timestamp(day), "title": title, "collab": collab,
            "reach": reach, "views": reach, "impressions": reach, "engagement": engagement,
            "engagement_rate": rate, "is_organic": organic}


def frame(rows):
    return pd.DataFrame(rows)


CURRENT = frame([
    row("Instagram", "2026-07-02", 4000, 400, 10.0),
    row("Instagram", "2026-07-09", 250000, 500, 0.2, organic=False),
    row("Instagram", "2026-07-16", 3000, 240, 8.0),
    row("Facebook", "2026-07-03", 2000, 120, 6.0, fmt="Photos"),
    row("Facebook", "2026-07-20", 1500, 60, 4.0, fmt="Photos"),
    row("Facebook", "2026-07-27", 1800, 90, 5.0, fmt="Photos"),
])
PREVIOUS = frame([
    row("Instagram", "2026-06-05", 5000, 300, 6.0),
    row("Facebook", "2026-06-12", 1000, 40, 4.0, fmt="Photos"),
])


def loader(start_date=None, end_date=None, **_):
    return PREVIOUS.copy() if str(start_date).startswith("2026-05") or str(start_date).startswith("2026-06") else CURRENT.copy()


def good_reply(facts):
    reach = f"{facts['totals']['reach']:,}"
    engagement = f"{facts['totals']['engagement']:,}"
    filler = " This suggests the audience responds to the content when it reaches them on its own merit, not through spend."
    points = [{"kind": "insight", "headline": f"Point {n}", "text": f"Total reach was {reach} with {engagement} engagements.{filler}"}
              for n in range(1, 4)]
    points.append({"kind": "decision", "headline": "Shift effort", "text": f"Move effort toward what earned {engagement} engagements.{filler}"})
    return {"insights": points}


class FactSheetTests(unittest.TestCase):
    def test_previous_period_is_the_same_length_just_before(self):
        self.assertEqual(overview_insights.previous_range("2026-07-01", "2026-07-31"), ("2026-05-31", "2026-06-30"))
        self.assertIsNone(overview_insights.previous_range(None, "2026-07-31"))
        self.assertIsNone(overview_insights.previous_range("2026-07-31", "2026-07-01"))

    def test_fact_sheet_compares_periods_and_never_says_campaign(self):
        facts = overview_insights.build_facts(
            "All platforms", "2026-07-01", "2026-07-31", overview_insights.records_from_frame(CURRENT),
            overview_insights.records_from_frame(PREVIOUS), ("2026-05-31", "2026-06-30"))
        self.assertEqual(facts["scope"], "All platforms")
        self.assertNotIn("campaign", json.dumps(facts).lower())
        change = facts["vs_previous_period"]
        self.assertEqual(change["previous_period"]["posts"], 2)
        self.assertEqual(change["posts_change_pct"], 200.0)
        self.assertTrue(facts["patterns_to_interpret"][0].startswith("Against the previous period"))
        self.assertEqual({p["name"] for p in facts["platforms"]}, {"Instagram", "Facebook"})

    def test_long_periods_use_months_not_twelve_weeks(self):
        rows = [row("Instagram", f"2026-{month:02d}-{day:02d}", 1000 * month, 50, 5.0)
                for month in range(1, 7) for day in (3, 10, 17, 24)]
        facts = overview_insights.build_facts("Instagram", "2026-01-01", "2026-06-30",
                                              overview_insights.records_from_frame(frame(rows)))
        self.assertNotIn("weekly", facts)
        self.assertEqual([m["month"] for m in facts["monthly"]], [f"2026-{m:02d}" for m in range(1, 7)])
        self.assertTrue(any(text.startswith("Peak reach month was 2026-06") for text in facts["patterns_to_interpret"]))

    def test_only_grounded_points_survive_three_insights_then_one_decision(self):
        facts = overview_insights.build_facts("All platforms", None, None, overview_insights.records_from_frame(CURRENT))
        reply = good_reply(facts)
        reply["insights"].insert(0, {"kind": "insight", "headline": "Made up", "text": "Reach hit 987,654,321 which is far more than anything in the fact sheet. This suggests the number was invented."})
        reply["insights"].append({"kind": "decision", "headline": "Second decision", "text": reply["insights"][-1]["text"]})
        points = overview_insights.clean_and_ground(reply, facts)
        self.assertEqual([p["kind"] for p in points], ["insight", "insight", "insight", "decision"])
        self.assertNotIn("Made up", [p["headline"] for p in points])


@patch.dict(os.environ, ENV)
class EndpointTests(unittest.TestCase):
    @patch("main.http_requests.post")
    @patch("main.sql_agent.worker_json")
    @patch("main.get_filtered_data", side_effect=loader)
    def test_strategic_points_fill_the_shape_the_panel_reads(self, _, worker_json, post):
        def answer(messages, max_tokens):
            facts = json.loads(messages[1]["content"].split("Fact sheet: ", 1)[1])
            return good_reply(facts)
        worker_json.side_effect = answer
        result = get_executive_summary("2026-07-01", "2026-07-31", None)
        self.assertEqual(len(result["key_highlights"]), 4)
        self.assertTrue(all(isinstance(text, str) and ": " in text for text in result["key_highlights"]))
        self.assertEqual(len(result["recommendations"]), 1)
        self.assertNotIn("fallback", result["_meta"])
        post.assert_not_called()  # the earlier Worker insights were not needed

    @patch("main.http_requests.post")
    @patch("main.sql_agent.worker_json")
    @patch("main.get_filtered_data", side_effect=loader)
    def test_a_selected_platform_is_the_only_data_the_ai_sees(self, _, worker_json, post):
        seen = []

        def answer(messages, max_tokens):
            seen.append(messages[1]["content"])
            return good_reply(json.loads(messages[1]["content"].split("Fact sheet: ", 1)[1]))
        worker_json.side_effect = answer
        get_executive_summary("2026-07-01", "2026-07-31", "Facebook")
        facts = json.loads(seen[0].split("Fact sheet: ", 1)[1])
        self.assertEqual([p["name"] for p in facts["platforms"]], ["Facebook"])
        self.assertEqual(facts["totals"]["posts"], 3)
        self.assertEqual(facts["vs_previous_period"]["previous_period"]["posts"], 1)
        self.assertNotIn("Instagram", seen[0].split("Fact sheet: ", 1)[1])
        self.assertIn("Talk only about Facebook", seen[0])

    @patch("main.http_requests.post")
    @patch("main.sql_agent.worker_json")
    @patch("main.get_filtered_data", side_effect=loader)
    def test_unusable_ai_reply_falls_back_to_the_earlier_insights(self, _, worker_json, post):
        worker_json.return_value = {"insights": [{"kind": "insight", "headline": "Short", "text": "Too short."}]}
        response = Mock(status_code=200)
        response.json.return_value = {"key_highlights": ["Earlier style insight"]}
        post.return_value = response
        result = get_executive_summary("2026-07-01", "2026-07-31", None)
        self.assertEqual(result["key_highlights"], ["Earlier style insight"])

    @patch("main.http_requests.post")
    @patch("main.sql_agent.worker_json", side_effect=RuntimeError("AI service down"))
    @patch("main.get_filtered_data", side_effect=loader)
    def test_ai_errors_fall_back_to_the_earlier_insights(self, _, worker_json, post):
        response = Mock(status_code=200)
        response.json.return_value = {"key_highlights": ["Earlier style insight"]}
        post.return_value = response
        result = get_executive_summary("2026-07-01", "2026-07-31", None)
        self.assertEqual(result["key_highlights"], ["Earlier style insight"])

    @patch("main.http_requests.post")
    @patch("main._strategic_overview_insights", side_effect=ValueError("bug in the new code"))
    @patch("main.get_filtered_data", side_effect=loader)
    def test_a_bug_in_the_new_path_cannot_break_the_panel(self, _, strategic, post):
        response = Mock(status_code=200)
        response.json.return_value = {"key_highlights": ["Earlier style insight"]}
        post.return_value = response
        result = get_executive_summary("2026-07-01", "2026-07-31", None)
        self.assertEqual(result["key_highlights"], ["Earlier style insight"])


class PillarChartTests(unittest.TestCase):
    @patch("main.get_filtered_data")
    def test_categories_are_the_stored_pillars_and_untagged_posts_are_left_out(self, filtered):
        from main import get_content_types
        rows = CURRENT.copy()
        rows["pillar"] = ["Brand", "Marketing", "Brand", "", "Security", "Brand"]
        filtered.return_value = rows
        result = get_content_types("2025-01-01", "2025-12-31")
        self.assertEqual(sorted(r["type"] for r in result["Overall"]), ["Brand", "Marketing", "Security"])
        self.assertEqual(sum(r["count"] for r in result["Overall"]), 5)
        rows["pillar"] = ""
        self.assertEqual(get_content_types("2026-01-01", "2026-01-31")["Overall"], [])


if __name__ == "__main__":
    unittest.main()
