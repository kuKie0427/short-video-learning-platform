import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { VideoLearningPlayer } from '../components/VideoLearningPlayer';
import { MOCK_VIDEOS, type Video } from '../services/mockData';
import { videoApi } from '../services/api';

export const VideoDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [video, setVideo] = useState<Video | null>(null);
  
  // 检测是否从搜索页面来
  const isFromSearch = new URLSearchParams(location.search).get('from') === 'search';
  
  // 将旧的简单ID映射到UUID格式
  const normalizeId = (id: string): string => {
    const idMap: Record<string, string> = {
      '1': '00000000-0000-0000-0000-000000000001',
      '2': '00000000-0000-0000-0000-000000000002'
    };
    return idMap[id] || id;
  };
  
  useEffect(() => {
    const fetchMeta = async () => {
      if (!id) return;
      
      const normalizedId = normalizeId(id);
      
      // 先尝试从 mock 数据中查找
      const mockVideo = MOCK_VIDEOS.find(v => v.id === normalizedId);
      if (mockVideo) {
        setVideo(mockVideo);
        return;
      }
      
      // 如果不是mock数据，再尝试从后端获取
      try {
        const res = await videoApi.getVideoDetail(normalizedId);
        if (res.data) {
          setVideo({
            id: res.data.id,
            title: res.data.title,
            description: res.data.description || '',
            url: res.data.url,
            cover: res.data.cover || '',
            author: { 
              id: res.data.author?.id || 'u_any', 
              name: res.data.author?.name || '作者', 
              avatar: res.data.author?.avatar || 'https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=100&q=80' 
            },
            likes: res.data.likes || 0,
            comments: res.data.comments || 0,
            shares: res.data.shares || 0
          });
        }
      } catch (error) {
        console.log('Failed to fetch video from API, using fallback');
        // API失败，使用默认视频
        setVideo(MOCK_VIDEOS[0]);
      }
    };
    fetchMeta();
  }, [id]);

  const handleComplete = () => {
    // Navigate back after completion or stay
    // navigate(-1); 
  };

  return (
    <div className="flex flex-col h-screen bg-black text-white">
      {/* Navbar */}
      <div className="flex items-center p-4 sticky top-0 z-10 bg-gradient-to-b from-black/80 to-transparent">
        <button 
          onClick={() => navigate(-1)} 
          className="p-2 -ml-2 rounded-full hover:bg-white/10 transition-colors"
        >
          <ArrowLeft size={24} />
        </button>
        <span className="ml-2 font-bold truncate flex-1">{video?.title || ''}</span>
      </div>

      {/* Player Area */}
      <div className="flex-1 flex flex-col justify-center">
        {id && (
          <VideoLearningPlayer
            videoId={id}
            onComplete={handleComplete}
            autoResume={!isFromSearch} // 从搜索来的视频不自动恢复，询问用户
          />
        )}
        
        <div className="p-6">
          <h1 className="text-xl font-bold mb-2">{video?.title || ''}</h1>
          <div className="flex items-center gap-3 mb-4">
            <img src={video?.author.avatar} className="w-8 h-8 rounded-full border border-white/20" alt="author" />
            <span className="text-sm text-gray-300">{video?.author.name}</span>
          </div>
          <p className="text-sm text-gray-400 leading-relaxed">
            {video?.description}
          </p>
        </div>
      </div>
    </div>
  );
};
