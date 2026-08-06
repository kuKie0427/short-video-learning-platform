import React, { useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload as UploadIcon, CheckCircle, FileVideo, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';
import { useResumableUpload } from '../hooks/useResumableUpload';

export const VideoUploader: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { status, progress, currentChunk, totalChunks, error, uploadedVideoId, startUpload, reset } = useResumableUpload();

  // 上传完成后自动跳转到切分页面
  useEffect(() => {
    if (status === 'completed' && uploadedVideoId) {
      // 延迟1秒后跳转，让用户看到成功提示
      const timer = setTimeout(() => {
        navigate('/split');
      }, 1500);
      return () => clearTimeout(timer);
    }
  }, [status, uploadedVideoId, navigate]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      startUpload(e.target.files[0]);
    }
  };

  const renderContent = () => {
    switch (status) {
      case 'idle':
        return (
          <div 
            className="flex flex-col items-center justify-center h-64 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
          >
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center text-blue-500 mb-4">
              <UploadIcon size={32} />
            </div>
            <p className="text-gray-600 font-bold mb-1">点击选择视频</p>
            <p className="text-xs text-gray-400">支持断点续传</p>
            <input 
              ref={fileInputRef}
              type="file" 
              accept="video/*" 
              className="hidden"
              onChange={handleFileChange}
            />
          </div>
        );

      case 'compressing':
        return (
          <div className="flex flex-col items-center justify-center h-64 p-6">
            <Loader2 size={48} className="text-blue-500 animate-spin mb-4" />
            <h3 className="font-bold text-lg mb-2">正在预处理视频...</h3>
            <p className="text-sm text-gray-500">正在检查格式与时长</p>
          </div>
        );

      case 'uploading':
        return (
          <div className="flex flex-col items-center justify-center h-64 p-6 w-full">
            <div className="w-full max-w-xs mb-6 relative">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                 <span>上传中...</span>
                 <span>{progress}%</span>
              </div>
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
            
            <div className="flex items-center gap-3 text-blue-600 bg-blue-50 px-4 py-2 rounded-full">
              <RefreshCw size={18} className="animate-spin" />
              <span className="text-sm font-medium">正在上传第 {currentChunk}/{totalChunks} 片</span>
            </div>
            <p className="text-xs text-gray-400 mt-4">请勿关闭页面，支持断点续传</p>
          </div>
        );

      case 'transcoding':
        return (
          <div className="flex flex-col items-center justify-center h-64 p-6">
             <div className="w-16 h-16 bg-purple-100 rounded-full flex items-center justify-center text-purple-500 mb-4 animate-pulse">
               <FileVideo size={32} />
             </div>
             <h3 className="font-bold text-lg mb-2">正在转码中...</h3>
             <p className="text-sm text-gray-500">即将完成，请稍候</p>
          </div>
        );

      case 'completed':
        return (
          <div className="flex flex-col items-center justify-center h-64 p-6">
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center text-green-500 mb-4 animate-bounce">
              <CheckCircle size={32} />
            </div>
            <h3 className="font-bold text-lg mb-2">上传成功！</h3>
            <p className="text-sm text-gray-500 mb-2">正在跳转到切分页面...</p>
            <div className="flex items-center gap-2 text-blue-600">
              <Loader2 size={16} className="animate-spin" />
              <span className="text-xs">即将开始智能切分</span>
            </div>
          </div>
        );

      case 'error':
        return (
          <div className="flex flex-col items-center justify-center h-64 p-6">
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center text-red-500 mb-4">
              <AlertCircle size={32} />
            </div>
            <h3 className="font-bold text-lg mb-2 text-red-600">上传失败</h3>
            <p className="text-sm text-gray-500 mb-6 text-center max-w-xs">{error}</p>
            <button 
              onClick={reset}
              className="px-6 py-2 bg-blue-600 text-white rounded-full font-medium hover:bg-blue-700"
            >
              重试
            </button>
          </div>
        );
    }
  };

  return (
    <div className="w-full bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      {renderContent()}
    </div>
  );
};
