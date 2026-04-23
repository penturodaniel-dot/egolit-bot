import { useState, useEffect } from 'react';
import {
  getPlaces, createPlace, updatePlace, deletePlace, togglePlace,
  getEvents, createEvent, updateEvent, deleteEvent, toggleEvent,
} from '../api.js';
import Header from '../components/Header.jsx';

// ─── Place form fields ───────────────────────────────────────────────────────
const EMPTY_PLACE = {
  name: '', category: '', description: '',
  district: '', address: '', price_from: '', price_to: '',
  for_who: '', tags: '', phone: '', instagram: '',
  telegram: '', website: '', booking_url: '', photo_url: '',
  city: 'Дніпро', is_published: true, is_featured: false, priority: 0,
};

// ─── Event form fields ────────────────────────────────────────────────────────
const EMPTY_EVENT = {
  title: '', description: '', category: '',
  date: '', time: '', price: '',
  place_name: '', place_address: '', tags: '',
  photo_url: '', ticket_url: '',
  city: 'Дніпро', is_published: true, is_featured: false, priority: 0,
};

// ─── Reusable modal ───────────────────────────────────────────────────────────
function Modal({ title, onClose, children }) {
  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <div className="modal-title">{title}</div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

// ─── Form field helper ────────────────────────────────────────────────────────
function Field({ label, children, half }) {
  return (
    <div className={`form-field${half ? ' form-field-half' : ''}`}>
      <label className="form-label">{label}</label>
      {children}
    </div>
  );
}

// ─── Place Form ───────────────────────────────────────────────────────────────
function PlaceForm({ initial, onSave, onCancel }) {
  const [data, setData] = useState({ ...EMPTY_PLACE, ...initial });
  const [saving, setSaving] = useState(false);

  const set = (k, v) => setData((prev) => ({ ...prev, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try { await onSave(data); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={handleSubmit} className="content-form">
      <div className="form-grid">
        <Field label="Назва *"><input className="form-input" value={data.name} onChange={e => set('name', e.target.value)} required maxLength={200} /></Field>
        <Field label="Категорія"><input className="form-input" value={data.category} onChange={e => set('category', e.target.value)} maxLength={100} /></Field>
        <Field label="Опис" ><textarea className="form-textarea" value={data.description} onChange={e => set('description', e.target.value)} rows={3} /></Field>
        <Field label="Район"><input className="form-input" value={data.district} onChange={e => set('district', e.target.value)} maxLength={100} /></Field>
        <Field label="Адреса"><input className="form-input" value={data.address} onChange={e => set('address', e.target.value)} maxLength={200} /></Field>
        <Field label="Ціна від" half><input className="form-input" type="number" value={data.price_from} onChange={e => set('price_from', e.target.value)} /></Field>
        <Field label="Ціна до" half><input className="form-input" type="number" value={data.price_to} onChange={e => set('price_to', e.target.value)} /></Field>
        <Field label="Для кого"><input className="form-input" value={data.for_who} onChange={e => set('for_who', e.target.value)} maxLength={200} /></Field>
        <Field label="Теги (через кому)"><input className="form-input" value={data.tags} onChange={e => set('tags', e.target.value)} maxLength={300} /></Field>
        <Field label="Телефон"><input className="form-input" value={data.phone} onChange={e => set('phone', e.target.value)} maxLength={50} /></Field>
        <Field label="Instagram"><input className="form-input" value={data.instagram} onChange={e => set('instagram', e.target.value)} maxLength={100} /></Field>
        <Field label="Telegram"><input className="form-input" value={data.telegram} onChange={e => set('telegram', e.target.value)} maxLength={100} /></Field>
        <Field label="Сайт"><input className="form-input" value={data.website} onChange={e => set('website', e.target.value)} maxLength={200} /></Field>
        <Field label="Бронювання URL"><input className="form-input" value={data.booking_url} onChange={e => set('booking_url', e.target.value)} maxLength={300} /></Field>
        <Field label="Фото URL"><input className="form-input" value={data.photo_url} onChange={e => set('photo_url', e.target.value)} maxLength={300} /></Field>
        <Field label="Місто" half><input className="form-input" value={data.city} onChange={e => set('city', e.target.value)} maxLength={100} /></Field>
        <Field label="Пріоритет (0–100)" half><input className="form-input" type="number" min={0} max={100} value={data.priority} onChange={e => set('priority', parseInt(e.target.value) || 0)} /></Field>
        <div className="form-checkboxes">
          <label className="check-label">
            <input type="checkbox" checked={data.is_published} onChange={e => set('is_published', e.target.checked)} />
            Опублікований
          </label>
          <label className="check-label">
            <input type="checkbox" checked={data.is_featured} onChange={e => set('is_featured', e.target.checked)} />
            Рекомендований
          </label>
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Скасувати</button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? 'Збереження...' : 'Зберегти'}
        </button>
      </div>
    </form>
  );
}

// ─── Event Form ───────────────────────────────────────────────────────────────
function EventForm({ initial, onSave, onCancel }) {
  const [data, setData] = useState({ ...EMPTY_EVENT, ...initial });
  const [saving, setSaving] = useState(false);

  const set = (k, v) => setData((prev) => ({ ...prev, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try { await onSave(data); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={handleSubmit} className="content-form">
      <div className="form-grid">
        <Field label="Назва *"><input className="form-input" value={data.title} onChange={e => set('title', e.target.value)} required maxLength={200} /></Field>
        <Field label="Категорія"><input className="form-input" value={data.category} onChange={e => set('category', e.target.value)} maxLength={100} /></Field>
        <Field label="Опис"><textarea className="form-textarea" value={data.description} onChange={e => set('description', e.target.value)} rows={3} /></Field>
        <Field label="Дата" half><input className="form-input" type="date" value={data.date} onChange={e => set('date', e.target.value)} /></Field>
        <Field label="Час" half><input className="form-input" type="time" value={data.time} onChange={e => set('time', e.target.value)} /></Field>
        <Field label="Ціна"><input className="form-input" value={data.price} onChange={e => set('price', e.target.value)} maxLength={100} /></Field>
        <Field label="Майданчик"><input className="form-input" value={data.place_name} onChange={e => set('place_name', e.target.value)} maxLength={200} /></Field>
        <Field label="Адреса майданчика"><input className="form-input" value={data.place_address} onChange={e => set('place_address', e.target.value)} maxLength={200} /></Field>
        <Field label="Теги (через кому)"><input className="form-input" value={data.tags} onChange={e => set('tags', e.target.value)} maxLength={300} /></Field>
        <Field label="Фото URL"><input className="form-input" value={data.photo_url} onChange={e => set('photo_url', e.target.value)} maxLength={300} /></Field>
        <Field label="Квитки URL"><input className="form-input" value={data.ticket_url} onChange={e => set('ticket_url', e.target.value)} maxLength={300} /></Field>
        <Field label="Місто" half><input className="form-input" value={data.city} onChange={e => set('city', e.target.value)} maxLength={100} /></Field>
        <Field label="Пріоритет (0–100)" half><input className="form-input" type="number" min={0} max={100} value={data.priority} onChange={e => set('priority', parseInt(e.target.value) || 0)} /></Field>
        <div className="form-checkboxes">
          <label className="check-label">
            <input type="checkbox" checked={data.is_published} onChange={e => set('is_published', e.target.checked)} />
            Опублікований
          </label>
          <label className="check-label">
            <input type="checkbox" checked={data.is_featured} onChange={e => set('is_featured', e.target.checked)} />
            Рекомендований
          </label>
        </div>
      </div>
      <div className="form-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Скасувати</button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? 'Збереження...' : 'Зберегти'}
        </button>
      </div>
    </form>
  );
}

// ─── Content table row ────────────────────────────────────────────────────────
function ContentRow({ item, type, onEdit, onDelete, onToggle }) {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    await onToggle(item.id, !item.is_published);
    setToggling(false);
  };

  const handleDelete = async () => {
    if (!confirm(`Видалити "${item.name || item.title}"?`)) return;
    setDeleting(true);
    await onDelete(item.id);
    setDeleting(false);
  };

  return (
    <tr className="content-row">
      <td className="td-id">#{item.id}</td>
      <td>
        <div className="content-name">{item.name || item.title}</div>
        {item.category && <div className="content-cat">{item.category}</div>}
        {(item.date || item.place_name) && (
          <div className="content-cat">{item.date} {item.place_name}</div>
        )}
      </td>
      <td>
        <button
          className={`toggle-btn${item.is_published ? ' toggle-on' : ' toggle-off'}`}
          onClick={handleToggle}
          disabled={toggling}
        >
          {item.is_published ? '✓ Активний' : '✕ Прихований'}
        </button>
      </td>
      <td>
        {item.is_featured && <span className="featured-badge">⭐ Рек.</span>}
      </td>
      <td className="td-priority">{item.priority || 0}</td>
      <td className="td-actions-content">
        <button className="btn-edit-sm" onClick={() => onEdit(item)} title="Редагувати">✏️</button>
        <button className="btn-del-sm" onClick={handleDelete} disabled={deleting} title="Видалити">
          {deleting ? '...' : '🗑️'}
        </button>
      </td>
    </tr>
  );
}

// ─── Main Content Page ────────────────────────────────────────────────────────
export default function Content() {
  const [tab, setTab] = useState('places'); // places | events
  const [places, setPlaces] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalType, setModalType] = useState(null); // 'add-place' | 'edit-place' | 'add-event' | 'edit-event'
  const [editItem, setEditItem] = useState(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [p, e] = await Promise.all([getPlaces(), getEvents()]);
      setPlaces(p);
      setEvents(e);
    } catch {
      setError('Помилка завантаження');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Places CRUD
  const handleSavePlace = async (data) => {
    if (editItem) {
      const updated = await updatePlace(editItem.id, data);
      setPlaces((prev) => prev.map((p) => p.id === editItem.id ? updated : p));
    } else {
      const created = await createPlace(data);
      setPlaces((prev) => [...prev, created]);
    }
    setModalType(null);
    setEditItem(null);
  };

  const handleDeletePlace = async (id) => {
    await deletePlace(id);
    setPlaces((prev) => prev.filter((p) => p.id !== id));
  };

  const handleTogglePlace = async (id, published) => {
    const updated = await togglePlace(id, published);
    setPlaces((prev) => prev.map((p) => p.id === id ? { ...p, is_published: updated.is_published ?? published } : p));
  };

  // Events CRUD
  const handleSaveEvent = async (data) => {
    if (editItem) {
      const updated = await updateEvent(editItem.id, data);
      setEvents((prev) => prev.map((e) => e.id === editItem.id ? updated : e));
    } else {
      const created = await createEvent(data);
      setEvents((prev) => [...prev, created]);
    }
    setModalType(null);
    setEditItem(null);
  };

  const handleDeleteEvent = async (id) => {
    await deleteEvent(id);
    setEvents((prev) => prev.filter((e) => e.id !== id));
  };

  const handleToggleEvent = async (id, published) => {
    const updated = await toggleEvent(id, published);
    setEvents((prev) => prev.map((e) => e.id === id ? { ...e, is_published: updated.is_published ?? published } : e));
  };

  return (
    <div className="page-wrap">
      <Header title="Контент" subtitle="Заклади та події" />

      <div className="page-content">
        {/* Tab switcher */}
        <div className="content-tabs">
          <button className={`tab-btn${tab === 'places' ? ' active' : ''}`} onClick={() => setTab('places')}>
            🏠 Заклади ({places.length})
          </button>
          <button className={`tab-btn${tab === 'events' ? ' active' : ''}`} onClick={() => setTab('events')}>
            🎉 Події ({events.length})
          </button>
          <button
            className="btn-primary"
            style={{ marginLeft: 'auto' }}
            onClick={() => { setEditItem(null); setModalType(tab === 'places' ? 'add-place' : 'add-event'); }}
          >
            + Додати {tab === 'places' ? 'заклад' : 'подію'}
          </button>
        </div>

        {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="spinner" style={{ width: 32, height: 32 }} />
          </div>
        ) : (
          <div className="table-wrap card">
            <table className="content-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Назва / Категорія</th>
                  <th>Статус</th>
                  <th>Рек.</th>
                  <th>Пріоритет</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {tab === 'places' && (
                  places.length === 0 ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>Заклади відсутні</td></tr>
                  ) : places.map((p) => (
                    <ContentRow
                      key={p.id} item={p} type="place"
                      onEdit={(item) => { setEditItem(item); setModalType('edit-place'); }}
                      onDelete={handleDeletePlace}
                      onToggle={handleTogglePlace}
                    />
                  ))
                )}
                {tab === 'events' && (
                  events.length === 0 ? (
                    <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>Події відсутні</td></tr>
                  ) : events.map((e) => (
                    <ContentRow
                      key={e.id} item={e} type="event"
                      onEdit={(item) => { setEditItem(item); setModalType('edit-event'); }}
                      onDelete={handleDeleteEvent}
                      onToggle={handleToggleEvent}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      {(modalType === 'add-place' || modalType === 'edit-place') && (
        <Modal
          title={modalType === 'add-place' ? 'Додати заклад' : 'Редагувати заклад'}
          onClose={() => { setModalType(null); setEditItem(null); }}
        >
          <PlaceForm
            initial={editItem || {}}
            onSave={handleSavePlace}
            onCancel={() => { setModalType(null); setEditItem(null); }}
          />
        </Modal>
      )}
      {(modalType === 'add-event' || modalType === 'edit-event') && (
        <Modal
          title={modalType === 'add-event' ? 'Додати подію' : 'Редагувати подію'}
          onClose={() => { setModalType(null); setEditItem(null); }}
        >
          <EventForm
            initial={editItem || {}}
            onSave={handleSaveEvent}
            onCancel={() => { setModalType(null); setEditItem(null); }}
          />
        </Modal>
      )}

      <style>{`
        .content-tabs { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab-btn {
          padding: 8px 18px; border-radius: 20px;
          font-size: 13px; font-weight: 600; cursor: pointer;
          border: 1.5px solid var(--border);
          color: var(--text-secondary); background: transparent;
          font-family: var(--font); transition: all 0.15s;
        }
        .tab-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; box-shadow: 0 3px 10px rgba(255,107,53,0.35); }
        .tab-btn:hover:not(.active) { background: var(--card-hover); }
        .content-table { width: 100%; border-collapse: collapse; }
        .content-table th {
          padding: 12px 14px; text-align: left;
          font-size: 11.5px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.06em; color: var(--text-muted);
          border-bottom: 2px solid var(--border);
        }
        .content-table td { padding: 14px 14px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
        .content-row:hover td { background: var(--bg); }
        .td-id { color: var(--text-muted); font-size: 12px; }
        .content-name { font-weight: 700; color: var(--text-primary); font-size: 13.5px; }
        .content-cat { font-size: 12px; color: var(--text-secondary); margin-top: 3px; }
        .toggle-btn {
          padding: 5px 12px; border-radius: 20px;
          font-size: 12px; font-weight: 600; cursor: pointer;
          border: none; transition: all 0.15s;
        }
        .toggle-on { background: #dcfce7; color: #16a34a; }
        .toggle-off { background: #f1f5f9; color: #64748b; }
        .toggle-btn:hover { opacity: 0.8; }
        .featured-badge { background: #fef9c3; color: #a16207; padding: 3px 8px; border-radius: 6px; font-size: 11.5px; font-weight: 600; }
        .td-priority { color: var(--text-muted); font-size: 13px; text-align: center; }
        .td-actions-content { display: flex; gap: 6px; }
        .btn-edit-sm { background: var(--accent-light); color: var(--accent); border: none; cursor: pointer; padding: 6px 10px; border-radius: 8px; font-size: 14px; transition: all 0.15s; }
        .btn-edit-sm:hover { background: rgba(255,107,53,0.2); }
        .btn-del-sm { background: #fef2f2; color: #dc2626; border: none; cursor: pointer; padding: 6px 10px; border-radius: 8px; font-size: 14px; transition: all 0.15s; }
        .btn-del-sm:hover { background: #fecaca; }

        /* Modal */
        .modal-overlay {
          position: fixed; inset: 0; z-index: 1000;
          background: rgba(0,0,0,0.35);
          display: flex; align-items: center; justify-content: center;
          padding: 20px;
          backdrop-filter: blur(3px);
        }
        .modal-box {
          background: var(--card-bg);
          border-radius: var(--radius);
          box-shadow: 0 20px 60px rgba(0,0,0,0.2);
          width: 100%; max-width: 680px;
          max-height: 90vh;
          display: flex; flex-direction: column;
          overflow: hidden;
        }
        .modal-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 18px 24px;
          border-bottom: 1px solid var(--border);
          flex-shrink: 0;
        }
        .modal-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
        .modal-close {
          background: var(--bg); border: 1.5px solid var(--border);
          border-radius: 8px; width: 32px; height: 32px;
          font-size: 14px; cursor: pointer; color: var(--text-secondary);
          display: flex; align-items: center; justify-content: center;
        }
        .modal-close:hover { background: #fef2f2; color: var(--danger); border-color: #fecaca; }
        .modal-body { padding: 20px 24px; overflow-y: auto; flex: 1; }

        /* Form */
        .content-form { display: flex; flex-direction: column; gap: 0; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 16px; margin-bottom: 20px; }
        .form-field { display: flex; flex-direction: column; gap: 6px; grid-column: span 2; }
        .form-field-half { grid-column: span 1; }
        .form-label { font-size: 12.5px; font-weight: 600; color: var(--text-secondary); }
        .form-input {
          padding: 9px 12px;
          border: 1.5px solid var(--border);
          border-radius: 8px; font-size: 13.5px;
          color: var(--text-primary); background: var(--bg);
          font-family: var(--font); outline: none;
          transition: border-color 0.15s;
        }
        .form-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(255,107,53,0.08); }
        .form-textarea {
          padding: 9px 12px;
          border: 1.5px solid var(--border);
          border-radius: 8px; font-size: 13.5px;
          color: var(--text-primary); background: var(--bg);
          font-family: var(--font); outline: none;
          resize: vertical; transition: border-color 0.15s;
        }
        .form-textarea:focus { border-color: var(--accent); }
        .form-checkboxes { grid-column: span 2; display: flex; gap: 20px; }
        .check-label { display: flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 500; color: var(--text-secondary); cursor: pointer; }
        .check-label input { accent-color: var(--accent); width: 16px; height: 16px; cursor: pointer; }
        .form-actions { display: flex; justify-content: flex-end; gap: 10px; padding-top: 4px; }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }
        .table-wrap { overflow-x: auto; border-radius: var(--radius); }
      `}</style>
    </div>
  );
}
