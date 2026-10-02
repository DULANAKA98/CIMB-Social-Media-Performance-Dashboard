import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildModel, change, comparisonRange, exposureMetric, exposureValue, filterFollowerData, followerChartMarkers, followerModel, followerTickLabel, full, percent, safeLink, thumbnailForPost } from './model.js';

test('previous period uses inclusive day bounds and crosses month/year boundaries', () => {
  assert.deepEqual(comparisonRange({ start: '2026-01-01', end: '2026-01-31' }), { start: '2025-12-01', end: '2025-12-31' });
  assert.deepEqual(comparisonRange({ start: '2026-08-12', end: '2026-08-12' }), { start: '2026-08-11', end: '2026-08-11' });
  assert.equal(comparisonRange({ start: '', end: '' }), null);
  assert.equal(comparisonRange({ start: '2026-08-12', end: '2026-08-01' }), null);
});

test('prior-year comparison clamps leap day', () => {
  assert.deepEqual(comparisonRange({ start: '2024-02-01', end: '2024-02-29' }, 'year'), { start: '2023-02-01', end: '2023-02-28' });
});

const source = {
  summary: { kpis: { total_reach: 1200, total_engagement: 70, avg_engagement_rate: 5.83 } },
  stats: { Facebook: { posts_count: 2, avg_reach: 200, avg_engagement_rate: 5 }, Instagram: { posts_count: 3, avg_reach: 200, avg_engagement_rate: 7 }, 'Instagram Overall': { contents_count: 5, avg_reach: 160 }, 'Instagram Stories': { posts_count: 2, stories_count: 2, avg_reach: 100, avg_engagement_rate: 4 } },
  engagement: { overall: { posts_count: 7 }, platforms: [{ platform: 'Facebook', total_engagement: 20 }, { platform: 'Instagram', total_engagement: 40 }, { platform: 'Instagram Stories', total_engagement: 10 }] },
  content: { Facebook: [{ id: 1, platform: 'Facebook', reach: 200, engagement: 10 }], Instagram: [{ id: 2, platform: 'Instagram', reach: 300, engagement: 30 }], 'Instagram Stories': [{ id: 3, platform: 'Instagram Stories', format: 'IG Story', reach: 200, engagement: 10 }] },
  categories: { Overall: [{ type: 'Brand', count: 7 }], Facebook: [{ type: 'Brand', count: 2 }], 'Instagram Stories': [{ type: 'Brand', count: 2 }] },
  formats: [{ platform: 'Facebook', format: 'Video', posts: 1, avg_er: 2, avg_reach: 200, avg_engagement: 10 }, { platform: 'Instagram', format: 'Video', posts: 3, avg_er: 6, avg_reach: 300, avg_engagement: 30 }, { platform: 'Grand Total', is_total: true, is_grand_total: true, posts: 4, avg_er: 999 }],
  breakdown: {
    Facebook: { reach_source: 'reach', include_views: true, organic: { posts: 1, reach: 200, views: 300, engagement: 10, average_engagement_rate: 5 }, paid: { posts: 1, reach: 200, views: 250, engagement: 10, average_engagement_rate: 5 } },
    TikTok: { reach_source: 'views', include_views: false, organic: { posts: 1, reach: 900, views: 900, engagement: 45, average_engagement_rate: 5 }, paid: { posts: 1, reach: 100, views: 100, engagement: 3, average_engagement_rate: 3 } },
    LinkedIn: { reach_source: 'impressions', include_views: false, organic: { posts: 1, reach: 800, views: 20, engagement: 24, average_engagement_rate: 3 }, paid: { posts: 0, reach: 0, views: 0, engagement: 0, average_engagement_rate: null } },
  },
};

test('executive totals include Instagram Stories as a separate performance platform', () => {
  const model = buildModel(source);
  assert.equal(model.rows.length, 6);
  assert.equal(model.kpis.reach, 1200);
  assert.equal(model.kpis.er, 5.83);
  assert.equal(model.rows.reduce((total, row) => total + (row.reach || 0), 0), 1200);
  assert.deepEqual(model.reachSplit.map(row => row.value), [700, 500]);
  assert.equal(model.posts[0].id, 2);
});

test('Instagram Stories remain independently selectable', () => {
  const model = buildModel(source, 'Instagram Stories');
  assert.equal(model.kpis.reach, 200);
  assert.equal(model.kpis.engagement, 10);
  assert.equal(model.kpis.er, 4);
  assert.equal(model.kpis.posts, 2);
  assert.equal(model.posts[0].id, 3);
  assert.equal(model.categories[0].count, 2);
  assert.equal(model.formats.length, 0);
});

test('platform selection scopes every available breakdown to that platform', () => {
  const model = buildModel(source, 'Facebook');
  assert.equal(model.kpis.reach, 400);
  assert.equal(model.kpis.engagement, 20);
  assert.equal(model.kpis.er, 5);
  assert.equal(model.posts.length, 1);
  assert.equal(model.categories[0].count, 2);
  assert.equal(model.formats[0].posts, 1);
  assert.deepEqual(model.reachSplit.map(row => row.value), [200, 200]);
  assert.deepEqual(model.metricBreakdowns.map(metric => metric.label), ['Reach', 'Views', 'Engagement', 'Avg. ER%']);
  assert.deepEqual(model.metricBreakdowns[0].rows.map(row => row.value), [200, 200]);
});

