"""Tests for the generated-SQL guardrails in sql_agent.

validate_sql is the static half of the trust boundary around model-written SQL,
so both what it accepts and what it rejects are covered here.
"""
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory; no queries run here

from sql_agent import (  # noqa: E402
    MAX_ROWS,
    SqlAgentError,
    _json_safe,
    _llm_json,
    answer_question,
    strip_sql_fences,
    strip_string_literals,
    validate_sql,
    worker_sql_url,
)


class ValidateSqlAccepts(unittest.TestCase):
    def test_plain_select_is_wrapped_with_the_row_cap(self):
        out = validate_sql("SELECT title FROM posts")
        self.assertIn("SELECT title FROM posts", out)
        self.assertTrue(out.rstrip().endswith("LIMIT %d" % MAX_ROWS))

    def test_cte_is_allowed_and_its_name_is_not_treated_as_a_table(self):
        sql = ("WITH monthly AS (SELECT platform, SUM(engagement) e FROM posts GROUP BY platform) "
               "SELECT * FROM monthly ORDER BY e DESC")
        self.assertIn("monthly", validate_sql(sql))

    def test_model_limit_is_kept_and_still_capped_by_the_wrapper(self):
        out = validate_sql("SELECT title FROM posts ORDER BY engagement DESC LIMIT 5")
        self.assertIn("LIMIT 5", out)
        self.assertTrue(out.rstrip().endswith("LIMIT %d" % MAX_ROWS))

    def test_follower_snapshots_is_allowed(self):
        self.assertIn("follower_snapshots", validate_sql(
            "SELECT platform, followers FROM follower_snapshots"))

    def test_keyword_inside_a_string_literal_is_not_rejected(self):
        # The literal contains CALL, SET and DROP, none of which are statements.
        out = validate_sql(
            "SELECT title FROM posts WHERE title LIKE '%call center drop set%'")
        self.assertIn("call center drop set", out)

    def test_markdown_fences_are_stripped(self):
        self.assertIn("SELECT 1 FROM posts",
                      validate_sql("```sql\nSELECT 1 FROM posts\n```"))

    def test_extract_from_date_is_not_mistaken_for_a_table(self):
        sql = (
            "SELECT title, engagement FROM posts "
            "WHERE platform = 'TikTok' "
            "AND EXTRACT(MONTH FROM date) = 5 "
            "AND EXTRACT(YEAR FROM date) = 2026 "
            "ORDER BY engagement DESC LIMIT 1"
        )
        self.assertIn("EXTRACT(MONTH FROM date)", validate_sql(sql))

    def test_public_schema_on_allowed_table_is_accepted(self):
        self.assertIn("public.posts", validate_sql("SELECT title FROM public.posts"))


class ValidateSqlRejects(unittest.TestCase):
    def assert_rejected(self, sql):
        with self.assertRaises(SqlAgentError):
            validate_sql(sql)

    def test_writes(self):
        for sql in (
            "INSERT INTO posts (id) VALUES ('x')",
            "UPDATE posts SET reach = 0",
            "DELETE FROM posts",
            "DROP TABLE posts",
            "ALTER TABLE posts ADD COLUMN x TEXT",
            "TRUNCATE posts",
        ):
            with self.subTest(sql=sql):
                self.assert_rejected(sql)

    def test_write_smuggled_after_a_select(self):
        self.assert_rejected("SELECT 1 FROM posts; DROP TABLE posts")

    def test_select_into_is_a_write(self):
        self.assert_rejected("SELECT * INTO copy_of_posts FROM posts")

    def test_comments(self):
        self.assert_rejected("SELECT 1 FROM posts -- sneaky")
        self.assert_rejected("SELECT 1 /* sneaky */ FROM posts")

    def test_table_outside_the_allowlist(self):
        self.assert_rejected("SELECT * FROM ai_reports")
        self.assert_rejected("SELECT * FROM pg_shadow")

    def test_join_onto_a_disallowed_table(self):
        self.assert_rejected(
            "SELECT p.title FROM posts p JOIN pg_user u ON true")

    def test_disallowed_schema_is_rejected(self):
        self.assert_rejected("SELECT * FROM auth.users")

    def test_sensitive_functions_are_rejected(self):
        self.assert_rejected("SELECT pg_read_file('/etc/passwd') FROM posts LIMIT 1")

    def test_transaction_control(self):
        self.assert_rejected("SELECT 1 FROM posts ROLLBACK")

    def test_empty(self):
        self.assert_rejected("")
        self.assert_rejected("```\n```")


class Helpers(unittest.TestCase):
    def test_strip_string_literals_blanks_content_but_keeps_structure(self):
        self.assertEqual(
            strip_string_literals("WHERE a = 'drop' AND b = 'x'"),
            "WHERE a = '' AND b = ''",
        )

    def test_strip_string_literals_handles_escaped_quotes(self):
        self.assertEqual(strip_string_literals("WHERE a = 'it''s drop'"), "WHERE a = ''")

    def test_strip_sql_fences_removes_trailing_semicolon(self):
        self.assertEqual(strip_sql_fences("SELECT 1;"), "SELECT 1")

    def test_json_safe_normalises_awkward_values(self):
        self.assertIsNone(_json_safe(float("nan")))
        self.assertIsNone(_json_safe(float("inf")))
        self.assertEqual(_json_safe(3), 3)
        self.assertEqual(_json_safe("x"), "x")

    def test_json_safe_serialises_dates(self):
        from datetime import datetime
        self.assertEqual(_json_safe(datetime(2026, 5, 1, 9, 30)), "2026-05-01T09:30:00")


class ProviderSelection(unittest.TestCase):
    """The Cloudflare Worker is the primary provider; Groq is optional."""

    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("CIMB_INSIGHTS_URL", "CIMB_INSIGHTS_KEY", "GROQ_API_KEY")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_worker_url_is_derived_from_the_insights_url(self):
        os.environ["CIMB_INSIGHTS_URL"] = "https://example.workers.dev/insights"
        os.environ["CIMB_INSIGHTS_KEY"] = "k"
        self.assertEqual(worker_sql_url(), "https://example.workers.dev/sql")

    def test_worker_url_requires_both_url_and_key(self):
        os.environ["CIMB_INSIGHTS_URL"] = "https://example.workers.dev/insights"
        self.assertIsNone(worker_sql_url())

    def test_worker_url_rejects_non_https(self):
        os.environ["CIMB_INSIGHTS_URL"] = "http://example.workers.dev/insights"
        os.environ["CIMB_INSIGHTS_KEY"] = "k"
        self.assertIsNone(worker_sql_url())

    def test_unconfigured_error_names_both_providers(self):
        with self.assertRaises(SqlAgentError) as caught:
            _llm_json([{"role": "user", "content": "hi"}], 10)
        message = str(caught.exception)
        self.assertIn("CIMB_INSIGHTS_URL", message)
        self.assertIn("GROQ_API_KEY", message)


class ConversationRouting(unittest.TestCase):
    @patch("sql_agent._llm_json")
    def test_casual_message_returns_natural_reply_without_query(self, model):
        model.return_value = {
            "action": "respond",
            "sql": None,
            "reply": "Hey! I can dig into posts, platforms, performance, or follower trends. What are you curious about?",
            "suggested_questions": ["What did best in May 2026?"],
        }
        result = answer_question("hey, what can you do?", [], {})
        self.assertIsNone(result["sql"])
        self.assertEqual(result["row_count"], 0)
        self.assertIn("I can dig into", result["reply"])


if __name__ == "__main__":
    unittest.main()
