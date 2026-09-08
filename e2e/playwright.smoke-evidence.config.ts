import { defineConfig, devices } from '@playwright/test';

/**
 * 发布冒烟留痕配置（测试负责人用）
 *
 * 用途：跑发布前人工冒烟（《手工测试用例-正式版》S 系列）时，同步抓取每一步的
 * 页面截图作为「实际结果」列的证据，落盘到 backend/docs/manual-evidence/。
 *
 * 与主配置 e2e/playwright.config.ts 的差别只有两处：
 *   1. screenshot: 'on'（主配置是 only-on-failure，冒烟留痕要全过程截图）
 *   2. outputDir 指向 manual-evidence（避免被 test-results 的 gitignore 吃掉）
 *
 * 用法（前置：后端全栈 + 网关 + 前端 dev server 已启动，见 e2e/README.md）：
 *   cd e2e && npm run evidence            # 全 6 条冒烟链路 + 截图
 *   npx playwright test -c playwright.smoke-evidence.config.ts tests/home.spec.ts
 *
 * 截图文件名为 `<用例目录>/test-<序号>-chromium.png`，按用例编号（S01/S04/S09/S10/S11/S15）
 * 手工重命名为 `S04-1.png` 这种《手工测试用例-正式版》约定的形式后归档。
 */
export default defineConfig({
  testDir: './tests',
  outputDir: '../backend/docs/manual-evidence/raw',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    // 留痕：每步截图 + 完整 trace，事后可 `npx playwright show-trace` 复核断言现场
    screenshot: 'on',
    trace: 'on',
    video: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
