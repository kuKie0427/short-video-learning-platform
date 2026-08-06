import React, { useRef, useState, useEffect } from 'react';
import { Play, Pause, CheckCircle, HelpCircle, X, Loader2 } from 'lucide-react';
import { videoApi, learnApi } from '../services/api';

// --- Types ---
interface VideoDetail {
  id: string;
  title: string;
  play_url: string;
  cover_url?: string;
  last_position: number; // Seconds
}

interface HeartbeatPayload {
  video_id: string;
  position: number;
  duration: number;
}

interface VideoLearningPlayerProps {
  videoId: string;
  onComplete?: (status: 'learned' | 'review_needed') => void;
  autoResume?: boolean; // 是否自动跳转到上次播放位置，默认true
}

export const VideoLearningPlayer: React.FC<VideoLearningPlayerProps> = ({ 
  videoId, 
  onComplete,
  autoResume = true // 默认自动恢复
}) => {
  // --- Refs ---
  const videoRef = useRef<HTMLVideoElement>(null);
  const positionRef = useRef(0); // Store current position for cleanup closure
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasCompletedRef = useRef(false); // Ref to avoid state closure issues

  // --- State ---
  const [videoData, setVideoData] = useState<VideoDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // Visual progress 0-100
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [showResumeModal, setShowResumeModal] = useState(false); // 新增：显示继续播放提示

  // Heartbeat Status State
  const [heartbeatStatus, setHeartbeatStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');
  const [lastHeartbeatTime, setLastHeartbeatTime] = useState<Date | null>(null);

  // 将旧的简单ID映射到UUID格式
  const normalizeId = (id: string): string => {
    const idMap: Record<string, string> = {
      '1': '00000000-0000-0000-0000-000000000001',
      '2': '00000000-0000-0000-0000-000000000002'
    };
    return idMap[id] || id;
  };

  const normalizedVideoId = normalizeId(videoId);

  // --- 1. Initialization: Fetch Video & Last Position ---
  useEffect(() => {
    let mounted = true;
    
    const fetchVideo = async () => {
      try {
        setLoading(true);
        
        console.log('🎬 开始加载视频，videoId:', videoId, 'normalizedVideoId:', normalizedVideoId);
        
        // 优先尝试从后端获取视频详情（包含学习进度）
        try {
          console.log('📡 调用后端 API getVideoDetail...');
          const res = await videoApi.getVideoDetail(normalizedVideoId);
          console.log('📡 后端响应:', res);
          console.log('📡 后端数据:', res.data?.data);
          
          // 后端响应格式是 { code, message, data: { video信息 } }
          const videoInfo = res.data?.data || res.data;
          
          if (videoInfo && videoInfo.id && mounted) {
            const data: VideoDetail = {
              id: videoInfo.id,
              title: videoInfo.title,
              play_url: videoInfo.play_url || videoInfo.url,
              cover_url: videoInfo.cover_url || videoInfo.cover,
              last_position: videoInfo.last_position || 0
            };
            console.log('✅ 从后端加载视频成功，data:', data);
            setVideoData(data);
            setLoading(false);
            return;
          }
          console.warn('⚠️ 后端响应无数据, mounted:', mounted, 'videoInfo:', videoInfo);
        } catch (apiError) {
          console.warn('⚠️ 后端 API 调用失败:', apiError);
        }
        
        // 如果后端失败，使用 mock 数据作为后备
        console.log('🔍 尝试使用 mock 数据...');
        const { MOCK_VIDEOS } = await import('../services/mockData');
        console.log('📚 可用的 mock 视频:', MOCK_VIDEOS.map(v => ({ id: v.id, title: v.title })));
        const mockVideo = MOCK_VIDEOS.find(v => v.id === normalizedVideoId);
        console.log('🎯 匹配结果:', mockVideo ? `找到 ${mockVideo.title}` : '未找到');
        
        if (mockVideo && mounted) {
          const data: VideoDetail = {
            id: mockVideo.id,
            title: mockVideo.title,
            play_url: mockVideo.url,
            cover_url: mockVideo.cover,
            last_position: 0  // Mock 数据总是从头开始
          };
          setVideoData(data);
          console.log('✅ 使用 mock 数据成功，data:', data);
          setLoading(false);
          return;
        }
        
        // 如果连 mock 数据都没有，显示错误
        console.error('❌ 无法加载视频数据，所有数据源都失败');
      } catch (error) {
        console.error('❌ fetchVideo 异常:', error);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchVideo();

    return () => { 
      mounted = false;
      console.log('🔄 VideoLearningPlayer unmounted, videoId:', videoId);
    };
  }, [videoId, normalizedVideoId]);

  // --- Auto-Seek on Load ---
  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const video = e.currentTarget;
    setDuration(video.duration);
    
    if (videoData?.last_position && videoData.last_position > 0) {
      if (autoResume) {
        // 自动跳转到上次位置
        video.currentTime = videoData.last_position;
        setCurrentTime(videoData.last_position);
      } else {
        // 显示是否继续播放的询问
        setShowResumeModal(true);
      }
    }
  };

  // --- 2. Heartbeat System ---
  const sendHeartbeat = async (playing: boolean, forcePosition?: number) => {
    if (!videoRef.current) return;
    
    // Use ref or forcePosition to get latest value without state dependency
    const pos = Math.floor(forcePosition ?? positionRef.current);
    const dur = Math.floor(videoRef.current.duration || 0);

    // 只有当 duration 有效时才发送心跳
    if (!dur || dur <= 0 || isNaN(dur)) {
      console.log('⏸️ Skipping heartbeat: invalid duration', dur);
      return;
    }

    const payload: HeartbeatPayload = {
      video_id: normalizedVideoId,
      position: pos,
      duration: dur
    };

    console.log('📤 Sending heartbeat payload:', JSON.stringify(payload), 'Types:', {
      video_id: typeof payload.video_id,
      position: typeof payload.position,
      duration: typeof payload.duration
    });

    try {
      setHeartbeatStatus('sending');
      await learnApi.sendHeartbeat(payload);
      console.log('💓 Heartbeat sent successfully');
      setHeartbeatStatus('success');
      setLastHeartbeatTime(new Date());
      // Reset status to idle after 2 seconds
      setTimeout(() => setHeartbeatStatus('idle'), 2000);
    } catch (error) {
      // Fail silently for heartbeat
      console.error('❌ Heartbeat failed:', error);
      setHeartbeatStatus('error');
    }
  };

  // Timer Effect
  useEffect(() => {
    if (isPlaying) {
      // Send immediately on start
      sendHeartbeat(true);

      // Schedule every 10s
      heartbeatTimerRef.current = setInterval(() => {
        sendHeartbeat(true);
      }, 10000);
    } else {
      // Clear when paused
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }
    }

    return () => {
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
      }
    };
  }, [isPlaying, videoId]);

  // Cleanup & AppState Listener Effect
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // App went to background -> Force heartbeat
        sendHeartbeat(false);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      
      // Component Unmount -> Force heartbeat
      // Reading from positionRef.current ensures we have latest value even in closure
      console.log('🛑 Player unmount cleanup');
      sendHeartbeat(false);
    };
  }, [videoId]);


  // --- 3. Completion Logic & Progress ---
  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const curr = videoRef.current.currentTime;
      const dur = videoRef.current.duration;
      
      // Update Ref for cleanup access
      positionRef.current = curr;

      // Update State for UI
      setCurrentTime(curr);
      setProgress((curr / dur) * 100);

      // Check Completion (>= 90%)
      if (!hasCompletedRef.current && dur > 0 && (curr / dur) >= 0.9) {
        handleReachCompletion();
      }
    }
  };

  const handleReachCompletion = () => {
    hasCompletedRef.current = true;
    if (videoRef.current) {
      videoRef.current.pause();
      setIsPlaying(false);
    }
    console.log('🎉 90% reached, showing modal');
    setShowCompleteModal(true);
  };

  const handleCompletionChoice = async (status: 'learned' | 'review_needed') => {
    try {
      await learnApi.completeLearn({
        video_id: videoId,
        status: status
      });
      setShowCompleteModal(false);
      if (onComplete) onComplete(status);
    } catch (error) {
      console.error('Failed to complete', error);
      alert('提交失败，请重试');
    }
  };

  // --- UI Controls ---
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Format seconds to MM:SS
  const formatTime = (time: number) => {
    if (isNaN(time)) return '0:00';
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  // 处理继续播放选择
  const handleResumeChoice = (resume: boolean) => {
    setShowResumeModal(false);
    if (resume && videoRef.current && videoData?.last_position) {
      videoRef.current.currentTime = videoData.last_position;
      setCurrentTime(videoData.last_position);
    }
  };

  if (loading) {
    return (
      <div className="w-full aspect-video bg-gray-900 rounded-xl flex items-center justify-center text-white">
        <Loader2 className="animate-spin mr-2" />
        加载视频中...
      </div>
    );
  }

  if (!videoData) {
    return (
      <div className="w-full aspect-video bg-gray-900 rounded-xl flex items-center justify-center text-white">
        <X className="mr-2" />
        视频加载失败
      </div>
    );
  }

  return (
    <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden shadow-lg group">
      <video
        ref={videoRef}
        src={videoData.play_url}
        poster={videoData.cover_url}
        className="w-full h-full object-contain"
        playsInline
        onClick={togglePlay}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onPlay={() => setIsPlaying(true)}
        onPause={() => {
          setIsPlaying(false);
          sendHeartbeat(false);
        }}
        onEnded={() => setIsPlaying(false)}
      />



      {/* Heartbeat Status Indicator (Top Right) */}
      <div className="absolute top-4 right-4 z-20 flex flex-col items-end pointer-events-none">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full backdrop-blur-md transition-all duration-300 ${
            heartbeatStatus === 'error' ? "bg-red-500/80 text-white" :
            heartbeatStatus === 'sending' ? "bg-blue-500/80 text-white" :
            heartbeatStatus === 'success' ? "bg-green-500/80 text-white" :
            "bg-black/40 text-gray-200"
          }`}
        >
          {heartbeatStatus === 'sending' && <Loader2 size={12} className="animate-spin" />}
          {heartbeatStatus === 'success' && <CheckCircle size={12} />}
          {heartbeatStatus === 'error' && <X size={12} />}
          {heartbeatStatus === 'idle' && <HelpCircle size={12} />}
          
          <span className="text-[10px] font-medium font-mono">
            {heartbeatStatus === 'sending' ? '同步中...' :
             heartbeatStatus === 'success' ? '已同步' :
             heartbeatStatus === 'error' ? '同步失败' :
             '学习监控中'}
          </span>
        </div>
        {lastHeartbeatTime && (
          <span className="text-[9px] text-white/60 mt-1 mr-2 font-mono">
            上次同步: {lastHeartbeatTime.toLocaleTimeString([], { hour12: false })}
          </span>
        )}
      </div>

      {/* Center Play Button (Overlay) */}
      {!isPlaying && !showCompleteModal && (
        <div 
          className="absolute inset-0 flex items-center justify-center bg-black/30 cursor-pointer"
          onClick={togglePlay}
        >
          <div className="bg-white/20 backdrop-blur-sm p-4 rounded-full transition-transform hover:scale-110">
            <Play fill="white" size={48} className="text-white ml-1" />
          </div>
        </div>
      )}

      {/* Bottom Controls */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
        <div className="flex items-center gap-4 text-white">
          <button onClick={togglePlay}>
            {isPlaying ? <Pause size={24} fill="white" /> : <Play size={24} fill="white" />}
          </button>
          
          <div className="text-xs font-mono">
            {formatTime(currentTime)} / {formatTime(duration)}
          </div>

          <div className="flex-1 h-1 bg-gray-600 rounded-full overflow-hidden cursor-pointer relative group/progress">
            <div 
              className="h-full bg-blue-500 relative" 
              style={{ width: `${progress}%` }}
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow opacity-0 group-hover/progress:opacity-100 transition-opacity" />
            </div>
            
            {/* Interactive Range Input */}
            <input 
              type="range" 
              min="0" 
              max="100" 
              step="0.1"
              value={progress}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setProgress(val);
                if (videoRef.current && videoRef.current.duration) {
                  const newTime = (val / 100) * videoRef.current.duration;
                  videoRef.current.currentTime = newTime;
                  // Trigger completion check manually on seek
                  if (!hasCompletedRef.current && videoRef.current.duration > 0 && (newTime / videoRef.current.duration) >= 0.9) {
                    handleReachCompletion();
                  }
                }
              }}
              onClick={(e) => e.stopPropagation()}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
            />
          </div>
        </div>
      </div>

      {/* Resume Modal */}
      {showResumeModal && videoData?.last_position && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in zoom-in duration-300">
          <div className="bg-white rounded-2xl p-6 w-[80%] max-w-sm shadow-2xl">
            <h3 className="text-lg font-bold text-gray-900 mb-4">继续上次播放</h3>
            
            <p className="text-gray-600 text-sm mb-6">
              检测到您上次播放到 {formatTime(videoData.last_position)}，是否要继续播放？
            </p>

            <div className="space-y-3">
              <button
                onClick={() => handleResumeChoice(true)}
                className="w-full flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-600 text-white py-3 rounded-xl font-bold transition-colors"
              >
                继续播放
              </button>
              
              <button
                onClick={() => handleResumeChoice(false)}
                className="w-full flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 text-gray-700 py-3 rounded-xl font-bold transition-colors"
              >
                从头开始
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Completion Modal */}
      {showCompleteModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in zoom-in duration-300">
          <div className="bg-white rounded-2xl p-6 w-[80%] max-w-sm shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900">恭喜！已学习 90%</h3>
              <button onClick={() => setShowCompleteModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            
            <p className="text-gray-600 text-sm mb-6">
              您已完成本节课的大部分内容，请评估您的学习效果：
            </p>

            <div className="space-y-3">
              <button
                onClick={() => handleCompletionChoice('learned')}
                className="w-full flex items-center justify-center gap-2 bg-green-500 hover:bg-green-600 text-white py-3 rounded-xl font-bold transition-colors"
              >
                <CheckCircle size={20} />
                我已学会
              </button>
              
              <button
                onClick={() => handleCompletionChoice('review_needed')}
                className="w-full flex items-center justify-center gap-2 bg-amber-100 hover:bg-amber-200 text-amber-700 py-3 rounded-xl font-bold transition-colors"
              >
                <HelpCircle size={20} />
                需复习
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
