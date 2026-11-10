/* eslint-disable react/prop-types */
import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { ArrowLeft, ArrowUpRight, Check, ChevronLeft, ChevronRight, ExternalLink, Eye, FileText, Flag, Hash, Heart, ImagePlus, Info, Lightbulb, Link2, Megaphone, Pencil, Percent, Plus, RefreshCw, Search, Sparkles, Trash2, Trophy, Users, X } from 'lucide-react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { API_URL, queryFor } from './usePerformanceData';
import { PLATFORMS, compact, dateLabel, full, percent, safeLink } from './model';
import { CHART_STYLE, DateFilter, Empty, Kpi, Panel, PlatformIcon, PostThumbnail, TOOLTIP_STYLE, trapFocus } from './ui';
import './campaigns.css';

const ALL_PLATFORMS = 'All platforms';
const SORTS = [
  { key: 'date', label: 'Newest' },
  { key: 'engagement_rate', label: 'ER%' },
  { key: 'engagement', label: 'Total engagement' },
  { key: 'reach', label: 'Reach' },
  { key: 'views', label: 'Views' },
];
const COMPARE_GROUPS = [
  { key: 'posts', label: 'Posts', format: full, rows: [['posts', 'Total posts'], ['organic_posts', 'Organic posts'], ['paid_posts', 'Paid posts']] },
  { key: 'reach', label: 'Reach', format: compact, rows: [['reach', 'Total reach'], ['organic_reach', 'Organic reach'], ['paid_reach', 'Paid reach']] },
  { key: 'views', label: 'Views', format: compact, rows: [['views', 'Total views'], ['organic_views', 'Organic views'], ['paid_views', 'Paid views']] },
  { key: 'avg_er', label: 'Avg. ER%', format: percent, rows: [['avg_er', 'Avg. ER%'], ['organic_avg_er', 'Avg. organic ER%'], ['paid_avg_er', 'Avg. paid ER%']] },
];
const SPLIT_COLORS = ['#3d2a35', '#ed0027', '#8f1a3c'];
const errorText = (error, fallback) => {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (!error?.response) return `${fallback} (no response from the server)`;
  return `${fallback} (error ${error.response.status})`;
};
const dateSpan = campaign => campaign.first_post ? `${dateLabel(campaign.first_post)} – ${dateLabel(campaign.last_post)}` : 'No posts yet';

