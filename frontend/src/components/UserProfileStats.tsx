import React from 'react';
import { Clock, CheckCircle, PlayCircle, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export interface LearnRecord {
  video_id: string;
  video_title: string;
  cover_url: string;
  status: 'learned' | 'review_needed';
  last_watch_time: string;
}

interface UserProfileStatsProps {
  totalTime: number; // in minutes
  completedCount: number;
  records: LearnRecord[];
}

export const UserProfileStats: React.FC<UserProfileStatsProps> = ({
  totalTime,
  completedCount,
  records
}) => {
  const navigate = useNavigate();
  const reviewList = records.filter(r => r.status === 'review_needed');

  const formatTime = (mins: number) => {
    if (mins < 60) return `${mins}分钟`;
    const hours = Math.floor(mins / 60);
    const m = mins % 60;
    return `${hours}小时${m}分钟`;
  };

  return (
    <div className="w-full bg-white mb-2">
      {/* 1. Stats Overview */}
      <div className="grid grid-cols-2 gap-4 p-4 border-b border-gray-100">
        <div className="bg-blue-50 p-4 rounded-2xl flex flex-col items-center justify-center">
          <div className="flex items-center gap-2 mb-1 text-blue-600">
            <Clock size={18} />
            <span className="text-sm font-medium">累计学习</span>
          </div>
          <span className="text-xl font-bold text-gray-900">{formatTime(totalTime)}</span>
        </div>
        
        <div className="bg-green-50 p-4 rounded-2xl flex flex-col items-center justify-center">
          <div className="flex items-center gap-2 mb-1 text-green-600">
            <CheckCircle size={18} />
            <span className="text-sm font-medium">已修完</span>
          </div>
          <span className="text-xl font-bold text-gray-900">{completedCount} 节</span>
        </div>
      </div>

      {/* 2. Review List */}
      {reviewList.length > 0 && (
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-lg flex items-center gap-2">
              <AlertCircle size={20} className="text-amber-500" />
              待复习任务
            </h3>
            <span className="text-xs text-gray-400">{reviewList.length} 个视频</span>
          </div>
          
          <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar snap-x">
            {reviewList.map((item) => (
              <div 
                key={item.video_id}
                onClick={() => navigate(`/video/${item.video_id}`)}
                className="flex-shrink-0 w-40 snap-start cursor-pointer group"
              >
                <div className="relative aspect-video bg-gray-200 rounded-xl overflow-hidden mb-2 shadow-sm">
                  <img 
                    src={item.cover_url} 
                    alt={item.video_title} 
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  <div className="absolute inset-0 bg-black/20 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                    <PlayCircle className="text-white" size={32} />
                  </div>
                </div>
                
                <h4 className="font-bold text-sm text-gray-800 line-clamp-2 mb-1 leading-tight">
                  {item.video_title}
                </h4>
                <p className="text-xs text-gray-400">
                  上次复习: {new Date(item.last_watch_time).toLocaleDateString()}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
