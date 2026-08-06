import React from 'react';
import { MessageSquare, Heart, UserPlus } from 'lucide-react';

export const Inbox: React.FC = () => {
  return (
    <div className="flex flex-col h-full bg-white pb-20">
      <div className="p-4 border-b">
        <h1 className="text-xl font-bold text-center">消息</h1>
      </div>

      <div className="flex justify-around p-4 border-b border-gray-100">
        <div className="flex flex-col items-center gap-2">
          <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center text-red-500">
            <Heart size={24} fill="currentColor" />
          </div>
          <span className="text-xs text-gray-600">赞</span>
        </div>
        <div className="flex flex-col items-center gap-2">
          <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-500">
            <MessageSquare size={24} fill="currentColor" />
          </div>
          <span className="text-xs text-gray-600">评论</span>
        </div>
        <div className="flex flex-col items-center gap-2">
          <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-green-500">
            <UserPlus size={24} fill="currentColor" />
          </div>
          <span className="text-xs text-gray-600">粉丝</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-start gap-3 p-4 hover:bg-gray-50 active:bg-gray-100 transition-colors">
             <div className="relative">
                <div className="w-12 h-12 bg-gray-200 rounded-full overflow-hidden">
                  <img src={`https://picsum.photos/seed/${i + 10}/100`} alt="Avatar" className="w-full h-full object-cover" />
                </div>
             </div>
             <div className="flex-1 min-w-0">
               <div className="flex justify-between items-baseline mb-1">
                 <h3 className="font-bold text-sm">系统通知</h3>
                 <span className="text-xs text-gray-400">10:2{i}</span>
               </div>
               <p className="text-sm text-gray-600 line-clamp-1">您的视频《Python基础教程》已完成智能拆分，快来看看吧！</p>
             </div>
             <div className="w-12 h-12 bg-gray-100 rounded overflow-hidden">
                <img src={`https://picsum.photos/seed/${i}/100`} alt="Video" className="w-full h-full object-cover opacity-80" />
             </div>
          </div>
        ))}
      </div>
    </div>
  );
};
