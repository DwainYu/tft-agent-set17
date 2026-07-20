import { useState, useCallback, useEffect } from 'react';
import type { UserInfo, TokenResponse } from '../types';
import { authApi } from '../api/client';

export function useAuth() {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // Try to restore session on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      authApi.me()
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const saveTokens = (data: TokenResponse) => {
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
  };

  const login = useCallback(async (phone: string, password: string) => {
    const res = await authApi.login(phone, password);
    saveTokens(res.data);
    const meRes = await authApi.me();
    setUser(meRes.data);
    return res.data;
  }, []);

  const register = useCallback(async (phone: string, password: string, sms_code: string) => {
    const res = await authApi.register(phone, password, sms_code);
    saveTokens(res.data);
    const meRes = await authApi.me();
    setUser(meRes.data);
    return res.data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  }, []);

  return { user, loading, login, register, logout };
}
