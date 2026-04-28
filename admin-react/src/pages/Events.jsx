import { useState, useEffect } from 'react';
import {
  getAllEvents, createUnifiedEvent, updateUnifiedEvent,
  deleteUnifiedEvent, toggleUnifiedEvent,
} from '../api.js';
import Header from '../components/Header.jsx';

const EVENT_CATEGORIES = [
  'концерти', 'театр', 'стендап', 'для дітей', 'фестивалі',
  'виставки', 'кіно', 'активний відпочинок', 'майстер-класи',
  'спорт', 'клуби', 'інше',
];

const EMPTY = {
  title: '', category: '', description: '', date: '', time: '',
  price: '', venue_name: '', venue_address: '', city: 'Дніпро',
  image_url: '', source_url: '', ticket_url: '',
  is_published: true, is_featured: false, priority: 0,
  tags: '', internal_notes: '',
};

function Modal({ title, onClose, children }) {
  return (
    <div className="ef-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="ef-box">
        <div className="ef-header">
          <span className="ef-title">{title}</span>
          <button className="ef-close" onClick={onClose}>✕</button>
        </div>
        <div className="ef-body">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children, half }) {
  return (
    <div className={`ef-field${half ? ' ef-half' : ''}`}>
      <label className="ef-label">{label}</label>
      {children}
    </div>
  );
}

