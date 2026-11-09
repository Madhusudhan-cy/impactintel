import apiClient from './client';

export const repositoriesApi = {
  list: () => apiClient('/repos'),
  getDetails: (owner, repo) => apiClient(`/repos/${owner}/${repo}`),
  remove: (owner, repo) => apiClient(`/repos/${owner}/${repo}`, { method: 'DELETE' }),
  triggerIndex: (owner, repo, payload = {}) =>
    apiClient(`/repos/${owner}/${repo}/index`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getIndexStatus: (owner, repo) => apiClient(`/repos/${owner}/${repo}/index/status`),
};
