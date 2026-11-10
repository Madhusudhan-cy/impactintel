export function resolveApiUrl(endpoint) {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }

  // Read configured base URL and strip trailing slashes.
  // VITE_API_BASE_URL must be set in Vercel environment variables to point at
  // the production backend: https://impactintel.onrender.com/api
  const base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').trim().replace(/\/+$/, '');

  // Normalize endpoint: ensure it starts with exactly one slash
  const cleanPath = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  // Guard against accidental /api duplication: if the base already ends with /api
  // and the endpoint also starts with /api/, strip the prefix from the endpoint to
  // prevent double /api/api/... in the final URL.
  if (base.endsWith('/api') && cleanPath.startsWith('/api/')) {
    // e.g. base="https://host/api" + cleanPath="/api/repos" → "https://host/api/repos"
    return `${base}${cleanPath.slice(4)}`;
  }

  // If base does not include an /api segment at all, append it so that all
  // service endpoints (/repos, /auth/me, …) resolve under /api automatically.
  if (!base.endsWith('/api')) {
    return `${base}/api${cleanPath}`;
  }

  return `${base}${cleanPath}`;
}

export async function apiClient(endpoint, options = {}) {
  const token = localStorage.getItem('auth_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const url = resolveApiUrl(endpoint);

  const response = await fetch(url, {
    // Include cookies for session-based authentication flows in addition to
    // the JWT Bearer token carried via the Authorization header.
    credentials: 'include',
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = 'An unexpected error occurred';
    try {
      const data = await response.json();
      errorDetail = data.detail || data.message || JSON.stringify(data);
    } catch {
      errorDetail = response.statusText;
    }
    const error = new Error(errorDetail);
    error.status = response.status;
    throw error;
  }

  // Handle empty responses
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return response.json();
  }
  return response.text();
}

export default apiClient;