function EventForm({ initial, onSave, onCancel }) {
  const [data, setData] = useState({ ...EMPTY, ...initial });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setData(p => ({ ...p, [k]: v }));

  const handleSubmit = async e => {
    e.preventDefault();
    setSaving(true);
    try { await onSave(data); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div className="ef-row">
        <Field label="Назва *" >
          <input className="ef-input" value={data.title} required
            onChange={e => set('title', e.target.value)} placeholder="Назва події" />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Категорія" half>
          <select className="ef-input" value={data.category}
            onChange={e => set('category', e.target.value)}>
            <option value="">— оберіть —</option>
            {EVENT_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Місто" half>
          <input className="ef-input" value={data.city}
            onChange={e => set('city', e.target.value)} placeholder="Дніпро" />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Дата" half>
          <input className="ef-input" type="date" value={data.date || ''}
            onChange={e => set('date', e.target.value)} />
        </Field>
        <Field label="Час" half>
          <input className="ef-input" type="time" value={data.time || ''}
            onChange={e => set('time', e.target.value)} />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Майданчик" half>
          <input className="ef-input" value={data.venue_name || ''}
            onChange={e => set('venue_name', e.target.value)} placeholder="Назва місця" />
        </Field>
        <Field label="Адреса" half>
          <input className="ef-input" value={data.venue_address || ''}
            onChange={e => set('venue_address', e.target.value)} placeholder="вул. Яворницького, 1" />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Ціна" half>
          <input className="ef-input" value={data.price || ''}
            onChange={e => set('price', e.target.value)} placeholder="від 200 грн" />
        </Field>
        <Field label="Пріоритет" half>
          <input className="ef-input" type="number" min="0" max="100"
            value={data.priority || 0}
            onChange={e => set('priority', parseInt(e.target.value) || 0)} />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Посилання на квитки">
          <input className="ef-input" value={data.ticket_url || ''}
            onChange={e => set('ticket_url', e.target.value)} placeholder="https://..." />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Джерело / сайт">
          <input className="ef-input" value={data.source_url || ''}
            onChange={e => set('source_url', e.target.value)} placeholder="https://..." />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Фото (URL)">
          <input className="ef-input" value={data.image_url || ''}
            onChange={e => set('image_url', e.target.value)} placeholder="https://..." />
        </Field>
      </div>
      {data.image_url && (
        <div style={{ marginBottom: 12 }}>
          <img src={data.image_url} alt="preview" style={{ maxHeight: 120, borderRadius: 8, objectFit: 'cover' }} />
        </div>
      )}
      <div className="ef-row">
        <Field label="Опис">
          <textarea className="ef-input ef-textarea" value={data.description || ''}
            onChange={e => set('description', e.target.value)} rows={3}
            placeholder="Опис події..." />
        </Field>
      </div>
      <div className="ef-row">
        <Field label="Теги" half>
          <input className="ef-input" value={data.tags || ''}
            onChange={e => set('tags', e.target.value)} placeholder="джаз, весілля, фест" />
        </Field>
        <Field label="Нотатки (внутрішні)" half>
          <input className="ef-input" value={data.internal_notes || ''}
            onChange={e => set('internal_notes', e.target.value)} placeholder="Для адміна" />
        </Field>
      </div>
      <div className="ef-row ef-checks">
        <label className="ef-check">
          <input type="checkbox" checked={data.is_published}
            onChange={e => set('is_published', e.target.checked)} />
          Опубліковано
        </label>
        <label className="ef-check">
          <input type="checkbox" checked={data.is_featured}
            onChange={e => set('is_featured', e.target.checked)} />
          Топ подія
        </label>
      </div>
      <div className="ef-footer">
        <button type="button" className="ef-btn-cancel" onClick={onCancel}>Скасувати</button>
        <button type="submit" className="ef-btn-save" disabled={saving}>
          {saving ? 'Збереження...' : 'Зберегти'}
        </button>
      </div>
    </form>
  );
}

export default function Events() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [modal, setModal] = useState(null); // null | { mode: 'add'|'edit', event?: obj }
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    getAllEvents()
      .then(data => setEvents(Array.isArray(data) ? data : []))
      .catch(() => setError('Помилка завантаження'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const filtered = events.filter(e => {
    if (filterCat && e.category !== filterCat) return false;
    if (filterSource && e.source !== filterSource) return false;
    if (search) {
      const q = search.toLowerCase();
      return (e.title || '').toLowerCase().includes(q) ||
        (e.venue_name || '').toLowerCase().includes(q) ||
        (e.description || '').toLowerCase().includes(q);
    }
    return true;
  });

  const handleSave = async (data) => {
    try {
      if (modal.mode === 'add') {
        await createUnifiedEvent(data);
      } else {
        await updateUnifiedEvent(modal.event.id, data);
      }
      setModal(null);
      load();
    } catch (e) {
      alert('Помилка: ' + e.message);
    }
  };

  const handleDelete = async (ev) => {
    if (!window.confirm(`Видалити "${ev.title}"?`)) return;
    setDeleting(ev.id);
    try {
      await deleteUnifiedEvent(ev.id);
      load();
    } catch (e) {
      alert('Помилка: ' + e.message);
    } finally {
      setDeleting(null);
    }
  };

  const handleToggle = async (ev) => {
    try {
      await toggleUnifiedEvent(ev.id);
      load();
    } catch (e) {
      alert('Помилка: ' + e.message);
    }
  };

  const sources = [...new Set(events.map(e => e.source).filter(Boolean))];

  const formatDate = (d) => {
    if (!d) return '—';
    try {
      return new Date(d).toLocaleDateString('uk-UA', { day: '2-digit', month: '2-digit', year: '2-digit' });
    } catch { return d; }
  };

  return (
    <div className="ef-page">
      <Header title="Афіша" subtitle={`${filtered.length} подій`} />

      <div className="ef-toolbar">
        <input
          className="ef-search"
          placeholder="Пошук подій..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select className="ef-filter-select" value={filterCat} onChange={e => setFilterCat(e.target.value)}>
          <option value="">Всі категорії</option>
          {EVENT_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="ef-filter-select" value={filterSource} onChange={e => setFilterSource(e.target.value)}>
          <option value="">Всі джерела</option>
          {sources.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="ef-btn-add" onClick={() => setModal({ mode: 'add' })}>
          + Додати подію
        </button>
      </div>

      {error && <div className="ef-error">{error}</div>}

      {loading ? (
        <div className="ef-loading">Завантаження...</div>
      ) : filtered.length === 0 ? (
        <div className="ef-empty">
          <div className="ef-empty-icon">📅</div>
          <div>Подій не знайдено</div>
          <button className="ef-btn-add" onClick={() => setModal({ mode: 'add' })}>
            Додати першу подію
          </button>
        </div>
      ) : (
        <div className="ef-table-wrap">
          <table className="ef-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Подія</th>
                <th>Дата</th>
                <th>Категорія</th>
                <th>Місце</th>
                <th>Ціна</th>
                <th>Джерело</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((ev, idx) => (
                <tr key={ev.id} className={ev.is_featured ? 'ef-row-featured' : ''}>
                  <td className="ef-td-num">{idx + 1}</td>
                  <td className="ef-td-main">
                    <div className="ef-event-cell">
                      {ev.image_url || ev.cloudinary_url ? (
                        <img
                          src={ev.cloudinary_url || ev.image_url}
                          alt={ev.title}
                          className="ef-thumb"
                          onError={e => { e.target.style.display = 'none'; }}
                        />
                      ) : (
                        <div className="ef-thumb-ph">📅</div>
                      )}
                      <div>
                        <div className="ef-name">
                          {ev.is_featured && <span className="ef-badge-top">ТОП</span>}
                          {ev.title}
                        </div>
                        {ev.description && (
                          <div className="ef-desc">{ev.description.slice(0, 80)}{ev.description.length > 80 ? '…' : ''}</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="ef-td-date">{formatDate(ev.date)}{ev.time ? <div className="ef-time">{ev.time.slice(0,5)}</div> : null}</td>
                  <td><span className="ef-cat-badge">{ev.category || '—'}</span></td>
                  <td className="ef-td-venue">
                    {ev.venue_name && <div className="ef-venue-name">{ev.venue_name}</div>}
                    {ev.venue_address && <div className="ef-venue-addr">{ev.venue_address}</div>}
                    {!ev.venue_name && !ev.venue_address && '—'}
                  </td>
                  <td className="ef-td-price">{ev.price || '—'}</td>
                  <td>
                    <span className={`ef-source-badge ef-source-${ev.source || 'manual'}`}>
                      {ev.source || 'manual'}
                    </span>
                  </td>
                  <td>
                    <button
                      className={`ef-toggle${ev.is_published ? ' ef-toggle-on' : ' ef-toggle-off'}`}
                      onClick={() => handleToggle(ev)}
                      title={ev.is_published ? 'Приховати' : 'Опублікувати'}
                    >
                      {ev.is_published ? 'Опубл.' : 'Прихов.'}
                    </button>
                  </td>
                  <td className="ef-td-actions">
                    {ev.ticket_url && (
                      <a href={ev.ticket_url} target="_blank" rel="noreferrer" className="ef-action-link" title="Квитки">
                        🎟
                      </a>
                    )}
                    {(ev.source === 'manual' || !ev.source) && (
                      <>
                        <button className="ef-action-btn" onClick={() => setModal({ mode: 'edit', event: ev })}>✏️</button>
                        <button
                          className="ef-action-btn ef-action-del"
                          onClick={() => handleDelete(ev)}
                          disabled={deleting === ev.id}
                        >🗑</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <Modal
          title={modal.mode === 'add' ? 'Нова подія' : 'Редагувати подію'}
          onClose={() => setModal(null)}
        >
          <EventForm
            initial={modal.event || {}}
            onSave={handleSave}
            onCancel={() => setModal(null)}
          />
        </Modal>
      )}

      <style>{`
        .ef-page { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
        .ef-toolbar {
          display: flex; align-items: center; gap: 10px;
          padding: 14px 20px; border-bottom: 1px solid var(--border);
          flex-wrap: wrap;
        }
        .ef-search {
          flex: 1; min-width: 160px; max-width: 280px;
          padding: 8px 12px; border-radius: var(--radius-sm);
          border: 1px solid var(--border); font-size: 13px;
          background: var(--card-bg); color: var(--text-primary);
          outline: none;
        }
        .ef-search:focus { border-color: var(--accent); }
        .ef-filter-select {
          padding: 8px 10px; border-radius: var(--radius-sm);
          border: 1px solid var(--border); font-size: 13px;
          background: var(--card-bg); color: var(--text-primary);
          cursor: pointer; outline: none;
        }
        .ef-btn-add {
          margin-left: auto; padding: 8px 16px;
          background: var(--accent); color: #fff;
          border: none; border-radius: var(--radius-sm);
          font-size: 13px; font-weight: 600; cursor: pointer;
          transition: opacity 0.15s; white-space: nowrap;
        }
        .ef-btn-add:hover { opacity: 0.88; }
        .ef-error { padding: 12px 20px; color: #dc2626; font-size: 13px; }
        .ef-loading { padding: 40px; text-align: center; color: var(--text-muted); }
        .ef-empty {
          flex: 1; display: flex; flex-direction: column;
          align-items: center; justify-content: center; gap: 12px;
          color: var(--text-muted); font-size: 14px;
        }
        .ef-empty-icon { font-size: 48px; }
        .ef-table-wrap { flex: 1; overflow: auto; }
        .ef-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .ef-table th {
          position: sticky; top: 0; z-index: 2;
          background: var(--table-header, #f8f9fa);
          padding: 10px 14px; text-align: left;
          font-size: 11px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.06em; color: var(--text-muted);
          border-bottom: 1px solid var(--border);
          white-space: nowrap;
        }
        .ef-table td {
          padding: 10px 14px; border-bottom: 1px solid var(--border-light);
          vertical-align: middle;
        }
        .ef-table tr:hover td { background: var(--card-hover); }
        .ef-row-featured td { background: #fffbf0; }
        .ef-td-num { color: var(--text-muted); width: 36px; }
        .ef-td-main { max-width: 320px; }
        .ef-event-cell { display: flex; align-items: flex-start; gap: 10px; }
        .ef-thumb {
          width: 52px; height: 38px; object-fit: cover;
          border-radius: 6px; flex-shrink: 0; background: var(--border);
        }
        .ef-thumb-ph {
          width: 52px; height: 38px; flex-shrink: 0;
          background: var(--border); border-radius: 6px;
          display: flex; align-items: center; justify-content: center;
          font-size: 18px;
        }
        .ef-name { font-weight: 600; color: var(--text-primary); font-size: 13px; display: flex; align-items: center; gap: 5px; flex-wrap: wrap; }
        .ef-desc { font-size: 11.5px; color: var(--text-muted); margin-top: 2px; line-height: 1.4; }
        .ef-badge-top {
          background: #fef3c7; color: #d97706; border: 1px solid #fde68a;
          border-radius: 4px; padding: 1px 5px; font-size: 9px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.05em; flex-shrink: 0;
        }
        .ef-td-date { width: 80px; white-space: nowrap; }
        .ef-time { font-size: 11px; color: var(--text-muted); margin-top: 1px; }
        .ef-cat-badge {
          background: var(--accent-light); color: var(--accent);
          border-radius: 20px; padding: 2px 9px; font-size: 11px; font-weight: 600;
          white-space: nowrap;
        }
        .ef-td-venue { max-width: 160px; }
        .ef-venue-name { font-weight: 500; font-size: 12.5px; }
        .ef-venue-addr { font-size: 11px; color: var(--text-muted); }
        .ef-td-price { white-space: nowrap; font-size: 12.5px; color: var(--text-secondary); }
        .ef-source-badge {
          border-radius: 4px; padding: 2px 7px; font-size: 10px; font-weight: 700;
          text-transform: uppercase; letter-spacing: 0.04em;
        }
        .ef-source-manual { background: #dcfce7; color: #16a34a; }
        .ef-source-egolist { background: #dbeafe; color: #1d4ed8; }
        .ef-source-kontramarka { background: #f3e8ff; color: #7c3aed; }
        .ef-source-karabas { background: #fef3c7; color: #b45309; }
        .ef-toggle {
          padding: 3px 9px; border-radius: 20px; border: none;
          font-size: 11px; font-weight: 600; cursor: pointer; white-space: nowrap;
        }
        .ef-toggle-on { background: #dcfce7; color: #16a34a; }
        .ef-toggle-off { background: #f1f5f9; color: var(--text-muted); }
        .ef-td-actions { display: flex; align-items: center; gap: 4px; white-space: nowrap; }
        .ef-action-btn {
          background: none; border: none; cursor: pointer;
          font-size: 15px; padding: 3px 4px; border-radius: 5px;
          transition: background 0.15s;
        }
        .ef-action-btn:hover { background: var(--card-hover); }
        .ef-action-del:hover { background: #fef2f2; }
        .ef-action-link {
          font-size: 15px; padding: 3px 4px; border-radius: 5px;
          text-decoration: none; transition: background 0.15s;
        }
        .ef-action-link:hover { background: var(--card-hover); }

        /* Modal */
        .ef-overlay {
          position: fixed; inset: 0; z-index: 1000;
          background: rgba(0,0,0,0.45);
          display: flex; align-items: center; justify-content: center;
        }
        .ef-box {
          background: var(--card-bg); border-radius: var(--radius);
          width: 600px; max-width: 96vw; max-height: 90vh;
          display: flex; flex-direction: column;
          box-shadow: 0 20px 60px rgba(0,0,0,0.25);
        }
        .ef-header {
          display: flex; align-items: center; justify-content: space-between;
          padding: 18px 22px 14px;
          border-bottom: 1px solid var(--border);
        }
        .ef-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
        .ef-close {
          background: none; border: none; font-size: 17px;
          color: var(--text-muted); cursor: pointer; padding: 3px 7px;
          border-radius: 5px;
        }
        .ef-close:hover { background: var(--card-hover); color: var(--text-primary); }
        .ef-body { padding: 18px 22px; overflow-y: auto; flex: 1; }
        .ef-row { display: flex; gap: 12px; margin-bottom: 14px; }
        .ef-field { flex: 1; display: flex; flex-direction: column; gap: 5px; }
        .ef-half { flex: 0 0 calc(50% - 6px); }
        .ef-label { font-size: 12px; font-weight: 600; color: var(--text-secondary); }
        .ef-input {
          padding: 8px 10px; border-radius: var(--radius-sm);
          border: 1px solid var(--border); font-size: 13px;
          background: var(--bg); color: var(--text-primary);
          outline: none; width: 100%; box-sizing: border-box;
          transition: border 0.15s;
        }
        .ef-input:focus { border-color: var(--accent); }
        .ef-textarea { resize: vertical; min-height: 70px; }
        .ef-checks { display: flex; align-items: center; gap: 20px; margin-bottom: 14px; flex-wrap: wrap; }
        .ef-check {
          display: flex; align-items: center; gap: 6px;
          font-size: 13px; font-weight: 500; color: var(--text-primary);
          cursor: pointer; user-select: none;
        }
        .ef-check input { cursor: pointer; width: 15px; height: 15px; }
        .ef-footer {
          display: flex; justify-content: flex-end; gap: 10px;
          padding-top: 16px; border-top: 1px solid var(--border); margin-top: 6px;
        }
        .ef-btn-cancel {
          padding: 8px 18px; border-radius: var(--radius-sm);
          border: 1px solid var(--border); background: var(--card-bg);
          color: var(--text-secondary); font-size: 13px; font-weight: 600;
          cursor: pointer; transition: all 0.15s;
        }
        .ef-btn-cancel:hover { background: var(--card-hover); }
        .ef-btn-save {
          padding: 8px 22px; border-radius: var(--radius-sm);
          border: none; background: var(--accent); color: #fff;
          font-size: 13px; font-weight: 600; cursor: pointer; transition: opacity 0.15s;
        }
        .ef-btn-save:hover:not(:disabled) { opacity: 0.88; }
        .ef-btn-save:disabled { opacity: 0.55; cursor: default; }
      `}</style>
    </div>
  );
}
