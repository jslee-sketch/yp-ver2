import { createContext, useContext, useState, useEffect } from 'react';
import type { ReactNode } from 'react';

interface SellerInfo {
  id: number;
  business_name: string;
  level: number;
  points: number;
}

export interface AuthUser {
  id: number;
  email: string;
  name: string;
  nickname?: string;
  role: 'buyer' | 'seller' | 'both' | 'admin' | 'actuator';
  level: number;
  points: number;
  trust_tier?: string;
  verified?: boolean;
  seller?: SellerInfo;
}

interface AuthContextType {
  user: AuthUser | null;
  isLoggedIn: boolean;
  isLoading: boolean;
  login: (token: string, user: AuthUser) => void;
  logout: () => void;
  updateUser: (updates: Partial<AuthUser>) => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser]       = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 초기 로드: localStorage에서 사용자 정보 복원
  useEffect(() => {
    const savedUser  = localStorage.getItem('user');
    const savedToken = localStorage.getItem('access_token');
    if (savedUser && savedToken) {
      try {
        setUser(JSON.parse(savedUser) as AuthUser);
      } catch {
        localStorage.removeItem('user');
        localStorage.removeItem('access_token');
      }
    }
    setIsLoading(false);
  }, []);

  const login = (token: string, userData: AuthUser) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setUser(null);
  };

  const updateUser = (updates: Partial<AuthUser>) => {
    if (user) {
      const updated = { ...user, ...updates };
      localStorage.setItem('user', JSON.stringify(updated));
      setUser(updated);
    }
  };

  return (
    <AuthContext.Provider value={{
      user,
      isLoggedIn: !!user,
      isLoading,
      login,
      logout,
      updateUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
