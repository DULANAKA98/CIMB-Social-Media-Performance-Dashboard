import React, { useEffect, useState } from 'react'
import axios from 'axios'
import Dashboard from './components/PerformanceDashboard'
import Login from './components/Login'
import { API_URL } from './components/performance/usePerformanceData'

// 'checking' until the server confirms whether the session cookie is still valid.
function App() {
  const [auth, setAuth] = useState('checking');

  useEffect(() => {
    localStorage.removeItem('authed'); // flag from the old browser-only login
    axios.get(`${API_URL}/auth/me`)
      .then(() => setAuth('signed-in'))
      .catch(() => setAuth('signed-out'));
    // Any API call refused for a missing or expired session returns to the login page.
    const interceptor = axios.interceptors.response.use(undefined, error => {
      if (error?.response?.status === 401 && !String(error.config?.url || '').includes('/auth/login')) setAuth('signed-out');
      return Promise.reject(error);
    });
    return () => axios.interceptors.response.eject(interceptor);
  }, []);

  const handleLogout = async () => {
    try { await axios.post(`${API_URL}/auth/logout`); } catch { /* cookie expires on its own */ }
    setAuth('signed-out');
  };

  if (auth === 'checking') return <div className="App" aria-busy="true" />;
  if (auth === 'signed-out') return <Login onLogin={() => setAuth('signed-in')} />;

  return (
    <div className="App">
      <Dashboard onLogout={handleLogout} />
    </div>
  );
}

export default App
