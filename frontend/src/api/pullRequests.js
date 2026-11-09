import apiClient from './client';

export const pullRequestsApi = {
  list: (owner, repo) => apiClient(`/repos/${owner}/${repo}/pulls`),
  getAnalysis: (owner, repo, prNumber) => apiClient(`/repos/${owner}/${repo}/pulls/${prNumber}`),
  analyzeManual: (owner, repo, prNumber, payload) =>
    apiClient(`/repos/${owner}/${repo}/pulls/${prNumber}/analyze`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
