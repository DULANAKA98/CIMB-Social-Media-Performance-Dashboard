export const PLATFORMS = [
  { name: 'Instagram', short: 'IG', color: '#c72c75' },
  { name: 'Facebook', short: 'FB', color: '#1877f2' },
  { name: 'TikTok', short: 'TT', color: '#20212a' },
  { name: 'YouTube', short: 'YT', color: '#ed0027' },
  { name: 'LinkedIn', short: 'LI', color: '#0a66c2' },
];

export const number = value => value == null || !Number.isFinite(Number(value)) ? null : Number(value);
export const sum = values => values.reduce((total, value) => total + (number(value) ?? 0), 0);
export const full = value => number(value) == null ? '—' : Math.round(value).toLocaleString('en-GB');
export const compact = value => number(value) == null ? '—' : new Intl.NumberFormat('en-GB', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export const percent = value => number(value) == null ? '—' : `${Number(value).toFixed(2)}%`;
export const safeLink = value => /^https?:\/\//i.test(value || '') ? value : null;
export const dateLabel = value => value ? new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : 'All time';
const iso = date => date.toISOString().slice(0, 10);

const normalizeUrl = value => {
  if (!safeLink(value)) return '';
  try {
    const url = new URL(value);
    return `${url.hostname.replace(/^www\./, '').toLowerCase()}${url.pathname.replace(/\/$/, '')}`;
  } catch { return ''; }
};
const normalizePlatform = value => String(value || '').toLowerCase().replace(/[^a-z]/g, '');
const comparableDate = value => String(value?.dateTime || value || '').slice(0, 10);
const titleWords = value => new Set(String(value || '').toLowerCase().replace(/https?:\/\/\S+/g, '').replace(/[^a-z0-9]+/g, ' ').split(' ').filter(word => word.length > 2));
const titleScore = (left, right) => {
  const a = titleWords(left); const b = titleWords(right);
  if (!a.size || !b.size) return 0;
  return [...a].filter(word => b.has(word)).length / Math.min(a.size, b.size);
};

export function thumbnailForPost(post, items = []) {
  const exactUrl = normalizeUrl(post?.link);
  let match = exactUrl ? items.find(item => normalizeUrl(item.link) === exactUrl) : null;
  if (!match) {
    const platform = normalizePlatform(post?.platform);
    const date = comparableDate(post?.date);
    const candidates = items.filter(item => normalizePlatform(item.platform).includes(platform) && comparableDate(item.publication_date) === date);
    if (candidates.length === 1) match = candidates[0];
    else if (candidates.length > 1) {
      const ranked = candidates.map(item => ({ item, score: titleScore(post?.title, item.title) })).sort((a, b) => b.score - a.score);
      if (ranked[0]?.score >= .25) match = ranked[0].item;
    }
  }
  return safeLink(match?.picture);
}

export function filterFollowerData(data, range) {
  if (!data || (!range?.start && !range?.end)) return data;
  return Object.fromEntries(Object.entries(data).map(([key, value]) => {
    if (key === '_meta' || !Array.isArray(value)) return [key, value];
    return [key, value.filter(row => (!range.start || row.month >= range.start) && (!range.end || row.month <= range.end))];
  }));
}

export function comparisonRange(range, mode = 'previous') {
  if (!range.start || !range.end || range.start > range.end) return null;
  const start = new Date(`${range.start}T00:00:00Z`);
  const end = new Date(`${range.end}T00:00:00Z`);
  if (mode === 'year') {
    // Clamp leap day rather than silently moving it into March.
    const shift = date => new Date(Date.UTC(date.getUTCFullYear() - 1, date.getUTCMonth(), Math.min(date.getUTCDate(), new Date(Date.UTC(date.getUTCFullYear() - 1, date.getUTCMonth() + 1, 0)).getUTCDate())));
    return { start: iso(shift(start)), end: iso(shift(end)) };
  }
  const duration = end - start + 86400000;
  return { start: iso(new Date(start - duration)), end: iso(new Date(start - 86400000)) };
}

export function change(current, previous, isRate = false) {
  if (number(current) == null || number(previous) == null || (!isRate && previous === 0)) return null;
  const value = isRate ? current - previous : (current - previous) / previous * 100;
  return { value, label: `${value > 0 ? '+' : ''}${value.toFixed(isRate ? 2 : 1)}${isRate ? 'pp' : '%'}` };
}

export function buildModel(data, platform = null) {
  const selected = platform ? PLATFORMS.filter(item => item.name === platform) : PLATFORMS;
  const rows = selected.map(item => {
    const stat = data.stats?.[item.name];
    const engagement = data.engagement?.platforms?.find(row => row.platform === item.name);
    return { ...item, posts: stat?.posts_count ?? null, reach: stat ? stat.posts_count * stat.avg_reach : null, engagement: engagement?.total_engagement ?? null, er: stat?.avg_engagement_rate ?? null };
  });
  const posts = data.content ? selected.flatMap(item => data.content[item.name] || []).sort((a, b) => b.engagement - a.engagement) : null;
  const kpis = platform ? { reach: rows[0]?.reach, engagement: rows[0]?.engagement, er: rows[0]?.er, posts: rows[0]?.posts } : {
    reach: data.summary?.kpis?.total_reach ?? null,
    engagement: data.summary?.kpis?.total_engagement ?? null,
    er: data.summary?.kpis?.avg_engagement_rate ?? null,
    posts: data.engagement?.overall?.posts_count ?? null,
  };
  const organicReach = posts == null ? null : sum(posts.map(post => post.reach));
  // Both source endpoints exclude Instagram Stories. Do not include the
  // Instagram Overall/Stories helper rows in the executive totals again.
  const validSplit = organicReach != null && kpis.reach != null && organicReach <= kpis.reach + 0.01;
  const reachSplit = validSplit ? [
    { name: 'Organic', value: organicReach, color: '#ed0027' },
    { name: 'Paid', value: Math.max(0, kpis.reach - organicReach), color: '#740924' },
  ] : null;
  const categories = data.categories?.[platform || 'Overall'] ?? null;
  const formatMap = new Map();
  for (const row of data.formats || []) {
    if (row.is_total || row.is_grand_total || (platform && row.platform !== platform)) continue;
    const prev = formatMap.get(row.format) || { name: row.format, posts: 0, erTotal: 0, reach: 0, engagement: 0 };
    prev.posts += row.posts;
    prev.erTotal += row.avg_er * row.posts;
    prev.reach += row.avg_reach * row.posts;
    prev.engagement += row.avg_engagement * row.posts;
    formatMap.set(row.format, prev);
  }
  const formats = [...formatMap.values()].map(row => ({ ...row, er: row.posts ? row.erTotal / row.posts : 0 })).sort((a, b) => b.er - a.er);
  return { kpis, rows, posts, reachSplit, categories, formats };
}

export function followerModel(data, platform = null) {
  const names = platform ? [platform] : PLATFORMS.map(item => item.name);
  const available = names.filter(name => data?.[name]?.length);
  const metadata = {
    lastRefreshedAt: data?._meta?.last_refreshed_at || null,
    refreshSchedule: data?._meta?.refresh_schedule || null,
  };
  // Cross-platform totals require matching months from every selected platform.
  // Missing observations are never filled with zeros or carried forward.
  if (available.length !== names.length) return { total: null, rows: [], coverage: available.length, expected: names.length, ...metadata };
  const months = data[names[0]].map(row => row.month).filter(month => names.every(name => data[name].some(row => row.month === month))).sort();
  const rows = months.map(month => ({ month, label: data[names[0]].find(row => row.month === month).month_label, followers: sum(names.map(name => data[name].find(row => row.month === month).followers)) }));
  return { total: rows.at(-1)?.followers ?? null, rows, coverage: available.length, expected: names.length, ...metadata };
}
