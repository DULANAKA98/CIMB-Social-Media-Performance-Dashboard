import { useEffect, useState } from 'react';
import axios from 'axios';

export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
const ENDPOINTS = { summary: 'dashboard-summary', stats: 'platform-stats', engagement: 'engagement-summary', content: 'all-content', categories: 'content-types', formats: 'format-performance' };
export const queryFor = range => ({ ...(range?.start ? { start_date: range.start } : {}), ...(range?.end ? { end_date: range.end } : {}) });

export default function usePerformanceData(range, refreshKey, enabled = true) {
  const [state, setState] = useState({ loading: enabled, data: {}, errors: [], empty: false, updatedAt: null });
  useEffect(() => {
    if (!enabled) {
      setState({ loading: false, data: {}, errors: [], empty: false, updatedAt: null });
      return;
    }
    const controller = new AbortController();
    // Clear stale values when the date filter changes; do not show old totals
    // under a new period label, even while a request is in flight.
    setState({ loading: true, data: {}, errors: [], empty: false, updatedAt: null });
    const entries = Object.entries(ENDPOINTS);
    Promise.allSettled(entries.map(([, endpoint]) => axios.get(`${API_URL}/${endpoint}`, { params: queryFor(range), signal: controller.signal, timeout: 60000 })))
      .then(results => {
        if (controller.signal.aborted) return;
        const data = {};
        const errors = [];
        let noData = 0;
        results.forEach((result, index) => {
          const key = entries[index][0];
          if (result.status === 'fulfilled' && !result.value.data?.error) data[key] = result.value.data;
          else if (result.status === 'rejected' && result.reason.response?.status === 400 && /no data/i.test(result.reason.response?.data?.detail || '')) noData++;
          else errors.push(key);
        });
        setState({ loading: false, data, errors, empty: noData === entries.length, updatedAt: new Date() });
      });
    return () => controller.abort();
  }, [range, refreshKey, enabled]);
  return state;
}
