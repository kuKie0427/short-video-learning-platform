import { test, expect } from '@playwright/test';

/**
 * 登录流程冒烟（前端 mock 实现）
 *
 * 注意: 当前前端登录页为 mock（src/pages/Login.tsx），
 * 验证码固定 123456、token 为 mock-jwt-token、未调后端 API。
 * 真实登录 API 链路由后端集成测试覆盖（tests/api/test_auth.py）。
 * 本用例验证 UI 流程可用性，并记录前端对接现状。
 */
test('登录流程: 手机号 + 验证码 → 跳转首页', async ({ page }) => {
  await page.goto('/login');

  // 输入 11 位手机号
  await page.getByPlaceholder('请输入手机号').fill('13800138000');
  await page.getByRole('button', { name: '获取验证码' }).click();

  // 等待验证码输入框出现（mock 1 秒延迟后显示）
  await page.getByPlaceholder('请输入验证码').waitFor({ timeout: 10_000 });

  // 输入测试验证码并登录
  await page.getByPlaceholder('请输入验证码').fill('123456');
  await page.getByRole('button', { name: '登录' }).click();

  // 登录成功跳转首页（mock 1 秒延迟）
  await page.waitForURL((url) => url.pathname === '/', { timeout: 10_000 });
});

test('登录页校验: 非法手机号被拦截', async ({ page }) => {
  await page.goto('/login');

  // 10 位手机号 → 点获取验证码应弹提示且不进入验证码阶段
  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('手机号');
    await dialog.dismiss();
  });
  await page.getByPlaceholder('请输入手机号').fill('1380013800');
  await page.getByRole('button', { name: '获取验证码' }).click();

  // 验证码输入框不应出现
  await page.getByPlaceholder('请输入验证码').waitFor({ state: 'detached', timeout: 3_000 });
});
