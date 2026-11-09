import apiClient from './client';

export const graphApi = {
  getSummary: (owner, repo) => apiClient(`/repos/${owner}/${repo}/graph/summary`),
  searchNodes: (owner, repo, params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiClient(`/repos/${owner}/${repo}/graph/nodes${query ? `?${query}` : ''}`);
  },
  getNodeDetails: (owner, repo, nodeId) =>
    apiClient(`/repos/${owner}/${repo}/graph/node?node_id=${encodeURIComponent(nodeId)}`),
  getNeighbors: (owner, repo, nodeId, maxNodes = 25) => {
    const query = new URLSearchParams({
      ...(nodeId ? { node_id: nodeId } : {}),
      max_nodes: maxNodes,
    }).toString();
    return apiClient(`/repos/${owner}/${repo}/graph/neighbors?${query}`);
  },
};
