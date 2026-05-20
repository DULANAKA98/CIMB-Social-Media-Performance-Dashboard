import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { RefreshCw, Sparkles, BarChart2, Layers, TrendingUp, FileText, Download, PieChart, Target, BookOpen } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

const NAV_ITEMS = [
  { id: 'executive', label: 'Executive Summary', icon: Sparkles },
  { id: 'highlights', label: 'Platform Highlights', icon: BarChart2 },
  { id: 'engagement', label: 'Total Engagement', icon: TrendingUp },
  { id: 'content', label: 'All Organic Content Performance', icon: FileText },
  { id: 'formats', label: 'Organic Content Types & Format Performance', icon: Layers },
  { id: 'download', label: 'Download All Contents', icon: Download },
  { id: 'pillar', label: 'Content Mix & Pillar Alignment', icon: PieChart },
  { id: 'strategy', label: 'Platform Strategy Recommendations', icon: Target },
  { id: 'learnings', label: 'Key Learnings & Recommendations', icon: BookOpen },
];

const Dashboard = ({ onLogout }) => {
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [activeTab, setActiveTab] = useState('executive');
  
  const [summary, setSummary] = useState(null);
  const [platformStats, setPlatformStats] = useState(null);
  const [organicContent, setOrganicContent] = useState(null);
  const [allContent, setAllContent] = useState(null);
  const [engagementSummary, setEngagementSummary] = useState(null);
  const [contentTypes, setContentTypes] = useState(null);
  const [formatPerformance, setFormatPerformance] = useState(null);
  const [executiveSummary, setExecutiveSummary] = useState(null);
  const [execLoading, setExecLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [dataSourceUrl, setDataSourceUrl] = useState('');
  const [dataSourceLoading, setDataSourceLoading] = useState(false);
  const [dataSourceError, setDataSourceError] = useState('');
  
  const [pillarSheetUrl, setPillarSheetUrl] = useState('');
  const [pillarData, setPillarData] = useState(null);
  const [pillarLoading, setPillarLoading] = useState(false);
  const [pillarError, setPillarError] = useState('');
  const [crossPlatformLoading, setCrossPlatformLoading] = useState(false);
  const [strategyData, setStrategyData] = useState(null);
  const [strategyLoading, setStrategyLoading] = useState(false);
  // Track expanded state per platform section: { Facebook_top: true, Facebook_bottom: false, ... }
  const [expanded, setExpanded] = useState({});
  const [dataLoaded, setDataLoaded] = useState(false); // Always start false to force user to connect data source
  
  const handleLoadDataSource = async (e) => {
    e.preventDefault();
    if (!dataSourceUrl.trim()) return;
    setDataSourceLoading(true);
    setDataSourceError('');
    try {
      const res = await axios.get(`${API_URL}/refresh?sheet_url=${encodeURIComponent(dataSourceUrl)}`);
      if (res.data.error) {
        setDataSourceError(res.data.error);
      } else {
        setDataLoaded(true);
        fetchData();
      }
    } catch (err) {
      setDataSourceError(err.response?.data?.error || 'Failed to load data. Please check the URL.');
    } finally {
      setDataSourceLoading(false);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      let query = '';
      if (startDate && endDate) {
        query = `?start_date=${startDate}&end_date=${endDate}`;
      }

      const [sumRes, statsRes, orgRes, allRes, engRes, ctRes, formatRes] = await Promise.all([
        axios.get(`${API_URL}/dashboard-summary${query}`),
        axios.get(`${API_URL}/platform-stats${query}`),
        axios.get(`${API_URL}/organic-content${query}`),
        axios.get(`${API_URL}/all-content${query}`),
        axios.get(`${API_URL}/engagement-summary${query}`),
        axios.get(`${API_URL}/content-types${query}`),
        axios.get(`${API_URL}/format-performance${query}`)
      ]);
      
      setSummary(sumRes.data);
      setPlatformStats(statsRes.data);
      setOrganicContent(orgRes.data);
      setAllContent(allRes.data);
      setEngagementSummary(engRes.data);
      setContentTypes(ctRes.data);
      setFormatPerformance(formatRes.data);
      setExpanded({});
      setDataLoaded(true);
    } catch (error) {
      console.error("Error fetching data:", error);
      if (error.response && error.response.status === 400) {
        setDataLoaded(false);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (dataLoaded) {
      fetchData();
    }
    // eslint-disable-next-line
  }, [startDate, endDate]);

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await axios.get(`${API_URL}/refresh?sheet_url=${encodeURIComponent(dataSourceUrl)}`);
      await fetchData();
    } catch (error) {
      console.error("Error refreshing data:", error);
      setLoading(false);
    }
  };

  const handleDownloadExcel = async () => {
    let currentUrl = dataSourceUrl;
    if (!currentUrl) {
      currentUrl = prompt("Please enter the Google Sheet URL to download:");
      if (!currentUrl) return;
      setDataSourceUrl(currentUrl);
    }

    setDownloadLoading(true);
    try {
      let query = `?sheet_url=${encodeURIComponent(currentUrl)}`;
      if (startDate && endDate) query += `&start_date=${startDate}&end_date=${endDate}`;
      else if (startDate) query += `&start_date=${startDate}`;
      else if (endDate) query += `&end_date=${endDate}`;

      const res = await axios.get(`${API_URL}/export-all-contents${query}`, {
        responseType: 'blob',
      });

      if (res.data.type === 'application/json') {
        const text = await res.data.text();
        try {
          const json = JSON.parse(text);
          if (json.error) {
            alert(`Download failed: ${json.error}`);
            return;
          }
        } catch (e) {
          // Fall through
        }
      }

      const period = (startDate && endDate)
        ? `${startDate}_${endDate}`
        : (startDate || endDate || 'all');
      const filename = `CIMB_All_Contents_${period}.xlsx`;

      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Download failed. Please try again.');
    } finally {
      setDownloadLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '0';
    return Math.round(num).toLocaleString();
  };

  const handleFetchPillar = async () => {
    let currentUrl = pillarSheetUrl;
    if (!currentUrl) {
      currentUrl = prompt("Please enter the Google Sheet URL for Pillar data:");
      if (!currentUrl) return;
      setPillarSheetUrl(currentUrl);
    }
    setPillarLoading(true);
    setPillarError('');
    setPillarData(null);
    try {
      let query = `?sheet_url=${encodeURIComponent(currentUrl)}`;
      if (startDate) query += `&start_date=${startDate}`;
      if (endDate) query += `&end_date=${endDate}`;
      const res = await axios.get(`${API_URL}/pillar-er${query}`);
      if (res.data.error) {
        setPillarError(res.data.error);
      } else {
        setPillarData(res.data);
      }
    } catch (err) {
      setPillarError('Failed to fetch data. Please check the URL and try again.');
    } finally {
      setPillarLoading(false);
    }
  };

  const handleDownloadCrossPlatform = async () => {
    let currentUrl = pillarSheetUrl;
    if (!currentUrl) {
      currentUrl = prompt("Please enter the Google Sheet URL to download:");
      if (!currentUrl) return;
      setPillarSheetUrl(currentUrl);
    }
    setCrossPlatformLoading(true);
    try {
      let query = `?sheet_url=${encodeURIComponent(currentUrl)}`;
      if (startDate) query += `&start_date=${startDate}`;
      if (endDate) query += `&end_date=${endDate}`;
      const res = await axios.get(`${API_URL}/export-cross-platform${query}`, { responseType: 'blob' });
      
      if (res.data.type === 'application/json') {
        const text = await res.data.text();
        try {
          const json = JSON.parse(text);
          if (json.error) {
            alert(`Download failed: ${json.error}`);
            return;
          }
        } catch (e) {
          // Fall through
        }
      }

      const period = startDate && endDate ? `${startDate}_${endDate}` : 'all';
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url; a.download = `Cross_Platform_Contents_Performance_${period}.xlsx`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert('Download failed. Please try again.');
    } finally {
      setCrossPlatformLoading(false);
    }
  };

  const renderPillarTable = () => {
    if (!pillarData) return null;
    const { platforms, pivot } = pillarData;
    const PLATFORM_COLORS = {
      Facebook: '#1877f2', Instagram: '#e1306c',
      LinkedIn: '#0a66c2', TikTok: '#00f2fe', YouTube: '#ff0000',
    };
    return (
      <div className="glass-panel" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center' }}>
          <thead>
            <tr style={{ background: '#7f1d1d' }}>
              <th style={{ padding: '1rem 1.4rem', border: '1px solid rgba(255,255,255,0.08)', textAlign: 'left', color: '#fff', fontWeight: 700, fontSize: '0.9rem', textTransform: 'none', background: '#991b1b' }}>
                Pillar
              </th>
              {platforms.map(p => (
                <th key={p} style={{ padding: '1rem', border: '1px solid rgba(255,255,255,0.08)', color: '#fff', fontWeight: 700, fontSize: '0.9rem', textTransform: 'none', background: '#b91c1c' }}>
                  <span style={{ color: PLATFORM_COLORS[p] || '#fff' }}>{p}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pivot.map((row, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                <td style={{ padding: '0.85rem 1.4rem', border: '1px solid rgba(255,255,255,0.06)', fontWeight: 700, fontSize: '0.88rem', color: '#fff', textAlign: 'left', background: 'rgba(153,27,27,0.2)' }}>
                  {row.pillar}
                </td>
                {platforms.map(p => (
                  <td key={p} style={{ padding: '0.85rem 1rem', border: '1px solid rgba(255,255,255,0.06)', fontSize: '0.9rem', color: row[p] != null ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
                    {row[p] != null ? `${row[p].toFixed(2)}%` : '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const generateExecSummary = async () => {
    setExecLoading(true);
    setExecutiveSummary(null);
    try {
      let query = '';
      if (startDate && endDate) query = `?start_date=${startDate}&end_date=${endDate}`;
      const res = await axios.get(`${API_URL}/executive-summary${query}`);
      if (res.data.error) {
        setExecutiveSummary({ error: res.data.error });
      } else {
        setExecutiveSummary(res.data);
      }
    } catch (err) {
      setExecutiveSummary({ error: 'Failed to generate summary. Please try again.' });
    } finally {
      setExecLoading(false);
    }
  };

  if (!dataLoaded) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'linear-gradient(135deg, #0a0c14 0%, #0d1117 50%, #0a0e18 100%)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: "'Inter', 'Outfit', sans-serif", position: 'relative', overflow: 'hidden',
      }}>
        {/* Background blobs */}
        <div style={{
          position: 'absolute', width: 500, height: 500,
          background: 'radial-gradient(circle, rgba(185,28,28,0.12) 0%, transparent 70%)',
          top: '10%', left: '5%', borderRadius: '50%', pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', width: 400, height: 400,
          background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)',
          bottom: '10%', right: '10%', borderRadius: '50%', pointerEvents: 'none',
        }} />

        <div style={{
          width: '100%', maxWidth: 500, background: 'rgba(255,255,255,0.04)',
          backdropFilter: 'blur(20px)', border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 20, padding: '2.8rem 2.4rem', boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
          position: 'relative', zIndex: 10
        }}>
          <div style={{ textAlign: 'center', marginBottom: '2.2rem' }}>
            <div style={{
              width: 60, height: 60, borderRadius: 16, background: 'linear-gradient(135deg, #b91c1c, #7f1d1d)',
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '1rem',
              boxShadow: '0 8px 24px rgba(185,28,28,0.4)',
            }}>
              <FileText size={26} color="#fff" />
            </div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.3px', margin: 0, marginBottom: '0.3rem' }}>
              Connect Data Source
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem', margin: 0, lineHeight: 1.5 }}>
              Please provide the Google Sheet URL containing the raw analytics data to load the dashboard.
            </p>
          </div>

          <form onSubmit={handleLoadDataSource}>
            <div style={{ marginBottom: '1.6rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '0.4rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                Google Sheet URL
              </label>
              <input
                type="text"
                value={dataSourceUrl}
                onChange={e => { setDataSourceUrl(e.target.value); setDataSourceError(''); }}
                placeholder="https://docs.google.com/spreadsheets/d/..."
                style={{
                  width: '100%', boxSizing: 'border-box', background: 'rgba(255,255,255,0.06)',
                  border: `1px solid ${dataSourceError ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: 10, padding: '0.85rem 1rem', color: '#fff', fontSize: '0.92rem',
                  fontFamily: 'inherit', outline: 'none', transition: 'border-color 0.2s',
                }}
                onFocus={e => e.target.style.borderColor = 'rgba(185,28,28,0.6)'}
                onBlur={e => e.target.style.borderColor = dataSourceError ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'}
              />
            </div>

            {dataSourceError && (
              <p style={{ color: '#f87171', fontSize: '0.83rem', margin: '-0.8rem 0 1rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                ⚠ {dataSourceError}
              </p>
            )}

            <button
              type="submit"
              disabled={dataSourceLoading || !dataSourceUrl.trim()}
              style={{
                width: '100%', background: dataSourceLoading || !dataSourceUrl.trim() ? 'rgba(185,28,28,0.4)' : 'linear-gradient(135deg, #b91c1c, #991b1b)',
                color: '#fff', border: 'none', borderRadius: 10, padding: '0.85rem', fontWeight: 700, fontSize: '0.95rem',
                cursor: dataSourceLoading || !dataSourceUrl.trim() ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
                fontFamily: 'inherit', boxShadow: dataSourceLoading || !dataSourceUrl.trim() ? 'none' : '0 4px 20px rgba(185,28,28,0.4)',
                transition: 'all 0.2s',
              }}
            >
              {dataSourceLoading ? (
                <><div style={{ width: 18, height: 18, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} /> Loading Data...</>
              ) : (
                <><Layers size={18} /> Load Dashboard</>
              )}
            </button>
          </form>
          {onLogout && (
            <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
               <button onClick={onLogout} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.4)', fontSize: '0.8rem', cursor: 'pointer', textDecoration: 'underline' }}>
                 Sign Out
               </button>
            </div>
          )}
        </div>
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  if (loading && !summary) {
    return (
      <div className="loading-screen">
        <div className="spinner"></div>
        <h2>Fetching Live Data...</h2>
      </div>
    );
  }

  const renderPlatformCard = (platformName, stats) => {
    if (!stats) return null;
    
    return (
      <div className="glass-panel" key={platformName} style={{ marginBottom: '1.5rem' }}>
        <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>
          {platformName} Analytics
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
          <div className="metric-box">
            <span>Posts</span>
            <strong>{stats.posts_count}</strong>
          </div>
          <div className="metric-box">
            <span>Avg. Reach</span>
            <strong>{formatNumber(stats.avg_reach)}</strong>
          </div>
          <div className="metric-box">
            <span>Avg. ER%</span>
            <strong style={{ color: 'var(--accent-pink)' }}>{stats.avg_engagement_rate?.toFixed(2)}%</strong>
          </div>
        </div>
      </div>
    );
  };

  const getTableHeaders = (platformName) => {
    const firstHeader = platformName === 'Instagram' ? 'Post Content' : 'Title';
    const commonHeaders = [<th>{firstHeader}</th>, <th>Date</th>];
    const endHeaders = [<th>Total Engagement</th>, <th>Likes</th>, <th>Comments</th>];
    
    let specificHeaders = [];
    if (platformName === 'Facebook' || platformName === 'Instagram') {
      specificHeaders = [<th>Reach</th>, <th>Views</th>];
    } else if (platformName === 'TikTok' || platformName === 'YouTube') {
      specificHeaders = [<th>Views</th>];
    } else if (platformName === 'LinkedIn') {
      specificHeaders = [<th>Impressions</th>];
    }

    let extraEngHeaders = [];
    if (platformName === 'LinkedIn') {
      extraEngHeaders = [<th>Reposts</th>];
    } else if (platformName === 'TikTok') {
      extraEngHeaders = [<th>Shares</th>, <th>Favorites</th>];
    } else if (platformName === 'Instagram') {
      extraEngHeaders = [<th>Shares</th>, <th>Saves</th>];
    } else {
      extraEngHeaders = [<th>Shares</th>];
    }

    return (
      <tr>
        {commonHeaders}
        {specificHeaders}
        {endHeaders}
        {extraEngHeaders}
        <th>ER %</th>
        <th>Link</th>
      </tr>
    );
  };

  const renderTableRows = (platformName, data) => {
    if (data.length === 0) return <tr><td colSpan="12" style={{textAlign:'center'}}>No organic data found</td></tr>;
    
    return data.map((post, idx) => (
      <tr key={idx}>
        <td style={{ maxWidth: '250px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {post.title || 'No description'}
        </td>
        <td>{post.date ? new Date(post.date).toLocaleDateString() : 'N/A'}</td>
        
        {(platformName === 'Facebook' || platformName === 'Instagram') && (
          <>
            <td>{formatNumber(post.reach)}</td>
            <td>{formatNumber(post.views)}</td>
          </>
        )}
        
        {(platformName === 'TikTok' || platformName === 'YouTube') && (
          <td>{formatNumber(post.views)}</td>
        )}
        
        {platformName === 'LinkedIn' && (
          <td>{formatNumber(post.reach)}</td>
        )}

        <td style={{ color: 'var(--accent-purple)', fontWeight: 'bold' }}>{formatNumber(post.engagement)}</td>
        <td>{formatNumber(post.likes)}</td>
        <td>{formatNumber(post.comments)}</td>
        
        {platformName === 'LinkedIn' ? (
          <td>{formatNumber(post.reposts)}</td>
        ) : platformName === 'TikTok' ? (
          <>
            <td>{formatNumber(post.shares)}</td>
            <td>{formatNumber(post.favorites)}</td>
          </>
        ) : platformName === 'Instagram' ? (
          <>
            <td>{formatNumber(post.shares)}</td>
            <td>{formatNumber(post.favorites)}</td>
          </>
        ) : (
          <td>{formatNumber(post.shares)}</td>
        )}
        
        <td>{post.engagement_rate?.toFixed(2)}%</td>
        <td>
          {post.link && post.link !== 'nan' ? (
            <a href={post.link} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-blue)', textDecoration: 'none' }}>View</a>
          ) : '-'}
        </td>
      </tr>
    ));
  };

  const toggleExpand = (key) => {
    setExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const renderOrganicSection = (platformName, data) => {
    if (!data || (data.top.length === 0 && data.bottom.length === 0)) return null;
    const allData = allContent?.[platformName] ?? [];
    const allExpanded = expanded[`${platformName}_all`];

    const showAllBtn = (key, label) => (
      <button
        onClick={() => toggleExpand(key)}
        style={{
          marginTop: '0.75rem',
          background: 'rgba(255,255,255,0.07)',
          border: '1px solid rgba(255,255,255,0.15)',
          color: 'var(--accent-blue)',
          padding: '0.4rem 1.2rem',
          borderRadius: '6px',
          cursor: 'pointer',
          fontSize: '0.85rem',
          fontWeight: '600',
          transition: 'background 0.2s',
          display: 'block',
          width: '100%',
        }}
        onMouseEnter={e => e.target.style.background = 'rgba(255,255,255,0.13)'}
        onMouseLeave={e => e.target.style.background = 'rgba(255,255,255,0.07)'}
      >
        {label}
      </button>
    );

    return (
      <div key={platformName} style={{ marginBottom: '3rem' }}>
        <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', color: 'var(--accent-blue)' }}>{platformName} Organic Performance</h2>

        {allExpanded ? (
          // Full sorted list view
          <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ marginBottom: '1rem' }}>All Organic Posts — Sorted by Total Engagement ({allData.length} posts)</h3>
            <div className="table-container">
              <table>
                <thead>{getTableHeaders(platformName)}</thead>
                <tbody>{renderTableRows(platformName, allData)}</tbody>
              </table>
            </div>
            {showAllBtn(`${platformName}_all`, '▲ Show Less')}
          </div>
        ) : (
          // Default top 5 / bottom 5 view
          <>
            <div className="glass-panel" style={{ marginBottom: '1.5rem' }}>
              <h3 style={{ marginBottom: '1rem' }}>Top 5 Organic Posts (By Total Engagement)</h3>
              <div className="table-container">
                <table>
                  <thead>{getTableHeaders(platformName)}</thead>
                  <tbody>{renderTableRows(platformName, data.top)}</tbody>
                </table>
              </div>
            </div>

            <div className="glass-panel" style={{ marginBottom: '1rem' }}>
              <h3 style={{ marginBottom: '1rem' }}>Bottom 5 Organic Posts (By Total Engagement)</h3>
              <div className="table-container">
                <table>
                  <thead>{getTableHeaders(platformName)}</thead>
                  <tbody>{renderTableRows(platformName, data.bottom)}</tbody>
                </table>
              </div>
            </div>

            {allData.length > 0 && showAllBtn(`${platformName}_all`, `▼ Show All ${allData.length} Posts`)}
          </>
        )}
      </div>
    );
  };

  const PLATFORM_COLORS = {
    Facebook: '#1877f2',
    Instagram: '#e1306c',
    TikTok: '#00f2fe',
    YouTube: '#ff0000',
    LinkedIn: '#0a66c2',
  };

  const renderEngagementSection = () => {
    if (!engagementSummary) return null;
    const { platforms, overall } = engagementSummary;

    const handleCopyOverall = () => {
      if (!contentTypes?.Overall) return;
      const text = contentTypes.Overall.map(({ type }) => type).join(', ');
      navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copy-btn-Overall');
        if (btn) {
          btn.textContent = '✓ Copied!';
          btn.style.color = '#10b981';
          setTimeout(() => { btn.textContent = '⎘ Copy'; btn.style.color = 'var(--text-secondary)'; }, 1800);
        }
      });
    };

    return (
      <div style={{ marginBottom: '3rem' }}>
        <div
          className="glass-panel"
          style={{
            marginBottom: '1.5rem',
            background: 'linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(236,72,153,0.12) 100%)',
            borderColor: 'rgba(139,92,246,0.3)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.2rem' }}>
            <span style={{
              background: 'linear-gradient(135deg, var(--accent-purple), var(--accent-pink))',
              borderRadius: '8px',
              padding: '0.4rem 0.7rem',
              fontSize: '1rem',
            }}>⚡</span>
            <h3 style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>Overall Across All Platforms</h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            <div className="metric-box" style={{ borderColor: 'rgba(139,92,246,0.25)' }}>
              <span>Total Posts</span>
              <strong>{formatNumber(overall.posts_count)}</strong>
            </div>
            <div className="metric-box" style={{ borderColor: 'rgba(139,92,246,0.25)' }}>
              <span>Total Engagements</span>
              <strong style={{ color: 'var(--accent-purple)' }}>{formatNumber(overall.total_engagement)}</strong>
            </div>
            <div className="metric-box" style={{ borderColor: 'rgba(236,72,153,0.25)' }}>
              <span>Avg. Eng. / Post</span>
              <strong style={{ color: 'var(--accent-pink)' }}>{formatNumber(overall.avg_engagement_per_post)}</strong>
            </div>
          </div>
          {contentTypes?.Overall && (() => {
            const overallText = contentTypes.Overall.map(({ type }) => type).join(', ');
            return (
              <div style={{ marginTop: '1.2rem', borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', letterSpacing: '1px', textTransform: 'uppercase', fontWeight: '600' }}>
                    Content Mix
                  </p>
                  <button
                    id="copy-btn-Overall"
                    onClick={handleCopyOverall}
                    style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.72rem', cursor: 'pointer', fontWeight: '600', fontFamily: 'inherit', padding: '0.1rem 0.4rem', borderRadius: '4px', transition: 'color 0.2s' }}
                    onMouseEnter={e => e.target.style.color = '#fff'}
                    onMouseLeave={e => { if (e.target.textContent !== '✓ Copied!') e.target.style.color = 'var(--text-secondary)'; }}
                  >
                    ⎘ Copy
                  </button>
                </div>
                <p
                  onClick={e => { const r = document.createRange(); r.selectNodeContents(e.currentTarget); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); }}
                  style={{ fontSize: '0.88rem', lineHeight: '1.65', color: 'var(--text-primary)', cursor: 'text', userSelect: 'text', WebkitUserSelect: 'text', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.05)', margin: 0, wordBreak: 'break-word' }}
                >
                  {overallText}
                </p>
                <p style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '0.3rem', opacity: 0.6 }}>
                  Click text to select · {contentTypes.Overall.length} type{contentTypes.Overall.length !== 1 ? 's' : ''}
                </p>
              </div>
            );
          })()}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.2rem' }}>
          {platforms.map(({ platform, total_engagement, posts_count, avg_engagement_per_post }) => {
            const color = PLATFORM_COLORS[platform] || 'var(--accent-blue)';
            const types = contentTypes?.[platform] || [];
            const typeText = types.map(({ type }) => type).join(', ');

            const handleCopy = () => {
              navigator.clipboard.writeText(typeText).then(() => {
                const btn = document.getElementById(`copy-btn-${platform}`);
                if (btn) {
                  btn.textContent = '✓ Copied!';
                  btn.style.color = '#10b981';
                  setTimeout(() => { btn.textContent = '⎘ Copy'; btn.style.color = 'var(--text-secondary)'; }, 1800);
                }
              });
            };

            return (
              <div
                key={platform}
                className="glass-panel"
                style={{ borderColor: `${color}33` }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
                  <span style={{
                    display: 'inline-block',
                    width: '10px', height: '10px',
                    borderRadius: '50%',
                    background: color,
                    boxShadow: `0 0 8px ${color}`,
                    flexShrink: 0,
                  }} />
                  <h4 style={{ fontSize: '1rem', color: 'var(--text-primary)', fontWeight: '700' }}>{platform}</h4>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem' }}>
                  <div className="metric-box" style={{ borderColor: `${color}22` }}>
                    <span>Total Engagements</span>
                    <strong style={{ fontSize: '1.4rem', color }}>{formatNumber(total_engagement)}</strong>
                  </div>
                  <div className="metric-box" style={{ borderColor: `${color}22` }}>
                    <span>Avg. Eng. / Post</span>
                    <strong style={{ fontSize: '1.4rem' }}>{formatNumber(avg_engagement_per_post)}</strong>
                  </div>
                </div>

                {types.length > 0 && (
                  <div style={{ marginTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '0.9rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <p style={{ fontSize: '0.68rem', color: 'var(--text-secondary)', letterSpacing: '1px', textTransform: 'uppercase', fontWeight: '600' }}>
                        Content Types
                      </p>
                      <button
                        id={`copy-btn-${platform}`}
                        onClick={handleCopy}
                        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontSize: '0.72rem', cursor: 'pointer', fontWeight: '600', fontFamily: 'inherit', padding: '0.1rem 0.4rem', borderRadius: '4px', transition: 'color 0.2s' }}
                        onMouseEnter={e => e.target.style.color = '#fff'}
                        onMouseLeave={e => { if (e.target.textContent !== '✓ Copied!') e.target.style.color = 'var(--text-secondary)'; }}
                      >
                        ⎘ Copy
                      </button>
                    </div>
                    <p
                      onClick={e => { const r = document.createRange(); r.selectNodeContents(e.currentTarget); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); }}
                      style={{ fontSize: '0.88rem', lineHeight: '1.65', color: 'var(--text-primary)', cursor: 'text', userSelect: 'text', WebkitUserSelect: 'text', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '0.6rem 0.75rem', border: '1px solid rgba(255,255,255,0.05)', margin: 0, wordBreak: 'break-word' }}
                    >
                      {typeText}
                    </p>
                    <p style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '0.3rem', opacity: 0.6 }}>
                      Click text to select · {types.length} type{types.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                )}
                <div style={{ marginTop: '0.75rem', fontSize: '0.78rem', color: 'var(--text-secondary)', textAlign: 'right' }}>
                  {posts_count} post{posts_count !== 1 ? 's' : ''} in period
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderFormatPerformanceSection = () => {
    if (!formatPerformance || formatPerformance.length === 0) return null;

    let currentPlatform = null;

    return (
      <div style={{ marginBottom: '3rem' }}>
        <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
          <table className="format-table" style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'center' }}>
            <thead>
              <tr style={{ background: '#b91c1c', color: 'white' }}>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>Platform</th>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>Format</th>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>No. of Posts</th>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>Avg. Reach</th>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>Avg. Engagements</th>
                <th style={{ padding: '1rem', border: '1px solid #7f1d1d', background: '#b91c1c', color: 'white', textAlign: 'center', textTransform: 'none', fontSize: '0.95rem' }}>Avg. Engagement Rate</th>
              </tr>
            </thead>
            <tbody>
              {formatPerformance.map((row, idx) => {
                const isGrandTotal = row.is_grand_total;
                const isPlatformTotal = row.is_total && !isGrandTotal;
                
                // Track platform to only show name on first row of that platform
                const showPlatformName = !isGrandTotal && !isPlatformTotal && row.platform !== currentPlatform;
                if (!isGrandTotal && !isPlatformTotal) {
                  currentPlatform = row.platform;
                }

                // Styling logic based on row type
                let bgStyle = 'transparent';
                let fontWeight = 'normal';
                let color = 'var(--text-primary)';
                
                if (isGrandTotal) {
                  bgStyle = 'rgba(255, 255, 255, 0.15)';
                  fontWeight = 'bold';
                } else if (isPlatformTotal) {
                  bgStyle = 'rgba(245, 158, 11, 0.15)'; // light orange/gold tint for platform totals
                  fontWeight = 'bold';
                  color = '#fbbf24'; // amber-400
                }

                return (
                  <tr key={idx} style={{ background: bgStyle, fontWeight }}>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem', color: isGrandTotal ? 'white' : 'var(--text-primary)' }}>
                      {isGrandTotal ? 'Grand Total' : (isPlatformTotal ? row.format : (showPlatformName ? row.platform : ''))}
                    </td>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem' }}>
                      {isGrandTotal || isPlatformTotal ? '' : row.format}
                    </td>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem', color: isPlatformTotal ? color : 'var(--text-primary)' }}>
                      {formatNumber(row.posts)}
                    </td>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem', color: isPlatformTotal ? color : 'var(--text-primary)' }}>
                      {formatNumber(row.avg_reach)}
                    </td>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem', color: isPlatformTotal ? color : 'var(--text-primary)' }}>
                      {formatNumber(row.avg_engagement)}
                    </td>
                    <td style={{ border: '1px solid rgba(255,255,255,0.1)', padding: '0.8rem', color: isPlatformTotal ? color : 'var(--text-primary)' }}>
                      {row.avg_er?.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // ── Executive Summary renderer ──────────────────────────────────────────────
  const renderExecutiveSummary = () => {
    if (!executiveSummary && !execLoading) return null;

    if (execLoading) {
      return (
        <div className="glass-panel" style={{ marginBottom: '3rem', textAlign: 'center', padding: '3rem' }}>
          <div className="spinner" style={{ margin: '0 auto 1rem', width: 40, height: 40, borderTopColor: 'var(--accent-purple)' }} />
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Gemini is analysing your data…</p>
        </div>
      );
    }

    if (executiveSummary?.error) {
      return (
        <div className="glass-panel" style={{ marginBottom: '3rem', borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)' }}>
          <p style={{ color: '#f87171' }}>⚠ {executiveSummary.error}</p>
        </div>
      );
    }

    const es = executiveSummary;
    const PLATFORM_COLORS_EXEC = {
      Facebook: '#1877f2', Instagram: '#e1306c', TikTok: '#00f2fe',
      YouTube: '#ff0000', LinkedIn: '#0a66c2',
    };

    // Build plain-text version for copy
    const plainText = [
      `EXECUTIVE SUMMARY — ${es.period || ''}`,
      ``,
      `TOP PERFORMING PLATFORM: ${es.top_platform}`,
      es.top_platform_reason,
      ``,
      `KEY HIGHLIGHTS`,
      ...(es.key_highlights || []).map(h => `• ${h}`),
      ``,
      `AUDIENCE BEHAVIOUR`,
      ...(es.audience_behaviour || []).map(h => `• ${h}`),
      ``,
      `HIGH-LEVEL RECOMMENDATIONS`,
      ...Object.entries(es.recommendations || {}).map(([p, r]) => `${p}: ${r}`),
    ].join('\n');

    const handleCopyAll = () => {
      navigator.clipboard.writeText(plainText).then(() => {
        const btn = document.getElementById('exec-copy-btn');
        if (btn) {
          const prev = btn.textContent;
          btn.textContent = '✓ Copied!';
          btn.style.color = '#10b981';
          setTimeout(() => { btn.textContent = prev; btn.style.color = ''; }, 2000);
        }
      });
    };

    return (
      <div style={{ marginBottom: '3rem' }}>
        <div
          className="glass-panel"
          style={{
            background: 'linear-gradient(135deg, rgba(20,22,30,0.95) 0%, rgba(15,17,22,0.98) 100%)',
            borderColor: 'rgba(139,92,246,0.25)',
            padding: '2rem',
          }}
        >
          {/* Summary header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.8rem' }}>
            <div>
              <h2 style={{ fontSize: '1.6rem', marginBottom: '0.25rem', display: 'inline-block' }}>Executive Summary</h2>
              {es.period && (
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>Period: {es.period}</p>
              )}
            </div>
            <div style={{ display: 'flex', gap: '0.6rem' }}>
              <button
                id="exec-copy-btn"
                onClick={handleCopyAll}
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border: '1px solid rgba(255,255,255,0.12)',
                  color: 'var(--text-secondary)',
                  padding: '0.4rem 1rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                  fontWeight: '600',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#fff'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
              >
                ⎘ Copy All
              </button>
              <button
                onClick={() => setExecutiveSummary(null)}
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  color: 'var(--text-secondary)',
                  padding: '0.4rem 0.8rem',
                  borderRadius: '8px',
                  fontSize: '0.8rem',
                  cursor: 'pointer',
                  fontFamily: 'inherit',
                }}
              >
                ✕
              </button>
            </div>
          </div>

          {/* Two-column layout */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>

            {/* LEFT COLUMN */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>

              {/* Top Platform */}
              <div style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.2)', borderRadius: '14px', overflow: 'hidden' }}>
                <div style={{ background: 'linear-gradient(90deg, rgba(139,92,246,0.7), rgba(236,72,153,0.5))', padding: '0.55rem 1rem' }}>
                  <p style={{ fontSize: '0.8rem', fontWeight: '700', letterSpacing: '0.5px', color: '#fff' }}>Top Performing Platform</p>
                </div>
                <div style={{ padding: '1rem 1.2rem', display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                  <span style={{
                    fontSize: '2rem',
                    width: '2.5rem', height: '2.5rem',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: `${PLATFORM_COLORS_EXEC[es.top_platform] || '#8b5cf6'}22`,
                    borderRadius: '10px',
                    border: `1px solid ${PLATFORM_COLORS_EXEC[es.top_platform] || '#8b5cf6'}44`,
                  }}>
                    {es.top_platform === 'Facebook' ? '📘' : es.top_platform === 'Instagram' ? '📸' : es.top_platform === 'TikTok' ? '🎵' : es.top_platform === 'YouTube' ? '▶️' : '💼'}
                  </span>
                  <div>
                    <p style={{ fontSize: '1.3rem', fontWeight: '800', color: PLATFORM_COLORS_EXEC[es.top_platform] || '#8b5cf6' }}>{es.top_platform}</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.4', marginTop: '0.1rem' }}>{es.top_platform_reason}</p>
                  </div>
                </div>
              </div>

              {/* Key Highlights */}
              <div style={{ background: 'rgba(59,130,246,0.06)', border: '1px solid rgba(59,130,246,0.18)', borderRadius: '14px', overflow: 'hidden' }}>
                <div style={{ background: 'linear-gradient(90deg, rgba(59,130,246,0.7), rgba(99,102,241,0.5))', padding: '0.55rem 1rem' }}>
                  <p style={{ fontSize: '0.8rem', fontWeight: '700', letterSpacing: '0.5px', color: '#fff' }}>Key Highlights</p>
                </div>
                <ul style={{ margin: 0, padding: '1rem 1.2rem 1rem 2.2rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {(es.key_highlights || []).map((h, i) => (
                    <li key={i} style={{ fontSize: '0.875rem', lineHeight: '1.55', color: 'var(--text-primary)' }}
                      dangerouslySetInnerHTML={{ __html: h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}
                    />
                  ))}
                </ul>
              </div>

              {/* Audience Behaviour */}
              <div style={{ background: 'rgba(16,185,129,0.06)', border: '1px solid rgba(16,185,129,0.18)', borderRadius: '14px', overflow: 'hidden' }}>
                <div style={{ background: 'linear-gradient(90deg, rgba(16,185,129,0.65), rgba(5,150,105,0.45))', padding: '0.55rem 1rem' }}>
                  <p style={{ fontSize: '0.8rem', fontWeight: '700', letterSpacing: '0.5px', color: '#fff' }}>Audience Behaviour</p>
                </div>
                <ul style={{ margin: 0, padding: '1rem 1.2rem 1rem 2.2rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {(es.audience_behaviour || []).map((h, i) => (
                    <li key={i} style={{ fontSize: '0.875rem', lineHeight: '1.55', color: 'var(--text-primary)' }}
                      dangerouslySetInnerHTML={{ __html: h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}
                    />
                  ))}
                </ul>
              </div>
            </div>

            {/* RIGHT COLUMN — Recommendations */}
            <div style={{ background: 'rgba(236,72,153,0.05)', border: '1px solid rgba(236,72,153,0.15)', borderRadius: '14px', overflow: 'hidden' }}>
              <div style={{ background: 'linear-gradient(90deg, rgba(236,72,153,0.65), rgba(239,68,68,0.45))', padding: '0.55rem 1rem' }}>
                <p style={{ fontSize: '0.8rem', fontWeight: '700', letterSpacing: '0.5px', color: '#fff' }}>High-Level Recommendations</p>
              </div>
              <div style={{ padding: '1.2rem', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                {Object.entries(es.recommendations || {}).map(([platform, rec]) => (
                  <div key={platform}>
                    <p style={{
                      fontSize: '0.82rem',
                      fontWeight: '700',
                      color: PLATFORM_COLORS_EXEC[platform] || 'var(--accent-blue)',
                      marginBottom: '0.3rem',
                      letterSpacing: '0.2px',
                    }}>
                      {platform}
                    </p>
                    <p style={{ fontSize: '0.855rem', lineHeight: '1.55', color: 'var(--text-primary)', margin: 0 }}
                      dangerouslySetInnerHTML={{ __html: `• ${rec.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}` }}
                    />
                  </div>
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    );
  };

  const activeNavLabel = NAV_ITEMS.find(n => n.id === activeTab)?.label ?? '';

  return (
    <div className="app-shell">

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-logo">
          <h1>CIMB Social Media</h1>
          <p>Analytics Dashboard</p>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <div
              key={id}
              className={`nav-item${activeTab === id ? ' active' : ''}`}
              onClick={() => setActiveTab(id)}
            >
              <span className="nav-icon"><Icon size={17} /></span>
              <span className="nav-label">{label}</span>
              <span className="nav-indicator" />
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <p>Dulanaka Siriwardana © {new Date().getFullYear()}</p>
          {onLogout && (
            <button
              onClick={onLogout}
              style={{
                marginTop: '0.6rem', width: '100%',
                background: 'rgba(185,28,28,0.15)',
                border: '1px solid rgba(185,28,28,0.35)',
                borderRadius: '8px', padding: '0.5rem 1rem',
                color: '#fca5a5', fontSize: '0.8rem', fontWeight: 600,
                cursor: 'pointer', display: 'flex', alignItems: 'center',
                justifyContent: 'center', gap: '0.4rem', fontFamily: 'inherit',
                transition: 'background 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(185,28,28,0.28)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(185,28,28,0.15)'}
            >
              ⎋ Sign Out
            </button>
          )}
        </div>
      </aside>

      {/* ── Main area ── */}
      <div className="main-content">

        {/* Sticky top bar */}
        <div className="top-bar">
          <div className="top-bar-title">
            {activeNavLabel}
            {loading && summary && <span>— updating…</span>}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div className="glass-panel" style={{ padding: '0.4rem 0.9rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input
                type="date"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
                style={{ background: 'transparent', color: 'white', border: 'none', padding: '0.15rem 0.4rem', borderRadius: '4px', outline: 'none', fontSize: '0.85rem' }}
              />
              <span style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>to</span>
              <input
                type="date"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
                style={{ background: 'transparent', color: 'white', border: 'none', padding: '0.15rem 0.4rem', borderRadius: '4px', outline: 'none', fontSize: '0.85rem' }}
              />
            </div>

            <button className="refresh-btn" onClick={handleRefresh} disabled={loading} style={{ padding: '0.6rem 1.1rem', fontSize: '0.85rem' }}>
              {loading ? <div className="spinner" style={{ width: 16, height: 16 }}></div> : <RefreshCw size={15} />}
              {loading ? 'Syncing…' : 'Sync Data'}
            </button>

            <button
              onClick={generateExecSummary}
              disabled={execLoading}
              style={{
                background: execLoading ? 'rgba(139,92,246,0.3)' : 'linear-gradient(135deg, rgba(139,92,246,0.85), rgba(236,72,153,0.75))',
                color: 'white', border: 'none', padding: '0.6rem 1.1rem', borderRadius: '8px',
                fontWeight: '700', cursor: execLoading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                fontSize: '0.85rem', fontFamily: 'inherit', transition: 'opacity 0.2s',
                boxShadow: '0 4px 15px rgba(139,92,246,0.3)',
              }}
              onMouseEnter={e => { if (!execLoading) e.currentTarget.style.opacity = '0.88'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
            >
              {execLoading ? <div className="spinner" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff' }}></div> : <Sparkles size={14} />}
              {execLoading ? 'Generating…' : 'AI Summary'}
            </button>
          </div>
        </div>

        {/* Page content */}
        <div className="page-content">

          {activeTab === 'executive' && (
            <div>
              {!executiveSummary && !execLoading && (
                <div className="glass-panel" style={{ textAlign: 'center', padding: '4rem 2rem', borderStyle: 'dashed' }}>
                  <Sparkles size={40} style={{ margin: '0 auto 1rem', color: 'var(--accent-purple)', display: 'block' }} />
                  <h3 style={{ marginBottom: '0.5rem' }}>No Summary Yet</h3>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>Click "AI Summary" in the top bar to generate an executive report for the selected date range.</p>
                  <button
                    onClick={generateExecSummary}
                    style={{ background: 'linear-gradient(135deg, rgba(139,92,246,0.85), rgba(236,72,153,0.75))', color: 'white', border: 'none', padding: '0.75rem 1.8rem', borderRadius: '10px', fontWeight: '700', cursor: 'pointer', fontSize: '0.95rem', fontFamily: 'inherit' }}
                  >
                    ✦ Generate AI Summary
                  </button>
                </div>
              )}
              {renderExecutiveSummary()}
            </div>
          )}

          {activeTab === 'highlights' && (
            <div>
              {platformStats && Object.entries(platformStats).map(([platformName, stats]) =>
                renderPlatformCard(platformName, stats)
              )}
            </div>
          )}

          {activeTab === 'engagement' && (
            <div>
              {renderEngagementSection()}
            </div>
          )}

          {activeTab === 'content' && (
            <div>
              {organicContent && Object.entries(organicContent).map(([platformName, data]) =>
                renderOrganicSection(platformName, data)
              )}
            </div>
          )}

          {activeTab === 'formats' && (
            <div>
              <h2 style={{ marginBottom: '1.5rem', fontSize: '1.5rem', color: 'var(--accent-blue)' }}>Organic Content Types & Format Performance</h2>
              {renderFormatPerformanceSection()}
            </div>
          )}

          {activeTab === 'download' && (
            <div style={{ maxWidth: '600px', margin: '0 auto', paddingTop: '2rem' }}>
              <div className="glass-panel" style={{
                textAlign: 'center',
                padding: '3rem 2.5rem',
                background: 'linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(139,92,246,0.08) 100%)',
                borderColor: 'rgba(59,130,246,0.2)',
              }}>
                <div style={{
                  width: '64px', height: '64px', borderRadius: '18px', margin: '0 auto 1.5rem',
                  background: 'linear-gradient(135deg, rgba(59,130,246,0.25), rgba(139,92,246,0.2))',
                  border: '1px solid rgba(59,130,246,0.3)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <Download size={28} style={{ color: 'var(--accent-blue)' }} />
                </div>

                <h2 style={{ fontSize: '1.5rem', marginBottom: '0.6rem' }}>Download All Contents</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: '1.6', marginBottom: '0.5rem' }}>
                  Exports all contents (Organic &amp; Paid) for the selected date range across all platforms as an Excel file.
                </p>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', marginBottom: '2rem', opacity: 0.7 }}>
                  Columns: Date · Platform · Format · Pillar · Organic/Paid · Collab · Title · Caption · Reach · Views · Interaction · ER% · Likes · Comments · Shares · Saves · Reposts · URL · Year Month
                </p>

                {(startDate && endDate) ? (
                  <div style={{
                    display: 'inline-block', background: 'rgba(59,130,246,0.1)',
                    border: '1px solid rgba(59,130,246,0.2)', borderRadius: '8px',
                    padding: '0.4rem 1rem', marginBottom: '1.8rem', fontSize: '0.85rem', color: 'var(--accent-blue)'
                  }}>
                    📅 {startDate} → {endDate}
                  </div>
                ) : (
                  <div style={{
                    display: 'inline-block', background: 'rgba(245,158,11,0.08)',
                    border: '1px solid rgba(245,158,11,0.2)', borderRadius: '8px',
                    padding: '0.4rem 1rem', marginBottom: '1.8rem', fontSize: '0.85rem', color: '#fbbf24'
                  }}>
                    ⚠ No date range selected — all available data will be exported
                  </div>
                )}

                <br />
                <button
                  onClick={handleDownloadExcel}
                  disabled={downloadLoading}
                  style={{
                    background: downloadLoading
                      ? 'rgba(59,130,246,0.3)'
                      : 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
                    color: 'white', border: 'none',
                    padding: '0.85rem 2.2rem', borderRadius: '10px',
                    fontWeight: '700', cursor: downloadLoading ? 'not-allowed' : 'pointer',
                    display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
                    fontSize: '1rem', fontFamily: 'inherit',
                    boxShadow: '0 4px 20px rgba(59,130,246,0.35)',
                    transition: 'opacity 0.2s',
                  }}
                  onMouseEnter={e => { if (!downloadLoading) e.currentTarget.style.opacity = '0.88'; }}
                  onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
                >
                  {downloadLoading
                    ? <><div className="spinner" style={{ width: 18, height: 18, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff' }}></div> Preparing file…</>
                    : <><Download size={18} /> Download Excel</>}
                </button>

                <p style={{ marginTop: '1.2rem', fontSize: '0.75rem', color: 'var(--text-secondary)', opacity: 0.55 }}>
                  The file is generated fresh from Google Sheets each time
                </p>
              </div>
            </div>
          )}

          {activeTab === 'pillar' && (
            <div>
              <h2 style={{ marginBottom: '0.5rem', fontSize: '1.5rem', color: 'var(--accent-blue)' }}>Content Mix &amp; Pillar Alignment</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.8rem' }}>
                Paste your exported &quot;All Contents&quot; Google Sheet URL below. Only Organic posts are included in the ER% calculation.
              </p>

              {/* URL input */}
              <div className="glass-panel" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.5rem', padding: '1rem 1.4rem' }}>
                <PieChart size={18} style={{ color: 'var(--accent-blue)', flexShrink: 0 }} />
                <input
                  type="text"
                  placeholder="Paste Google Sheet URL here…"
                  value={pillarSheetUrl}
                  onChange={e => setPillarSheetUrl(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleFetchPillar()}
                  style={{
                    flex: 1, background: 'transparent', border: 'none', outline: 'none',
                    color: 'var(--text-primary)', fontSize: '0.88rem', fontFamily: 'inherit',
                  }}
                />
                <button
                  onClick={handleFetchPillar}
                  disabled={pillarLoading || !pillarSheetUrl.trim()}
                  style={{
                    background: pillarLoading ? 'rgba(59,130,246,0.3)' : 'linear-gradient(135deg, #3b82f6, #6366f1)',
                    color: '#fff', border: 'none', padding: '0.55rem 1.2rem',
                    borderRadius: '8px', fontWeight: 700, fontSize: '0.85rem',
                    cursor: pillarLoading ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', gap: '0.4rem',
                    fontFamily: 'inherit', whiteSpace: 'nowrap',
                  }}
                >
                  {pillarLoading
                    ? <><div className="spinner" style={{ width: 14, height: 14, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Loading…</>
                    : 'Load Data'}
                </button>
              </div>

              {/* Error */}
              {pillarError && (
                <div className="glass-panel" style={{ marginBottom: '1.5rem', borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', padding: '1rem 1.4rem' }}>
                  <p style={{ color: '#f87171', fontSize: '0.88rem' }}>⚠ {pillarError}</p>
                </div>
              )}

              {/* Table */}
              {pillarData && !pillarError && (
                <div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: '0.75rem' }}>
                    Showing avg ER% per Pillar × Platform (Organic only{startDate && endDate ? ` · ${startDate} → ${endDate}` : ''})
                  </p>
                  {renderPillarTable()}

                  {/* Download Cross-Platform Report */}
                  <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end' }}>
                    <button
                      onClick={handleDownloadCrossPlatform}
                      disabled={crossPlatformLoading}
                      style={{
                        background: crossPlatformLoading ? 'rgba(16,185,129,0.3)' : 'linear-gradient(135deg, #059669, #10b981)',
                        color: '#fff', border: 'none', padding: '0.65rem 1.4rem',
                        borderRadius: '10px', fontWeight: '700', fontSize: '0.88rem',
                        cursor: crossPlatformLoading ? 'not-allowed' : 'pointer',
                        display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
                        fontFamily: 'inherit', boxShadow: '0 4px 16px rgba(16,185,129,0.3)',
                        transition: 'opacity 0.2s',
                      }}
                      onMouseEnter={e => { if (!crossPlatformLoading) e.currentTarget.style.opacity = '0.88'; }}
                      onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
                    >
                      {crossPlatformLoading
                        ? <><div className="spinner" style={{ width: 15, height: 15, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Preparing…</>
                        : <><Download size={16} /> Download Cross-Platform Report</>}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Platform Strategy Recommendations ── */}
          {activeTab === 'strategy' && (
            <div>
              <h2 style={{ marginBottom: '0.4rem', fontSize: '1.5rem', color: 'var(--accent-blue)' }}>Platform Strategy Recommendations</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                AI-generated STOP · PAUSE · CONTINUE · ENHANCE framework based on organic ER% and format performance for the selected period.
              </p>

              {!strategyData && !strategyLoading && (
                <button onClick={async () => {
                  setStrategyLoading(true);
                  try {
                    let q = startDate && endDate ? `?start_date=${startDate}&end_date=${endDate}` : '';
                    const r = await axios.get(`${API_URL}/strategy-insights${q}`);
                    setStrategyData(r.data);
                  } catch { } finally { setStrategyLoading(false); }
                }} style={{
                  background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', border: 'none',
                  padding: '0.75rem 1.8rem', borderRadius: '10px', fontWeight: 700, fontSize: '0.92rem',
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'inherit',
                  boxShadow: '0 4px 20px rgba(124,58,237,0.35)',
                }}><Target size={18} /> Generate Strategy Insights</button>
              )}

              {strategyLoading && <p style={{ color: 'var(--text-secondary)' }}>⏳ Generating AI insights… this may take 20–40 seconds.</p>}

              {strategyData?.error && <p style={{ color: '#f87171' }}>⚠ {strategyData.error}</p>}

              {strategyData && !strategyData.error && (() => {
                const strat = strategyData.platform_strategy || {};
                const platforms = ['Facebook', 'Instagram', 'YouTube', 'TikTok', 'LinkedIn'];
                const COLS = [
                  { key: 'stop',     label: 'STOP',     hdrBg: '#fca5a5', hdrColor: '#7f1d1d' },
                  { key: 'pause',    label: 'PAUSE',    hdrBg: '#fde68a', hdrColor: '#78350f' },
                  { key: 'continue', label: 'CONTINUE', hdrBg: '#6ee7b7', hdrColor: '#064e3b' },
                  { key: 'enhance',  label: 'ENHANCE',  hdrBg: '#a5f3fc', hdrColor: '#164e63' },
                ];
                return (
                  <div>
                    <div className="glass-panel" style={{ padding: 0, overflow: 'hidden', marginBottom: '1.5rem' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr>
                            <th style={{ padding: '0.9rem 1.2rem', background: '#1e293b', border: '1px solid rgba(255,255,255,0.08)', textAlign: 'left', fontWeight: 700, color: '#fff', fontSize: '0.85rem', textTransform: 'none', width: '14%' }}></th>
                            {COLS.map(c => (
                              <th key={c.key} style={{ padding: '0.9rem 1rem', background: c.hdrBg, border: '1px solid rgba(255,255,255,0.08)', textAlign: 'center', fontWeight: 800, color: c.hdrColor, fontSize: '0.85rem', letterSpacing: '0.05em' }}>{c.label}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {platforms.map((plat, i) => {
                            const pd = strat[plat] || {};
                            return (
                              <tr key={plat} style={{ background: i % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
                                <td style={{ padding: '0.85rem 1.2rem', border: '1px solid rgba(255,255,255,0.07)', fontWeight: 700, fontSize: '0.9rem', color: '#fff', background: 'rgba(185,28,28,0.15)' }}>{plat}</td>
                                {COLS.map(c => (
                                  <td key={c.key} style={{ padding: '0.85rem 1rem', border: '1px solid rgba(255,255,255,0.07)', fontSize: '0.85rem', color: 'var(--text-primary)', verticalAlign: 'top' }}>
                                    {pd[c.key] || '—'}
                                  </td>
                                ))}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>

                    {/* Key Takeaways */}
                    <div className="glass-panel" style={{ background: '#0f172a', borderColor: 'rgba(255,255,255,0.1)' }}>
                      <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem', color: '#fff' }}>Key Takeaways</h3>
                      <ul style={{ paddingLeft: '1.2rem', margin: 0 }}>
                        {(strategyData.key_takeaways || []).map((t, i) => (
                          <li key={i} style={{ marginBottom: '0.55rem', fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{t}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* ── Key Learnings & Recommendations ── */}
          {activeTab === 'learnings' && (
            <div>
              <h2 style={{ marginBottom: '0.4rem', fontSize: '1.5rem', color: 'var(--accent-blue)' }}>Key Learnings &amp; Recommendations</h2>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                AI-derived strategic learnings with concrete action items based on platform engagement data.
              </p>

              {!strategyData && !strategyLoading && (
                <button onClick={async () => {
                  setStrategyLoading(true);
                  try {
                    let q = startDate && endDate ? `?start_date=${startDate}&end_date=${endDate}` : '';
                    const r = await axios.get(`${API_URL}/strategy-insights${q}`);
                    setStrategyData(r.data);
                  } catch { } finally { setStrategyLoading(false); }
                }} style={{
                  background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', color: '#fff', border: 'none',
                  padding: '0.75rem 1.8rem', borderRadius: '10px', fontWeight: 700, fontSize: '0.92rem',
                  cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontFamily: 'inherit',
                  boxShadow: '0 4px 20px rgba(124,58,237,0.35)',
                }}><BookOpen size={18} /> Generate Key Learnings</button>
              )}

              {strategyLoading && <p style={{ color: 'var(--text-secondary)' }}>⏳ Generating AI insights… this may take 20–40 seconds.</p>}
              {strategyData?.error && <p style={{ color: '#f87171' }}>⚠ {strategyData.error}</p>}

              {strategyData && !strategyData.error && (
                <div className="glass-panel" style={{ padding: '1.8rem 2rem' }}>
                  <div style={{ background: '#b91c1c', borderRadius: '8px', padding: '0.75rem 1.5rem', marginBottom: '1.8rem', textAlign: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '1rem', color: '#fff', letterSpacing: '0.02em' }}>Key Learnings</span>
                  </div>
                  {(strategyData.key_learnings || []).map((item, i) => (
                    <div key={i} style={{ marginBottom: '1.8rem', paddingBottom: '1.8rem', borderBottom: i < (strategyData.key_learnings.length - 1) ? '1px solid rgba(255,255,255,0.07)' : 'none' }}>
                      <p style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                        {item.number}. {item.title}
                      </p>
                      <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: '0.75rem' }}>
                        {item.description}
                      </p>
                      <p style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.6 }}>
                        Action: {item.action}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
