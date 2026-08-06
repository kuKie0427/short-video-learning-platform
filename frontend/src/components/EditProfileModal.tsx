import React, { useState, useRef } from 'react';
import { X, ChevronLeft, Camera, ChevronRight, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { splitApi } from '../services/api';

interface EditProfileModalProps {
  onClose: () => void;
}

export const EditProfileModal: React.FC<EditProfileModalProps> = ({ onClose }) => {
  const { user, updateUser } = useAuth();
  const [loading, setLoading] = useState(false);
  
  // Form State
  const [avatar, setAvatar] = useState(user?.avatar || '');
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [bio, setBio] = useState(user?.bio || '');
  const [gender, setGender] = useState(user?.gender || 'male');
  const [location, setLocation] = useState(user?.location || '');
  const [school, setSchool] = useState(user?.school || '');

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle Image Upload
  const handleAvatarClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setLoading(true);
      // Convert to Base64
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64 = reader.result as string;
        try {
          const res = await splitApi.uploadImage(base64);
          if (res.data.code === 200) {
            setAvatar(res.data.data.url);
          }
        } catch (error) {
          console.error("Upload failed", error);
          alert("图片上传失败");
        } finally {
          setLoading(false);
        }
      };
      reader.readAsDataURL(file);
    } catch (error) {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      const res = await splitApi.updateProfile({
        nickname,
        bio,
        gender,
        location,
        school,
        avatar_url: avatar  // 后端期望 avatar_url 字段
      });

      if (res.data.code === 200) {
        // 将后端返回的 avatar_url 映射为 avatar
        const userData = {
          ...res.data.data,
          avatar: res.data.data.avatar || res.data.data.avatar_url
        };
        updateUser(userData);
        onClose();
      }
    } catch (error) {
      console.error("Update failed", error);
      alert("保存失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-white flex flex-col animate-in slide-in-from-bottom duration-300">
      {/* Navbar */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
        <button onClick={onClose} className="text-gray-600">
          <ChevronLeft size={24} />
        </button>
        <span className="text-base font-bold text-gray-900">编辑资料</span>
        <button 
          onClick={handleSave}
          disabled={loading}
          className="text-blue-600 font-medium text-sm disabled:opacity-50"
        >
          {loading ? '保存中...' : '保存'}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto bg-gray-50">
        {/* Avatar Section */}
        <div className="flex flex-col items-center py-8 bg-white mb-2">
          <div className="relative group cursor-pointer" onClick={handleAvatarClick}>
            <div className="w-24 h-24 rounded-full overflow-hidden border-2 border-gray-100">
              <img src={avatar} alt="Avatar" className="w-full h-full object-cover" />
            </div>
            <div className="absolute inset-0 bg-black/30 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Camera className="text-white" size={24} />
            </div>
            <div className="absolute bottom-0 left-0 right-0 h-1/3 bg-gradient-to-t from-black/50 to-transparent flex justify-center items-end pb-1">
              <Camera className="text-white/80 w-5 h-5" />
            </div>
          </div>
          <span className="text-xs text-gray-500 mt-3">点击更换头像</span>
          <input 
            ref={fileInputRef}
            type="file" 
            accept="image/*" 
            className="hidden" 
            onChange={handleFileChange}
          />
        </div>

        {/* Form Fields */}
        <div className="bg-white px-4">
          <div className="flex items-center justify-between py-4 border-b border-gray-50">
            <span className="text-gray-900 w-20">名字</span>
            <input 
              type="text" 
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              className="flex-1 text-right text-gray-600 focus:outline-none placeholder-gray-300"
              placeholder="设置名字"
            />
            <ChevronRight size={16} className="text-gray-300 ml-2" />
          </div>

          <div className="flex items-center justify-between py-4 border-b border-gray-50">
            <span className="text-gray-900 w-20">简介</span>
            <input 
              type="text" 
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              className="flex-1 text-right text-gray-600 focus:outline-none placeholder-gray-300"
              placeholder="介绍一下自己"
            />
            <ChevronRight size={16} className="text-gray-300 ml-2" />
          </div>

          <div className="flex items-center justify-between py-4 border-b border-gray-50">
            <span className="text-gray-900 w-20">性别</span>
            <select 
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="flex-1 text-right text-gray-600 focus:outline-none bg-transparent appearance-none dir-rtl"
              dir="rtl"
            >
              <option value="male">男</option>
              <option value="female">女</option>
              <option value="other">不展示</option>
            </select>
            <ChevronRight size={16} className="text-gray-300 ml-2" />
          </div>

          <div className="flex items-center justify-between py-4 border-b border-gray-50">
            <span className="text-gray-900 w-20">所在地</span>
            <input 
              type="text" 
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="flex-1 text-right text-gray-600 focus:outline-none placeholder-gray-300"
              placeholder="添加位置"
            />
            <ChevronRight size={16} className="text-gray-300 ml-2" />
          </div>

          <div className="flex items-center justify-between py-4">
            <span className="text-gray-900 w-20">学校</span>
            <input 
              type="text" 
              value={school}
              onChange={(e) => setSchool(e.target.value)}
              className="flex-1 text-right text-gray-600 focus:outline-none placeholder-gray-300"
              placeholder="添加学校"
            />
            <ChevronRight size={16} className="text-gray-300 ml-2" />
          </div>
        </div>
      </div>
    </div>
  );
};
