"""
测试Mock工具
提供存储服务、短信服务等的Mock实现
"""
import os
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import Mock, MagicMock


class MockStorageService:
    """Mock存储服务（用于测试）"""
    
    def __init__(self):
        self.uploaded_files = {}
        self.base_dir = Path(tempfile.mkdtemp(prefix="test_storage_"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def upload_file(self, file_data: bytes, object_key: str, content_type: str = None) -> str:
        """上传文件"""
        file_path = self.base_dir / object_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        self.uploaded_files[object_key] = {
            'data': file_data,
            'content_type': content_type,
            'path': str(file_path)
        }
        
        return f"/test/uploads/{object_key}"
    
    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """获取预签名URL"""
        return f"/test/uploads/{object_key}?expires={expires_in}"
    
    def delete_file(self, object_key: str) -> bool:
        """删除文件"""
        if object_key in self.uploaded_files:
            file_path = Path(self.uploaded_files[object_key]['path'])
            if file_path.exists():
                file_path.unlink()
            del self.uploaded_files[object_key]
            return True
        return False
    
    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在"""
        return object_key in self.uploaded_files
    
    def cleanup(self):
        """清理测试文件"""
        import shutil
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir, ignore_errors=True)
        self.uploaded_files.clear()


class MockSMSService:
    """Mock短信服务（用于测试）"""
    
    def __init__(self):
        self.sent_messages = []
    
    def send_sms(self, phone: str, code: str) -> bool:
        """发送短信"""
        self.sent_messages.append({
            'phone': phone,
            'code': code,
            'timestamp': os.times()
        })
        return True
    
    def get_last_message(self, phone: Optional[str] = None):
        """获取最后发送的消息"""
        if not self.sent_messages:
            return None
        
        if phone:
            for msg in reversed(self.sent_messages):
                if msg['phone'] == phone:
                    return msg
            return None
        
        return self.sent_messages[-1]
    
    def cleanup(self):
        """清理测试数据"""
        self.sent_messages.clear()


class MockVideoSplitService:
    """Mock视频拆分服务（用于测试）"""
    
    def __init__(self, default_segment_duration: int = 60):
        self.default_segment_duration = default_segment_duration
        self.split_calls = []
    
    def split_video(
        self,
        video_path: str,
        split_mode: str,
        auto_config: Optional[dict] = None
    ) -> list:
        """拆分视频"""
        self.split_calls.append({
            'video_path': video_path,
            'split_mode': split_mode,
            'auto_config': auto_config
        })
        
        # 模拟拆分结果
        total_duration = self.get_video_duration(video_path)
        segments = []
        segment_index = 0
        current_time = 0
        
        segment_duration = (
            auto_config.get('segment_duration', self.default_segment_duration)
            if auto_config else self.default_segment_duration
        )
        
        while current_time < total_duration:
            start_time = current_time
            end_time = min(current_time + segment_duration, total_duration)
            duration = end_time - start_time
            
            segments.append({
                'segment_index': segment_index,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'thumbnail_url': f"/test/thumbnails/segment_{segment_index}.jpg",
                'scene_type': split_mode,
                'confidence': 0.85
            })
            
            segment_index += 1
            current_time = end_time
        
        return segments
    
    def get_video_duration(self, video_path: str) -> int:
        """获取视频时长"""
        # 模拟返回5分钟
        return 300
    
    def cleanup(self):
        """清理测试数据"""
        self.split_calls.clear()


class MockRedis:
    """Mock Redis客户端（用于测试）"""
    
    def __init__(self):
        self.data = {}
        self.expires = {}
    
    def get(self, key: str):
        """获取值"""
        if key in self.expires and self.expires[key] < os.times()[0]:
            del self.data[key]
            del self.expires[key]
            return None
        return self.data.get(key)
    
    def set(self, key: str, value: str):
        """设置值"""
        self.data[key] = value
        return True
    
    def setex(self, key: str, time: int, value: str):
        """设置带过期时间的值"""
        self.data[key] = value
        self.expires[key] = os.times()[0] + time
        return True
    
    def incr(self, key: str):
        """递增"""
        current = int(self.data.get(key, 0))
        new_value = current + 1
        self.data[key] = str(new_value)
        return new_value
    
    def delete(self, *keys):
        """删除键"""
        count = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                count += 1
            if key in self.expires:
                del self.expires[key]
        return count
    
    def exists(self, key: str):
        """检查键是否存在"""
        return 1 if key in self.data else 0
    
    def expire(self, key: str, time: int):
        """设置过期时间"""
        if key in self.data:
            self.expires[key] = os.times()[0] + time
            return True
        return False
    
    def hset(self, key: str, mapping: dict = None, **kwargs):
        """设置哈希字段"""
        if key not in self.data:
            self.data[key] = {}
        
        if isinstance(self.data[key], dict):
            if mapping:
                self.data[key].update(mapping)
            if kwargs:
                self.data[key].update(kwargs)
        else:
            # 如果key已存在但不是dict，转换为dict
            self.data[key] = {}
            if mapping:
                self.data[key].update(mapping)
            if kwargs:
                self.data[key].update(kwargs)
        
        return len(self.data[key])
    
    def hgetall(self, key: str):
        """获取所有哈希字段"""
        if key not in self.data:
            return {}
        value = self.data[key]
        if isinstance(value, dict):
            return value
        return {}
    
    def hincrby(self, key: str, field: str, increment: int = 1):
        """哈希字段递增"""
        if key not in self.data:
            self.data[key] = {}
        
        if not isinstance(self.data[key], dict):
            self.data[key] = {}
        
        current = int(self.data[key].get(field, 0))
        new_value = current + increment
        self.data[key][field] = str(new_value)
        return new_value
    
    def keys(self, pattern: str):
        """获取匹配模式的键"""
        import fnmatch
        matching_keys = []
        for key in self.data.keys():
            # 简单的模式匹配（支持*通配符）
            if fnmatch.fnmatch(key, pattern):
                matching_keys.append(key)
        return matching_keys
    
    def ping(self):
        """Ping Redis"""
        return True
    
    def cleanup(self):
        """清理测试数据"""
        self.data.clear()
        self.expires.clear()


