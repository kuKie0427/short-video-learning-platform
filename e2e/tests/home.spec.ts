import { test, expect } from '@playwright/test';

/**
 * 首页推荐流冒烟
 *
 * 开发环境前端自动注入默认 UUID token（AuthContext.tsx），
 * 请求经 vite proxy → nginx 网关 → content 服务（/api/feed/recommend）。
 * 需要后端 content 服务与 mock 视频数据就绪（scripts/insert_mock_videos.py）。
 */
test('首页加载: 推荐流视频卡片出现', async ({ page }) => {
  await page.goto('/');

  // 顶部导航"推荐"tab
  await expect(page.getByText('推荐', { exact: true })).toBeVisible();

  // 等待视频流数据加载（推荐接口返回 mock 视频）
  // Home 是抖音式全屏视频流，视频元素或标题出现即视为加载成功
  await page.waitForSelector('video, .snap-start', { timeout: 15_000 });

  // 断言至少一个视频进入 DOM（mock 视频: 3分钟学习微积分 / 雅思3分钟学习）
  const videoCount = await page.locator('.snap-start').count();
  expect(videoCount).toBeGreaterThan(0);
});
