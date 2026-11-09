import { describe, it, expect, vi, beforeEach } from 'vitest';
import { repositoriesApi } from '../api/repositories';
import { pullRequestsApi } from '../api/pullRequests';
import { graphApi } from '../api/graph';
import { chatApi } from '../api/chat';

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
