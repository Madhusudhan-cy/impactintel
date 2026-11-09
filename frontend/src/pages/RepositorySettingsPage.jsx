import React, { useState } from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { repositoriesApi } from '../api/repositories';
import { useAuth } from '../context/AuthContext';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  FolderGit2,
  RotateCw,
  Trash2,
  Github,
} from 'lucide-react';

export default function RepositorySettingsPage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const outletCtx = useOutletContext();
  const { user, logout } = useAuth();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [confirmDelete, setConfirmDelete] = useState(false);

  const { data: details, refetch } = useQuery({
    queryKey: ['repo-details', owner, repo],
    queryFn: () => repositoriesApi.getDetails(owner, repo),
  });

  const reindexMutation = useMutation({
    mutationFn: () => repositoriesApi.triggerIndex(owner, repo, { branch: 'main', commit_sha: 'HEAD' }),
    onSuccess: () => {
      refetch();
    },
  });

  const removeMutation = useMutation({
    mutationFn: () => repositoriesApi.remove(owner, repo),
    onSuccess: () => {
      navigate('/repositories');
    },
  });

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#F5FAFA]">
      <Header
        title="Repository Settings"
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'Settings']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <main className="p-5 sm:p-6 max-w-4xl w-full mx-auto space-y-5">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-[#172B35] tracking-tight">
            Repository Configuration
          </h2>
          <p className="text-xs text-[#6B818B] mt-0.5">
            Manage indexing schedules, connected OAuth permissions, and local database storage.
          </p>
        </div>

        {/* General Information Card */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card space-y-3">
          <h3 className="text-xs font-bold text-[#172B35] flex items-center gap-2">
            <FolderGit2 className="w-4 h-4 text-[#16B89A]" />
            <span>General Repository Details</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE]">
              <div className="text-[#6B818B] uppercase text-[10px] font-bold">Full Name</div>
              <div className="text-[#172B35] font-semibold mt-0.5">{details?.full_name || decodedRepo}</div>
            </div>

            <div className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE]">
              <div className="text-[#6B818B] uppercase text-[10px] font-bold">Default Branch</div>
              <div className="text-[#172B35] font-semibold mt-0.5">{details?.default_branch || 'main'}</div>
            </div>

            <div className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE]">
              <div className="text-[#6B818B] uppercase text-[10px] font-bold">Indexed Commit</div>
              <div className="text-[#172B35] font-semibold mt-0.5 truncate">{details?.commit_sha || 'HEAD'}</div>
            </div>

            <div className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE]">
              <div className="text-[#6B818B] uppercase text-[10px] font-bold">Indexing Status</div>
              <div className="text-[#087F70] font-bold mt-0.5">{details?.indexing_status || 'INDEXED'}</div>
            </div>
          </div>
        </div>

        {/* Connected GitHub Account Card */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] flex items-center justify-center text-[#172B35]">
              <Github className="w-4.5 h-4.5" />
            </div>
            <div>
              <div className="text-xs font-bold text-[#172B35] flex items-center gap-1.5">
                <span>@{user?.login || 'dev-user'}</span>
                <Badge variant="success">OAuth Active</Badge>
              </div>
              <div className="text-[11px] text-[#6B818B] font-mono mt-0.5">
                Authorized with repository access scopes
              </div>
            </div>
          </div>

          <button
            onClick={logout}
            className="px-3 py-1.5 rounded-lg bg-white hover:bg-[#F5FAFA] text-[#6B818B] hover:text-rose-600 border border-[#E1ECEE] text-xs font-semibold shadow-sm transition-colors cursor-pointer"
          >
            Disconnect Account
          </button>
        </div>

        {/* Re-indexing Card */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h4 className="text-xs font-bold text-[#172B35]">Re-index Knowledge Graph</h4>
            <p className="text-[11px] text-[#6B818B] mt-0.5">
              Re-scan the repository tree, regenerate AST symbols, and update embeddings.
            </p>
          </div>

          <button
            onClick={() => reindexMutation.mutate()}
            disabled={reindexMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
          >
            <RotateCw className={`w-3.5 h-3.5 ${reindexMutation.isPending ? 'animate-spin' : ''}`} />
            <span>{reindexMutation.isPending ? 'Re-indexing...' : 'Trigger Re-index'}</span>
          </button>
        </div>

        {/* Danger Zone */}
        <div className="p-5 rounded-xl bg-rose-50/40 border border-rose-200 shadow-card space-y-3">
          <div>
            <h4 className="text-xs font-bold text-rose-700">Danger Zone</h4>
            <p className="text-[11px] text-[#6B818B] mt-0.5">
              Remove this repository from this platform's local database. This action does <strong>not</strong> delete the repository on GitHub.
            </p>
          </div>

          {confirmDelete ? (
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => removeMutation.mutate()}
                disabled={removeMutation.isPending}
                className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
              >
                {removeMutation.isPending ? 'Removing...' : 'Confirm Remove'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="px-3 py-1.5 rounded-lg bg-white text-[#6B818B] hover:text-[#172B35] border border-[#E1ECEE] text-xs font-semibold cursor-pointer"
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-white hover:bg-rose-50 text-rose-700 border border-rose-200 text-xs font-semibold shadow-sm transition-colors cursor-pointer"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Remove Repository</span>
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
