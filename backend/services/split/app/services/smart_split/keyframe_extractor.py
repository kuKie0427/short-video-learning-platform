import os
import shutil

# 重型 AI 依赖为可选：未安装时导入不失败，实例化时给出明确错误
try:
    import cv2
    import numpy as np
    from skimage.metrics import structural_similarity as ssim
except ImportError as e:
    cv2 = None
    np = None
    ssim = None
    _AI_DEPS_ERROR = f"缺少 AI 依赖(opencv-python/scikit-image): {e}"
else:
    _AI_DEPS_ERROR = None

class KeyframeExtractor:
    def __init__(self, video_path, output_dir='output_keyframes', interval=1, threshold=0.3, strategy='all', weight_neighbor=0.4, weight_ssim=0.6):
        if cv2 is None:
            raise ImportError(_AI_DEPS_ERROR)
        self.video_path = video_path
        self.output_dir = output_dir
        self.interval_seconds = interval
        self.threshold = threshold
        self.strategy = strategy
        self.weight_neighbor = weight_neighbor
        self.weight_ssim = weight_ssim
        self.keyframe_counter = 0
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"无法打开视频文件: {video_path}")
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.sampled_frames = []
        self.frame_indices = []
        self.frame_times = []
    
    def __del__(self):
        """析构函数：释放视频资源"""
        if hasattr(self, 'cap') and self.cap is not None and self.cap.isOpened():
            self.cap.release()
    
    def close(self):
        """手动关闭视频流"""
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()

    def preprocess_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
        return blurred

    def extract_roi(self, frame):
        if len(frame.shape) == 3:
            h, w = frame.shape[:2]
        else:
            h, w = frame.shape
        roi_height = int(h * 0.7)
        roi_width = int(w * 0.8)
        start_y = int(h * 0.15)
        start_x = int(w * 0.1)
        return frame[start_y:start_y+roi_height, start_x:start_x+roi_width]

    def calculate_neighbor_change(self, img1, img2):
        if img1 is None or img2 is None:
            return 0
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray1, gray2)
        height, width = gray1.shape
        total_pixels = height * width
        changed_pixels = np.sum(diff > 30)
        change_percentage = changed_pixels / total_pixels
        return change_percentage

    def calculate_ssim_change(self, img1, img2):
        processed1 = self.preprocess_frame(img1)
        processed2 = self.preprocess_frame(img2)
        roi1 = self.extract_roi(processed1)
        roi2 = self.extract_roi(processed2)
        if roi1.shape != roi2.shape:
            h = min(roi1.shape[0], roi2.shape[0])
            w = min(roi1.shape[1], roi2.shape[1])
            roi1 = cv2.resize(roi1, (w, h))
            roi2 = cv2.resize(roi2, (w, h))
        score, _ = ssim(roi1, roi2, full=True)
        change_score = 1 - score
        contrast1 = np.std(roi1)
        contrast2 = np.std(roi2)
        contrast_change = abs(contrast1 - contrast2) / 255.0
        combined_score = 0.7 * change_score + 0.3 * contrast_change
        return combined_score

    def sample_frames(self):
        """按3秒间隔采样视频帧"""
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        
        # 计算采样间隔(帧数)
        interval_frames = int(self.fps * self.interval_seconds)
        if interval_frames == 0:
            interval_frames = 1
        
        # 采样第一秒的帧
        first_second_frame = min(int(self.fps * 1), self.total_frames - 1)
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, first_second_frame)
        ret, frame = self.cap.read()
        if ret:
            self.sampled_frames.append(frame)
            self.frame_indices.append(first_second_frame)
            self.frame_times.append(first_second_frame / self.fps)
        
        # 重置到开始，按间隔采样
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        current_frame = 0
        while current_frame < self.total_frames:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
            ret, frame = self.cap.read()
            if ret:
                frame_time = current_frame / self.fps if self.fps > 0 else 0
                # 避免重复添加（修复）
                if current_frame not in self.frame_indices:
                    self.sampled_frames.append(frame)
                    self.frame_indices.append(current_frame)
                    self.frame_times.append(frame_time)
            else:
                break
            current_frame += interval_frames
        
        # 采样最后一秒的帧
        last_second_frame = max(0, int(self.fps * (self.duration - 1)))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, last_second_frame)
        ret, frame = self.cap.read()
        if ret and last_second_frame not in self.frame_indices:
            self.sampled_frames.append(frame)
            self.frame_indices.append(last_second_frame)
            self.frame_times.append(self.duration - 1)

    def format_timestamp(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds - int(seconds)) * 1000)
        return f"{minutes:02d}m{secs:02d}s{millisecs:03d}"

    def save_keyframe(self, frame, timestamp, change_score=None):
        time_str = self.format_timestamp(timestamp)
        self.keyframe_counter += 1
        if change_score is not None:
            filename = f"{time_str}_{self.keyframe_counter:04d}_change{change_score:.3f}.jpg"
        else:
            filename = f"{time_str}_{self.keyframe_counter:04d}.jpg"
        filepath = os.path.join(self.output_dir, filename)
        cv2.imwrite(filepath, frame)
        return filepath

    def calculate_combined_change(self, current_frame, prev_frame=None, reference_frame=None):
        """组合策略：结合相邻帧和参考帧的变化检测"""
        if prev_frame is None or reference_frame is None:
            return 0
        neighbor_change = self.calculate_neighbor_change(prev_frame, current_frame)
        ssim_change = self.calculate_ssim_change(reference_frame, current_frame)
        combined_change = (self.weight_neighbor * neighbor_change + 
                          self.weight_ssim * ssim_change)
        return combined_change

    def extract_using_neighbor_strategy(self):
        """策略1：基于相邻帧变化提取关键帧"""
        keyframes = []
        if len(self.sampled_frames) < 2:
            return keyframes
        
        # 保存第一帧
        first_time = self.frame_times[0]
        filepath = self.save_keyframe(self.sampled_frames[0], first_time)
        keyframes.append({
            'path': filepath,
            'timestamp': first_time,
            'strategy': 'neighbor',
            'change_score': 0
        })
        
        # 检测相邻帧变化
        for i in range(len(self.sampled_frames) - 1):
            change = self.calculate_neighbor_change(self.sampled_frames[i], self.sampled_frames[i + 1])
            if change > self.threshold:
                frame_time = self.frame_times[i]
                filepath = self.save_keyframe(self.sampled_frames[i], frame_time, change)
                keyframes.append({
                    'path': filepath,
                    'timestamp': frame_time,
                    'strategy': 'neighbor',
                    'change_score': change
                })
        
        # 保存最后一帧
        last_time = self.frame_times[-1]
        filepath = self.save_keyframe(self.sampled_frames[-1], last_time)
        keyframes.append({
            'path': filepath,
            'timestamp': last_time,
            'strategy': 'neighbor',
            'change_score': 0
        })
        
        return keyframes

    def extract_using_reference_strategy(self):
        """策略2：基于参考帧SSIM变化提取关键帧"""
        keyframes = []
        if len(self.sampled_frames) < 2:
            return keyframes
        
        # 设置初始参考帧
        reference_frame = self.sampled_frames[0]
        reference_time = self.frame_times[0]
        
        # 保存第一帧
        filepath = self.save_keyframe(reference_frame, reference_time)
        keyframes.append({
            'path': filepath,
            'timestamp': reference_time,
            'strategy': 'reference',
            'change_score': 0
        })
        
        # 检测与参考帧的变化
        for i in range(1, len(self.sampled_frames)):
            current_frame = self.sampled_frames[i]
            current_time = self.frame_times[i]
            change = self.calculate_ssim_change(reference_frame, current_frame)
            
            if change > self.threshold:
                filepath = self.save_keyframe(current_frame, current_time, change)
                keyframes.append({
                    'path': filepath,
                    'timestamp': current_time,
                    'strategy': 'reference',
                    'change_score': change
                })
                # 更新参考帧
                reference_frame = current_frame
                reference_time = current_time
        
        return keyframes

    def extract_using_combined_strategy(self):
        """策略3：组合相邻帧和参考帧策略"""
        keyframes = []
        if len(self.sampled_frames) < 2:
            return keyframes
        
        # 保存第一帧
        first_time = self.frame_times[0]
        filepath = self.save_keyframe(self.sampled_frames[0], first_time)
        keyframes.append({
            'path': filepath,
            'timestamp': first_time,
            'strategy': 'combined',
            'change_score': 0
        })
        
        # 设置初始参考帧和前一帧
        reference_frame = self.sampled_frames[0]
        prev_frame = self.sampled_frames[0]
        
        # 检测组合变化
        for i in range(1, len(self.sampled_frames)):
            current_frame = self.sampled_frames[i]
            current_time = self.frame_times[i]
            
            change = self.calculate_combined_change(
                current_frame, prev_frame, reference_frame
            )
            
            if change > self.threshold:
                filepath = self.save_keyframe(current_frame, current_time, change)
                keyframes.append({
                    'path': filepath,
                    'timestamp': current_time,
                    'strategy': 'combined',
                    'change_score': change
                })
                # 更新参考帧
                reference_frame = current_frame
            
            # 更新前一帧
            prev_frame = current_frame
        
        # 确保保存最后一帧
        last_time = self.frame_times[-1]
        if not keyframes or keyframes[-1]['timestamp'] != last_time:
            filepath = self.save_keyframe(self.sampled_frames[-1], last_time)
            keyframes.append({
                'path': filepath,
                'timestamp': last_time,
                'strategy': 'combined',
                'change_score': 0
            })
        
        return keyframes

    def _select_top_keyframes(self, keyframes, max_count):
        """智能选择最重要的关键帧
        
        策略：
        1. 时间均匀分布（确保视频全程都有覆盖）
        2. 优先选择变化分数高的帧
        3. 始终保留第一帧和最后一帧
        """
        if len(keyframes) <= max_count:
            return keyframes
        
        # 始终保留第一帧和最后一帧
        selected = [keyframes[0], keyframes[-1]]
        remaining_slots = max_count - 2
        
        if remaining_slots <= 0:
            return selected
        
        # 计算理想的时间间隔
        total_duration = keyframes[-1]['timestamp'] - keyframes[0]['timestamp']
        ideal_interval = total_duration / (max_count - 1) if max_count > 1 else total_duration
        
        # 为中间的关键帧打分
        candidates = []
        for i in range(1, len(keyframes) - 1):
            kf = keyframes[i]
            
            # 分数1：变化分数（0-1）
            score_change = min(kf['change_score'], 1.0)
            
            # 分数2：时间分布均匀性（0-1）
            expected_position = keyframes[0]['timestamp']
            min_distance = float('inf')
            for j in range(max_count):
                expected_time = keyframes[0]['timestamp'] + ideal_interval * j
                distance = abs(kf['timestamp'] - expected_time)
                min_distance = min(min_distance, distance)
            score_distribution = max(0, 1 - min_distance / ideal_interval)
            
            # 综合分数：变化分数40% + 分布均匀性60%
            total_score = score_change * 0.4 + score_distribution * 0.6
            
            candidates.append({
                'keyframe': kf,
                'score': total_score
            })
        
        # 按分数排序并选择前N个
        candidates.sort(key=lambda x: x['score'], reverse=True)
        for candidate in candidates[:remaining_slots]:
            selected.append(candidate['keyframe'])
        
        # 按时间戳重新排序
        selected.sort(key=lambda x: x['timestamp'])
        
        return selected

    def merge_and_select_best_keyframes(self, neighbor_keyframes, reference_keyframes, max_keyframes=8):
        """合并并选择最佳关键帧（优化文件IO，限制数量）"""
        # 合并所有关键帧
        all_keyframes = neighbor_keyframes + reference_keyframes
        
        # 按时间戳分组（0.1秒精度）
        time_groups = {}
        for kf in all_keyframes:
            time_key = round(kf['timestamp'], 1)
            if time_key not in time_groups:
                time_groups[time_key] = []
            time_groups[time_key].append(kf)
        
        # 选择每组中变化分数最高的关键帧
        best_keyframes = []
        for time_key, frames in time_groups.items():
            if len(frames) == 1:
                best_keyframes.append(frames[0])
            else:
                best_frame = max(frames, key=lambda x: x['change_score'])
                best_keyframes.append(best_frame)
        
        # 按时间戳排序
        best_keyframes.sort(key=lambda x: x['timestamp'])
        
        # 智能选择最重要的 max_keyframes 张关键帧
        if len(best_keyframes) > max_keyframes:
            selected_keyframes = self._select_top_keyframes(best_keyframes, max_keyframes)
        else:
            selected_keyframes = best_keyframes
        
        # 创建best_keyframes子目录
        best_output_dir = os.path.join(self.output_dir, "best_keyframes")
        if not os.path.exists(best_output_dir):
            os.makedirs(best_output_dir)
        
        # 复制最佳关键帧到best_keyframes目录（优化：使用文件复制而非重新编码）
        final_keyframes = []
        for i, kf in enumerate(selected_keyframes):
            old_path = kf['path']
            
            if os.path.exists(old_path):
                # 生成新文件名
                time_str = self.format_timestamp(kf['timestamp'])
                new_filename = f"{time_str}_{i+1:04d}_best.jpg"
                new_path = os.path.join(best_output_dir, new_filename)
                
                # 使用文件复制（避免重新编码，保持原始质量）
                try:
                    shutil.copy2(old_path, new_path)
                    final_keyframes.append({
                        'path': new_path,
                        'timestamp': kf['timestamp'],
                        'strategy': kf['strategy'],
                        'change_score': kf['change_score']
                    })
                except Exception as e:
                    # 如果复制失败，回退到读取-写入方式
                    frame = cv2.imread(old_path)
                    if frame is not None:
                        cv2.imwrite(new_path, frame)
                        final_keyframes.append({
                            'path': new_path,
                            'timestamp': kf['timestamp'],
                            'strategy': kf['strategy'],
                            'change_score': kf['change_score']
                        })
        
        return final_keyframes

    def run(self):
        """运行关键帧提取（优化版）"""
        try:
            self.sample_frames()
            
            # 根据策略提取关键帧
            if self.strategy == 'neighbor':
                keyframes = self.extract_using_neighbor_strategy()
            elif self.strategy == 'reference':
                keyframes = self.extract_using_reference_strategy()
            elif self.strategy == 'combined':
                keyframes = self.extract_using_combined_strategy()
            else:
                # 默认使用'all'策略：运行两种策略并选择最佳
                neighbor_keyframes = self.extract_using_neighbor_strategy()
                self.keyframe_counter = 0
                reference_keyframes = self.extract_using_reference_strategy()
                keyframes = self.merge_and_select_best_keyframes(neighbor_keyframes, reference_keyframes)
            
            return keyframes
        finally:
            # 确保资源被释放
            self.close()

    def extract_all_sampled_frames(self):
        """提取所有采样帧作为关键帧（备用方法）"""
        keyframes = []
        for i, frame in enumerate(self.sampled_frames):
            if i < len(self.frame_times):
                timestamp = self.frame_times[i]
                filepath = self.save_keyframe(frame, timestamp)
                keyframes.append({
                    'path': filepath,
                    'timestamp': timestamp,
                    'strategy': 'all_frames',
                    'change_score': 0
                })
        return keyframes
