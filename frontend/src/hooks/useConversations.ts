import { useState, useCallback, useEffect } from 'react';
import type { Conversation } from '../types';
import { conversationApi } from '../api/client';

export function useConversations(enabled: boolean) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const res = await conversationApi.list();
      setConversations(res.data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const create = useCallback(async (title: string) => {
    const res = await conversationApi.create(title);
    setConversations(prev => [res.data, ...prev]);
    return res.data;
  }, []);

  return { conversations, loading, refresh, create };
}
