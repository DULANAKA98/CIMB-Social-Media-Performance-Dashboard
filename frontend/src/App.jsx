import React, { useState } from 'react'
import Dashboard from './components/Dashboard'
import Login from './components/Login'

function App() {
  const [authed, setAuthed] = useState(() => localStorage.getItem('authed') === 'true');

  const handleLogin = () => {
    localStorage.setItem('authed', 'true');
    setAuthed(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('authed');
    setAuthed(false);
  };

  if (!authed) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="App">
      <Dashboard onLogout={handleLogout} />
    </div>
  );
}

export default App
