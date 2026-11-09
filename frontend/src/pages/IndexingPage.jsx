import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { repositoriesApi } from '../api/repositories';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  CheckCircle2,
  Clock,
  Play,
  RotateCw,
  ArrowRight,
  Terminal,
} from 'lucide-react';

export default function IndexingPage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const { data: statusData, refetch } = useQuery({
    queryKey: ['indexing-status', owner, repo],
    queryFn: () => repositoriesApi.getIndexStatus(owner, repo),
    refetchInterval: (query) => {
      const data = query.state.data;
      return data?.status === 'INDEXING' ? 2000 : false;
    },
  });

  const indexMutation = useMutation({
    mutationFn: () => repositoriesApi.triggerIndex(owner, repo, { branch: 'main', commit_sha: 'HEAD' }),
    onSuccess: () => {
      refetch();
    },
  });

  const isIndexed = statusData?.status === 'INDEXED';
  const isIndexing = statusData?.status === 'INDEXING' || indexMutation.isPending;

  const stages = [
    { title: '1. Repository Source Retrieval', desc: 'Resolved files on disk / cloned repository tree', complete: isIndexed },
    { title: '2. Multi-Language AST Extraction', desc: 'Parsed Tree-sitter JS/TS/React and Python AST', complete: isIndexed },
    { title: '3. Dependency Graph Construction', desc: 'Built directed NetworkX DiGraph (calls, renders, routes, tests)', complete: isIndexed },
    { title: '4. Semantic Code Chunking', desc: 'Preserved semantic boundaries for hybrid RAG retrieval', complete: isIndexed },
    { title: '5. Database & pgvector Persistence', desc: 'Saved nodes, edges, chunks, and embeddings to database', complete: isIndexed },
  ];

  return (
    <div className="min-h-screen bg-[#F5FAFA] flex flex-col text-[#172B35] font-sans selection:bg-[#DDF7EF] selection:text-[#087F70]">
      <Header
        title={`Indexing: ${decodedRepo}`}
        subtitle="Extract fine-grained symbols and construct Code Knowledge Graph"
        breadcrumbs={['Repositories', decodedRepo, 'Indexing']}
      />

      <main className="p-5 sm:p-6 max-w-4xl w-full mx-auto flex-1 space-y-5">
        {/* Status card */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Badge variant={isIndexed ? 'success' : isIndexing ? 'warning' : 'neutral'}>
                {statusData?.status || 'NOT_INDEXED'}
              </Badge>
              <span className="text-[11px] text-[#6B818B] font-mono">
                branch: {statusData?.branch || 'main'}
              </span>
            </div>
            <h2 className="text-lg font-bold text-[#172B35] tracking-tight">{decodedRepo}</h2>
            <p className="text-xs text-[#6B818B] mt-0.5">
              {isIndexed
                ? `Last indexed on ${new Date(statusData.indexed_at || Date.now()).toLocaleString()}`
                : 'Repository requires AST indexing before structural impact analysis can be performed.'}
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => indexMutation.mutate()}
              disabled={isIndexing}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] disabled:opacity-50 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              {isIndexing ? (
                <>
                  <RotateCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Indexing Codebase...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5" />
                  <span>{isIndexed ? 'Re-index Repository' : 'Start Indexing'}</span>
                </>
              )}
            </button>

            {isIndexed && (
              <button
                onClick={() => navigate(`/repositories/${encodeURIComponent(decodedRepo)}/overview`)}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white hover:bg-[#E2F4FC]/40 text-[#172B35] border border-[#E1ECEE] hover:border-[#55BDEB] text-xs font-semibold shadow-sm transition-all cursor-pointer"
              >
                <span>Dashboard</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Graph metrics if indexed */}
        {isIndexed && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
              <div className="text-[10px] font-mono text-[#6B818B] uppercase font-bold">Total Nodes</div>
              <div className="text-xl font-bold text-[#087F70] mt-0.5">{statusData.total_nodes}</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
              <div className="text-[10px] font-mono text-[#6B818B] uppercase font-bold">Total Edges</div>
              <div className="text-xl font-bold text-[#258FC7] mt-0.5">{statusData.total_edges}</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
              <div className="text-[10px] font-mono text-[#6B818B] uppercase font-bold">Commit SHA</div>
              <div className="text-xs font-mono font-bold text-[#172B35] mt-1 truncate">
                {statusData.commit_sha || 'HEAD'}
              </div>
            </div>
            <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
              <div className="text-[10px] font-mono text-[#6B818B] uppercase font-bold">Languages</div>
              <div className="text-xs font-mono font-bold text-[#16B89A] mt-1">
                JS, TS, Python
              </div>
            </div>
          </div>
        )}

        {/* Indexing pipeline stages */}
        <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
          <h3 className="text-xs font-bold text-[#172B35] mb-3 flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-[#16B89A]" />
            <span>AST & Graph Pipeline</span>
          </h3>

          <div className="space-y-2">
            {stages.map((stage, idx) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border transition-all flex items-start gap-3 ${
                  stage.complete
                    ? 'bg-[#F5FAFA] border-[#16B89A]/30'
                    : 'bg-white border-[#E1ECEE]'
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  {stage.complete ? (
                    <CheckCircle2 className="w-4 h-4 text-[#16B89A]" />
                  ) : (
                    <Clock className="w-4 h-4 text-[#6B818B]" />
                  )}
                </div>
                <div>
                  <div className="text-xs font-bold text-[#172B35]">{stage.title}</div>
                  <div className="text-[10px] text-[#6B818B] mt-0.5">{stage.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
