import React, { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface User {
  id: string;
  phone: string;
  nickname: string;
  avatar: string;
  bio?: string;
  gender?: string;
  location?: string;
  school?: string;
  roles?: string[];
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
  checkAuth: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // 初始化时检查本地 Token
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const storedToken = localStorage.getItem('token');
    
    // 开发环境：自动使用默认UUID token
    const isDevelopment = import.meta.env.DEV;
    const effectiveToken = storedToken || (isDevelopment ? '00000000-0000-0000-0000-000000000001' : null);
    
    if (effectiveToken) {
      try {
        // 如果有 token，尝试获取用户信息
        // 注意：这里假设后端有一个 /user/me 接口。如果暂时没有，可以先模拟成功
        // const response = await authApi.getMe();
        // setUser(response.data.data);
        
        // Mock user data for now if API fails or is not ready
        const mockUser = {
          id: isDevelopment ? '00000000-0000-0000-0000-000000000001' : 'u1',
          phone: '13800138000',
          nickname: '测试用户',
          avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=200&q=80'
        };
        
        setUser(mockUser);
        setToken(effectiveToken);
        
        // 在开发环境中，如果没有存储token，自动保存默认token
        if (isDevelopment && !storedToken) {
          localStorage.setItem('token', effectiveToken);
        }
      } catch (error) {
        console.error('Auth check failed', error);
        // 开发环境中即使出错也保持登录状态
        if (!isDevelopment) {
          logout();
        }
      }
    }
    setIsLoading(false);
  };

  const login = (newToken: string, newUser: User) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setUser(newUser);
  };

  const logout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  const updateUser = (updatedUser: User) => {
    setUser(updatedUser);
  };

  return (
    <AuthContext.Provider value={{ 
      user, 
      token, 
      isLoading, 
      isAuthenticated: !!user, 
      login, 
      logout,
      checkAuth,
      updateUser
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
