"""Strategic AI insights for the Executive Overview and each Platform Performance page.

Same approach as campaign_insights: the backend works out a fact sheet (splits, shares, ratios,
timeline, standout posts, change against the previous period) so the model explains what the
numbers mean without doing arithmetic. Every number in a returned point must appear in that fact
sheet; anything else is dropped. The reply keeps the shape the Key Insights panel already reads.
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import campaign_insights as base
import campaigns as helpers

POINTS = 4            # the Key Insights panel shows four lines
INSIGHTS = 3          # three insights, then one decision
MIN_POINTS = 3        # fewer than this is not worth showing; the caller falls back
MAX_TOKENS = 1000
MAX_WEEKS = 12        # longer periods are summarised by month


def records_from_frame(frame) -> List[Dict[str, Any]]:
    """Dashboard rows as plain records, with ISO dates, for the fact sheet."""
    records = []
    for row in frame.to_dict("records"):
        when = row.get("date")
        row["date"] = when.isoformat() if hasattr(when, "isoformat") and str(when) != "NaT" else None
        row["is_organic"] = None if row.get("is_organic") is None else bool(row["is_organic"])
        records.append(row)
    return records


def previous_range(start: Optional[str], end: Optional[str]) -> Optional[Tuple[str, str]]:
    """The period of the same length that ends the day before the selected one starts."""
    try:
        first, last = datetime.fromisoformat(start[:10]).date(), datetime.fromisoformat(end[:10]).date()
    except (TypeError, ValueError):
        return None
    if last < first:
        return None
    days = (last - first).days + 1
    return str(first - timedelta(days=days)), str(first - timedelta(days=1))


def _totals(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    reach = sum(helpers.exposure(r) for r in records)
    engagement = sum(base._num(r.get("engagement")) for r in records)
    paid = [r for r in records if r.get("is_organic") is False]
    return {"posts": len(records), "reach": int(reach), "engagement": int(engagement),
            "avg_er_pct": base._avg([base._num(r.get("engagement_rate")) for r in records]),
            "paid_posts": len(paid), "paid_share_of_reach_pct": base._pct(sum(helpers.exposure(r) for r in paid), reach)}


def _change(now: float, before: float) -> Optional[float]:
    return round(100 * (now - before) / before, 1) if before else None


def _rename(value: Any) -> Any:
    """The shared fact sheet was written for campaigns; here the whole is the selected period."""
    if isinstance(value, dict):
        return {key.replace("share_of_campaign_", "share_of_total_"): _rename(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rename(item) for item in value]
    if isinstance(value, str):
        return value.replace("campaign reach", "total reach").replace("of campaign", "of total")
    return value


def build_facts(scope: str, start: Optional[str], end: Optional[str], records: List[Dict[str, Any]],
                previous: Optional[List[Dict[str, Any]]] = None,
                previous_period: Optional[Tuple[str, str]] = None) -> Dict[str, Any]:
    facts = _rename(base.build_facts(scope, "", records))
    facts.pop("hashtag", None)
    facts["scope"] = facts.pop("campaign")
    facts["period"]["selected_start"], facts["period"]["selected_end"] = start or "", end or ""
    patterns = facts["patterns_to_interpret"]

    months = defaultdict(list)
    for record in records:
        if record.get("date"):
            months[record["date"][:7]].append(record)
    if facts["period"]["weeks_active"] > MAX_WEEKS and len(months) >= 2:
        # Twelve weeks cannot describe a longer period: switch the timeline to months.
        total_reach = sum(helpers.exposure(r) for r in records)
        total_eng = sum(base._num(r.get("engagement")) for r in records)
        keep = ("posts", "reach", "engagement", "avg_er_pct", "share_of_campaign_reach_pct")
        monthly = [_rename({"month": month, **{k: v for k, v in base._group(rows, total_reach, total_eng).items() if k in keep}})
                   for month, rows in sorted(months.items())]
        facts.pop("weekly", None)
        facts["monthly"] = monthly
        patterns = [text for text in patterns if not text.startswith("Peak reach week")]
        peak = max(monthly, key=lambda row: row["reach"])
        low = min(monthly, key=lambda row: row["reach"])
        rated = [row for row in monthly if row["posts"] >= 3 and row.get("avg_er_pct") is not None]
        text = (f"Peak reach month was {peak['month']}: {base._f(peak['posts'])} posts, "
                f"{base._f(peak.get('share_of_total_reach_pct'))}% of total reach. Lowest was {low['month']}: "
                f"{base._f(low['posts'])} posts, {base._f(low.get('share_of_total_reach_pct'))}% of total reach.")
        if rated:
            best = max(rated, key=lambda row: row["avg_er_pct"])
            text += f" Highest ER month was {best['month']} at {base._f(best['avg_er_pct'])}%."
        patterns.append(text)

    if previous and previous_period:
        now, before = _totals(records), _totals(previous)
        comparison = {
            "previous_period": {"start": previous_period[0], "end": previous_period[1], **before},
            "posts_change_pct": _change(now["posts"], before["posts"]),
            "reach_change_pct": _change(now["reach"], before["reach"]),
            "engagement_change_pct": _change(now["engagement"], before["engagement"]),
            "avg_er_change_points": (round(now["avg_er_pct"] - before["avg_er_pct"], 2)
                                     if now["avg_er_pct"] is not None and before["avg_er_pct"] is not None else None),
        }
        facts["vs_previous_period"] = {k: v for k, v in comparison.items() if v is not None}
        if comparison["reach_change_pct"] is not None and comparison["engagement_change_pct"] is not None:
            text = (f"Against the previous period ({previous_period[0]} to {previous_period[1]}): posts "
                    f"{base._f(before['posts'])} to {base._f(now['posts'])} ({base._f(comparison['posts_change_pct'])}%), reach "
                    f"{base._f(before['reach'])} to {base._f(now['reach'])} ({base._f(comparison['reach_change_pct'])}%), engagement "
                    f"{base._f(before['engagement'])} to {base._f(now['engagement'])} ({base._f(comparison['engagement_change_pct'])}%), "
                    f"average ER {base._f(before['avg_er_pct'])}% to {base._f(now['avg_er_pct'])}%.")
            if now["paid_share_of_reach_pct"] is not None and before["paid_share_of_reach_pct"] is not None:
                text += (f" Paid posts carried {base._f(before['paid_share_of_reach_pct'])}% of reach then and "
                         f"{base._f(now['paid_share_of_reach_pct'])}% now.")
            patterns.insert(0, text)
    facts["patterns_to_interpret"] = patterns
    return facts


SYSTEM = (
    "You are a senior social media strategist on the CIMB in-house team, briefing the marketing manager on "
    "performance for a reporting period. You find what the numbers mean, not what they say. Return only JSON."
)


def build_messages(facts: Dict[str, Any], platform: Optional[str] = None) -> List[Dict[str, str]]:
    subject = f"{platform} performance" if platform else "performance across all social platforms"
    focus = (f"Talk only about {platform}. Never compare it with other platforms; none are in the fact sheet."
             if platform else
             "Cover the whole account: at least one point must be about how the platforms differ.")
    rules = f"""Write exactly {POINTS} points about {subject} for the period {facts['period'].get('first_post', '')} to
{facts['period'].get('last_post', '')}, for the marketing manager, using only the fact sheet below.
"patterns_to_interpret" lists the notable tensions already found in the numbers; build on them.

