import { auth } from './firebase';

const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

async function withAuthHeaders() {
  const user = auth.currentUser;
  if (!user) return {};
  const token = await user.getIdToken();
  return {
    Authorization: `Bearer ${token}`,
  };
}

export async function apiGet(path) {
  const headers = await withAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    headers,
  });
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function apiPost(path, body, method = 'POST') {
  const headers = await withAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`${method} ${path} failed: ${res.status}`);
  }
  return res.json();
}

