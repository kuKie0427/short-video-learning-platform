/**
 * 登录页组件测试（Vitest + React Testing Library）
 *
 * 测试策略：黑盒行为验证——模拟用户操作，断言 UI 反馈与登录副作用，
 * 不关心内部实现。覆盖用例设计方法中的等价类与边界值：
 * - 等价类：合法手机号（11 位）/ 非法手机号（10 位）
 * - 等价类：正确验证码（123456）/ 错误验证码
 * - 时序边界：验证码输入框在 mock 延迟后出现
 *
 * 注意：当前登录页为 mock 实现（见 src/pages/Login.tsx），
 * 真实登录 API 链路由后端集成测试覆盖（backend/tests/api/test_auth.py）。
 *
 * 定时器说明：登录页使用 setTimeout 模拟 1 秒网络延迟。
 * 本环境 user-event 与 fake timers 存在兼容问题（type 会挂起），
 * 故使用真实定时器 + 显式超时，用例间相互独立，无竞态。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Login } from '../pages/Login';

// 用 vi.hoisted 保证 mock 函数在模块提升阶段可用
const mocks = vi.hoisted(() => ({
  login: vi.fn(),
}));

// 只 mock useAuth 的 login 副作用，路由与 UI 走真实实现
vi.mock('../context/AuthContext', () => ({
  useAuth: () => ({ login: mocks.login }),
}));

const renderLogin = () =>
  render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<div>HOME_PAGE</div>} />
      </Routes>
    </MemoryRouter>
  );

describe('登录页', () => {
  beforeEach(() => {
    // jsdom 未实现 window.alert，stub 后断言调用
    vi.spyOn(window, 'alert').mockImplementation(() => {});
    mocks.login.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('非法手机号（10 位）被拦截：提示错误且不出现验证码输入框', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByPlaceholderText('请输入手机号'), '1380013800');
    await user.click(screen.getByRole('button', { name: '获取验证码' }));

    expect(window.alert).toHaveBeenCalledWith('请输入正确的手机号');
    expect(screen.queryByPlaceholderText('请输入验证码')).not.toBeInTheDocument();
    expect(mocks.login).not.toHaveBeenCalled();
  });

  it('合法手机号点击获取验证码后，1 秒 mock 延迟出现验证码输入框', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByPlaceholderText('请输入手机号'), '13800138000');
    await user.click(screen.getByRole('button', { name: '获取验证码' }));

    // 延迟未到时不出现
    expect(screen.queryByPlaceholderText('请输入验证码')).not.toBeInTheDocument();
    // 延迟到达后出现（mock 延迟 1 秒，显式超时等待）
    expect(
      await screen.findByPlaceholderText('请输入验证码', {}, { timeout: 3000 })
    ).toBeInTheDocument();
    // 按钮切换为登录
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
  });

  it('错误验证码被拦截：提示错误且不触发登录', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByPlaceholderText('请输入手机号'), '13800138000');
    await user.click(screen.getByRole('button', { name: '获取验证码' }));
    await screen.findByPlaceholderText('请输入验证码', {}, { timeout: 3000 });

    await user.type(screen.getByPlaceholderText('请输入验证码'), '999999');
    await user.click(screen.getByRole('button', { name: '登录' }));

    expect(window.alert).toHaveBeenCalledWith('验证码错误 (测试码: 123456)');
    expect(mocks.login).not.toHaveBeenCalled();
  });

  it('正确验证码登录成功：login 被调用并跳转到目标页', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByPlaceholderText('请输入手机号'), '13800138000');
    await user.click(screen.getByRole('button', { name: '获取验证码' }));
    await screen.findByPlaceholderText('请输入验证码', {}, { timeout: 3000 });

    await user.type(screen.getByPlaceholderText('请输入验证码'), '123456');
    await user.click(screen.getByRole('button', { name: '登录' }));

    // mock 延迟 1 秒后完成登录并跳转首页
    expect(await screen.findByText('HOME_PAGE', {}, { timeout: 3000 })).toBeInTheDocument();
    expect(mocks.login).toHaveBeenCalledWith(
      'mock-jwt-token',
      expect.objectContaining({ nickname: '测试用户' })
    );
  });
});
