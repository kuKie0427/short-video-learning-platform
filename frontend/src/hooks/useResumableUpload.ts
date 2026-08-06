import { useState, useCallback } from 'react';
import { uploadApi } from '../services/api';

const CHUNK_SIZE = 2 * 1024 * 1024; // 2MB
const MAX_RETRIES = 3;

interface UploadState {
  status: 'idle' | 'compressing' | 'uploading' | 'transcoding' | 'completed' | 'error';
  progress: number;
  currentChunk: number;
  totalChunks: number;
  error: string | null;
  uploadedVideoId: string | null;
}

interface UploadTask {
  uploadId: string;
  uploadUrl: string;
  file: File;
  completedChunks: number[];
}

export const useResumableUpload = () => {
  const [state, setState] = useState<UploadState>({
    status: 'idle',
    progress: 0,
    currentChunk: 0,
    totalChunks: 0,
    error: null,
    uploadedVideoId: null,
  });

  // Local storage key helper
  const getStorageKey = (fileName: string, fileSize: number) => 
    `upload_${fileName}_${fileSize}`;

  // Retry logic wrapper
  const uploadChunkWithRetry = async (
    url: string, 
    uploadId: string, 
    chunkIndex: number, 
    chunk: Blob, 
    retryCount = 0
  ): Promise<void> => {
    try {
      await uploadApi.uploadChunk(url, uploadId, chunkIndex, chunk);
    } catch (error) {
      if (retryCount < MAX_RETRIES) {
        const delay = Math.pow(2, retryCount) * 1000; // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay));
        return uploadChunkWithRetry(url, uploadId, chunkIndex, chunk, retryCount + 1);
      }
      throw error;
    }
  };

  const startUpload = useCallback(async (file: File) => {
    setState(prev => ({ ...prev, status: 'compressing', error: null }));

    try {
      // 1. Duration Check (Mock implementation for web)
      // In a real scenario, use an invisible video element to check duration
      const duration = await new Promise<number>((resolve, reject) => {
        const video = document.createElement('video');
        video.preload = 'metadata';
        video.onloadedmetadata = () => {
          window.URL.revokeObjectURL(video.src);
          resolve(video.duration);
        };
        video.onerror = () => reject(new Error('Invalid video file'));
        video.src = window.URL.createObjectURL(file);
      });

      // 不再在前端拦截或限制视频时长，允许上传任意时长的视频。
      // 注意：后端或审核策略可能对时长有要求。

      // 2. Mock Compression/Processing
      // In web, we might just proceed. In React Native, use ffmpeg-kit here.
      // setState({ ...state, status: 'compressing' });
      // await mockCompression();

      // 3. Resume Check or Init
      const storageKey = getStorageKey(file.name, file.size);
      const savedTaskStr = localStorage.getItem(storageKey);
      let task: UploadTask;
      
      setState(prev => ({ ...prev, status: 'uploading' }));

      if (savedTaskStr) {
        const savedData = JSON.parse(savedTaskStr);
        // Verify if it's the same file roughly
        task = {
          uploadId: savedData.uploadId,
          uploadUrl: savedData.uploadUrl,
          file: file,
          completedChunks: savedData.completedChunks || []
        };
        console.log('Resuming upload...', task);
      } else {
        // Determine video type based on duration (short: ≤3min, long: >3min)
        const videoType = duration <= 180 ? 'short' : 'long';
        
        const initRes = await uploadApi.initUpload({
          file_name: file.name,
          file_size: file.size,
          duration: Math.ceil(duration),
          mime_type: file.type,
          video_type: videoType
        });
        
        task = {
          uploadId: initRes.data.data.upload_id,
          uploadUrl: initRes.data.data.upload_url,
          file: file,
          completedChunks: []
        };
        
        localStorage.setItem(storageKey, JSON.stringify({
          uploadId: task.uploadId,
          uploadUrl: task.uploadUrl,
          completedChunks: []
        }));
      }

      // 4. Chunk Upload Loop
      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      setState(prev => ({ ...prev, totalChunks }));

      for (let i = 0; i < totalChunks; i++) {
        if (task.completedChunks.includes(i)) {
          // Skip completed
          continue;
        }

        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);

        setState(prev => ({ 
          ...prev, 
          currentChunk: i + 1,
          progress: Math.round(((i) / totalChunks) * 100)
        }));

        await uploadChunkWithRetry(task.uploadUrl, task.uploadId, i, chunk);

        // Update local record
        task.completedChunks.push(i);
        localStorage.setItem(storageKey, JSON.stringify({
          uploadId: task.uploadId,
          uploadUrl: task.uploadUrl,
          completedChunks: task.completedChunks
        }));
      }

      // 5. Complete
      setState(prev => ({ ...prev, status: 'transcoding', progress: 100 }));
      const completeRes = await uploadApi.completeUpload({ upload_id: task.uploadId });
      const videoId = completeRes.data?.data?.video_id || null;
      
      // Cleanup
      localStorage.removeItem(storageKey);
      setState(prev => ({ ...prev, status: 'completed', uploadedVideoId: videoId }));

    } catch (err: any) {
      console.error(err);
      setState(prev => ({ 
        ...prev, 
        status: 'error', 
        error: err.message || '上传失败，请重试' 
      }));
    }
  }, []);

  const reset = () => {
    setState({
      status: 'idle',
      progress: 0,
      currentChunk: 0,
      totalChunks: 0,
      error: null,
      uploadedVideoId: null,
    });
  };

  return {
    ...state,
    startUpload,
    reset
  };
};