// Resize in the browser so the stored picture stays small (it lives in the database).
function readImage(file) {
  return new Promise((resolve, reject) => {
    if (!/^image\/(png|jpe?g|webp|gif)$/.test(file.type)) { reject(new Error('Choose a PNG, JPG, WebP or GIF image.')); return; }
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('Could not read that image.'));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error('Could not read that image.'));
      image.onload = () => {
        const scale = Math.min(1, 900 / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(image.width * scale);
        canvas.height = Math.round(image.height * scale);
        const context = canvas.getContext('2d');
        context.fillStyle = '#fff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.86));
      };
      image.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

export function CampaignImage({ campaign, className = '' }) {
  if (campaign?.image) return <span className={`campaign-image ${className}`}><img src={campaign.image} alt="" /></span>;
  const initials = (campaign?.name || '?').split(/\s+/).slice(0, 2).map(word => word[0]).join('').toUpperCase();
  return <span className={`campaign-image is-placeholder ${className}`} aria-hidden="true"><b>{initials}</b></span>;
}

function Modal({ title, subtitle, onClose, children, wide = false }) {
  useEffect(() => {
    const escape = event => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [onClose]);
  // The page wrapper keeps a transform from its entrance animation, which would make a
  // fixed backdrop position against the page instead of the window, so render at the app root.
  return createPortal(<div className="perf-modal-backdrop campaign-modal-backdrop" onPointerDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={`perf-modal campaign-modal ${wide ? 'is-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} onKeyDown={trapFocus}>
      <div className="campaign-modal-head"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button className="icon-button" aria-label="Close" onClick={onClose}><X size={18} /></button></div>
      {children}
    </div>
  </div>, document.querySelector('.performance-app') || document.body);
}

function CampaignForm({ campaign, onSaved, onCancel }) {
  const [name, setName] = useState(campaign?.name || '');
  const [hashtag, setHashtag] = useState(campaign?.hashtag || '');
  const [image, setImage] = useState(campaign?.image || '');
  const [dragging, setDragging] = useState(false);
  const [state, setState] = useState({ saving: false, error: '' });
  const fileInput = useRef(null);
  const pickImage = async file => {
    if (!file) return;
    try { setImage(await readImage(file)); setState(prev => ({ ...prev, error: '' })); } catch (error) { setState({ saving: false, error: error.message }); }
  };
  const submit = async event => {
    event.preventDefault();
    setState({ saving: true, error: '' });
    try {
      const body = { name, hashtag, image };
      const response = campaign ? await axios.patch(`${API_URL}/campaigns/${campaign.id}`, body) : await axios.post(`${API_URL}/campaigns`, body);
      onSaved(response.data);
    } catch (error) { setState({ saving: false, error: errorText(error, 'The campaign could not be saved. Try again.') }); }
  };
  const tag = hashtag.trim().replace(/^#/, '');
  return <form className="campaign-form" onSubmit={submit}>
    <div className={`campaign-dropzone ${dragging ? 'is-dragging' : ''} ${image ? 'has-image' : ''}`}
      onDragOver={event => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}
      onDrop={event => { event.preventDefault(); setDragging(false); pickImage(event.dataTransfer.files?.[0]); }}>
      {image ? <img src={image} alt="Campaign picture preview" /> : <div><ImagePlus size={26} strokeWidth={1.5} /><strong>Add a campaign picture</strong><span>Drag an image here or browse · PNG, JPG or WebP</span></div>}
      <div className="campaign-dropzone-actions"><button type="button" className="perf-button" onClick={() => fileInput.current?.click()}>{image ? 'Change picture' : 'Browse'}</button>{image && <button type="button" className="perf-button" onClick={() => setImage('')}>Remove</button>}</div>
      <input ref={fileInput} type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={event => { pickImage(event.target.files?.[0]); event.target.value = ''; }} />
    </div>
    <label>Campaign name<input value={name} maxLength={120} required placeholder="e.g. Hmmm Dulu Raya 2026" onChange={event => setName(event.target.value)} /></label>
    <label>Campaign hashtag<span className="hashtag-input"><Hash size={15} /><input value={hashtag.replace(/^#/, '')} required placeholder="hmmmdulu" onChange={event => setHashtag(event.target.value.replace(/\s/g, ''))} /></span>
      <small>Posts whose caption includes <b>#{tag || 'hashtag'}</b> are added automatically. Matching ignores upper and lower case.</small></label>
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
    <div className="campaign-form-actions"><button type="button" className="perf-button" onClick={onCancel}>Cancel</button><button className="perf-button primary" disabled={state.saving || !name.trim() || !tag}>{state.saving ? <><RefreshCw size={14} className="spin" />Saving…</> : campaign ? 'Save changes' : <><Plus size={14} />Create campaign</>}</button></div>
  </form>;
}

function MatchSummary({ result, hashtag, onAddPosts, onDone, doneLabel = 'View campaign' }) {
  return <div className="campaign-match-summary" role="status">
    <span className="match-badge"><Check size={26} /></span>
    <h3>{result.matched === 0 ? 'Campaign saved' : `${full(result.matched)} ${result.matched === 1 ? 'post' : 'posts'} matched`}</h3>
    <p>{result.matched === 0 ? `No unassigned posts in Data Hub include #${hashtag} yet.` : `Posts that include #${hashtag} in their caption were added to this campaign.`}
      {result.in_other_campaigns > 0 && ` ${full(result.in_other_campaigns)} more ${result.in_other_campaigns === 1 ? 'post uses' : 'posts use'} this hashtag but already ${result.in_other_campaigns === 1 ? 'belongs' : 'belong'} to another campaign.`}</p>
    <div className="campaign-match-callout"><Link2 size={16} /><span>Some posts don’t use the hashtag? Add them by pasting their links.</span></div>
    <div className="campaign-form-actions"><button className="perf-button" onClick={onAddPosts}><Plus size={14} />Add more posts</button><button className="perf-button primary" onClick={onDone}>{doneLabel}</button></div>
  </div>;
}

function AddPostsForm({ campaign, onAdded, onCancel }) {
  const [text, setText] = useState('');
  const [state, setState] = useState({ saving: false, error: '', result: null });
  const links = useMemo(() => text.split(/[\s,]+/).map(link => link.trim()).filter(Boolean), [text]);
  const send = async (linkList, moveFromOther = false) => {
    setState(prev => ({ ...prev, saving: true, error: '' }));
    try {
      const response = await axios.post(`${API_URL}/campaigns/${campaign.id}/posts`, { links: linkList, move_from_other: moveFromOther });
      setState(prev => {
        const result = moveFromOther && prev.result
          ? { ...prev.result, added: [...prev.result.added, ...response.data.added], in_other_campaigns: response.data.in_other_campaigns }
          : response.data;
        return { saving: false, error: '', result };
      });
      if (response.data.added.length) onAdded();
    } catch (error) { setState(prev => ({ ...prev, saving: false, error: errorText(error, 'The links could not be added. Try again.') })); }
  };
  const result = state.result;
  if (result) return <div className="campaign-link-results">
    {result.added.length > 0 && <section className="link-result success"><h3><Check size={15} />{result.added.length} added to {campaign.name}</h3><ul>{result.added.slice(0, 6).map(post => <li key={post.id}><PlatformIcon name={post.platform} size={13} /><span>{post.title || 'Untitled post'}</span><small>{dateLabel(post.date)}</small></li>)}</ul>{result.added.length > 6 && <p>+ {result.added.length - 6} more</p>}</section>}
    {result.already_in_campaign > 0 && <section className="link-result neutral"><h3>{result.already_in_campaign} already in this campaign</h3></section>}
    {result.in_other_campaigns.length > 0 && <section className="link-result warning"><h3>{result.in_other_campaigns.length} {result.in_other_campaigns.length === 1 ? 'post belongs' : 'posts belong'} to another campaign</h3><ul>{result.in_other_campaigns.map(row => <li key={row.post_id}><span>{row.link}</span><small>{row.campaign}</small></li>)}</ul><button className="perf-button" disabled={state.saving} onClick={() => send(result.in_other_campaigns.map(row => row.link), true)}>Move {result.in_other_campaigns.length === 1 ? 'it' : 'them'} to {campaign.name}</button></section>}
    {result.not_found.length > 0 && <section className="link-result error"><h3>{result.not_found.length} not found in Data Hub</h3><ul>{result.not_found.map(link => <li key={link}><span>{link}</span></li>)}</ul><p>Upload the platform export in Data Hub first, then add the link again.</p></section>}
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
    <div className="campaign-form-actions"><button className="perf-button" onClick={() => { setText(''); setState({ saving: false, error: '', result: null }); }}>Add more links</button><button className="perf-button primary" onClick={onCancel}>Done</button></div>
  </div>;
  return <form className="campaign-form" onSubmit={event => { event.preventDefault(); send(links); }}>
    <label>Post links<textarea rows={6} value={text} autoFocus placeholder={'https://www.instagram.com/p/…\nhttps://www.tiktok.com/@cimbmalaysia/video/…'} onChange={event => setText(event.target.value)} />
      <small>Paste one or more links, one per line. Posts must already be in Data Hub; their metrics are filled in automatically.</small></label>
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
    <div className="campaign-form-actions"><button type="button" className="perf-button" onClick={onCancel}>Cancel</button><button className="perf-button primary" disabled={state.saving || !links.length}>{state.saving ? <><RefreshCw size={14} className="spin" />Finding posts…</> : <><Link2 size={14} />Add {links.length > 1 ? `${links.length} links` : 'post'}</>}</button></div>
  </form>;
}

function CampaignCard({ campaign, onOpen, style }) {
  return <button className="campaign-card" style={style} onClick={() => onOpen(campaign.id)} aria-label={`Open campaign ${campaign.name}`}>
    <div className="campaign-card-media"><CampaignImage campaign={campaign} /><span className="campaign-card-tag">#{campaign.hashtag}</span></div>
    <div className="campaign-card-body">
      <div className="campaign-card-title"><h3>{campaign.name}</h3><ChevronRight size={16} /></div>
      <p>{dateSpan(campaign)} · {full(campaign.posts)} {campaign.posts === 1 ? 'post' : 'posts'}</p>
      <div className="campaign-card-platforms">{campaign.platforms.map(name => <PlatformIcon key={name} name={name} size={12} />)}</div>
      <dl className="campaign-card-metrics"><div><dt>Reach</dt><dd>{compact(campaign.reach)}</dd></div><div><dt>Engagement</dt><dd>{compact(campaign.engagement)}</dd></div><div><dt>Avg. ER%</dt><dd>{percent(campaign.avg_er)}</dd></div></dl>
    </div>
  </button>;
}

function CompareCampaigns({ campaigns }) {
  const [selected, setSelected] = useState(() => campaigns.filter(c => c.posts > 0).slice(0, 3).map(c => c.id));
  const [group, setGroup] = useState('reach');
  useEffect(() => setSelected(ids => ids.filter(id => campaigns.some(c => c.id === id))), [campaigns]);
  const chosen = campaigns.filter(c => selected.includes(c.id));
  const activeGroup = COMPARE_GROUPS.find(item => item.key === group);
  const chartRows = chosen.map(c => ({ name: c.name, ...Object.fromEntries(activeGroup.rows.map(([key, label]) => [label, c[key] ?? 0])) }));
  const toggle = id => setSelected(ids => ids.includes(id) ? ids.filter(value => value !== id) : ids.length >= 6 ? ids : [...ids, id]);
  return <Panel title="Compare Campaigns" subtitle="Select up to six campaigns · all campaign posts, organic and paid" className="campaign-compare">
    <div className="compare-picker" role="group" aria-label="Campaigns to compare">{campaigns.map(c => <button key={c.id} aria-pressed={selected.includes(c.id)} onClick={() => toggle(c.id)}><CampaignImage campaign={c} className="is-chip" /><span>{c.name}</span>{selected.includes(c.id) && <Check size={13} />}</button>)}</div>
    {chosen.length < 2 ? <Empty icon={Trophy} title="Pick at least two campaigns">Select campaigns above to compare posts, reach, views and engagement rate side by side.</Empty> : <>
      <div className="compare-chart-head"><div className="metric-selector" role="group" aria-label="Chart metric"><span>Chart</span>{COMPARE_GROUPS.map(item => <button key={item.key} aria-pressed={group === item.key} onClick={() => setGroup(item.key)}>{item.label}</button>)}</div></div>
      <div className="compare-chart" role="img" aria-label={`${activeGroup.label} by campaign`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <BarChart data={chartRows} margin={{ top: 14, right: 8, left: 0, bottom: 4 }} barGap={3} barCategoryGap="24%">
            <CartesianGrid stroke="#f0f0f4" vertical={false} /><XAxis dataKey="name" tick={CHART_STYLE} axisLine={false} tickLine={false} interval={0} tickFormatter={value => value.length > 18 ? `${value.slice(0, 17)}…` : value} />
            <YAxis tick={CHART_STYLE} axisLine={false} tickLine={false} width={52} tickFormatter={group === 'avg_er' ? value => `${value}%` : compact} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#faf6f8' }} formatter={value => activeGroup.format(value)} />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
            {activeGroup.rows.map(([, label], index) => <Bar key={label} dataKey={label} fill={SPLIT_COLORS[index]} radius={[3, 3, 0, 0]} maxBarSize={34} />)}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="perf-table-scroll"><table className="compare-table">
        <thead><tr><th>Metric</th>{chosen.map(c => <th key={c.id}><span className="compare-head"><CampaignImage campaign={c} className="is-chip" />{c.name}</span></th>)}</tr></thead>
        <tbody>{COMPARE_GROUPS.map(item => item.rows.map(([key, label], index) => {
          const values = chosen.map(c => c[key]).filter(value => value != null);
          const best = values.length > 1 ? Math.max(...values) : null;
          return <tr key={key} className={index === 0 ? 'group-start' : ''}><th scope="row">{label}</th>{chosen.map(c => <td key={c.id} className={best != null && c[key] === best && best > 0 ? 'is-best' : ''}>{best != null && c[key] === best && best > 0 && <Trophy size={11} />}{item.format(c[key])}</td>)}</tr>;
        }))}</tbody>
      </table></div>
      <p className="panel-footnote">Reach counts views for TikTok and YouTube and impressions for LinkedIn, as elsewhere on the dashboard. Avg. ER% is the mean of each post’s ER%. <Trophy size={10} /> marks the highest value in each row.</p>
    </>}
  </Panel>;
}

const DETAIL_METRICS = [
  { key: 'posts', label: 'Posts', format: full, icon: FileText },
  { key: 'reach', label: 'Reach', format: full, icon: Megaphone, help: 'TikTok and YouTube count views and LinkedIn counts impressions as reach.' },
  { key: 'views', label: 'Views', format: full, icon: Eye },
  { key: 'engagement', label: 'Engagement', format: full, icon: Heart },
  { key: 'avg_er', label: 'Avg. ER%', format: percent, icon: Percent, rate: true, help: 'Mean of each campaign post’s ER%.' },
];
const SPLIT_LABELS = ['Total', 'Organic', 'Paid'];

const INSIGHT_KINDS = {
  insight: { label: 'Insight', icon: Sparkles },
  decision: { label: 'Decision', icon: ArrowUpRight },
};

// Five AI insights for one campaign, generated on request by the same CIMB Insights service as Key Insights.
function CampaignInsights({ campaignId }) {
  const [state, setState] = useState({ loading: false, items: [], error: '', fallback: false });
  const generate = async () => {
    setState(prev => ({ ...prev, loading: true, error: '' }));
    try {
      const { data } = await axios.get(`${API_URL}/campaigns/${campaignId}/insights`, { timeout: 60000 });
      setState({ loading: false, items: data.insights || [], error: '', fallback: !!data._meta?.fallback });
    } catch (error) {
      setState(prev => ({ ...prev, loading: false, error: errorText(error, 'AI insights are unavailable right now. Try again shortly.') }));
    }
  };
  return <aside className="campaign-insights" aria-label="AI insights">
    <div className="campaign-insights-head"><span><Lightbulb size={16} />AI insights</span>
      {state.items.length > 0 && <button className="text-button" disabled={state.loading} onClick={generate}>{state.loading ? 'Generating…' : 'Regenerate'} <RefreshCw size={12} /></button>}</div>
    {state.loading && !state.items.length ? <div className="campaign-insights-loading">{[0, 1, 2, 3, 4].map(i => <i key={i} />)}</div>
      : state.items.length ? <ol className="campaign-insights-list">{state.items.map((item, index) => {
        const kind = INSIGHT_KINDS[item.kind] || INSIGHT_KINDS.insight;
        const Icon = kind.icon;
        return <li key={index} className={`is-${item.kind}`} style={{ '--item-delay': `${index * 60}ms` }}><span className="insight-icon" title={kind.label}><Icon size={12} /></span><p><small>{kind.label}</small>{item.text.replace(/\*\*/g, '')}</p></li>;
      })}</ol>
        : <div className="campaign-insights-empty"><Sparkles size={22} /><strong>Get 5 insights on this campaign</strong><p>What this campaign's numbers really mean, and the decisions they point to.</p><button className="perf-button primary" onClick={generate}>Generate AI insights</button></div>}
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
    <p className="panel-footnote">{state.items.length ? (state.fallback ? 'Calculated highlights · AI was unavailable' : 'AI-generated with CIMB Insights · review before sharing') : "Uses only this campaign's aggregate numbers."}</p>
  </aside>;
}

// One campaign's totals split into organic and paid: a chart for the chosen metric and a table of all of them.
function CampaignBreakdown({ campaign }) {
  const [metricKey, setMetricKey] = useState('reach');
  const metric = DETAIL_METRICS.find(item => item.key === metricKey);
  const values = m => [campaign[m.key], campaign[`organic_${m.key}`], campaign[`paid_${m.key}`]];
  const chartRows = SPLIT_LABELS.map((name, i) => ({ name, value: values(metric)[i] ?? 0 }));
  const axis = metric.rate ? value => `${value}%` : compact;
  return <section className="perf-panel campaign-breakdown" aria-label="Campaign performance">
    <div className="panel-heading"><div><h2>Campaign performance</h2><p>All campaign posts · organic and paid split</p></div>
      <div className="metric-selector" role="group" aria-label="Chart metric"><span>Chart</span>{DETAIL_METRICS.map(item => <button key={item.key} aria-pressed={metricKey === item.key} onClick={() => setMetricKey(item.key)}>{item.label}</button>)}</div>
    </div>
    <div className="campaign-breakdown-body">
      <div className="campaign-breakdown-chart" role="img" aria-label={`${metric.label}: total, organic and paid`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
          <BarChart data={chartRows} margin={{ top: 28, right: 12, left: 4, bottom: 4 }} barCategoryGap="28%">
            <CartesianGrid stroke="#f0f0f4" vertical={false} />
            <XAxis dataKey="name" tick={{ ...CHART_STYLE, fontSize: 13 }} axisLine={false} tickLine={false} />
            <YAxis tick={CHART_STYLE} axisLine={false} tickLine={false} width={56} tickFormatter={axis} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: '#faf6f8' }} formatter={value => [metric.format(value), metric.label]} />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={86}>
              {chartRows.map((row, i) => <Cell key={row.name} fill={SPLIT_COLORS[i]} />)}
              <LabelList dataKey="value" position="top" formatter={metric.rate ? percent : compact} style={{ fontSize: 13, fontWeight: 700, fill: '#3f3543' }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="perf-table-scroll">
        <table className="compare-table campaign-breakdown-table">
          <thead><tr><th>Metric</th>{SPLIT_LABELS.map((label, i) => <th key={label}><span className="split-head"><i style={{ background: SPLIT_COLORS[i] }} />{label}</span></th>)}</tr></thead>
          <tbody>{DETAIL_METRICS.map(item => {
            const [total, organic, paid] = values(item);
            const organicShare = !item.rate && total ? (organic || 0) / total * 100 : null;
            const Icon = item.icon;
            return <tr key={item.key} className={metricKey === item.key ? 'is-active' : ''} onClick={() => setMetricKey(item.key)} title="Show in chart">
              <th scope="row"><span className="breakdown-metric"><span className="breakdown-icon"><Icon size={14} /></span>{item.label}{item.help && <span className="metric-help" tabIndex={0} aria-label={item.help}><Info size={11} /><span role="tooltip">{item.help}</span></span>}</span>
                {organicShare != null && <span className="share-bar" aria-label={`${organicShare.toFixed(0)}% organic`}><i style={{ width: `${organicShare}%` }} /></span>}</th>
              <td className="is-total">{item.format(total)}</td><td>{item.format(organic)}</td><td>{item.format(paid)}</td>
            </tr>;
          })}</tbody>
        </table>
        <p className="panel-footnote">Bar under each metric: organic share of the total. Click a row to chart it.</p>
      </div>
      <CampaignInsights key={campaign.id} campaignId={campaign.id} />
    </div>
  </section>;
}

function CampaignList({ onOpen, onChanged }) {
  const [state, setState] = useState({ loading: true, campaigns: [], error: '' });
  const [modal, setModal] = useState(null); // {step: 'form'|'matched'|'links', campaign, result}
  const [search, setSearch] = useState('');
  const load = () => {
    setState(prev => ({ ...prev, loading: true, error: '' }));
    axios.get(`${API_URL}/campaigns`, { timeout: 60000 })
      .then(response => setState({ loading: false, campaigns: response.data.campaigns || [], error: '' }))
      .catch(() => setState({ loading: false, campaigns: [], error: 'Campaigns could not be loaded.' }));
  };
  useEffect(load, []);
  const campaigns = state.campaigns.filter(c => `${c.name} ${c.hashtag}`.toLowerCase().includes(search.trim().toLowerCase().replace(/^#/, '')));
  const totals = state.campaigns.reduce((acc, c) => ({ posts: acc.posts + c.posts, reach: acc.reach + c.reach, engagement: acc.engagement + c.engagement }), { posts: 0, reach: 0, engagement: 0 });
  const closeModal = () => { setModal(null); };
  const saved = data => { setModal({ step: 'matched', campaign: data.campaign, result: data }); load(); onChanged(); };

  return <div className="campaigns-view">
    <div className="campaigns-hero">
      <div><span className="campaigns-eyebrow"><Flag size={13} />Campaign hub</span><h2>Campaigns</h2><p>Create campaigns, group their posts by hashtag or link, and see how each campaign performs.</p></div>
      <button className="perf-button primary campaigns-new" onClick={() => setModal({ step: 'form' })}><Plus size={15} />New campaign</button>
    </div>
    <div className="perf-kpis campaign-kpis">
      <Kpi label="Campaigns" value={state.loading ? '—' : full(state.campaigns.length)} icon={Flag}><span className="delta neutral">Manage below</span></Kpi>
      <Kpi label="Campaign posts" value={state.loading ? '—' : full(totals.posts)} icon={FileText}><span className="delta neutral">Across all campaigns</span></Kpi>
      <Kpi label="Total Reach" value={state.loading ? '—' : full(totals.reach)} icon={Megaphone} help="TikTok and YouTube count views and LinkedIn counts impressions as reach."><span className="delta neutral">All campaign posts</span></Kpi>
      <Kpi label="Total Engagement" value={state.loading ? '—' : full(totals.engagement)} icon={Heart} tone="red"><span className="delta neutral">All campaign posts</span></Kpi>
    </div>

    <Panel title="Manage Campaigns" subtitle="Open a campaign to see its posts, add content and edit details" className="campaign-manage" action={state.campaigns.length > 3 ? <label className="campaign-search"><Search size={14} /><span className="sr-only">Search campaigns</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search campaigns or hashtags…" /></label> : null}>
      {state.loading ? <div className="cross-loading"><RefreshCw size={19} />Loading campaigns…</div>
        : state.error ? <Empty icon={Flag} title={state.error} action={<button className="perf-button" onClick={load}>Try again</button>}>Check the connection and try again.</Empty>
          : !state.campaigns.length ? <div className="campaigns-empty"><span className="empty-icon"><Flag size={24} strokeWidth={1.5} /></span><strong>Create your first campaign</strong><p>Give it a name, a picture and its hashtag. Every Data Hub post that uses the hashtag is added automatically.</p><button className="perf-button primary" onClick={() => setModal({ step: 'form' })}><Plus size={14} />New campaign</button></div>
            : <div className="campaign-grid">{campaigns.map((campaign, index) => <CampaignCard key={campaign.id} campaign={campaign} onOpen={onOpen} style={{ '--card-delay': `${Math.min(index, 8) * 40}ms` }} />)}<button className="campaign-card is-new" onClick={() => setModal({ step: 'form' })}><span><Plus size={22} /></span><strong>New campaign</strong><small>Name, picture and hashtag</small></button></div>}
    </Panel>

    {state.campaigns.length > 1 && <CompareCampaigns campaigns={state.campaigns} />}

    {modal?.step === 'form' && <Modal title="New campaign" subtitle="Posts with this hashtag in their caption join the campaign automatically." onClose={closeModal}><CampaignForm onSaved={saved} onCancel={closeModal} /></Modal>}
    {modal?.step === 'matched' && <Modal title={modal.campaign.name} onClose={closeModal}><MatchSummary result={modal.result} hashtag={modal.campaign.hashtag} onAddPosts={() => setModal(prev => ({ ...prev, step: 'links' }))} onDone={() => { closeModal(); onOpen(modal.campaign.id); }} /></Modal>}
    {modal?.step === 'links' && <Modal title="Add posts by link" subtitle={`Add Data Hub posts to ${modal.campaign.name}`} onClose={closeModal} wide><AddPostsForm campaign={modal.campaign} onAdded={() => { load(); onChanged(); }} onCancel={() => { closeModal(); onOpen(modal.campaign.id); }} /></Modal>}
  </div>;
}

function CampaignDetail({ campaignId, onBack, onChanged }) {
  const [range, setRange] = useState({ start: '', end: '' });
  const [reload, setReload] = useState(0);
  const [state, setState] = useState({ loading: true, campaign: null, posts: [], error: '' });
  const [thumbnails, setThumbnails] = useState([]);
  const [search, setSearch] = useState('');
  const [platform, setPlatform] = useState(ALL_PLATFORMS);
  const [sort, setSort] = useState('date');
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(null); // 'links' | 'edit' | {step: 'matched', result}
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setState(prev => ({ ...prev, loading: true, error: '' }));
    axios.get(`${API_URL}/campaigns/${campaignId}/posts`, { params: queryFor(range), signal: controller.signal, timeout: 60000 })
      .then(response => setState({ loading: false, campaign: response.data.campaign, posts: response.data.posts || [], error: '' }))
      .catch(error => { if (!controller.signal.aborted) setState(prev => ({ ...prev, loading: false, error: error.response?.status === 404 ? 'This campaign no longer exists.' : 'Campaign posts could not be loaded.' })); });
    return () => controller.abort();
  }, [campaignId, range, reload]);

  const span = state.campaign?.first_post ? { start: state.campaign.first_post.slice(0, 10), end: state.campaign.last_post.slice(0, 10) } : null;
  useEffect(() => {
    if (!span) return undefined;
    const controller = new AbortController();
    axios.get(`${API_URL}/post-thumbnails`, { params: { start_date: span.start, end_date: span.end }, signal: controller.signal, timeout: 60000 })
      .then(response => setThumbnails(response.data?.items || []))
      .catch(() => {});
    return () => controller.abort();
  }, [span?.start, span?.end]); // eslint-disable-line react-hooks/exhaustive-deps

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return state.posts
      .filter(post => platform === ALL_PLATFORMS || post.platform === platform)
      .filter(post => !term || `${post.title} ${post.format} ${post.platform} ${post.collab}`.toLowerCase().includes(term))
      .slice().sort((a, b) => sort === 'date' ? String(b.date || '').localeCompare(String(a.date || '')) : (b[sort] || 0) - (a[sort] || 0));
  }, [state.posts, search, platform, sort]);
  useEffect(() => setPage(1), [search, platform, sort, range]);
  useEffect(() => { window.scrollTo({ top: 0, behavior: 'smooth' }); }, [campaignId]);
  const pageSize = 15;
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * pageSize;
  const visible = rows.slice(pageStart, pageStart + pageSize);
  const refresh = () => { setReload(value => value + 1); onChanged(); };

  const removePost = async post => {
    if (!window.confirm(`Remove “${post.title || 'this post'}” from ${state.campaign.name}? It stays in Data Hub.`)) return;
    setBusy(post.id);
    try { await axios.delete(`${API_URL}/campaigns/${campaignId}/posts/${post.id}`); refresh(); } catch { setNotice('The post could not be removed. Try again.'); }
    setBusy('');
  };
  const resync = async () => {
    setBusy('sync');
    try {
      const { data } = await axios.post(`${API_URL}/campaigns/${campaignId}/sync`);
      setNotice(data.matched ? `${data.matched} new ${data.matched === 1 ? 'post' : 'posts'} with #${state.campaign.hashtag} added.` : `No new posts with #${state.campaign.hashtag} found.`);
      if (data.matched) refresh();
    } catch { setNotice('Hashtag sync failed. Try again.'); }
    setBusy('');
  };
  const remove = async () => {
    if (!window.confirm(`Delete the campaign “${state.campaign.name}”? Its posts stay in Data Hub but will no longer be linked to a campaign.`)) return;
    setBusy('delete');
    try { await axios.delete(`${API_URL}/campaigns/${campaignId}`); onChanged(); onBack(); } catch { setNotice('The campaign could not be deleted. Try again.'); setBusy(''); }
  };

  const campaign = state.campaign;
  if (!campaign) return <div className="campaigns-view"><button className="perf-button back-button" onClick={onBack}><ArrowLeft size={15} />All campaigns</button>{state.loading ? <div className="cross-loading"><RefreshCw size={19} />Loading campaign…</div> : <Empty icon={Flag} title={state.error || 'Campaign not found'}>Return to the campaign list and try again.</Empty>}</div>;

  return <div className="campaigns-view campaign-detail">
    <button className="perf-button back-button" onClick={onBack}><ArrowLeft size={15} />All campaigns</button>
    <section className="campaign-detail-hero">
      <CampaignImage campaign={campaign} className="is-hero" />
      <div className="campaign-detail-text"><span className="campaigns-eyebrow"><Hash size={13} />{campaign.hashtag}</span><h2>{campaign.name}</h2><p>{dateSpan(campaign)} · {full(campaign.posts)} {campaign.posts === 1 ? 'post' : 'posts'}</p><div className="campaign-card-platforms">{campaign.platforms.map(name => <span key={name}><PlatformIcon name={name} size={12} />{name}</span>)}</div></div>
      <div className="campaign-detail-actions">
        <button className="perf-button primary" onClick={() => setModal('links')}><Plus size={14} />Add posts</button>
        <button className="perf-button" disabled={busy === 'sync'} onClick={resync} title={`Find new Data Hub posts with #${campaign.hashtag}`}><RefreshCw size={14} className={busy === 'sync' ? 'spin' : ''} />Sync hashtag</button>
        <button className="perf-button" onClick={() => setModal('edit')}><Pencil size={14} />Edit</button>
        <button className="perf-button danger" disabled={busy === 'delete'} onClick={remove} aria-label="Delete campaign" title="Delete campaign"><Trash2 size={14} /></button>
      </div>
    </section>
    {notice && <div className="data-notice campaign-notice" role="status"><Check size={16} /><span>{notice}</span><button onClick={() => setNotice('')} aria-label="Dismiss"><X size={14} /></button></div>}

    <CampaignBreakdown campaign={campaign} />

    <section className="perf-panel campaign-posts-panel" aria-label="Campaign posts">
      <div className="panel-heading"><div><h2>Campaign content</h2><p>{full(rows.length)} matching {rows.length === 1 ? 'post' : 'posts'}{range.start ? ` · ${dateLabel(range.start)} – ${dateLabel(range.end)}` : ''}</p></div><DateFilter range={range} onApply={setRange} label="Campaign posts period" /></div>
      <div className="campaign-post-controls">
        <label className="cross-content-search"><Search size={15} /><span className="sr-only">Search campaign posts</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search caption, format, platform or collab…" /></label>
        <label className="post-platform-filter"><span className="sr-only">Filter by platform</span><select aria-label="Filter by platform" value={platform} onChange={event => setPlatform(event.target.value)}><option>{ALL_PLATFORMS}</option>{PLATFORMS.map(item => <option key={item.name}>{item.name}</option>)}</select></label>
        <div className="metric-selector" role="group" aria-label="Sort campaign posts"><span>Sort by</span>{SORTS.map(item => <button key={item.key} aria-pressed={sort === item.key} onClick={() => setSort(item.key)}>{item.label}</button>)}</div>
      </div>
      {state.loading && !state.posts.length ? <div className="cross-loading"><RefreshCw size={19} />Loading posts…</div> : visible.length ? <>
        <div className="cross-table-scroll"><table className="campaign-post-table">
          <thead><tr><th>Post</th><th>Date</th><th>Platform</th><th>Format</th><th>Organic/Paid</th><th>Collab</th><th>Reach</th><th>Views</th><th>Engagement</th><th>ER%</th><th>Likes</th><th>Comments</th><th>Shares</th><th>Saves</th><th><span className="sr-only">Actions</span></th></tr></thead>
          <tbody>{visible.map(post => <tr key={post.id}>
            <td><div className="post-identity"><PostThumbnail post={post} thumbnails={thumbnails} /><div>{safeLink(post.link) ? <a href={safeLink(post.link)} target="_blank" rel="noreferrer" title={post.title}>{post.title || 'Untitled post'}<ExternalLink size={10} /></a> : <strong title={post.title}>{post.title || 'Untitled post'}</strong>}</div></div></td>
            <td>{dateLabel(post.date)}</td>
            <td><span className="campaign-platform"><PlatformIcon name={post.platform} size={12} />{post.platform}</span></td>
            <td>{post.format || '—'}</td>
            <td><span className={`organic-chip ${post.is_organic === false ? 'is-paid' : ''}`}>{post.is_organic === false ? 'Paid' : 'Organic'}</span></td>
            <td><span className="campaign-collab" title={post.collab}>{post.collab || '—'}</span></td>
            <td className={sort === 'reach' ? 'is-sorted' : ''}>{full(post.reach)}</td><td className={sort === 'views' ? 'is-sorted' : ''}>{full(post.views)}</td>
            <td className={sort === 'engagement' ? 'is-sorted' : ''}>{full(post.engagement)}</td><td className={`er-cell ${sort === 'engagement_rate' ? 'is-sorted' : ''}`}>{percent(post.engagement_rate)}</td>
            <td>{full(post.likes)}</td><td>{full(post.comments)}</td><td>{full(post.shares)}</td><td>{full(post.favorites)}</td>
            <td><button className="icon-button" disabled={busy === post.id} aria-label={`Remove ${post.title || 'post'} from campaign`} title="Remove from campaign" onClick={() => removePost(post)}><X size={14} /></button></td>
          </tr>)}</tbody>
        </table></div>
        <nav className="post-pagination cross-pagination" aria-label="Campaign post pages"><span>Showing {pageStart + 1}–{Math.min(pageStart + pageSize, rows.length)} of {rows.length}</span><div><button aria-label="Previous page" disabled={currentPage === 1} onClick={() => setPage(value => Math.max(1, value - 1))}><ChevronLeft size={15} /></button><span>Page {currentPage} of {pageCount}</span><button aria-label="Next page" disabled={currentPage === pageCount} onClick={() => setPage(value => Math.min(pageCount, value + 1))}><ChevronRight size={15} /></button></div></nav>
      </> : <Empty icon={FileText} title={state.posts.length ? 'No matching posts' : 'No posts in this campaign yet'} action={!state.posts.length && <button className="perf-button primary" onClick={() => setModal('links')}><Plus size={14} />Add posts by link</button>}>{state.posts.length ? 'Try another search, platform or date range.' : range.start ? 'No campaign posts in this period.' : `Posts with #${campaign.hashtag} appear here automatically after they are uploaded to Data Hub.`}</Empty>}
    </section>

    {modal === 'links' && <Modal title="Add posts by link" subtitle={`Add Data Hub posts to ${campaign.name}`} onClose={() => setModal(null)} wide><AddPostsForm campaign={campaign} onAdded={refresh} onCancel={() => setModal(null)} /></Modal>}
    {modal === 'edit' && <Modal title="Edit campaign" subtitle="Renaming keeps every post in the campaign." onClose={() => setModal(null)}><CampaignForm campaign={campaign} onCancel={() => setModal(null)} onSaved={data => { refresh(); if (data.matched) setModal({ step: 'matched', result: data, campaign: data.campaign }); else setModal(null); }} /></Modal>}
    {modal?.step === 'matched' && <Modal title={modal.campaign.name} onClose={() => setModal(null)}><MatchSummary result={modal.result} hashtag={modal.campaign.hashtag} onAddPosts={() => setModal('links')} onDone={() => setModal(null)} doneLabel="Done" /></Modal>}
  </div>;
}

export default function Campaigns({ campaignId, onOpen, onChanged }) {
  return campaignId
    ? <CampaignDetail key={campaignId} campaignId={campaignId} onBack={() => onOpen(null)} onChanged={onChanged} />
    : <CampaignList onOpen={onOpen} onChanged={onChanged} />;
}