test('platform breakdowns use native exposure metric names without duplicating views', () => {
  const tiktok = buildModel(source, 'TikTok');
  assert.equal(tiktok.reachSource, 'views');
  assert.deepEqual(tiktok.metricBreakdowns.map(metric => metric.label), ['Views', 'Engagement', 'Avg. ER%']);
  assert.deepEqual(tiktok.metricBreakdowns[0].rows.map(row => row.value), [900, 100]);

  const linkedin = buildModel(source, 'LinkedIn');
  assert.equal(linkedin.reachSource, 'impressions');
  assert.deepEqual(linkedin.metricBreakdowns.map(metric => metric.label), ['Impressions', 'Engagement', 'Avg. ER%']);
  assert.equal(linkedin.metricBreakdowns[2].rows[1].value, null);
});

test('top post exposure uses each platform native metric', () => {
  assert.deepEqual(exposureMetric('TikTok'), { key: 'views', label: 'Views' });
  assert.deepEqual(exposureMetric('YouTube'), { key: 'views', label: 'Views' });
  assert.deepEqual(exposureMetric('LinkedIn'), { key: 'impressions', label: 'Impressions' });
  assert.deepEqual(exposureMetric('Facebook'), { key: 'reach', label: 'Reach' });
  assert.equal(exposureValue({ platform: 'TikTok', reach: 10, views: 25 }), 25);
  assert.equal(exposureValue({ platform: 'LinkedIn', reach: 10, impressions: 30 }), 30);
  assert.equal(exposureValue({ platform: 'Instagram', reach: 40, views: 50 }), 40);
});

test('format ER is weighted by post count, never an average of averages', () => {
  assert.equal(buildModel(source).formats[0].er, 5);
  assert.equal(buildModel(source).formats[0].posts, 4);
});

test('missing sources remain unavailable, not invented zeros or paid classifications', () => {
  const missing = buildModel({});
  assert.equal(missing.kpis.reach, null);
  assert.equal(missing.posts, null);
  assert.equal(missing.reachSplit, null);
  assert.equal(full(null), '—');
  assert.equal(percent(undefined), '—');
  assert.equal(buildModel({ ...source, summary: { kpis: { total_reach: 1 } } }).reachSplit, null);
});

test('deltas handle zero baselines and percentage points honestly', () => {
  assert.equal(change(4, 0), null);
  assert.equal(change(null, 3), null);
  assert.equal(change(0, 10).label, '-100.0%');
  assert.equal(change(3, 2.5, true).label, '+0.50pp');
});

test('follower totals require matching daily snapshots across all selected platforms', () => {
  const single = { Facebook: [{ month: '2026-09-11', month_label: '11 Sep 2026', followers: 10 }] };
  assert.equal(followerModel(single).total, null);
  assert.equal(followerModel(single, 'Facebook').total, 10);
  const complete = Object.fromEntries(['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn'].map(name => [name, [{ month: '2026-09-11', month_label: '11 Sep 2026', followers: 10 }]]));
  complete._meta = { last_refreshed_at: '2026-09-11T00:00:00Z', refresh_schedule: 'Daily at 08:00 Asia/Kuala_Lumpur' };
  assert.equal(followerModel(complete).total, 50);
  assert.equal(followerModel(complete).lastRefreshedAt, '2026-09-11T00:00:00Z');
  complete.LinkedIn[0].month = '2026-09-12';
  assert.equal(followerModel(complete).total, null);
});

test('follower chart markers adapt to the reporting period without dropping the trend line data', () => {
  const daily = Array.from({ length: 31 }, (_, index) => ({ month: `2026-08-${String(index + 1).padStart(2, '0')}` }));
  const monthlyPlan = followerChartMarkers(daily);
  assert.deepEqual(monthlyPlan.indexes, [0, 6, 12, 18, 24, 30]);
  assert.deepEqual(monthlyPlan.ticks, ['2026-08-01', '2026-08-07', '2026-08-13', '2026-08-19', '2026-08-25', '2026-08-31']);
  assert.equal(followerTickLabel('2026-08-19', monthlyPlan.spanDays), '19 Aug');

  const longPeriod = Array.from({ length: 235 }, (_, index) => ({ month: new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10) }));
  const longPlan = followerChartMarkers(longPeriod);
  assert.equal(longPlan.indexes.length, 8);
  assert.equal(longPlan.indexes[0], 0);
  assert.equal(longPlan.indexes.at(-1), 234);
  assert.equal(followerTickLabel('2026-08-23', longPlan.spanDays), 'Aug');
});

test('only http(s) post links are rendered', () => {
  assert.equal(safeLink('javascript:alert(1)'), null);
  assert.equal(safeLink('https://example.com/post'), 'https://example.com/post');
});

test('thumbnail matching prefers the post URL and safely falls back to platform and date', () => {
  const items = [
    { platform: 'INSTAGRAM', publication_date: '2026-09-10T08:00:00Z', link: 'https://instagram.com/p/abc/?utm_source=test', picture: 'https://cdn.example.com/a.jpg' },
    { platform: 'facebook', publication_date: { dateTime: '2026-09-10T09:30:00Z' }, link: '', picture: 'https://cdn.example.com/b.jpg' },
  ];
  assert.equal(thumbnailForPost({ platform: 'Instagram', date: '2026-09-01', link: 'https://www.instagram.com/p/abc/' }, items), 'https://cdn.example.com/a.jpg');
  assert.equal(thumbnailForPost({ platform: 'Facebook', date: '2026-09-10', link: '' }, items), 'https://cdn.example.com/b.jpg');
  assert.equal(thumbnailForPost({ platform: 'TikTok', date: '2026-09-10' }, items), null);
});

test('follower date filtering is independent and preserves response metadata', () => {
  const data = { Facebook: [{ month: '2026-08-01' }, { month: '2026-09-01' }], _meta: { last_refreshed_at: 'now' } };
  const filtered = filterFollowerData(data, { start: '2026-08-15', end: '2026-09-30' });
  assert.deepEqual(filtered.Facebook, [{ month: '2026-09-01' }]);
  assert.deepEqual(filtered._meta, data._meta);
});
