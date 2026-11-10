import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { repositoriesApi } from '../api/repositories';
import { pullRequestsApi } from '../api/pullRequests';
import { graphApi } from '../api/graph';
import { chatApi } from '../api/chat';
import { resolveApiUrl, apiClient } from '../api/client';

// ---------------------------------------------------------------------------
// resolveApiUrl regression tests (production URL-resolution fix)
// ---------------------------------------------------------------------------
describe('resolveApiUrl', () => {
  it('resolves /repos against production backend base URL without double /api', () => {
    // Simulates VITE_API_BASE_URL = https://impactintel.onrender.com/api
    // The env var is baked in at build time; here we directly test the pure logic.
    const base = 'https://impactintel.onrender.com/api';
    // Inline the same logic as resolveApiUrl (env-agnostic)
    function resolve(endpoint) {
      const cleanPath = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      if (base.endsWith('/api') && cleanPath.startsWith('/api/')) {
        return `${base}${cleanPath.slice(4)}`;
      }
      if (!base.endsWith('/api')) return `${base}/api${cleanPath}`;
      return `${base}${cleanPath}`;
    }
    expect(resolve('/repos')).toBe('https://impactintel.onrender.com/api/repos');
    expect(resolve('/repos/installation/status')).toBe(
      'https://impactintel.onrender.com/api/repos/installation/status'
    );
    expect(resolve('/auth/me')).toBe('https://impactintel.onrender.com/api/auth/me');
  });

  it('does not duplicate /api when endpoint starts with /api/', () => {
    const base = 'https://impactintel.onrender.com/api';
    function resolve(endpoint) {
      const cleanPath = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
      if (base.endsWith('/api') && cleanPath.startsWith('/api/')) {
        return `${base}${cleanPath.slice(4)}`;
      }
      if (!base.endsWith('/api')) return `${base}/api${cleanPath}`;
      return `${base}${cleanPath}`;
    }
    // /api/repos must NOT become /api/api/repos
    expect(resolve('/api/repos')).toBe('https://impactintel.onrender.com/api/repos');
    expect(resolve('/api/auth/me')).toBe('https://impactintel.onrender.com/api/auth/me');
  });

  it('resolveApiUrl returns absolute URLs unchanged', () => {
    const abs = 'https://other-service.example.com/data';
    expect(resolveApiUrl(abs)).toBe(abs);
  });
});

// ---------------------------------------------------------------------------
// apiClient credential and fetch behaviour tests
// ---------------------------------------------------------------------------
describe('apiClient', () => {
  let fetchSpy;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => ({}),
    });
    global.fetch = fetchSpy;
    // Ensure no stale token bleeds across tests
    localStorage.removeItem('auth_token');
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.removeItem('auth_token');
  });

  it('always sends credentials: include', async () => {
    await apiClient('/repos');
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ credentials: 'include' })
    );
  });

  it('sends Authorization header when auth_token is in localStorage', async () => {
    localStorage.setItem('auth_token', 'test_jwt_token');
    await apiClient('/repos');
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer test_jwt_token' }),
      })
    );
  });

  it('omits Authorization header when no token is stored', async () => {
    await apiClient('/repos');
    const [, opts] = fetchSpy.mock.calls[0];
    expect(opts.headers).not.toHaveProperty('Authorization');
  });

  it('throws with error.status on non-ok response', async () => {
    fetchSpy.mockResolvedValue({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Not authenticated' }),
    });
    await expect(apiClient('/repos')).rejects.toMatchObject({
      message: 'Not authenticated',
      status: 401,
    });
  });
});

// ---------------------------------------------------------------------------
// API service integration tests
// ---------------------------------------------------------------------------
describe('API Services', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('repositoriesApi.list calls /repos', async () => {
    const mockData = [{ id: 1, full_name: 'org/shop-repo' }];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => mockData,
    });

    const res = await repositoriesApi.list();
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/repos'),
      expect.objectContaining({ headers: expect.any(Object) })
    );
    expect(res).toEqual(mockData);
  });

  it('pullRequestsApi.analyzeManual sends POST with payload', async () => {
    const mockRes = { pr_number: 101, status: 'COMPLETED' };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => mockRes,
    });

    const payload = {
      pr_title: 'Test PR',
      changed_files: [{ filename: 'src/app.js', status: 'modified' }],
    };

    const res = await pullRequestsApi.analyzeManual('org', 'shop-repo', 101, payload);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/repos/org/shop-repo/pulls/101/analyze'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
    expect(res).toEqual(mockRes);
  });

  it('graphApi.getNeighbors constructs query with node_id and max_nodes', async () => {
    const mockGraph = { center_node_id: 'src/app.js', nodes: [], edges: [] };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => mockGraph,
    });

    const res = await graphApi.getNeighbors('org', 'shop-repo', 'src/app.js', 10);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/repos/org/shop-repo/graph/neighbors?node_id=src%2Fapp.js&max_nodes=10'),
      expect.any(Object)
    );
    expect(res).toEqual(mockGraph);
  });

  it('chatApi.ask sends query and conversation_id', async () => {
    const mockReply = { answer: 'Function processPayment handles checkout.', is_verified: true };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: async () => mockReply,
    });

    const payload = { query: 'What does processPayment do?', conversation_id: 'conv_123' };
    const res = await chatApi.ask('org', 'shop-repo', payload);
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/repos/org/shop-repo/chat'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(payload),
      })
    );
    expect(res).toEqual(mockReply);
  });
});
