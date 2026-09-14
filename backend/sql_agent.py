"""
sql_agent.py — answer free-form questions by generating read-only SQL.

The model never receives database credentials or a connection. It is given the
schema and the question, and returns a single SELECT; this module validates the
statement and executes it inside a read-only, time-limited transaction. Results
are then handed back to the model to be phrased as an answer.

Trust boundary: the generated SQL is untrusted input. `validate_sql` is the
static gate and the read-only transaction is the enforcement of last resort.
"""
import json
import math
import os
import re
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import requests as http_requests

from database import engine

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama3-70b-8192"]

MAX_ROWS = 200            # hard cap on rows returned by any generated query
ROWS_SHOWN_TO_MODEL = 60  # rows forwarded to the phrasing step
STATEMENT_TIMEOUT_MS = 10000
SQL_ATTEMPTS = 3          # first try plus two repair attempts
SCHEMA_CACHE_TTL = 300

ALLOWED_TABLES = {"posts", "follower_snapshots"}

# Whole-word tokens that have no business in a read-only analytical query.
FORBIDDEN_TOKENS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|COPY|VACUUM|"
    r"ATTACH|DETACH|PRAGMA|EXEC|EXECUTE|CALL|MERGE|UPSERT|REPLACE|INTO|LOCK|"
    r"REINDEX|REFRESH|LISTEN|NOTIFY|SET|RESET|BEGIN|COMMIT|ROLLBACK|SAVEPOINT)\b",
    re.IGNORECASE,
)
TABLE_REFERENCE = re.compile(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
CTE_NAME = re.compile(r"(?:WITH|,)\s+([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(", re.IGNORECASE)

_schema_cache: Dict[str, Any] = {"value": None, "at": 0.0}


class SqlAgentError(Exception):
    """Raised when a question cannot be answered with a safe query."""


# -- SQL validation -----------------------------------------------------------
def strip_sql_fences(raw: str) -> str:
    sql = (raw or "").strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1]
        sql = sql.rsplit("```", 1)[0]
    return sql.strip().rstrip(";").strip()


def strip_string_literals(sql: str) -> str:
    """Blank out quoted literals so keyword scanning ignores post text.

    Without this, a legitimate search such as WHERE title LIKE '%call center%'
    would trip the CALL keyword check.
    """
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


def validate_sql(raw: str) -> str:
    """Return an execution-safe SELECT, or raise SqlAgentError.

    Rejects anything that is not a single read-only statement over the allowed
    tables, then wraps the query so the row cap applies regardless of whether
    the model wrote its own LIMIT.
    """
    sql = strip_sql_fences(raw)
    if not sql:
        raise SqlAgentError("The generated query was empty.")

    # Keyword and table checks run against a literal-free copy; the original is
    # what executes.
    scanned = strip_string_literals(sql)
    if ";" in scanned:
        raise SqlAgentError("Only a single statement is allowed; remove the semicolon.")
    if "--" in scanned or "/*" in scanned:
        raise SqlAgentError("SQL comments are not allowed.")
    if not re.match(r"^\s*(SELECT|WITH)\b", scanned, re.IGNORECASE):
        raise SqlAgentError("Only SELECT queries are allowed.")

    forbidden = FORBIDDEN_TOKENS.search(scanned)
    if forbidden:
        raise SqlAgentError("The keyword %s is not allowed." % forbidden.group(1).upper())

    cte_names = {name.lower() for name in CTE_NAME.findall(scanned)}
    for table in TABLE_REFERENCE.findall(scanned):
        if table.lower() not in ALLOWED_TABLES | cte_names:
            raise SqlAgentError(
                "Table '%s' is not available. Allowed tables: %s."
                % (table, ", ".join(sorted(ALLOWED_TABLES)))
            )

    return "SELECT * FROM (\n%s\n) AS agent_result LIMIT %d" % (sql, MAX_ROWS)


# -- Execution ----------------------------------------------------------------
def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return "<binary>"
    return str(value)


def run_readonly(sql: str) -> List[Dict[str, Any]]:
    """Execute validated SQL in a transaction that is rolled back either way."""
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if connection.dialect.name == "postgresql":
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                connection.exec_driver_sql(
                    "SET LOCAL statement_timeout = %d" % STATEMENT_TIMEOUT_MS
                )
            result = connection.exec_driver_sql(sql)
            columns = list(result.keys())
            rows = result.fetchmany(MAX_ROWS)
            return [
                {column: _json_safe(value) for column, value in zip(columns, row)}
                for row in rows
            ]
        finally:
            transaction.rollback()


