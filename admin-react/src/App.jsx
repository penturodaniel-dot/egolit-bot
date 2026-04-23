import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { useState, useEffect, createContext, useContext } from 'react';
import { getMe } from './api.js';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import Chats from './pages/Chats.jsx';
import Leads from './pages/Leads.jsx';
import Analytics from './pages/Analytics.jsx';
import Content from './pages/Content.jsx';
import Prompt from './pages/Prompt.jsx';
import Settings from './pages/Settings.jsx';
import Buttons from './pages/Buttons.jsx';

// Auth context
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// Protected route wrapper — redirects to /login if not authenticated
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Завантаження...</div>
        </div>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

export default function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMe()
      .then((data) => {
        setUser(data);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const authValue = { user, setUser, loading };

  return (
    <AuthContext.Provider value={authValue}>
      <Routes>
        {/* Public route */}
        <Route path="/login" element={<Login />} />

        {/* Root redirect */}
        <Route path="/" element={<Navigate to="/chats" replace />} />

        {/* Protected routes */}
        <Route
          path="/chats"
          element={
            <RequireAuth>
              <Layout>
                <Chats />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/chats/:sessionId"
          element={
            <RequireAuth>
              <Layout>
                <Chats />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/leads"
          element={
            <RequireAuth>
              <Layout>
                <Leads />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/analytics"
          element={
            <RequireAuth>
              <Layout>
                <Analytics />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/content"
          element={
            <RequireAuth>
              <Layout>
                <Content />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/buttons"
          element={
            <RequireAuth>
              <Layout>
                <Buttons />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/prompt"
          element={
            <RequireAuth>
              <Layout>
                <Prompt />
              </Layout>
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <Layout>
                <Settings />
              </Layout>
            </RequireAuth>
          }
        />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/chats" replace />} />
      </Routes>
    </AuthContext.Provider>
  );
}
