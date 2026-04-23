// Buttons page — placeholder (full implementation via existing /buttons admin route)
import Header from '../components/Header.jsx';

export default function Buttons() {
  return (
    <div className="page-wrap">
      <Header title="Кнопки" subtitle="Динамічне меню" />
      <div className="page-content">
        <div style={{ maxWidth: 600 }}>
          <div className="card" style={{ padding: '32px 36px', textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>🔘</div>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 8 }}>
              Управління кнопками
            </div>
            <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 24 }}>
              Ця сторінка дозволяє налаштовувати динамічні кнопки меню Telegram-бота.
              Кнопки відображаються користувачам і запускають відповідні дії.
            </p>
            <a
              href="/buttons"
              className="btn-primary"
              style={{ display: 'inline-flex', textDecoration: 'none' }}
            >
              Відкрити редактор кнопок
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
