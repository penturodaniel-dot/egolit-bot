import { useState, useEffect, useRef, useCallback } from 'react';
import { getAnalytics, syncKarabas } from '../api.js';
import Header from '../components/Header.jsx';

function drawBarChart(canvas, labels, values, color = '#ff6b35') {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!values || values.length === 0) return;
  const maxVal = Math.max(...values, 1);
  const barCount = values.length;
  const padLeft = 32, padRight = 12, padTop = 16, padBottom = 30;
  const chartW = W - padLeft - padRight;
  const chartH = H - padTop - padBottom;
  const barW = Math.max(4, (chartW / barCount) * 0.65);
  const barGap = chartW / barCount;
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padTop + (chartH / 4) * i;
    ctx.beginPath(); ctx.moveTo(padLeft, y); ctx.lineTo(W - padRight, y); ctx.stroke();
    ctx.fillStyle = '#94a3b8'; ctx.font = '10px system-ui'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxVal - (maxVal / 4) * i), padLeft - 4, y + 4);
  }
  values.forEach((val, i) => {
    const barH = (val / maxVal) * chartH;
    const x = padLeft + barGap * i + (barGap - barW) / 2;
    const y = padTop + chartH - barH;
    const grad = ctx.createLinearGradient(0, y, 0, y + barH);
    grad.addColorStop(0, color); grad.addColorStop(1, color + '88');
    ctx.fillStyle = grad;
    ctx.beginPath(); ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0]); ctx.fill();
    if (labels[i]) {
      ctx.fillStyle = '#94a3b8'; ctx.font = '10px system-ui'; ctx.textAlign = 'center';
      ctx.fillText(String(labels[i]).slice(5), x + barW / 2, H - 8); // show MM-DD
    }
  });
}

function StatCard({ label, value, sub, accent, color }) {
  return (
    <div className="analytics-stat-card card" style={accent ? { borderTop: `3px solid ${color || 'var(--accent)'}` } : {}}>
      <div className="analytics-stat-value" style={accent ? { color: color || 'var(--accent)' } : {}}>{value ?? '—'}</div>
      <div className="analytics-stat-label">{label}</div>
      {sub && <div className="analytics-stat-sub">{sub}</div>}
    </div>
  );
}

function ChartSection({ title, labels, values, color }) {
  const canvasRef = useRef(null);
  useEffect(() => { drawBarChart(canvasRef.current, labels, values, color); }, [labels, values, color]);
  return (
    <div className="chart-card card">
      <div className="chart-title">{title}</div>
      <canvas ref={canvasRef} width={600} height={160} className="chart-canvas" />
    </div>
  );
}

