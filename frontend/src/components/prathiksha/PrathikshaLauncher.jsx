import React from 'react';
import { usePrathiksha } from './PrathikshaContext';
import PrathikshaAvatar from './PrathikshaAvatar';

export default function PrathikshaLauncher() {
  const { isOpen, toggleChat, messages } = usePrathiksha();

  return (
    <div className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5">
      {/* Tooltip badge when collapsed */}
      {!isOpen && messages.length === 0 && (
        <div
          onClick={toggleChat}
          className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/95 backdrop-blur-md border border-[#E1ECEE] shadow-sm text-xs font-medium text-[#087F70] cursor-pointer hover:border-[#16B89A] transition-all"
        >
          <span className="w-2 h-2 rounded-full bg-[#16B89A]"></span>
          <span>Ask Prathiksha</span>
        </div>
      )}

      {/* Floating circular button */}
      <button
        onClick={toggleChat}
        aria-label={isOpen ? 'Close Prathiksha chat' : 'Open Prathiksha assistant'}
        className={`relative w-12 h-12 rounded-full bg-gradient-to-tr from-[#16B89A] to-[#55BDEB] border-2 border-white shadow-aqua-glow hover:shadow-lg hover:scale-105 active:scale-95 transition-all duration-200 flex items-center justify-center p-0.5 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#16B89A]/40 ${
          isOpen ? 'ring-2 ring-[#16B89A] scale-95' : ''
        }`}
      >
        <PrathikshaAvatar size="sm" className="!w-9 !h-9 shadow-none border-none bg-transparent" />

        {/* Live status dot */}
        <span className="absolute top-0.5 right-0.5 w-2.5 h-2.5 rounded-full bg-[#16B89A] border-2 border-white"></span>
      </button>
    </div>
  );
}
