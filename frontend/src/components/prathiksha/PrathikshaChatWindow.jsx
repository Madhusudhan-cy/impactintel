import React, { useState, useRef, useEffect } from 'react';
import {
  X,
  Minus,
  RotateCcw,
  Send,
  Loader2,
  Sparkles,
  HelpCircle,
} from 'lucide-react';
import { usePrathiksha, SUGGESTED_QUESTIONS } from './PrathikshaContext';
import PrathikshaAvatar from './PrathikshaAvatar';
import ChatMessage from './ChatMessage';

export default function PrathikshaChatWindow() {
  const {
    isOpen,
    closeChat,
    messages,
    sendMessage,
    isPending,
    resetConversation,
    activeRepo,
  } = usePrathiksha();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      inputRef.current?.focus();
    }
  }, [isOpen, messages, isPending]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e?.preventDefault();
    if (!input.trim() || isPending) return;
    const text = input;
    setInput('');
    sendMessage(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSuggestionClick = (question) => {
    sendMessage(question);
  };

  const showWelcome = messages.length === 0;

  return (
    <div
      className="fixed bottom-20 right-4 sm:right-6 z-50 w-[calc(100vw-2rem)] sm:w-[380px] h-[520px] max-h-[calc(100vh-6rem)] bg-white rounded-2xl border border-[#E1ECEE] shadow-card-hover flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-3 duration-150"
      role="dialog"
      aria-label="Prathiksha Chat Window"
    >
      {/* Header */}
      <div className="px-3.5 py-2.5 bg-[#F5FAFA] border-b border-[#E1ECEE] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <PrathikshaAvatar size="xs" />
          <div className="min-w-0">
            <div className="flex items-center gap-1.5 leading-none">
              <span className="font-bold text-xs text-[#172B35]">Prathiksha</span>
              <span className="inline-flex items-center gap-1 text-[10px] text-[#087F70] font-medium font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-[#16B89A] animate-pulse"></span>
                <span>Online</span>
              </span>
            </div>
            <div className="text-[10px] text-[#6B818B] font-mono truncate mt-0.5">
              {activeRepo}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-0.5">
          <button
            onClick={resetConversation}
            title="Start new conversation"
            className="p-1.5 rounded-md text-[#6B818B] hover:text-[#087F70] hover:bg-[#DDF7EF] transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={closeChat}
            title="Minimize"
            className="p-1.5 rounded-md text-[#6B818B] hover:text-[#172B35] hover:bg-[#DDF7EF] transition-colors"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={closeChat}
            title="Close"
            className="p-1.5 rounded-md text-[#6B818B] hover:text-rose-600 hover:bg-rose-50 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Message Body / Welcome Screen */}
      <div className="flex-1 p-3.5 overflow-y-auto space-y-3 bg-[#F5FAFA]/30">
        {showWelcome ? (
          <div className="h-full flex flex-col justify-between py-2">
            <div className="text-center space-y-2.5 my-auto">
              <div className="flex justify-center">
                <PrathikshaAvatar size="lg" />
              </div>

              <div className="space-y-1 px-3">
                <h3 className="font-bold text-sm text-[#172B35] tracking-tight">
                  Hey, I'm Prathiksha! How can I help you?
                </h3>
                <p className="text-xs text-[#6B818B] leading-relaxed">
                  I'm your repository assistant. I can help you understand your codebase,
                  analyze pull requests, explore dependencies, and find answers using code evidence.
                </p>
              </div>
            </div>

            {/* Suggested Questions */}
            <div className="space-y-1.5 pt-2">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-[#6B818B] px-1 font-semibold">
                <HelpCircle className="w-3 h-3 text-[#16B89A]" />
                <span>Suggested Questions</span>
              </div>
              <div className="grid grid-cols-1 gap-1.5">
                {SUGGESTED_QUESTIONS.map((question, qIdx) => (
                  <button
                    key={qIdx}
                    onClick={() => handleSuggestionClick(question)}
                    className="w-full text-left px-3 py-1.5 rounded-lg bg-white hover:bg-[#DDF7EF]/60 border border-[#E1ECEE] hover:border-[#16B89A] text-xs font-medium text-[#172B35] hover:text-[#087F70] transition-all shadow-sm flex items-center justify-between group cursor-pointer"
                  >
                    <span>{question}</span>
                    <Sparkles className="w-3.5 h-3.5 text-[#55BDEB] group-hover:text-[#16B89A] transition-colors shrink-0 ml-1.5" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg, idx) => (
              <ChatMessage key={idx} message={msg} />
            ))}

            {isPending && (
              <div className="flex gap-2.5 pr-4 items-start animate-in fade-in duration-150">
                <PrathikshaAvatar size="sm" className="mt-0.5 animate-pulse" />
                <div className="p-3 rounded-xl rounded-tl-sm text-xs bg-white border border-[#E1ECEE] shadow-sm flex items-center gap-2 text-[#087F70]">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#16B89A]" />
                  <span className="font-mono text-[11px]">
                    Analyzing codebase with LangGraph...
                  </span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Form */}
      <form
        onSubmit={handleSubmit}
        className="p-2.5 bg-white border-t border-[#E1ECEE] flex items-center gap-2 shrink-0"
      >
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Prathiksha about code or PRs..."
          rows={1}
          disabled={isPending}
          className="flex-1 resize-none py-1.5 px-3 text-xs bg-[#F5FAFA] border border-[#E1ECEE] rounded-lg text-[#172B35] placeholder-[#6B818B] focus:outline-none focus:border-[#16B89A] focus:ring-1 focus:ring-[#16B89A] transition-all"
        />

        <button
          type="submit"
          disabled={!input.trim() || isPending}
          className="p-2 rounded-lg bg-[#16B89A] hover:bg-[#087F70] disabled:opacity-40 disabled:hover:bg-[#16B89A] text-white transition-all shadow-sm cursor-pointer shrink-0"
          title="Send message"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
}
