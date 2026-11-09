import apiClient from './client';

export const chatApi = {
  ask: (owner, repo, payload) =>
    apiClient(`/repos/${owner}/${repo}/chat`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getHistory: (owner, repo, conversationId) =>
    apiClient(`/repos/${owner}/${repo}/chat/${conversationId}`),
};
