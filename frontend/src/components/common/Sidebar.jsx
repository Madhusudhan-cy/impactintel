import React from 'react';
import { NavLink, useParams, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  GitPullRequest,
  Network,
  History,
  Settings,
  FolderGit2,
  ChevronDown,
  Layers,
  X,
} from 'lucide-react';

export default function Sidebar({ repoInfo, mobileOpen = false, onCloseMobile }) {
  const { repoId } = useParams();
  const navigate = useNavigate();

  const currentRepo = repoInfo
    ? `${repoInfo.owner}/${repoInfo.name}`
    : (repoId ? decodeURIComponent(repoId) : 'org/shop-repo');

  const navItems = [
    {
      to: `/repositories/${encodeURIComponent(currentRepo)}/overview`,
      label: 'Overview',
      icon: LayoutDashboard,
    },
    {
      to: `/repositories/${encodeURIComponent(currentRepo)}/pull-requests`,
      label: 'Pull Requests',
      icon: GitPullRequest,
    },
    {
      to: `/repositories/${encodeURIComponent(currentRepo)}/graph`,
      label: 'Knowledge Graph',
      icon: Network,
    },
    {
      to: `/repositories/${encodeURIComponent(currentRepo)}/history`,
      label: 'Analysis History',
      icon: History,
    },
    {
      to: `/repositories/${encodeURIComponent(currentRepo)}/settings`,
      label: 'Settings',
      icon: Settings,
    },
  ];

  const handleNavClick = () => {
    if (onCloseMobile) {
      onCloseMobile();
    }
  };

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-[#172B35]/20 backdrop-blur-sm z-40 md:hidden"
          onClick={onCloseMobile}
        />
      )}

      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 w-60 bg-white border-r border-[#E1ECEE] flex flex-col justify-between shrink-0 shadow-sm transition-transform duration-200 ease-in-out md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          {/* Brand Header */}
          <div className="h-14 border-b border-[#E1ECEE] flex items-center justify-between px-4">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-[#16B89A] to-[#087F70] flex items-center justify-center text-white shadow-sm">
                <Layers className="w-4 h-4" />
              </div>
              <div>
                <div className="font-bold text-xs text-[#172B35] tracking-tight leading-none">
                  ImpactIntel
                </div>
                <div className="text-[10px] text-[#6B818B] font-mono mt-0.5">
                  Code Intelligence
                </div>
              </div>
            </div>

            {onCloseMobile && (
              <button
                onClick={onCloseMobile}
                className="md:hidden p-1 rounded-md text-[#6B818B] hover:text-[#172B35] hover:bg-[#F5FAFA]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Repository Switcher */}
          <div className="p-3 border-b border-[#E1ECEE]">
            <button
              onClick={() => {
                navigate('/repositories');
                handleNavClick();
              }}
              className="w-full flex items-center justify-between p-2 rounded-lg bg-[#F5FAFA] hover:bg-[#DDF7EF]/40 border border-[#E1ECEE] hover:border-[#16B89A]/50 transition-all text-left group cursor-pointer"
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-6 h-6 rounded-md bg-[#DDF7EF] flex items-center justify-center shrink-0 text-[#087F70]">
                  <FolderGit2 className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0">
                  <div className="text-[9px] text-[#6B818B] uppercase font-bold tracking-wider leading-none">
                    Active Repo
                  </div>
                  <div className="text-xs font-mono font-semibold text-[#172B35] truncate group-hover:text-[#087F70] transition-colors mt-0.5">
                    {currentRepo}
                  </div>
                </div>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-[#6B818B] group-hover:text-[#087F70] shrink-0 ml-1 transition-colors" />
            </button>
          </div>

          {/* Navigation Links */}
          <nav className="p-2.5 space-y-0.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={handleNavClick}
                  className={({ isActive }) =>
                    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-[#DDF7EF] text-[#087F70] font-semibold border border-[#16B89A]/30'
                        : 'text-[#6B818B] hover:text-[#172B35] hover:bg-[#F5FAFA]'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-[#E1ECEE] bg-[#F5FAFA]/60 text-[10px] text-[#6B818B] font-mono flex items-center justify-between">
          <span>ImpactIntel Platform</span>
          <span className="flex items-center gap-1 text-[#087F70]">
            <span className="w-1.5 h-1.5 rounded-full bg-[#16B89A]"></span>
            <span>v2.2</span>
          </span>
        </div>
      </aside>
    </>
  );
}
