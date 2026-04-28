import { useState, useEffect } from 'react';
import {
  getPerformers, createPerformer, updatePerformer,
  deletePerformer, togglePerformer, getPerformerCategories,
} from '../api.js';
import Header from '../components/Header.jsx';

const EMPTY = {
  name: '', category: '', description: '', city: 'Дніпро',
  price_from: '', price_to: '', phone: '', instagram: '',
  telegram: '', website: '', photo_url: '', tags: '',
  experience: '', is_published: true, is_featured: false, priority: 0,
};

function Modal({ title, onClose, children }) {
  return (
    <div className="pf-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="pf-box">
        <div className="pf-header">
          <span className="pf-title">{title}</span>
          <button className="pf-close" onClick={onClose}>✕</button>
        </div>
        <div className="pf-body">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children, half }) {
  return (
    <div className={`pf-field${half ? ' pf-half' : ''}`}>
      <label className="pf-label">{label}</label>
      {children}
    </div>
  );
}

function PerformerForm({ initial, categories, onSave, onCancel }) {
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
    <form onSubmit={handleSubmit} className="pf-form">
      <div className="pf-grid">
        <Field label="Ім'я / Назва *">
          <input className="pf-input" value={data.name} onChange={e => set('name', e.target.value)} required maxLength={200} />
        </Field>
        <Field label="Категорія">
          <select className="pf-input" value={data.category} onChange={e => set('category', e.target.value)}>
            <option value="">— оберіть —</option>
            {categories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Опис">
          <textarea className="pf-textarea" value={data.description} onChange={e => set('description', e.target.value)} rows={3} />
        </Field>
        <Field label="Місто" half>
          <input className="pf-input" value={data.city} onChange={e => set('city', e.target.value)} maxLength={100} />
        </Field>
        <Field label="Досвід" half>
          <input className="pf-input" value={data.experience} onChange={e => set('experience', e.target.value)} placeholder="напр. 5 років" maxLength={100} />
        </Field>
        <Field label="Ціна від, ₴" half>
          <input className="pf-input" type="number" value={data.price_from} onChange={e => set('price_from', e.target.value)} />
        </Field>
        <Field label="Ціна до, ₴" half>
          <input className="pf-input" type="number" value={data.price_to} onChange={e => set('price_to', e.target.value)} />
        </Field>
        <Field label="Телефон" half>
          <input className="pf-input" value={data.phone} onChange={e => set('phone', e.target.value)} maxLength={50} />
        </Field>
        <Field label="Instagram" half>
          <input className="pf-input" value={data.instagram} onChange={e => set('instagram', e.target.value)} maxLength={100} />
        </Field>
        <Field label="Telegram" half>
          <input className="pf-input" value={data.telegram} onChange={e => set('telegram', e.target.value)} maxLength={100} />
        </Field>
        <Field label="Сайт" half>
          <input className="pf-input" value={data.website} onChange={e => set('website', e.target.value)} maxLength={200} />
        </Field>
        <Field label="Фото URL">
          <input className="pf-input" value={data.photo_url} onChange={e => set('photo_url', e.target.value)} maxLength={300} />
        </Field>
        {data.photo_url && (
          <div style={{ gridColumn: 'span 2' }}>
            <img src={data.photo_url} alt="preview" style={{ maxWidth: 120, maxHeight: 80, borderRadius: 8, objectFit: 'cover' }} onError={e => e.target.style.display = 'none'} />
          </div>
        )}
        <Field label="Теги (через кому)">
          <input className="pf-input" value={data.tags} onChange={e => set('tags', e.target.value)} maxLength={300} placeholder="весілля, корпоратив, дитячі свята" />
        </Field>
        <Field label="Пріоритет (0–100)" half>
          <input className="pf-input" type="number" min={0} max={100} value={data.priority} onChange={e => set('priority', parseInt(e.target.value) || 0)} />
        </Field>
        <div className="pf-checks">
          <label className="pf-check">
            <input type="checkbox" checked={data.is_published} onChange={e => set('is_published', e.target.checked)} />
            Опублікований
          </label>
          <label className="pf-check">
            <input type="checkbox" checked={data.is_featured} onChange={e => set('is_featured', e.target.checked)} />
            ⭐ Рекомендований
          </label>
        </div>
      </div>
      <div className="pf-actions">
        <button type="button" className="btn-secondary" onClick={onCancel}>Скасувати</button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? 'Збереження...' : 'Зберегти'}
        </button>
      </div>
    </form>
  );
}

