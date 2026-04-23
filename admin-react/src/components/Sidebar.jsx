import { useNavigate, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { getManagerStatus, setManagerStatus, logout } from '../api.js';

// Navigation items matching variant2 design
const NAV_SECTIONS = [
  {
    label: 'Робочий стіл',
    items: [
      {
        path: '/leads',
        label: 'Заявки',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        ),
      },
      {
        path: '/chats',
        label: 'Чати',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        ),
      },
      {
        path: '/content',
        label: 'Контент',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Аналіз',
    items: [
      {
        path: '/analytics',
        label: 'Аналітика',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        ),
      },
      {
        path: '/buttons',
        label: 'Кнопки',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0110 0v4" />
          </svg>
        ),
      },
    ],
  },
  {
    label: 'Налаштування',
    items: [
      {
        path: '/prompt',
        label: 'AI Промт',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2a10 10 0 100 20 10 10 0 000-20zm0 0v4m0 8v4m-4-4h8" />
          </svg>
        ),
      },
      {
        path: '/settings',
        label: 'Налаштування',
        icon: (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06-.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
          </svg>
        ),
      },
    ],
  },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [online, setOnline] = useState(true);
  const [managerName, setManagerName] = useState('Менеджер');

  useEffect(() => {
    getManagerStatus()
      .then((data) => {
        setOnline(data.online ?? true);
        if (data.username) setManagerName(data.username);
      })
      .catch(() => {});
  }, []);

  const handleLogout = async () => {
    try { await logout(); } catch {}
    navigate('/login');
  };

  const handleToggleStatus = async () => {
    const next = !online;
    setOnline(next);
    try {
      await setManagerStatus(next);
    } catch {
      setOnline(!next); // revert on error
    }
  };

  const initials = managerName
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-row">
          <div className="logo-icon">E</div>
          <div>
            <div className="logo-text">
              Ego<span>list</span>
            </div>
            <div className="logo-sub">Адмін · Дніпро</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="nav">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <div className="nav-section">{section.label}</div>
            {section.items.map((item) => {
              const isActive =
                item.path === '/chats'
                  ? location.pathname.startsWith('/chats')
                  : location.pathname === item.path;
              return (
                <div
                  key={item.path}
                  className={`nav-item${isActive ? ' active' : ''}`}
                  onClick={() => navigate(item.path)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  {item.label}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Manager status footer */}
      <div className="sidebar-footer">
        <div className="manager-card">
          <div className="manager-avatar">
            {initials}
            <div className="online-indicator" style={{ background: online ? '#10b981' : '#94a3b8' }} />
          </div>
          <div className="manager-info">
            <div className="manager-name">{managerName}</div>
            <button
              className={`toggle-pill${online ? '' : ' offline'}`}
              onClick={handleToggleStatus}
              title={online ? 'Перейти в офлайн' : 'Перейти в онлайн'}
            >
              <div className="toggle-dot" />
              {online ? 'Онлайн' : 'Офлайн'}
            </button>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Вийти">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
          </button>
        </div>
      </div>

      <style>{`
        .sidebar {
          width: 230px;
          min-width: 230px;
          max-width: 230px;
          background: var(--sidebar-bg);
          display: flex;
          flex-direction: column;
          border-right: 1px solid var(--border);
          box-shadow: 2px 0 12px rgba(0,0,0,0.04);
          z-index: 10;
          height: 100%;
          overflow: hidden;
        }
        .sidebar-logo {
          padding: 22px 20px 18px;
          border-bottom: 1px solid var(--border-light);
          flex-shrink: 0;
        }
        .logo-row { display: flex; align-items: center; gap: 11px; }
        .logo-icon {
          width: 38px; height: 38px;
          border-radius: var(--radius-sm);
          background: linear-gradient(135deg, #ff6b35 0%, #ff4500 100%);
          display: flex; align-items: center; justify-content: center;
          font-size: 18px; font-weight: 800; color: #fff;
          box-shadow: 0 4px 12px rgba(255,107,53,0.35);
          flex-shrink: 0;
        }
        .logo-text { font-size: 18px; font-weight: 800; color: var(--text-primary); letter-spacing: -0.02em; }
        .logo-text span { color: var(--accent); }
        .logo-sub { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
        .nav {
          flex: 1; padding: 14px 12px;
          display: flex; flex-direction: column; gap: 2px;
          overflow-y: auto;
        }
        .nav-section {
          font-size: 10px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.08em; color: var(--text-muted);
          padding: 12px 8px 6px;
        }
        .nav-item {
          display: flex; align-items: center; gap: 10px;
          padding: 10px 12px;
          border-radius: var(--radius-sm);
          cursor: pointer;
          color: var(--text-secondary);
          font-size: 13.5px; font-weight: 500;
          transition: all 0.15s;
          border-left: 3px solid transparent;
          user-select: none;
        }
        .nav-item:hover { background: var(--card-hover); color: var(--text-primary); }
        .nav-item.active {
          background: var(--accent-light);
          color: var(--accent);
          border-left-color: var(--accent);
          font-weight: 600;
        }
        .nav-icon {
          width: 18px; height: 18px; flex-shrink: 0; opacity: 0.75;
          display: flex; align-items: center; justify-content: center;
        }
        .nav-icon svg { width: 100%; height: 100%; }
        .nav-item.active .nav-icon { opacity: 1; }
        .sidebar-footer {
          padding: 14px 16px 18px;
          border-top: 1px solid var(--border-light);
          flex-shrink: 0;
        }
        .manager-card {
          display: flex; align-items: center; gap: 10px;
          padding: 10px;
          background: var(--bg);
          border-radius: var(--radius-sm);
          border: 1px solid var(--border);
        }
        .manager-avatar {
          width: 34px; height: 34px;
          border-radius: 10px;
          background: linear-gradient(135deg, #ff6b35, #0066ff);
          display: flex; align-items: center; justify-content: center;
          font-size: 12px; font-weight: 700; color: #fff;
          flex-shrink: 0; position: relative;
        }
        .online-indicator {
          width: 9px; height: 9px;
          border-radius: 50%;
          border: 2px solid var(--sidebar-bg);
          position: absolute; bottom: -1px; right: -1px;
        }
        .manager-name { font-size: 12.5px; font-weight: 700; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .manager-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; }
        .toggle-pill {
          display: inline-flex; align-items: center; gap: 4px;
          padding: 3px 7px;
          border-radius: 20px;
          background: #dcfce7; border: 1px solid #bbf7d0;
          cursor: pointer; transition: all 0.2s;
          font-size: 10px; font-weight: 600; color: #16a34a;
          white-space: nowrap; align-self: flex-start;
        }
        .toggle-pill.offline { background: #f1f5f9; border-color: var(--border); color: var(--text-muted); }
        .toggle-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
        .logout-btn {
          width: 30px; height: 30px; border-radius: 8px; flex-shrink: 0;
          background: var(--bg); border: 1px solid var(--border);
          display: flex; align-items: center; justify-content: center;
          cursor: pointer; color: var(--text-muted); transition: all 0.15s;
        }
        .logout-btn:hover { background: #fef2f2; border-color: #fecaca; color: #dc2626; }
      `}</style>
    </aside>
  );
}
