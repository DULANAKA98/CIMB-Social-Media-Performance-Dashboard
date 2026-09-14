"""Tests for the generated-SQL guardrails in sql_agent.

validate_sql is the static half of the trust boundary around model-written SQL,
so both what it accepts and what it rejects are covered here.
"""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory; no queries run here

from sql_agent import (  # noqa: E402
    MAX_ROWS,
    SqlAgentError,
    _json_safe,
    strip_sql_fences,
    strip_string_literals,
    validate_sql,
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


if __name__ == "__main__":
    unittest.main()
