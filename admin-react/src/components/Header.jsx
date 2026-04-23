// Top gradient header bar matching variant2 topbar design

export default function Header({ title, subtitle, stats = [] }) {
  return (
    <header className="topbar">
      <div>
        <span className="topbar-title">{title}</span>
        {subtitle && <span className="topbar-sub">/ {subtitle}</span>}
      </div>
      {stats.length > 0 && (
        <div className="topbar-right">
          {stats.map((s, i) => (
            <div key={i} className="stat-chip">
              <div className={`stat-dot${s.variant ? ' ' + s.variant : ''}`} />
              <span className="stat-chip-val">{s.value}</span>
              <span className="stat-chip-label">{s.label}</span>
            </div>
          ))}
        </div>
      )}

      <style>{`
        .topbar {
          background: linear-gradient(135deg, #ff6b35 0%, #ff4500 40%, #0066ff 100%);
          padding: 0 24px;
          height: 60px;
          min-height: 60px;
          display: flex;
          align-items: center;
          gap: 16px;
          box-shadow: 0 2px 16px rgba(255,107,53,0.3);
          flex-shrink: 0;
        }
        .topbar-title { font-size: 16px; font-weight: 700; color: #fff; }
        .topbar-sub { font-size: 12px; color: rgba(255,255,255,0.7); margin-left: 4px; }
        .topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
        .stat-chip {
          display: flex; align-items: center; gap: 7px;
          background: rgba(255,255,255,0.18);
          border: 1px solid rgba(255,255,255,0.25);
          border-radius: 20px;
          padding: 6px 14px;
          color: #fff; font-size: 12.5px;
          backdrop-filter: blur(8px);
        }
        .stat-chip-val { font-weight: 700; }
        .stat-chip-label { opacity: 0.8; }
        .stat-dot { width: 7px; height: 7px; border-radius: 50%; background: rgba(255,255,255,0.6); }
        .stat-dot.online { background: #86efac; }
        .stat-dot.warn { background: #fde68a; }
      `}</style>
    </header>
  );
}
