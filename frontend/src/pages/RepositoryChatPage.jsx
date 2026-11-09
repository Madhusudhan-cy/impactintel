import React, { useState, useRef, useEffect } from 'react';
import { useParams, useOutletContext } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { chatApi } from '../api/chat';
import Header from '../components/common/Header';
import {
  Send,
  ShieldCheck,
  RotateCcw,
  Sparkles,
  FileCode,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import PrathikshaAvatar from '../components/prathiksha/PrathikshaAvatar';

export default function RepositoryChatPage() {
  const { repoId } = useParams();
  const outletCtx = useOutletContext();
  const decodedRepo = decodeURIComponent(repoId || 'org/shop-repo');
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello! I am your conversational repository impact assistant. Ask me anything about ${decodedRepo}'s architecture, callers, callee functions, or tests.`,
      retrieval_evidence: [],
      is_verified: true,
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [expandedEvidenceIdx, setExpandedEvidenceIdx] = useState(null);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const chatMutation = useMutation({
    mutationFn: (queryText) =>
      chatApi.ask(owner, repo, {
        query: queryText,
        conversation_id: conversationId,
      }),
    onSuccess: (data) => {
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.answer,
          is_verified: data.is_verified,
          retrieval_evidence: data.retrieval_evidence || [],
          identified_entities: data.identified_entities || [],
        },
      ]);
    },
    onError: (err) => {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `Error generating repository response: ${err.message}`,
          is_verified: false,
          isError: true,
        },
      ]);
    },
  });

  const handleSendMessage = (e) => {
    e?.preventDefault();
    if (!inputQuery.trim() || chatMutation.isPending) return;

    const query = inputQuery.trim();
    setInputQuery('');
    setMessages((prev) => [...prev, { role: 'user', content: query }]);
    chatMutation.mutate(query);
  };

  const handleNewConversation = () => {
    setConversationId(null);
    setMessages([
      {
        role: 'assistant',
        content: `Started a new conversation session for ${decodedRepo}. Context has been reset.`,
        is_verified: true,
      },
    ]);
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden bg-[#F5FAFA]">
      <Header
        title="Repository AI Intelligence Chat"
        subtitle={decodedRepo}
        breadcrumbs={['Repositories', decodedRepo, 'AI Chat']}
        onMenuToggle={outletCtx?.openMobileSidebar}
      />

      <div className="flex-1 flex flex-col justify-between max-w-4xl w-full mx-auto p-4 sm:p-5 overflow-hidden">
        {/* Chat Actions Header */}
        <div className="flex items-center justify-between pb-2.5 border-b border-[#E1ECEE] text-xs font-mono text-[#6B818B]">
          <div className="flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-[#16B89A]" />
            <span>Hybrid Graph RAG + BM25 + Vector Verification</span>
          </div>

          <button
            onClick={handleNewConversation}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white border border-[#E1ECEE] text-[#087F70] hover:border-[#16B89A] shadow-sm transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3 h-3" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex gap-2.5 sm:gap-3.5 ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.role === 'assistant' && (
                <PrathikshaAvatar size="sm" className="mt-0.5" />
              )}

              <div
                className={`max-w-2xl rounded-xl p-3.5 sm:p-4 text-xs leading-relaxed space-y-2.5 shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-[#16B89A] text-white font-medium rounded-tr-sm'
                    : 'bg-white border border-[#E1ECEE] text-[#172B35] rounded-tl-sm'
                }`}
              >
                {/* Verification Badge */}
                {msg.role === 'assistant' && msg.is_verified && (
                  <div className="flex items-center gap-1.5 text-[10px] font-mono font-medium text-[#087F70] pb-1.5 border-b border-[#E1ECEE]">
                    <ShieldCheck className="w-3.5 h-3.5 text-[#16B89A]" />
                    <span>Grounded & Verified Evidence</span>
                  </div>
                )}

                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Evidence References */}
                {msg.retrieval_evidence && msg.retrieval_evidence.length > 0 && (
                  <div className="pt-2 border-t border-[#E1ECEE] space-y-2">
                    <button
                      onClick={() =>
                        setExpandedEvidenceIdx(expandedEvidenceIdx === idx ? null : idx)
                      }
                      className="flex items-center gap-1.5 text-[10px] font-mono text-[#087F70] hover:underline"
                    >
                      <FileCode className="w-3 h-3 text-[#16B89A]" />
                      <span>
                        {msg.retrieval_evidence.length} Code Grounding Evidence Sources
                      </span>
                      {expandedEvidenceIdx === idx ? (
                        <ChevronUp className="w-3 h-3 ml-1" />
                      ) : (
                        <ChevronDown className="w-3 h-3 ml-1" />
                      )}
                    </button>

                    {expandedEvidenceIdx === idx && (
                      <div className="space-y-1.5 pt-1">
                        {msg.retrieval_evidence.map((item, cIdx) => (
                          <div
                            key={cIdx}
                            className="p-2.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] font-mono text-[10px] space-y-1 text-[#172B35]"
                          >
                            <div className="flex items-center justify-between text-[#087F70] font-bold">
                              <span>{item.file_path}</span>
                              <span className="text-[9px] text-[#6B818B]">
                                {item.symbol_type} • lines {item.start_line}-{item.end_line}
                              </span>
                            </div>
                            <pre className="text-[10px] text-[#172B35] overflow-x-auto p-1.5 rounded bg-white border border-[#E1ECEE]">
                              <code>{item.content}</code>
                            </pre>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Form */}
        <form
          onSubmit={handleSendMessage}
          className="pt-3 border-t border-[#E1ECEE] flex items-center gap-2.5"
        >
          <input
            type="text"
            placeholder="Ask about functions, routes, callers, or PR blast radius..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            disabled={chatMutation.isPending}
            className="flex-1 px-3.5 py-2.5 rounded-lg bg-white border border-[#E1ECEE] text-xs text-[#172B35] placeholder-[#6B818B] focus:outline-none focus:border-[#16B89A] shadow-sm"
          />

          <button
            type="submit"
            disabled={!inputQuery.trim() || chatMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg bg-[#16B89A] hover:bg-[#087F70] disabled:opacity-40 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </form>
      </div>
    </div>
  );
}
