'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { loginWithGoogle } from './api';

export interface User {
  sub: string;
  email: string;
  name: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  token: string | null;
  login: (idToken: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function parseJwt(token: string): User | null {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload) as User;
  } catch (e) {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    const storedToken = localStorage.getItem('agent_jwt');
    if (storedToken) {
      const decoded = parseJwt(storedToken);
      if (decoded) {
        // Simple client side expiry check
        const exp = (decoded as any).exp;
        const now = Date.now() / 1000;
        if (exp && exp < now) {
          localStorage.removeItem('agent_jwt');
        } else {
          setToken(storedToken);
          setUser(decoded);
        }
      } else {
        localStorage.removeItem('agent_jwt');
      }
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!loading) {
      const isPublicPath = pathname === '/login';
      if (!user && !isPublicPath) {
        router.replace('/login');
      } else if (user && isPublicPath) {
        router.replace('/projects');
      }
    }
  }, [user, pathname, loading, router]);

  const login = async (idToken: string) => {
    try {
      const data = await loginWithGoogle(idToken);
      localStorage.setItem('agent_jwt', data.access_token);
      const decoded = parseJwt(data.access_token);
      setToken(data.access_token);
      setUser(decoded);
      router.push('/projects');
    } catch (error) {
      console.error('Google login failed:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('agent_jwt');
    setToken(null);
    setUser(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!user, user, token, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
