import React, { useState } from 'react'
import Dashboard from './components/Dashboard'
import Login from './components/Login'

function App() {
  const [authed, setAuthed] = useState(false);

  const handleLogin = () => setAuthed(true);

  const handleLogout = () => {
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
