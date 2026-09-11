/* eslint-disable react/prop-types */
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { ArrowDown, ArrowUp, ArrowUpRight, BarChart3, CalendarDays, Camera, Check, ChevronDown, ChevronRight, CirclePlay, Database, Download, ExternalLink, FileText, Heart, House, Info, Lightbulb, LogOut, Megaphone, Menu, Music2, RefreshCw, Settings2, Target, TrendingUp, Users, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import DataHub from './DataHub';
import usePerformanceData, { API_URL, queryFor } from './performance/usePerformanceData';
import { PLATFORMS, buildModel, change, compact, comparisonRange, dateLabel, followerModel, full, percent, safeLink } from './performance/model';
import './performance/performance.css';

const LegacyDashboard = lazy(() => import('./Dashboard'));
const ICONS = { Instagram: Camera, TikTok: Music2, YouTube: CirclePlay };
const CHART_STYLE = { fontSize: 12, fill: '#818493' };
const TOOLTIP_STYLE = { background: '#fff', border: '1px solid #e9e9ef', borderRadius: 8, fontSize: 14, color: '#25232a', boxShadow: '0 5px 25px #26081510' };

function trapFocus(event) {
  if (event.key !== 'Tab') return;
  const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]), input:not([disabled]), select, a[href]')];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

function PlatformIcon({ name, size = 16 }) {
  if (name === 'Facebook' || name === 'LinkedIn') return <span className="platform-letter-icon" style={{ width: size, fontSize: size }} aria-hidden="true">{name === 'Facebook' ? 'f' : 'in'}</span>;
  const Icon = ICONS[name] || BarChart3;
  return <Icon size={size} aria-hidden="true" />;
}

function Panel({ title, subtitle, children, className = '', action }) {
  return <section className={`perf-panel ${className}`} aria-label={title}>
    <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
    {children}
  </section>;
}

function Empty({ icon: Icon = BarChart3, title = 'No data for this period', children, action }) {
  return <div className="perf-empty"><span className="empty-icon"><Icon size={23} strokeWidth={1.5} /></span><strong>{title}</strong>{children && <p>{children}</p>}{action}</div>;
}

function Delta({ current, previous, rate = false, label = 'vs previous period' }) {
  const delta = change(current, previous, rate);
  if (!delta) return <span className="delta neutral">Comparison unavailable</span>;
  return <span className={`delta ${delta.value < 0 ? 'negative' : 'positive'}`}>{delta.value < 0 ? <ArrowDown size={11} /> : <ArrowUp size={11} />}<b>{delta.label}</b><span>{label}</span></span>;
}

function Kpi({ label, value, icon: Icon, children, help, tone = '' }) {
  return <section className="perf-kpi" aria-label={label} title={help}>
    <div><h2>{label}</h2><strong>{value}</strong></div><span className={`kpi-symbol ${tone}`}><Icon size={21} strokeWidth={1.6} /></span>
    <div className="kpi-detail">{children}</div>
  </section>;
}

function DateFilter({ range, onApply }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(range);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const close = event => { if (!ref.current?.contains(event.target)) setOpen(false); };
    const escape = event => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', escape); };
  }, [open]);
  const invalid = !draft.start || !draft.end || draft.start > draft.end;
  const apply = value => { onApply(value); setOpen(false); };
  return <div className="date-filter" ref={ref}>
    <button className="perf-button date-trigger" aria-expanded={open} onClick={() => { setDraft(range); setOpen(!open); }}><CalendarDays size={15} /><span>{range.start ? `${dateLabel(range.start)} – ${dateLabel(range.end)}` : 'All available dates'}</span><ChevronDown size={13} /></button>
    {open && <div className="date-popover" role="dialog" aria-label="Reporting period">
      <div className="popover-title"><strong>Reporting period</strong><button aria-label="Close date filter" className="icon-button" onClick={() => setOpen(false)}><X size={16} /></button></div>
      <div className="date-shortcuts"><button onClick={() => apply({ start: '', end: '' })}>All time</button><button onClick={() => {
        const now = new Date();
        const local = value => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
        apply({ start: local(new Date(now.getFullYear(), now.getMonth() - 1, 1)), end: local(new Date(now.getFullYear(), now.getMonth(), 0)) });
      }}>Last month</button></div>
      <label>Start date<input type="date" value={draft.start} max={draft.end || undefined} onInput={e => { const value = e.currentTarget.value; setDraft(prev => ({ ...prev, start: value })); }} onChange={e => { const value = e.currentTarget.value; setDraft(prev => ({ ...prev, start: value })); }} /></label>
      <label>End date<input type="date" value={draft.end} min={draft.start || undefined} onInput={e => { const value = e.currentTarget.value; setDraft(prev => ({ ...prev, end: value })); }} onChange={e => { const value = e.currentTarget.value; setDraft(prev => ({ ...prev, end: value })); }} /></label>
      {draft.start && draft.end && draft.start > draft.end && <p className="form-error">End date must be on or after start date.</p>}
      <button className="perf-button primary" disabled={invalid} onClick={() => apply(draft)}>Apply dates</button>
    </div>}
  </div>;
}

