import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../context/AuthContext';

import RepositorySelectionPage from '../pages/RepositorySelectionPage';
import DashboardPage from '../pages/DashboardPage';
import ImpactReportPage from '../pages/ImpactReportPage';
import RepositoryChatPage from '../pages/RepositoryChatPage';
import RepositorySettingsPage from '../pages/RepositorySettingsPage';

// Mock the API layer cleanly for component rendering tests
vi.mock('../api/auth', () => ({
  authApi: {
    getCurrentUser: vi.fn().mockResolvedValue({
      authenticated: true,
      user: { id: 1001, login: 'dev-user', name: 'Dev User' },
    }),
    getAuthUrl: vi.fn().mockResolvedValue({ url: '/auth/callback?code=mock' }),
    logout: vi.fn().mockResolvedValue({ status: 'logged_out' }),
  },
}));

vi.mock('../api/repositories', () => ({
  repositoriesApi: {
    list: vi.fn(),
    getDetails: vi.fn(),
    remove: vi.fn(),
    triggerIndex: vi.fn(),
    getIndexStatus: vi.fn(),
  },
}));

vi.mock('../api/pullRequests', () => ({
  pullRequestsApi: {
    list: vi.fn(),
    getAnalysis: vi.fn(),
    analyzeManual: vi.fn(),
  },
}));

vi.mock('../api/graph', () => ({
  graphApi: {
    getSummary: vi.fn(),
    searchNodes: vi.fn(),
    getNodeDetails: vi.fn(),
    getNeighbors: vi.fn(),
  },
}));

vi.mock('../api/chat', () => ({
  chatApi: {
    ask: vi.fn(),
    getHistory: vi.fn(),
  },
}));

import { repositoriesApi } from '../api/repositories';
import { pullRequestsApi } from '../api/pullRequests';
import { graphApi } from '../api/graph';
import { chatApi } from '../api/chat';

