import { createContext, useContext, ReactNode } from 'react';
import type { UserInfo } from '../types';
import { useAuth } from '../hooks/useAuth';

interface AuthContextValue {
  user: UserInfo | null;
  loading: boolean;
  login: (phone: string, password: string) => Promise<unknown>;
  register: (phone: string, password: string, sms_code: string) => Promise<unknown>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const auth = useAuth();
  return <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>;
}

export function useAuthContext(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuthContext must be used within AuthProvider');
  return ctx;
}