function PerformanceChart({ model }) {
  const rows = model.rows.filter(row => row.posts != null);
  return <Panel title="Performance by Platform" className="platform-chart" action={<div className="chart-legend"><span><i />Reach</span><span><i className="dark-dot" />Engagement</span><span><i className="line-dot" />Avg. ER%</span></div>}>
    {rows.length ? <><div className="chart-area" role="img" aria-label="Reach, engagement and average post engagement rate by platform">
      <ResponsiveContainer width="100%" height="100%"><ComposedChart data={rows} margin={{ top: 22, right: 1, bottom: 0, left: -10 }} barGap={3}>
        <CartesianGrid stroke="#f0f0f4" vertical={false} /><XAxis dataKey="short" tick={CHART_STYLE} axisLine={false} tickLine={false} />
        <YAxis yAxisId="volume" tickFormatter={compact} tick={CHART_STYLE} axisLine={false} tickLine={false} width={46} />
        <YAxis yAxisId="rate" orientation="right" tickFormatter={value => `${value}%`} tick={CHART_STYLE} axisLine={false} tickLine={false} width={36} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(value, name) => [name === 'Avg. ER%' ? percent(value) : full(value), name]} labelFormatter={(_, payload) => payload?.[0]?.payload?.name} />
        <Bar yAxisId="volume" dataKey="reach" name="Reach" fill="#ed0027" radius={[3, 3, 0, 0]} maxBarSize={36}><LabelList dataKey="reach" position="top" formatter={compact} style={{ fontSize: 11, fill: '#5a5361' }} /></Bar>
        <Bar yAxisId="volume" dataKey="engagement" name="Engagement" fill="#760a26" radius={[2, 2, 0, 0]} maxBarSize={22} />
        <Line yAxisId="rate" dataKey="er" name="Avg. ER%" stroke="#9297ab" strokeWidth={1.7} dot={{ r: 3, fill: '#9297ab' }} />
      </ComposedChart></ResponsiveContainer>
    </div><div className="platform-legend">{rows.map(row => <span key={row.name}><PlatformIcon name={row.name} size={12} />{row.name}</span>)}</div></> : <Empty>Upload platform exports in Data Hub to populate this chart.</Empty>}
  </Panel>;
}

function ReachBreakdown({ model }) {
  const total = model.kpis.reach;
  return <Panel title="Reach Breakdown" subtitle="Organic and paid post reach" className="reach-chart">
    {model.reachSplit && total > 0 ? <div className="reach-body"><div className="donut-chart" role="img" aria-label={`Organic reach ${full(model.reachSplit[0].value)}, paid reach ${full(model.reachSplit[1].value)}`}>
      <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={model.reachSplit} dataKey="value" innerRadius="64%" outerRadius="92%" startAngle={90} endAngle={-270} stroke="#fff" strokeWidth={3}>{model.reachSplit.map(row => <Cell key={row.name} fill={row.color} />)}</Pie><Tooltip contentStyle={TOOLTIP_STYLE} formatter={value => full(value)} /></PieChart></ResponsiveContainer>
      <div className="donut-center"><strong>{compact(total)}</strong><span>Total reach</span></div>
    </div><div className="donut-legend">{model.reachSplit.map(row => <div key={row.name}><i style={{ background: row.color }} /><span>{row.name}<strong>{compact(row.value)} <small>({Math.round(row.value / total * 100)}%)</small></strong></span></div>)}</div></div> : <Empty icon={Target}>Reach data will appear here when available.</Empty>}
  </Panel>;
}

