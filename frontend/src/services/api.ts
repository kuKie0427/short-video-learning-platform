import axios from 'axios';

// Create an Axios instance with default config
const api = axios.create({
  baseURL: '/api', // Proxy will handle this in development
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    let token = localStorage.getItem('token');
    
    // 开发环境：如果没有token，使用默认UUID
    if (!token && import.meta.env.DEV) {
      token = '00000000-0000-0000-0000-000000000001';
      localStorage.setItem('token', token);
    }
    
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle common errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 只在生产环境且未登录时重定向到登录页
    if (error.response && error.response.status === 401 && !import.meta.env.DEV) {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  sendCode: (phone: string, scene: 'register' | 'login') => 
    api.post('/auth/send_code', { phone, scene }),
  
  loginByPhone: (phone: string, code: string) => 
    api.post('/auth/login_by_phone', { phone, code }),
    
  getMe: () => api.get('/user/me'),
};

export const videoApi = {
  getRecommendFeed: (page = 1) => api.get('/feed/recommend', { params: { page, strategy: 'popularity' } }),
  getVideoDetail: (id: string) => api.get(`/feed/video/${id}`),
};

export const uploadApi = {
  initUpload: (data: { file_name: string; file_size: number; duration: number; mime_type: string; video_type: string }) => 
    api.post('/upload/init', data),
  
  uploadChunk: (url: string, uploadId: string, chunkIndex: number, chunk: Blob) => {
    return api.put(url, chunk, {
      headers: {
        'Content-Type': 'application/octet-stream',
        'upload_id': uploadId,
        'chunk_index': chunkIndex
      }
    });
  },

  completeUpload: (data: { upload_id: string }) => 
    api.post('/upload/complete', data),
};

export const splitApi = {
  // 仅分析视频（GLM智能分析，耗时可能较长）
  analyze: (long_video_id: string) => 
    api.post('/split/analyze', { long_video_id }, { timeout: 600000 }), // 10分钟超时
  // 直接切分视频（基于已有分析结果，不重复分析）
  directSplit: (data: any) => api.post('/split/direct-split', data, { timeout: 300000 }), // 5分钟超时
  createTask: (data: any) => api.post('/split/tasks', data, { timeout: 60000 }), // 60秒超时
  getTaskStatus: (taskId: string) => api.get(`/split/tasks/${taskId}`),
  // 获取完整切分结果
  getTaskResult: (taskId: string) => api.get(`/split/tasks/${taskId}/result`),
  // 发布选中的片段到主页
  publishSegments: (data: { segment_ids: string[] }) => api.post('/split/publish-segments', data),
  // User profile APIs
  updateProfile: (data: any) => api.put('/auth/profile', data),
  uploadImage: (base64: string) => api.post('/upload/image', { image: base64 }),
};

export const contentApi = {
  getVideos: (params: { page: number; page_size: number }) => 
    api.get('/feed/recommend', { params }),
  getMyVideos: (params: { page: number; page_size: number; days?: number }) => 
    api.get('/feed/my_videos', { params }),
};

export const learnApi = {
  sendHeartbeat: (data: { video_id: string; position: number; buffered: number; playing: boolean }) =>
    api.post('/learn/heartbeat', data),
    
  completeLearn: (data: { video_id: string; status: 'learned' | 'review_needed'; title?: string; cover?: string }) =>
    api.post('/learn/complete', data),

  getRecords: () => api.get('/learn/records'),
};

export const searchApi = {
  getSuggestions: (prefix: string) => 
    api.get('/search/suggest', { params: { q: prefix } }),
    
  searchVideos: (params: {
    q: string;
    duration_range?: '0-60' | '60-180';
    sort_by?: 'relevance' | 'latest' | 'hot';
    tags?: string;
    page?: number;
  }) => api.get('/search/videos', { params }),
};

export default api;
