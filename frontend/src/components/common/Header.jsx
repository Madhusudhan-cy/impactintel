import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { LogOut, Activity, Menu, GitBranch } from 'lucide-react';

export default function Header({
  title,
  subtitle,
  breadcrumbs = [],
  branch = 'main',
  onMenuToggle,
}) {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 border-b border-[#E1ECEE] bg-white px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      <div className="flex items-center gap-3 min-w-0">
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="md:hidden p-1.5 rounded-md text-[#6B818B] hover:text-[#172B35] hover:bg-[#F5FAFA] transition-colors"
            title="Toggle Sidebar"
          >
            <Menu className="w-4.5 h-4.5" />
          </button>
        )}

        <div className="min-w-0">
          {breadcrumbs.length > 0 && (
            <div className="flex items-center gap-1.5 text-[11px] text-[#6B818B] leading-none mb-1">
              {breadcrumbs.map((crumb, idx) => (
                <React.Fragment key={idx}>
                  {idx > 0 && <span className="text-[#CBEAE7]">/</span>}
                  <span
                    className={
                      idx === breadcrumbs.length - 1
                        ? 'text-[#172B35] font-semibold'
                        : 'truncate'
                    }
                  >
                    {crumb}
                  </span>
                </React.Fragment>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2">
            <h1 className="text-sm sm:text-base font-bold text-[#172B35] leading-none">
              {title}
            </h1>
            {subtitle && (
              <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono text-[#6B818B] bg-[#F5FAFA] px-2 py-0.5 rounded border border-[#E1ECEE]">
                <span>{subtitle}</span>
                {branch && (
                  <>
                    <span className="text-[#CBEAE7]">•</span>
                    <span className="flex items-center gap-0.5 text-[#087F70]">
                      <GitBranch className="w-3 h-3 text-[#16B89A]" />
                      <span>{branch}</span>
                    </span>
                  </>
                )}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* GitHub Connection Status */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#DDF7EF] border border-[#16B89A]/30 text-[#087F70] text-[11px] font-mono font-medium">
          <Activity className="w-3 h-3 text-[#16B89A] animate-pulse" />
          <span>Connected</span>
        </div>

        {user && (
          <div className="flex items-center gap-2 pl-2 sm:pl-3 border-l border-[#E1ECEE]">
            <img
              src={user.avatar_url || 'https://avatars.githubusercontent.com/u/583231'}
              alt={user.login}
              className="w-7 h-7 rounded-full border border-[#E1ECEE] object-cover ring-1 ring-[#16B89A]/30"
            />
            <div className="hidden md:block text-left text-xs leading-tight">
              <div className="font-semibold text-[#172B35]">{user.name || user.login}</div>
              <div className="text-[#6B818B] font-mono text-[10px]">@{user.login}</div>
            </div>
            <button
              onClick={logout}
              title="Sign out"
              className="p-1 rounded-md text-[#6B818B] hover:text-rose-600 hover:bg-rose-50 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
