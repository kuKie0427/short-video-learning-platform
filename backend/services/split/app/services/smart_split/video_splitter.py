import os
import re
import subprocess

class VideoSplitter:
    def __init__(self, video_path, knowledge_file, output_dir="./output_splited_videos"):
        self.video_path = video_path
        self.knowledge_file = knowledge_file
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def parse_knowledge_points(self):
        """解析知识点文件"""
        knowledge_points = []
        if not os.path.exists(self.knowledge_file):
            return knowledge_points
        
        formats = [
            r'\s*\d+\.\s*\[(\d{2}:\d{2})\]-\[(\d{2}:\d{2})\]\s+(.+)',
            r'\s*\[(\d{2}:\d{2})\]-\[(\d{2}:\d{2})\]\s+(.+)',
            r'\s*\d+\.\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+)',
            r'\s*(\d{2}:\d{2})-(\d{2}:\d{2})\s+(.+)',
        ]
        
        with open(self.knowledge_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            matched = False
            for fmt in formats:
                match = re.match(fmt, line)
                if match:
                    start_time_str = match.group(1)
                    end_time_str = match.group(2)
                    title = match.group(3).strip()
                    
                    try:
                        start_time = self.parse_time_to_seconds(start_time_str)
                        end_time = self.parse_time_to_seconds(end_time_str)
                        
                        if end_time <= start_time:
                            continue
                        
                        knowledge_points.append({
                            'index': len(knowledge_points) + 1,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration': end_time - start_time,
                            'title': title
                        })
                        matched = True
                        break
                    except ValueError:
                        continue
            
            if not matched:
                print(f"无法识别格式: {line}")
        
        return knowledge_points

    def parse_time_to_seconds(self, time_str):
        """将时间字符串转换为秒数"""
        parts = time_str.split(':')
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        else:
            raise ValueError(f"无法解析的时间格式: {time_str}")

    def split_video(self, knowledge_points, method='copy'):
        """根据知识点分割视频"""
        video_files = []
        
        for i, point in enumerate(knowledge_points):
            start_time = point['start_time']
            end_time = point['end_time']
            title = point['title']
            
            # 生成安全的文件名
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            safe_title = re.sub(r'\s+', '_', safe_title)
            safe_title = safe_title[:50]
            
            filename = f"{i+1:03d}_{safe_title}.mp4"
            output_path = os.path.join(self.output_dir, filename)
            
            # 使用ffmpeg分割
            if method == 'copy':
                cmd = [
                    'ffmpeg',
                    '-i', self.video_path,
                    '-ss', str(start_time),
                    '-to', str(end_time),
                    '-c', 'copy',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    output_path
                ]
            else:
                cmd = [
                    'ffmpeg',
                    '-i', self.video_path,
                    '-ss', str(start_time),
                    '-to', str(end_time),
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-y',
                    output_path
                ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
                if result.returncode == 0:
                    if os.path.exists(output_path):
                        size_mb = os.path.getsize(output_path) / (1024 * 1024)
                        video_files.append({
                            'path': output_path,
                            'filename': filename,
                            'knowledge_point': point,
                            'size_mb': size_mb
                        })
            except Exception as e:
                print(f"分割失败: {e}")
        
        return video_files
