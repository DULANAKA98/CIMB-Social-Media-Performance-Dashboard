/* eslint-disable react/prop-types */
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Bot, Database, MessageCircle, Send, Sparkles, Trash2, X } from 'lucide-react';
import './ChatWidget.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
const STARTERS = [
  'Which platform performed best?',
  'Which content format had the strongest engagement rate?',
  'What were the top-performing posts?',
];
const GREETING = {
  role: 'assistant',
  content: 'Hi — ask me about performance, platforms, formats, categories, followers or top posts for the selected dashboard period.',
  greeting: true,
};

function periodLabel(startDate, endDate, platform) {
  const scope = platform || 'All platforms';
  if (!startDate || !endDate) return `${scope} · All available dates`;
  const date = value => new Intl.DateTimeFormat('en-MY', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(`${value}T00:00:00`));
  return `${scope} · ${date(startDate)} – ${date(endDate)}`;
}

export default function ChatWidget({ startDate, endDate, activeTab, currentPage, selectedPlatform }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([GREETING]);
  const [suggestions, setSuggestions] = useState(STARTERS);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages, isLoading]);

  useEffect(() => {
    if (!isOpen) return undefined;
    inputRef.current?.focus();
    const close = event => { if (event.key === 'Escape') setIsOpen(false); };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [isOpen]);

  const clearChat = () => {
    setMessages([GREETING]);
    setSuggestions(STARTERS);
    setInput('');
    inputRef.current?.focus();
  };

  const send = async value => {
    const question = value.trim();
    if (!question || isLoading) return;
    const userMessage = { role: 'user', content: question };
    setMessages(previous => [...previous, userMessage]);
    setSuggestions([]);
    setInput('');
    setIsLoading(true);
    try {
      const history = messages
        .filter(message => !message.greeting)
        .slice(-8)
        .map(({ role, content }) => ({ role, content }));
      const response = await axios.post(`${API_URL}/chat`, {
        message: question,
        history,
        start_date: startDate || null,
        end_date: endDate || null,
        active_tab: currentPage || activeTab || 'executive',
        platform: selectedPlatform || null,
      }, { timeout: 60000 });
      setMessages(previous => [...previous, {
        role: 'assistant',
        content: response.data.reply,
        fallback: Boolean(response.data?._meta?.fallback),
      }]);
      setSuggestions(Array.isArray(response.data.suggested_questions) ? response.data.suggested_questions : STARTERS);
    } catch (error) {
      const detail = error.response?.data?.detail;
      setMessages(previous => [...previous, {
        role: 'assistant',
        content: typeof detail === 'string' ? detail : 'I could not reach the dashboard data right now. Please try again in a moment.',
        error: true,
      }]);
      setSuggestions(STARTERS);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = event => {
    event.preventDefault();
    send(input);
  };

  return <div className="cimb-chat-shell">
    {isOpen && <section className="cimb-chat-window" role="dialog" aria-label="CIMB data assistant" aria-live="polite">
      <header className="cimb-chat-header">
        <span className="cimb-chat-avatar"><Sparkles size={18} /></span>
        <div><h2>CIMB Data Assistant</h2><p><span /> Connected to dashboard data</p></div>
        <button type="button" className="cimb-chat-icon" onClick={clearChat} title="Clear conversation" aria-label="Clear conversation"><Trash2 size={16} /></button>
        <button type="button" className="cimb-chat-icon" onClick={() => setIsOpen(false)} aria-label="Close data assistant"><X size={18} /></button>
      </header>

      <div className="cimb-chat-context"><Database size={13} /><span>{periodLabel(startDate, endDate, selectedPlatform)}</span></div>

      <div className="cimb-chat-messages">
        {messages.map((message, index) => <div key={`${message.role}-${index}`} className={`cimb-chat-row ${message.role}`}>
          {message.role === 'assistant' && <span className="cimb-chat-mini-avatar"><Bot size={14} /></span>}
          <div className={`cimb-chat-bubble ${message.error ? 'error' : ''}`}>
            {message.content}
            {message.fallback && <small>Calculated fallback answer</small>}
          </div>
        </div>)}
        {isLoading && <div className="cimb-chat-row assistant"><span className="cimb-chat-mini-avatar"><Bot size={14} /></span><div className="cimb-chat-bubble typing"><i /><i /><i /><span className="sr-only">Analyzing dashboard data</span></div></div>}
        <div ref={messagesEndRef} />
      </div>

      {!isLoading && suggestions.length > 0 && <div className="cimb-chat-suggestions" aria-label="Suggested questions">
        {suggestions.slice(0, 3).map(suggestion => <button type="button" key={suggestion} onClick={() => send(suggestion)}>{suggestion}</button>)}
      </div>}

      <form className="cimb-chat-form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="cimb-chat-input">Ask the dashboard</label>
        <textarea
          id="cimb-chat-input"
          ref={inputRef}
          rows={1}
          maxLength={600}
          value={input}
          onChange={event => setInput(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey) {
              event.preventDefault();
              if (input.trim()) send(input);
            }
          }}
          placeholder="Ask about your dashboard…"
          disabled={isLoading}
        />
        <button type="submit" disabled={!input.trim() || isLoading} aria-label="Send question"><Send size={17} /></button>
      </form>
      <p className="cimb-chat-disclaimer">Answers use the selected dashboard data. Review before sharing.</p>
    </section>}

    <button
      type="button"
      className={`cimb-chat-launcher ${isOpen ? 'is-open' : ''}`}
      onClick={() => setIsOpen(value => !value)}
      aria-expanded={isOpen}
      aria-label={isOpen ? 'Close CIMB data assistant' : 'Open CIMB data assistant'}
    >
      {isOpen ? <X size={23} /> : <MessageCircle size={24} />}
      {!isOpen && <span>Ask CIMB data</span>}
    </button>
  </div>;
}
