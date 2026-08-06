# 移动端前端项目 (Frontend)

这是一个基于 React + TypeScript + Vite + Tailwind CSS 构建的移动端 Web 应用 (H5)。

## 🚀 快速开始

1. **安装依赖**
   ```bash
   npm install
   ```

2. **启动开发服务器**
   ```bash
   npm run dev
   ```
   
3. **访问**
   打开浏览器访问 `http://localhost:3000`。
   为了在手机上测试，请确保手机和电脑在同一局域网，并访问 `http://<电脑IP>:3000`。

## 📱 功能模块

- **首页 (Home)**: 沉浸式短视频播放流 (仿 TikTok/抖音)。
- **课程 (Courses)**: 课程发现与列表。
- **创作 (Upload)**: 视频上传与**智能拆分**任务发起。
- **消息 (Inbox)**: 系统通知与互动消息。
- **我的 (Profile)**: 个人中心与作品管理。

## 🛠 技术栈

- **React 18**: UI 库
- **Vite**: 构建工具
- **Tailwind CSS**: 样式框架
- **React Router 6**: 路由管理
- **Lucide React**: 图标库
- **Axios**: HTTP 请求

## 🔌 后端对接

在 `vite.config.ts` 中配置了 API 代理：
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000', // 修改为你的后端网关地址
    changeOrigin: true,
  },
}
```
请确保后端服务已启动。
