import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  getSessions, getMessages, sendMessage,
  setSessionStatus, setSessionTag, markSessionRead,
  getQuickReplies, createQuickReply, deleteQuickReply,
} from '../api.js';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getInitials(name = '') {
  return name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2) || '??';
}

const AVATAR_COLORS = [
  'linear-gradient(135deg,#ff6b35,#ff4500)',
  'linear-gradient(135deg,#0066ff,#6366f1)',
  'linear-gradient(135deg,#10b981,#059669)',
  'linear-gradient(135deg,#8b5cf6,#a855f7)',
  'linear-gradient(135deg,#ec4899,#f43f5e)',
  'linear-gradient(135deg,#f59e0b,#d97706)',
];

function avatarColor(id) {
  return AVATAR_COLORS[(id || 0) % AVATAR_COLORS.length];
}

function formatTime(isoStr) {
  if (!isoStr) return '';
  const d = new Date(isoStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return d.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return 'Вчора';
  if (diffDays < 7) return d.toLocaleDateString('uk-UA', { weekday: 'short' });
  return d.toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit' });
}

function formatMsgTime(isoStr) {
  if (!isoStr) return '';
  return new Date(isoStr).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  return new Date(isoStr).toLocaleDateString('uk-UA', { day: 'numeric', month: 'long', year: 'numeric' });
}

function groupByDate(messages) {
  const groups = [];
  let lastDate = null;
  for (const msg of messages) {
    const d = msg.created_at ? new Date(msg.created_at).toDateString() : null;
    if (d !== lastDate) {
      groups.push({ type: 'divider', date: msg.created_at, key: d });
      lastDate = d;
    }
    groups.push(msg);
  }
  return groups;
}

const STATUS_LABELS = { ai: 'AI', human: 'Людина', closed: 'Закрито' };
const TAG_LABELS = { hot: 'Гарячий', cold: 'Холодний', vip: 'VIP' };

// Sound notification using Web Audio API (no external file needed)
function playNotificationSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.4);
  } catch {}
}

function sendBrowserNotification(title, body) {
  if (Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/favicon.ico' });
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission();
  }
}

// ─── Session List Item ────────────────────────────────────────────────────────

