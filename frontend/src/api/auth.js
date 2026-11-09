import apiClient from './client';

export const authApi = {
  getAuthUrl: () => apiClient('/auth/github/url'),
  getCurrentUser: () => apiClient('/auth/me'),
  logout: () => apiClient('/auth/logout', { method: 'POST' }),
};