function ProgressBar({ label, value, max, color = '#ff6b35' }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="progress-row">
      <div className="progress-label">{label}</div>
      <div className="progress-track"><div className="progress-fill" style={{ width: `${pct}%`, background: color }} /></div>
      <div className="progress-value">{value}</div>
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setData(await getAnalytics()); }
    catch { setError('Помилка завантаження аналітики'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSync = async () => {
    setSyncing(true); setSyncMsg('');
    try {
      const res = await syncKarabas();
      setSyncMsg(`✅ +${res.new} нових, ${res.updated} оновлено, всього ${res.total_active} подій`);
      await load();
    } catch (e) {
      setSyncMsg(`❌ Помилка: ${e.message}`);
    } finally {
      setSyncing(false);
    }
  };

  // Map API response to display values
  const users   = data?.users   || {};
  const msgs    = data?.messages || {};
  const leads   = data?.leads   || {};
  const charts  = data?.charts  || {};
  const dialogs = data?.dialogs ?? 0;
  const handoffs = data?.handoffs ?? 0;
  const conversion = data?.conversion ?? 0;
  const eventsActive = data?.events_active ?? 0;
  const leadsByCat = data?.leads_by_category || [];
  const maxLeadCat = leadsByCat.length ? Math.max(...leadsByCat.map(c => c.count), 1) : 1;

  return (
    <div className="page-wrap">
      <Header title="Аналітика" subtitle="Statistics" />
      <div className="page-content">

        {/* Action bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button className="btn-primary" onClick={handleSync} disabled={syncing} style={{ background: 'linear-gradient(135deg,#10b981,#059669)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 2v6h-6M3 12a9 9 0 0115-6.7L21 8M3 22v-6h6M21 12a9 9 0 01-15 6.7L3 16" />
              </svg>
              {syncing ? 'Синхронізація...' : 'Оновити афіші Karabas'}
            </button>
            {syncMsg && <span style={{ fontSize: 13, color: syncMsg.startsWith('✅') ? '#10b981' : '#dc2626' }}>{syncMsg}</span>}
          </div>
          <button className="btn-primary" onClick={load} disabled={loading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            {loading ? 'Завантаження...' : 'Оновити статистику'}
          </button>
        </div>

        {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}

        {loading && !data ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="spinner" style={{ width: 36, height: 36 }} />
          </div>
        ) : (
          <>
            {/* Users + Activity */}
            <div className="section-label">Користувачі</div>
            <div className="analytics-stats-grid" style={{ marginBottom: 24 }}>
              <StatCard label="Всього користувачів"  value={users.total}     accent color="var(--accent)" />
              <StatCard label="Нових сьогодні"        value={users.today}     sub="за сьогодні" />
              <StatCard label="Активні (7 днів)"      value={users.active_7d} sub="за тиждень" />
              <StatCard label="Активні (30 днів)"     value={users.active_30d} sub="за місяць" />
            </div>

            {/* Messages + Leads */}
            <div className="section-label">Активність</div>
            <div className="analytics-stats-grid" style={{ marginBottom: 24 }}>
              <StatCard label="Повідомлень (вхідних)" value={msgs.in}       />
              <StatCard label="Відповідей (вихідних)" value={msgs.out}      />
              <StatCard label="Діалогів"               value={dialogs}       />
              <StatCard label="Передано менеджеру"     value={handoffs}      />
            </div>

            {/* Leads + Events */}
            <div className="section-label">Заявки та події</div>
            <div className="analytics-stats-grid" style={{ marginBottom: 24 }}>
              <StatCard label="Всього заявок"   value={leads.total}   accent color="#10b981" />
              <StatCard label="Нових заявок"    value={leads.new}     sub="очікують" />
              <StatCard label="В роботі"        value={leads.in_work} />
              <StatCard label="Виконано"        value={leads.done}    />
              <StatCard label="Заявок сьогодні" value={leads.today}   sub="за сьогодні" />
              <StatCard label="Конверсія"       value={`${conversion}%`} sub="заявок від діалогів" accent color="var(--accent2)" />
              <StatCard label="Активних афіш"   value={eventsActive}  sub="Karabas" />
            </div>

            {/* Charts */}
            <div className="charts-row">
              <ChartSection
                title="Нові користувачі (14 днів)"
                labels={charts.daily_users?.labels || []}
                values={charts.daily_users?.values || []}
                color="#ff6b35"
              />
              <ChartSection
                title="Повідомлення від клієнтів (14 днів)"
                labels={charts.daily_msgs?.labels || []}
                values={charts.daily_msgs?.values || []}
                color="#0066ff"
              />
            </div>

            {/* Leads by category */}
            {leadsByCat.length > 0 && (
              <div className="card leads-breakdown">
                <div className="chart-title">Заявки за категоріями</div>
                <div className="progress-list">
                  {leadsByCat.map(cat => (
                    <ProgressBar key={cat.category} label={cat.category} value={cat.count} max={maxLeadCat} />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <style>{`
        .section-label {
          font-size: 11px; font-weight: 700; text-transform: uppercase;
          letter-spacing: 0.08em; color: var(--text-muted);
          margin-bottom: 10px;
        }
        .analytics-stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 14px;
        }
        .analytics-stat-card { padding: 18px 20px; border-radius: var(--radius); }
        .analytics-stat-value { font-size: 28px; font-weight: 800; color: var(--text-primary); line-height: 1.1; }
        .analytics-stat-label { font-size: 11.5px; color: var(--text-muted); margin-top: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
        .analytics-stat-sub { font-size: 11px; color: var(--text-muted); margin-top: 3px; }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .chart-card { padding: 20px 22px; border-radius: var(--radius); }
        .chart-title { font-size: 13.5px; font-weight: 700; color: var(--text-primary); margin-bottom: 14px; }
        .chart-canvas { width: 100%; height: auto; display: block; }
        .leads-breakdown { padding: 20px 22px; margin-bottom: 24px; border-radius: var(--radius); }
        .progress-list { display: flex; flex-direction: column; gap: 12px; }
        .progress-row { display: flex; align-items: center; gap: 12px; }
        .progress-label { width: 160px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); font-weight: 500; }
        .progress-track { flex: 1; height: 8px; background: var(--border-light); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
        .progress-value { width: 36px; text-align: right; font-size: 13px; font-weight: 700; color: var(--text-primary); }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }
        @media (max-width: 1200px) {
          .analytics-stats-grid { grid-template-columns: repeat(3, 1fr); }
        }
        @media (max-width: 900px) {
          .analytics-stats-grid { grid-template-columns: repeat(2, 1fr); }
          .charts-row { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  );
}
