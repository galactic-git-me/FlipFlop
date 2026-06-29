import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

export function useAuth() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('auth_token');
    if (stored) setToken(stored);
    setLoading(false);
  }, []);

  const login = useCallback((newToken: string) => {
    localStorage.setItem('auth_token', newToken);
    setToken(newToken);
    router.push('/');
  }, [router]);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setToken(null);
    router.push('/login');
  }, [router]);

  return { token, loading, login, logout, isAuthenticated: !!token };
}
