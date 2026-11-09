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
} from 'lucide-react';

export default function RepositorySelectionPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');

  const { data: repos = [], isLoading, error, refetch } = useQuery({
    queryKey: ['repositories'],
    queryFn: repositoriesApi.list,
  });

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

  return (
    <div className="min-h-screen bg-[#F5FAFA] flex flex-col text-[#172B35] font-sans selection:bg-[#DDF7EF] selection:text-[#087F70]">
      <Header
        title="Repository Selection"
        subtitle="Select a connected repository to explore impact and intelligence"
        breadcrumbs={['Home', 'Repositories']}
      />

      <main className="p-5 sm:p-6 max-w-6xl w-full mx-auto flex-1">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#172B35] tracking-tight">
              Connected Repositories
            </h2>
            <p className="text-xs text-[#6B818B] mt-0.5 max-w-xl">
              Select a repository to inspect pull requests, trace dependency graphs, and query code intelligence with Prathiksha.
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

            <button
              onClick={() => refetch()}
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
            <div className="text-xs font-mono font-medium">Loading repositories from backend...</div>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs mb-5 shadow-sm">
            Failed to load repositories: {error.message}
          </div>
        )}

        {/* Repositories grid */}
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
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg bg-[#DDF7EF] flex items-center justify-center text-[#087F70] shrink-0">
                          <FolderGit2 className="w-4 h-4" />
                        </div>
                        <h3 className="text-xs font-bold text-[#172B35] group-hover:text-[#087F70] transition-colors font-mono">
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
                      {repo.description || 'Full-stack application repository ready for Code Knowledge Graph analysis.'}
                    </p>
                  </div>

                  <div className="pt-3 border-t border-[#E1ECEE] flex items-center justify-between text-xs text-[#6B818B] font-mono">
                    <div className="flex items-center gap-3">
                      <span className="flex items-center gap-1">
                        <GitBranch className="w-3.5 h-3.5 text-[#16B89A]" />
                        <span>{repo.default_branch || 'main'}</span>
                      </span>
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

        {!isLoading && filteredRepos.length === 0 && (
          <div className="p-10 text-center rounded-xl bg-white border border-[#E1ECEE] text-[#6B818B] text-xs font-mono">
            No repositories found matching "{searchTerm}".
          </div>
        )}
      </main>
    </div>
  );
}
