import { useState, useEffect, useRef, useCallback } from 'react';
import { getAnalytics } from '../api.js';
import Header from '../components/Header.jsx';

// Draw a simple bar chart on a canvas element
function drawBarChart(canvas, labels, values, color = '#ff6b35') {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  ctx.clearRect(0, 0, W, H);

  if (!values || values.length === 0) return;

  const maxVal = Math.max(...values, 1);
  const barCount = values.length;
  const padLeft = 32;
  const padRight = 12;
  const padTop = 16;
  const padBottom = 30;
  const chartW = W - padLeft - padRight;
  const chartH = H - padTop - padBottom;
  const barW = Math.max(4, (chartW / barCount) * 0.65);
  const barGap = chartW / barCount;

  // Y grid lines
  ctx.strokeStyle = '#e2e8f0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = padTop + (chartH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(W - padRight, y);
    ctx.stroke();
    // Y labels
    const val = Math.round(maxVal - (maxVal / 4) * i);
    ctx.fillStyle = '#94a3b8';
    ctx.font = '10px system-ui';
    ctx.textAlign = 'right';
    ctx.fillText(val, padLeft - 4, y + 4);
  }

  // Bars
  values.forEach((val, i) => {
    const barH = (val / maxVal) * chartH;
    const x = padLeft + barGap * i + (barGap - barW) / 2;
    const y = padTop + chartH - barH;

    // Gradient fill
    const grad = ctx.createLinearGradient(0, y, 0, y + barH);
    grad.addColorStop(0, color);
    grad.addColorStop(1, color + '88');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(x, y, barW, barH, [4, 4, 0, 0]);
    ctx.fill();

    // X labels
    if (labels[i]) {
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px system-ui';
      ctx.textAlign = 'center';
      const lbl = String(labels[i]).slice(0, 5);
      ctx.fillText(lbl, x + barW / 2, H - 8);
    }
  });
}

// Stat card component
function StatCard({ label, value, sub, accent }) {
  return (
    <div className={`analytics-stat-card card${accent ? ' analytics-stat-accent' : ''}`}>
      <div className="analytics-stat-value">{value ?? '—'}</div>
      <div className="analytics-stat-label">{label}</div>
      {sub && <div className="analytics-stat-sub">{sub}</div>}
    </div>
  );
}

// Bar chart section
function ChartSection({ title, labels, values, color }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawBarChart(canvas, labels, values, color);
  }, [labels, values, color]);

  return (
    <div className="chart-card card">
      <div className="chart-title">{title}</div>
      <canvas ref={canvasRef} width={600} height={160} className="chart-canvas" />
    </div>
  );
}

// Progress bar for lead categories
function ProgressBar({ label, value, max, color = '#ff6b35' }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="progress-row">
      <div className="progress-label">{label}</div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="progress-value">{value}</div>
    </div>
  );
}

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const d = await getAnalytics();
      setData(d);
    } catch {
      setError('Помилка завантаження аналітики');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const stats = data?.stats || {};
  const charts = data?.charts || {};
  const leadsByCategory = data?.leads_by_category || [];

  const maxLeadCat = leadsByCategory.length
    ? Math.max(...leadsByCategory.map((c) => c.count), 1)
    : 1;

  return (
    <div className="page-wrap">
      <Header title="Аналітика" subtitle="Statistics" />

      <div className="page-content">
        {/* Refresh button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 20 }}>
          <button className="btn-primary" onClick={load} disabled={loading}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
              <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
            </svg>
            {loading ? 'Завантаження...' : 'Оновити'}
          </button>
        </div>

        {error && (
          <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>
        )}

        {loading && !data ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
            <div className="spinner" style={{ width: 36, height: 36 }} />
          </div>
        ) : (
          <>
            {/* Stat cards grid */}
            <div className="analytics-stats-grid">
              <StatCard label="Всього користувачів" value={stats.total_users} accent />
              <StatCard label="Активні (7 днів)" value={stats.active_7d} sub="за тиждень" />
              <StatCard label="Активні (30 днів)" value={stats.active_30d} sub="за місяць" />
              <StatCard label="Всього діалогів" value={stats.total_sessions} />
              <StatCard label="Повідомлень" value={stats.total_messages} />
              <StatCard label="Заявок" value={stats.total_leads} accent />
              <StatCard label="Передано менеджеру" value={stats.handoffs} />
              <StatCard
                label="Конверсія"
                value={stats.conversion != null ? `${stats.conversion}%` : '—'}
                sub="заявок від діалогів"
                accent
              />
            </div>

            {/* Charts */}
            <div className="charts-row">
              <ChartSection
                title="Нові користувачі (30 днів)"
                labels={charts.users_daily?.labels || []}
                values={charts.users_daily?.values || []}
                color="#ff6b35"
              />
              <ChartSection
                title="Повідомлення (30 днів)"
                labels={charts.messages_daily?.labels || []}
                values={charts.messages_daily?.values || []}
                color="#0066ff"
              />
            </div>

            {/* Leads by category */}
            {leadsByCategory.length > 0 && (
              <div className="card leads-breakdown">
                <div className="chart-title">Заявки за категоріями</div>
                <div className="progress-list">
                  {leadsByCategory.map((cat) => (
                    <ProgressBar
                      key={cat.category}
                      label={cat.category}
                      value={cat.count}
                      max={maxLeadCat}
                      color="#ff6b35"
                    />
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <style>{`
        .analytics-stats-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
          margin-bottom: 24px;
        }
        .analytics-stat-card {
          padding: 20px 22px;
          border-radius: var(--radius);
        }
        .analytics-stat-accent { border-top: 3px solid var(--accent); }
        .analytics-stat-value { font-size: 30px; font-weight: 800; color: var(--text-primary); line-height: 1.1; }
        .analytics-stat-accent .analytics-stat-value { color: var(--accent); }
        .analytics-stat-label { font-size: 12.5px; color: var(--text-muted); margin-top: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
        .analytics-stat-sub { font-size: 11.5px; color: var(--text-muted); margin-top: 3px; }
        .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
        .chart-card { padding: 20px 22px; border-radius: var(--radius); }
        .chart-title { font-size: 13.5px; font-weight: 700; color: var(--text-primary); margin-bottom: 14px; }
        .chart-canvas { width: 100%; height: auto; display: block; }
        .leads-breakdown { padding: 20px 22px; margin-bottom: 24px; border-radius: var(--radius); }
        .progress-list { display: flex; flex-direction: column; gap: 12px; }
        .progress-row { display: flex; align-items: center; gap: 12px; }
        .progress-label { width: 140px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); font-weight: 500; }
        .progress-track { flex: 1; height: 8px; background: var(--border-light); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.4s ease; }
        .progress-value { width: 36px; text-align: right; font-size: 13px; font-weight: 700; color: var(--text-primary); }
        .error-msg { padding: 12px 16px; background: #fef2f2; border: 1px solid #fecaca; border-radius: var(--radius-sm); color: #dc2626; font-size: 13.5px; }

        @media (max-width: 1100px) {
          .analytics-stats-grid { grid-template-columns: repeat(2, 1fr); }
          .charts-row { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  );
}