function SessionItem({ session, active, onClick }) {
  const color = avatarColor(session.id);
  const initials = getInitials(session.first_name
    ? `${session.first_name} ${session.last_name || ''}`
    : session.username || '');

  const name = session.first_name
    ? `${session.first_name}${session.last_name ? ' ' + session.last_name : ''}`
    : session.username || `User ${session.user_id}`;

  return (
    <div className={`session-item${active ? ' active' : ''}`} onClick={onClick}>
      <div className="sess-avatar" style={{ background: color }}>
        {initials}
        <div
          className="status-dot"
          style={{ background: session.status === 'human' ? '#10b981' : '#94a3b8' }}
        />
      </div>
      <div className="sess-body">
        <div className="sess-top">
          <span className="sess-name">{name}</span>
          <span className="sess-time">{formatTime(session.last_message_at || session.updated_at)}</span>
        </div>
        <div className="sess-preview">{session.last_message || '—'}</div>
        <div className="sess-bottom">
          <span className="sess-handle">
            {session.username ? `@${session.username}` : `id${session.user_id}`}
          </span>
          {session.unread_count > 0 && (
            <span className={`unread-badge${session.status === 'ai' ? ' blue' : ''}`}>
              {session.unread_count}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Chat Header ──────────────────────────────────────────────────────────────

function ChatHeader({ session, onToggleInfo, onTakeOver, onReturnToAI, onClose }) {
  if (!session) return null;
  const color = avatarColor(session.id);
  const name = session.first_name
    ? `${session.first_name}${session.last_name ? ' ' + session.last_name : ''}`
    : session.username || `User ${session.user_id}`;
  const initials = getInitials(name);
  const isHuman = session.status === 'human';

  return (
    <div className="chat-topbar">
      <div className="sess-avatar-sm-lg" style={{ background: color }}>{initials}</div>
      <div>
        <div className="chat-user-name">{name}</div>
        <div className="chat-user-meta">
          {isHuman ? (
            <span className="online-pill"><span className="online-pill-dot" />Людина</span>
          ) : (
            <span className="ai-pill">🤖 AI</span>
          )}
          {session.username && <span>@{session.username}</span>}
          {session.tag && (
            <span className={`tag-badge tag-${session.tag}`}>{TAG_LABELS[session.tag]}</span>
          )}
        </div>
      </div>
      <div className="chat-actions">
        {!isHuman && session.status !== 'closed' && (
          <button className="btn-take-over" onClick={onTakeOver} title="Підключитись до чату">
            Підключитись
          </button>
        )}
        {isHuman && (
          <button className="btn-return-ai" onClick={onReturnToAI} title="Повернути AI">
            Повернути AI
          </button>
        )}
        {session.status !== 'closed' && (
          <button className="icon-btn" onClick={onClose} title="Закрити діалог">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
        <button className="icon-btn" onClick={onToggleInfo} title="Інфо про клієнта">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─── Message Bubble ───────────────────────────────────────────────────────────

function MessageBubble({ msg, session }) {
  const isOut = msg.direction === 'out';
  const color = avatarColor(session?.id);
  const initials = getInitials(
    session?.first_name
      ? `${session.first_name} ${session.last_name || ''}`
      : session?.username || ''
  );

  return (
    <div className={`msg-row${isOut ? ' out' : ''}`}>
      {!isOut && (
        <div className="msg-avatar-sm" style={{ background: color, color: '#fff' }}>{initials}</div>
      )}
      <div>
        <div className={`bubble ${isOut ? 'out' : 'in'}`}>{msg.text}</div>
        <div className="bubble-meta">
          {formatMsgTime(msg.created_at)}
          {isOut && <span className="tick-read">✓✓</span>}
        </div>
      </div>
      {isOut && (
        <div className="msg-avatar-sm" style={{ background: 'linear-gradient(135deg,#ff6b35,#0066ff)', color: '#fff' }}>АД</div>
      )}
    </div>
  );
}

// ─── Right Sidebar ────────────────────────────────────────────────────────────

function RightSidebar({ session, quickReplies, onTagChange, onAddQR, onDeleteQR }) {
  const [newQRTitle, setNewQRTitle] = useState('');
  const [newQRContent, setNewQRContent] = useState('');
  const [addingQR, setAddingQR] = useState(false);

  if (!session) return null;

  const name = session.first_name
    ? `${session.first_name}${session.last_name ? ' ' + session.last_name : ''}`
    : session.username || `User ${session.user_id}`;
  const initials = getInitials(name);
  const color = avatarColor(session.id);

  const handleAddQR = async (e) => {
    e.preventDefault();
    if (!newQRTitle.trim() || !newQRContent.trim()) return;
    await onAddQR(newQRTitle.trim(), newQRContent.trim());
    setNewQRTitle('');
    setNewQRContent('');
    setAddingQR(false);
  };

  return (
    <div className="right-sidebar">
      {/* Client profile */}
      <div className="rs-card">
        <div className="client-profile">
          <div className="client-avatar" style={{ background: color }}>{initials}</div>
          <div className="client-name">{name}</div>
          {session.username && <div className="client-handle">@{session.username}</div>}
          <div className={`lead-status lead-${session.tag || 'new'}`}>
            <svg width="7" height="7" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="10" /></svg>
            {TAG_LABELS[session.tag] || 'Нова заявка'}
          </div>
        </div>
        <div className="info-list">
          <div className="info-row">
            <span className="info-label">User ID</span>
            <span className="info-value">{session.user_id}</span>
          </div>
          {session.username && (
            <div className="info-row">
              <span className="info-label">Username</span>
              <span className="info-value">@{session.username}</span>
            </div>
          )}
          <div className="info-row">
            <span className="info-label">Статус</span>
            <span className="info-value">{STATUS_LABELS[session.status] || session.status}</span>
          </div>
          {session.updated_at && (
            <div className="info-row">
              <span className="info-label">Оновлено</span>
              <span className="info-value">{formatDate(session.updated_at)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Tag selector */}
      <div className="rs-card">
        <div className="rs-card-title">Тег ліда</div>
        <div className="tags-wrap">
          {[null, 'hot', 'cold', 'vip'].map((t) => (
            <button
              key={t ?? 'none'}
              className={`tag${session.tag === t ? ' tag-active' : ''}${t === 'hot' ? ' tag-hot-btn' : t === 'vip' ? ' tag-vip-btn' : t === 'cold' ? ' tag-cold-btn' : ''}`}
              onClick={() => onTagChange(t)}
            >
              {t ? TAG_LABELS[t] : 'Без тегу'}
            </button>
          ))}
        </div>
      </div>

      {/* Quick replies management */}
      <div className="rs-card">
        <div className="rs-card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          Швидкі відповіді
          <button className="rs-add-btn" onClick={() => setAddingQR((v) => !v)}>
            {addingQR ? '✕' : '+'}
          </button>
        </div>
        {addingQR && (
          <form onSubmit={handleAddQR} className="qr-add-form">
            <input
              className="qr-add-input"
              placeholder="Назва..."
              value={newQRTitle}
              onChange={(e) => setNewQRTitle(e.target.value)}
              maxLength={50}
            />
            <textarea
              className="qr-add-textarea"
              placeholder="Текст відповіді..."
              value={newQRContent}
              onChange={(e) => setNewQRContent(e.target.value)}
              rows={3}
              maxLength={500}
            />
            <button type="submit" className="btn-primary" style={{ width: '100%', fontSize: 12, padding: '8px' }}>
              Зберегти
            </button>
          </form>
        )}
        <div className="qr-list">
          {quickReplies.length === 0 && (
            <div style={{ color: 'var(--text-muted)', fontSize: 12, textAlign: 'center', padding: '12px 0' }}>
              Немає швидких відповідей
            </div>
          )}
          {quickReplies.map((qr) => (
            <div key={qr.id} className="qr-list-item">
              <div>
                <div className="qr-list-title">{qr.title}</div>
                <div className="qr-list-content">{qr.content}</div>
              </div>
              <button className="qr-del-btn" onClick={() => onDeleteQR(qr.id)} title="Видалити">✕</button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main Chats Page ──────────────────────────────────────────────────────────

export default function Chats() {
  const { sessionId } = useParams();
  const navigate = useNavigate();

  // Sessions state
  const [sessions, setSessions] = useState([]);
  const [filteredSessions, setFilteredSessions] = useState([]);
  const [activeSession, setActiveSession] = useState(null);
  const [filter, setFilter] = useState('all'); // all | ai | human | closed
  const [search, setSearch] = useState('');

  // Messages state
  const [messages, setMessages] = useState([]);
  const [lastMsgId, setLastMsgId] = useState(0);
  const [loadingMessages, setLoadingMessages] = useState(false);

  // Input state
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);

  // Quick replies
  const [quickReplies, setQuickReplies] = useState([]);

  // UI state
  const [showInfo, setShowInfo] = useState(true);

  // Refs
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const pollRef = useRef(null);
  const prevUnreadRef = useRef({});

  // Request notification permission on mount
  useEffect(() => {
    if (Notification && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // Load sessions
  const loadSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      setSessions(data);
    } catch {}
  }, []);

  // Load quick replies
  const loadQuickReplies = useCallback(async () => {
    try {
      const data = await getQuickReplies();
      setQuickReplies(data);
    } catch {}
  }, []);

  useEffect(() => {
    loadSessions();
    loadQuickReplies();
  }, []);

  // Filter sessions
  useEffect(() => {
    let list = [...sessions];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(
        (s) =>
          (s.first_name || '').toLowerCase().includes(q) ||
          (s.last_name || '').toLowerCase().includes(q) ||
          (s.username || '').toLowerCase().includes(q) ||
          String(s.user_id).includes(q)
      );
    }
    if (filter === 'ai') list = list.filter((s) => s.status === 'ai');
    else if (filter === 'human') list = list.filter((s) => s.status === 'human');
    else if (filter === 'closed') list = list.filter((s) => s.status === 'closed');
    else list = list.filter((s) => s.status !== 'closed');
    setFilteredSessions(list);
  }, [sessions, filter, search]);

  // Sync sessionId from URL
  useEffect(() => {
    if (sessionId) {
      const sess = sessions.find((s) => String(s.id) === String(sessionId));
      if (sess) setActiveSession(sess);
    }
  }, [sessionId, sessions]);

  // Load messages when active session changes
  useEffect(() => {
    if (!activeSession) return;
    setMessages([]);
    setLastMsgId(0);
    setLoadingMessages(true);

    getMessages(activeSession.id, 0)
      .then((data) => {
        setMessages(data);
        const maxId = data.length ? Math.max(...data.map((m) => m.id)) : 0;
        setLastMsgId(maxId);
        markSessionRead(activeSession.id).catch(() => {});
        setSessions((prev) =>
          prev.map((s) => (s.id === activeSession.id ? { ...s, unread_count: 0 } : s))
        );
      })
      .catch(() => {})
      .finally(() => setLoadingMessages(false));
  }, [activeSession?.id]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Polling for new messages + sessions
  useEffect(() => {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      // Refresh session list
      try {
        const data = await getSessions();

        // Check for new unread from sessions we're not viewing
        data.forEach((s) => {
          const prev = prevUnreadRef.current[s.id] || 0;
          if (
            s.unread_count > prev &&
            s.unread_count > 0 &&
            (!activeSession || s.id !== activeSession.id)
          ) {
            const name = s.first_name || s.username || `User ${s.user_id}`;
            playNotificationSound();
            sendBrowserNotification('Нове повідомлення', `${name}: ${s.last_message || ''}`);
          }
          prevUnreadRef.current[s.id] = s.unread_count;
        });

        setSessions(data);
      } catch {}

      // Fetch new messages for active session
      if (activeSession) {
        try {
          const newMsgs = await getMessages(activeSession.id, lastMsgId);
          if (newMsgs.length > 0) {
            setMessages((prev) => [...prev, ...newMsgs]);
            const maxId = Math.max(...newMsgs.map((m) => m.id));
            setLastMsgId((prev) => Math.max(prev, maxId));
            markSessionRead(activeSession.id).catch(() => {});
          }
        } catch {}
      }
    }, 2000);

    return () => clearInterval(pollRef.current);
  }, [activeSession?.id, lastMsgId]);

  // Select session
  const handleSelectSession = (session) => {
    setActiveSession(session);
    navigate(`/chats/${session.id}`, { replace: true });
  };

  // Send message
  const handleSend = async () => {
    const text = inputText.trim();
    if (!text || !activeSession || sending) return;
    setSending(true);
    setInputText('');

    // Optimistic update
    const tempMsg = {
      id: Date.now(),
      direction: 'out',
      text,
      created_at: new Date().toISOString(),
      _temp: true,
    };
    setMessages((prev) => [...prev, tempMsg]);

    try {
      await sendMessage(activeSession.id, text);
    } catch {
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.id !== tempMsg.id));
      setInputText(text);
    } finally {
      setSending(false);
    }
  };

  // Handle Enter key in textarea
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Auto-resize textarea
  const handleInputChange = (e) => {
    setInputText(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  };

  // Session actions
  const handleTakeOver = async () => {
    if (!activeSession) return;
    try {
      await setSessionStatus(activeSession.id, 'human');
      setActiveSession((prev) => ({ ...prev, status: 'human' }));
      setSessions((prev) => prev.map((s) => s.id === activeSession.id ? { ...s, status: 'human' } : s));
    } catch {}
  };

  const handleReturnToAI = async () => {
    if (!activeSession) return;
    try {
      await setSessionStatus(activeSession.id, 'ai');
      setActiveSession((prev) => ({ ...prev, status: 'ai' }));
      setSessions((prev) => prev.map((s) => s.id === activeSession.id ? { ...s, status: 'ai' } : s));
    } catch {}
  };

  const handleCloseSession = async () => {
    if (!activeSession) return;
    try {
      await setSessionStatus(activeSession.id, 'closed');
      setActiveSession((prev) => ({ ...prev, status: 'closed' }));
      setSessions((prev) => prev.map((s) => s.id === activeSession.id ? { ...s, status: 'closed' } : s));
    } catch {}
  };

  const handleTagChange = async (tag) => {
    if (!activeSession) return;
    try {
      await setSessionTag(activeSession.id, tag);
      setActiveSession((prev) => ({ ...prev, tag }));
      setSessions((prev) => prev.map((s) => s.id === activeSession.id ? { ...s, tag } : s));
    } catch {}
  };

  const handleAddQR = async (title, content) => {
    try {
      await createQuickReply(title, content);
      await loadQuickReplies();
    } catch {}
  };

  const handleDeleteQR = async (id) => {
    try {
      await deleteQuickReply(id);
      setQuickReplies((prev) => prev.filter((q) => q.id !== id));
    } catch {}
  };

  // Group messages by date for display
  const groupedMessages = groupByDate(messages);

  // Stats for header
  const totalSessions = sessions.length;
  const humanSessions = sessions.filter((s) => s.status === 'human').length;
  const unreadTotal = sessions.reduce((acc, s) => acc + (s.unread_count || 0), 0);

  return (
    <div className="page-wrap">
      {/* Top header bar */}
      <header className="topbar">
        <div>
          <span className="topbar-title">Чати</span>
          <span className="topbar-sub">/ CRM</span>
        </div>
        <div className="topbar-right">
          <div className="stat-chip">
            <div className="stat-dot" />
            <span className="stat-chip-val">{totalSessions}</span>
            <span className="stat-chip-label">чатів</span>
          </div>
          <div className="stat-chip">
            <div className="stat-dot online" />
            <span className="stat-chip-val">{humanSessions}</span>
            <span className="stat-chip-label">з менеджером</span>
          </div>
          {unreadTotal > 0 && (
            <div className="stat-chip">
              <div className="stat-dot warn" />
              <span className="stat-chip-val">{unreadTotal}</span>
              <span className="stat-chip-label">нових</span>
            </div>
          )}
        </div>
      </header>

      <div className="content-area">
        {/* ── LEFT: Session list ── */}
        <div className="session-list">
          <div className="list-header">
            <div className="list-title">Розмови</div>
            <div className="search-wrap">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
              </svg>
              <input
                type="text"
                placeholder="Пошук клієнтів..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          <div className="list-tabs">
            {[['all', 'Всі'], ['ai', 'AI'], ['human', 'Людина'], ['closed', 'Закриті']].map(([val, label]) => (
              <button
                key={val}
                className={`tab-btn${filter === val ? ' active' : ''}`}
                onClick={() => setFilter(val)}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="sessions">
            {filteredSessions.length === 0 && (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                {search ? 'Нічого не знайдено' : 'Немає розмов'}
              </div>
            )}
            {filteredSessions.map((sess) => (
              <SessionItem
                key={sess.id}
                session={sess}
                active={activeSession?.id === sess.id}
                onClick={() => handleSelectSession(sess)}
              />
            ))}
          </div>
        </div>

        {/* ── CENTER: Chat area ── */}
        <div className="chat-area">
          {!activeSession ? (
            <div className="chat-empty">
              <div className="chat-empty-icon">💬</div>
              <div className="chat-empty-title">Оберіть розмову</div>
              <div className="chat-empty-sub">Виберіть чат зі списку зліва, щоб почати переписку</div>
            </div>
          ) : (
            <>
              <ChatHeader
                session={activeSession}
                onToggleInfo={() => setShowInfo((v) => !v)}
                onTakeOver={handleTakeOver}
                onReturnToAI={handleReturnToAI}
                onClose={handleCloseSession}
              />

              {/* Messages */}
              <div className="messages-wrap">
                {loadingMessages && (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
                    <div className="spinner" />
                  </div>
                )}
                {groupedMessages.map((item, idx) =>
                  item.type === 'divider' ? (
                    <div key={`d-${idx}`} className="date-divider">
                      {formatDate(item.date)}
                    </div>
                  ) : (
                    <MessageBubble key={item.id} msg={item} session={activeSession} />
                  )
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Input area */}
              <div className="input-area">
                {quickReplies.length > 0 && (
                  <div className="quick-replies">
                    {quickReplies.slice(0, 4).map((qr) => (
                      <button
                        key={qr.id}
                        className="qr-btn"
                        onClick={() => {
                          setInputText(qr.content);
                          textareaRef.current?.focus();
                        }}
                      >
                        {qr.title}
                      </button>
                    ))}
                  </div>
                )}
                <div className="input-row">
                  <textarea
                    ref={textareaRef}
                    className="msg-input"
                    placeholder="Написати повідомлення... (Enter — надіслати, Shift+Enter — новий рядок)"
                    value={inputText}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    disabled={activeSession.status === 'closed'}
                  />
                  <button
                    className="send-btn"
                    onClick={handleSend}
                    disabled={!inputText.trim() || sending || activeSession.status === 'closed'}
                    title="Надіслати"
                  >
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* ── RIGHT: Info sidebar ── */}
        {activeSession && showInfo && (
          <RightSidebar
            session={activeSession}
            quickReplies={quickReplies}
            onTagChange={handleTagChange}
            onAddQR={handleAddQR}
            onDeleteQR={handleDeleteQR}
          />
        )}
      </div>

      <style>{`
        /* ── Header ── */
        .topbar {
          background: linear-gradient(135deg, #ff6b35 0%, #ff4500 40%, #0066ff 100%);
          padding: 0 24px; height: 60px; min-height: 60px;
          display: flex; align-items: center; gap: 16px;
          box-shadow: 0 2px 16px rgba(255,107,53,0.3);
          flex-shrink: 0;
        }
        .topbar-title { font-size: 16px; font-weight: 700; color: #fff; }
        .topbar-sub { font-size: 12px; color: rgba(255,255,255,0.7); margin-left: 4px; }
        .topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
        .stat-chip {
          display: flex; align-items: center; gap: 7px;
          background: rgba(255,255,255,0.18);
          border: 1px solid rgba(255,255,255,0.25);
          border-radius: 20px; padding: 6px 14px;
          color: #fff; font-size: 12.5px;
          backdrop-filter: blur(8px);
        }
        .stat-chip-val { font-weight: 700; }
        .stat-chip-label { opacity: 0.8; }
        .stat-dot { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.6); }
        .stat-dot.online { background: #86efac; }
        .stat-dot.warn { background: #fde68a; }

        /* ── Content area ── */
        .content-area { flex: 1; display: flex; overflow: hidden; }

        /* ── Session list ── */
        .session-list {
          width: 310px; min-width: 310px;
          background: var(--sidebar-bg);
          border-right: 1px solid var(--border);
          display: flex; flex-direction: column; overflow: hidden;
        }
        .list-header { padding: 16px 16px 12px; border-bottom: 1px solid var(--border-light); }
        .list-title { font-size: 15px; font-weight: 700; color: var(--text-primary); margin-bottom: 12px; }
        .search-wrap {
          display: flex; align-items: center; gap: 8px;
          background: var(--bg);
          border: 1.5px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 9px 12px;
          transition: border-color 0.15s;
        }
        .search-wrap:focus-within {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
        }
        .search-wrap svg { color: var(--text-muted); flex-shrink: 0; }
        .search-wrap input { border: none; background: none; outline: none; color: var(--text-primary); font-size: 13.5px; font-family: var(--font); width: 100%; }
        .search-wrap input::placeholder { color: var(--text-muted); }
        .list-tabs {
          display: flex; padding: 10px 16px; gap: 4px;
          border-bottom: 1px solid var(--border);
          overflow-x: auto; flex-shrink: 0;
        }
        .tab-btn {
          padding: 6px 14px; border-radius: 20px;
          font-size: 12px; font-weight: 600;
          cursor: pointer; white-space: nowrap;
          border: 1.5px solid var(--border);
          color: var(--text-secondary); background: transparent;
          font-family: var(--font); transition: all 0.15s;
        }
        .tab-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; box-shadow: 0 3px 10px rgba(255,107,53,0.35); }
        .tab-btn:hover:not(.active) { background: var(--card-hover); }
        .sessions { overflow-y: auto; flex: 1; }
        .session-item {
          display: flex; align-items: center; gap: 12px;
          padding: 14px 16px;
          cursor: pointer;
          border-bottom: 1px solid var(--border-light);
          border-left: 3px solid transparent;
          transition: background 0.12s;
        }
        .session-item:hover { background: var(--card-hover); }
        .session-item.active { background: var(--accent-light); border-left-color: var(--accent); }
        .sess-avatar {
          width: 44px; height: 44px;
          border-radius: var(--radius); color: #fff;
          display: flex; align-items: center; justify-content: center;
          font-size: 15px; font-weight: 700;
          flex-shrink: 0; position: relative;
          box-shadow: var(--shadow);
        }
        .status-dot {
          width: 11px; height: 11px; border-radius: 50%;
          border: 2px solid var(--sidebar-bg);
          position: absolute; bottom: 0; right: 0;
        }
        .sess-body { flex: 1; min-width: 0; }
        .sess-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }
        .sess-name { font-size: 13.5px; font-weight: 700; color: var(--text-primary); }
        .sess-time { font-size: 11px; color: var(--text-muted); flex-shrink: 0; margin-left: 8px; }
        .sess-preview { font-size: 12.5px; color: var(--text-secondary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .sess-bottom { display: flex; justify-content: space-between; align-items: center; margin-top: 5px; }
        .sess-handle { font-size: 11px; color: var(--text-muted); }
        .unread-badge {
          min-width: 20px; height: 20px; border-radius: 10px;
          background: var(--accent); color: #fff;
          font-size: 11px; font-weight: 700;
          display: flex; align-items: center; justify-content: center;
          padding: 0 6px;
          box-shadow: 0 2px 8px rgba(255,107,53,0.4);
        }
        .unread-badge.blue { background: var(--accent2); box-shadow: 0 2px 8px rgba(0,102,255,0.4); }

        /* ── Chat area ── */
        .chat-area { flex: 1; display: flex; flex-direction: column; background: var(--bg); min-width: 0; }
        .chat-empty {
          flex: 1; display: flex; flex-direction: column;
          align-items: center; justify-content: center; gap: 12px;
          color: var(--text-muted);
        }
        .chat-empty-icon { font-size: 48px; }
        .chat-empty-title { font-size: 18px; font-weight: 700; color: var(--text-secondary); }
        .chat-empty-sub { font-size: 13px; }

        /* Chat topbar */
        .chat-topbar {
          background: var(--card-bg);
          border-bottom: 1px solid var(--border);
          padding: 14px 20px;
          display: flex; align-items: center; gap: 14px;
          box-shadow: var(--shadow);
          flex-shrink: 0;
        }
        .sess-avatar-sm-lg {
          width: 42px; height: 42px;
          border-radius: 12px;
          display: flex; align-items: center; justify-content: center;
          font-size: 13px; font-weight: 700; color: #fff;
          flex-shrink: 0;
          box-shadow: 0 4px 12px rgba(255,107,53,0.3);
        }
        .chat-user-name { font-size: 15px; font-weight: 700; color: var(--text-primary); }
        .chat-user-meta { font-size: 12px; color: var(--text-secondary); margin-top: 2px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
        .online-pill {
          display: flex; align-items: center; gap: 4px;
          background: #dcfce7; color: #15803d;
          padding: 2px 8px; border-radius: 20px;
          font-size: 11px; font-weight: 600;
        }
        .online-pill-dot { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
        .ai-pill {
          background: var(--accent2-light); color: var(--accent2);
          padding: 2px 8px; border-radius: 20px;
          font-size: 11px; font-weight: 600;
        }
        .tag-badge {
          padding: 2px 8px; border-radius: 20px;
          font-size: 11px; font-weight: 600;
        }
        .tag-badge.tag-hot { background: #fef2f2; color: #dc2626; }
        .tag-badge.tag-cold { background: #f1f5f9; color: #64748b; }
        .tag-badge.tag-vip { background: #faf5ff; color: #7c3aed; }
        .chat-actions { margin-left: auto; display: flex; gap: 8px; align-items: center; }
        .btn-take-over {
          padding: 8px 16px; border-radius: var(--radius-sm);
          background: linear-gradient(135deg, #ff6b35, #ff4500);
          color: #fff; border: none;
          font-size: 12.5px; font-weight: 600;
          cursor: pointer; transition: all 0.15s;
          box-shadow: 0 3px 10px rgba(255,107,53,0.3);
        }
        .btn-take-over:hover { transform: translateY(-1px); box-shadow: 0 5px 14px rgba(255,107,53,0.38); }
        .btn-return-ai {
          padding: 8px 16px; border-radius: var(--radius-sm);
          background: var(--accent2-light); color: var(--accent2);
          border: 1.5px solid rgba(0,102,255,0.2);
          font-size: 12.5px; font-weight: 600;
          cursor: pointer; transition: all 0.15s;
        }
        .btn-return-ai:hover { background: #dbeafe; }
        .icon-btn {
          width: 36px; height: 36px;
          border-radius: 10px;
          background: var(--bg); border: 1.5px solid var(--border);
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; color: var(--text-secondary); transition: all 0.15s;
        }
        .icon-btn:hover { background: var(--accent-light); border-color: var(--accent); color: var(--accent); }

        /* Messages */
        .messages-wrap {
          flex: 1; overflow-y: auto; padding: 22px 20px;
          display: flex; flex-direction: column; gap: 14px;
        }
        .date-divider { text-align: center; font-size: 11.5px; color: var(--text-muted); margin: 4px 0; font-weight: 500; }
        .msg-row { display: flex; gap: 10px; align-items: flex-end; }
        .msg-row.out { flex-direction: row-reverse; }
        .msg-avatar-sm {
          width: 30px; height: 30px; border-radius: 9px;
          display: flex; align-items: center; justify-content: center;
          font-size: 10px; font-weight: 700; flex-shrink: 0;
          margin-bottom: 2px; box-shadow: var(--shadow);
        }
        .bubble {
          max-width: 62%; padding: 11px 15px;
          border-radius: var(--radius); line-height: 1.6;
          font-size: 13.5px; white-space: pre-wrap; word-break: break-word;
        }
        .bubble.in {
          background: var(--card-bg); color: var(--text-primary);
          border-radius: var(--radius) var(--radius) var(--radius) 4px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.07);
        }
        .bubble.out {
          background: linear-gradient(135deg, #ff6b35 0%, #ff4500 100%);
          color: #fff;
          border-radius: var(--radius) var(--radius) 4px var(--radius);
          box-shadow: 0 4px 14px rgba(255,107,53,0.3);
        }
        .bubble-meta {
          font-size: 10.5px; color: var(--text-muted);
          margin-top: 5px; display: flex; align-items: center; gap: 4px;
        }
        .msg-row.out .bubble-meta { justify-content: flex-end; color: rgba(255,107,53,0.7); }
        .tick-read { color: var(--accent2); font-size: 12px; }

        /* Input */
        .input-area {
          border-top: 1px solid var(--border);
          background: var(--card-bg);
          padding: 14px 20px;
          box-shadow: 0 -2px 12px rgba(0,0,0,0.04);
          flex-shrink: 0;
        }
        .quick-replies { display: flex; gap: 7px; margin-bottom: 12px; flex-wrap: wrap; }
        .qr-btn {
          padding: 6px 13px; border-radius: 20px;
          border: 1.5px solid var(--border);
          background: var(--bg); color: var(--text-secondary);
          font-size: 12px; font-weight: 500; cursor: pointer;
          transition: all 0.15s; font-family: var(--font);
        }
        .qr-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
        .input-row { display: flex; gap: 10px; align-items: flex-end; }
        .msg-input {
          flex: 1; background: var(--bg);
          border: 1.5px solid var(--border);
          border-radius: var(--radius);
          padding: 11px 16px;
          color: var(--text-primary); font-size: 13.5px;
          font-family: var(--font); outline: none;
          transition: all 0.15s;
          resize: none; min-height: 44px; max-height: 120px;
          line-height: 1.5;
        }
        .msg-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(255,107,53,0.1); }
        .msg-input::placeholder { color: var(--text-muted); }
        .msg-input:disabled { opacity: 0.5; cursor: not-allowed; }
        .send-btn {
          width: 44px; height: 44px; border-radius: var(--radius-sm);
          background: linear-gradient(135deg, #ff6b35, #ff4500);
          border: none; cursor: pointer;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
          box-shadow: 0 4px 14px rgba(255,107,53,0.4);
          transition: all 0.15s;
        }
        .send-btn:hover:not(:disabled) { transform: scale(1.06); box-shadow: 0 6px 18px rgba(255,107,53,0.45); }
        .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        /* Right sidebar */
        .right-sidebar {
          width: 285px; min-width: 285px;
          background: var(--sidebar-bg);
          border-left: 1px solid var(--border);
          overflow-y: auto; padding: 18px;
          display: flex; flex-direction: column; gap: 18px;
        }
        .rs-card {
          background: var(--bg); border: 1px solid var(--border);
          border-radius: var(--radius); padding: 16px;
        }
        .rs-card-title {
          font-size: 11px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.08em; color: var(--text-muted); margin-bottom: 12px;
        }
        .client-profile {
          display: flex; flex-direction: column; align-items: center; gap: 8px;
          padding-bottom: 14px; border-bottom: 1px solid var(--border); margin-bottom: 14px;
        }
        .client-avatar {
          width: 64px; height: 64px; border-radius: var(--radius);
          display: flex; align-items: center; justify-content: center;
          font-size: 22px; font-weight: 800; color: #fff;
          box-shadow: 0 6px 20px rgba(255,107,53,0.3);
        }
        .client-name { font-size: 16px; font-weight: 800; color: var(--text-primary); }
        .client-handle { font-size: 12.5px; color: var(--accent2); font-weight: 500; }
        .lead-status {
          display: flex; align-items: center; gap: 6px;
          padding: 5px 12px; border-radius: 20px;
          font-size: 12px; font-weight: 600;
        }
        .lead-hot { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
        .lead-new { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
        .lead-done { background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0; }
        .lead-cold { background: #f1f5f9; color: #64748b; border: 1px solid var(--border); }
        .lead-vip { background: #faf5ff; color: #7c3aed; border: 1px solid #ddd6fe; }
        .info-list { display: flex; flex-direction: column; gap: 8px; }
        .info-row { display: flex; justify-content: space-between; align-items: center; font-size: 12.5px; }
        .info-label { color: var(--text-muted); }
        .info-value { font-weight: 600; color: var(--text-primary); text-align: right; }
        .tags-wrap { display: flex; flex-wrap: wrap; gap: 6px; }
        .tag {
          padding: 5px 12px; border-radius: 8px;
          font-size: 11.5px; font-weight: 600;
          background: var(--accent-light); color: var(--accent);
          border: 1px solid rgba(255,107,53,0.2);
          cursor: pointer; transition: all 0.15s;
        }
        .tag.tag-active { background: var(--accent); color: #fff; }
        .tag.tag-hot-btn { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
        .tag.tag-hot-btn.tag-active { background: #dc2626; color: #fff; border-color: #dc2626; }
        .tag.tag-cold-btn { background: #f1f5f9; color: #64748b; border-color: var(--border); }
        .tag.tag-cold-btn.tag-active { background: #64748b; color: #fff; border-color: #64748b; }
        .tag.tag-vip-btn { background: #faf5ff; color: #7c3aed; border-color: #ddd6fe; }
        .tag.tag-vip-btn.tag-active { background: #7c3aed; color: #fff; border-color: #7c3aed; }
        .rs-add-btn {
          background: var(--accent-light); color: var(--accent);
          border: 1px solid rgba(255,107,53,0.2);
          border-radius: 6px; width: 22px; height: 22px;
          font-size: 14px; font-weight: 700;
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; line-height: 1;
          padding: 0;
        }
        .qr-add-form { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
        .qr-add-input, .qr-add-textarea {
          padding: 8px 12px;
          border: 1.5px solid var(--border);
          border-radius: 8px; font-size: 12.5px;
          font-family: var(--font); color: var(--text-primary);
          background: var(--card-bg); outline: none;
          transition: border-color 0.15s;
        }
        .qr-add-input:focus, .qr-add-textarea:focus { border-color: var(--accent); }
        .qr-add-textarea { resize: vertical; }
        .qr-list { display: flex; flex-direction: column; gap: 8px; }
        .qr-list-item {
          display: flex; justify-content: space-between; align-items: flex-start;
          gap: 8px; padding: 10px 12px;
          background: var(--card-bg); border: 1px solid var(--border);
          border-radius: 8px;
        }
        .qr-list-title { font-size: 12px; font-weight: 700; color: var(--text-primary); margin-bottom: 3px; }
        .qr-list-content { font-size: 11.5px; color: var(--text-secondary); line-height: 1.4; }
        .qr-del-btn {
          background: none; border: none; color: var(--text-muted);
          font-size: 12px; cursor: pointer; padding: 0; flex-shrink: 0;
          line-height: 1;
        }
        .qr-del-btn:hover { color: var(--danger); }
      `}</style>
    </div>
  );
}