# -- Schema description -------------------------------------------------------
def _distinct_values(column: str, limit: int = 40) -> List[str]:
    try:
        rows = run_readonly(
            "SELECT * FROM (SELECT DISTINCT %s AS v FROM posts "
            "WHERE %s IS NOT NULL ORDER BY 1 LIMIT %d) AS d" % (column, column, limit)
        )
        return [str(row["v"]) for row in rows if str(row["v"]).strip()]
    except Exception:
        return []


def schema_doc() -> str:
    """Schema plus the vocabulary actually present, refreshed periodically."""
    now = time.time()
    if _schema_cache["value"] and now - _schema_cache["at"] < SCHEMA_CACHE_TTL:
        return _schema_cache["value"]

    platforms = _distinct_values("platform") or [
        "Facebook", "Instagram", "TikTok", "YouTube", "LinkedIn"
    ]
    formats = _distinct_values("format")

    doc = """Database dialect: %s

TABLE posts -- one row per published post
  id               TEXT primary key
  platform         TEXT   values present: %s
  format           TEXT   content format; values present: %s
  collab           TEXT   collaboration partner, often empty
  date             TIMESTAMP  when the post was published
  title            TEXT   post caption or title
  link             TEXT   permalink
  reach            FLOAT  reported reach; not deduplicated people
  views            FLOAT
  engagement       FLOAT  total interactions
  likes            FLOAT
  comments         FLOAT
  shares           FLOAT
  favorites        FLOAT
  reposts          FLOAT
  impressions      FLOAT
  watch_time_hours FLOAT
  engagement_rate  FLOAT  per-post engagement rate, already a percentage
  is_organic       BOOLEAN  true = organic, false = paid
  created_at       TIMESTAMP  row insert time, NOT the publish date

TABLE follower_snapshots -- daily follower counts per platform
  platform      TEXT
  followers     INTEGER
  provider      TEXT   data source
  snapshot_date DATE
  observed_at   TIMESTAMP
  refreshed_at  TIMESTAMP

Semantics that matter:
- Always filter on posts.date for when a post was published. Never use created_at.
- Instagram Stories are stored as platform='Instagram' with a story format
  (lower(format) in ('ig story','instagram story','story')). They are excluded
  from standard performance totals, so exclude them unless asked about stories.
- Organic means is_organic = true.
- engagement_rate is already a percentage; never multiply it by 100.
- For an aggregate engagement rate use SUM(engagement) / NULLIF(SUM(reach),0) * 100,
  not AVG(engagement_rate), unless the question asks for the average of post rates.
- follower_snapshots is independent of posts; its dates need not overlap the post
  date range, so never constrain follower queries to the posts' date span.
""" % (
        engine.dialect.name,
        ", ".join(platforms),
        ", ".join(formats) if formats else "(none loaded)",
    )
    _schema_cache.update({"value": doc, "at": now})
    return doc


# -- Groq ---------------------------------------------------------------------
def _groq_json(api_key: str, messages: List[Dict[str, str]], max_tokens: int) -> Dict[str, Any]:
    headers = {"Authorization": "Bearer %s" % api_key, "Content-Type": "application/json"}
    last_error = "no model attempted"
    for model in GROQ_MODELS:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            response = http_requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        except http_requests.RequestException as exc:
            last_error = type(exc).__name__
            continue
        if response.status_code != 200:
            last_error = "HTTP %d" % response.status_code
            continue
        try:
            return json.loads(response.json()["choices"][0]["message"]["content"])
        except (KeyError, ValueError) as exc:
            last_error = "unparsable response (%s)" % type(exc).__name__
            continue
    raise SqlAgentError("No Groq model answered. Last error: %s" % last_error)


def _history_text(history: List[Dict[str, str]]) -> str:
    if not history:
        return "(none)"
    return "\n".join("%s: %s" % (item["role"], item["content"]) for item in history[-6:])


