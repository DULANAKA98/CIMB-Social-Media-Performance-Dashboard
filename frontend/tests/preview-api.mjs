// Read-only, synthetic API fixtures for local UI QA. Never imported by the app.
// Start with: node tests/preview-api.mjs
// Point the local Vite server at http://127.0.0.1:8766/api.
// Date range 2099-01-01..2099-01-31 tests empty data; 2098 tests API failure.
import http from 'node:http';
import process from 'node:process';

const names = ['Facebook', 'Instagram', 'Instagram Stories', 'TikTok', 'YouTube', 'LinkedIn'];
const followerNames = names.filter(name => name !== 'Instagram Stories');
const totals = [6400000, 9700000, 1200000, 7500000, 2100000, 800000];
const engagements = [198000, 342000, 36000, 286000, 54000, 25000];
const titles = ['Building brighter financial futures', 'A little progress, every day', 'Your next chapter starts here', 'Making more possible, together'];
const posts = names.flatMap((platform, p) => Array.from({ length: 12 }, (_, i) => ({
  id: p * 12 + i, platform, format: platform === 'Instagram Stories' ? 'IG Story' : ['Video', 'Static', 'Carousel'][i % 3], title: `${titles[i % 4]} · Test post ${i + 1}`,
  date: `2026-08-${String(i + 1).padStart(2, '0')}`, reach: totals[p] * .75 / 12,
  engagement: engagements[p] * .75 / 12, engagement_rate: engagements[p] / totals[p] * 100,
  is_organic: i % 4 !== 0, views: totals[p] / 10, impressions: totals[p] * .75 / 12, link: '', likes: 1200, comments: 25, shares: 12, favorites: 7,
})));
const stats = Object.fromEntries(names.map((name, p) => [name, { posts_count: 16, avg_reach: totals[p] / 16, avg_engagement_rate: engagements[p] / totals[p] * 100 }]));
stats['Instagram Stories'].stories_count = stats['Instagram Stories'].posts_count;
stats['Instagram Overall'] = { contents_count: 32, avg_reach: 100000, avg_engagement_rate: 3.1 };
const categories = ['Marketing', 'Brand', 'Financial Education', 'Sustainability', 'Security', 'Other'];
const performanceBreakdown = Object.fromEntries(names.map(platform => {
  const platformPosts = posts.filter(post => post.platform === platform);
  const reachSource = ['TikTok', 'YouTube'].includes(platform) ? 'views' : platform === 'LinkedIn' ? 'impressions' : 'reach';
  const summarize = organic => {
    const rows = platformPosts.filter(post => post.is_organic === organic);
    return {
      posts: rows.length,
      reach: rows.reduce((total, post) => total + post[reachSource], 0),
      views: rows.reduce((total, post) => total + post.views, 0),
      engagement: rows.reduce((total, post) => total + post.engagement, 0),
      average_engagement_rate: rows.length ? rows.reduce((total, post) => total + post.engagement_rate, 0) / rows.length : null,
    };
  };
  return [platform, { reach_source: reachSource, include_views: ['Facebook', 'Instagram', 'Instagram Stories'].includes(platform), organic: summarize(true), paid: summarize(false) }];
}));
const summarizeOverallBreakdown = organic => {
  const rows = posts.filter(post => post.is_organic === organic);
  const exposure = post => ['TikTok', 'YouTube'].includes(post.platform) ? post.views : post.platform === 'LinkedIn' ? post.impressions : post.reach;
  return {
    posts: rows.length,
    reach: rows.reduce((total, post) => total + exposure(post), 0),
    views: rows.reduce((total, post) => total + post.views, 0),
    engagement: rows.reduce((total, post) => total + post.engagement, 0),
    average_engagement_rate: rows.length ? rows.reduce((total, post) => total + post.engagement_rate, 0) / rows.length : null,
  };
};
performanceBreakdown.Overall = { reach_source: 'mixed', include_views: false, organic: summarizeOverallBreakdown(true), paid: summarizeOverallBreakdown(false) };
const fixtures = {
  'status': { has_data: true, post_count: 96, last_sync: '2026-08-28T08:00:00Z' },
  'dashboard-summary': { kpis: { total_reach: totals.reduce((a, b) => a + b, 0), total_engagement: engagements.reduce((a, b) => a + b, 0), avg_engagement_rate: 3.41, top_platform: 'Instagram' } },
  'platform-stats': stats,
  'engagement-summary': { overall: { total_engagement: engagements.reduce((a, b) => a + b, 0), posts_count: 96 }, platforms: names.map((platform, i) => ({ platform, total_engagement: engagements[i], posts_count: 16 })) },
  'all-content': Object.fromEntries(names.map(platform => [platform, posts.filter(post => post.platform === platform && post.is_organic)])),
  'organic-content': Object.fromEntries(names.map(platform => [platform, { top: posts.filter(post => post.platform === platform).slice(0, 5), bottom: [] }])),
  'content-types': Object.fromEntries([...names, 'Overall'].map(platform => [platform, categories.map((type, i) => ({ type, count: (6 - i) * (platform === 'Overall' ? 3 : 1), reach: (6 - i) * 1450000 * (platform === 'Overall' ? 3 : 1), engagement: (6 - i) * 49000, engagement_rate: 2.35 + i * .31 }))])),
  'format-performance': names.flatMap(platform => ['Video', 'Carousel', 'Static', 'Link'].map((format, i) => ({ platform, format, is_total: false, posts: 4, avg_reach: 50000, avg_engagement: 2000, avg_er: 4.52 - i * .6 }))),
  'performance-breakdown': performanceBreakdown,
  'follower-growth': { ...Object.fromEntries(followerNames.map((platform, index) => [platform, ['2026-08-13', '2026-08-20', '2026-08-27', '2026-09-03', '2026-09-10', '2026-09-11'].map((date, i) => ({ month: date, month_label: `${date.slice(8)} ${date.slice(5, 7) === '08' ? 'Aug' : 'Sep'} 2026`, followers: 450000 + index * 100000 + i * 22000 }))])), _meta: { last_refreshed_at: '2026-09-11T09:20:00Z', refresh_schedule: 'Daily at 08:00 Asia/Kuala_Lumpur' } },
  'metricool': { ...Object.fromEntries(followerNames.map((platform, index) => [platform, ['2026-08-14', '2026-08-20', '2026-08-27', '2026-09-03', '2026-09-10', '2026-09-12'].map((date, i) => ({ month: date, month_label: `${date.slice(8)} ${date.slice(5, 7) === '08' ? 'Aug' : 'Sep'} 2026`, followers: 450000 + index * 100000 + i * 22000 }))])), _meta: { last_refreshed_at: '2026-09-12T09:20:00Z', source: 'Metricool', errors: {} } },
  'post-thumbnails': { items: posts.map(post => ({ platform: post.platform, title: post.title, publication_date: post.date, link: '', picture: `https://picsum.photos/seed/cimb-${post.id}/120/90` })) },
  'post-thumbnail': { picture: 'https://picsum.photos/seed/cimb-fallback/120/90', source: 'Synthetic public metadata fallback' },
  'posts': { posts, total: posts.length, pages: 2 },
  'executive-summary': { error: 'Test fixture: AI unavailable' },
};

