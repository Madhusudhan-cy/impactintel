import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import {
  Layers,
  GitPullRequest,
  Network,
  BotMessageSquare,
  ShieldCheck,
  ArrowRight,
  Terminal,
  Cpu,
  Github,
  Sparkles,
} from 'lucide-react';

export default function LandingPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleGitHubLogin = async () => {
    setLoading(true);
    try {
      const res = await authApi.getAuthUrl();
      if (res && res.url) {
        if (res.url.startsWith('/')) {
          navigate(res.url);
        } else {
          window.location.href = res.url;
        }
      } else {
        navigate('/repositories');
      }
    } catch (err) {
      console.warn('Using local dev bypass:', err);
      navigate('/repositories');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F5FAFA] text-[#172B35] flex flex-col font-sans selection:bg-[#DDF7EF] selection:text-[#087F70]">
      {/* Top Navigation */}
      <nav className="h-16 border-b border-[#E1ECEE] bg-white/95 backdrop-blur-md px-6 sm:px-8 flex items-center justify-between max-w-7xl w-full mx-auto sticky top-0 z-40 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#16B89A] to-[#087F70] flex items-center justify-center text-white shadow-sm">
            <Layers className="w-4.5 h-4.5" />
          </div>
          <div>
            <div className="font-bold text-sm tracking-tight text-[#172B35]">
              ImpactIntel
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono leading-none">
              Repository Impact Intelligence
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <button
              onClick={() => navigate('/repositories')}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              <span>Go to Repositories</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              onClick={handleGitHubLogin}
              disabled={loading}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white hover:bg-[#F5FAFA] text-[#172B35] border border-[#E1ECEE] hover:border-[#16B89A] text-xs font-semibold shadow-sm transition-all cursor-pointer"
            >
              <Github className="w-4 h-4 text-[#172B35]" />
              <span>{loading ? 'Connecting...' : 'Continue with GitHub'}</span>
            </button>
          )}
        </div>
      </nav>

      {/* Hero Section */}
      <section className="py-14 sm:py-20 px-6 max-w-5xl mx-auto text-center flex-1 flex flex-col justify-center">
        {/* Pill Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#DDF7EF] border border-[#16B89A]/40 text-[#087F70] text-xs font-mono font-medium mx-auto mb-5 shadow-sm">
          <Terminal className="w-3.5 h-3.5 text-[#16B89A]" />
          <span>Evidence-Grounded Code Blast-Radius Intelligence</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight text-[#172B35] mb-5 leading-[1.18]">
          Know the exact impact of every code change{' '}
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#16B89A] via-[#087F70] to-[#55BDEB]">
            before you merge.
          </span>
        </h1>

        {/* Hero Subtitle */}
        <p className="text-sm sm:text-base text-[#6B818B] max-w-2xl mx-auto mb-8 leading-relaxed">
          An intelligent platform that maps multi-language repositories into a fine-grained{' '}
          <strong className="text-[#172B35] font-semibold">Code Knowledge Graph</strong>.
          Computes transitive blast radii, recommends impacted tests, and answers conversational codebase questions with verified evidence.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 mb-14">
          <button
            onClick={handleGitHubLogin}
            disabled={loading}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg bg-[#16B89A] hover:bg-[#087F70] text-white font-semibold text-xs shadow-sm transition-all cursor-pointer"
          >
            <Github className="w-4 h-4" />
            <span>Continue with GitHub</span>
            <ArrowRight className="w-3.5 h-3.5 ml-0.5" />
          </button>

          <button
            onClick={() => navigate('/repositories')}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-lg bg-white hover:bg-[#E2F4FC]/40 text-[#172B35] border border-[#E1ECEE] hover:border-[#55BDEB] text-xs font-semibold shadow-sm transition-all cursor-pointer"
          >
            <Cpu className="w-4 h-4 text-[#55BDEB]" />
            <span>Explore Repositories</span>
          </button>
        </div>

        {/* Feature Grid: 4 Core Features */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-left">
          <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#16B89A] shadow-card hover:shadow-card-hover transition-all">
            <div className="w-9 h-9 rounded-lg bg-[#DDF7EF] border border-[#16B89A]/30 text-[#087F70] flex items-center justify-center mb-3">
              <GitPullRequest className="w-4.5 h-4.5 text-[#16B89A]" />
            </div>
            <h3 className="font-bold text-sm text-[#172B35] mb-1.5">PR Impact Analysis</h3>
            <p className="text-xs text-[#6B818B] leading-relaxed">
              Traces transitive dependencies up to 3 hops through reverse BFS. Detects caller functions, parent components, and API routes before merge.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#55BDEB] shadow-card hover:shadow-card-hover transition-all">
            <div className="w-9 h-9 rounded-lg bg-[#E2F4FC] border border-[#55BDEB]/30 text-[#258FC7] flex items-center justify-center mb-3">
              <Network className="w-4.5 h-4.5 text-[#55BDEB]" />
            </div>
            <h3 className="font-bold text-sm text-[#172B35] mb-1.5">Code Knowledge Graph</h3>
            <p className="text-xs text-[#6B818B] leading-relaxed">
              Explore symbols, methods, and React components with on-demand lazy expansion and directional edge inspection without client overhead.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#16B89A] shadow-card hover:shadow-card-hover transition-all">
            <div className="w-9 h-9 rounded-lg bg-[#DDF7EF] border border-[#16B89A]/30 text-[#087F70] flex items-center justify-center mb-3">
              <BotMessageSquare className="w-4.5 h-4.5 text-[#16B89A]" />
            </div>
            <h3 className="font-bold text-sm text-[#172B35] mb-1.5">Evidence-Grounded RAG</h3>
            <p className="text-xs text-[#6B818B] leading-relaxed">
              Combines Graph RAG, BM25, and vector retrieval using LangGraph. Every statement is verified against code chunks to eliminate hallucinations.
            </p>
          </div>

          <div className="p-5 rounded-xl bg-white border border-[#E1ECEE] hover:border-[#55BDEB] shadow-card hover:shadow-card-hover transition-all">
            <div className="w-9 h-9 rounded-lg bg-[#E2F4FC] border border-[#55BDEB]/30 text-[#258FC7] flex items-center justify-center mb-3">
              <ShieldCheck className="w-4.5 h-4.5 text-[#55BDEB]" />
            </div>
            <h3 className="font-bold text-sm text-[#172B35] mb-1.5">Repository Intelligence</h3>
            <p className="text-xs text-[#6B818B] leading-relaxed">
              Targeted automated test suites, commit SHA indexing tracking, and persistent historical impact audits for complete repository confidence.
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-12 bg-white border-t border-[#E1ECEE] px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-8">
            <h2 className="text-xl font-bold text-[#172B35] mb-1">How It Works</h2>
            <p className="text-xs text-[#6B818B] font-mono">From Git Commit to Fine-Grained Intelligence</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            {[
              { step: '01', title: 'AST Extraction', desc: 'Parses Tree-sitter JS/TS & Python AST for functions, routes, and JSX.' },
              { step: '02', title: 'Graph Building', desc: 'Constructs directed NetworkX graph with imports, calls, renders, and tests.' },
              { step: '03', title: 'Impact Tracing', desc: 'Traverses reverse dependencies to pinpoint all impacted components.' },
              { step: '04', title: 'Verified Answers', desc: 'LangGraph workflow with hallucination detection and claim verification.' },
            ].map((s) => (
              <div
                key={s.step}
                className="p-4 rounded-xl bg-[#F5FAFA] border border-[#E1ECEE]"
              >
                <div className="text-[#087F70] font-mono text-xs font-bold mb-1.5">{s.step}</div>
                <div className="text-xs font-bold text-[#172B35] mb-1">{s.title}</div>
                <div className="text-[11px] text-[#6B818B] leading-relaxed">{s.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="h-14 border-t border-[#E1ECEE] bg-white flex items-center justify-between px-6 sm:px-8 text-xs text-[#6B818B] max-w-7xl w-full mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded bg-[#DDF7EF] flex items-center justify-center text-[#087F70]">
            <Layers className="w-3 h-3" />
          </div>
          <span className="font-semibold text-[#172B35]">ImpactIntel</span>
          <span>© 2026</span>
        </div>
        <div className="font-mono text-[#6B818B] text-[11px] hidden sm:block">
          FastAPI • NetworkX • Tree-sitter • LangGraph • React Flow
        </div>
      </footer>
    </div>
  );
}
