import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './context/AuthContext';

import Layout from './components/common/Layout';
import LandingPage from './pages/LandingPage';
import GitHubCallbackPage from './pages/GitHubCallbackPage';
import RepositorySelectionPage from './pages/RepositorySelectionPage';
import IndexingPage from './pages/IndexingPage';
import DashboardPage from './pages/DashboardPage';
import PullRequestsPage from './pages/PullRequestsPage';
import ImpactReportPage from './pages/ImpactReportPage';
import GraphExplorerPage from './pages/GraphExplorerPage';
import RepositoryChatPage from './pages/RepositoryChatPage';
import AnalysisHistoryPage from './pages/AnalysisHistoryPage';
import RepositorySettingsPage from './pages/RepositorySettingsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Landing & Auth */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/auth/callback" element={<GitHubCallbackPage />} />

            {/* Repositories Hub */}
            <Route path="/repositories" element={<RepositorySelectionPage />} />
            <Route path="/repositories/:repoId/indexing" element={<IndexingPage />} />

            {/* Repository Main Dashboard & Navigation */}
            <Route path="/repositories/:repoId" element={<Layout />}>
              <Route index element={<Navigate to="overview" replace />} />
              <Route path="overview" element={<DashboardPage />} />
              <Route path="pull-requests" element={<PullRequestsPage />} />
              <Route path="pull-requests/:prNumber" element={<ImpactReportPage />} />
              <Route path="graph" element={<GraphExplorerPage />} />
              <Route path="chat" element={<RepositoryChatPage />} />
              <Route path="history" element={<AnalysisHistoryPage />} />
              <Route path="settings" element={<RepositorySettingsPage />} />
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
