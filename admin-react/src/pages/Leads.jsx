import { useState, useEffect } from 'react';
import { getLeads, updateLeadStatus } from '../api.js';
import Header from '../components/Header.jsx';

const STATUS_OPTIONS = [
  { value: 'new', label: 'Нова', class: 'badge-new' },
  { value: 'in_work', label: 'В роботі', class: 'badge-work' },
  { value: 'done', label: 'Виконано', class: 'badge-done' },
  { value: 'rejected', label: 'Відмова', class: 'badge-cold' },
];

function statusLabel(val) {
  return STATUS_OPTIONS.find((o) => o.value === val)?.label || val || 'Нова';
}
function statusClass(val) {
  return STATUS_OPTIONS.find((o) => o.value === val)?.class || 'badge-new';
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('uk-UA', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// Inline status+note editor for a lead row
function LeadRow({ lead, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(lead.status || 'new');
  const [note, setNote] = useState(lead.manager_note || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onUpdate(lead.id, status, note);
      setEditing(false);
    } catch {}
    setSaving(false);
  };

  return (
    <tr className={`leads-row${editing ? ' leads-row-editing' : ''}`}>
      <td className="td-id">#{lead.id}</td>
      <td className="td-name">
        <div className="lead-name">{lead.name || '—'}</div>
        <div className="lead-phone">{lead.phone || '—'}</div>
      </td>
      <td>
        {lead.username ? (
          <a href={`https://t.me/${lead.username}`} target="_blank" rel="noreferrer" className="lead-tg">
            @{lead.username}
          </a>
        ) : '—'}
      </td>
      <td>{lead.category || '—'}</td>
      <td>{lead.budget || '—'}</td>
      <td>{lead.event_date || '—'}</td>
      <td>{lead.people_count || '—'}</td>
      <td className="td-details">
        <span className="lead-details-text">{lead.details || '—'}</span>
      </td>
      <td>
        {editing ? (
          <select
            className="status-select"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        ) : (
          <span className={`badge ${statusClass(lead.status)}`}>{statusLabel(lead.status)}</span>
        )}
      </td>
      <td className="td-note">
        {editing ? (
          <input
            className="note-input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Нотатка..."
            maxLength={200}
          />
        ) : (
          <span className="note-text">{lead.manager_note || '—'}</span>
        )}
      </td>
      <td className="td-date">{formatDate(lead.created_at)}</td>
      <td className="td-actions">
        {editing ? (
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn-save-sm" onClick={handleSave} disabled={saving}>
              {saving ? '...' : '✓'}
            </button>
            <button className="btn-cancel-sm" onClick={() => { setEditing(false); setStatus(lead.status || 'new'); setNote(lead.manager_note || ''); }}>
              ✕
            </button>
          </div>
        ) : (
          <button className="btn-edit-sm" onClick={() => setEditing(true)} title="Редагувати">
            ✏️
          </button>
        )}
      </td>
    </tr>
  );
}

export default function Leads() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getLeads();
      setLeads(data);
    } catch {
      setError('Помилка завантаження заявок');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpdate = async (id, status, note) => {
    await updateLeadStatus(id, status, note);
    setLeads((prev) =>
      prev.map((l) => l.id === id ? { ...l, status, manager_note: note } : l)
    );
  };

  // Stats
  const total = leads.length;
  const newCount = leads.filter((l) => !l.status || l.status === 'new').length;
  const inWorkCount = leads.filter((l) => l.status === 'in_work').length;
  const doneCount = leads.filter((l) => l.status === 'done').length;

  // Filter
  const filtered = leads.filter((l) => {
    const matchSearch =
      !search ||
      (l.name || '').toLowerCase().includes(search.toLowerCase()) ||
      (l.phone || '').includes(search) ||
      (l.username || '').toLowerCase().includes(search.toLowerCase());
    const matchStatus =
      statusFilter === 'all' || (l.status || 'new') === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="page-wrap">
      <Header title="Заявки" subtitle="Leads" />

      <div className="page-content">
        {/* Stats row */}
        <div className="stats-row">
          {[
            { label: 'Нові', value: newCount, cls: 'stat-card-accent' },
            { label: 'В роботі', value: inWorkCount, cls: '' },
            { label: 'Виконано', value: doneCount, cls: '' },
            { label: 'Всього', value: total, cls: '' },
          ].map((s) => (
            <div key={s.label} className={`stat-card card ${s.cls}`}>
              <div className="stat-card-value">{s.value}</div>
              <div className="stat-card-label">{s.label}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="leads-filters">
          <div className="search-wrap" style={{ maxWidth: 300 }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
            </svg>
            <input
              type="text"
              placeholder="Пошук за ім'ям, телефоном, username..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="filter-tabs">
            {[['all', 'Всі'], ...STATUS_OPTIONS.map((o) => [o.value, o.label])].map(([val, label]) => (
              <button
                key={val}
                className={`tab-btn${statusFilter === val ? ' active' : ''}`}
                onClick={() => setStatusFilter(val)}
              >
                {label}
              </button>
            ))}
          </div>
          <button className="btn-secondary" onClick={load} style={{ marginLeft: 'auto' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            Оновити
          </button>
        </div>

        {/* Table */}
        {error && <div className="error-msg">{error}</div>}
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
            <div className="spinner" style={{ width: 32, height: 32 }} />
          </div>
        ) : (
          <div className="table-wrap card">
            <table className="leads-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ім'я / Телефон</th>
                  <th>Username</th>
                  <th>Категорія</th>
                  <th>Бюджет</th>
                  <th>Дата події</th>
                  <th>Осіб</th>
                  <th>Деталі</th>
                  <th>Статус</th>
                  <th>Нотатка</th>
                  <th>Отримано</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={12} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '32px 0' }}>
                      {search || statusFilter !== 'all' ? 'Нічого не знайдено' : 'Заявок поки немає'}
                    </td>
                  </tr>
                )}
                {filtered.map((lead) => (
                  <LeadRow key={lead.id} lead={lead} onUpdate={handleUpdate} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <style>{`
        .stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat-card {
          padding: 20px 24px; text-align: center;
          border-radius: var(--radius);
        }
        .stat-card-accent { border-left: 4px solid var(--accent); }
        .stat-card-value { font-size: 32px; font-weight: 800; color: var(--text-primary); line-height: 1; }
        .stat-card-accent .stat-card-value { color: var(--accent); }
        .stat-card-label { font-size: 13px; color: var(--text-muted); margin-top: 6px; font-weight: 500; }
        .leads-filters { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
        .search-wrap {
          display: flex; align-items: center; gap: 8px;
          background: var(--card-bg); border: 1.5px solid var(--border);
          border-radius: var(--radius-sm); padding: 9px 12px;
          transition: border-color 0.15s; flex: 1; min-width: 200px;
        }
        .search-wrap:focus-within { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(255,107,53,0.1); }
        .search-wrap input { border: none; background: none; outline: none; color: var(--text-primary); font-size: 13.5px; font-family: var(--font); width: 100%; }
        .filter-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
        .tab-btn {
          padding: 7px 16px; border-radius: 20px;
          font-size: 12.5px; font-weight: 600; cursor: pointer;
          border: 1.5px solid var(--border);
          color: var(--text-secondary); background: transparent;
          font-family: var(--font); transition: all 0.15s;
        }
        .tab-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; box-shadow: 0 3px 10px rgba(255,107,53,0.35); }
        .tab-btn:hover:not(.active) { background: var(--card-hover); }
        .table-wrap { overflow-x: auto; }
        .leads-table { width: 100%; border-collapse: collapse; }
        .leads-table th {
          padding: 12px 14px; text-align: left;
          font-size: 11.5px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.06em; color: var(--text-muted);
          border-bottom: 2px solid var(--border);
          white-space: nowrap;
        }
        .leads-table td { padding: 14px 14px; border-bottom: 1px solid var(--border-light); vertical-align: middle; font-size: 13px; }
        .leads-row:hover td { background: var(--bg); }
        .leads-row-editing td { background: var(--accent-light); }
        .td-id { color: var(--text-muted); font-size: 12px; }
        .lead-name { font-weight: 700; color: var(--text-primary); }
        .lead-phone { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
        .lead-tg { color: var(--accent2); font-weight: 500; text-decoration: none; font-size: 13px; }
        .lead-tg:hover { text-decoration: underline; }
        .td-details { max-width: 180px; }
        .lead-details-text { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: 12.5px; color: var(--text-secondary); }
        .td-note { max-width: 160px; }
        .note-text { font-size: 12.5px; color: var(--text-secondary); }
        .td-date { white-space: nowrap; font-size: 12px; color: var(--text-muted); }
        .td-actions { text-align: center; }
        .status-select {
          padding: 6px 10px; border: 1.5px solid var(--border);
          border-radius: 8px; font-size: 12.5px; font-family: var(--font);
          color: var(--text-primary); background: var(--card-bg);
          outline: none; cursor: pointer;
        }
        .note-input {
          padding: 7px 10px; border: 1.5px solid var(--border);
          border-radius: 8px; font-size: 12.5px; font-family: var(--font);
          color: var(--text-primary); background: var(--card-bg);
          outline: none; width: 100%; min-width: 120px;
        }
        .note-input:focus { border-color: var(--accent); }
        .btn-save-sm {
          padding: 5px 12px; border-radius: 6px;
          background: linear-gradient(135deg, #ff6b35, #ff4500);
          color: #fff; border: none; font-size: 14px;
          font-weight: 700; cursor: pointer;
        }
        .btn-cancel-sm {
          padding: 5px 10px; border-radius: 6px;
          background: var(--bg); color: var(--text-secondary);
          border: 1.5px solid var(--border); font-size: 13px; cursor: pointer;
        }
        .btn-edit-sm {
          background: none; border: none; cursor: pointer; font-size: 15px;
          padding: 4px 8px; border-radius: 6px;
          transition: background 0.15s;
        }
        .btn-edit-sm:hover { background: var(--accent-light); }
        .error-msg {
          padding: 12px 16px; background: #fef2f2;
          border: 1px solid #fecaca; border-radius: var(--radius-sm);
          color: #dc2626; font-size: 13.5px; margin-bottom: 16px;
        }
      `}</style>
    </div>
  );
}
