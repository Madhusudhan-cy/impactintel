import React from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { repositoriesApi } from '../api/repositories';
import { graphApi } from '../api/graph';
import { pullRequestsApi } from '../api/pullRequests';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import { usePrathiksha } from '../components/prathiksha/PrathikshaContext';
import {
  GitPullRequest,
  Network,
  BotMessageSquare,
  ArrowRight,
  Database,
  Layers,
  FileCode,
  Activity,
  GitBranch,
  Calendar,
  CheckCircle2,
  Clock,
} from 'lucide-react';

export default function DashboardPage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const outletCtx = useOutletContext();
  const { openChat } = usePrathiksha();

  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const { data: repoDetails } = useQuery({
    queryKey: ['repo-details', owner, repo],
    queryFn: () => repositoriesApi.getDetails(owner, repo),
  });

  const { data: graphSummary } = useQuery({
    queryKey: ['graph-summary', owner, repo],
    queryFn: () => graphApi.getSummary(owner, repo),
  });

  const { data: pullRequests = [] } = useQuery({
    queryKey: ['pull-requests', owner, repo],
    queryFn: () => pullRequestsApi.list(owner, repo),
  });

  const activeBranch = repoDetails?.branch || repoDetails?.default_branch || 'main';

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#F5FAFA]">
      <Header
        title="Overview"
        subtitle={decodedRepo}
        branch={activeBranch}
        breadcrumbs={['Repositories', decodedRepo, 'Overview']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <main className="p-5 sm:p-6 max-w-6xl w-full mx-auto space-y-5">
        {/* Compact Repository Heading */}
        <div className="p-4 sm:p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <Badge variant={repoDetails?.indexing_status === 'INDEXED' ? 'success' : 'warning'}>
                {repoDetails?.indexing_status || 'INDEXED'}
              </Badge>
              <span className="text-[11px] text-[#6B818B] font-mono flex items-center gap-1">
                <GitBranch className="w-3.5 h-3.5 text-[#16B89A]" />
                <span>branch: {activeBranch}</span>
              </span>
              <span className="text-[#E1ECEE]">•</span>
              <span className="text-[11px] text-[#6B818B] font-mono">
                commit: {repoDetails?.commit_sha || 'HEAD'}
              </span>
            </div>

            <h2 className="text-xl sm:text-2xl font-bold text-[#172B35] tracking-tight font-mono">
              {decodedRepo}
            </h2>
            <p className="text-xs text-[#6B818B] mt-0.5">
              Code Knowledge Graph & transitive PR blast radius intelligence.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={() => navigate(`/repositories/${encodeURIComponent(decodedRepo)}/pull-requests`)}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              <GitPullRequest className="w-3.5 h-3.5" />
              <span>Inspect PRs</span>
            </button>

            <button
              onClick={openChat}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-white hover:bg-[#E2F4FC]/50 text-[#172B35] border border-[#E1ECEE] hover:border-[#55BDEB] text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              <BotMessageSquare className="w-3.5 h-3.5 text-[#55BDEB]" />
              <span>Ask AI Chat</span>
            </button>
          </div>
        </div>

        {/* 4 Compact Repository Metrics in Horizontal Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {/* Metric 1: Graph Nodes */}
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card hover:border-[#16B89A]/50 transition-all">
            <div className="flex items-center justify-between text-[#6B818B] mb-1">
              <span className="text-[10px] font-mono uppercase font-bold tracking-wider">
                Graph Nodes
              </span>
              <div className="w-6 h-6 rounded bg-[#DDF7EF] flex items-center justify-center text-[#087F70]">
                <Layers className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="text-2xl font-bold text-[#172B35]">
              {graphSummary?.total_nodes || repoDetails?.total_nodes || 0}
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono mt-0.5 truncate">
              Functions, routes, classes
            </div>
          </div>

          {/* Metric 2: Graph Edges */}
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card hover:border-[#55BDEB]/50 transition-all">
            <div className="flex items-center justify-between text-[#6B818B] mb-1">
              <span className="text-[10px] font-mono uppercase font-bold tracking-wider">
                Graph Edges
              </span>
              <div className="w-6 h-6 rounded bg-[#E2F4FC] flex items-center justify-center text-[#258FC7]">
                <Network className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="text-2xl font-bold text-[#172B35]">
              {graphSummary?.total_edges || repoDetails?.total_edges || 0}
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono mt-0.5 truncate">
              Calls, renders, imports, tests
            </div>
          </div>

          {/* Metric 3: PR Analyses */}
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card hover:border-[#16B89A]/50 transition-all">
            <div className="flex items-center justify-between text-[#6B818B] mb-1">
              <span className="text-[10px] font-mono uppercase font-bold tracking-wider">
                PR Analyses
              </span>
              <div className="w-6 h-6 rounded bg-[#DDF7EF] flex items-center justify-center text-[#16B89A]">
                <GitPullRequest className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="text-2xl font-bold text-[#172B35]">
              {pullRequests.length}
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono mt-0.5 truncate">
              Stored impact reports
            </div>
          </div>

          {/* Metric 4: Indexed Commit */}
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card hover:border-[#55BDEB]/50 transition-all">
            <div className="flex items-center justify-between text-[#6B818B] mb-1">
              <span className="text-[10px] font-mono uppercase font-bold tracking-wider">
                Indexed Commit
              </span>
              <div className="w-6 h-6 rounded bg-[#E2F4FC] flex items-center justify-center text-[#55BDEB]">
                <FileCode className="w-3.5 h-3.5" />
              </div>
            </div>
            <div className="text-sm font-mono font-bold text-[#172B35] mt-1.5 truncate">
              {repoDetails?.commit_sha || 'HEAD'}
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono mt-0.5 truncate">
              Verified AST snapshot
            </div>
          </div>
        </div>

        {/* Entities Breakdown */}
        {graphSummary?.node_type_counts && (
          <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
            <div className="flex items-center justify-between mb-3.5">
              <h3 className="text-xs font-bold text-[#172B35] flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-[#16B89A]" />
                <span>Code Knowledge Graph Entities Breakdown</span>
              </h3>
              <button
                onClick={() => navigate(`/repositories/${encodeURIComponent(decodedRepo)}/graph`)}
                className="text-[11px] font-mono text-[#087F70] hover:text-[#16B89A] hover:underline font-semibold flex items-center gap-1 cursor-pointer"
              >
                <span>Full Graph Explorer</span>
                <ArrowRight className="w-3 h-3" />
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
              {Object.entries(graphSummary.node_type_counts).map(([type, count]) => (
                <div
                  key={type}
                  className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] text-center"
                >
                  <div className="text-base font-bold text-[#087F70]">{count}</div>
                  <div className="text-[11px] font-mono text-[#6B818B] mt-0.5">{type}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Pull Request Impact Reports */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
          <div className="flex items-center justify-between mb-3.5">
            <h3 className="text-xs font-bold text-[#172B35] flex items-center gap-1.5">
              <GitPullRequest className="w-3.5 h-3.5 text-[#16B89A]" />
              <span>Recent Pull Request Impact Reports</span>
            </h3>
            <button
              onClick={() => navigate(`/repositories/${encodeURIComponent(decodedRepo)}/pull-requests`)}
              className="text-[11px] font-semibold text-[#087F70] hover:text-[#16B89A]"
            >
              View all PRs →
            </button>
          </div>

          {pullRequests.length > 0 ? (
            <div className="divide-y divide-[#E1ECEE]">
              {pullRequests.slice(0, 5).map((pr) => (
                <div
                  key={pr.id || pr.pr_number}
                  onClick={() =>
                    navigate(
                      `/repositories/${encodeURIComponent(decodedRepo)}/pull-requests/${pr.pr_number}`
                    )
                  }
                  className="py-3 flex items-center justify-between hover:bg-[#F5FAFA] px-2.5 rounded-lg cursor-pointer transition-colors"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="w-7 h-7 rounded-md bg-[#DDF7EF] flex items-center justify-center text-[#087F70] shrink-0">
                      <GitPullRequest className="w-3.5 h-3.5 text-[#16B89A]" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-semibold text-[#172B35] truncate">
                        #{pr.pr_number} {pr.pr_title}
                      </div>
                      <div className="text-[10px] text-[#6B818B] font-mono mt-0.5">
                        base: {pr.base_branch} • analyzed at{' '}
                        {new Date(pr.created_at || Date.now()).toLocaleDateString()}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-3">
                    <span className="text-xs font-mono text-[#6B818B]">
                      affected: <strong className="text-rose-600 font-bold">{pr.total_affected}</strong>
                    </span>
                    <Badge variant={pr.status === 'COMPLETED' ? 'success' : 'neutral'}>
                      {pr.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-xs text-[#6B818B] font-mono">
              No PRs analyzed yet. Use the Pull Requests tab to trigger an analysis.
            </div>
          )}
        </div>

        {/* Repository Activity */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
          <h3 className="text-xs font-bold text-[#172B35] mb-3 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-[#55BDEB]" />
            <span>Repository Activity</span>
          </h3>

          <div className="space-y-2 text-xs font-mono">
            <div className="p-2.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] flex items-center justify-between">
              <div className="flex items-center gap-2 text-[#172B35]">
                <Clock className="w-3.5 h-3.5 text-[#16B89A]" />
                <span>Last indexed snapshot</span>
              </div>
              <span className="text-[#6B818B]">
                {repoDetails?.indexed_at
                  ? new Date(repoDetails.indexed_at).toLocaleString()
                  : 'Active session'}
              </span>
            </div>

            <div className="p-2.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] flex items-center justify-between">
              <div className="flex items-center gap-2 text-[#172B35]">
                <CheckCircle2 className="w-3.5 h-3.5 text-[#087F70]" />
                <span>Code Knowledge Graph Status</span>
              </div>
              <span className="text-[#087F70] font-semibold">
                {repoDetails?.indexing_status || 'INDEXED'} ({graphSummary?.total_nodes || 0} symbols)
              </span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
