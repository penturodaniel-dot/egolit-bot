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

// ── Documentation data ────────────────────────────────────────────────────

const ACTION_DOCS = [
  { value: 'submenu',       icon: '📂', label: 'Підменю',               desc: 'Відкриває дочірні кнопки — будь-яка кількість рівнів. Дочірні кнопки додаються через "Батьківська кнопка" або кнопку "+ суб".' },
  { value: 'direct_search', icon: '🎯', label: 'Прямий пошук (JSON)',   desc: 'Виконує пошук відразу без AI. Параметри задаються у полі JSON нижче. Підтримує ask_date для інтерактивного вибору дати.' },
  { value: 'ai_search',     icon: '🤖', label: 'AI пошук',              desc: 'Передає AI-промт у движок. AI сам визначає категорію, дату, тип. Використовується рідко — краще direct_search.' },
  { value: 'custom_query',  icon: '✍️', label: 'Свій запит',            desc: 'Просить користувача ввести довільний текст, потім шукає через AI. Аналог вільного введення тексту.' },
  { value: 'lead_form',     icon: '📋', label: 'Форма заявки',          desc: 'Запускає 7-крокову форму: ім\'я → телефон → категорія → бюджет → дата → кількість людей → деталі. Заявка зберігається в CRM.' },
  { value: 'manager',       icon: '📞', label: 'Менеджер',              desc: 'Показує вибір: Залишити заявку або Живий чат. Не потребує налаштувань.' },
  { value: 'text',          icon: '💬', label: 'Текст',                 desc: 'Просто відправляє текстове повідомлення. (Поки не реалізовано — резерв)' },
  { value: 'url',           icon: '🔗', label: 'URL',                   desc: 'Відкриває посилання. (Поки не реалізовано — резерв)' },
];

const EVENT_CATEGORIES = [
  'концерти', 'театр', 'стендап', 'для дітей', 'фестивалі',
  'виставки', 'кіно', 'активний відпочинок', 'майстер-класи', 'спорт', 'клуби', 'інше',
];

const SERVICE_CATEGORIES = [
  'ведучі', 'музиканти', 'фото та відеозйомка', 'аніматори', 'артисти та шоу',
  'кейтеринг та бар', 'оформлення та декор', 'організатори заходів',
  'візажисти та зачіски', 'кондитери', 'танцювальні шоу', 'актори', 'хостес',
  'персонал для заходів', 'майстер-класи', 'блогери', 'перекладачі',
  'ресторани та банкетні зали', 'розважальні заклади', 'готелі та комплекси',
  'квест-кімнати', 'нічні клуби та караоке', 'фото та відеостудії',
  'конференц-зали', 'бази відпочинку', 'місця для весільних церемоній',
  'івент-простори', 'альтанки та бесідки', 'культурні локації',
  'звукове обладнання', 'світлове обладнання', 'конструкції та сцени',
  'спецефекти', 'декор і фотозони', 'проектори та екрани',
  'меблі для заходів', 'фото-відеообладнання', 'прокат інвентарю',
];

const JSON_EXAMPLES = [
  {
    title: 'Концерти на вихідні',
    json: `{\n  "intent": "event",\n  "category": "концерти",\n  "date_filter": "weekend"\n}`,
  },
  {
    title: 'Кіно сьогодні',
    json: `{\n  "intent": "event",\n  "category": "кіно",\n  "date_filter": "today"\n}`,
  },
  {
    title: 'Всі події (вибір дати користувачем)',
    json: `{\n  "intent": "event",\n  "ask_date": true\n}`,
  },
  {
    title: 'Театр цього тижня',
    json: `{\n  "intent": "event",\n  "category": "театр",\n  "date_filter": "week"\n}`,
  },
  {
    title: 'Для дітей (вибір дати)',
    json: `{\n  "intent": "event",\n  "category": "для дітей",\n  "ask_date": true\n}`,
  },
  {
    title: 'Фотографи',
    json: `{\n  "intent": "service",\n  "categories": ["фото та відеозйомка"]\n}`,
  },
  {
    title: 'Ресторани',
    json: `{\n  "intent": "service",\n  "categories": ["ресторани та банкетні зали"]\n}`,
  },
  {
    title: 'Аніматори у Дніпрі',
    json: `{\n  "intent": "service",\n  "categories": ["аніматори"],\n  "city": "Дніпро"\n}`,
  },
  {
    title: 'Ведучі + Музиканти (весілля)',
    json: `{\n  "intent": "service",\n  "categories": [\n    "ведучі",\n    "музиканти"\n  ]\n}`,
  },
];

