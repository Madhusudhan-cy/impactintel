import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  FileCode,
  Copy,
  Check,
} from 'lucide-react';
import PrathikshaAvatar from './PrathikshaAvatar';

function FormattedText({ content = '' }) {
  const codeBlockRegex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
  const parts = [];
  let lastIndex = 0;
  let match;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        value: content.substring(lastIndex, match.index),
      });
    }
    parts.push({
      type: 'code',
      lang: match[1] || 'text',
      value: match[2].trim(),
    });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push({
      type: 'text',
      value: content.substring(lastIndex),
    });
  }

  return (
    <div className="space-y-2 text-xs leading-relaxed">
      {parts.map((p, i) => {
        if (p.type === 'code') {
          return <CodeBlock key={i} code={p.value} lang={p.lang} />;
        }

        const paragraphs = p.value.split('\n\n');
        return (
          <div key={i} className="space-y-1.5">
            {paragraphs.map((para, pIdx) => {
              if (!para.trim()) return null;
              if (para.trim().startsWith('- ') || para.trim().startsWith('* ')) {
                const items = para.split('\n').filter(Boolean);
                return (
                  <ul key={pIdx} className="list-disc pl-4 space-y-0.5">
                    {items.map((item, itIdx) => (
                      <li key={itIdx}>
                        <InlineFormatted text={item.replace(/^[-*]\s*/, '')} />
                      </li>
                    ))}
                  </ul>
                );
              }

              return (
                <p key={pIdx} className="text-[#172B35]">
                  <InlineFormatted text={para} />
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function InlineFormatted({ text = '' }) {
  const regex = /(\*\*.*?\*\*|`.*?`)/g;
  const segments = text.split(regex);

  return (
    <>
      {segments.map((seg, idx) => {
        if (seg.startsWith('**') && seg.endsWith('**')) {
          return (
            <strong key={idx} className="font-semibold text-[#087F70]">
              {seg.slice(2, -2)}
            </strong>
          );
        }
        if (seg.startsWith('`') && seg.endsWith('`')) {
          return (
            <code
              key={idx}
              className="px-1.5 py-0.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] text-[#087F70] font-mono text-[11px]"
            >
              {seg.slice(1, -1)}
            </code>
          );
        }
        return <span key={idx}>{seg}</span>;
      })}
    </>
  );
}

function CodeBlock({ code, lang }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-lg border border-[#E1ECEE] bg-[#F5FAFA] overflow-hidden my-2">
      <div className="px-3 py-1 bg-[#DDF7EF]/40 border-b border-[#E1ECEE] flex items-center justify-between text-[10px] font-mono text-[#6B818B]">
        <span>{lang || 'code'}</span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1 hover:text-[#087F70] transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-[#16B89A]" /> : <Copy className="w-3 h-3" />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre className="p-3 text-[11px] font-mono text-[#172B35] overflow-x-auto leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function ChatMessage({ message }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const isUser = message.role === 'user';
  const isError = message.isError;
  const evidence = message.retrieval_evidence || [];

  if (isUser) {
    return (
      <div className="flex justify-end pl-8">
        <div className="bg-[#16B89A] text-white px-3.5 py-2 rounded-xl rounded-tr-sm text-xs shadow-sm max-w-[85%] leading-relaxed font-medium">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-2.5 pr-4 items-start">
      <PrathikshaAvatar size="sm" className="mt-0.5" />

      <div className="flex-1 min-w-0 space-y-2">
        <div
          className={`p-3 rounded-xl rounded-tl-sm text-xs bg-white border border-[#E1ECEE] shadow-sm ${
            isError ? 'border-rose-200 bg-rose-50/40 text-rose-800' : ''
          }`}
        >
          {/* Header pill */}
          <div className="flex items-center justify-between gap-2 mb-2 pb-1 border-b border-[#E1ECEE]">
            <span className="font-bold text-xs text-[#087F70]">
              Prathiksha
            </span>

            {message.is_verified ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-[#DDF7EF] text-[#087F70] border border-[#16B89A]/30">
                <ShieldCheck className="w-3 h-3 text-[#16B89A]" />
                <span>Verified Evidence</span>
              </span>
            ) : isError ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-mono font-medium bg-rose-50 text-rose-700 border border-rose-200">
                <ShieldAlert className="w-3 h-3 text-rose-500" />
                <span>Failed</span>
              </span>
            ) : null}
          </div>

          <FormattedText content={message.content} />

          {/* Entities identified */}
          {message.identified_entities && message.identified_entities.length > 0 && (
            <div className="mt-2 pt-2 border-t border-[#E1ECEE] flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] font-mono uppercase text-[#6B818B]">Symbols:</span>
              {message.identified_entities.map((sym, idx) => (
                <span
                  key={idx}
                  className="px-1.5 py-0.5 rounded bg-[#F5FAFA] border border-[#E1ECEE] text-[#087F70] font-mono text-[10px]"
                >
                  {sym}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Evidence panel expandable */}
        {evidence.length > 0 && (
          <div className="rounded-lg border border-[#E1ECEE] bg-white overflow-hidden text-xs shadow-sm">
            <button
              onClick={() => setShowEvidence(!showEvidence)}
              className="w-full px-3 py-1.5 bg-[#F5FAFA] hover:bg-[#DDF7EF]/40 flex items-center justify-between text-[11px] font-medium text-[#087F70] transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <FileCode className="w-3.5 h-3.5 text-[#16B89A]" />
                <span>Code Grounding Evidence ({evidence.length} sources)</span>
              </div>
              {showEvidence ? (
                <ChevronUp className="w-3.5 h-3.5 text-[#6B818B]" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-[#6B818B]" />
              )}
            </button>

            {showEvidence && (
              <div className="p-3 space-y-2 bg-white divide-y divide-[#E1ECEE]">
                {evidence.map((item, idx) => (
                  <div key={idx} className={idx > 0 ? 'pt-2' : ''}>
                    <div className="flex items-start justify-between gap-2 mb-1">
                      <div className="font-mono text-[11px] font-semibold text-[#172B35] truncate">
                        {item.file_path}
                      </div>
                      {item.symbol_type && (
                        <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-[#E2F4FC] text-[#258FC7]">
                          {item.symbol_type}
                        </span>
                      )}
                    </div>

                    <div className="text-[10px] font-mono text-[#6B818B] mb-1 flex items-center gap-2">
                      {item.symbol_name && <span>symbol: <strong>{item.symbol_name}</strong></span>}
                      {item.start_line != null && (
                        <span>
                          lines {item.start_line}-{item.end_line}
                        </span>
                      )}
                      {item.rrf_score != null && (
                        <span className="text-[#16B89A]">
                          score: {Number(item.rrf_score).toFixed(3)}
                        </span>
                      )}
                    </div>

                    {item.content && (
                      <pre className="p-2 rounded bg-[#F5FAFA] border border-[#E1ECEE] text-[10px] font-mono text-[#172B35] overflow-x-auto max-h-24">
                        <code>{item.content}</code>
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
