import React from 'react';
import { Search, PlayCircle, Clock } from 'lucide-react';

export const Courses: React.FC = () => {
  return (
    <div className="flex flex-col h-full bg-gray-50 pb-20">
      <div className="bg-white p-4 sticky top-0 z-10 shadow-sm">
        <h1 className="text-xl font-bold mb-4">发现课程</h1>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input 
            type="text" 
            placeholder="搜索感兴趣的课程..." 
            className="w-full bg-gray-100 rounded-full py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="bg-white rounded-xl overflow-hidden shadow-sm flex flex-col">
            <div className="relative h-32 bg-gray-200">
               <img src={`https://picsum.photos/seed/${i}/400/200`} alt="Course Cover" className="w-full h-full object-cover" />
               <div className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded flex items-center gap-1">
                 <Clock size={12} />
                 <span>12 节课</span>
               </div>
            </div>
            <div className="p-3">
              <h3 className="font-bold text-base mb-1">Python 数据分析实战系列 {i}</h3>
              <div className="flex items-center justify-between text-xs text-gray-500">
                <div className="flex items-center gap-1">
                  <PlayCircle size={14} />
                  <span>1.2w 人在学</span>
                </div>
                <button className="bg-blue-600 text-white px-3 py-1 rounded-full font-medium">
                  开始学习
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