// ── Documentation panel ───────────────────────────────────────────────────

function DocsPanel() {
  const [open, setOpen] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState(null);

  const copyJson = (text, idx) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    });
  };

  return (
    <div style={{ marginBottom: 20, border: '1.5px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 10,
          padding: '13px 18px', background: open ? '#f8fafc' : '#fff',
          border: 'none', cursor: 'pointer', textAlign: 'left',
          borderBottom: open ? '1.5px solid #e2e8f0' : 'none',
        }}
      >
        <span style={{ fontSize: 17 }}>📖</span>
        <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)' }}>Документація — як налаштовувати кнопки</span>
        <span style={{ marginLeft: 'auto', fontSize: 13, color: 'var(--text-muted)', transition: 'transform .2s', display: 'inline-block', transform: open ? 'rotate(180deg)' : 'none' }}>▼</span>
      </button>

      {open && (
        <div style={{ padding: '20px 22px', background: '#fff', display: 'flex', flexDirection: 'column', gap: 28 }}>

          {/* ── Структура меню ── */}
          <section>
            <h4 style={SH}>🗂 Структура меню (рівні)</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 10 }}>
              {[
                { lvl: 'Рівень 1 — корінь', desc: 'Батьківська кнопка = немає. Відображається в головному меню Telegram. Тип: submenu (щоб розкрити), або будь-яка дія.', color: '#0284c7' },
                { lvl: 'Рівень 2 — підменю', desc: 'Батьківська кнопка = кнопка рівня 1. Відображається після натискання батьківської. Тип: submenu або дія.', color: '#7c3aed' },
                { lvl: 'Рівень 3 — листя', desc: 'Батьківська кнопка = кнопка рівня 2. Кінцева дія — direct_search, lead_form, manager тощо. Підменю 4-го рівня не підтримується.', color: '#059669' },
              ].map((item) => (
                <div key={item.lvl} style={{ padding: '12px 14px', borderRadius: 8, border: `2px solid ${item.color}20`, background: `${item.color}08` }}>
                  <div style={{ fontWeight: 700, fontSize: 12.5, color: item.color, marginBottom: 5 }}>{item.lvl}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{item.desc}</div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Типи дій ── */}
          <section>
            <h4 style={SH}>⚡ Типи дій</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7, marginTop: 10 }}>
              {ACTION_DOCS.map((a) => (
                <div key={a.value} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '9px 12px', borderRadius: 7, background: '#f8fafc', border: '1px solid #e2e8f0' }}>
                  <span style={{ fontSize: 15, flexShrink: 0, marginTop: 1 }}>{a.icon}</span>
                  <div>
                    <span style={{ fontWeight: 700, fontSize: 12.5, color: 'var(--text-primary)' }}>{a.label}</span>
                    <code style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8, background: '#e2e8f0', padding: '1px 5px', borderRadius: 3 }}>{a.value}</code>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 3, lineHeight: 1.5 }}>{a.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── JSON параметри direct_search ── */}
          <section>
            <h4 style={SH}>🎯 JSON параметри для direct_search</h4>
            <div style={{ marginTop: 10, overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                <thead>
                  <tr style={{ background: '#f1f5f9' }}>
                    {['Поле', 'Тип', 'Значення', 'Опис'].map((h) => (
                      <th key={h} style={{ padding: '8px 12px', textAlign: 'left', fontWeight: 700, color: 'var(--text-secondary)', borderBottom: '1.5px solid #e2e8f0' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { field: 'intent', type: 'string', vals: '"event" | "service"', desc: 'Тип пошуку: event — афіша, service — виконавці/локації' },
                    { field: 'category', type: 'string', vals: 'назва категорії', desc: 'Категорія для intent=event. Один рядок (ILIKE пошук)' },
                    { field: 'categories', type: 'array', vals: '["кат1","кат2"]', desc: 'Категорії для intent=service. Масив рядків' },
                    { field: 'date_filter', type: 'string', vals: '"today"|"weekend"|"week"|"month"|null', desc: 'Фіксована дата для intent=event. null = всі майбутні події' },
                    { field: 'ask_date', type: 'boolean', vals: 'true | false', desc: 'Якщо true — показує клавіатуру вибору дати перед пошуком. Не використовувати разом з date_filter' },
                    { field: 'city', type: 'string', vals: '"Дніпро"', desc: 'Фільтр по місту (ILIKE). Залиш порожнім — всі міста' },
                    { field: 'search_text', type: 'string', vals: 'будь-який рядок', desc: 'Текстовий пошук по назві/опису (ILIKE). Для вузького пошуку' },
                  ].map((row, i) => (
                    <tr key={row.field} style={{ background: i % 2 === 0 ? '#fff' : '#f8fafc' }}>
                      <td style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9' }}><code style={{ fontWeight: 700, color: '#7c3aed' }}>{row.field}</code></td>
                      <td style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{row.type}</td>
                      <td style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', fontFamily: 'monospace', fontSize: 11.5, color: '#0284c7' }}>{row.vals}</td>
                      <td style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{row.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── Категорії ── */}
          <section>
            <h4 style={SH}>🗂 Доступні категорії</h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginTop: 10 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: .5 }}>📅 Категорії подій (intent=event)</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {EVENT_CATEGORIES.map((c) => (
                    <span key={c} style={PILL_BLUE}>{c}</span>
                  ))}
                </div>
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--text-secondary)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: .5 }}>👤 Категорії виконавців (intent=service)</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                  {SERVICE_CATEGORIES.map((c) => (
                    <span key={c} style={PILL_PURPLE}>{c}</span>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* ── Приклади JSON ── */}
          <section>
            <h4 style={SH}>📋 Готові приклади JSON</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10, marginTop: 10 }}>
              {JSON_EXAMPLES.map((ex, idx) => (
                <div key={idx} style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 12px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>{ex.title}</span>
                    <button
                      onClick={() => copyJson(ex.json, idx)}
                      style={{ fontSize: 11, padding: '3px 8px', border: '1px solid #cbd5e1', borderRadius: 4, background: '#fff', cursor: 'pointer', color: 'var(--text-secondary)', transition: 'all .15s' }}
                    >
                      {copiedIdx === idx ? '✅ Скопійовано' : '📋 Копіювати'}
                    </button>
                  </div>
                  <pre style={{ margin: 0, padding: '10px 12px', fontSize: 11.5, fontFamily: 'monospace', color: '#334155', background: '#fff', lineHeight: 1.6, overflowX: 'auto' }}>{ex.json}</pre>
                </div>
              ))}
            </div>
          </section>

          {/* ── Швидкий гайд ── */}
          <section>
            <h4 style={SH}>🚀 Як додати нову кнопку — швидкий гайд</h4>
            <ol style={{ margin: '10px 0 0', paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              <li>Натисни <strong>+ Додати кнопку</strong>.</li>
              <li>Введи <strong>Емодзі</strong> і <strong>Текст кнопки</strong> — це те, що побачить користувач у Telegram.</li>
              <li>Вибери <strong>Тип дії</strong>:
                <ul style={{ marginTop: 4, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <li>Хочеш підменю → <strong>📂 Підменю</strong></li>
                  <li>Хочеш шукати без AI → <strong>🎯 Прямий пошук</strong> + вставити JSON з прикладів вище</li>
                  <li>Хочеш форму заявки → <strong>📋 Форма заявки</strong></li>
                  <li>Хочеш підключити менеджера → <strong>📞 Менеджер</strong></li>
                </ul>
              </li>
              <li>Для <strong>дочірніх кнопок</strong>: встанови Батьківська кнопка або натисни <strong>+ суб</strong> прямо на рядку.</li>
              <li><strong>Позиція</strong> — порядок відображення (0 = перша). Менше = вище.</li>
              <li>Перемикач зліва вмикає/вимикає кнопку без видалення.</li>
            </ol>
          </section>

        </div>
      )}
    </div>
  );
}

const SH = { fontSize: 13.5, fontWeight: 700, color: 'var(--text-primary)', margin: 0, paddingBottom: 6, borderBottom: '1.5px solid #f1f5f9' };
const PILL_BLUE = { fontSize: 11.5, background: '#eff6ff', color: '#1d4ed8', padding: '2px 8px', borderRadius: 20, border: '1px solid #bfdbfe' };
const PILL_PURPLE = { fontSize: 11.5, background: '#f5f3ff', color: '#6d28d9', padding: '2px 8px', borderRadius: 20, border: '1px solid #ddd6fe' };

// ── Page component ────────────────────────────────────────────────────────

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

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
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

        <DocsPanel />

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
