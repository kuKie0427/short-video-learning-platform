import React, { useRef, useState, useEffect } from 'react';
import { Heart, MessageCircle, Share2, Play, X, Send, MoreHorizontal, Link as LinkIcon, CheckCircle, HelpCircle } from 'lucide-react';
import type { Video } from '../services/mockData';
import { learnApi } from '../services/api';
import clsx from 'clsx';

interface VideoPlayerProps {
  video: Video;
  isActive: boolean;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({ video, isActive }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);

  const [isLongPressing, setIsLongPressing] = useState(false);
  const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  
  // Learning Completion State
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const hasCompletedRef = useRef(false);

  // Interaction States
  const [isLiked, setIsLiked] = useState(false);
  const [likeCount, setLikeCount] = useState(video.likes);
  const [showComments, setShowComments] = useState(false);
  const [showShare, setShowShare] = useState(false);
  const [commentText, setCommentText] = useState('');
  const [comments, setComments] = useState([
    { id: 1, user: '学习小助手', text: '这个视频讲得太好了！醍醐灌顶！', time: '10分钟前', likes: 23 },
    { id: 2, user: 'User8821', text: '马住，考前必看', time: '1小时前', likes: 5 },
    { id: 3, user: '大牛', text: '期待更新下一集', time: '2小时前', likes: 12 },
  ]);

