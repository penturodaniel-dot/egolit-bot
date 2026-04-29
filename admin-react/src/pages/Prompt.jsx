import { useState, useEffect } from 'react';
import { getPrompt, savePrompt } from '../api.js';
import Header from '../components/Header.jsx';

export default function Prompt() {
  const [extra, setExtra] = useState('');
  const [keywordMap, setKeywordMap] = useState('');
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
        setKeywordMap(data.keyword_map || '');
      })
      .catch(() => setError('Помилка завантаження промту'))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError('');
    try {
      await savePrompt(extra, keywordMap);
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

          {error && (
            <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>
          )}

          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
              <div className="spinner" style={{ width: 28, height: 28 }} />
            </div>
          ) : (
            <>
              {/* Extra instructions */}
              <div className="card" style={{ padding: '20px 24px', marginBottom: 24 }}>
                <div className="section-title">Додаткові інструкції для AI</div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 14, lineHeight: 1.6 }}>
                  Правила поведінки бота: як класифікувати запити, що відповідати, які уточнення просити.
                  Зміни застосовуються одразу без перезапуску.
                </p>
                <textarea
                  className="prompt-textarea"
                  value={extra}
                  onChange={(e) => setExtra(e.target.value)}
                  placeholder="Наприклад: Завжди пропонуй знижку 10% на перший захід..."
                  rows={14}
                />
              </div>

              {/* Keyword → category map */}
              <div className="card" style={{ padding: '20px 24px', marginBottom: 24 }}>
                <div className="section-title">Словник ключових слів → категорія</div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.6 }}>
                  Гарантований переклад слів запиту в категорію виконавців — не залежить від AI.
                  Формат: <code style={{ background: 'var(--bg)', padding: '2px 6px', borderRadius: 4, fontSize: 12 }}>слово1, слово2 → категорія</code>
                </p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 14, lineHeight: 1.6 }}>
                  Рядки з # — коментарі. Одне правило = один рядок. Можна писати рос. та укр. слова.
                </p>
                <textarea
                  className="prompt-textarea"
                  value={keywordMap}
                  onChange={(e) => setKeywordMap(e.target.value)}
                  placeholder={'ведущий, тамада → ведучі\nфотограф → фото та відеозйомка\nаниматор, клоун → аніматори'}
                  rows={12}
                  style={{ fontFamily: 'Courier New, monospace', fontSize: 13 }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12 }}>
                {saved && (
                  <span style={{ color: 'var(--online)', fontSize: 13, fontWeight: 600 }}>
                    ✓ Збережено
                  </span>
                )}
                <button className="btn-primary" onClick={handleSave} disabled={saving}>
                  {saving ? 'Збереження...' : 'Зберегти'}
                </button>
              </div>
            </>
          )}
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
          transition: border-color 0.15s; box-sizing: border-box;
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
