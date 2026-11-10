import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { repositoriesApi } from '../api/repositories';
import { useAuth } from '../context/AuthContext';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  FolderGit2,
  Search,
  ArrowRight,
  RefreshCw,
  Lock,
  Globe,
  Loader2,
  GitBranch,
  ExternalLink,
  ShieldAlert,
  PlusCircle,
  Github,
} from 'lucide-react';

export default function RepositorySelectionPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');

  // 1. Fetch repositories accessible to the user
  const {
    data: rawRepos = [],
    isLoading: isReposLoading,
    error: reposError,
    refetch: refetchRepos,
  } = useQuery({
    queryKey: ['repositories', searchTerm],
    queryFn: () => repositoriesApi.list({ q: searchTerm }),
  });

  // 2. Fetch GitHub App installation status
  const {
    data: installStatus,
    isLoading: isInstallLoading,
    refetch: refetchInstallStatus,
  } = useQuery({
    queryKey: ['installation-status'],
    queryFn: repositoriesApi.getInstallationStatus,
    retry: 1,
  });

  const repos = Array.isArray(rawRepos) ? rawRepos : rawRepos?.repositories || [];
  const hasInstallations = installStatus?.has_installations ?? (repos.length > 0);
  const installUrl =
    installStatus?.install_url ||
    'https://github.com/apps/impactintel/installations/new';

  const filteredRepos = repos.filter((r) =>
    (r.full_name || r.name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleSelectRepo = (repo) => {
    const repoIdentifier = encodeURIComponent(repo.full_name || `${repo.owner}/${repo.name}`);
    if (repo.indexing_status === 'INDEXED') {
      navigate(`/repositories/${repoIdentifier}/overview`);
    } else {
      navigate(`/repositories/${repoIdentifier}/indexing`);
    }
  };

  const handleRefreshAll = () => {
    refetchRepos();
    refetchInstallStatus();
  };

  const isLoading = isReposLoading || isInstallLoading;

  return (
    <div className="min-h-screen bg-[#F5FAFA] flex flex-col text-[#172B35] font-sans selection:bg-[#DDF7EF] selection:text-[#087F70]">
      <Header
        title="Repository Selection"
        subtitle="Select an authorized repository to explore impact and intelligence"
        breadcrumbs={['Home', 'Repositories']}
      />

      <main className="p-5 sm:p-6 max-w-6xl w-full mx-auto flex-1">
        {/* Header Toolbar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#172B35] tracking-tight">
              Connected Repositories
            </h2>
            <p className="text-xs text-[#6B818B] mt-0.5 max-w-xl">
              Select an authorized repository from your GitHub App installation to inspect pull requests, trace dependency graphs, and run impact analysis.
            </p>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <div className="relative w-full sm:w-64">
              <Search className="w-3.5 h-3.5 text-[#6B818B] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search repositories..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-white border border-[#E1ECEE] text-xs text-[#172B35] placeholder-[#6B818B] focus:outline-none focus:border-[#16B89A] shadow-sm"
              />
            </div>

            <a
              href={installUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white border border-[#E1ECEE] hover:border-[#16B89A] text-xs font-semibold text-[#172B35] hover:text-[#087F70] shadow-sm transition-colors whitespace-nowrap"
              title="Add more repositories or configure GitHub App permissions"
            >
              <PlusCircle className="w-3.5 h-3.5 text-[#16B89A]" />
              <span>Configure App</span>
            </a>

            <button
              onClick={handleRefreshAll}
              className="p-1.5 rounded-lg bg-white border border-[#E1ECEE] hover:border-[#16B89A] text-[#6B818B] hover:text-[#087F70] shadow-sm transition-colors cursor-pointer"
              title="Refresh repository list"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-20 text-[#6B818B]">
            <Loader2 className="w-7 h-7 animate-spin text-[#16B89A] mb-2.5" />
            <div className="text-xs font-mono font-medium">Loading authorized repositories from GitHub...</div>
          </div>
        )}

        {/* Error state */}
        {!isLoading && reposError && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs mb-5 shadow-sm flex items-start gap-3">
            <ShieldAlert className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <div className="font-semibold text-rose-900 mb-0.5">Failed to load repositories</div>
              <div>{reposError.message}</div>
              <div className="mt-2">
                <button
                  onClick={handleRefreshAll}
                  className="px-3 py-1 rounded bg-rose-600 text-white font-semibold text-[11px] hover:bg-rose-700 transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}

        {/* State 1: GitHub App is NOT installed on user's account */}
        {!isLoading && !hasInstallations && (
          <div className="p-8 sm:p-12 text-center rounded-2xl bg-white border border-[#E1ECEE] shadow-card max-w-2xl mx-auto my-8">
            <div className="w-12 h-12 rounded-xl bg-[#DDF7EF] border border-[#16B89A]/30 text-[#087F70] flex items-center justify-center mx-auto mb-4">
              <Github className="w-6 h-6 text-[#16B89A]" />
            </div>
            <h3 className="text-base sm:text-lg font-bold text-[#172B35] mb-2">
              GitHub App Installation Required
            </h3>
            <p className="text-xs text-[#6B818B] leading-relaxed max-w-lg mx-auto mb-6">
              ImpactIntel needs permission to access your repositories through our GitHub App. Install the app on your personal account or organization and choose which repositories to analyze.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href={installUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all"
              >
                <Github className="w-4 h-4" />
                <span>Install ImpactIntel on GitHub</span>
                <ExternalLink className="w-3.5 h-3.5 ml-1" />
              </a>

              <button
                onClick={handleRefreshAll}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white border border-[#E1ECEE] hover:border-[#16B89A] text-xs font-semibold text-[#172B35] transition-all"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>I've Installed It — Refresh</span>
              </button>
            </div>
          </div>
        )}

        {/* State 2: App is installed, but 0 repositories granted */}
        {!isLoading && hasInstallations && filteredRepos.length === 0 && (
          <div className="p-8 sm:p-12 text-center rounded-2xl bg-white border border-[#E1ECEE] shadow-card max-w-2xl mx-auto my-8">
            <div className="w-12 h-12 rounded-xl bg-[#E2F4FC] border border-[#55BDEB]/30 text-[#258FC7] flex items-center justify-center mx-auto mb-4">
              <FolderGit2 className="w-6 h-6 text-[#258FC7]" />
            </div>
            <h3 className="text-base sm:text-lg font-bold text-[#172B35] mb-2">
              {searchTerm ? 'No Matching Repositories' : 'No Repositories Authorized'}
            </h3>
            <p className="text-xs text-[#6B818B] leading-relaxed max-w-lg mx-auto mb-6">
              {searchTerm
                ? `No repositories matched "${searchTerm}". Try a different search term or configure repository permissions on GitHub.`
                : 'The ImpactIntel GitHub App is installed, but no repositories are currently authorized. Grant access to your repositories in GitHub App settings to begin.'}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href={installUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all"
              >
                <PlusCircle className="w-4 h-4" />
                <span>Configure Repository Access</span>
                <ExternalLink className="w-3.5 h-3.5 ml-0.5" />
              </a>

              <button
                onClick={handleRefreshAll}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-white border border-[#E1ECEE] hover:border-[#16B89A] text-xs font-semibold text-[#172B35] transition-all"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Refresh Repositories</span>
              </button>
            </div>
          </div>
        )}

        {/* State 3: Repositories grid */}
        {!isLoading && filteredRepos.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredRepos.map((repo) => {
              const fullName = repo.full_name || `${repo.owner}/${repo.name}`;
              const isIndexed = repo.indexing_status === 'INDEXED';

              return (
                <div
                  key={repo.id || fullName}
                  onClick={() => handleSelectRepo(repo)}
                  className="p-5 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#16B89A]/60 hover:shadow-card-hover shadow-card transition-all cursor-pointer group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-[#DDF7EF] flex items-center justify-center text-[#087F70] shrink-0">
                          <FolderGit2 className="w-4 h-4" />
                        </div>
                        <h3 className="text-xs font-bold text-[#172B35] group-hover:text-[#087F70] transition-colors font-mono truncate">
                          {fullName}
                        </h3>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {repo.private ? (
                          <span title="Private repository" className="text-[#6B818B]">
                            <Lock className="w-3.5 h-3.5" />
                          </span>
                        ) : (
                          <span title="Public repository" className="text-[#6B818B]">
                            <Globe className="w-3.5 h-3.5" />
                          </span>
                        )}

                        <Badge variant={isIndexed ? 'success' : 'neutral'}>
                          {isIndexed ? 'Indexed' : 'Not Indexed'}
                        </Badge>
                      </div>
                    </div>

                    <p className="text-xs text-[#6B818B] mb-4 line-clamp-2 leading-relaxed">
                      {repo.description || 'Connected repository accessible through your authorized GitHub App installation.'}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-[#E1ECEE] flex items-center justify-between text-xs text-[#6B818B] font-mono">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <GitBranch className="w-3.5 h-3.5 text-[#16B89A]" />
                        <span>{repo.default_branch || 'main'}</span>
                      </span>
                      {repo.language && (
                        <span className="px-1.5 py-0.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] text-[10px] text-[#087F70]">
                          {repo.language}
                        </span>
                      )}
                      {isIndexed && (
                        <span>nodes: <strong className="text-[#172B35]">{repo.total_nodes || 0}</strong></span>
                      )}
                    </div>

                    <span className="inline-flex items-center gap-1 text-[#087F70] font-semibold text-xs group-hover:translate-x-0.5 transition-transform">
                      <span>{isIndexed ? 'Overview' : 'Index'}</span>
                      <ArrowRight className="w-3 h-3" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
