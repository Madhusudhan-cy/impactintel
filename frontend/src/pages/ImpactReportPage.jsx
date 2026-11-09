import React, { useState } from 'react';
import { useParams, useNavigate, useOutletContext } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { pullRequestsApi } from '../api/pullRequests';
import Header from '../components/common/Header';
import Badge from '../components/common/Badge';
import {
  GitPullRequest,
  FileCode,
  Network,
  TestTube,
  ShieldAlert,
  ChevronRight,
  GitBranch,
} from 'lucide-react';

export default function ImpactReportPage() {
  const { repoId, prNumber } = useParams();
  const navigate = useNavigate();
  const outletCtx = useOutletContext();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [activeTab, setActiveTab] = useState('affected'); // 'affected' | 'paths' | 'tests' | 'files'

  const { data: analysis, isLoading, error } = useQuery({
    queryKey: ['pr-analysis', owner, repo, prNumber],
    queryFn: () => pullRequestsApi.getAnalysis(owner, repo, prNumber),
  });

  const report = analysis?.report || {};
  const affectedComponents = report.affected_components || [];
  const changedFiles = report.changed_files || [];
  const unmappedFiles = report.unmapped_files || [];

  const relatedTests = [];
  affectedComponents.forEach((c) => {
    (c.related_tests || []).forEach((t) => {
      if (!relatedTests.includes(t)) {
        relatedTests.push(t);
      }
    });
  });

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-[#F5FAFA]">
      <Header
        title={`PR #${prNumber} Impact Report`}
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'Pull Requests', `#${prNumber}`]}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <main className="p-5 sm:p-6 max-w-6xl w-full mx-auto space-y-4">
        {/* PR Header Banner */}
        <div className="p-4 sm:p-5 rounded-xl bg-white border border-[#E1ECEE] shadow-card flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <Badge variant={analysis?.status === 'COMPLETED' ? 'success' : 'warning'}>
                {analysis?.status || 'COMPLETED'}
              </Badge>
              <span className="text-[11px] text-[#6B818B] font-mono flex items-center gap-1">
                <GitBranch className="w-3.5 h-3.5 text-[#16B89A]" />
                <span>PR #{analysis?.pr_number || prNumber} • base: {analysis?.base_branch || 'main'}</span>
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold text-[#172B35] tracking-tight">
              {analysis?.pr_title || `Pull Request #${prNumber}`}
            </h2>
            <div className="flex items-center gap-2 text-[11px] text-[#6B818B] font-mono mt-1">
              <span>commit: {analysis?.base_commit_sha || 'HEAD'}</span>
              <span>•</span>
              <span>analyzed at {new Date(analysis?.created_at || Date.now()).toLocaleString()}</span>
            </div>
          </div>

          <div className="text-left sm:text-right shrink-0 bg-[#F5FAFA] sm:bg-transparent p-3 sm:p-0 rounded-lg border border-[#E1ECEE] sm:border-none">
            <div className="text-2xl sm:text-3xl font-extrabold text-rose-600 font-mono">
              {analysis?.total_affected || affectedComponents.length || 0}
            </div>
            <div className="text-[10px] text-[#6B818B] uppercase font-mono tracking-wider font-bold">
              Affected Components
            </div>
          </div>
        </div>

        {/* Impact Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
            <div className="text-[10px] text-[#6B818B] uppercase font-mono font-bold">Changed Files</div>
            <div className="text-xl font-bold text-[#172B35] mt-0.5">{changedFiles.length}</div>
            <div className="text-[10px] text-[#6B818B] font-mono">Direct diff modifications</div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
            <div className="text-[10px] text-[#6B818B] uppercase font-mono font-bold">Transitive Blast Radius</div>
            <div className="text-xl font-bold text-rose-600 mt-0.5">{affectedComponents.length}</div>
            <div className="text-[10px] text-[#6B818B] font-mono">Callers, parents & handlers</div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
            <div className="text-[10px] text-[#6B818B] uppercase font-mono font-bold">Connected Tests</div>
            <div className="text-xl font-bold text-[#087F70] mt-0.5">{relatedTests.length}</div>
            <div className="text-[10px] text-[#6B818B] font-mono">Suggested test coverage</div>
          </div>

          <div className="p-3.5 rounded-xl bg-white border border-[#E1ECEE] shadow-card">
            <div className="text-[10px] text-[#6B818B] uppercase font-mono font-bold">Max Dependency Depth</div>
            <div className="text-xl font-bold text-[#55BDEB] mt-0.5">
              {affectedComponents.length > 0 ? Math.max(...affectedComponents.map((c) => c.depth || 1)) : 0} hops
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono">Reverse BFS propagation</div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="border-b border-[#E1ECEE] flex items-center gap-5 text-xs font-semibold overflow-x-auto">
          {[
            { id: 'affected', label: `Affected Components (${affectedComponents.length})`, icon: ShieldAlert },
            { id: 'paths', label: 'Transitive Causal Paths', icon: Network },
            { id: 'tests', label: `Suggested Tests (${relatedTests.length})`, icon: TestTube },
            { id: 'files', label: `Changed Files (${changedFiles.length})`, icon: FileCode },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`pb-2.5 flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
                  active
                    ? 'border-b-2 border-[#16B89A] text-[#087F70] font-bold'
                    : 'text-[#6B818B] hover:text-[#172B35]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab 1: Affected Components List */}
        {activeTab === 'affected' && (
          <div className="space-y-3">
            {affectedComponents.length > 0 ? (
              affectedComponents.map((comp, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#16B89A]/50 shadow-card transition-all space-y-2.5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-xs text-[#172B35] font-mono">
                          {comp.component || comp.node_id || comp.file_path}
                        </span>
                        <Badge variant="primary">{comp.type || comp.entity_type || 'Symbol'}</Badge>
                        <Badge variant={comp.depth === 1 ? 'warning' : 'neutral'}>
                          Depth: {comp.depth} {comp.depth === 1 ? '(Direct Caller)' : '(Transitive)'}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-[#6B818B] font-mono mt-0.5">
                        file: {comp.file_path || comp.file}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <div className="text-xs font-mono text-[#087F70] font-bold">
                        {comp.confidence != null ? (comp.confidence * 100).toFixed(0) : '100'}% confidence
                      </div>
                    </div>
                  </div>

                  {/* Causal Path */}
                  {((comp.path && comp.path.length > 0) ||
                    (comp.dependency_path && comp.dependency_path.length > 0)) && (
                    <div className="p-2 rounded bg-[#F5FAFA] border border-[#E1ECEE] font-mono text-xs text-[#6B818B] flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-[#6B818B] font-bold uppercase">Causal Path:</span>
                      {(comp.path || comp.dependency_path).map((step, sIdx) => (
                        <React.Fragment key={sIdx}>
                          {sIdx > 0 && <ChevronRight className="w-3 h-3 text-[#16B89A]" />}
                          <span
                            className={
                              sIdx === (comp.path || comp.dependency_path).length - 1
                                ? 'text-[#087F70] font-bold'
                                : 'text-[#6B818B]'
                            }
                          >
                            {step}
                          </span>
                        </React.Fragment>
                      ))}
                    </div>
                  )}

                  {/* Evidence snippet */}
                  {comp.evidence && comp.evidence.length > 0 && (
                    <div className="text-xs font-mono bg-[#F5FAFA] p-2.5 rounded border border-[#E1ECEE] text-[#172B35]">
                      <span className="text-[#6B818B]">Evidence line {comp.evidence[0].line}: </span>
                      <code>{comp.evidence[0].statement}</code>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="text-center py-10 text-xs text-[#6B818B] font-mono bg-white rounded-xl border border-[#E1ECEE]">
                No affected components discovered. Changes appear isolated.
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Transitive Causal Paths */}
        {activeTab === 'paths' && (
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card space-y-3">
            <h3 className="text-xs font-bold text-[#172B35]">Transitive Dependency Blast Radius Flow</h3>
            <p className="text-xs text-[#6B818B]">
              Each row demonstrates how a direct change in a source file propagates upwards through caller functions, React rendering trees, and API controllers.
            </p>

            <div className="space-y-2 pt-1">
              {affectedComponents.map((c, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] text-xs font-mono space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[#172B35]">
                    <span className="text-[#087F70] font-bold">{c.component || c.node_id || c.file_path}</span>
                    <span className="text-[#6B818B]">
                      {c.type || c.entity_type || 'Symbol'} • {c.file_path}
                    </span>
                  </div>
                  <div className="text-[#6B818B] flex items-center gap-1.5 flex-wrap text-[11px]">
                    {(c.path || c.dependency_path)?.join(' ➔ ') || 'Directly modified'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 3: Suggested Tests */}
        {activeTab === 'tests' && (
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card space-y-3">
            <h3 className="text-xs font-bold text-[#172B35]">Recommended Test Suites</h3>
            <p className="text-xs text-[#6B818B]">
              The Code Knowledge Graph connected these automated test suites to modified and impacted components.
            </p>

            {relatedTests.length > 0 ? (
              <div className="space-y-2">
                {relatedTests.map((t, idx) => (
                  <div
                    key={idx}
                    className="p-3 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] flex items-center justify-between"
                  >
                    <div className="flex items-center gap-2.5">
                      <div className="w-6 h-6 rounded bg-[#DDF7EF] flex items-center justify-center text-[#087F70]">
                        <TestTube className="w-3.5 h-3.5 text-[#16B89A]" />
                      </div>
                      <span className="text-xs font-mono font-bold text-[#172B35]">{t}</span>
                    </div>
                    <Badge variant="info">Targeted Test</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-xs text-[#6B818B] font-mono bg-[#F5FAFA] rounded-lg border border-[#E1ECEE]">
                No direct tests were identified covering these affected symbols.
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Changed Files */}
        {activeTab === 'files' && (
          <div className="p-4 rounded-xl bg-white border border-[#E1ECEE] shadow-card space-y-3">
            <h3 className="text-xs font-bold text-[#172B35]">Modified Files in Pull Request</h3>
            <div className="space-y-2">
              {changedFiles.map((f, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-lg bg-[#F5FAFA] border border-[#E1ECEE] flex items-center justify-between text-xs font-mono"
                >
                  <div className="flex items-center gap-2">
                    <FileCode className="w-4 h-4 text-[#16B89A]" />
                    <span className="text-[#172B35] font-semibold">{f.filename || f}</span>
                  </div>
                  <Badge variant="warning">{f.status || 'modified'}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
