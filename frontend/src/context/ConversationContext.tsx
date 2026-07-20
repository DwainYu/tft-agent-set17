import { createContext, useContext, ReactNode, useState, useCallback } from 'react';
import type { Conversation } from '../types';
import { useConversations } from '../hooks/useConversations';
import { useAuthContext } from './AuthContext';

interface ConversationContextValue {
  conversations: Conversation[];
  loading: boolean;
  refresh: () => Promise<void>;
  create: (title: string) => Promise<Conversation>;
  selectedId: number | null;
  selectConversation: (id: number) => void;
  createConversation: () => Promise<void>;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

export function ConversationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuthContext();
  const conv = useConversations(!!user);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const createConversation = useCallback(async () => {
    const newConv = await conv.create('新对话');
    setSelectedId(newConv.id);
  }, [conv]);

  return (
    <ConversationContext.Provider
      value={{
        ...conv,
        selectedId,
        selectConversation: setSelectedId,
        createConversation,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

export function useConversationContext(): ConversationContextValue {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error('useConversationContext must be used within ConversationProvider');
  return ctx;
}
