import { test, expect } from '@playwright/test';
import path from 'path';

/**
 * 切分全流程冒烟（真实后端链路）
 *
 * 链路: UI 上传 → 直连 direct-split API（ffmpeg 按时间戳切分）→ UI 结果页 → UI 列表状态。
 *
 * 为什么绕开 analyze（AI 知识点分析）:
 * analyze 依赖重型 AI 依赖（torch/opencv/funasr + SenseVoice 模型权重），
 * E2E 环境不安装——缺失时明确报错是设计意图（backend/tests/unit/test_pipeline_flow.py 覆盖），
 * GLM 降级路径由后端单元测试覆盖（test_glm_fallback.py）。
 * direct-split 仅依赖 ffmpeg 与视频文件路径，可在 E2E 环境完整验证。
 *
 * 覆盖的缺陷回归:
 * - direct-split 视频路径硬编码 /app/data（Docker），本地/CI 部署必失败
 *   → 兼容 UPLOAD_BASE_DIR（services/split/app/api/split.py）
 * - 列表"查看结果"按钮指向不存在的路由 /split/result/
 *   → 修正为 /video-split-result/（frontend/src/pages/VideoSplit.tsx）
 */
const DEV_TOKEN = '00000000-0000-0000-0000-000000000001';

test('切分全流程: 上传 → 直接切分 → 结果页渲染 → 列表状态 → 查看结果', async ({ page }) => {
  test.setTimeout(180_000);

  // ── 1. 真实上传视频（走 upload 服务完整链路）──
  await page.goto('/upload');
  const videoFile = path.resolve(__dirname, '../../short_video/3分钟学习微积分.mp4');
  await page.locator('input[type="file"]').setInputFiles(videoFile);
  await page.waitForURL(/\/split/, { timeout: 120_000 });

  // ── 2. 从 /split 列表响应中取刚上传视频的 long_video_id ──
  const listResp = await page.waitForResponse(
    (resp) => resp.url().includes('/api/feed/my_videos') && resp.status() === 200,
    { timeout: 30_000 }
  );
  const body = await listResp.json();
  const videos = body.data?.videos || [];
  const uploaded = videos.find((v: { title: string }) => v.title.startsWith('视频_UP_')) || videos[0];
  expect(uploaded, '切分列表应有长视频').toBeTruthy();
  expect(uploaded.long_video_id, '长视频应有关联的 long_video_id').toBeTruthy();

  // ── 3. 直连 direct-split（ffmpeg 同步切分，2 段 60s）──
  const splitResp = await page.request.post('/api/split/direct-split', {
    headers: { Authorization: `Bearer ${DEV_TOKEN}` },
    data: {
      long_video_id: uploaded.long_video_id,
      organization_mode: 'standalone',
      knowledge_points: [
        { id: 1, title: '微积分导论', start_time: 0, end_time: 60, duration: 60 },
        { id: 2, title: '函数与极限', start_time: 60, end_time: 120, duration: 60 },
      ],
    },
  });
  expect(splitResp.status()).toBe(200);
  const splitData = (await splitResp.json()).data;
  expect(splitData.status, 'direct-split 应同步完成').toBe('completed');
  expect(splitData.task_id).toBeTruthy();
  const taskId = splitData.task_id;

  // ── 4. 结果页渲染（task 详情 + 片段列表）──
  await page.goto(`/video-split-result/${taskId}`);
  await expect(page.getByRole('heading', { name: '视频切分完成 🎉' })).toBeVisible({ timeout: 30_000 });
  // 2 个片段渲染出来（片段卡片缩略图/序号）
  await expect(page.getByText(/共切分为 2 个片段/)).toBeVisible();
  const segmentCards = await page.locator('div.relative input[type="checkbox"]').count();
  expect(segmentCards, '结果页应有 2 个片段卡片').toBe(2);

  // ── 5. 列表页任务状态 → 查看结果按钮 → 结果页（覆盖死路由回归）──
  await page.goto('/split');
  await expect(page.getByText('切分完成').first()).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: '查看结果' }).first().click();
  await page.waitForURL(/\/video-split-result\//, { timeout: 15_000 });
  await expect(page.getByRole('heading', { name: '视频切分完成 🎉' })).toBeVisible();
});