function Followers({ followers, loading, error, onConnect }) {
  return <Panel title="Follower Growth" subtitle="Monthly audience size" className="follower-chart" action={<button className="icon-button" aria-label="Connect follower sheet" title="Connect follower sheet" onClick={onConnect}><Settings2 size={14} /></button>}>
    {loading ? <Empty title="Loading follower history…" /> : followers.rows.length ? <div className="chart-area" role="img" aria-label="Monthly follower growth">
      <ResponsiveContainer width="100%" height="100%"><LineChart data={followers.rows} margin={{ top: 20, right: 12, left: -8, bottom: 5 }}>
        <CartesianGrid stroke="#f0f0f4" vertical={false} /><XAxis dataKey="label" tick={CHART_STYLE} axisLine={false} tickLine={false} tickFormatter={value => value.split(' ')[0]} />
        <YAxis tickFormatter={compact} tick={CHART_STYLE} axisLine={false} tickLine={false} domain={['auto', 'auto']} width={47} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={full} /><Line dataKey="followers" name="Followers" stroke="#ed0027" strokeWidth={2} dot={{ r: 3, fill: '#ed0027', stroke: '#fff', strokeWidth: 1 }} />
      </LineChart></ResponsiveContainer>
    </div> : <Empty icon={TrendingUp} title={error ? 'Follower data unavailable' : 'Connect your audience data'} action={<button className="text-button" onClick={onConnect}>{error ? 'Check source' : 'Connect follower sheet'} <ArrowUpRight size={13} /></button>}>
      {error || (followers.coverage ? `${followers.coverage} of ${followers.expected} platforms supplied. Matching months are needed for a combined total.` : 'Add monthly follower counts to see how your audience is growing.')}
    </Empty>}
  </Panel>;
}

function Categories({ rows }) {
  const visible = rows?.slice(0, 7) || [];
  const max = Math.max(...visible.map(row => row.count), 1);
  return <Panel title="Content Categories Performance" subtitle="Published posts · auto-classified by title" className="category-chart">
    {visible.length ? <div className="category-rows">{visible.map((row, index) => <div className="category-row" key={row.type}><span title={row.type}>{row.type}</span><div><i style={{ width: `${row.count / max * 100}%`, opacity: 1 - index * 0.065 }} /></div><strong>{full(row.count)}</strong></div>)}</div> : <Empty icon={FileText}>Content categories will appear after posts are uploaded.</Empty>}
  </Panel>;
}

function Formats({ rows }) {
  return <Panel title="Content Format Performance" subtitle="Average post ER% · organic content" className="format-chart">
    {rows.length ? <div className="chart-area" role="img" aria-label="Average organic engagement rate by content format">
      <ResponsiveContainer width="100%" height="100%"><BarChart data={rows.slice(0, 6)} margin={{ top: 25, right: 8, left: 8, bottom: 8 }}>
        <XAxis dataKey="name" tick={{ ...CHART_STYLE, fontSize: 11 }} axisLine={false} tickLine={false} interval={0} /><YAxis hide domain={[0, 'auto']} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={value => percent(value)} cursor={{ fill: '#f7f7fa' }} />
        <Bar dataKey="er" name="Avg. ER%" radius={[3, 3, 0, 0]} maxBarSize={43}>{rows.slice(0, 6).map((row, index) => <Cell key={row.name} fill={['#ed0027', '#790a29', '#888996', '#b5b6c2', '#d1bdc5', '#dfe0e8'][index]} />)}<LabelList dataKey="er" position="top" formatter={percent} style={{ fontSize: 12, fill: '#39323f', fontWeight: 600 }} /></Bar>
      </BarChart></ResponsiveContainer>
    </div> : <Empty icon={BarChart3}>Upload organic posts to compare content formats.</Empty>}
  </Panel>;
}