const port = Number(process.env.PORT || 8766);

http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json');
  if (req.method !== 'GET') { res.writeHead(405); res.end(JSON.stringify({ error: 'Preview API is read-only' })); return; }
  const url = new URL(req.url, 'http://localhost');
  if (url.searchParams.get('start_date')?.startsWith('2099')) { res.writeHead(400); res.end(JSON.stringify({ detail: 'No data in database. Please upload platform Excel files first.' })); return; }
  if (url.searchParams.get('start_date')?.startsWith('2098')) { res.writeHead(503); res.end(JSON.stringify({ detail: 'Synthetic connection failure' })); return; }
  const endpoint = url.pathname.split('/').at(-1);
  if (!(endpoint in fixtures)) { res.writeHead(404); res.end('{}'); return; }
  if (endpoint === 'metricool') {
    const start = url.searchParams.get('start_date') || '';
    const end = url.searchParams.get('end_date') || '9999-12-31';
    const filtered = Object.fromEntries(followerNames.map(name => [name, fixtures.metricool[name].filter(row => row.month >= start && row.month <= end)]));
    res.end(JSON.stringify({ ...filtered, _meta: fixtures.metricool._meta }));
    return;
  }
  if (endpoint === 'executive-summary') {
    const platform = url.searchParams.get('platform') || 'All platforms';
    const start = url.searchParams.get('start_date') || 'the first available date';
    const end = url.searchParams.get('end_date') || 'the latest available date';
    res.end(JSON.stringify({
      key_highlights: [
        `${platform} AI insight generated for ${start} to ${end}.`,
        `${platform} performance is calculated only from records inside the selected reporting period.`,
        `The current scope contains dashboard metrics for ${platform}.`,
      ],
      _meta: { fallback: false },
    }));
    return;
  }
  res.end(JSON.stringify(fixtures[endpoint]));
}).listen(port, '127.0.0.1', () => console.log(`Synthetic, read-only UI preview API: http://127.0.0.1:${port}/api`));
