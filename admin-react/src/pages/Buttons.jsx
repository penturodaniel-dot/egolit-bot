import { useState, useEffect } from 'react';
import { getButtons, createButton, updateButton, deleteButton, toggleButton } from '../api.js';
import Header from '../components/Header.jsx';

const ACTION_TYPES = [
  { value: 'ai_search',     label: '🤖 AI пошук' },
  { value: 'direct_search', label: '🎯 Прямий пошук (JSON)' },
  { value: 'submenu',       label: '📂 Підменю' },
  { value: 'lead_form',     label: '📋 Форма заявки' },
  { value: 'custom_query',  label: '✍️ Свій запит' },
  { value: 'manager',       label: '📞 Менеджер' },
  { value: 'text',          label: '💬 Текст' },
  { value: 'url',           label: '🔗 URL' },
];

const EMPTY_FORM = {
  label: '', emoji: '', action_type: 'ai_search', ai_prompt: '',
  parent_id: '', position: 0, direct_params: '',
};

export default function Buttons() {
  const [buttons, setButtons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getButtons();
      setButtons(data);
    } catch {
      setError('Помилка завантаження кнопок');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const rootButtons = buttons.filter((b) => b.parent_id == null);
  const childrenOf = (pid) => buttons.filter((b) => b.parent_id === pid);

  const openAdd = (parentId = null) => {
    setForm({ ...EMPTY_FORM, parent_id: parentId ?? '' });
    setEditingId(null);
    setShowModal(true);
  };

  const openEdit = (btn) => {
    setForm({
      label: btn.label || '',
      emoji: btn.emoji || '',
      action_type: btn.action_type || 'ai_search',
      ai_prompt: btn.ai_prompt || '',
      parent_id: btn.parent_id ?? '',
      position: btn.position ?? 0,
      direct_params: btn.direct_params || '',
    });
    setEditingId(btn.id);
    setShowModal(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.label.trim()) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        parent_id: form.parent_id !== '' ? Number(form.parent_id) : null,
        position: Number(form.position) || 0,
        direct_params: form.direct_params.trim() || null,
      };
      if (editingId) {
        await updateButton(editingId, payload);
      } else {
        await createButton(payload);
      }
      setShowModal(false);
      await load();
    } catch {
      alert('Помилка збереження');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (id) => {
    try {
      await toggleButton(id);
      setButtons((prev) => prev.map((b) => b.id === id ? { ...b, is_active: !b.is_active } : b));
    } catch {}
  };

  const handleDelete = async (id, label) => {
    if (!confirm(`Видалити кнопку "${label}"?`)) return;
    try {
      await deleteButton(id);
      setButtons((prev) => prev.filter((b) => b.id !== id));
    } catch {
      alert('Помилка видалення');
    }
  };

  const f = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  // Build label map for parent_id selector
  const buttonLabelMap = {};
  buttons.forEach((b) => { buttonLabelMap[b.id] = `${b.emoji ? b.emoji + ' ' : ''}${b.label} (#${b.id})`; });

  return (
    <div className="page-wrap">
      <Header title="Кнопки меню" subtitle="Динамічне меню бота" />
      <div className="page-content">
        {error && <div style={{ color: '#dc2626', marginBottom: 12 }}>{error}</div>}

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            Кнопки відображаються в меню Telegram-бота
          </div>
          <button className="btn-primary" onClick={() => openAdd(null)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Додати кнопку
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>Завантаження...</div>
        ) : rootButtons.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '48px 32px' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔘</div>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Кнопок поки немає</div>
            <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 20 }}>
              Додайте першу кнопку — вона з'явиться в меню Telegram-бота
            </p>
            <button className="btn-primary" onClick={() => openAdd(null)}>Додати першу кнопку</button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {rootButtons.map((btn) => (
              <div key={btn.id}>
                <ButtonRow
                  btn={btn}
                  onEdit={openEdit}
                  onToggle={handleToggle}
                  onDelete={handleDelete}
                  onAddChild={() => openAdd(btn.id)}
                />
                {childrenOf(btn.id).map((child) => (
                  <div key={child.id} style={{ marginLeft: 32, marginTop: 6 }}>
                    <ButtonRow
                      btn={child}
                      onEdit={openEdit}
                      onToggle={handleToggle}
                      onDelete={handleDelete}
                      onAddChild={() => openAdd(child.id)}
                      isChild
                    />
                    {childrenOf(child.id).map((grandchild) => (
                      <div key={grandchild.id} style={{ marginLeft: 32, marginTop: 6 }}>
                        <ButtonRow
                          btn={grandchild}
                          onEdit={openEdit}
                          onToggle={handleToggle}
                          onDelete={handleDelete}
                          isChild
                          level={3}
                        />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h3>{editingId ? 'Редагувати кнопку' : 'Нова кнопка'}</h3>
              <button className="modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: '20px 24px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '64px 1fr', gap: 10 }}>
                <div>
                  <label className="field-label">Емодзі</label>
                  <input className="field-input" value={form.emoji} onChange={f('emoji')} placeholder="🔘" maxLength={4} />
                </div>
                <div>
                  <label className="field-label">Текст кнопки *</label>
                  <input className="field-input" value={form.label} onChange={f('label')} placeholder="Фотограф" required />
                </div>
              </div>

              <div>
                <label className="field-label">Тип дії</label>
                <select className="field-input" value={form.action_type} onChange={f('action_type')}>
                  {ACTION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>

              {form.action_type === 'ai_search' && (
                <div>
                  <label className="field-label">AI промт (запит для пошуку)</label>
                  <input className="field-input" value={form.ai_prompt} onChange={f('ai_prompt')} placeholder="Знайди фотографів для весілля" />
                </div>
              )}

              {form.action_type === 'direct_search' && (
                <div>
                  <label className="field-label">Параметри пошуку (JSON)</label>
                  <textarea
                    className="field-input"
                    value={form.direct_params}
                    onChange={f('direct_params')}
                    rows={4}
                    placeholder={'{"intent":"event","category":"кіно","date_filter":"today"}'}
                    style={{ fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
                  />
                  <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 5, lineHeight: 1.6 }}>
                    <strong>Приклади:</strong><br />
                    <code style={{ background: 'var(--bg)', padding: '1px 4px', borderRadius: 3 }}>
                      {'{"intent":"event","category":"кіно","date_filter":"today"}'}
                    </code><br />
                    <code style={{ background: 'var(--bg)', padding: '1px 4px', borderRadius: 3 }}>
                      {'{"intent":"event","date_filter":"weekend"}'}
                    </code><br />
                    <code style={{ background: 'var(--bg)', padding: '1px 4px', borderRadius: 3 }}>
                      {'{"intent":"service","categories":["ресторани та банкетні зали"]}'}
                    </code><br />
                    <span style={{ color: 'var(--text-secondary)' }}>
                      intent: "event" | "service" &nbsp;·&nbsp;
                      date_filter: "today" | "weekend" | "week" | "month" | null
                    </span>
                  </div>
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 80px', gap: 10 }}>
                <div>
                  <label className="field-label">Батьківська кнопка</label>
                  <select
                    className="field-input"
                    value={form.parent_id}
                    onChange={f('parent_id')}
                  >
                    <option value="">— Немає (корінь) —</option>
                    {buttons.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.emoji ? b.emoji + ' ' : ''}{b.label} (#{b.id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="field-label">Позиція</label>
                  <input className="field-input" value={form.position} onChange={f('position')} type="number" min="0" />
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 4 }}>
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>Скасувати</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? 'Збереження...' : editingId ? 'Зберегти' : 'Додати'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <style>{`
        .field-label { display: block; font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 5px; }
        .field-input { width: 100%; padding: 9px 12px; border: 1.5px solid var(--border); border-radius: var(--radius-sm); font-size: 13.5px; color: var(--text-primary); background: var(--bg); outline: none; box-sizing: border-box; }
        .field-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(255,107,53,.1); background: #fff; }
        .btn-row { display: flex; align-items: center; background: #fff; border-radius: var(--radius-sm); padding: 12px 16px; border: 1px solid var(--border); gap: 12px; }
        .btn-row-inactive { opacity: 0.55; }
        .btn-label { flex: 1; font-size: 14px; font-weight: 600; color: var(--text-primary); }
        .btn-type { font-size: 11.5px; color: var(--text-muted); background: var(--bg); border-radius: 4px; padding: 2px 7px; }
        .btn-type-direct { font-size: 11.5px; color: #fff; background: #7c3aed; border-radius: 4px; padding: 2px 7px; }
        .btn-type-submenu { font-size: 11.5px; color: #fff; background: #0284c7; border-radius: 4px; padding: 2px 7px; }
        .btn-action-sm { padding: 5px 11px; border: 1.5px solid var(--border); border-radius: 6px; font-size: 12px; cursor: pointer; background: #fff; color: var(--text-secondary); transition: all .15s; }
        .btn-action-sm:hover { border-color: var(--accent); color: var(--accent); }
        .btn-action-sm.danger:hover { border-color: #dc2626; color: #dc2626; }
        .toggle-pill { width: 38px; height: 22px; border-radius: 11px; border: none; cursor: pointer; transition: background .2s; flex-shrink: 0; position: relative; }
        .toggle-pill::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform .2s; }
        .toggle-on { background: var(--accent); }
        .toggle-on::after { transform: translateX(16px); }
        .toggle-off { background: #d1d5db; }
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 100; display: flex; align-items: center; justify-content: center; }
        .modal-box { background: #fff; border-radius: var(--radius); box-shadow: 0 20px 60px rgba(0,0,0,.18); width: 90%; max-width: 500px; max-height: 90vh; overflow-y: auto; }
        .modal-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px 0; }
        .modal-header h3 { font-size: 17px; font-weight: 700; }
        .modal-close { background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-muted); padding: 4px 8px; border-radius: 6px; }
        .modal-close:hover { background: var(--bg); }
      `}</style>
    </div>
  );
}

function ButtonRow({ btn, onEdit, onToggle, onDelete, onAddChild, isChild, level }) {
  const actionType = ACTION_TYPES.find((t) => t.value === btn.action_type);
  const badgeClass =
    btn.action_type === 'direct_search' ? 'btn-type-direct' :
    btn.action_type === 'submenu' ? 'btn-type-submenu' :
    'btn-type';
  const badgeLabel = actionType?.label || btn.action_type;

  return (
    <div className={`btn-row${btn.is_active ? '' : ' btn-row-inactive'}`}>
      <button
        className={`toggle-pill ${btn.is_active ? 'toggle-on' : 'toggle-off'}`}
        onClick={() => onToggle(btn.id)}
        title={btn.is_active ? 'Активна' : 'Вимкнена'}
      />
      <span className="btn-label">
        {btn.emoji && <span style={{ marginRight: 6 }}>{btn.emoji}</span>}
        {btn.label}
        {isChild && level === 3 && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>↳↳ рівень 3</span>}
        {isChild && !level && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>↳ підкнопка</span>}
      </span>
      <span className={badgeClass}>{badgeLabel}</span>
      <span style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>#{btn.id} · pos {btn.position}</span>
      {onAddChild && (
        <button className="btn-action-sm" onClick={onAddChild} title="Додати підкнопку">+ суб</button>
      )}
      <button className="btn-action-sm" onClick={() => onEdit(btn)}>✏️ Ред.</button>
      <button className="btn-action-sm danger" onClick={() => onDelete(btn.id, btn.label)}>🗑</button>
    </div>
  );
}
