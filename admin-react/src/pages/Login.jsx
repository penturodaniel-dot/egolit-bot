import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { login } from '../api.js';
import { useAuth } from '../App.jsx';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();

  const from = location.state?.from?.pathname || '/chats';

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Введіть логін та пароль');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const data = await login(username, password);
      setUser(data?.user || { username });
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.status === 401 ? 'Невірний логін або пароль' : 'Помилка входу. Спробуйте знову.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-root">
      {/* Left panel — coral gradient brand panel */}
      <div className="login-left">
        <div className="login-brand">
          <div className="login-logo-icon">E</div>
          <div className="login-brand-text">
            <span className="login-brand-name">Ego<span>list</span></span>
            <span className="login-brand-sub">CRM · Дніпро</span>
          </div>
        </div>
        <div className="login-hero">
          <div className="login-hero-title">Управляйте<br />клієнтами<br />легко</div>
          <div className="login-hero-desc">Повноцінна CRM для вашого Telegram-бота: чати, заявки, аналітика та контент в одному місці.</div>
        </div>
        <div className="login-features">
          {['💬 CRM-чати в реальному часі', '📋 Управління заявками', '📊 Аналітика та звіти', '🤖 AI-асистент'].map((f) => (
            <div key={f} className="login-feature-item">{f}</div>
          ))}
        </div>
      </div>

      {/* Right panel — white login form */}
      <div className="login-right">
        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-form-header">
            <h1 className="login-form-title">Вхід в систему</h1>
            <p className="login-form-sub">Введіть дані для доступу до адмін-панелі</p>
          </div>

          {error && (
            <div className="login-error">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Логін</label>
            <input
              className="form-input"
              type="text"
              placeholder="admin"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Пароль</label>
            <input
              className="form-input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="login-submit" disabled={loading}>
            {loading ? (
              <><div className="spinner" style={{ width: 18, height: 18, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Вхід...</>
            ) : 'Увійти в панель'}
          </button>

          <div className="login-footer-text">
            Egolist CRM · Дніпро, Україна
          </div>
        </form>
      </div>

      <style>{`
        .login-root {
          display: flex;
          height: 100vh;
          overflow: hidden;
        }
        .login-left {
          width: 45%;
          background: linear-gradient(135deg, #ff6b35 0%, #ff4500 50%, #cc3300 100%);
          display: flex;
          flex-direction: column;
          padding: 48px 44px;
          color: #fff;
          position: relative;
          overflow: hidden;
        }
        .login-left::before {
          content: '';
          position: absolute;
          top: -60px; right: -60px;
          width: 280px; height: 280px;
          border-radius: 50%;
          background: rgba(255,255,255,0.07);
        }
        .login-left::after {
          content: '';
          position: absolute;
          bottom: -80px; left: -40px;
          width: 320px; height: 320px;
          border-radius: 50%;
          background: rgba(0,0,0,0.08);
        }
        .login-brand {
          display: flex; align-items: center; gap: 14px;
          position: relative; z-index: 1;
        }
        .login-logo-icon {
          width: 46px; height: 46px;
          border-radius: 14px;
          background: rgba(255,255,255,0.2);
          border: 2px solid rgba(255,255,255,0.3);
          display: flex; align-items: center; justify-content: center;
          font-size: 22px; font-weight: 900; color: #fff;
        }
        .login-brand-text { display: flex; flex-direction: column; }
        .login-brand-name { font-size: 22px; font-weight: 800; color: #fff; letter-spacing: -0.02em; }
        .login-brand-name span { opacity: 0.85; }
        .login-brand-sub { font-size: 12px; opacity: 0.7; }
        .login-hero {
          flex: 1;
          display: flex; flex-direction: column; justify-content: center;
          position: relative; z-index: 1;
        }
        .login-hero-title {
          font-size: 38px; font-weight: 800; line-height: 1.15;
          letter-spacing: -0.02em; margin-bottom: 18px;
        }
        .login-hero-desc { font-size: 15px; opacity: 0.82; line-height: 1.65; max-width: 340px; }
        .login-features {
          display: flex; flex-direction: column; gap: 10px;
          position: relative; z-index: 1;
        }
        .login-feature-item {
          font-size: 13.5px; opacity: 0.9; font-weight: 500;
          display: flex; align-items: center; gap: 8px;
        }
        .login-right {
          flex: 1;
          background: #fff;
          display: flex; align-items: center; justify-content: center;
          padding: 40px;
        }
        .login-form {
          width: 100%; max-width: 400px;
          display: flex; flex-direction: column; gap: 20px;
        }
        .login-form-header { text-align: center; margin-bottom: 8px; }
        .login-form-title { font-size: 26px; font-weight: 800; color: var(--text-primary); margin-bottom: 8px; }
        .login-form-sub { font-size: 14px; color: var(--text-secondary); }
        .login-error {
          display: flex; align-items: center; gap: 8px;
          padding: 12px 14px;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: var(--radius-sm);
          color: #dc2626;
          font-size: 13.5px;
          font-weight: 500;
        }
        .form-group { display: flex; flex-direction: column; gap: 7px; }
        .form-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
        .form-input {
          padding: 12px 16px;
          border: 1.5px solid var(--border);
          border-radius: var(--radius-sm);
          font-size: 14px;
          color: var(--text-primary);
          background: var(--bg);
          outline: none;
          transition: all 0.15s;
        }
        .form-input:focus {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
          background: #fff;
        }
        .form-input::placeholder { color: var(--text-muted); }
        .login-submit {
          display: flex; align-items: center; justify-content: center; gap: 8px;
          width: 100%;
          padding: 14px;
          background: linear-gradient(135deg, #ff6b35, #ff4500);
          color: #fff;
          border: none;
          border-radius: var(--radius-sm);
          font-size: 15px; font-weight: 700;
          cursor: pointer;
          transition: all 0.15s;
          box-shadow: 0 4px 16px rgba(255,107,53,0.35);
          margin-top: 4px;
        }
        .login-submit:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 6px 20px rgba(255,107,53,0.42);
        }
        .login-submit:disabled { opacity: 0.7; cursor: not-allowed; }
        .login-footer-text {
          text-align: center;
          font-size: 12px;
          color: var(--text-muted);
          margin-top: 8px;
        }
      `}</style>
    </div>
  );
}
