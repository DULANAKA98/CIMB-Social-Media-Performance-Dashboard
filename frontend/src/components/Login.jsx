/* eslint-disable react/prop-types */
import { useState } from 'react';
import { Eye, EyeOff, LogIn, Lock, User } from 'lucide-react';
import './Login.css';

const VALID_USERNAME = 'dulanaka';
const VALID_PASSWORD = '1234';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  const handleSubmit = async event => {
    event.preventDefault();
    setError('');
    setLoading(true);

    await new Promise(resolve => setTimeout(resolve, 600));

    if (username.trim() === VALID_USERNAME && password === VALID_PASSWORD) {
      onLogin();
    } else {
      setError('Invalid username or password.');
      setShake(true);
      setTimeout(() => setShake(false), 500);
    }
    setLoading(false);
  };

  return <main className="login-page">
    <div className="login-glow login-glow-left" />
    <div className="login-glow login-glow-right" />

    <section className={`login-card ${shake ? 'is-shaking' : ''}`} aria-labelledby="login-title">
      <div className="login-brand">
        <img src="/cimb-logo.jpg?v=2" alt="CIMB" width="180" height="50" />
        <h1 id="login-title">Social Media Performance Dashboard</h1>
        <p>Secure reporting workspace</p>
      </div>

      <form onSubmit={handleSubmit}>
        <label className="login-field">
          <span>Username</span>
          <span className={`login-input ${error ? 'has-error' : ''}`}>
            <User size={17} aria-hidden="true" />
            <input
              type="text"
              value={username}
              onChange={event => { setUsername(event.target.value); setError(''); }}
              placeholder="Enter username"
              autoComplete="username"
            />
          </span>
        </label>

        <label className="login-field">
          <span>Password</span>
          <span className={`login-input ${error ? 'has-error' : ''}`}>
            <Lock size={17} aria-hidden="true" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={event => { setPassword(event.target.value); setError(''); }}
              placeholder="Enter password"
              autoComplete="current-password"
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword(value => !value)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          </span>
        </label>

        {error && <p className="login-error" role="alert">{error}</p>}

        <button className="login-submit" type="submit" disabled={loading || !username || !password}>
          {loading ? <><span className="login-spinner" /> Signing in…</> : <><LogIn size={18} /> Sign in</>}
        </button>
      </form>
    </section>
  </main>;
}
