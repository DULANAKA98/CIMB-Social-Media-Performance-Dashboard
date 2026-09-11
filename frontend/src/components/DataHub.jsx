import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Plus, Trash2, Check, AlertCircle, ChevronLeft, ChevronRight, Search, ExternalLink, UploadCloud } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

const PLATFORMS = ['Facebook', 'Instagram', 'TikTok', 'YouTube', 'LinkedIn'];
const PLATFORM_UPLOADS = [
  { field: 'fb_file', label: 'Facebook' },
  { field: 'ig_file', label: 'Instagram Posts' },
  { field: 'ig_story_file', label: 'Instagram Stories' },
  { field: 'tt_file', label: 'TikTok' },
  { field: 'yt_file', label: 'YouTube' },
  { field: 'li_file', label: 'LinkedIn' },
];
const FORMATS = ['Video', 'Static', 'Carousel', 'Reel', 'IG Story', 'Story', 'Article', 'Unknown'];
const NUMERIC_COLS = ['reach', 'views', 'engagement', 'likes', 'comments', 'shares', 'favorites', 'reposts', 'engagement_rate'];

const COLUMNS = [
  { key: 'date', label: 'Date', width: '110px' },
  { key: 'platform', label: 'Platform', width: '115px' },
  { key: 'format', label: 'Format', width: '105px' },
  { key: 'is_organic', label: 'Organic/Paid', width: '115px' },
  { key: 'collab', label: 'Collab', width: '140px' },
  { key: 'title', label: 'Title', width: '220px' },
  { key: 'reach', label: 'Reach', width: '90px' },
  { key: 'views', label: 'Views', width: '90px' },
  { key: 'engagement', label: 'Engagement', width: '110px' },
  { key: 'engagement_rate', label: 'ER %', width: '80px' },
  { key: 'likes', label: 'Likes', width: '80px' },
  { key: 'comments', label: 'Comments', width: '95px' },
  { key: 'shares', label: 'Shares', width: '80px' },
  { key: 'favorites', label: 'Saves', width: '80px' },
  { key: 'link', label: 'Link', width: '70px' },
];

