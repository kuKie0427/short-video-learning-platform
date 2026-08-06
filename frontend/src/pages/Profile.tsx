import React, { useEffect, useState } from 'react';
import { Share2, Bookmark, Grid, Lock, LogOut, PlayCircle as PlayCircleIcon } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { UserProfileStats, type LearnRecord } from '../components/UserProfileStats';
import { EditProfileModal } from '../components/EditProfileModal';
import { MOCK_VIDEOS } from '../services/mockData';
import { learnApi } from '../services/api';

export const Profile: React.FC = () => {
  const { user, logout } = useAuth();
  const [records, setRecords] = useState<LearnRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [isEditOpen, setIsEditOpen] = useState(false);

  // Fetch records from backend
  useEffect(() => {
    const fetchRecords = async () => {
      try {
        const res = await learnApi.getRecords();
        if (res.data.code === 200) {
          // 后端返回的数据结构是 { records: [], total: 0 }
          setRecords(res.data.data.records || []);
        }
      } catch (error) {
        console.error("Failed to fetch learn records", error);
      } finally {
        setLoading(false);
      }
    };

    fetchRecords();
  }, []);

  return (
    <div className="flex flex-col h-full bg-white pb-20 overflow-y-auto">
      {/* Header Actions */}
      <div className="flex justify-between items-center p-4 sticky top-0 bg-white z-10">
        <h1 className="font-bold text-lg">{user?.nickname || '我的'}</h1>
        <div className="flex gap-4">
          <Share2 size={24} />
          <button onClick={logout} title="退出登录">
             <LogOut size={24} className="text-red-500" />
          </button>
        </div>
      </div>

      {/* Profile Info */}
      <div className="flex flex-col items-center px-4 pb-6 border-b border-gray-100">
        <div className="w-24 h-24 rounded-full overflow-hidden bg-gray-200 mb-4 border-4 border-gray-50">
           <img src={user?.avatar || "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=200&q=80"} alt="Avatar" className="w-full h-full object-cover" />
        </div>
        <h2 className="text-xl font-bold mb-1">@{user?.nickname || '用户'}</h2>
        <p className="text-sm text-gray-500 mb-4">{user?.bio || '热爱编程，分享技术 | 全栈开发者'}</p>

        
        <div className="flex gap-8 mb-6">
          <div className="flex flex-col items-center">
            <span className="font-bold text-lg">142</span>
            <span className="text-xs text-gray-500">关注</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="font-bold text-lg">1.2w</span>
            <span className="text-xs text-gray-500">粉丝</span>
          </div>
          <div className="flex flex-col items-center">
            <span className="font-bold text-lg">8.5k</span>
            <span className="text-xs text-gray-500">获赞</span>
          </div>
        </div>

        <div className="flex gap-2 w-full">
          <button 
            onClick={() => setIsEditOpen(true)}
            className="flex-1 bg-gray-100 py-2 rounded font-medium text-sm active:bg-gray-200 transition-colors"
          >
            编辑资料
          </button>
          <button className="flex-1 bg-gray-100 py-2 rounded font-medium text-sm">添加朋友</button>
        </div>
      </div>

      {/* Edit Profile Modal */}
      {isEditOpen && <EditProfileModal onClose={() => setIsEditOpen(false)} />}

      {/* Learning Stats Component */}
      <UserProfileStats 
        totalTime={128} 
        completedCount={records.filter(r => r.status === 'learned').length} 
        records={records} 
      />

      {/* Tabs */}
      <div className="flex border-b border-gray-200 sticky top-[60px] bg-white z-10">
        <div className="flex-1 flex items-center justify-center py-3 border-b-2 border-black">
          <Grid size={20} />
        </div>
        <div className="flex-1 flex items-center justify-center py-3 text-gray-400">
          <Bookmark size={20} />
        </div>
        <div className="flex-1 flex items-center justify-center py-3 text-gray-400">
          <Lock size={20} />
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-3 gap-0.5">
        {records.length > 0 ? (
          records.map((record, idx) => (
            <div key={idx} className="aspect-[3/4] bg-gray-200 relative group cursor-pointer">
               <img src={record.cover_url} alt="Cover" className="w-full h-full object-cover" />
               <div className="absolute top-1 right-1">
                 {record.status === 'learned' ? (
                   <div className="bg-green-500/80 p-1 rounded-full">
                     <PlayCircleIcon size={12} className="text-white" />
                   </div>
                 ) : (
                   <div className="bg-amber-500/80 p-1 rounded-full">
                     <Lock size={12} className="text-white" />
                   </div>
                 )}
               </div>
               <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/60 to-transparent p-2">
                 <p className="text-white text-[10px] line-clamp-2">{record.video_title}</p>
               </div>
            </div>
          ))
        ) : (
          <div className="col-span-3 py-10 text-center text-gray-400 text-sm">
            暂无学习记录
          </div>
        )}
      </div>
    </div>
  );
};
