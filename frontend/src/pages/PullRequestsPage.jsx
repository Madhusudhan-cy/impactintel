import React, { useState } from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { pullRequestsApi } from '../api/pullRequests';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  GitPullRequest,
  Search,
  Plus,
  Play,
  RotateCw,
  ArrowRight,
  X,
} from 'lucide-react';

export default function PullRequestsPage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const outletCtx = useOutletContext();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [searchTerm, setSearchTerm] = useState('');
  const [showModal, setShowModal] = useState(false);

  // Manual analysis form state
  const [prNumber, setPrNumber] = useState('142');
  const [prTitle, setPrTitle] = useState('Optimize database query connection pooling');
  const [changedFilesInput, setChangedFilesInput] = useState(
    'src/database/database.js\nsrc/services/paymentService.js'
  );

  const { data: pullRequests = [], isLoading } = useQuery({
    queryKey: ['pull-requests', owner, repo],
    queryFn: () => pullRequestsApi.list(owner, repo),
  });

  const analyzeMutation = useMutation({
    mutationFn: () => {
      const files = changedFilesInput
        .split('\n')
        .map((f) => f.trim())
        .filter(Boolean)
        .map((f) => ({ filename: f, status: 'modified' }));

      return pullRequestsApi.analyzeManual(owner, repo, parseInt(prNumber, 10), {
        pr_title: prTitle,
        changed_files: files,
        base_branch: 'main',
        base_commit_sha: 'HEAD',
        head_commit_sha: 'manual_sha',
        post_comment: false,
      });
    },
    onSuccess: (data) => {
      setShowModal(false);
      queryClient.invalidateQueries(['pull-requests', owner, repo]);
      navigate(`/repositories/${encodeURIComponent(decodedRepo)}/pull-requests/${data.pr_number}`);
    },
  });

  const filteredPRs = pullRequests.filter((pr) =>
    (pr.pr_title || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    String(pr.pr_number).includes(searchTerm)
  );

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#F5FAFA]">
      <Header
        title="Pull Requests"
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'Pull Requests']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <main className="p-5 sm:p-6 max-w-6xl w-full mx-auto space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#172B35] tracking-tight">
              Pull Request Impact Analyses
            </h2>
            <p className="text-xs text-[#6B818B] mt-0.5">
              Inspect affected components, dependency propagation paths, and suggested tests.
            </p>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto">
            <div className="relative w-full sm:w-60">
              <Search className="w-3.5 h-3.5 text-[#6B818B] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search PRs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-white border border-[#E1ECEE] text-xs text-[#172B35] placeholder-[#6B818B] focus:outline-none focus:border-[#16B89A] shadow-sm"
              />
            </div>

            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shrink-0 shadow-sm transition-all cursor-pointer"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>New Analysis</span>
            </button>
          </div>
        </div>

        {/* PR List Table */}
        <div className="rounded-xl bg-white border border-[#E1ECEE] shadow-card overflow-hidden">
          {isLoading ? (
            <div className="py-16 text-center text-xs text-[#6B818B] font-mono">
              Loading PR analyses...
            </div>
          ) : filteredPRs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#F5FAFA] border-b border-[#E1ECEE] text-[#6B818B] font-mono text-[10px] uppercase">
                  <tr>
                    <th className="py-2.5 px-4">PR #</th>
                    <th className="py-2.5 px-4">Title</th>
                    <th className="py-2.5 px-4">Base Branch</th>
                    <th className="py-2.5 px-4">Affected</th>
                    <th className="py-2.5 px-4">Status</th>
                    <th className="py-2.5 px-4">Analyzed</th>
                    <th className="py-2.5 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#E1ECEE]">
                  {filteredPRs.map((pr) => (
                    <tr
                      key={pr.id || pr.pr_number}
                      onClick={() =>
                        navigate(
                          `/repositories/${encodeURIComponent(decodedRepo)}/pull-requests/${pr.pr_number}`
                        )
                      }
                      className="hover:bg-[#F5FAFA] cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-4 font-mono font-bold text-[#087F70]">
                        #{pr.pr_number}
                      </td>
                      <td className="py-3 px-4 font-semibold text-[#172B35] max-w-md truncate">
                        {pr.pr_title}
                      </td>
                      <td className="py-3 px-4 font-mono text-[#6B818B]">
                        {pr.base_branch}
                      </td>
                      <td className="py-3 px-4 font-mono font-bold text-rose-600">
                        {pr.total_affected}
                      </td>
                      <td className="py-3 px-4">
                        <Badge variant={pr.status === 'COMPLETED' ? 'success' : 'neutral'}>
                          {pr.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-4 font-mono text-[#6B818B] text-[11px]">
                        {new Date(pr.created_at || Date.now()).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right font-medium text-[#087F70]">
                        <span className="inline-flex items-center gap-1 hover:underline">
                          <span>Report</span>
                          <ArrowRight className="w-3 h-3" />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-[#6B818B] font-mono">
              No pull request analyses found. Click "New Analysis" to trigger one.
            </div>
          )}
        </div>

        {/* Modal */}
        {showModal && (
          <div className="fixed inset-0 bg-[#172B35]/25 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="max-w-md w-full bg-white rounded-xl border border-[#E1ECEE] shadow-card-hover p-5 space-y-3.5">
              <div className="flex items-center justify-between pb-2.5 border-b border-[#E1ECEE]">
                <h3 className="font-bold text-xs text-[#172B35]">Run PR Impact Analysis</h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="p-1 rounded text-[#6B818B] hover:text-[#172B35]"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2.5 text-xs">
                <div>
                  <label className="block text-[10px] font-mono uppercase text-[#6B818B] font-semibold mb-1">
                    PR Number
                  </label>
                  <input
                    type="number"
                    value={prNumber}
                    onChange={(e) => setPrNumber(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] font-mono text-xs focus:outline-none focus:border-[#16B89A]"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono uppercase text-[#6B818B] font-semibold mb-1">
                    PR Title
                  </label>
                  <input
                    type="text"
                    value={prTitle}
                    onChange={(e) => setPrTitle(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] text-xs focus:outline-none focus:border-[#16B89A]"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-mono uppercase text-[#6B818B] font-semibold mb-1">
                    Changed Files (one per line)
                  </label>
                  <textarea
                    rows={3}
                    value={changedFilesInput}
                    onChange={(e) => setChangedFilesInput(e.target.value)}
                    className="w-full px-2.5 py-1.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] font-mono text-xs focus:outline-none focus:border-[#16B89A]"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2.5 border-t border-[#E1ECEE]">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-[#6B818B] hover:text-[#172B35]"
                >
                  Cancel
                </button>
                <button
                  onClick={() => analyzeMutation.mutate()}
                  disabled={analyzeMutation.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
                >
                  <Play className="w-3 h-3" />
                  <span>{analyzeMutation.isPending ? 'Analyzing...' : 'Run Analysis'}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
