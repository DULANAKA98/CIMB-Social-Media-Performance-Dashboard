/* eslint-disable react/prop-types */
// Building blocks shared by the dashboard pages.
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { BarChart3, CalendarDays, ChevronDown, Info, X } from 'lucide-react';
import { FaFacebookF, FaInstagram, FaLinkedinIn, FaTiktok, FaYoutube } from 'react-icons/fa6';
import { API_URL } from './usePerformanceData';
import { PLATFORMS, dateLabel, safeLink, thumbnailForPost } from './model';

export const BRAND_ICONS = { Facebook: FaFacebookF, Instagram: FaInstagram, 'Instagram Stories': FaInstagram, TikTok: FaTiktok, YouTube: FaYoutube, LinkedIn: FaLinkedinIn };
export const CHART_STYLE = { fontSize: 12, fill: '#818493' };
export const TOOLTIP_STYLE = { background: '#fff', border: '1px solid #e9e9ef', borderRadius: 8, fontSize: 14, color: '#25232a', boxShadow: '0 5px 25px #26081510' };

export function trapFocus(event) {
  if (event.key !== 'Tab') return;
  const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]), input:not([disabled]), select, a[href]')];
  if (!controls.length) return;
  const first = controls[0];
  const last = controls.at(-1);
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

export function PlatformIcon({ name, size = 16 }) {
  const Icon = BRAND_ICONS[name] || BarChart3;
  const color = PLATFORMS.find(platform => platform.name === name)?.color;
  return <Icon size={size} color={color} aria-hidden="true" />;
}

export function Panel({ title, subtitle, children, className = '', action }) {
  return <section className={`perf-panel ${className}`} aria-label={title}>
    <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>
    {children}
  </section>;
}

export function Empty({ icon: Icon = BarChart3, title = 'No data for this period', children, action }) {
  return <div className="perf-empty"><span className="empty-icon"><Icon size={23} strokeWidth={1.5} /></span><strong>{title}</strong>{children && <p>{children}</p>}{action}</div>;
}

export function Kpi({ label, value, icon: Icon, children, help, tone = '' }) {
  return <section className="perf-kpi" aria-label={label}>
    <div><h2 className="kpi-heading"><span>{label}</span>{help && <span className="metric-help" tabIndex={0} aria-label={`${label}: ${help}`}><Info size={12} /><span role="tooltip">{help}</span></span>}</h2><strong>{value}</strong></div><span className={`kpi-symbol ${tone}`}><Icon size={21} strokeWidth={1.6} /></span>
    <div className="kpi-detail">{children}</div>
  </section>;
}

export function DateFilter({ range, onApply, label = 'Reporting period' }) {
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
    {open && <div className="date-popover" role="dialog" aria-label={label}>
      <div className="popover-title"><strong>{label}</strong><button aria-label="Close date filter" className="icon-button" onClick={() => setOpen(false)}><X size={16} /></button></div>
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

// Fired by Download report before printing, so components can show everything the report needs.
export const PREPARE_PRINT_EVENT = 'cimb:prepare-print';

// Load every image inside `root` now (lazy ones included) and resolve once all have loaded or failed,
// or after `timeoutMs` so a slow image never blocks the report.
let pendingThumbnailLookups = 0;

export function waitForImages(root, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise(resolve => {
    // Give React a moment to render rows added for printing, then let per-post thumbnail lookups finish.
    const waitForLookups = () => {
      if (pendingThumbnailLookups > 0 && Date.now() < deadline) { window.setTimeout(waitForLookups, 200); return; }
      window.setTimeout(waitForLoads, 150);
    };
    const waitForLoads = () => {
      const images = Array.from((root || document).querySelectorAll('img'));
      images.forEach(img => { if (img.loading === 'lazy') img.loading = 'eager'; });
      const pending = images.filter(img => !img.complete);
      if (!pending.length) { resolve(); return; }
      let left = pending.length;
      const done = () => { left -= 1; if (left <= 0) { window.clearTimeout(timer); resolve(); } };
      const timer = window.setTimeout(resolve, Math.max(1500, deadline - Date.now()));
      pending.forEach(img => { img.addEventListener('load', done, { once: true }); img.addEventListener('error', done, { once: true }); });
    };
    window.setTimeout(waitForLookups, 150);
  });
}

export function PostThumbnail({ post, thumbnails }) {
  const metricoolSrc = thumbnailForPost(post, thumbnails);
  const postUrl = safeLink(post.link);
  const [fallbackSrc, setFallbackSrc] = useState('');
  const [failedSrc, setFailedSrc] = useState('');
  useEffect(() => { setFallbackSrc(''); setFailedSrc(''); }, [metricoolSrc, postUrl]);
  useEffect(() => {
    if (!postUrl || fallbackSrc || (metricoolSrc && failedSrc !== metricoolSrc)) return;
    const controller = new AbortController();
    pendingThumbnailLookups += 1;
    axios.get(`${API_URL}/post-thumbnail`, { params: { url: postUrl }, signal: controller.signal, timeout: 25000 })
      .then(response => setFallbackSrc(safeLink(response.data?.picture) || ''))
      .catch(() => {})
      .finally(() => { pendingThumbnailLookups -= 1; });
    return () => controller.abort();
  }, [fallbackSrc, failedSrc, metricoolSrc, postUrl]);
  const src = metricoolSrc && failedSrc !== metricoolSrc ? metricoolSrc : fallbackSrc && failedSrc !== fallbackSrc ? fallbackSrc : '';
  if (!src) return <span className="post-format-icon"><PlatformIcon name={post.platform} size={18} /></span>;
  return <span className="post-thumbnail"><img src={src} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailedSrc(src)} /></span>;
}
