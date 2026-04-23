import { useState, useEffect } from 'react';
import { getSettings, saveSettings, testNotification } from '../api.js';
import Header from '../components/Header.jsx';

export default function Settings() {
  const [chatId, setChatId] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testResult, setTestResult] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    getSettings()
      .then((data) => {
        setChatId(data.notification_chat_id || '');
        setEnabled(data.notification_enabled !== false);
      })
      .catch(() => setError('Помилка завантаження налаштувань'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      await saveSettings({
        notification_chat_id: chatId,
        notification_enabled: enabled,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult('');
    try {
      await testNotification();
      setTestResult('success');
    } catch {
      setTestResult('error');
    } finally {
      setTesting(false);
      setTimeout(() => setTestResult(''), 4000);
    }
  };

  return (
    <div className="page-wrap">
      <Header title="Налаштування" subtitle="Settings" />
      <div className="page-content">
        <div style={{ maxWidth: 600 }}>
          <div className="card" style={{ padding: '24px' }}>
            <div className="settings-section-title">Сповіщення в Telegram</div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 22, lineHeight: 1.6 }}>
              При отриманні нової заявки бот надішле сповіщення в зазначений чат.
            </p>

            {error && (
              <div className="error-msg" style={{ marginBottom: 20 }}>{error}</div>
            )}

            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <div className="spinner" style={{ width: 28, height: 28 }} />
              </div>
            ) : (
              <>
                {/* Notification enabled toggle */}
                <div className="settings-row">
                  <div>
                    <div className="settings-row-title">Сповіщення увімкнені</div>
                    <div className="settings-row-sub">Надсилати сповіщення менеджеру про нові заявки</div>
                  </div>
                  <button
                    className={`big-toggle${enabled ? ' big-toggle-on' : ''}`}
                    onClick={() => setEnabled((v) => !v)}
                    type="button"
                  >
                    <div className="big-toggle-thumb" />
                  </button>
                </div>

                <div className="settings-divider" />

                {/* Chat ID input */}
                <div className="settings-field-group">
                  <label className="settings-label">Telegram Chat ID</label>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>
                    ID чату або каналу, куди надсилати сповіщення. Можна знайти через @userinfobot
                  </div>
                  <input
                    className="settings-input"
                    type="text"
                    placeholder="-1001234567890"
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                  />
                </div>

                {/* Actions */}
                <div className="settings-actions">
                  <button
                    className="btn-secondary"
                    onClick={handleTest}
                    disabled={testing || !chatId}
                    title={!chatId ? 'Спочатку введіть Chat ID' : ''}
                  >
                    {testing ? 'Відправлення...' : '🔔 Тест сповіщення'}
                  </button>
                  {testResult === 'success' && (
                    <span className="settings-feedback success">✓ Сповіщення надіслано!</span>
                  )}
                  {testResult === 'error' && (
                    <span className="settings-feedback error">✕ Помилка відправки</span>
                  )}
                  <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
                    {saved && (
                      <span className="settings-feedback success">✓ Збережено</span>
                    )}
                    <button className="btn-primary" onClick={handleSave} disabled={saving}>
                      {saving ? 'Збереження...' : 'Зберегти'}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Info card */}
          <div className="card" style={{ padding: '20px 24px', marginTop: 20, background: 'var(--accent2-light)', border: '1px solid rgba(0,102,255,0.15)' }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <span style={{ fontSize: 20, flexShrink: 0 }}>ℹ️</span>
              <div>
                <div style={{ fontSize: 13.5, fontWeight: 700, color: 'var(--accent2)', marginBottom: 6 }}>
                  Як отримати Chat ID
                </div>
                <ol style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, paddingLeft: 18 }}>
                  <li>Напишіть в Telegram боту <strong>@userinfobot</strong></li>
                  <li>Він покаже ваш User ID — вставте його вище</li>
                  <li>Для груп або каналів — додайте бота в чат і напишіть там</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .settings-section-title { font-size: 16px; font-weight: 800; color: var(--text-primary); margin-bottom: 8px; }
        .settings-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 4px 0; }
        .settings-row-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }
        .settings-row-sub { font-size: 12.5px; color: var(--text-muted); margin-top: 3px; }
        .big-toggle {
          width: 46px; height: 26px; border-radius: 13px;
          background: var(--border); border: none; cursor: pointer;
          position: relative; transition: background 0.2s;
          flex-shrink: 0;
        }
        .big-toggle-on { background: var(--online); }
        .big-toggle-thumb {
          position: absolute; top: 3px; left: 3px;
          width: 20px; height: 20px; border-radius: 50%;
          background: #fff; transition: transform 0.2s;
          box-shadow: 0 1px 4px rgba(0,0,0,0.2);
        }
        .big-toggle-on .big-toggle-thumb { transform: translateX(20px); }
        .settings-divider { height: 1px; background: var(--border); margin: 20px 0; }
        .settings-field-group { margin-bottom: 20px; }
        .settings-label { display: block; font-size: 13px; font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; }
        .settings-input {
          width: 100%; padding: 11px 14px;
          border: 1.5px solid var(--border);
          border-radius: var(--radius-sm);
          font-size: 14px; font-family: var(--font);
          color: var(--text-primary); background: var(--bg);
          outline: none; transition: all 0.15s;
        }
        .settings-input:focus {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
        }
        .settings-actions { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
        .settings-feedback { font-size: 13px; font-weight: 600; }
        .settings-feedback.success { color: var(--online); }
        .settings-feedback.error { color: var(--danger); }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }
      `}</style>
    </div>
  );
}