function renderWithRouter(ui, initialEntries = ['/']) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe('Detailed Pages Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('RepositorySelectionPage renders repo cards fetched from API', async () => {
    repositoriesApi.list.mockResolvedValue([
      {
        id: 1,
        full_name: 'org/shop-repo',
        owner: 'org',
        name: 'shop-repo',
        indexing_status: 'INDEXED',
        total_nodes: 42,
        total_edges: 52,
        languages: ['JavaScript', 'Python'],
      },
    ]);

    renderWithRouter(<RepositorySelectionPage />, ['/repositories']);

    await waitFor(() => {
      expect(screen.getByText('org/shop-repo')).toBeInTheDocument();
      expect(screen.getByText(/42/)).toBeInTheDocument();
      expect(screen.getByText('Indexed')).toBeInTheDocument();
    });
  });

  it('DashboardPage renders metrics and repository actions', async () => {
    repositoriesApi.getDetails.mockResolvedValue({
      id: 1,
      full_name: 'org/shop-repo',
      owner: 'org',
      name: 'shop-repo',
      indexing_status: 'INDEXED',
      branch: 'main',
      total_nodes: 42,
      total_edges: 52,
    });
    graphApi.getSummary.mockResolvedValue({
      repository: 'org/shop-repo',
      total_nodes: 42,
      total_edges: 52,
      node_type_counts: { Function: 21, File: 17, Component: 2, Class: 1, Test: 1 },
      top_modules: ['src', 'tests'],
    });
    pullRequestsApi.list.mockResolvedValue([]);

    renderWithRouter(
      <Routes>
        <Route path="/repositories/:repoId/overview" element={<DashboardPage />} />
      </Routes>,
      ['/repositories/org%2Fshop-repo/overview']
    );

    await waitFor(() => {
      expect(screen.getAllByText('org/shop-repo').length).toBeGreaterThan(0);
      expect(screen.getByText('Inspect PRs')).toBeInTheDocument();
      expect(screen.getByText('Ask AI Chat')).toBeInTheDocument();
      expect(screen.getByText('Graph Nodes')).toBeInTheDocument();
    });
  });

  it('ImpactReportPage displays affected components and dependency paths', async () => {
    pullRequestsApi.getAnalysis.mockResolvedValue({
      pr_number: 101,
      pr_title: 'Fix database connection pooling',
      status: 'COMPLETED',
      base_branch: 'main',
      base_commit_sha: 'HEAD',
      total_affected: 1,
      created_at: '2026-11-09T04:52:06.275237',
      report: {
        total_affected: 1,
        changed_files: ['src/database/database.js'],
        affected_components: [
          {
            file_path: 'src/services/paymentService.js',
            entity_type: 'File',
            depth: 1,
            impact_level: 'Direct (Depth 1)',
            dependency_path: ['src/database/database.js', 'src/services/paymentService.js'],
            related_tests: ['tests/payment.test.js'],
            confidence: 1.0,
            evidence: [{ line: 2, statement: 'import db', extractor: 'tree_sitter' }],
          },
        ],
        unaffected_files: [],
        unmapped_files: [],
      },
    });

    renderWithRouter(
      <Routes>
        <Route path="/repositories/:repoId/pull-requests/:prNumber" element={<ImpactReportPage />} />
      </Routes>,
      ['/repositories/shop-repo/pull-requests/101']
    );

    await waitFor(() => {
      const h2 = screen.getByRole('heading', { level: 2 });
      expect(h2.textContent).toBe('Fix database connection pooling');
      expect(screen.getAllByText(/src\/services\/paymentService\.js/).length).toBeGreaterThan(0);
      expect(screen.getByText(/Direct Caller/)).toBeInTheDocument();
    });
  });

  it('RepositoryChatPage renders conversational messages and handles input', async () => {
    chatApi.ask.mockResolvedValue({
      conversation_id: 'conv-test-123',
      answer: 'The processPayment function validates amount and charges account.',
      is_verified: true,
      retrieval_evidence: [
        {
          chunk_id: 'chunk_1',
          file_path: 'src/services/paymentService.js',
          symbol_name: 'processPayment',
          symbol_type: 'Function',
          start_line: 1,
          end_line: 10,
          content: 'export function processPayment() {}',
          rrf_score: 0.048,
        },
      ],
      identified_entities: ['processPayment'],
    });

    renderWithRouter(
      <Routes>
        <Route path="/repositories/:repoId/chat" element={<RepositoryChatPage />} />
      </Routes>,
      ['/repositories/shop-repo/chat']
    );

    expect(screen.getByText(/conversational repository impact assistant/i)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/Ask about functions, routes, callers/i);
    fireEvent.change(input, { target: { value: 'What does processPayment do?' } });
    await waitFor(() => expect(input.value).toBe('What does processPayment do?'));
    fireEvent.submit(input.closest('form'));

    await waitFor(() => {
      expect(chatApi.ask).toHaveBeenCalled();
      expect(screen.getByText(/processPayment function validates amount/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Grounded & Verified Evidence/i).length).toBeGreaterThanOrEqual(1);
    });
  });

  it('RepositorySettingsPage renders settings info and actions', async () => {
    repositoriesApi.getDetails.mockResolvedValue({
      id: 1,
      full_name: 'org/shop-repo',
      owner: 'org',
      name: 'shop-repo',
      default_branch: 'main',
      commit_sha: 'HEAD',
      indexing_status: 'INDEXED',
    });

    renderWithRouter(
      <Routes>
        <Route path="/repositories/:repoId/settings" element={<RepositorySettingsPage />} />
      </Routes>,
      ['/repositories/org%2Fshop-repo/settings']
    );

    await waitFor(() => {
      expect(screen.getByText('General Repository Details')).toBeInTheDocument();
      expect(screen.getByText('OAuth Active')).toBeInTheDocument();
      expect(screen.getByText('Trigger Re-index')).toBeInTheDocument();
      expect(screen.getByText('Danger Zone')).toBeInTheDocument();
    });
  });
});
