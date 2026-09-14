import test from "node:test";
import assert from "node:assert/strict";
import worker, { validateOutput, validateSnapshot } from "../src/index.js";

const snapshot = {
  date_range: { start: "2026-07-01", end: "2026-07-31" },
  platforms: [
    { name: "Instagram", posts: 10, reach: 12000, engagement: 900, engagement_rate: 7.5 },
    { name: "Facebook", posts: 8, reach: 15000, engagement: 600, engagement_rate: 4 },
  ],
};

test("validates dashboard snapshots", () => {
  assert.deepEqual(validateSnapshot(snapshot), []);
  assert.ok(validateSnapshot({ date_range: {}, platforms: [] }).length >= 2);
});

test("validates AI response shape", () => {
  assert.equal(validateOutput({
    key_highlights: ["Instagram led engagement efficiency.", "Facebook led reported reach."],
    audience_behaviour: ["Video-led content attracted stronger audience response."],
    recommendations: ["Maintain the strongest content pattern and test one variation."],
  }), true);
});

test("protects the endpoint and returns grounded insights", async () => {
  const env = {
    CIMB_INSIGHTS_KEY: "test-secret",
    AI: {
      run: async () => ({
        response: {
          key_highlights: [
            "Instagram recorded the highest engagement rate at 7.5%.",
            "Facebook generated the most reported reach at 15,000.",
          ],
          audience_behaviour: ["Audience response was strongest where engagement efficiency was highest."],
          recommendations: ["Continue testing the strongest content pattern during the next reporting period."],
        },
      }),
    },
  };

  const unauthorized = await worker.fetch(new Request("https://example.com/insights", {
    method: "POST",
    body: JSON.stringify(snapshot),
  }), env);
  assert.equal(unauthorized.status, 401);

  const response = await worker.fetch(new Request("https://example.com/insights", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": "test-secret" },
    body: JSON.stringify(snapshot),
  }), env);
  assert.equal(response.status, 200);
  const body = await response.json();
  assert.equal(body._meta.fallback, false);
  assert.equal(body.key_highlights.length, 2);
});

test("falls back safely when the model invents a number", async () => {
  const response = await worker.fetch(new Request("https://example.com/insights", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": "test-secret" },
    body: JSON.stringify(snapshot),
  }), {
    CIMB_INSIGHTS_KEY: "test-secret",
    AI: {
      run: async () => ({
        response: {
          key_highlights: ["Instagram improved by 99% during the selected period.", "Facebook led reported reach."],
          audience_behaviour: ["Audience response was concentrated around visual content."],
          recommendations: ["Continue testing the strongest content pattern."],
        },
      }),
    },
  });
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body._meta.fallback, true);
  assert.match(body.key_highlights[0], /7\.5%/);
});
