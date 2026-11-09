import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '../context/AuthContext';
import Badge from '../components/common/Badge';
import Header from '../components/common/Header';
import Sidebar from '../components/common/Sidebar';
import LandingPage from '../pages/LandingPage';
import { PrathikshaProvider } from '../components/prathiksha/PrathikshaContext';
import PrathikshaWidget from '../components/prathiksha/PrathikshaWidget';

function renderWithProviders(ui) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>{ui}</BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe('Frontend Components & Pages', () => {
  it('renders Badge with correct variant styling', () => {
    const { rerender } = render(<Badge variant="success">Indexed</Badge>);
    expect(screen.getByText('Indexed')).toBeInTheDocument();
    expect(screen.getByText('Indexed')).toHaveClass('bg-emerald-500/10');

    rerender(<Badge variant="danger">Failed</Badge>);
    expect(screen.getByText('Failed')).toHaveClass('bg-rose-500/10');
  });

  it('renders Header with title and breadcrumbs', () => {
    renderWithProviders(
      <Header
        title="Impact Report"
        subtitle="org/shop-repo"
        breadcrumbs={['Repositories', 'org/shop-repo', 'PR #101']}
      />
    );
    expect(screen.getByText('Impact Report')).toBeInTheDocument();
    expect(screen.getByText('PR #101')).toBeInTheDocument();
  });

  it('renders Sidebar with repository navigation links and no chat in main navigation', () => {
    renderWithProviders(<Sidebar repoInfo={{ owner: 'org', name: 'shop-repo' }} />);
    expect(screen.getByText('Overview')).toBeInTheDocument();
    expect(screen.getByText('Pull Requests')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
    expect(screen.getByText('Analysis History')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.queryByText('Repository AI Chat')).not.toBeInTheDocument();
    expect(screen.queryByText('Prathiksha AI')).not.toBeInTheDocument();
  });

  it('renders LandingPage hero section and call to actions, with preview section removed', () => {
    renderWithProviders(<LandingPage />);
    expect(screen.getByText(/Know the exact impact of every code change/i)).toBeInTheDocument();
    expect(screen.getByText(/Evidence-Grounded Code Blast-Radius Intelligence/i)).toBeInTheDocument();

    // Verify repository preview panel is completely removed
    expect(screen.queryByText(/3 Hops Transitive/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/42 Nodes • 52 Edges Indexed/i)).not.toBeInTheDocument();
  });

  it('renders Prathiksha floating launcher and displays exact welcome message with suggestions', () => {
    renderWithProviders(
      <PrathikshaProvider>
        <PrathikshaWidget />
      </PrathikshaProvider>
    );

    const launcher = screen.getByRole('button', { name: /Open Prathiksha assistant/i });
    expect(launcher).toBeInTheDocument();

    fireEvent.click(launcher);

    expect(screen.getByText("Hey, I'm Prathiksha! How can I help you?")).toBeInTheDocument();
    expect(
      screen.getByText(/I'm your repository assistant. I can help you understand your codebase/i)
    ).toBeInTheDocument();

    expect(screen.getByText('Explain a function or module')).toBeInTheDocument();
    expect(screen.getByText('Analyze code dependencies')).toBeInTheDocument();
    expect(screen.getByText('Find related tests')).toBeInTheDocument();
    expect(screen.getByText('Explain this pull request')).toBeInTheDocument();
  });
});