  useEffect(() => {
    if (isActive) {
      // Handle the play promise to avoid race conditions
      const playPromise = videoRef.current?.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          setIsPlaying(true);
        }).catch((error) => {
          // Auto-play was prevented
          console.log("Auto-play prevented:", error);
          setIsPlaying(false);
        });
      }
    } else {
      videoRef.current?.pause();
      setIsPlaying(false);
      if (videoRef.current) videoRef.current.currentTime = 0;
      setShowComments(false);
      setShowShare(false);
    }

    // Cleanup function to ensure video stops when component updates/unmounts
    return () => {
      videoRef.current?.pause();
    };
  }, [isActive]);

  const togglePlay = async () => {
    if (videoRef.current) {
      try {
        if (videoRef.current.paused) {
          const playPromise = videoRef.current.play();
          if (playPromise !== undefined) {
            await playPromise;
            setIsPlaying(true);
          }
        } else {
          videoRef.current.pause();
          setIsPlaying(false);
        }
      } catch (error) {
        console.error("Playback error:", error);
        setIsPlaying(false);
      }
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const curr = videoRef.current.currentTime;
      const dur = videoRef.current.duration;
      const progress = dur > 0 ? (curr / dur) * 100 : 0;
      setProgress(progress);

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
    setShowCompleteModal(true);
  };

  const handleCompletionChoice = async (status: 'learned' | 'review_needed') => {
    try {
      await learnApi.completeLearn({
        video_id: video.id,
        status: status,
        title: video.description, // Use description as title for now
        cover: video.cover
      });
      setShowCompleteModal(false);
      // Show simple toast or alert for now
      alert(status === 'learned' ? '已标记为学会！' : '已加入复习列表');
    } catch (error) {
      console.error('Failed to mark completion', error);
      alert('网络错误，请重试');
    }
  };

  const handleLike = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isLiked) {
      setLikeCount(prev => prev - 1);
    } else {
      setLikeCount(prev => prev + 1);
    }
    setIsLiked(!isLiked);
  };

  const handleSendComment = () => {
    if (!commentText.trim()) return;
    setComments([
      { id: Date.now(), user: '我', text: commentText, time: '刚刚', likes: 0 },
      ...comments
    ]);
    setCommentText('');
  };

  const handleTouchStart = () => {
    longPressTimerRef.current = setTimeout(() => {
      setIsLongPressing(true);
      if (videoRef.current) videoRef.current.playbackRate = 2.0;
    }, 300); // 300ms long press threshold
  };

  const handleTouchEnd = () => {
    if (longPressTimerRef.current) {
      clearTimeout(longPressTimerRef.current);
      longPressTimerRef.current = null;
    }
    if (isLongPressing) {
      setIsLongPressing(false);
      if (videoRef.current) videoRef.current.playbackRate = 1.0;
    }
  };

  return (
    <div 
      className="relative w-full h-full bg-black snap-start shrink-0 overflow-hidden"
      onTouchStart={handleTouchStart}
      onTouchEnd={handleTouchEnd}
      onMouseDown={handleTouchStart}
      onMouseUp={handleTouchEnd}
      onMouseLeave={handleTouchEnd}
    >
      {/* 2X Speed Overlay */}
      {isLongPressing && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 z-30 bg-black/40 backdrop-blur-md px-4 py-1 rounded-full flex items-center gap-2 animate-in fade-in duration-200">
          <MoreHorizontal size={16} className="text-white" />
          <span className="text-white text-xs font-bold">2X 倍速播放中</span>
        </div>
      )}

      {/* Video Element */}
      <video
        ref={videoRef}
        src={video.url}
        className="w-full h-full object-cover"
        loop
        playsInline
        preload="auto"
        onClick={togglePlay}
        onTimeUpdate={handleTimeUpdate}
        poster={video.cover}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onLoadStart={() => console.log('视频开始加载:', video.title)}
        onLoadedData={() => console.log('视频数据加载完成:', video.title)}
        onCanPlay={() => console.log('视频可以播放:', video.title)}
        onError={(e) => console.error('视频加载错误:', video.title, e)}
      />

      {/* Play/Pause Overlay Icon */}
      {!isPlaying && !showComments && !showShare && (
        <div 
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          <div className="bg-black/30 p-4 rounded-full backdrop-blur-sm">
            <Play fill="white" size={48} className="text-white ml-1" />
          </div>
        </div>
      )}

      {/* Side Actions */}
      <div className={clsx(
        "absolute right-2 bottom-20 flex flex-col items-center gap-6 z-10 transition-opacity duration-200",
        (showComments || showShare) ? "opacity-0 pointer-events-none" : "opacity-100"
      )}>
        <div className="relative">
          <img 
            src={video.author.avatar} 
            alt={video.author.name} 
            className="w-12 h-12 rounded-full border-2 border-white object-cover"
          />
          <div className="absolute -bottom-2 left-1/2 -translate-x-1/2 bg-red-500 rounded-full p-0.5">
             <div className="w-3 h-3 flex items-center justify-center text-white text-[10px]">+</div>
          </div>
        </div>
        
        <div className="flex flex-col items-center gap-1 cursor-pointer" onClick={handleLike}>
          <Heart 
            size={32} 
            className={clsx("drop-shadow-md transition-colors", isLiked ? "text-red-500 fill-red-500" : "text-white")} 
          />
          <span className="text-white text-xs font-medium drop-shadow-md">{likeCount}</span>
        </div>

        <div className="flex flex-col items-center gap-1 cursor-pointer" onClick={(e) => { e.stopPropagation(); setShowComments(true); }}>
          <MessageCircle size={32} className="text-white drop-shadow-md" />
          <span className="text-white text-xs font-medium drop-shadow-md">{video.comments}</span>
        </div>

        <div className="flex flex-col items-center gap-1 cursor-pointer" onClick={(e) => { e.stopPropagation(); setShowShare(true); }}>
          <Share2 size={32} className="text-white drop-shadow-md" />
          <span className="text-white text-xs font-medium drop-shadow-md">{video.shares}</span>
        </div>
      </div>

      {/* Bottom Info */}
      <div className={clsx(
        "absolute left-4 bottom-6 right-16 z-10 text-white transition-opacity duration-200",
        (showComments || showShare) ? "opacity-0" : "opacity-100"
      )}>
        <h3 className="font-bold text-lg mb-2 drop-shadow-md">@{video.author.name}</h3>
        <p className="text-sm mb-2 drop-shadow-md line-clamp-2">{video.description}</p>
        <div className="flex items-center gap-2 text-xs opacity-80">
           <span className="bg-white/20 px-2 py-1 rounded backdrop-blur-sm">♫ 原始原声 - {video.author.name}</span>
        </div>
      </div>

      {/* Progress Bar (Interactive) */}
      <div className="absolute bottom-[54px] left-0 right-0 h-1 group hover:h-4 transition-all z-20 cursor-pointer">
        <div className="relative w-full h-full bg-white/20">
           {/* Visual Progress */}
           <div 
            className="absolute top-0 left-0 h-full bg-white transition-all duration-100 ease-linear"
            style={{ width: `${progress}%` }}
          />
          
          {/* Input Range for Dragging */}
          <input 
            type="range" 
            min="0" 
            max="100" 
            step="0.1"
            value={isNaN(progress) ? 0 : progress}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              if (!isNaN(val)) {
                setProgress(val);
                if (videoRef.current) {
                  videoRef.current.currentTime = (val / 100) * videoRef.current.duration;
                }
              }
            }}
            onClick={(e) => e.stopPropagation()} // Prevent togglePlay
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer hover:scale-y-[400%] transition-transform origin-bottom"
          />
        </div>
      </div>

      {/* Completion Modal */}
      {showCompleteModal && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in zoom-in duration-300">
          <div className="bg-white rounded-2xl p-6 w-[80%] max-w-sm shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-gray-900">本课学习效果确认</h3>
            </div>
            
            <p className="text-gray-600 text-sm mb-6">
              您已观看大部分内容，是否标记为已学？
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

      {/* Comments Drawer */}
      {showComments && (
        <div className="absolute inset-0 z-50 flex flex-col justify-end bg-black/50 backdrop-blur-sm animate-in slide-in-from-bottom duration-200">
          <div className="bg-white rounded-t-2xl h-[50%] flex flex-col w-full" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="flex justify-between items-center p-4 border-b">
              <div className="w-6" /> {/* Spacer */}
              <h3 className="font-bold text-sm">{comments.length} 条评论</h3>
              <button onClick={() => setShowComments(false)} className="p-1 hover:bg-gray-100 rounded-full">
                <X size={20} className="text-gray-500" />
              </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {comments.map((comment) => (
                <div key={comment.id} className="flex gap-3">
                  <div className="w-8 h-8 bg-gray-200 rounded-full flex-shrink-0" />
                  <div className="flex-1">
                    <p className="text-xs text-gray-500 font-medium mb-0.5">{comment.user}</p>
                    <p className="text-sm text-gray-800">{comment.text}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-400">
                      <span>{comment.time}</span>
                      <span>回复</span>
                    </div>
                  </div>
                  <div className="flex flex-col items-center gap-1 text-gray-400">
                    <Heart size={14} />
                    <span className="text-[10px]">{comment.likes}</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Input */}
            <div className="p-4 border-t bg-white pb-safe">
              <div className="flex items-center gap-3 bg-gray-100 px-4 py-2 rounded-full">
                <input 
                  type="text" 
                  placeholder="留下你的精彩评论..." 
                  className="flex-1 bg-transparent text-sm outline-none"
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendComment()}
                />
                <button 
                  onClick={handleSendComment}
                  className={clsx("transition-colors", commentText ? "text-blue-600" : "text-gray-400")}
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
          </div>
          {/* Click outside to close */}
          <div className="flex-1" onClick={() => setShowComments(false)} />
        </div>
      )}

      {/* Share Sheet */}
      {showShare && (
        <div className="absolute inset-0 z-50 flex flex-col justify-end bg-black/50 backdrop-blur-sm animate-in slide-in-from-bottom duration-200">
          <div className="bg-white rounded-t-2xl p-4 pb-safe w-full max-h-[40%]" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-bold text-sm">分享至</h3>
              <button onClick={() => setShowShare(false)} className="p-1 hover:bg-gray-100 rounded-full">
                <X size={20} className="text-gray-500" />
              </button>
            </div>

            <div className="flex justify-around mb-8">
              {[
                { label: '微信', color: 'bg-green-500', icon: MessageCircle },
                { label: '朋友圈', color: 'bg-green-600', icon: MoreHorizontal },
                { label: '复制链接', color: 'bg-gray-500', icon: LinkIcon },
                { label: '更多', color: 'bg-blue-500', icon: MoreHorizontal },
              ].map((item, idx) => (
                <div key={idx} className="flex flex-col items-center gap-2 cursor-pointer group">
                  <div className={`${item.color} w-12 h-12 rounded-full flex items-center justify-center text-white shadow-lg group-active:scale-95 transition-transform`}>
                    <item.icon size={24} />
                  </div>
                  <span className="text-xs text-gray-500">{item.label}</span>
                </div>
              ))}
            </div>

            <button 
              onClick={() => setShowShare(false)}
              className="w-full bg-gray-100 py-3 rounded-xl font-bold text-gray-700 active:bg-gray-200 transition-colors"
            >
              取消
            </button>
          </div>
          {/* Click outside to close */}
          <div className="flex-1" onClick={() => setShowShare(false)} />
        </div>
      )}
    </div>
  );
};
