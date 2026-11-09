import React from 'react';

const VARIANTS = {
  primary: 'bg-[#DDF7EF] text-[#087F70] border-[#16B89A]/40',
  success: 'bg-emerald-500/10 text-[#087F70] border-emerald-500/20',
  warning: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
  danger: 'bg-rose-500/10 text-rose-700 border-rose-500/20',
  neutral: 'bg-[#F5FAFA] text-[#6B818B] border-[#E1ECEE]',
  info: 'bg-[#E2F4FC] text-[#258FC7] border-[#55BDEB]/40',
  blue: 'bg-[#E2F4FC] text-[#258FC7] border-[#55BDEB]/40',
};

export default function Badge({ children, variant = 'neutral', className = '' }) {
  const style = VARIANTS[variant] || VARIANTS.neutral;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium border ${style} ${className}`}
    >
      {children}
    </span>
  );
}
