const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8010';
const DEFAULT_PROFILE = import.meta.env.VITE_DEFAULT_PROFILE_ID || 'profile_alex';

async function parseResponse(response) {
  if (!response.ok) {
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const payload = await response.json();
      const message = payload?.detail || payload?.message || JSON.stringify(payload);
      throw new Error(message || `Request failed (${response.status})`);
    }
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  return response.json();
}

export async function getHome(profileId = DEFAULT_PROFILE) {
  const response = await fetch(`${API_BASE_URL}/api/home?profile_id=${encodeURIComponent(profileId)}`);
  return parseResponse(response);
}

export async function searchShows(query) {
  const response = await fetch(`${API_BASE_URL}/api/search?q=${encodeURIComponent(query)}`);
  return parseResponse(response);
}

export async function getRecommendations(profileId = DEFAULT_PROFILE) {
  const response = await fetch(`${API_BASE_URL}/api/recommendations?profile_id=${encodeURIComponent(profileId)}`);
  return parseResponse(response);
}

export async function postSessionEvent(payload) {
  const response = await fetch(`${API_BASE_URL}/api/session/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export { DEFAULT_PROFILE };
