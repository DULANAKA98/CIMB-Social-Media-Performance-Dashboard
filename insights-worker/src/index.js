const MODEL = "@cf/meta/llama-3.1-8b-instruct-fast";
const MAX_BODY_BYTES = 96 * 1024;

const RESPONSE_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    key_highlights: {
      type: "array",
      minItems: 2,
      maxItems: 4,
      items: { type: "string", minLength: 12, maxLength: 240 },
    },
    audience_behaviour: {
      type: "array",
      minItems: 1,
      maxItems: 3,
      items: { type: "string", minLength: 12, maxLength: 240 },
    },
    recommendations: {
      type: "array",
      minItems: 1,
      maxItems: 3,
      items: { type: "string", minLength: 12, maxLength: 240 },
    },
  },
  required: ["key_highlights", "audience_behaviour", "recommendations"],
};

function json(body, status = 200, extraHeaders = {}) {
  return Response.json(body, {
    status,
    headers: {
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      ...extraHeaders,
    },
  });
}

function safeEqual(left, right) {
  const a = new TextEncoder().encode(String(left || ""));
  const b = new TextEncoder().encode(String(right || ""));
  const length = Math.max(a.length, b.length, 1);
  let different = a.length ^ b.length;
  for (let index = 0; index < length; index += 1) {
    different |= (a[index % Math.max(a.length, 1)] || 0) ^ (b[index % Math.max(b.length, 1)] || 0);
  }
  return different === 0;
}

function finiteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function validDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

export function validateSnapshot(snapshot) {
  const errors = [];
  if (!snapshot || typeof snapshot !== "object" || Array.isArray(snapshot)) {
    return ["Body must be a JSON object."];
  }
  if (!snapshot.date_range || !validDate(snapshot.date_range.start) || !validDate(snapshot.date_range.end)) {
    errors.push("date_range.start and date_range.end must use YYYY-MM-DD.");
  }
  if (!Array.isArray(snapshot.platforms) || snapshot.platforms.length === 0) {
    errors.push("platforms must contain at least one platform summary.");
  } else {
    snapshot.platforms.forEach((platform, index) => {
      if (!platform || typeof platform.name !== "string" || !platform.name.trim()) {
        errors.push(`platforms[${index}].name is required.`);
      }
      ["posts", "reach", "engagement", "engagement_rate"].forEach((field) => {
        if (!finiteNumber(platform?.[field])) errors.push(`platforms[${index}].${field} must be a non-negative number.`);
      });
    });
  }
  return errors;
}

function unwrapModelResponse(result) {
  if (result && typeof result.response === "object" && result.response !== null) return result.response;
  const raw = typeof result?.response === "string" ? result.response : typeof result === "string" ? result : "";
  const cleaned = raw.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  return JSON.parse(cleaned);
}

function validInsightArray(value, min = 1, max = 4) {
  return Array.isArray(value)
    && value.length >= min
    && value.length <= max
    && value.every((item) => typeof item === "string" && item.trim().length >= 12 && item.length <= 240);
}

export function validateOutput(value) {
  return Boolean(
    value
    && typeof value === "object"
    && validInsightArray(value.key_highlights, 2, 4)
    && validInsightArray(value.audience_behaviour, 1, 3)
    && validInsightArray(value.recommendations, 1, 3)
  );
}

function numberTokens(value) {
  const matches = JSON.stringify(value).match(/-?\d[\d,]*(?:\.\d+)?/g) || [];
  return new Set(matches.map((token) => token.replace(/,/g, "").replace(/^(-?\d+\.\d*?)0+$/, "$1").replace(/\.$/, "")));
}

function keepGrounded(items, snapshot) {
  const allowed = numberTokens(snapshot);
  return items.filter((item) => {
    const used = numberTokens(item);
    return [...used].every((token) => allowed.has(token));
  });
}