function PerformerRow({ item, onEdit, onDelete, onToggle }) {
  const [busy, setBusy] = useState(false);

  const handleToggle = async () => {
    setBusy(true);
    await onToggle(item.id);
    setBusy(false);
  };

  const handleDelete = async () => {
    if (!confirm(`Видалити "${item.name}"?`)) return;
    setBusy(true);
    await onDelete(item.id);
    setBusy(false);
  };

  return (
    <tr className="pf-row">
      <td className="td-id">#{item.id}</td>
      <td>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {item.photo_url && (
            <img src={item.photo_url} alt="" style={{ width: 36, height: 36, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }}
              onError={e => e.target.style.display = 'none'} />
          )}
          <div>
            <div className="pf-name">{item.is_featured && '⭐ '}{item.name}</div>
            <div className="pf-meta">{item.category}{item.city && item.city !== 'Дніпро' ? ` · ${item.city}` : ''}</div>
          </div>
        </div>
      </td>
      <td>
        {item.price_from
          ? <span className="pf-price">від {item.price_from.toLocaleString()} ₴</span>
          : <span className="pf-price-empty">—</span>}
      </td>
      <td>
        <div className="pf-contacts">
          {item.phone && <a href={`tel:${item.phone}`} className="pf-contact-link">📞</a>}
          {item.instagram && <a href={`https://instagram.com/${item.instagram.replace('@','')}`} target="_blank" rel="noreferrer" className="pf-contact-link">📷</a>}
          {item.telegram && <a href={`https://t.me/${item.telegram.replace('@','')}`} target="_blank" rel="noreferrer" className="pf-contact-link">✈️</a>}
          {item.website && <a href={item.website} target="_blank" rel="noreferrer" className="pf-contact-link">🌐</a>}
        </div>
      </td>
      <td>
        <button
          className={`toggle-btn${item.is_published ? ' toggle-on' : ' toggle-off'}`}
          onClick={handleToggle} disabled={busy}
        >
          {item.is_published ? '✓ Активний' : '✕ Прихований'}
        </button>
      </td>
      <td className="td-actions-content">
        <button className="btn-edit-sm" onClick={() => onEdit(item)} title="Редагувати">✏️</button>
        <button className="btn-del-sm" onClick={handleDelete} disabled={busy} title="Видалити">
          {busy ? '...' : '🗑️'}
        </button>
      </td>
    </tr>
  );
}

