import axios from 'axios';
import type { SSEEvent, AskRequest, TokenResponse, UserInfo, Conversation, Message } from '../types';
import { ENDPOINTS } from './endpoints';

// Axios instance - NO baseURL prefix since backend has no /api prefix
export const http = axios.create({
  timeout: 30000,
});

// JWT interceptor
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// SSE streaming for /ask endpoint
export async function postAsk(
  req: AskRequest,
  onEvent: (e: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('access_token') || '';
  const res = await fetch(ENDPOINTS.ASK, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body?.getReader();
  if (!reader) throw new Error('No response body');
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // SSE events are separated by \n\n
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith('data: ')) {
        try {
          const event = JSON.parse(line.slice(6)) as SSEEvent;
          onEvent(event);
        } catch {
          // skip malformed events
        }
      }
    }
  }
  // Process remaining buffer
  if (buffer.trim().startsWith('data: ')) {
    try {
      const event = JSON.parse(buffer.trim().slice(6)) as SSEEvent;
      onEvent(event);
    } catch {
      // skip
    }
  }
}

// Auth API
export const authApi = {
  register: (phone: string, password: string, sms_code: string) =>
    http.post<TokenResponse>(ENDPOINTS.AUTH.REGISTER, { phone, password, sms_code }),
  login: (phone: string, password: string) =>
    http.post<TokenResponse>(ENDPOINTS.AUTH.LOGIN, { phone, password }),
  refresh: (refresh_token: string) =>
    http.post<TokenResponse>(ENDPOINTS.AUTH.REFRESH, { refresh_token }),
  me: () =>
    http.get<UserInfo>(ENDPOINTS.AUTH.ME),
};

// Conversations API
export const conversationApi = {
  list: () => http.get<Conversation[]>(ENDPOINTS.CONVERSATIONS.LIST),
  create: (title: string) => http.post<Conversation>(ENDPOINTS.CONVERSATIONS.CREATE, { title }),
  getMessages: (id: string | number) =>
    http.get<Message[]>(ENDPOINTS.CONVERSATIONS.MESSAGES(id)),
  addMessage: (id: string | number, role: string, content: string) =>
    http.post<Message>(ENDPOINTS.CONVERSATIONS.MESSAGES(id), { role, content }),
};