function deterministicFallback(snapshot) {
  const rankedEr = [...snapshot.platforms].sort((a, b) => b.engagement_rate - a.engagement_rate);
  const rankedReach = [...snapshot.platforms].sort((a, b) => b.reach - a.reach);
  const rankedEngagement = [...snapshot.platforms].sort((a, b) => b.engagement - a.engagement);
  const highlights = [
    `${rankedEr[0].name} recorded the highest average engagement rate at ${rankedEr[0].engagement_rate}%.`,
    `${rankedReach[0].name} generated the most reported reach at ${rankedReach[0].reach.toLocaleString("en-US")}.`,
  ];
  if (rankedEngagement[0].name !== rankedReach[0].name) {
    highlights.push(`${rankedEngagement[0].name} led engagement volume with ${rankedEngagement[0].engagement.toLocaleString("en-US")} engagements.`);
  }
  return {
    key_highlights: highlights,
    audience_behaviour: ["Audience response was strongest on the platform with the highest engagement efficiency in the selected period."],
    recommendations: ["Use the strongest platform and format signals as the starting point for the next content plan, then validate performance in the following reporting period."],
  };
}

function buildPrompt(snapshot) {
  return [
    "Create concise client-facing social media insights for CIMB Malaysia.",
    "Use only the supplied snapshot. Never invent metrics, targets, campaigns, causes, post details, or comparisons.",
    "Every number written must appear exactly in the snapshot. Treat reach as reported reach, not deduplicated people.",
    "Use calm, practical language. Say 'consistent with' or 'suggests' when interpreting patterns; do not claim causation.",
    "key_highlights: 2-4 notable, non-repetitive facts. audience_behaviour: 1-3 cautious observations. recommendations: 1-3 actions supported by the data.",
    `Snapshot: ${JSON.stringify(snapshot)}`,
  ].join("\n");
}

async function generate(env, snapshot) {
  const result = await env.AI.run(MODEL, {
    messages: [
      { role: "system", content: "You are a careful social media reporting analyst. Return only the requested JSON." },
      { role: "user", content: buildPrompt(snapshot) },
    ],
    response_format: { type: "json_schema", json_schema: RESPONSE_SCHEMA },
    temperature: 0.15,
    max_tokens: 850,
  });
  const output = unwrapModelResponse(result);
  if (!validateOutput(output)) throw new Error("The model response did not match the insight schema.");
  const grounded = {
    key_highlights: keepGrounded(output.key_highlights, snapshot),
    audience_behaviour: keepGrounded(output.audience_behaviour, snapshot),
    recommendations: keepGrounded(output.recommendations, snapshot),
  };
  if (grounded.key_highlights.length < 2 || grounded.audience_behaviour.length < 1 || grounded.recommendations.length < 1) {
    throw new Error("The model response contained unsupported numbers.");
  }
  return grounded;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/healthz") {
      return json({ ok: true, service: "cimb-dashboard-insights" });
    }
    if (url.pathname !== "/insights") return json({ error: "not_found" }, 404);
    if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405, { allow: "POST" });
    if (!env.CIMB_INSIGHTS_KEY) return json({ error: "service_not_configured" }, 503);
    if (!safeEqual(request.headers.get("x-api-key"), env.CIMB_INSIGHTS_KEY)) {
      return json({ error: "unauthorized" }, 401);
    }
    const contentLength = Number(request.headers.get("content-length") || 0);
    if (contentLength > MAX_BODY_BYTES) return json({ error: "body_too_large" }, 413);

    let snapshot;
    try {
      const body = await request.text();
      if (new TextEncoder().encode(body).length > MAX_BODY_BYTES) return json({ error: "body_too_large" }, 413);
      snapshot = JSON.parse(body);
    } catch {
      return json({ error: "invalid_json" }, 400);
    }
    const errors = validateSnapshot(snapshot);
    if (errors.length) return json({ error: "invalid_snapshot", details: errors }, 422);

    let insights;
    let fallback = false;
    try {
      insights = await generate(env, snapshot);
    } catch (error) {
      console.error("AI generation failed", error instanceof Error ? error.message : "unknown error");
      insights = deterministicFallback(snapshot);
      fallback = true;
    }
    return json({
      ...insights,
      _meta: {
        model: MODEL,
        generated_at: new Date().toISOString(),
        period: snapshot.date_range,
        fallback,
      },
    });
  },
};
