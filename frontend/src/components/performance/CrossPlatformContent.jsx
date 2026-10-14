/* eslint-disable react/prop-types */
import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { ChevronLeft, ChevronRight, ExternalLink, FileText, RefreshCw, Search } from 'lucide-react';
import { FaFacebookF, FaInstagram, FaLinkedinIn, FaTiktok, FaYoutube } from 'react-icons/fa6';
import { API_URL, queryFor } from './usePerformanceData';
import { compact, percent, safeLink } from './model';

const PLATFORM_ICONS = {
  Facebook: FaFacebookF,
  Instagram: FaInstagram,
  LinkedIn: FaLinkedinIn,
  TikTok: FaTiktok,
  YouTube: FaYoutube,
};

const METRICS = [
  { key: 'avg_er', label: 'ER%' },
  { key: 'engagement', label: 'Total engagement' },
  { key: 'views', label: 'Views' },
  { key: 'reach', label: 'Reach' },
];

const formatMetric = (metric, value) => value == null ? '—' : metric === 'avg_er' ? percent(value) : compact(value);

function PlatformHeading({ name }) {
  const Icon = PLATFORM_ICONS[name];
  return <span className="cross-platform-heading">{Icon && <Icon size={13} aria-hidden="true" />}{name}</span>;
}

function MetricCell({ bucket, metric, platform, title }) {
  if (!bucket) return <span className="cross-metric-empty">—</span>;
  const value = formatMetric(metric, bucket[metric]);
  const href = safeLink(bucket.link);
  const detail = bucket.posts > 1 ? `${bucket.posts} posts` : '1 post';
  return <div className="cross-metric-cell">
    {href ? <a href={href} target="_blank" rel="noreferrer" aria-label={`Open ${platform} post for ${title}`}>{value}<ExternalLink size={10} /></a> : <strong>{value}</strong>}
    <small>{detail}</small>
  </div>;
}

export default function CrossPlatformContent({ range, refreshKey = 0 }) {
  const [metric, setMetric] = useState('avg_er');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [state, setState] = useState({ loading: true, data: null, error: '' });

  useEffect(() => {
    const controller = new AbortController();
    setState({ loading: true, data: null, error: '' });
    axios.get(`${API_URL}/cross-platform-content`, { params: queryFor(range), signal: controller.signal, timeout: 60000 })
      .then(response => { if (!controller.signal.aborted) setState({ loading: false, data: response.data, error: '' }); })
      .catch(error => {
        if (controller.signal.aborted) return;
        const message = error.response?.status === 400 ? 'No posts were found for this reporting period.' : 'Unable to load cross-platform content performance.';
        setState({ loading: false, data: null, error: message });
      });
    return () => controller.abort();
  }, [range, refreshKey]);

  const platforms = state.data?.platforms || ['Facebook', 'Instagram', 'LinkedIn', 'TikTok', 'YouTube'];
  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return [...(state.data?.rows || [])]
      .filter(row => !term || `${row.pillar_category} ${row.content_title} ${row.caption}`.toLowerCase().includes(term))
      .sort((left, right) => (right.total?.[metric] ?? -Infinity) - (left.total?.[metric] ?? -Infinity));
  }, [state.data, metric, search]);

  useEffect(() => setPage(1), [metric, search, range]);
  const pageSize = 15;
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * pageSize;
  const visible = rows.slice(pageStart, pageStart + pageSize);
  const metricLabel = metric === 'avg_er' ? 'Avg. ER%' : METRICS.find(item => item.key === metric)?.label || 'ER%';

  return <div className="cross-platform-view">
    <div className="cross-platform-intro">
      <div><h2>Cross Platform Content Performance</h2><p>Compare matching content across social platforms for the selected reporting period.</p></div>
      <span>{rows.length.toLocaleString('en-GB')} content {rows.length === 1 ? 'group' : 'groups'}</span>
    </div>

    <section className="perf-panel cross-platform-panel" aria-label="Cross-platform content comparison">
      <div className="cross-platform-controls">
        <label className="cross-content-search"><Search size={15} /><span className="sr-only">Search content</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search pillar, title or caption…" /></label>
        <div className="metric-selector" role="group" aria-label="Comparison metric">
          <span>Compare by</span>
          {METRICS.map(item => <button key={item.key} aria-pressed={metric === item.key} onClick={() => setMetric(item.key)}>{item.label}</button>)}
        </div>
      </div>

      {state.loading ? <div className="cross-loading"><RefreshCw size={19} />Loading content comparison…</div> : state.error ? <div className="perf-empty"><span className="empty-icon"><FileText size={23} /></span><strong>{state.error}</strong><p>Choose another reporting period or refresh the dashboard.</p></div> : visible.length ? <>
        <div className="cross-table-scroll">
          <table className="cross-platform-table">
            <thead><tr><th>Pillar category</th><th>Content title</th><th>Caption</th>{platforms.map(name => <th key={name}><PlatformHeading name={name} /></th>)}<th>Total</th></tr></thead>
            <tbody>{visible.map(row => <tr key={row.key}>
              <td><span className="pillar-chip">{row.pillar_category}</span></td>
              <td><strong className="cross-content-title" title={row.content_title}>{row.content_title}</strong><small className="cross-match-count">Matched on {row.platform_count} {row.platform_count === 1 ? 'platform' : 'platforms'}</small></td>
              <td><span className="cross-caption" title={row.caption}>{row.caption}</span></td>
              {platforms.map(name => <td key={name}><MetricCell bucket={row.platforms?.[name]} metric={metric} platform={name} title={row.content_title} /></td>)}
              <td><strong className="cross-total" title={`${metricLabel} across matching posts`}>{formatMetric(metric, row.total?.[metric])}</strong></td>
            </tr>)}</tbody>
          </table>
        </div>
        <nav className="post-pagination cross-pagination" aria-label="Cross-platform content pages">
          <span>Showing {pageStart + 1}–{Math.min(pageStart + pageSize, rows.length)} of {rows.length}</span>
          <div><button aria-label="Previous page" disabled={currentPage === 1} onClick={() => setPage(value => Math.max(1, value - 1))}><ChevronLeft size={15} /></button><span>Page {currentPage} of {pageCount}</span><button aria-label="Next page" disabled={currentPage === pageCount} onClick={() => setPage(value => Math.min(pageCount, value + 1))}><ChevronRight size={15} /></button></div>
        </nav>
      </> : <div className="perf-empty"><span className="empty-icon"><FileText size={23} /></span><strong>No matching content</strong><p>{search ? 'Try a different search.' : 'No posts with usable captions were found in this period.'}</p></div>}

      <p className="cross-platform-note">Content is grouped when normalized stored captions match. Pillar categories use the current automatic title-based rules. Reach uses the stored platform value; TikTok and YouTube use views, while LinkedIn uses impressions.</p>
    </section>
  </div>;
}
