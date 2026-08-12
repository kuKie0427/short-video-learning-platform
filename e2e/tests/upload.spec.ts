import { test, expect } from '@playwright/test';
import path from 'path';

/**
 * 上传冒烟（真实后端链路）
 *
 * 上传走真实 API: init → chunk(PUT, 二进制分片, 5MB/片) → complete。
 * 测试素材: 项目 short_video/3分钟学习微积分.mp4（7.7MB，2 个分片）。
 * 需要 upload 服务 + 网关就绪；开发环境自动注入 UUID token。
 */
test('上传: 选择视频文件 → 上传流程启动 → 完成跳转', async ({ page }) => {
  test.setTimeout(120_000);

  await page.goto('/upload');

  // 选择真实视频文件（e2e/tests → 项目根 → short_video/）
  const videoFile = path.resolve(
    __dirname, '../../short_video/3分钟学习微积分.mp4'
  );
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(videoFile);

  // 上传完成后 VideoUploader 自动跳转到切分页 /split（本地环境上传极快，不等待中间状态）
  await page.waitForURL(/\/split/, { timeout: 120_000 });

  // 切分页出现刚上传的视频（标题以 "视频_" 开头）
  await page.getByRole('heading', { name: /视频_UP_/ }).first().waitFor({
    timeout: 15_000,
  });
});
