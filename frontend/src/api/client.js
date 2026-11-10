export function resolveApiUrl(endpoint) {
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    return endpoint;
  }

  // Read configured base URL and strip trailing slashes
  let base = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api').trim().replace(/\/+$/, '');

  // Normalize endpoint to start with a slash
  const cleanPath = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  // Ensure /api prefix is consistently applied without duplication
  if (!base.endsWith('/api') && !cleanPath.startsWith('/api/') && cleanPath !== '/api') {
    base = `${base}/api`;
  } else if (base.endsWith('/api') && cleanPath.startsWith('/api/')) {
    base = base.slice(0, -4);
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
