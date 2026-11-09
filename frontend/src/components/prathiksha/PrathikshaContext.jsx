import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { chatApi } from '../../api/chat';

const PrathikshaContext = createContext(null);

export const SUGGESTED_QUESTIONS = [
  'Explain a function or module',
  'Analyze code dependencies',
  'Find related tests',
  'Explain this pull request',
];

export function PrathikshaProvider({ children }) {
  const { repoId } = useParams();
  const decodedRepo = repoId ? decodeURIComponent(repoId) : 'org/shop-repo';
  const [owner, repo] = decodedRepo.includes('/') ? decodedRepo.split('/') : ['org', decodedRepo];

  const [isOpen, setIsOpen] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState(null);
  const [currentRepoKey, setCurrentRepoKey] = useState(decodedRepo);

  // Isolate conversation by repository: reset if repository changes
  useEffect(() => {
    if (decodedRepo && decodedRepo !== currentRepoKey) {
      setCurrentRepoKey(decodedRepo);
      setConversationId(null);
      setMessages([]);
      setError(null);
    }
  }, [decodedRepo, currentRepoKey]);

  const resetConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setError(null);
  }, []);

  const sendMessage = useCallback(
    async (queryText) => {
      const trimmed = queryText.trim();
      if (!trimmed || isPending) return;

      setIsPending(true);
      setError(null);

      // Append user message immediately
      setMessages((prev) => [...prev, { role: 'user', content: trimmed }]);

      try {
        const res = await chatApi.ask(owner, repo, {
          query: trimmed,
          conversation_id: conversationId,
        });

        if (res.conversation_id) {
          setConversationId(res.conversation_id);
        }

        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: res.answer,
            is_verified: res.is_verified,
            retrieval_evidence: res.retrieval_evidence || [],
            identified_entities: res.identified_entities || [],
          },
        ]);
      } catch (err) {
        console.error('Prathiksha query error:', err);
        setError(err.message || 'Error communicating with assistant');
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: `I encountered an issue connecting to the code intelligence service: ${err.message || 'Unable to fetch answer'}. Please ensure the repository is indexed and try again.`,
            isError: true,
            is_verified: false,
          },
        ]);
      } finally {
        setIsPending(false);
      }
    },
    [owner, repo, conversationId, isPending]
  );

  return (
    <PrathikshaContext.Provider
      value={{
        isOpen,
        setIsOpen,
        toggleChat: () => setIsOpen((prev) => !prev),
        openChat: () => setIsOpen(true),
        closeChat: () => setIsOpen(false),
        messages,
        conversationId,
        isPending,
        error,
        sendMessage,
        resetConversation,
        activeRepo: decodedRepo,
        owner,
        repo,
      }}
    >
      {children}
    </PrathikshaContext.Provider>
  );
}

export function usePrathiksha() {
  const ctx = useContext(PrathikshaContext);
  if (!ctx) {
    // Safe defaults when used outside of PrathikshaProvider in tests
    return {
      isOpen: false,
      setIsOpen: () => {},
      toggleChat: () => {},
      openChat: () => {},
      closeChat: () => {},
      messages: [],
      conversationId: null,
      isPending: false,
      error: null,
      sendMessage: () => {},
      resetConversation: () => {},
      activeRepo: '',
      owner: '',
      repo: '',
    };
  }
  return ctx;
}
