import apiClient from './client';

export const repositoriesApi = {
  list: (params = {}) => {
    const query = new URLSearchParams();
    if (params.q) query.append('q', params.q);
    if (params.page) query.append('page', params.page);
    if (params.per_page) query.append('per_page', params.per_page);
    const queryString = query.toString();
    return apiClient(`/repos${queryString ? `?${queryString}` : ''}`);
  },
  getInstallationStatus: () => apiClient('/repos/installation/status'),
  getDetails: (owner, repo) => apiClient(`/repos/${owner}/${repo}`),
  remove: (owner, repo) => apiClient(`/repos/${owner}/${repo}`, { method: 'DELETE' }),
  triggerIndex: (owner, repo, payload = {}) =>
    apiClient(`/repos/${owner}/${repo}/index`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getIndexStatus: (owner, repo) => apiClient(`/repos/${owner}/${repo}/index/status`),
};
