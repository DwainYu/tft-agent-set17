// All backend endpoints (NO /api prefix)
export const ENDPOINTS = {
  ASK: '/ask',
  HEALTH: '/health',
  AUTH: {
    REGISTER: '/auth/register',
    LOGIN: '/auth/login',
    REFRESH: '/auth/refresh',
    ME: '/auth/me',
  },
  CONVERSATIONS: {
    LIST: '/conversations',
    CREATE: '/conversations',
    MESSAGES: (id: string | number) => `/conversations/${id}/messages`,
  },
  ASSETS: '/assets',
} as const;