export default function Performers() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [filterCat, setFilterCat] = useState('');
  const [modal, setModal] = useState(null); // null | 'add' | 'edit'
  const [editItem, setEditItem] = useState(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [perfs, cats] = await Promise.all([getPerformers(), getPerformerCategories()]);
      setItems(perfs);
      setCategories(cats);
    } catch {
      setError('Помилка завантаження');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async data => {
    if (editItem) {
      const updated = await updatePerformer(editItem.id, data);
      setItems(prev => prev.map(p => p.id === editItem.id ? updated : p));
    } else {
      const created = await createPerformer(data);
      setItems(prev => [created, ...prev]);
    }
    setModal(null);
    setEditItem(null);
  };

  const handleDelete = async id => {
    await deletePerformer(id);
    setItems(prev => prev.filter(p => p.id !== id));
  };

  const handleToggle = async id => {
    const res = await togglePerformer(id);
    setItems(prev => prev.map(p => p.id === id ? { ...p, is_published: res.is_published } : p));
  };

  const filtered = items.filter(p => {
    const q = search.toLowerCase();
    const matchSearch = !q || p.name?.toLowerCase().includes(q) || p.category?.toLowerCase().includes(q) || p.tags?.toLowerCase().includes(q);
    const matchCat = !filterCat || p.category === filterCat;
    return matchSearch && matchCat;
  });

  const usedCats = [...new Set(items.map(p => p.category).filter(Boolean))].sort();

  return (
    <div className="page-wrap">
      <Header title="Виконавці" subtitle={`CRM-база виконавців · ${items.length} записів`} />

      <div className="page-content">
        <div className="pf-toolbar">
          <input
            className="pf-search"
            placeholder="🔍 Пошук за іменем, категорією, тегами..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select className="pf-filter" value={filterCat} onChange={e => setFilterCat(e.target.value)}>
            <option value="">Всі категорії</option>
            {usedCats.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button className="btn-primary" onClick={() => { setEditItem(null); setModal('add'); }}>
            + Додати виконавця
          </button>
        </div>

        {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="spinner" style={{ width: 32, height: 32 }} />
          </div>
        ) : (
          <div className="table-wrap card">
            <table className="pf-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Виконавець</th>
                  <th>Ціна</th>
                  <th>Контакти</th>
                  <th>Статус</th>
                  <th>Дії</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 0' }}>
                    {search || filterCat ? 'Нічого не знайдено' : 'Виконавців ще немає — додайте першого!'}
                  </td></tr>
                ) : filtered.map(item => (
                  <PerformerRow
                    key={item.id} item={item}
                    onEdit={i => { setEditItem(i); setModal('edit'); }}
                    onDelete={handleDelete}
                    onToggle={handleToggle}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {(modal === 'add' || modal === 'edit') && (
        <Modal
          title={modal === 'add' ? '+ Додати виконавця' : 'Редагувати виконавця'}
          onClose={() => { setModal(null); setEditItem(null); }}
        >
          <PerformerForm
            initial={editItem || {}}
            categories={categories}
            onSave={handleSave}
            onCancel={() => { setModal(null); setEditItem(null); }}
          />
        </Modal>
      )}

      <style>{`
        .pf-toolbar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
        .pf-search {
          flex: 1; min-width: 200px;
          padding: 9px 14px; border-radius: 10px;
          border: 1.5px solid var(--border); background: var(--card-bg);
          font-size: 13.5px; color: var(--text-primary); font-family: var(--font);
          outline: none;
        }
        .pf-search:focus { border-color: var(--accent); }
        .pf-filter {
          padding: 9px 12px; border-radius: 10px;
          border: 1.5px solid var(--border); background: var(--card-bg);
          font-size: 13px; color: var(--text-secondary); font-family: var(--font);
          outline: none; cursor: pointer;
        }
        .pf-table { width: 100%; border-collapse: collapse; }
        .pf-table th {
          padding: 12px 14px; text-align: left;
          font-size: 11.5px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.06em; color: var(--text-muted);
          border-bottom: 2px solid var(--border);
        }
        .pf-table td { padding: 13px 14px; border-bottom: 1px solid var(--border-light); vertical-align: middle; }
        .pf-row:hover td { background: var(--bg); }
        .td-id { color: var(--text-muted); font-size: 12px; }
        .pf-name { font-weight: 700; font-size: 13.5px; color: var(--text-primary); }
        .pf-meta { font-size: 12px; color: var(--text-muted); margin-top: 2px; }
        .pf-price { font-size: 13px; font-weight: 600; color: #16a34a; }
        .pf-price-empty { color: var(--text-muted); font-size: 13px; }
        .pf-contacts { display: flex; gap: 6px; }
        .pf-contact-link { font-size: 16px; text-decoration: none; opacity: 0.85; transition: opacity 0.15s; }
        .pf-contact-link:hover { opacity: 1; }
        .toggle-btn { padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; transition: all 0.15s; }
        .toggle-on { background: #dcfce7; color: #16a34a; }
        .toggle-off { background: #f1f5f9; color: #64748b; }
        .td-actions-content { display: flex; gap: 6px; }
        .btn-edit-sm { background: var(--accent-light); color: var(--accent); border: none; cursor: pointer; padding: 6px 10px; border-radius: 8px; font-size: 14px; }
        .btn-edit-sm:hover { background: rgba(255,107,53,0.2); }
        .btn-del-sm { background: #fef2f2; color: #dc2626; border: none; cursor: pointer; padding: 6px 10px; border-radius: 8px; font-size: 14px; }
        .btn-del-sm:hover { background: #fecaca; }

        /* Modal */
        .pf-overlay { position: fixed; inset: 0; z-index: 1000; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; padding: 20px; backdrop-filter: blur(3px); }
        .pf-box { background: var(--card-bg); border-radius: var(--radius); box-shadow: 0 20px 60px rgba(0,0,0,0.2); width: 100%; max-width: 680px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
        .pf-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
        .pf-title { font-size: 16px; font-weight: 700; color: var(--text-primary); }
        .pf-close { background: var(--bg); border: 1.5px solid var(--border); border-radius: 8px; width: 32px; height: 32px; font-size: 14px; cursor: pointer; color: var(--text-secondary); display: flex; align-items: center; justify-content: center; }
        .pf-close:hover { background: #fef2f2; color: var(--danger); border-color: #fecaca; }
        .pf-body { padding: 20px 24px; overflow-y: auto; flex: 1; }
        .pf-form { display: flex; flex-direction: column; gap: 0; }
        .pf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 16px; margin-bottom: 20px; }
        .pf-field { display: flex; flex-direction: column; gap: 6px; grid-column: span 2; }
        .pf-half { grid-column: span 1; }
        .pf-label { font-size: 12.5px; font-weight: 600; color: var(--text-secondary); }
        .pf-input { padding: 9px 12px; border: 1.5px solid var(--border); border-radius: 8px; font-size: 13.5px; color: var(--text-primary); background: var(--bg); font-family: var(--font); outline: none; transition: border-color 0.15s; }
        .pf-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(255,107,53,0.08); }
        .pf-textarea { padding: 9px 12px; border: 1.5px solid var(--border); border-radius: 8px; font-size: 13.5px; color: var(--text-primary); background: var(--bg); font-family: var(--font); outline: none; resize: vertical; transition: border-color 0.15s; }
        .pf-textarea:focus { border-color: var(--accent); }
        .pf-checks { grid-column: span 2; display: flex; gap: 20px; }
        .pf-check { display: flex; align-items: center; gap: 8px; font-size: 13.5px; font-weight: 500; color: var(--text-secondary); cursor: pointer; }
        .pf-check input { accent-color: var(--accent); width: 16px; height: 16px; }
        .pf-actions { display: flex; justify-content: flex-end; gap: 10px; padding-top: 4px; }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }
        .table-wrap { overflow-x: auto; border-radius: var(--radius); }
      `}</style>
    </div>
  );
}
