import { useState, useEffect } from 'react';
import { getPrompt, savePrompt } from '../api.js';
import Header from '../components/Header.jsx';

export default function Prompt() {
  const [extra, setExtra] = useState('');
  const [basePrompt, setBasePrompt] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getPrompt()
      .then((data) => {
        setExtra(data.ai_prompt_extra || '');
        setBasePrompt(data.base_prompt || '');
      })
      .catch(() => setError('Помилка завантаження промту'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      await savePrompt(extra);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      setError('Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-wrap">
      <Header title="AI Промт" subtitle="Налаштування" />
      <div className="page-content">
        <div style={{ maxWidth: 800 }}>
          {/* Base prompt (read-only) */}
          {basePrompt && (
            <div className="card" style={{ padding: '20px 24px', marginBottom: 24 }}>
              <div className="section-title">Базовий промт (тільки читання)</div>
              <div className="base-prompt-box">{basePrompt}</div>
            </div>
          )}

          {/* Extra instructions */}
          <div className="card" style={{ padding: '20px 24px' }}>
            <div className="section-title">Додаткові інструкції для AI</div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.6 }}>
              Введіть додаткові правила або контекст, який AI буде враховувати під час відповідей.
              Зміни застосовуються одразу без перезапуску бота.
            </p>

            {error && (
              <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>
            )}

            {loading ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <div className="spinner" style={{ width: 28, height: 28 }} />
              </div>
            ) : (
              <>
                <textarea
                  className="prompt-textarea"
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder="Наприклад: Завжди пропонуй знижку 10% на перший захід. Не розкривай інформацію про конкурентів..."
                  rows={10}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12, marginTop: 16 }}>
                  {saved && (
                    <span style={{ color: 'var(--online)', fontSize: 13, fontWeight: 600 }}>
                      ✓ Збережено
                    </span>
                  )}
                  <button className="btn-primary" onClick={handleSave} disabled={saving}>
                    {saving ? 'Збереження...' : 'Зберегти промт'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .section-title {
          font-size: 14px; font-weight: 700; color: var(--text-primary);
          margin-bottom: 12px;
        }
        .base-prompt-box {
          background: var(--bg); border: 1.5px solid var(--border);
          border-radius: 10px; padding: 14px 16px;
          font-size: 13px; color: var(--text-secondary);
          line-height: 1.7; white-space: pre-wrap;
          max-height: 200px; overflow-y: auto;
          font-family: 'Courier New', monospace;
        }
        .prompt-textarea {
          width: 100%; padding: 14px 16px;
          border: 1.5px solid var(--border);
          border-radius: var(--radius-sm);
          font-size: 13.5px; font-family: var(--font);
          color: var(--text-primary); background: var(--bg);
          outline: none; resize: vertical; line-height: 1.7;
          transition: border-color 0.15s;
        }
        .prompt-textarea:focus {
          border-color: var(--accent);
          box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
        }
        .prompt-textarea::placeholder { color: var(--text-muted); }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }
      `}</style>
    </div>
  );
}
