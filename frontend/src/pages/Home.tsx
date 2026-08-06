import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { MOCK_VIDEOS, type Video } from '../services/mockData';
import { VideoPlayer } from '../components/VideoPlayer';
import { videoApi } from '../services/api';

export const Home: React.FC = () => {
  const navigate = useNavigate();
  const [activeindex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [loading, setLoading] = useState(true);

  // Load videos from API
  useEffect(() => {
    const loadVideos = async () => {
      try {
        const response = await videoApi.getRecommendFeed(1);
        if (response.data?.data?.videos && response.data.data.videos.length > 0) {
          const apiVideos = response.data.data.videos.map((v: any) => ({
            id: v.id,
            title: v.title,
            description: v.description,
            url: v.play_url,
            cover: v.cover_url,
            author: {
              id: v.author_id,
              name: v.author_nickname || '用户',
              avatar: v.author_avatar || '/default-avatar.png'
            },
            likes: v.like_count || 0,
            comments: v.comment_count || 0,
            shares: 0
          }));
          setVideos(apiVideos);
        } else {
          // 如果API没有返回视频，使用Mock数据
          setVideos(MOCK_VIDEOS);
        }
      } catch (error) {
        console.error('加载视频失败:', error);
        // 加载失败时降级到Mock数据
        setVideos(MOCK_VIDEOS);
      } finally {
        setLoading(false);
      }
    };
    loadVideos();
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const index = Math.round(container.scrollTop / container.clientHeight);
      if (index !== activeindex) {
        setActiveIndex(index);
      }
    };

    // Use IntersectionObserver for better performance? 
    // For simplicity, scroll event with debounce/round is okay for demo
    // Actually, snap scroll handles the movement, we just need to detect which one is active.
    
    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [activeindex]);

  return (
    <div className="relative h-full w-full bg-black">
      {/* Search Overlay */}
      <div className="absolute top-4 right-4 z-20 pt-2">
        <button 
          onClick={() => navigate('/search')}
          className="bg-black/20 backdrop-blur-md p-2 rounded-full text-white hover:bg-black/40 transition-colors"
        >
          <Search size={24} />
        </button>
      </div>

      {/* Tabs Overlay (Optional, matching TikTok style) */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 pt-2 flex gap-4 text-white font-bold text-lg drop-shadow-md">
        <span className="opacity-60">关注</span>
        <span className="border-b-2 border-white pb-1">推荐</span>
      </div>

      <div 
        ref={containerRef}
        className="h-full w-full overflow-y-scroll snap-y snap-mandatory no-scrollbar"
        style={{ scrollBehavior: 'smooth' }}
      >
        {videos.map((video, index) => (
          <div key={video.id} className="w-full h-full snap-start">
            <VideoPlayer video={video} isActive={index === activeindex} />
          </div>
        ))}
      </div>
    </div>
  );
};

