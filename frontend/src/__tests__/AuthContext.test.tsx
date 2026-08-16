/**
 * AuthContext 状态管理测试（真实 Provider）
 *
 * 覆盖认证状态机的核心状态迁移：
 * - login: 未登录 → 已登录（token 持久化到 localStorage）
 * - logout: 已登录 → 未登录（token 清理）
 * - updateUser: 用户信息更新
 *
 * 注意：开发环境下 checkAuth 会自动注入默认 token（import.meta.env.DEV），
 * 因此用操作后的状态断言，而非初始状态。
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from '../context/AuthContext';

// 测试探针组件：暴露 context 状态与操作入口
function AuthHarness() {
  const auth = useAuth();
  return (
    <div>
      <span data-testid="user">{auth.user ? auth.user.nickname : 'none'}</span>
      <span data-testid="token">{auth.token ?? 'none'}</span>
      <button onClick={() => auth.login('tk-1', {
        id: 'u1',
        phone: '13800138000',
        nickname: '登录用户',
        avatar: '',
      })}>login</button>
      <button onClick={auth.logout}>logout</button>
      <button onClick={() => auth.user && auth.updateUser({ ...auth.user, nickname: '新昵称' })}>
        update
      </button>
    </div>
  );
}

const renderHarness = () =>
  render(
    <AuthProvider>
      <AuthHarness />
    </AuthProvider>
  );

describe('AuthContext', () => {
  it('login：设置用户态并持久化 token 到 localStorage', async () => {
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByRole('button', { name: 'login' }));

    expect(screen.getByTestId('user')).toHaveTextContent('登录用户');
    expect(screen.getByTestId('token')).toHaveTextContent('tk-1');
    expect(localStorage.getItem('token')).toBe('tk-1');
  });

  it('logout：清空用户态与 localStorage token', async () => {
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByRole('button', { name: 'login' }));
    await user.click(screen.getByRole('button', { name: 'logout' }));

    expect(screen.getByTestId('user')).toHaveTextContent('none');
    expect(screen.getByTestId('token')).toHaveTextContent('none');
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('updateUser：更新用户昵称且不影响登录态', async () => {
    const user = userEvent.setup();
    renderHarness();

    await user.click(screen.getByRole('button', { name: 'login' }));
    await user.click(screen.getByRole('button', { name: 'update' }));

    expect(screen.getByTestId('user')).toHaveTextContent('新昵称');
    // 登录态保持
    expect(screen.getByTestId('token')).toHaveTextContent('tk-1');
  });
});
