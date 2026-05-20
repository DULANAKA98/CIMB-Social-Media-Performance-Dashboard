import React, { useState } from 'react';
import { Lock, User, Eye, EyeOff, LogIn } from 'lucide-react';

const VALID_USERNAME = 'dulanaka';
const VALID_PASSWORD = '1234';

const Login = ({ onLogin }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate brief auth delay for UX
    await new Promise(r => setTimeout(r, 600));

    if (username.trim() === VALID_USERNAME && password === VALID_PASSWORD) {
      onLogin();
    } else {
      setError('Invalid username or password.');
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
    setLoading(false);
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0c14 0%, #0d1117 50%, #0a0e18 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'Inter', 'Outfit', sans-serif",
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Background decorative blobs */}
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

      {/* Card */}
      <div style={{
        width: '100%', maxWidth: 420,
        background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(20px)',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 20,
        padding: '2.8rem 2.4rem',
        boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
        animation: shake ? 'shake 0.4s ease' : undefined,
        position: 'relative',
      }}>
        {/* Logo / Brand */}
        <div style={{ textAlign: 'center', marginBottom: '2.2rem' }}>
          <div style={{
            width: 60, height: 60, borderRadius: 16,
            background: 'linear-gradient(135deg, #b91c1c, #7f1d1d)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: '1rem',
            boxShadow: '0 8px 24px rgba(185,28,28,0.4)',
          }}>
            <Lock size={26} color="#fff" />
          </div>
          <h1 style={{
            fontSize: '1.5rem', fontWeight: 800, color: '#fff',
            letterSpacing: '-0.3px', margin: 0, marginBottom: '0.3rem',
          }}>CIMB Posts Analytics Dashboard</h1>
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.83rem', margin: 0 }}>
            CIMB Social Media Intelligence
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {/* Username */}
          <div style={{ marginBottom: '1.1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '0.4rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Username
            </label>
            <div style={{ position: 'relative' }}>
              <User size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.3)' }} />
              <input
                type="text"
                value={username}
                onChange={e => { setUsername(e.target.value); setError(''); }}
                placeholder="Enter username"
                autoComplete="username"
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.06)',
                  border: `1px solid ${error ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: 10, padding: '0.75rem 1rem 0.75rem 2.6rem',
                  color: '#fff', fontSize: '0.92rem', fontFamily: 'inherit',
                  outline: 'none', transition: 'border-color 0.2s',
                }}
                onFocus={e => { e.target.style.borderColor = 'rgba(185,28,28,0.6)'; }}
                onBlur={e => { e.target.style.borderColor = error ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'; }}
              />
            </div>
          </div>

          {/* Password */}
          <div style={{ marginBottom: '1.6rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'rgba(255,255,255,0.5)', marginBottom: '0.4rem', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <Lock size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.3)' }} />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => { setPassword(e.target.value); setError(''); }}
                placeholder="Enter password"
                autoComplete="current-password"
                style={{
                  width: '100%', boxSizing: 'border-box',
                  background: 'rgba(255,255,255,0.06)',
                  border: `1px solid ${error ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: 10, padding: '0.75rem 2.8rem 0.75rem 2.6rem',
                  color: '#fff', fontSize: '0.92rem', fontFamily: 'inherit',
                  outline: 'none', transition: 'border-color 0.2s',
                }}
                onFocus={e => { e.target.style.borderColor = 'rgba(185,28,28,0.6)'; }}
                onBlur={e => { e.target.style.borderColor = error ? 'rgba(239,68,68,0.5)' : 'rgba(255,255,255,0.1)'; }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(v => !v)}
                style={{
                  position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                  background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                  color: 'rgba(255,255,255,0.35)', display: 'flex', alignItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <p style={{
              color: '#f87171', fontSize: '0.83rem', margin: '-0.8rem 0 1rem',
              display: 'flex', alignItems: 'center', gap: '0.3rem',
            }}>⚠ {error}</p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading || !username || !password}
            style={{
              width: '100%',
              background: loading || !username || !password
                ? 'rgba(185,28,28,0.4)'
                : 'linear-gradient(135deg, #b91c1c, #991b1b)',
              color: '#fff', border: 'none', borderRadius: 10,
              padding: '0.85rem', fontWeight: 700, fontSize: '0.95rem',
              cursor: loading || !username || !password ? 'not-allowed' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem',
              fontFamily: 'inherit',
              boxShadow: loading || !username || !password ? 'none' : '0 4px 20px rgba(185,28,28,0.4)',
              transition: 'all 0.2s',
            }}
          >
            {loading
              ? <><div style={{ width: 18, height: 18, border: '2px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.7s linear infinite' }} /> Signing in…</>
              : <><LogIn size={18} /> Sign In</>
            }
          </button>
        </form>
      </div>

      <style>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-8px); }
          40% { transform: translateX(8px); }
          60% { transform: translateX(-6px); }
          80% { transform: translateX(6px); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        input::placeholder { color: rgba(255,255,255,0.2); }
      `}</style>
    </div>
  );
};

export default Login;
