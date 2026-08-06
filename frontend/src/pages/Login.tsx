import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Smartphone, Lock, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
// import { authApi } from '../services/api';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [showCode, setShowCode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Get the redirect path from location state, or default to home
  const from = (location.state as any)?.from?.pathname || '/';

  const handleSendCode = async () => {
    if (phone.length === 11) {
      setIsLoading(true);
      try {
        // In a real app, you would call api.sendCode(phone)
        // await authApi.sendCode(phone, 'login');
        
        // Mock delay
        setTimeout(() => {
            setShowCode(true);
            setIsLoading(false);
            // alert('验证码已发送: 123456'); // For demo
        }, 1000);
      } catch (error) {
        alert('发送验证码失败');
        setIsLoading(false);
      }
    } else {
      alert('请输入正确的手机号');
    }
  };

  const handleLogin = async () => {
    if (code === '123456') {
      setIsLoading(true);
      try {
        // In a real app:
        // const res = await authApi.loginByPhone(phone, code);
        // login(res.data.token, res.data.user);
        
        // Mock login
        setTimeout(() => {
            login('mock-jwt-token', {
                id: 'u1',
                phone: phone,
                nickname: '测试用户',
                avatar: 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=200&q=80'
            });
            navigate(from, { replace: true });
        }, 1000);
      } catch (error) {
        alert('登录失败');
        setIsLoading(false);
      }
    } else {
      alert('验证码错误 (测试码: 123456)');
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col px-8 pt-20">
      <h1 className="text-3xl font-bold mb-2">欢迎回来</h1>
      <p className="text-gray-500 mb-12">登录体验更精彩的学习旅程</p>

      <div className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700">手机号</label>
          <div className="flex items-center gap-3 bg-gray-50 p-4 rounded-xl border border-gray-100 focus-within:border-blue-500 focus-within:bg-white transition-colors">
            <Smartphone className="text-gray-400" size={20} />
            <input 
              type="tel" 
              placeholder="请输入手机号" 
              className="flex-1 bg-transparent outline-none font-medium"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              maxLength={11}
              disabled={isLoading}
            />
          </div>
        </div>

        {showCode && (
          <div className="space-y-2 animate-in fade-in slide-in-from-bottom-4">
            <label className="text-sm font-medium text-gray-700">验证码 (测试: 123456)</label>
            <div className="flex items-center gap-3 bg-gray-50 p-4 rounded-xl border border-gray-100 focus-within:border-blue-500 focus-within:bg-white transition-colors">
              <Lock className="text-gray-400" size={20} />
              <input 
                type="number" 
                placeholder="请输入验证码" 
                className="flex-1 bg-transparent outline-none font-medium"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={6}
                disabled={isLoading}
              />
            </div>
          </div>
        )}

        <button 
          onClick={showCode ? handleLogin : handleSendCode}
          disabled={isLoading}
          className="w-full bg-black text-white py-4 rounded-xl font-bold text-lg flex items-center justify-center gap-2 hover:opacity-90 active:scale-95 transition-all mt-8 disabled:opacity-50"
        >
          {isLoading ? '处理中...' : (showCode ? '登录' : '获取验证码')}
          {!isLoading && <ArrowRight size={20} />}
        </button>

        <p className="text-center text-xs text-gray-400 mt-4">
          登录即代表同意 <a href="#" className="text-blue-500">用户协议</a> 和 <a href="#" className="text-blue-500">隐私政策</a>
        </p>
      </div>
    </div>
  );
};