function Posts({ posts, expanded, onExpand, platform }) {
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState('engagement');
  const filtered = (posts || []).filter(post => `${post.title} ${post.format} ${post.platform}`.toLowerCase().includes(search.toLowerCase())).slice().sort((a, b) => (b[sort] || 0) - (a[sort] || 0));
  return <Panel title={expanded ? 'Organic Content Performance' : 'Top Performing Posts'} subtitle={platform ? `${platform} · organic posts` : 'Across platforms · ranked by engagement'} className={expanded ? 'expanded-posts' : 'top-posts'} action={!expanded && <button className="text-button" onClick={onExpand}>View all <ArrowUpRight size={12} /></button>}>
    {expanded && <div className="post-controls"><input aria-label="Search posts" placeholder="Search posts, formats or platforms…" value={search} onChange={e => setSearch(e.target.value)} /><label>Sort by<select value={sort} onChange={e => setSort(e.target.value)}><option value="engagement">Engagement</option><option value="reach">Reach</option><option value="engagement_rate">ER%</option></select></label></div>}
    {filtered.length ? <div className="perf-table-scroll"><table className="perf-post-table"><thead><tr><th>Post</th><th>Reach</th><th>{expanded ? 'Engagement' : 'ER%'}</th>{expanded && <th>ER%</th>}</tr></thead><tbody>{filtered.slice(0, expanded ? 100 : 4).map((post, index) => <tr key={post.id ?? `${post.platform}-${index}`}>
      <td><div className="post-identity"><span className="post-format-icon"><PlatformIcon name={post.platform} size={18} /></span><div>{safeLink(post.link) ? <a href={safeLink(post.link)} target="_blank" rel="noreferrer" title={post.title}>{post.title || 'Untitled post'}<ExternalLink size={10} /></a> : <strong title={post.title}>{post.title || 'Untitled post'}</strong>}<span>{dateLabel(post.date)} · {post.format || post.platform}</span></div></div></td>
      <td>{compact(post.reach)}</td><td>{expanded ? compact(post.engagement) : percent(post.engagement_rate)}</td>{expanded && <td>{percent(post.engagement_rate)}</td>}
    </tr>)}</tbody></table>{expanded && filtered.length > 100 && <p className="panel-footnote">Showing the top 100 matching posts. The full export is available in Data Hub.</p>}</div> : <Empty icon={FileText} title={search ? 'No matching posts' : 'No organic posts yet'}>Posts will appear here once content data is available for this selection.</Empty>}
  </Panel>;
}

function Benchmarks({ current, previous, mode, onMode, hasRange, loading, comparison }) {
  const metrics = [['Reach', 'reach'], ['Engagement', 'engagement'], ['Engagement rate', 'er'], ['Followers', 'followers']];
  return <Panel title="Benchmarking" className="benchmark-panel">
    <div className="benchmark-tabs" role="group" aria-label="Benchmark comparison"><button aria-pressed={mode === 'previous'} onClick={() => onMode('previous')}>Previous period</button><button aria-pressed={mode === 'year'} onClick={() => onMode('year')}>Same period last year</button><button disabled title="Industry benchmark source not connected">Industry avg.</button><button disabled title="Campaign mapping not connected">Similar campaigns</button></div>
    <div className="benchmark-metrics">{metrics.map(([label, key]) => { const delta = !loading && change(current[key], previous[key], key === 'er'); return <div key={key}><span>{label}</span><strong className={delta && delta.value < 0 ? 'negative' : ''}>{delta ? delta.label : '—'}</strong><small>{loading ? 'Loading…' : delta ? key === 'er' ? 'percentage points' : 'change' : 'Not available'}</small></div>; })}</div>
    <p className="panel-footnote">{hasRange ? comparison ? `Compared with ${dateLabel(comparison.start)} – ${dateLabel(comparison.end)}.` : 'Comparison unavailable.' : 'Select a date range to compare performance.'}</p>
  </Panel>;
}

function Insights({ model, ai, loading, onGenerate, platform }) {
  const top = [...model.rows].filter(row => row.engagement > 0).sort((a, b) => b.engagement - a.engagement)[0];
  const highlights = ai?.key_highlights || (top ? [
    `${top.name} recorded ${compact(top.engagement)} engagements${model.rows.length > 1 ? ', the highest among the selected platforms' : ''}.`,
    `${full(model.kpis.posts)} posts contributed ${compact(model.kpis.reach)} in reported reach during this period.`,
    ...(model.formats[0] ? [`${model.formats[0].name} had the highest average organic post ER at ${percent(model.formats[0].er)}.`] : []),
  ] : []);
  return <Panel title="Key Insights" className="insights-panel" action={<Lightbulb size={18} />}>
    {highlights.length ? <ul className="insights-list">{highlights.slice(0, 4).map((text, index) => <li key={index}><Check size={14} /><span>{text.replace(/\*\*/g, '')}</span></li>)}</ul> : <Empty icon={Lightbulb} title="Your next insight starts here">Performance highlights will appear when data is available.</Empty>}
    {ai?.error && <p role="alert" className="form-error">AI insights are currently unavailable. Check the AI service configuration in the reporting tools.</p>}
    <button className="text-button" disabled={loading || !model.kpis.posts} onClick={onGenerate}>{loading ? 'Generating insights…' : platform ? 'Open AI reporting tools' : 'Generate AI insights'} <ArrowUpRight size={12} /></button>
    <p className="panel-footnote">{ai?.key_highlights ? 'AI-generated · review before sharing' : 'Calculated highlights · not causal findings'}</p>
  </Panel>;
}