The manager can already see every total and ratio on the dashboard. A point that only restates numbers is worthless.
Each point must say what the numbers MEAN: the likely reason behind the pattern and its consequence.

Each point has three parts:
- "headline": the takeaway in plain words, at most 60 characters, no numbers. Example: "Paid bought eyeballs, not conversations".
- "text": 2 sentences, 150-260 characters. Sentence 1 gives the evidence: 2-3 numbers that show the contrast.
  Sentence 2 explains what it suggests or why it matters, e.g. "This suggests...", "So...", "The risk is...".
- "kind": "insight" for points 1-{INSIGHTS}, "decision" for point {POINTS}.

Insights: pick the {INSIGHTS} most important, different tensions (for example the change against the previous period and
what drove it, paid vs organic efficiency, creator collabs vs own posts, platform or format efficiency, a few posts
carrying the results, timing across weeks or months).
Decision: one concrete move for the next period: shift budget or effort from X to Y, scale or cut a format, change how
creators are used, change timing, or test something specific. Name what to do, where, and the number that justifies it.
Banned: "keep monitoring", "post consistently", "leverage", "optimize content".

Rules:
- {focus}
- Never mention content categories or topics, and never name a campaign.
- Never write "CIMB Malaysia" or "CIMB's"; the reader is CIMB.
- Copy every number exactly from the fact sheet, writing thousands with commas (2,581,914). ER values are
  percentages: always add "%". Do not calculate new numbers.
- Reach on TikTok and YouTube means views, and on LinkedIn impressions; call it reach.
- A change against the previous period is not proof of cause; say "suggests" or "likely", not "because".
- Plain, confident English. No markdown, no jargon.
- Never put a double quote character inside "headline" or "text"; use single quotes if needed.
- Reply with the JSON object only: no text before or after it, no code fences.
- Write the whole JSON on ONE line. Never put a line break or tab inside a value. No trailing commas.

Return JSON: {{"insights": [{{"kind": "insight", "headline": "...", "text": "..."}}, ...]}}

Fact sheet: {json.dumps(facts, ensure_ascii=False, separators=(',', ':'))}"""
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": rules}]


def clean_and_ground(output: Any, facts: Dict[str, Any]) -> List[Dict[str, str]]:
    """Well-formed, grounded points: up to three insights, then one decision."""
    kept = base.clean_and_ground(output, facts)
    insights = [item for item in kept if item["kind"] == "insight"][:INSIGHTS]
    decisions = [item for item in kept if item["kind"] == "decision"][:POINTS - len(insights)]
    return insights + decisions


def to_response(points: List[Dict[str, str]]) -> Dict[str, Any]:
    """The shape the Key Insights panel and the older report view already read."""
    return {
        "key_highlights": [f"{item['headline']}: {item['text']}" for item in points],
        "audience_behaviour": [item["text"] for item in points if item["kind"] == "insight"],
        "recommendations": [item["text"] for item in points if item["kind"] == "decision"],
        "insights": points,
        "_meta": {"generated_at": datetime.now(timezone.utc).isoformat(), "style": "strategic"},
    }
