import { test, expect } from '@playwright/test';

/**
 * 搜索冒烟
 *
 * Search 页调用真实 searchApi.searchVideos（后端 search 服务），
 * 失败时降级为前端 MOCK_VIDEOS 过滤（前端 fallback 设计）。
 * mock 视频数据含"微积分"、"雅思"关键词（scripts/insert_mock_videos.py）。
 */
test('搜索: 输入关键词出现结果', async ({ page }) => {
  await page.goto('/search');

  // 搜索输入框
  const input = page.getByPlaceholder('搜索课程、知识点...');
  await input.waitFor({ timeout: 10_000 });
  await input.fill('微积分');

  // 触发搜索（提交或防抖后自动搜索）
  await input.press('Enter');

  // 断言结果出现（视频卡片/列表项）
  await page.waitForSelector('img, video, [class*="card"], [class*="result"]', {
    timeout: 15_000,
  });
});
