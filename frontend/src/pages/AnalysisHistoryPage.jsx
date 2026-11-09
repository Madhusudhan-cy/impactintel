import React, { useState } from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { pullRequestsApi } from '../api/pullRequests';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  GitPullRequest,
  Search,
  ArrowRight,
  FileCheck2,
} from 'lucide-react';

export default function AnalysisHistoryPage() {
  const { repoId } = useParams();
  const navigate = useNavigate();
  const outletCtx = useOutletContext();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [searchTerm, setSearchTerm] = useState('');

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['pr-history', owner, repo],
    queryFn: () => pullRequestsApi.list(owner, repo),
  });

  const filtered = records.filter((r) =>
    (r.pr_title || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    String(r.pr_number).includes(searchTerm)
  );

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#F5FAFA]">
      <Header
        title="Analysis History"
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'Analysis History']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <main className="p-5 sm:p-6 max-w-5xl w-full mx-auto space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-lg sm:text-xl font-bold text-[#172B35] tracking-tight">
              Stored Historical Reports
            </h2>
            <p className="text-xs text-[#6B818B] mt-0.5">
              Audit log of all pull request blast radius analyses executed on {decodedRepo}.
            </p>
          </div>

          <div className="relative w-full sm:w-60">
            <Search className="w-3.5 h-3.5 text-[#6B818B] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search history..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-white border border-[#E1ECEE] text-xs text-[#172B35] placeholder-[#6B818B] focus:outline-none focus:border-[#16B89A] shadow-sm"
            />
          </div>
        </div>

        <div className="rounded-xl bg-white border border-[#E1ECEE] shadow-card overflow-hidden">
          {isLoading ? (
            <div className="py-16 text-center text-xs text-[#6B818B] font-mono">
              Loading analysis history...
            </div>
          ) : filtered.length > 0 ? (
            <div className="divide-y divide-[#E1ECEE]">
              {filtered.map((item) => (
                <div
                  key={item.id || item.pr_number}
                  onClick={() =>
                    navigate(
                      `/repositories/${encodeURIComponent(decodedRepo)}/pull-requests/${item.pr_number}`
                    )
                  }
                  className="p-4 flex items-center justify-between hover:bg-[#F5FAFA] cursor-pointer transition-colors"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-[#DDF7EF] flex items-center justify-center text-[#087F70] shrink-0 mt-0.5">
                      <FileCheck2 className="w-4 h-4 text-[#16B89A]" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className="font-mono font-bold text-xs text-[#087F70]">
                          PR #{item.pr_number}
                        </span>
                        <span className="font-semibold text-xs text-[#172B35] truncate">
                          {item.pr_title}
                        </span>
                      </div>
                      <div className="text-[10px] text-[#6B818B] font-mono flex items-center gap-2">
                        <span>base: {item.base_branch}</span>
                        <span>•</span>
                        <span>created: {new Date(item.created_at || Date.now()).toLocaleString()}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-3">
                    <div className="text-right">
                      <div className="text-xs font-mono font-bold text-rose-600">
                        {item.total_affected} affected
                      </div>
                      <Badge variant={item.status === 'COMPLETED' ? 'success' : 'neutral'}>
                        {item.status}
                      </Badge>
                    </div>

                    <ArrowRight className="w-3.5 h-3.5 text-[#6B818B]" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-[#6B818B] font-mono">
              No analysis records stored for this repository.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
