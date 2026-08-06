import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { contentApi, splitApi } from '../services/api';

interface Video {
  video_id: string;
  long_video_id?: string;
  title: string;
  duration: number;
  created_at: string;
  thumbnail_url?: string;
}

interface SplitTask {
  task_id: string;
  video_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  progress_message?: string;
  message?: string;
}

interface SplitSegment {
  id: number;
  title: string;
  startTime: number;
  endTime: number;
  selected: boolean;
}

export const VideoSplit: React.FC = () => {
  const navigate = useNavigate();
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [splitTasks, setSplitTasks] = useState<Record<string, SplitTask>>({});
  const [error, setError] = useState<string | null>(null);
  const [selectedVideo, setSelectedVideo] = useState<Video | null>(null);
  const [segments, setSegments] = useState<SplitSegment[]>([]);
  const [splitting, setSplitting] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState<string | null>(null);
  
  // 新增：切分进度相关状态
  const [splitTaskId, setSplitTaskId] = useState<string | null>(null);
  const [splitProgress, setSplitProgress] = useState<number>(0);
  const [splitStatus, setSplitStatus] = useState<string>('idle');
  const [progressMessage, setProgressMessage] = useState<string>('');

  // 加载视频列表
  useEffect(() => {
    loadVideos();
  }, []);

  // 轮询任务状态
  useEffect(() => {
    const activeTasks = Object.values(splitTasks).filter(
      task => task.status === 'pending' || task.status === 'processing'
    );

    if (activeTasks.length === 0) return;

    const interval = setInterval(() => {
      activeTasks.forEach(task => {
        checkTaskStatus(task.task_id, task.video_id);
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [splitTasks]);

  const loadVideos = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await contentApi.getMyVideos({ page: 1, page_size: 20 });
      const videos = response.data?.data?.videos || [];
      // 只显示长视频，过滤掉切分后的片段
      const longVideos = videos.filter((v: any) => v.long_video_id);
      const mappedVideos = longVideos.map((v: any) => ({
        video_id: v.id,
        long_video_id: v.long_video_id,
        title: v.title,
        duration: v.duration,
        created_at: v.created_at,
        thumbnail_url: v.cover_url
      }));
      setVideos(mappedVideos);
    } catch (err: any) {
      console.error('加载视频列表失败:', err);
      setError(err.response?.data?.detail || '加载视频列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectVideo = async (video: Video) => {
    setSelectedVideo(video);
    setAnalyzing(true);
    setError(null);
    setAnalysisMessage(null);
    
    try {
      if (!video.long_video_id) {
        setError('此视频不是长视频，无法切分');
        return;
      }
      
      // 调用分析API（GLM分析，耗时30-60秒）
      const response = await splitApi.analyze(video.long_video_id);
      const data = response.data?.data;
      
      if (data) {
        const knowledgePoints = data.knowledge_points || [];
        const usedFallback = data.used_fallback || false;
        const message = data.message;
        
        // 设置提示信息
        if (message) {
          setAnalysisMessage(message);
        }
        
        // 转换为组件需要的格式
        const suggestedSegments: SplitSegment[] = knowledgePoints.map((kp: any) => ({
          id: kp.id,
          title: kp.title,
          startTime: kp.start_time,
          endTime: kp.end_time,
          selected: true // 默认全选
        }));
        
        setSegments(suggestedSegments);
        
        if (suggestedSegments.length === 0) {
          setError('未能生成切分点，请稍后再试');
        }
      } else {
        setError('分析失败，请稍后再试');
      }
    } catch (err: any) {
      console.error('视频分析失败:', err);
      const errorMsg = err.response?.data?.detail || err.response?.data?.message || '分析失败，请稍后再试';
      setError(errorMsg);
      // 分析失败时返回列表
      setSelectedVideo(null);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleBack = () => {
    setSelectedVideo(null);
    setSegments([]);
  };

  const toggleSegment = (id: number) => {
    setSegments(segments.map(seg => 
      seg.id === id ? { ...seg, selected: !seg.selected } : seg
    ));
  };

  const handleConfirmSplit = async () => {
    if (!selectedVideo) return;

    const selectedSegments = segments.filter(seg => seg.selected);
    if (selectedSegments.length === 0) {
      alert('请至少选择一个切分片段');
      return;
    }

    try {
      setSplitting(true);
      setError(null);
      
      if (!selectedVideo.long_video_id) {
        setError('此视频不是长视频，无法切分');
        return;
      }
      
      // 直接基于选中的知识点进行切分（不重复分析）
      const knowledgePoints = selectedSegments.map(seg => ({
        id: seg.id,
        title: seg.title,
        start_time: seg.startTime,
        end_time: seg.endTime,
        duration: seg.endTime - seg.startTime
      }));
      
      const response = await splitApi.directSplit({
        long_video_id: selectedVideo.long_video_id,
        knowledge_points: knowledgePoints,
        organization_mode: 'standalone'
      });

      const taskData = response.data.data;
      const taskId = taskData.task_id;

      // 直接切分是同步的，完成后立即跳转到结果页
      if (taskData.status === 'completed') {
        setTimeout(() => {
          navigate(`/video-split-result/${taskId}`);
        }, 500);
      } else {
        // 如果任务还在处理中，开始轮询
        setSplitTaskId(taskId);
        setSplitProgress(taskData.progress || 0);
        setSplitStatus('processing');
        setProgressMessage(taskData.progress_message || '正在切分视频...');
        startProgressPolling(taskId);
      }
      
    } catch (err: any) {
      console.error('创建切分任务失败:', err);
      setError(err.response?.data?.detail || err.response?.data?.message || '创建切分任务失败');
      setSplitting(false);
    }
  };

  // 轮询任务进度
  const startProgressPolling = (taskId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await splitApi.getTaskStatus(taskId);
        const taskData = response.data.data;
        
        setSplitProgress(taskData.progress || 0);
        setProgressMessage(taskData.progress_message || '处理中...');
        
        if (taskData.status === 'completed') {
          clearInterval(pollInterval);
          setSplitStatus('completed');
          // 跳转到结果页
          setTimeout(() => {
            navigate(`/video-split-result/${taskId}`);
          }, 500);
        } else if (taskData.status === 'failed') {
          clearInterval(pollInterval);
          setSplitStatus('failed');
          setError(taskData.error_message || '切分失败');
          setSplitting(false);
        }
      } catch (err) {
        console.error('获取任务状态失败:', err);
      }
    }, 2000); // 每2秒轮询一次
  };

  const checkTaskStatus = async (taskId: string, videoId: string) => {
    try {
      const response = await splitApi.getTaskStatus(taskId);
      const taskData = response.data.data;

      setSplitTasks(prev => ({
        ...prev,
        [videoId]: {
          ...prev[videoId],
          status: taskData.status,
          progress: taskData.progress,
          progress_message: taskData.progress_message,
          message: taskData.error_message
        }
      }));

      if (taskData.status === 'completed') {
        console.log('切分完成:', taskId);
      }
    } catch (err: any) {
      console.error('获取任务状态失败:', err);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
        <div className="text-white text-lg">加载中...</div>
      </div>
    );
  }

  // 如果正在分析，显示分析加载页
  if (analyzing) {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
        <div className="text-center">
          <div className="mb-6">
            <svg className="animate-spin h-16 w-16 text-indigo-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">正在智能分析视频...</h2>
          <p className="text-sm text-gray-600 mb-4">使用GLM大模型分析视频内容，预计需要5分钟</p>
          <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></div>
            <span>语音识别</span>
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse animation-delay-200"></div>
            <span>知识点提取</span>
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse animation-delay-400"></div>
            <span>生成建议</span>
          </div>
          <button
            onClick={() => {
              setAnalyzing(false);
              setSelectedVideo(null);
            }}
            className="mt-6 px-6 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
          >
            取消
          </button>
        </div>
      </div>
    );
  }

  // 如果选中了视频，显示切分配置页面
  if (selectedVideo) {
    return (
      <div className="min-h-screen bg-gray-50 pb-24">
        {/* 头部 */}
        <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-4 py-4 sticky top-0 z-10 shadow-md">
          <div className="relative">
            {/* 左上角返回按钮 */}
            <button
              onClick={handleBack}
              className="absolute left-0 top-0 w-9 h-9 flex items-center justify-center rounded-full
                         hover:bg-white/20 active:bg-white/30 transition-all duration-200"
              aria-label="返回"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            
            {/* 标题居中 */}
            <div className="text-center">
              <h1 className="text-lg font-semibold mb-1">视频切分</h1>
              <p className="text-sm opacity-90">智能分割视频片段</p>
            </div>
          </div>
        </div>

        {/* 视频预览区 */}
        <div className="relative bg-gradient-to-br from-gray-700 to-gray-800 h-48 flex items-center justify-center">
          {selectedVideo.thumbnail_url ? (
            <img src={selectedVideo.thumbnail_url} alt={selectedVideo.title} className="w-full h-full object-cover opacity-70" />
          ) : (
            <div className="text-white text-6xl opacity-60">▶</div>
          )}
          <div className="absolute inset-0 bg-black bg-opacity-20"></div>
        </div>

        {/* 视频信息 */}
        <div className="bg-white px-4 py-3 shadow-sm">
          <div className="flex justify-between items-center mb-2.5 text-sm">
            <span className="text-gray-600 font-medium">视频时长</span>
            <span className="text-gray-900 font-semibold">{formatTime(selectedVideo.duration)}</span>
          </div>
          <div className="flex justify-between items-center mb-2.5 text-sm">
            <span className="text-gray-600 font-medium">视频标题</span>
            <span className="text-gray-900 font-semibold truncate ml-2 max-w-xs">{selectedVideo.title}</span>
          </div>
          <div className="flex justify-between items-center text-sm">
            <span className="text-gray-600 font-medium">上传时间</span>
            <span className="text-gray-900 font-semibold">{formatDate(selectedVideo.created_at)}</span>
          </div>
        </div>

        {/* 分隔条 */}
        <div className="h-2 bg-gray-100"></div>

        {/* 切分列表 */}
        <div className="px-4 py-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-semibold text-gray-800">
            <span className="text-lg">📹</span>
            <span>建议切分点</span>
          </div>

          <div className="space-y-2.5">
            {segments.map((segment) => (
              <div
                key={segment.id}
                onClick={() => toggleSegment(segment.id)}
                className={`
                  bg-white rounded-xl p-3 flex items-center gap-3 cursor-pointer
                  border-2 transition-all duration-300 shadow-sm
                  ${segment.selected 
                    ? 'border-indigo-500 bg-gradient-to-r from-indigo-50 to-purple-50 shadow-md transform -translate-y-0.5' 
                    : 'border-gray-200 hover:border-indigo-300 hover:shadow-md hover:-translate-y-0.5'
                  }
                `}
              >
                <div className={`
                  w-10 h-10 rounded-lg flex items-center justify-center text-white text-lg font-bold
                  bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md
                  ${segment.selected ? 'scale-105' : ''}
                  transition-transform duration-300
                `}>
                  {segment.id}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-semibold text-gray-800 mb-1">
                    {segment.title}
                  </div>
                  <div className="text-xs text-gray-500">
                    {formatTime(segment.startTime)} - {formatTime(segment.endTime)}
                  </div>
                </div>
                <div className="flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={segment.selected}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleSegment(segment.id);
                    }}
                    className="w-5 h-5 rounded accent-indigo-500 cursor-pointer"
                  />
                </div>
              </div>
            ))}
          </div>

          {/* 提示信息 */}
          <div className="mt-4 p-3 bg-blue-50 border-l-4 border-blue-500 rounded-r-lg">
            <div className="flex items-start gap-2">
              <span className="text-blue-600 text-sm">💡</span>
              <p className="text-xs text-blue-700 leading-relaxed">
                点击片段卡片可以选择或取消选择，确认后将对选中的片段进行切分处理
              </p>
            </div>
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="px-4 pb-4">
            <div className="bg-red-50 border border-red-200 rounded-lg p-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        )}
        
        {/* 分析信息提示 */}
        {analysisMessage && (
          <div className="px-4 pb-4">
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
              <p className="text-sm text-yellow-700">{analysisMessage}</p>
            </div>
          </div>
        )}

        {/* 底部按钮 */}
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-4 flex gap-2 shadow-lg z-50">
          <button
            onClick={handleBack}
            disabled={splitting}
            className="flex-1 py-3 px-4 rounded-lg bg-gray-100 text-gray-700 font-semibold text-sm
                       hover:bg-gray-200 active:scale-98 transition-all duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <span>✕</span>
            <span>取消</span>
          </button>
          <button
            onClick={handleConfirmSplit}
            disabled={splitting}
            className="flex-1 py-3 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 
                       text-white font-semibold text-sm shadow-lg
                       hover:shadow-xl active:scale-98 transition-all duration-200
                       disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {splitting ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>处理中...</span>
              </>
            ) : (
              <>
                <span>✓</span>
                <span>确认切分</span>
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  // 视频列表页面
  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* 页面头部 */}
      <div className="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-4 py-4 sticky top-0 z-10 shadow-md">
        <div className="relative">
          {/* 左上角返回按钮 */}
          <button
            onClick={() => navigate(-1)}
            className="absolute left-0 top-0 w-9 h-9 flex items-center justify-center rounded-full
                       hover:bg-white/20 active:bg-white/30 transition-all duration-200"
            aria-label="返回"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          
          {/* 标题居中 */}
          <div className="text-center">
            <h1 className="text-lg font-semibold mb-1">视频切分</h1>
            <p className="text-sm opacity-90">选择视频进行智能切分</p>
          </div>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="px-4 mt-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* 视频列表 */}
      <div className="px-4 py-4">
        {videos.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4 opacity-40">📹</div>
            <p className="text-gray-500 mb-4">暂无视频</p>
            <button
              onClick={() => navigate('/upload')}
              className="px-6 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg 
                         hover:shadow-lg transition font-semibold"
            >
              上传视频
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {videos.map((video) => {
              const task = splitTasks[video.video_id];
              const isProcessing = task?.status === 'pending' || task?.status === 'processing';
              const isCompleted = task?.status === 'completed';

              return (
                <div
                  key={video.video_id}
                  className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden"
                >
                  <div className="flex items-center gap-3 p-3">
                    {/* 缩略图 */}
                    <div className="flex-shrink-0 w-24 h-16 bg-gray-200 rounded-lg overflow-hidden">
                      {video.thumbnail_url ? (
                        <img
                          src={video.thumbnail_url}
                          alt={video.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-2xl">
                          ▶
                        </div>
                      )}
                    </div>

                    {/* 视频信息 */}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-sm text-gray-900 truncate mb-1">
                        {video.title}
                      </h3>
                      <div className="flex items-center gap-2 text-xs text-gray-500">
                        <span>⏱ {formatTime(video.duration)}</span>
                        <span>•</span>
                        <span>{formatDate(video.created_at)}</span>
                      </div>

                      {/* 任务状态 */}
                      {task && (
                        <div className="mt-2">
                          {isProcessing && (
                            <div className="space-y-1">
                              <div className="flex items-center gap-2 text-xs">
                                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
                                <span className="text-blue-600 font-medium">
                                  处理中 {task.progress ? `${Math.round(task.progress)}%` : ''}
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-1">
                                <div
                                  className="bg-blue-500 h-1 rounded-full transition-all duration-300"
                                  style={{ width: `${task.progress || 0}%` }}
                                />
                              </div>
                            </div>
                          )}
                          {isCompleted && (
                            <div className="flex items-center gap-2 text-xs text-green-600">
                              <span>✓</span>
                              <span className="font-medium">切分完成</span>
                            </div>
                          )}
                          {task.status === 'failed' && (
                            <div className="flex items-center gap-2 text-xs text-red-600">
                              <span>✕</span>
                              <span className="font-medium">切分失败</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex-shrink-0">
                      {isCompleted ? (
                        <button
                          onClick={() => navigate(`/split/result/${task.task_id}`)}
                          className="px-3 py-1.5 bg-green-500 text-white rounded-lg text-xs font-semibold
                                     hover:bg-green-600 transition"
                        >
                          查看结果
                        </button>
                      ) : isProcessing ? (
                        <button
                          disabled
                          className="px-3 py-1.5 bg-gray-200 text-gray-400 rounded-lg text-xs font-semibold
                                     cursor-not-allowed"
                        >
                          处理中
                        </button>
                      ) : (
                        <button
                          onClick={() => handleSelectVideo(video)}
                          className="px-3 py-1.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white 
                                     rounded-lg text-xs font-semibold hover:shadow-lg transition"
                        >
                          开始切分
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 底部按钮 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-4 shadow-lg z-50">
        <button
          onClick={() => navigate('/')}
          className="w-full py-3 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 
                     text-white font-semibold text-sm shadow-lg
                     hover:shadow-xl active:scale-98 transition-all duration-200
                     flex items-center justify-center gap-2"
        >
          <span>←</span>
          <span>返回主页</span>
        </button>
      </div>

      {/* 切分进度模态框 */}
      {splitStatus === 'processing' && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">正在切分视频</h3>
            <div className="mb-4">
              <div className="flex justify-between text-sm mb-2">
                <span>切分进度</span>
                <span>{Math.round(splitProgress)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${splitProgress}%` }}
                />
              </div>
            </div>
            <p className="text-sm text-gray-600 mb-2">
              {progressMessage}
            </p>
            <p className="text-xs text-blue-600">
              ✓ 使用第一次分析结果，无需重新分析
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
