import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { MessageCircle, X, Send, Sparkles } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

const ChatWidget = ({ startDate, endDate, activeTab, executiveSummary, strategyData }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I am your AI Data Analyst. Ask me anything about the currently selected dataset!' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = { role: 'user', content: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send message, history (excluding the very first greeting if preferred, but sending it is fine), and dates
      const payload = {
        message: userMessage.content,
        history: messages.filter(m => m.role !== 'system'), // Exclude local system prompts if any
        start_date: startDate || null,
        end_date: endDate || null,
        active_tab: activeTab || null,
        executive_summary: executiveSummary || null,
        strategy_data: strategyData || null,
      };

      const res = await axios.post(`${API_URL}/chat`, payload);
      
      if (res.data.error) {
        setMessages((prev) => [...prev, { role: 'assistant', content: `Error: ${res.data.error}` }]);
      } else {
        setMessages((prev) => [...prev, { role: 'assistant', content: res.data.reply }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error communicating with the server.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={styles.widgetContainer}>
      {/* Chat Window */}
      {isOpen && (
        <div style={styles.chatWindow} className="glass-panel">
          <div style={styles.header}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sparkles size={18} color="var(--accent-purple)" />
              <h3 style={{ fontSize: 'calc(1rem + 2px)', margin: 0, color: 'var(--text-primary)' }}>AI Analyst</h3>
            </div>
            <button onClick={() => setIsOpen(false)} style={styles.closeBtn}>
              <X size={18} />
            </button>
          </div>
          
          <div style={styles.messagesContainer}>
            {messages.map((msg, idx) => (
              <div key={idx} style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: '1rem'
              }}>
                <div style={{
                  maxWidth: '85%',
                  padding: '0.8rem 1rem',
                  borderRadius: '12px',
                  background: msg.role === 'user' ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))' : 'rgba(255, 255, 255, 0.05)',
                  color: 'white',
                  fontSize: 'calc(0.9rem + 2px)',
                  lineHeight: '1.4',
                  wordWrap: 'break-word',
                  whiteSpace: 'pre-wrap'
                }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '1rem' }}>
                <div style={{ padding: '0.8rem 1rem', borderRadius: '12px', background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-secondary)' }}>
                  <div className="spinner" style={{ width: '16px', height: '16px', borderTopColor: 'var(--accent-purple)', borderWidth: '2px' }} />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSend} style={styles.inputArea}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about the dataset..."
              style={styles.input}
              disabled={isLoading}
            />
            <button type="submit" disabled={!input.trim() || isLoading} style={{
              ...styles.sendBtn,
              opacity: !input.trim() || isLoading ? 0.5 : 1,
              cursor: !input.trim() || isLoading ? 'not-allowed' : 'pointer'
            }}>
              <Send size={18} />
            </button>
          </form>
        </div>
      )}

      {/* Floating Button */}
      {!isOpen && (
        <button onClick={() => setIsOpen(true)} style={styles.floatingBtn}>
          <MessageCircle size={28} />
        </button>
      )}
    </div>
  );
};

const styles = {
  widgetContainer: {
    position: 'fixed',
    bottom: '30px',
    right: '30px',
    zIndex: 9999,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
  },
  floatingBtn: {
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))',
    color: 'white',
    border: 'none',
    boxShadow: '0 8px 32px rgba(139, 92, 246, 0.4)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'transform 0.2s ease',
  },
  chatWindow: {
    width: '380px',
    height: '550px',
    display: 'flex',
    flexDirection: 'column',
    padding: '0', // Overriding glass-panel padding
    overflow: 'hidden',
    boxShadow: '0 15px 45px rgba(0, 0, 0, 0.4)',
    marginBottom: '1rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '1rem 1.2rem',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    background: 'rgba(0, 0, 0, 0.2)',
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-secondary)',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4px',
  },
  messagesContainer: {
    flex: 1,
    overflowY: 'auto',
    padding: '1.2rem',
    display: 'flex',
    flexDirection: 'column',
  },
  inputArea: {
    display: 'flex',
    padding: '1rem',
    borderTop: '1px solid rgba(255, 255, 255, 0.08)',
    background: 'rgba(0, 0, 0, 0.2)',
    gap: '0.8rem',
  },
  input: {
    flex: 1,
    background: 'rgba(255, 255, 255, 0.05)',
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '8px',
    padding: '0.8rem 1rem',
    color: 'white',
    outline: 'none',
    fontFamily: 'inherit',
    fontSize: 'calc(0.9rem + 2px)',
  },
  sendBtn: {
    background: 'var(--accent-blue)',
    color: 'white',
    border: 'none',
    borderRadius: '8px',
    width: '42px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'opacity 0.2s ease',
  }
};

export default ChatWidget;