def generate_sql(api_key: str, question: str, history: List[Dict[str, str]],
                 hints: Dict[str, Any], previous_error: Optional[str],
                 previous_sql: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Ask the model for one SELECT. Returns (sql, refusal_reason)."""
    repair = ""
    if previous_error:
        repair = (
            "\nYour previous query failed and must be corrected.\n"
            "Previous SQL: %s\nError: %s\n" % (previous_sql, previous_error)
        )
    prompt = """%s

Dashboard the user is currently viewing (context only -- the question wins;
ignore these if the question names its own period or platform):
  date range: %s to %s
  platform tab: %s

Recent conversation:
%s

Question: %s
%s
Rules:
- One SELECT statement. No semicolon, no comments.
- Only the tables posts and follower_snapshots.
- Never INSERT, UPDATE, DELETE, or any other write.
- Use syntax valid for the dialect stated above.
- Select the columns needed to answer, including identifying ones such as title,
  platform and date, so the answer can name specific posts.
- Order and LIMIT deliberately; the result is capped at %d rows.
- Resolve relative dates against the dashboard range when the question is relative.

Reply with JSON:
  {"sql": "SELECT ..."}
or, only if no query over this schema could answer it:
  {"sql": null, "reason": "<short explanation>"}""" % (
        schema_doc(),
        hints.get("start_date") or "not set",
        hints.get("end_date") or "not set",
        hints.get("platform") or "all platforms",
        _history_text(history),
        question,
        repair,
        MAX_ROWS,
    )
    messages = [
        {"role": "system", "content":
            "You translate questions about a social media analytics database into a single "
            "read-only SQL SELECT. Reply only with JSON."},
        {"role": "user", "content": prompt},
    ]
    output = _groq_json(api_key, messages, max_tokens=900)
    sql = output.get("sql")
    if not sql:
        return None, str(output.get("reason") or "That question cannot be answered from this database.")
    return str(sql), None


def phrase_answer(api_key: str, question: str, history: List[Dict[str, str]],
                  sql: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    shown = rows[:ROWS_SHOWN_TO_MODEL]
    prompt = """Question: %s

Recent conversation:
%s

SQL that was run:
%s

Results (%d row(s)%s):
%s

Write the answer for a client-facing analyst.
- Use only numbers present in the results. Do not estimate or invent.
- If the result set is empty, say plainly that no rows matched and say what was
  searched, so the user can adjust the period or platform.
- If the user asks about your previous statement or how you work, answer that
  directly and conversationally; do not repeat a canned refusal.
- Reach is not deduplicated people. engagement_rate is already a percentage.
- Plain paragraphs or short bullets. No markdown tables.

Reply with JSON:
  {"reply": "<answer>", "suggested_questions": ["<q1>", "<q2>", "<q3>"]}""" % (
        question,
        _history_text(history),
        sql,
        len(rows),
        ", truncated for display" if len(rows) > len(shown) else "",
        json.dumps(shown, ensure_ascii=False)[:14000],
    )
    messages = [
        {"role": "system", "content":
            "You are CIMB Dashboard Analyst. Answer from the query results only. "
            "Reply only with JSON."},
        {"role": "user", "content": prompt},
    ]
    output = _groq_json(api_key, messages, max_tokens=900)
    reply = str(output.get("reply") or "").strip()
    if not reply:
        raise SqlAgentError("The model returned an empty answer.")
    suggestions = output.get("suggested_questions")
    if not isinstance(suggestions, list):
        suggestions = []
    return {
        "reply": reply,
        "suggested_questions": [str(item) for item in suggestions if str(item).strip()][:3],
    }


# -- Orchestration ------------------------------------------------------------
def answer_question(question: str, history: List[Dict[str, str]],
                    hints: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise SqlAgentError("The AI chat is not configured: GROQ_API_KEY is not set.")

    error: Optional[str] = None
    raw_sql: Optional[str] = None
    for _ in range(SQL_ATTEMPTS):
        raw_sql, refusal = generate_sql(api_key, question, history, hints, error, raw_sql)
        if refusal:
            return {"reply": refusal, "suggested_questions": [], "sql": None, "row_count": 0}
        try:
            safe_sql = validate_sql(raw_sql)
            rows = run_readonly(safe_sql)
        except SqlAgentError as exc:
            error = str(exc)
            continue
        except Exception as exc:
            error = "%s: %s" % (type(exc).__name__, str(exc)[:300])
            continue
        answer = phrase_answer(api_key, question, history, raw_sql, rows)
        answer.update({"sql": raw_sql, "row_count": len(rows)})
        return answer

    raise SqlAgentError("Could not build a working query for that question. Last error: %s" % error)
