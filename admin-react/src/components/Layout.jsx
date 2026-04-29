// Main app shell: sidebar + content area
// Also hosts global polling for urgent live-chat alerts (works on ANY page)
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar.jsx';
import { getSessions } from '../api.js';

// ─── Urgent alert helpers ─────────────────────────────────────────────────────

function playUrgentSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [0, 0.28, 0.56].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.setValueAtTime(1320, ctx.currentTime + delay);
      gain.gain.setValueAtTime(0.4, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + 0.22);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.22);
    });
  } catch {}
}

function sendBrowserNotification(title, body) {
  if (Notification.permission === 'granted') {
    new Notification(title, { body, icon: '/favicon.ico' });
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission();
  }
}

// ─── Layout ───────────────────────────────────────────────────────────────────

export default function Layout({ children }) {
  const navigate = useNavigate();
  const [urgentAlert, setUrgentAlert] = useState(null); // { name, sessionId }

  const prevStatusRef  = useRef({});
  const statusInitRef  = useRef(false);
  const titleBlinkRef  = useRef(null);

  const startTitleBlink = () => {
    if (titleBlinkRef.current) return;
    let on = true;
    titleBlinkRef.current = setInterval(() => {
      document.title = on ? '🔴 НОВИЙ ЧАТ!' : 'Egolist Admin';
      on = !on;
    }, 700);
  };

  const stopTitleBlink = () => {
    if (titleBlinkRef.current) {
      clearInterval(titleBlinkRef.current);
      titleBlinkRef.current = null;
    }
    document.title = 'Egolist Admin';
  };

  // Request browser notification permission on first mount
  useEffect(() => {
    if (Notification && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, []);

  // Global polling — detects ai→human transition on ANY page
  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const data = await getSessions();
        data.forEach((s) => {
          const prevStatus = prevStatusRef.current[s.id];

          // Detect ai → human transition (user clicked "Живий чат")
          if (statusInitRef.current && prevStatus === 'ai' && s.status === 'human') {
            const name = s.first_name
              ? `${s.first_name}${s.last_name ? ' ' + s.last_name : ''}`
              : s.username || `User ${s.user_id}`;
            playUrgentSound();
            sendBrowserNotification('🔴 Запит на живий чат!', `${name} хоче поговорити з менеджером`);
            setUrgentAlert({ name, sessionId: s.id });
            startTitleBlink();
          }
          prevStatusRef.current[s.id] = s.status;
        });
        if (!statusInitRef.current) statusInitRef.current = true;
      } catch {}
    }, 3000);

    return () => clearInterval(poll);
  }, []);

  const dismissAlert = () => { setUrgentAlert(null); stopTitleBlink(); };

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main-wrap">
        {children}
      </div>

      {/* ── Urgent live-chat alert modal ── */}
      {urgentAlert && (
        <div className="gl-urgent-overlay" onClick={dismissAlert}>
          <div className="gl-urgent-modal" onClick={(e) => e.stopPropagation()}>
            <div className="gl-urgent-pulse">🔴</div>
            <div className="gl-urgent-title">Запит на живий чат!</div>
            <div className="gl-urgent-name">{urgentAlert.name}</div>
            <div className="gl-urgent-sub">хоче поговорити з менеджером прямо зараз</div>
            <div className="gl-urgent-actions">
              <button
                className="gl-urgent-btn-go"
                onClick={() => {
                  navigate(`/chats/${urgentAlert.sessionId}`);
                  dismissAlert();
                }}
              >
                💬 Перейти до чату
              </button>
              <button className="gl-urgent-btn-later" onClick={dismissAlert}>
                Пізніше
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .app-shell {
          display: flex;
          height: 100vh;
          overflow: hidden;
        }
        .main-wrap {
          flex: 1;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-width: 0;
        }

        /* Urgent overlay */
        .gl-urgent-overlay {
          position: fixed; inset: 0; z-index: 10000;
          background: rgba(0,0,0,0.55);
          display: flex; align-items: center; justify-content: center;
          backdrop-filter: blur(3px);
          animation: gl-fade-in 0.2s ease;
        }
        .gl-urgent-modal {
          background: #fff; border-radius: 20px;
          padding: 36px 40px; text-align: center;
          box-shadow: 0 24px 60px rgba(0,0,0,0.25), 0 0 0 4px rgba(220,38,38,0.12);
          max-width: 380px; width: 90%;
          animation: gl-modal-in 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        .gl-urgent-pulse {
          font-size: 52px; margin-bottom: 12px; display: block;
          animation: gl-pulse 0.7s ease infinite alternate;
        }
        @keyframes gl-pulse {
          from { transform: scale(1); }
          to   { transform: scale(1.18); }
        }
        .gl-urgent-title {
          font-size: 20px; font-weight: 800; color: #dc2626; margin-bottom: 10px;
        }
        .gl-urgent-name {
          font-size: 18px; font-weight: 700; color: #111827; margin-bottom: 4px;
        }
        .gl-urgent-sub {
          font-size: 13.5px; color: #6b7280; margin-bottom: 24px;
        }
        .gl-urgent-actions { display: flex; flex-direction: column; gap: 10px; }
        .gl-urgent-btn-go {
          padding: 14px 24px; border-radius: 12px;
          background: linear-gradient(135deg, #ff6b35, #ff4500);
          color: #fff; border: none; font-size: 15px; font-weight: 700;
          cursor: pointer; box-shadow: 0 6px 18px rgba(255,107,53,0.45);
          transition: all 0.15s;
        }
        .gl-urgent-btn-go:hover { transform: translateY(-2px); box-shadow: 0 8px 22px rgba(255,107,53,0.5); }
        .gl-urgent-btn-later {
          padding: 10px; border-radius: 10px;
          background: none; border: 1.5px solid #e5e7eb;
          color: #9ca3af; font-size: 13px; cursor: pointer;
          transition: all 0.15s;
        }
        .gl-urgent-btn-later:hover { border-color: #d1d5db; color: #6b7280; }
        @keyframes gl-fade-in { from { opacity: 0; } to { opacity: 1; } }
        @keyframes gl-modal-in {
          from { opacity: 0; transform: scale(0.8); }
          to   { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
