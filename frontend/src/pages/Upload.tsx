import React, { useState } from 'react';
import { VideoUploader } from '../components/VideoUploader';
import clsx from 'clsx';

export const Upload: React.FC = () => {
  const [splitMode, setSplitMode] = useState<'auto' | 'manual' | 'hybrid'>('hybrid');

  return (
    <div className="flex flex-col h-full bg-white pb-20 overflow-y-auto">
      <div className="p-4 flex items-center justify-between border-b sticky top-0 bg-white z-10">
        <h1 className="font-bold text-lg">创作中心</h1>
        <div className="w-6" /> {/* Spacer */}
      </div>

      <div className="p-6 space-y-8">
        {/* Upload Section */}
        <section>
          <h2 className="font-bold text-lg mb-4">1. 上传视频</h2>
          <VideoUploader />
        </section>

        {/* Config Section */}
        <section>
          <h2 className="font-bold text-lg mb-4 flex items-center gap-2">
            2. 智能拆分设置
            <span className="text-xs font-normal text-gray-400 bg-gray-100 px-2 py-0.5 rounded">上传后生效</span>
          </h2>
          
          <div className="grid grid-cols-3 gap-3">
            {[
              { id: 'auto', label: '全自动', desc: 'AI自动识别场景' },
              { id: 'hybrid', label: '混合模式', desc: '自动识别+人工微调' },
              { id: 'manual', label: '纯手动', desc: '手动标记拆分点' }
            ].map((mode) => (
              <button
                key={mode.id}
                onClick={() => setSplitMode(mode.id as any)}
                className={clsx(
                  "flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all",
                  splitMode === mode.id 
                    ? "border-blue-500 bg-blue-50 text-blue-600" 
                    : "border-gray-200 text-gray-500"
                )}
              >
                <span className="font-bold text-sm mb-1">{mode.label}</span>
                <span className="text-[10px] text-center opacity-80">{mode.desc}</span>
              </button>
            ))}
          </div>
        </section>

          <div className="bg-blue-50 p-4 rounded-xl text-xs text-blue-600 leading-relaxed">
          <p className="font-bold mb-1">💡 提示：</p>
          <ul className="list-disc list-inside space-y-1">
            <li>支持断点续传，网络中断后重新选择同一文件即可继续。</li>
            <li>前端不再限制视频时长，超长视频可能导致上传或转码时间较长。</li>
            <li>上传完成后，系统将自动进行 AI 拆分处理。</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