export default function PerformanceDashboard({ onLogout }) {
  const [page, setPage] = useState('executive');
  const [platform, setPlatform] = useState(null);
  const [platformOpen, setPlatformOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 760px)').matches);
  const sidebarRef = useRef(null);
  const [range, setRange] = useState({ start: '', end: '' });
  const [refreshKey, setRefreshKey] = useState(0);
  const [benchmarkMode, setBenchmarkMode] = useState('previous');
  const [detailTab, setDetailTab] = useState('overview');
  const [showAllPosts, setShowAllPosts] = useState(false);
  const [followerDialog, setFollowerDialog] = useState(false);
  const [followerUrl, setFollowerUrl] = useState('');
  const [connectedUrl, setConnectedUrl] = useState('');
  const [followerState, setFollowerState] = useState({ data: null, loading: false, error: '' });
  const [aiState, setAiState] = useState({ data: null, loading: false });
  const [legacy, setLegacy] = useState(false);
  const aiController = useRef(null);
  const current = usePerformanceData(range, refreshKey);
  const comparedRange = useMemo(() => comparisonRange(range, benchmarkMode), [range, benchmarkMode]);
  const previous = usePerformanceData(comparedRange, refreshKey, !!comparedRange);
  const model = useMemo(() => buildModel(current.data, platform), [current.data, platform]);
  const previousModel = useMemo(() => buildModel(previous.data, platform), [previous.data, platform]);
  const followers = useMemo(() => followerModel(followerState.data, platform), [followerState.data, platform]);

  const navigate = (next, name = null) => { setPage(next); setPlatform(name); setDetailTab('overview'); setShowAllPosts(false); setMobileOpen(false); if (next !== 'data-hub' && page === 'data-hub') setRefreshKey(key => key + 1); };
  useEffect(() => {
    aiController.current?.abort();
    setAiState({ data: null, loading: false });
  }, [range, platform, refreshKey]);
  useEffect(() => () => aiController.current?.abort(), []);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 760px)');
    const update = () => setIsMobile(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    const trigger = document.activeElement;
    sidebarRef.current?.querySelector('button')?.focus();
    return () => trigger?.focus();
  }, [mobileOpen]);
  useEffect(() => {
    if (!followerDialog) return;
    const trigger = document.activeElement;
    return () => trigger?.focus();
  }, [followerDialog]);
  useEffect(() => {
    if (!connectedUrl) return;
    const controller = new AbortController();
    setFollowerState({ data: null, loading: true, error: '' });
    axios.get(`${API_URL}/follower-growth`, { params: { sheet_url: connectedUrl, ...queryFor(range) }, signal: controller.signal, timeout: 60000 })
      .then(response => { if (!controller.signal.aborted) setFollowerState({ data: response.data.error ? null : response.data, loading: false, error: response.data.error ? 'The follower sheet could not be read. Check sharing and tab names.' : '' }); })
      .catch(() => { if (!controller.signal.aborted) setFollowerState({ data: null, loading: false, error: 'Unable to load follower data. Check the sheet and try again.' }); });
    return () => controller.abort();
  }, [connectedUrl, range, refreshKey]);
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') { setMobileOpen(false); setFollowerDialog(false); } };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, []);

  const generateInsights = async () => {
    const controller = new AbortController();
    aiController.current?.abort();
    aiController.current = controller;
    setAiState({ data: null, loading: true });
    try {
      const response = await axios.get(`${API_URL}/executive-summary`, { params: queryFor(range), signal: controller.signal, timeout: 60000 });
      if (!controller.signal.aborted) setAiState({ data: response.data, loading: false });
    } catch { if (!controller.signal.aborted) setAiState({ data: { error: true }, loading: false }); }
  };
  const followerConnectValid = /^https:\/\/docs\.google\.com\/spreadsheets\/d\/[\w-]+/.test(followerUrl.trim());
  const title = page === 'data-hub' ? 'Data Hub' : platform ? `${platform} Performance` : page === 'platform' ? 'Platform Performance' : 'Executive Performance';

  if (legacy) return <><div className="legacy-back"><button onClick={() => { setLegacy(false); setRefreshKey(key => key + 1); }}>← Back to performance dashboard</button><span>Existing reporting workspace</span></div><Suspense fallback={<p>Opening reporting tools…</p>}><LegacyDashboard onLogout={onLogout} /></Suspense></>;

  return <div className="performance-app">
    <a className="skip-link" href="#performance-main">Skip to dashboard</a>
    {mobileOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
    <aside id="dashboard-navigation" ref={sidebarRef} className={`perf-sidebar ${mobileOpen ? 'is-open' : ''}`} aria-label="Dashboard navigation" aria-hidden={isMobile && !mobileOpen ? true : undefined} inert={isMobile && !mobileOpen ? '' : undefined} onKeyDown={mobileOpen ? trapFocus : undefined}>
      <div className="sidebar-top"><span>PERFORMANCE HUB</span><button className="mobile-only icon-button" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={19} /></button></div>
      <nav className="perf-nav">
        <button className={`perf-nav-item ${page === 'executive' ? 'active' : ''}`} aria-current={page === 'executive' ? 'page' : undefined} onClick={() => navigate('executive')}><House size={17} /><span>Executive Performance</span></button>
        <div className={`platform-parent ${page === 'platform' ? 'selected' : ''}`}><button className="perf-nav-item" aria-current={page === 'platform' && !platform ? 'page' : undefined} onClick={() => { navigate('platform'); setPlatformOpen(true); }}><BarChart3 size={17} /><span>Platform Performance</span></button><button className="submenu-toggle" aria-label="Toggle platform submenu" aria-expanded={platformOpen} aria-controls="platform-submenu" onClick={() => setPlatformOpen(!platformOpen)}>{platformOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</button></div>
        {platformOpen && <div className="platform-submenu" id="platform-submenu">{PLATFORMS.map(item => <button className={`perf-nav-item ${platform === item.name ? 'active' : ''}`} key={item.name} aria-current={platform === item.name ? 'page' : undefined} onClick={() => navigate('platform', item.name)}><PlatformIcon name={item.name} /><span>{item.name}</span>{platform === item.name && <i />}</button>)}</div>}
      </nav>
      <div className="perf-sidebar-bottom"><button className={`perf-nav-item ${page === 'data-hub' ? 'active' : ''}`} onClick={() => navigate('data-hub')}><Database size={16} /><span>Data Hub</span></button><button className="perf-nav-item" onClick={() => setLegacy(true)}><Settings2 size={16} /><span>Reporting tools</span><ExternalLink size={12} /></button><button className="perf-nav-item" onClick={onLogout}><LogOut size={16} /><span>Sign out</span></button><p className="brand-tagline">Moving You Forward <span>❯</span></p></div>
    </aside>

    <div className="perf-workspace">
      {import.meta.env.DEV && import.meta.env.VITE_UI_PREVIEW === 'true' && <div className="preview-notice">UI preview · Synthetic test data · Not connected to the live database</div>}
      <header className="perf-header"><div className="header-brand"><button className="mobile-only icon-button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={22} /></button><span className="cimb-wordmark"><img src="/cimb-logo.jpg?v=2" alt="CIMB" width="144" height="40" /></span><div className="header-titles"><h1>Social Media Performance Dashboard</h1><p>{title}</p></div></div><div className="header-actions"><DateFilter range={range} onApply={value => { setRange(value); setShowAllPosts(false); }} /><button className="perf-button primary export-button" onClick={() => window.print()} title="Print or save this dashboard as a PDF"><Download size={14} /><span>Download report</span></button></div></header>

      <main id="performance-main" className="perf-main" tabIndex={-1}>
        {page === 'data-hub' ? <div className="data-hub-view"><div className="section-intro"><h2>Your data, in one place.</h2><p>Upload and manage platform exports. Return to the overview to see updated performance.</p></div><DataHub startDate={range.start} endDate={range.end} /></div> : <>
          <div className="overview-toolbar"><div><span className="eyebrow">{platform ? `${platform.toUpperCase()} AT A GLANCE` : 'YOUR SOCIAL PERFORMANCE, AT A GLANCE'}</span><p>{range.start ? `${dateLabel(range.start)} – ${dateLabel(range.end)}` : 'All available data'}<span> · </span>{platform || 'All five platforms'}</p></div><div className="data-status"><span className={`status-dot ${current.errors.length ? 'warning' : ''}`} />{current.loading ? 'Loading data…' : current.errors.length ? 'Connection needs attention' : current.empty ? 'Ready for your data' : 'Connected to Data Hub'}<button className={`icon-button ${current.loading ? 'is-refreshing' : ''}`} title="Refresh data" aria-label="Refresh data" disabled={current.loading} onClick={() => setRefreshKey(key => key + 1)}><RefreshCw size={14} /></button></div></div>
          {current.errors.length > 0 && <div className="data-notice error" role="alert"><Info size={17} /><span>Some dashboard data could not be loaded ({current.errors.join(', ')}). Unavailable metrics are shown as —.</span><button onClick={() => setRefreshKey(key => key + 1)}>Retry</button></div>}
          {current.empty && <div className="data-notice"><Database size={17} /><span>No posts found for this period. Upload your platform exports or choose another date range.</span><button onClick={() => navigate('data-hub')}>Open Data Hub <ArrowUpRight size={13} /></button></div>}
          <div className={`perf-kpis ${current.loading ? 'is-loading' : ''}`} aria-busy={current.loading}>
            <Kpi label="Total Followers" value={full(followers.total)} icon={Users} help="Latest common month across the selected platforms; followers are not part of post exports."><span className="delta neutral">{followers.total == null ? <button className="text-button" onClick={() => setFollowerDialog(true)}>Connect follower data <ArrowUpRight size={11} /></button> : `As of ${followers.rows.at(-1)?.label}`}</span></Kpi>
            <Kpi label="Total Reach" value={full(model.kpis.reach)} icon={Megaphone} help="Sum of post reach, not deduplicated people. Instagram Stories excluded."><Delta current={model.kpis.reach} previous={previousModel.kpis.reach} label={benchmarkMode === 'year' ? 'vs last year' : 'vs previous period'} /></Kpi>
            <Kpi label="Total Engagement" value={full(model.kpis.engagement)} icon={Heart} tone="red" help="Total engagements across posts in the selected period. Instagram Stories excluded."><Delta current={model.kpis.engagement} previous={previousModel.kpis.engagement} label={benchmarkMode === 'year' ? 'vs last year' : 'vs previous period'} /></Kpi>
            <Kpi label={platform ? 'Avg. Post ER%' : 'Engagement Rate (ER%)'} value={percent(model.kpis.er)} icon={BarChart3} help={platform ? 'Mean of individual post engagement rates, as reported by the platform-stats endpoint.' : 'Total engagement / ER denominator. The backend uses views for Facebook/Instagram posts without reach.'}><Delta current={model.kpis.er} previous={previousModel.kpis.er} rate label={benchmarkMode === 'year' ? 'vs last year' : 'vs previous period'} /></Kpi>
          </div>
          {page === 'platform' && <div className="platform-section-header"><div><span className="platform-heading-icon">{platform ? <PlatformIcon name={platform} size={23} /> : <BarChart3 size={23} />}</span><h2>{platform || 'All platforms'} <small>{full(model.kpis.posts)} published posts</small></h2></div><div className="detail-tabs" role="group" aria-label="Platform view">{['overview', 'content', 'formats', ...(platform === 'Instagram' ? ['stories'] : [])].map(tab => <button key={tab} aria-pressed={detailTab === tab} onClick={() => setDetailTab(tab)}>{tab[0].toUpperCase() + tab.slice(1)}</button>)}</div></div>}
          {(page === 'executive' || detailTab === 'overview') && <div className="perf-grid" aria-busy={current.loading}>
            <PerformanceChart model={model} /><ReachBreakdown model={model} /><Followers followers={followers} loading={followerState.loading} error={followerState.error} onConnect={() => setFollowerDialog(true)} />
            <Panel title="Top Performing Campaigns" subtitle="Campaign-level results" className="campaign-panel"><Empty icon={Target} title="See the bigger campaign picture">Campaign tags are not included in the current data source. This view is ready for campaign mapping.</Empty><div className="campaign-columns"><span>Campaign</span><span>Reach</span><span>Engagement</span><span>ER%</span></div></Panel>
            <Categories rows={model.categories} /><Formats rows={model.formats} />
            <Benchmarks current={model.kpis} previous={previousModel.kpis} mode={benchmarkMode} onMode={setBenchmarkMode} hasRange={!!comparedRange} loading={previous.loading} comparison={comparedRange} />
            <Posts posts={model.posts} onExpand={() => { setShowAllPosts(!showAllPosts); }} platform={platform} />
            <Insights model={model} ai={platform ? null : aiState.data} loading={aiState.loading} onGenerate={platform ? () => setLegacy(true) : generateInsights} platform={platform} />
          </div>}
          {(showAllPosts || (page === 'platform' && detailTab === 'content')) && <Posts posts={model.posts} platform={platform} expanded />}
          {page === 'platform' && detailTab === 'formats' && <div className="format-detail"><Formats rows={model.formats} /><Panel title="Format breakdown" subtitle="Organic posts only"><div className="perf-table-scroll"><table className="perf-post-table"><thead><tr><th>Format</th><th>Posts</th><th>Reach</th><th>Engagement</th><th>Avg. ER%</th></tr></thead><tbody>{model.formats.map(row => <tr key={row.name}><td>{row.name}</td><td>{full(row.posts)}</td><td>{compact(row.reach)}</td><td>{compact(row.engagement)}</td><td>{percent(row.er)}</td></tr>)}</tbody></table>{!model.formats.length && <Empty />}</div></Panel></div>}
          {page === 'platform' && detailTab === 'stories' && <Panel title="Instagram Stories" subtitle="Reported separately; not included in the main post totals">{current.data.stats?.['Instagram Stories'] ? <div className="story-kpis"><Kpi label="Stories" value={full(current.data.stats['Instagram Stories'].stories_count)} icon={Camera} /><Kpi label="Average reach" value={full(current.data.stats['Instagram Stories'].avg_reach)} icon={Users} /><Kpi label="Average ER%" value={percent(current.data.stats['Instagram Stories'].avg_engagement_rate)} icon={Heart} /></div> : <Empty icon={Camera} title="No Instagram Stories in this period">Upload an Instagram Stories export in Data Hub to populate this view.</Empty>}</Panel>}
          <footer className="perf-footer"><span><Info size={12} /> Post-level reach is not deduplicated. Instagram Stories are reported separately.</span><span>{current.updatedAt && `Updated ${current.updatedAt.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`}</span></footer>
        </>}
      </main>
    </div>
    {followerDialog && <div className="perf-modal-backdrop" onClick={event => { if (event.target === event.currentTarget) setFollowerDialog(false); }}><section className="perf-modal" role="dialog" aria-modal="true" aria-labelledby="follower-dialog-title" onKeyDown={trapFocus}><div className="popover-title"><h2 id="follower-dialog-title">Connect follower history</h2><button className="icon-button" onClick={() => setFollowerDialog(false)} aria-label="Close follower connection"><X size={20} /></button></div><p>Use a publicly shared Google Sheet with monthly follower counts. This uses the dashboard’s existing follower-data connection.</p><p className="sheet-help">Tab names: [FB] Followers, [IG] Followers, [TT] Followers, [YT] Followers and [LI] Followers. Each tab needs Month and Followers columns.</p><form onSubmit={event => { event.preventDefault(); if (followerConnectValid) { setConnectedUrl(followerUrl.trim()); setRefreshKey(key => key + 1); setFollowerDialog(false); } }}><label>Google Sheet URL<input autoFocus type="url" placeholder="https://docs.google.com/spreadsheets/d/…" value={followerUrl} onChange={e => setFollowerUrl(e.target.value)} required /></label><p className="panel-footnote">Connected for this session only. Combined totals require matching months from all five platforms.</p><button className="perf-button primary" disabled={!followerConnectValid}>Connect sheet <ArrowUpRight size={14} /></button></form></section></div>}
  </div>;
}
