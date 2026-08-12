import { defineConfig, devices } from '@playwright/test';

/**
 * E2E 冒烟测试配置
 *
 * 前置条件（见 README.md）:
 * 1. 后端服务 + 本地网关(nginx) + PostgreSQL 就绪
 * 2. 前端 dev server 运行在 3000 端口（vite proxy 转发 /api 到网关）
 *
 * 注: 前端开发环境自动注入默认 UUID token（AuthContext.tsx），
 * 未登录也可浏览/上传；登录页为 mock 实现（验证码固定 123456）。
 */
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
