// ===== EGOLIST ADMIN — API HELPERS =====
// All API calls use fetch() with credentials: 'include' for session cookie auth

const BASE = '/api';

async function request(method, path, body) {
  const opts = {
    method,
    credentials: 'include',
    headers: {},
  };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw Object.assign(new Error(text || `HTTP ${res.status}`), { status: res.status });
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res.text();
}

// Auth
export const login = (username, password) =>
  request('POST', '/auth/login', { username, password });

export const logout = () =>
  request('POST', '/auth/logout');

export const getMe = () =>
  request('GET', '/auth/me');

// Chat sessions
export const getSessions = () =>
  request('GET', '/sessions');

export const getMessages = (sessionId, afterId = 0) =>
  request('GET', `/sessions/${sessionId}/messages?after_id=${afterId}`);

export const sendMessage = (sessionId, text) =>
  request('POST', `/sessions/${sessionId}/send`, { text });

export const setSessionStatus = (sessionId, status) =>
  request('POST', `/sessions/${sessionId}/status`, { status });

export const setSessionTag = (sessionId, tag) =>
  request('POST', `/sessions/${sessionId}/tag`, { tag });

export const markSessionRead = (sessionId) =>
  request('POST', `/sessions/${sessionId}/read`);

export const deleteSession = (sessionId) =>
  request('DELETE', `/sessions/${sessionId}`);

// Manager status
export const getManagerStatus = () =>
  request('GET', '/manager-status');

export const setManagerStatus = (online) =>
  request('POST', '/manager-status', { online });

// Quick replies
export const getQuickReplies = () =>
  request('GET', '/quick-replies');

export const createQuickReply = (title, content) =>
  request('POST', '/quick-replies', { title, content });

export const deleteQuickReply = (id) =>
  request('DELETE', `/quick-replies/${id}`);

// Analytics
export const getAnalytics = () =>
  request('GET', '/analytics');

// Leads
export const getLeads = () =>
  request('GET', '/leads');

export const updateLeadStatus = (leadId, status, note) =>
  request('POST', `/leads/${leadId}/status`, { status, note });

// Content
export const getPlaces = () =>
  request('GET', '/content/places');

export const createPlace = (data) =>
  request('POST', '/content/places', data);

export const updatePlace = (id, data) =>
  request('PUT', `/content/places/${id}`, data);

export const deletePlace = (id) =>
  request('DELETE', `/content/places/${id}`);

export const togglePlace = (id, published) =>
  request('POST', `/content/places/${id}/toggle`, { is_published: published });

export const getEvents = () =>
  request('GET', '/content/events');

export const createEvent = (data) =>
  request('POST', '/content/events', data);

export const updateEvent = (id, data) =>
  request('PUT', `/content/events/${id}`, data);

export const deleteEvent = (id) =>
  request('DELETE', `/content/events/${id}`);

export const toggleEvent = (id, published) =>
  request('POST', `/content/events/${id}/toggle`, { is_published: published });

// Buttons
export const getButtons = () =>
  request('GET', '/buttons');

export const createButton = (data) =>
  request('POST', '/buttons', data);

export const updateButton = (id, data) =>
  request('PUT', `/buttons/${id}`, data);

export const deleteButton = (id) =>
  request('DELETE', `/buttons/${id}`);

export const toggleButton = (id) =>
  request('POST', `/buttons/${id}/toggle`);

// Prompt
export const getPrompt = () =>
  request('GET', '/prompt');

export const savePrompt = (ai_prompt_extra) =>
  request('POST', '/prompt', { ai_prompt_extra });

// Settings
export const getSettings = () =>
  request('GET', '/settings');

export const saveSettings = (data) =>
  request('POST', '/settings', data);

export const testNotification = () =>
  request('POST', '/settings/test-notification');

// Karabas sync
export const syncKarabas = () =>
  request('POST', '/api/sync-karabas');