const DataHub = ({ startDate, endDate }) => {
  const [posts, setPosts] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [filterPlatform, setFilterPlatform] = useState('');
  const [dateSort, setDateSort] = useState('desc');
  const [loading, setLoading] = useState(false);

  // Upload panel
  const [platformFiles, setPlatformFiles] = useState({});
  const [fileInputKey, setFileInputKey] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState(null); // {type: 'success'|'error', text}
  const [lastSync, setLastSync] = useState(null);

  // Inline editing
  const [editingCell, setEditingCell] = useState(null); // {postId, col}
  const [editingValue, setEditingValue] = useState('');
  const [savedCell, setSavedCell] = useState(null); // {postId, col} — for green flash
  const [savingCell, setSavingCell] = useState(null);

  // Deleting
  const [deletingId, setDeletingId] = useState(null);

  // Adding a new row
  const [addingRow, setAddingRow] = useState(false);

  const fetchPosts = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit: 50 };
      if (filterPlatform) params.platform = filterPlatform;
      if (search) params.search = search;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      params.sort_order = dateSort;
      const res = await axios.get(`${API_URL}/posts`, { params });
      setPosts(res.data.posts || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch (e) {
      setPosts([]);
    } finally {
      setLoading(false);
    }
  }, [page, filterPlatform, search, startDate, endDate, dateSort]);

  useEffect(() => { fetchPosts(); }, [fetchPosts]);

  useEffect(() => { setPage(1); }, [startDate, endDate]);

  // Fetch last sync time
  useEffect(() => {
    axios.get(`${API_URL}/status`).then(res => {
      if (res.data.last_sync) setLastSync(new Date(res.data.last_sync).toLocaleString());
    }).catch(() => {});
  }, [syncing]);

  const handleSync = async (e) => {
    e.preventDefault();
    const selectedFiles = Object.entries(platformFiles).filter(([, file]) => file);
    if (!selectedFiles.length) return;
    setSyncing(true);
    setSyncMsg(null);
    try {
      const formData = new FormData();
      selectedFiles.forEach(([field, file]) => formData.append(field, file));
      const res = await axios.post(`${API_URL}/upload-platform-files`, formData);
      if (res.data.error) {
        setSyncMsg({ type: 'error', text: res.data.error });
      } else {
        setSyncMsg({ type: 'success', text: res.data.message });
        setPlatformFiles({});
        setFileInputKey(key => key + 1);
        fetchPosts();
      }
    } catch (err) {
      setSyncMsg({ type: 'error', text: 'Upload failed. Please check the spreadsheet files and try again.' });
    } finally {
      setSyncing(false);
    }
  };

  const startEdit = (postId, col, currentVal) => {
    setEditingCell({ postId, col });
    setEditingValue(currentVal !== null && currentVal !== undefined ? String(currentVal) : '');
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditingValue('');
  };

  const commitEdit = async (postId, col) => {
    const post = posts.find(p => p.id === postId);
    if (!post) return cancelEdit();
    let val = editingValue;
    if (NUMERIC_COLS.includes(col)) val = parseFloat(val) || 0;
    if (col === 'is_organic') val = val === 'true';
    setSavingCell({ postId, col });
    try {
      const res = await axios.patch(`${API_URL}/posts/${postId}`, { [col]: val });
      setPosts(prev => prev.map(p => p.id === postId ? {
        ...p,
        [col]: val,
        engagement_rate: res.data.engagement_rate ?? p.engagement_rate,
      } : p));
      setSavedCell({ postId, col });
      setTimeout(() => setSavedCell(null), 1500);
    } catch {}
    setEditingCell(null);
    setEditingValue('');
    setSavingCell(null);
  };

  const handleDelete = async (postId) => {
    if (!window.confirm('Delete this post from the database?')) return;
    setDeletingId(postId);
    try {
      await axios.delete(`${API_URL}/posts/${postId}`);
      setPosts(prev => prev.filter(p => p.id !== postId));
      setTotal(t => t - 1);
    } catch {}
    setDeletingId(null);
  };

  const handleAddRow = async () => {
    setAddingRow(true);
    try {
      const res = await axios.post(`${API_URL}/posts`, {
        platform: 'Facebook', format: 'Video', title: 'New Post',
        date: new Date().toISOString().split('T')[0],
      });
      fetchPosts();
    } catch {}
    setAddingRow(false);
  };

  const renderCell = (post, col) => {
    const isEditing = editingCell?.postId === post.id && editingCell?.col === col;
    const isSaved = savedCell?.postId === post.id && savedCell?.col === col;
    const val = post[col];

    if (isEditing) {
      if (col === 'platform') {
        return (
          <select
            value={editingValue}
            autoFocus
            onChange={e => setEditingValue(e.target.value)}
            onBlur={() => commitEdit(post.id, col)}
            style={styles.editSelect}
          >
            {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        );
      }
      if (col === 'format') {
        return (
          <select
            value={editingValue}
            autoFocus
            onChange={e => setEditingValue(e.target.value)}
            onBlur={() => commitEdit(post.id, col)}
            style={styles.editSelect}
          >
            {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
          </select>
        );
      }
      if (col === 'is_organic') {
        return (
          <select
            value={editingValue === 'false' ? 'false' : 'true'}
            autoFocus
            onChange={e => setEditingValue(e.target.value)}
            onBlur={() => commitEdit(post.id, col)}
            style={styles.editSelect}
          >
            <option value="true">Organic</option>
            <option value="false">Paid</option>
          </select>
        );
      }
      return (
        <input
          autoFocus
          value={editingValue}
          onChange={e => setEditingValue(e.target.value)}
          onBlur={() => commitEdit(post.id, col)}
          onKeyDown={e => {
            if (e.key === 'Enter') commitEdit(post.id, col);
            if (e.key === 'Escape') cancelEdit();
          }}
          style={styles.editInput}
        />
      );
    }

    if (col === 'link') {
      return val ? (
        <a href={val} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-blue)', display: 'flex', justifyContent: 'center' }}>
          <ExternalLink size={14} />
        </a>
      ) : <span style={{ color: 'rgba(255,255,255,0.2)' }}>—</span>;
    }

    if (col === 'platform') {
      const colors = { Facebook: '#1877f2', Instagram: '#e1306c', TikTok: '#00f2fe', YouTube: '#ff0000', LinkedIn: '#0a66c2' };
      return (
        <span style={{
          background: `${colors[val] || '#666'}22`,
          color: colors[val] || '#aaa',
          padding: '2px 10px', borderRadius: '999px', fontSize: 'calc(0.78rem + 2px)', fontWeight: 600,
        }}>{val}</span>
      );
    }

    if (col === 'is_organic') {
      const organic = val !== false;
      return (
        <span style={{
          background: organic ? 'rgba(16,185,129,0.14)' : 'rgba(245,158,11,0.14)',
          color: organic ? '#10b981' : '#f59e0b',
          padding: '2px 10px', borderRadius: '999px', fontSize: 'calc(0.75rem + 2px)', fontWeight: 700,
        }}>
          {organic ? 'Organic' : 'Paid'}
        </span>
      );
    }

    if (col === 'engagement_rate') {
      return <span style={{ color: '#10b981', fontWeight: 600 }}>{Number(val || 0).toFixed(2)}%</span>;
    }

    if (NUMERIC_COLS.includes(col)) {
      return <span>{Number(val || 0).toLocaleString()}</span>;
    }

    if (col === 'date') {
      try { return <span>{new Date(val).toLocaleDateString()}</span>; } catch { return <span>—</span>; }
    }

    return <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block' }}>{val || '—'}</span>;
  };

  return (
    <div>
      <h2 style={{ marginBottom: '0.4rem', fontSize: 'calc(1.5rem + 2px)', color: 'var(--accent-blue)' }}>Data Hub</h2>
      <p style={{ color: 'var(--text-secondary)', fontSize: 'calc(0.85rem + 2px)', marginBottom: '1.5rem' }}>
        Upload raw platform Excel or CSV files to the database and manage all content records directly here.
      </p>

      {/* Upload Panel */}
      <div className="glass-panel" style={{ marginBottom: '1.5rem', padding: '1.2rem 1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.8rem' }}>
          <UploadCloud size={17} color="var(--accent-purple)" />
          <span style={{ fontWeight: 700, fontSize: 'calc(0.95rem + 2px)', color: 'var(--text-primary)' }}>Upload Platform Files</span>
          {lastSync && <span style={{ marginLeft: 'auto', fontSize: 'calc(0.75rem + 2px)', color: 'var(--text-secondary)' }}>Last synced: {lastSync}</span>}
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: 'calc(0.78rem + 2px)', marginBottom: '0.9rem' }}>
          Select one or more Excel or CSV files. Excel uses a matching Raw_* sheet when available; LinkedIn also supports completed exports with an All posts sheet.
        </p>
        <form onSubmit={handleSync}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
            {PLATFORM_UPLOADS.map(({ field, label }) => (
              <label
                key={`${field}-${fileInputKey}`}
                style={{
                  display: 'flex', flexDirection: 'column', gap: '0.35rem', cursor: syncing ? 'default' : 'pointer',
                  background: 'rgba(255,255,255,0.04)', border: `1px solid ${platformFiles[field] ? 'rgba(16,185,129,0.45)' : 'rgba(255,255,255,0.12)'}`,
                  borderRadius: '10px', padding: '0.75rem 0.85rem', minWidth: 0,
                }}
              >
                <span style={{ fontWeight: 700, fontSize: 'calc(0.82rem + 2px)', color: 'var(--text-primary)' }}>{label}</span>
                <span style={{ fontSize: 'calc(0.72rem + 2px)', color: platformFiles[field] ? '#10b981' : 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {platformFiles[field]?.name || 'Choose Excel or CSV file'}
                </span>
                <input
                  type="file"
                  accept=".xlsx,.xlsm,.csv,text/csv"
                  disabled={syncing}
                  onChange={e => setPlatformFiles(files => ({ ...files, [field]: e.target.files?.[0] || null }))}
                  style={{ display: 'none' }}
                />
              </label>
            ))}
          </div>
          <button
            type="submit"
            disabled={!Object.values(platformFiles).some(Boolean) || syncing}
            style={{
              background: syncing ? 'rgba(139,92,246,0.4)' : 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))',
              color: 'white', border: 'none', borderRadius: '10px', padding: '0.7rem 1.4rem',
              fontWeight: 700, fontSize: 'calc(0.88rem + 2px)', cursor: syncing ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'inherit',
              boxShadow: '0 4px 16px rgba(139,92,246,0.3)',
            }}
          >
            {syncing
              ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: '2px', borderTopColor: 'white' }} /> Uploading…</>
              : <><UploadCloud size={15} /> Upload &amp; Sync</>
            }
          </button>
        </form>
        {syncMsg && (
          <div style={{
            marginTop: '0.7rem', display: 'flex', alignItems: 'center', gap: '0.5rem',
            color: syncMsg.type === 'success' ? '#10b981' : '#f87171', fontSize: 'calc(0.85rem + 2px)',
          }}>
            {syncMsg.type === 'success' ? <Check size={14} /> : <AlertCircle size={14} />}
            {syncMsg.text}
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ position: 'relative', flex: 1, minWidth: '200px' }}>
          <Search size={14} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)' }} />
          <input
            type="text" placeholder="Search content..."
            value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
            style={{
              width: '100%', paddingLeft: '34px', padding: '0.6rem 0.9rem 0.6rem 34px',
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: '8px', color: 'white', fontFamily: 'inherit', fontSize: 'calc(0.85rem + 2px)', outline: 'none',
            }}
          />
        </div>
        <select
          value={filterPlatform}
          onChange={e => { setFilterPlatform(e.target.value); setPage(1); }}
          style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px', color: 'white', padding: '0.6rem 0.9rem', fontFamily: 'inherit',
            fontSize: 'calc(0.85rem + 2px)', cursor: 'pointer', outline: 'none',
          }}
        >
          <option value="">All Platforms</option>
          {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <select
          value={dateSort}
          onChange={e => { setDateSort(e.target.value); setPage(1); }}
          aria-label="Sort records by date"
          style={{
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: '8px', color: 'white', padding: '0.6rem 0.9rem', fontFamily: 'inherit',
            fontSize: 'calc(0.85rem + 2px)', cursor: 'pointer', outline: 'none',
          }}
        >
          <option value="desc">Date: Newest first</option>
          <option value="asc">Date: Oldest first</option>
        </select>

        <span style={{ color: 'var(--text-secondary)', fontSize: 'calc(0.82rem + 2px)', marginLeft: 'auto' }}>
          {total.toLocaleString()} records
        </span>

        <button
          onClick={handleAddRow}
          disabled={addingRow}
          style={{
            background: 'linear-gradient(135deg, #059669, #10b981)', color: 'white',
            border: 'none', borderRadius: '8px', padding: '0.6rem 1.1rem',
            fontWeight: 700, fontSize: 'calc(0.85rem + 2px)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '0.4rem', fontFamily: 'inherit',
          }}
        >
          <Plus size={15} /> Add Row
        </button>
      </div>

      {/* Data Grid */}
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '1250px' }}>
            <thead>
              <tr>
                {COLUMNS.map(col => (
                  <th key={col.key} style={{
                    padding: '0.75rem 0.9rem', textAlign: 'left', fontSize: 'calc(0.72rem + 2px)',
                    fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase',
                    letterSpacing: '0.08em', background: 'rgba(0,0,0,0.25)',
                    borderBottom: '1px solid rgba(255,255,255,0.06)', width: col.width,
                    whiteSpace: 'nowrap',
                  }}>
                    {col.label}
                  </th>
                ))}
                <th style={{
                  padding: '0.75rem 0.9rem', background: 'rgba(0,0,0,0.25)',
                  borderBottom: '1px solid rgba(255,255,255,0.06)', width: '50px',
                }} />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={COLUMNS.length + 1} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <div className="spinner" style={{ margin: '0 auto', width: 24, height: 24, borderTopColor: 'var(--accent-purple)' }} />
                </td></tr>
              ) : posts.length === 0 ? (
                <tr><td colSpan={COLUMNS.length + 1} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: 'calc(0.9rem + 2px)' }}>
                  No content found. Upload a platform file to get started.
                </td></tr>
              ) : posts.map((post, idx) => (
                <tr
                  key={post.id}
                  style={{
                    background: idx % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(59,130,246,0.06)'}
                  onMouseLeave={e => e.currentTarget.style.background = idx % 2 === 0 ? 'rgba(255,255,255,0.01)' : 'transparent'}
                >
                  {COLUMNS.map(col => (
                    <td
                      key={col.key}
                      onDoubleClick={() => col.key !== 'link' && startEdit(post.id, col.key, post[col.key])}
                      style={{
                        padding: '0.55rem 0.9rem',
                        fontSize: 'calc(0.82rem + 2px)',
                        color: 'var(--text-primary)',
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        maxWidth: col.width,
                        overflow: 'hidden',
                        cursor: col.key !== 'link' ? 'text' : 'default',
                        background: savedCell?.postId === post.id && savedCell?.col === col.key
                          ? 'rgba(16,185,129,0.15)'
                          : 'transparent',
                        transition: 'background 0.5s',
                        position: 'relative',
                      }}
                    >
                      {renderCell(post, col.key)}
                    </td>
                  ))}
                  <td style={{ padding: '0.55rem 0.6rem', borderBottom: '1px solid rgba(255,255,255,0.04)', textAlign: 'center' }}>
                    <button
                      onClick={() => handleDelete(post.id)}
                      disabled={deletingId === post.id}
                      style={{
                        background: 'transparent', border: 'none',
                        color: deletingId === post.id ? 'rgba(255,255,255,0.2)' : 'rgba(248,113,113,0.6)',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        padding: '4px', borderRadius: '4px', transition: 'color 0.2s',
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = '#f87171'}
                      onMouseLeave={e => e.currentTarget.style.color = 'rgba(248,113,113,0.6)'}
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: '0.75rem', padding: '0.9rem', borderTop: '1px solid rgba(255,255,255,0.06)',
          }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={styles.pageBtn}
            >
              <ChevronLeft size={15} />
            </button>
            <span style={{ fontSize: 'calc(0.82rem + 2px)', color: 'var(--text-secondary)' }}>
              Page {page} of {pages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(pages, p + 1))}
              disabled={page === pages}
              style={styles.pageBtn}
            >
              <ChevronRight size={15} />
            </button>
          </div>
        )}
      </div>

      <p style={{ marginTop: '0.75rem', fontSize: 'calc(0.75rem + 2px)', color: 'rgba(160,170,178,0.5)' }}>
        💡 Double-click any cell to edit it inline. Press Enter to save, Escape to cancel.
      </p>
    </div>
  );
};

const styles = {
  editInput: {
    width: '100%', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.5)',
    borderRadius: '4px', color: 'white', padding: '2px 6px', fontFamily: 'inherit',
    fontSize: 'calc(0.82rem + 2px)', outline: 'none',
  },
  editSelect: {
    width: '100%', background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.5)',
    borderRadius: '4px', color: 'white', padding: '2px 4px', fontFamily: 'inherit',
    fontSize: 'calc(0.82rem + 2px)', outline: 'none',
  },
  pageBtn: {
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: '6px', color: 'var(--text-primary)', cursor: 'pointer',
    display: 'flex', alignItems: 'center', padding: '4px 8px',
    transition: 'background 0.2s',
  },
};

export default DataHub;
