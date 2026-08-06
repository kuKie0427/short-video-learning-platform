import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { splitApi } from '../services/api';

interface SplitSegment {
  id: string;
  segment_index: number;
  start_time: number;
  end_time: number;
  duration: number;
  thumbnail_url?: string;
  video_url?: string;
  title?: string;
  scene_type?: string;
}

interface TaskInfo {
  task_id: string;
  status: string;
  progress: number;
  created_at: string;
  completed_at?: string;
}

export default function VideoSplitResult() {
  const { taskId } = useParams<{ taskId: string }>();
  const navigate = useNavigate();
  
  const [task, setTask] = useState<TaskInfo | null>(null);
  const [segments, setSegments] = useState<SplitSegment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [playingSegment, setPlayingSegment] = useState<SplitSegment | null>(null);
  const [selectedSegments, setSelectedSegments] = useState<Set<string>>(new Set());
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (taskId) {
      loadSplitResult();
    }
  }, [taskId]);

  const loadSplitResult = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // 获取任务详情和切分片段
      const response = await splitApi.getTaskResult(taskId!);
      const data = response.data.data;
      
      console.log('切分结果数据:', data);
      console.log('切分片段:', data.segments);
      
      setTask(data.task);
      setSegments(data.segments || []);
    } catch (err: any) {
      console.error('加载切分结果失败:', err);
      setError(err.response?.data?.detail || '加载切分结果失败');
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const toggleSegmentSelection = (segmentId: string) => {
    setSelectedSegments(prev => {
      const newSet = new Set(prev);
      if (newSet.has(segmentId)) {
        newSet.delete(segmentId);
      } else {
        newSet.add(segmentId);
      }
      return newSet;
    });
  };

  const toggleSelectAll = () => {
    if (selectedSegments.size === segments.length) {
      setSelectedSegments(new Set());
    } else {
      setSelectedSegments(new Set(segments.map(s => s.id)));
    }
  };

  const handlePublishToFeed = async () => {
    if (selectedSegments.size === 0) {
      alert('请至少选择一个片段');
      return;
    }

    try {
      setUploading(true);
      const segmentIds = Array.from(selectedSegments);
      
      await splitApi.publishSegments({
        segment_ids: segmentIds
      });

      alert(`成功发布 ${segmentIds.length} 个片段到主页！`);
      setSelectedSegments(new Set());
    } catch (err: any) {
      console.error('发布失败:', err);
      alert(err.response?.data?.detail || '发布失败，请重试');
    } finally {
      setUploading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">加载切分结果...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">加载失败</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => navigate('/split')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回视频列表
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 py-8">
      <div className="container mx-auto px-4 max-w-7xl">
        {/* 标题栏 */}
        <div className="mb-8">
          <button
            onClick={() => navigate('/split')}
            className="text-blue-600 hover:text-blue-700 mb-4 flex items-center gap-2"
          >
            <span>←</span>
            <span>返回视频列表</span>
          </button>
          
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-800 mb-2">
                  视频切分完成 🎉
                </h1>
                <p className="text-gray-600">
                  共切分为 <span className="font-semibold text-blue-600">{segments.length}</span> 个片段
                  {selectedSegments.size > 0 && (
                    <span className="ml-2 text-green-600">
                      (已选择 {selectedSegments.size} 个)
                    </span>
                  )}
                </p>
                {task && task.completed_at && (
                  <p className="text-sm text-gray-500 mt-2">
                    完成时间: {new Date(task.completed_at).toLocaleString('zh-CN')}
                  </p>
                )}
              </div>
              
              {segments.length > 0 && (
                <div className="flex gap-3">
                  <button
                    onClick={toggleSelectAll}
                    className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
                  >
                    {selectedSegments.size === segments.length ? '取消全选' : '全选'}
                  </button>
                  <button
                    onClick={handlePublishToFeed}
                    disabled={selectedSegments.size === 0 || uploading}
                    className={`px-6 py-2 rounded-lg transition ${
                      selectedSegments.size === 0 || uploading
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    {uploading ? (
                      <span className="flex items-center gap-2">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        发布中...
                      </span>
                    ) : (
                      `发布到主页 (${selectedSegments.size})`
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 切分片段网格 */}
        {segments.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-12 text-center">
            <div className="text-gray-400 text-5xl mb-4">📹</div>
            <p className="text-gray-600">暂无切分片段</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {segments.map((segment, index) => (
              <div
                key={segment.id}
                className={`bg-white rounded-lg shadow-md overflow-hidden hover:shadow-xl transition-all duration-300 relative ${
                  selectedSegments.has(segment.id) ? 'ring-4 ring-green-500' : ''
                }`}
              >
                {/* 选择框 */}
                <div className="absolute top-3 left-3 z-10">
                  <input
                    type="checkbox"
                    checked={selectedSegments.has(segment.id)}
                    onChange={() => toggleSegmentSelection(segment.id)}
                    className="w-5 h-5 rounded border-2 border-white shadow-lg cursor-pointer accent-green-600"
                  />
                </div>
                {/* 缩略图 */}
                <div className="aspect-video bg-gradient-to-br from-blue-100 to-purple-100 relative">
                  {segment.thumbnail_url ? (
                    <img
                      src={segment.thumbnail_url}
                      alt={segment.scene_type || `片段 ${index + 1}`}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <span className="text-6xl font-bold text-white opacity-50">
                        {segment.segment_index + 1}
                      </span>
                    </div>
                  )}
                  <div className="absolute bottom-2 right-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded">
                    {formatTime(segment.duration)}
                  </div>
                </div>

                {/* 片段信息 */}
                <div className="p-4">
                  <h3 className="font-semibold text-lg mb-2 text-gray-800">
                    {segment.scene_type || `片段 ${segment.segment_index + 1}`}
                  </h3>
                  <div className="text-xs text-gray-500 space-y-1 mb-4">
                    <div className="flex justify-between">
                      <span>开始:</span>
                      <span className="font-mono">{formatTime(segment.start_time)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>结束:</span>
                      <span className="font-mono">{formatTime(segment.end_time)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>时长:</span>
                      <span className="font-mono">{formatTime(segment.duration)}</span>
                    </div>
                  </div>
                  
                  {/* 操作按钮 */}
                  <div className="flex gap-2">
                    <button 
                      className="flex-1 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
                      onClick={() => setPlayingSegment(segment)}
                    >
                      播放
                    </button>
                    <button 
                      className="flex-1 px-3 py-2 bg-gray-100 text-gray-700 text-sm rounded-lg hover:bg-gray-200 transition"
                      onClick={() => {
                        if (segment.video_url) {
                          const link = document.createElement('a');
                          link.href = segment.video_url;
                          link.download = `${segment.scene_type || '片段' + (segment.segment_index + 1)}.mp4`;
                          link.click();
                        } else {
                          alert('视频文件不存在');
                        }
                      }}
                    >
                      下载
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 视频播放模态框 */}
      {playingSegment && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"
          onClick={() => setPlayingSegment(null)}
        >
          <div 
            className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 模态框头部 */}
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold text-gray-800">
                {playingSegment.scene_type || `片段 ${playingSegment.segment_index + 1}`}
              </h3>
              <button
                onClick={() => setPlayingSegment(null)}
                className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
              >
                ×
              </button>
            </div>

            {/* 视频播放器 */}
            <div className="bg-black">
              {playingSegment.video_url ? (
                <video
                  controls
                  autoPlay
                  className="w-full max-h-[70vh]"
                  src={playingSegment.video_url}
                  onError={(e) => {
                    console.error('视频加载失败:', playingSegment.video_url);
                    console.error('Error details:', e);
                  }}
                  onLoadStart={() => {
                    console.log('开始加载视频:', playingSegment.video_url);
                  }}
                  onCanPlay={() => {
                    console.log('视频可以播放');
                  }}
                >
                  您的浏览器不支持视频播放
                </video>
              ) : (
                <div className="aspect-video flex items-center justify-center text-white">
                  <div className="text-center">
                    <div className="text-4xl mb-2">⚠️</div>
                    <p>视频文件不存在</p>
                  </div>
                </div>
              )}
            </div>

            {/* 模态框底部信息 */}
            <div className="p-4 bg-gray-50">
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-gray-600">开始时间: </span>
                  <span className="font-mono font-semibold">{formatTime(playingSegment.start_time)}</span>
                </div>
                <div>
                  <span className="text-gray-600">结束时间: </span>
                  <span className="font-mono font-semibold">{formatTime(playingSegment.end_time)}</span>
                </div>
                <div>
                  <span className="text-gray-600">时长: </span>
                  <span className="font-mono font-semibold">{formatTime(playingSegment.duration)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
