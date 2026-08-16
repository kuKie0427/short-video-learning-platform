/**
 * ProtectedRoute 路由守卫测试
 *
 * 覆盖三类状态：
 * - 未登录访问受保护页 → 重定向 /login
 * - 已登录访问受保护页 → 正常渲染内容
 * - 登录态加载中 → 显示 Loading，不提前重定向（避免闪烁跳转）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from '../components/ProtectedRoute';

// 用可变对象控制 useAuth 返回值，每个用例设置不同状态
const mocks = vi.hoisted(() => ({
  auth: { isAuthenticated: false, isLoading: false },
}));

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mocks.auth,
}));

const renderRoute = () =>
  render(
    <MemoryRouter initialEntries={['/profile']}>
      <Routes>
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <div>PROTECTED_CONTENT</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>LOGIN_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  );

describe('ProtectedRoute', () => {
  beforeEach(() => {
    mocks.auth = { isAuthenticated: false, isLoading: false };
  });

  it('未登录访问受保护页：重定向到登录页', () => {
    renderRoute();

    expect(screen.getByText('LOGIN_PAGE')).toBeInTheDocument();
    expect(screen.queryByText('PROTECTED_CONTENT')).not.toBeInTheDocument();
  });

  it('已登录访问受保护页：正常渲染子内容', () => {
    mocks.auth = { isAuthenticated: true, isLoading: false };
    renderRoute();

    expect(screen.getByText('PROTECTED_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
  });

  it('登录态加载中：显示 Loading 且不重定向', () => {
    mocks.auth = { isAuthenticated: false, isLoading: true };
    renderRoute();

    expect(screen.getByText('Loading...')).toBeInTheDocument();
    expect(screen.queryByText('LOGIN_PAGE')).not.toBeInTheDocument();
    expect(screen.queryByText('PROTECTED_CONTENT')).not.toBeInTheDocument();
  });
});
