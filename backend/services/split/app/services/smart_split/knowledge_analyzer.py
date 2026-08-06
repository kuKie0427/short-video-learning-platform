import os
import re
import json
import base64
import logging

logger = logging.getLogger(__name__)

# 依赖检查（zhipuai 为可选依赖：未安装/未配置密钥时自动走降级切分）
try:
    from zhipuai import ZhipuAI
    logger.info(f"✓ zhipuai 导入成功")
except ImportError as e:
    logger.error(f"✗ zhipuai 导入失败，AI 知识点分析将降级为等长切分: {e}")
    ZhipuAI = None

try:
    import cv2
    logger.info(f"✓ opencv 导入成功，版本: {cv2.__version__}")
except ImportError as e:
    logger.warning(f"⚠ opencv 导入失败: {e}")

class KnowledgePointAnalyzer:
    def __init__(self, stt_output_path, image_folder_path, api_key, time_window=30, max_direct_images=8, max_speech_segments=50):
        self.stt_output_path = stt_output_path
        self.image_folder_path = image_folder_path
        # API 密钥为空或 SDK 未安装时不初始化客户端（避免崩溃），分析时自动走降级切分
        self.client = ZhipuAI(api_key=api_key) if (api_key and ZhipuAI) else None
        self.time_window = time_window
        self.max_direct_images = max_direct_images
        self.max_speech_segments = max_speech_segments

    def load_stt_results(self):
        stt_results = []
        try:
            with open(self.stt_output_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        result = json.loads(line.strip())
                        stt_results.append(result)
            logger.info(f"成功加载 {len(stt_results)} 条语音转文字记录")
            return stt_results
        except Exception as e:
            logger.error(f"加载语音转文字结果失败: {e}")
            return []

    def load_image_files(self):
        """加载图片文件，优先从best_keyframes子目录加载"""
        image_files = []
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        
        # 优先检查best_keyframes子目录
        best_keyframes_dir = os.path.join(self.image_folder_path, "best_keyframes")
        search_dir = best_keyframes_dir if os.path.exists(best_keyframes_dir) else self.image_folder_path
        
        if not os.path.exists(search_dir):
            logger.warning(f"截图文件夹不存在: {search_dir}")
            return []
        
        logger.info(f"从目录加载图片: {search_dir}")
        
        for filename in os.listdir(search_dir):
            if any(filename.lower().endswith(ext) for ext in image_extensions):
                time_match = re.match(r'(\d+)m(\d+)s(\d+)_', filename)
                if time_match:
                    minutes = int(time_match.group(1))
                    seconds = int(time_match.group(2))
                    milliseconds = int(time_match.group(3))
                    total_seconds = minutes * 60 + seconds + milliseconds / 1000
                    image_files.append({
                        'filename': filename,
                        'path': os.path.join(search_dir, filename),
                        'timestamp': total_seconds,
                        'minutes': minutes,
                        'seconds': seconds,
                        'milliseconds': milliseconds
                    })
        image_files.sort(key=lambda x: x['timestamp'])
        logger.info(f"成功加载 {len(image_files)} 张截图")
        return image_files

    def encode_image_to_base64(self, image_path):
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"图片编码失败 {image_path}: {e}")
            return None

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"[{minutes:02d}:{secs:02d}]"

    def get_all_speech_content(self, stt_results):
        """获取所有语音内容，按时间顺序组织"""
        sorted_stt = sorted(stt_results, key=lambda x: x.get('start', 0))
        all_speech_content = []
        for i, result in enumerate(sorted_stt):
            start = result.get('start', 0)
            end = result.get('end', 0)
            text = result.get('text', '')
            if text and text.strip():
                mid_time = (start + end) / 2
                all_speech_content.append({
                    'index': i,
                    'start': start,
                    'end': end,
                    'mid_time': mid_time,
                    'text': text
                })
        return all_speech_content

    def select_key_speech_segments(self, all_speech_content):
        """选择关键的语音片段进行分析"""
        if len(all_speech_content) <= self.max_speech_segments:
            return all_speech_content
        logger.info(f"语音片段过多({len(all_speech_content)})，将选择{self.max_speech_segments}个关键片段")
        step = len(all_speech_content) // self.max_speech_segments
        selected_segments = [all_speech_content[i] for i in range(0, len(all_speech_content), max(1, step))]
        selected_segments = selected_segments[:self.max_speech_segments]
        if selected_segments[0]['start'] > 10:
            selected_segments.insert(0, all_speech_content[0])
            selected_segments = selected_segments[:self.max_speech_segments]
        if selected_segments[-1]['end'] < all_speech_content[-1]['end'] - 10:
            selected_segments.append(all_speech_content[-1])
            selected_segments = selected_segments[-self.max_speech_segments:]
        return selected_segments

    def merge_speech_segments(self, speech_segments):
        """合并连续的语音片段，减少片段数量"""
        if not speech_segments or len(speech_segments) <= self.max_speech_segments:
            return speech_segments
        
        merged_segments = []
        current_segment = speech_segments[0].copy()
        
        for i in range(1, len(speech_segments)):
            current = speech_segments[i]
            prev = speech_segments[i-1]
            
            # 如果当前片段与前一片段时间连续且内容相关，则合并
            time_gap = current['start'] - prev['end']
            if time_gap < 3.0:  # 时间间隔小于3秒
                # 合并文本
                current_segment['text'] += " " + current['text']
                current_segment['end'] = current['end']
                current_segment['mid_time'] = (current_segment['start'] + current['end']) / 2
            else:
                # 开始新片段
                merged_segments.append(current_segment)
                current_segment = current.copy()
        
        # 添加最后一个片段
        merged_segments.append(current_segment)
        
        logger.info(f"语音片段合并后数量: {len(merged_segments)}")
        return merged_segments

    def select_key_images(self, image_files, strategy="scoring"):
        """
        智能选择关键图片进行直接发送
        
        Args:
            image_files: 所有图片列表
            strategy: 选择策略，可选 "scoring"（赋分制）
        
        Returns:
            direct_images: 直接发送的图片列表
            text_images: 转为文字描述的图片列表
        """
        if len(image_files) <= self.max_direct_images:
            logger.info(f"图片数量{len(image_files)}未超过限制，全部直接发送")
            return image_files, []
        
        logger.info(f"图片数量{len(image_files)}超过限制，将选择{self.max_direct_images}张关键图片")
        
        # 赋分制选择：时间均匀分布 + 重点时间段
        scores = []
        total_time = image_files[-1]['timestamp'] - image_files[0]['timestamp']
        ideal_interval = total_time / (self.max_direct_images - 1) if self.max_direct_images > 1 else total_time
        
        for i, img in enumerate(image_files):
            # 基础分：时间分布均匀性
            expected_time = image_files[0]['timestamp'] + ideal_interval * (i / (len(image_files)-1))
            time_diff = abs(img['timestamp'] - expected_time)
            time_score = max(0, 1 - time_diff / ideal_interval)
            
            # 额外分：开头和结尾的图片更重要
            position_in_video = (img['timestamp'] - image_files[0]['timestamp']) / total_time
            if position_in_video < 0.1 or position_in_video > 0.9:
                position_score = 0.3
            elif position_in_video < 0.2 or position_in_video > 0.8:
                position_score = 0.15
            else:
                position_score = 0
            
            total_score = time_score + position_score
            scores.append((i, total_score))
        
        # 选择得分最高的图片
        scores.sort(key=lambda x: x[1], reverse=True)
        selected_indices = [idx for idx, _ in scores[:self.max_direct_images]]
        selected_indices.sort()
        direct_images = [image_files[i] for i in selected_indices]
        text_images = [img for i, img in enumerate(image_files) if i not in selected_indices]
        
        logger.info(f"选择了 {len(direct_images)} 张关键图片直接发送")
        return direct_images, text_images

    def describe_images_as_text(self, image_files):
        """将图片信息转为文字描述"""
        if not image_files:
            return "无"
        
        descriptions = []
        for img in image_files:
            time_str = self.format_time(img['timestamp']).replace('[', '').replace(']', '')
            filename = img['filename']
            
            # 从文件名推测图片类型
            if 'slide' in filename.lower():
                type_desc = "幻灯片"
            elif 'diagram' in filename.lower():
                type_desc = "图表"
            elif 'formula' in filename.lower():
                type_desc = "公式"
            else:
                type_desc = "截图"
            
            descriptions.append(f"[{time_str}] {type_desc}: {filename}")
        
        return "、".join(descriptions[:20])  # 最多显示20个描述

    def parse_batch_analysis_result(self, result):
        """解析批量分析结果"""
        knowledge_points = []
        if not result:
            return knowledge_points
        lines = result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            line = line.replace('<|end_of_box|>', '')
            pattern = r'\[(\d{2}):(\d{2})\]-\[(\d{2}):(\d{2})\]\s+(.+)'
            match = re.match(pattern, line)
            if match:
                start_min = int(match.group(1))
                start_sec = int(match.group(2))
                end_min = int(match.group(3))
                end_sec = int(match.group(4))
                content = match.group(5)
                start_time = start_min * 60 + start_sec
                end_time = end_min * 60 + end_sec
                duration = end_time - start_time
                knowledge_points.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration': duration,
                    'content': content,
                    'title': content
                })
        return knowledge_points

    def analyze_knowledge_points(self):
        """使用GLM进行知识点分析（优化版）"""
        logger.info("开始GLM知识点分析...")
        stt_results = self.load_stt_results()
        all_image_files = self.load_image_files()
        
        if not stt_results:
            logger.error("语音数据加载失败")
            return []
        
        # 未配置 GLM API 密钥时，直接走降级切分方案（等长切分）
        if self.client is None:
            logger.warning("未配置 GLM_API_KEY，使用降级切分方案（等长切分）")
            return self._fallback_split(stt_results)
        
        # 获取并优化语音内容
        all_speech_content = self.get_all_speech_content(stt_results)
        key_speech_segments = self.select_key_speech_segments(all_speech_content)
        key_speech_segments = self.merge_speech_segments(key_speech_segments)
        logger.info(f"将分析 {len(key_speech_segments)} 个语音片段")
        
        # 智能选择关键图片
        direct_images, text_images = self.select_key_images(all_image_files, strategy="scoring")
        
        # 构建用户内容
        user_content = []
        
        # 添加总体说明
        user_content.append({
            "type": "text",
            "text": f"""以下是一个教学视频的分析数据：

## 数据概述
1. 语音内容：{len(key_speech_segments)}个关键时间点的语音内容（按时间顺序排列）
2. 直接可视图像：{len(direct_images)}张关键截图（以图片形式提供）
3. 文字描述图像：{len(text_images)}张其他截图（以文字形式描述）

## 重要说明
- 分析应以语音内容为主要依据
- 直接可视图像提供关键视觉参考
- 文字描述图像提供完整的图像时间点信息，帮助理解视频结构

## 图像选择策略
- 直接可视图像：通过赋分制选择的关键图像，覆盖视频的不同时间段
- 文字描述图像：其他所有截图的时间点和文件名信息

请综合分析所有信息，以语音内容为主导，判断知识点边界。"""
        })
        
        # 添加语音片段内容
        user_content.append({
            "type": "text",
            "text": "\n" + "="*20 + "\n## 语音内容分析（主要依据）\n" + "="*20
        })
        
        for i, speech_segment in enumerate(key_speech_segments):
            time_str = self.format_time(speech_segment['mid_time']).replace('[', '').replace(']', '')
            speech_text = speech_segment['text']
            if len(speech_text) > 400:
                speech_text = speech_text[:400] + "..."
            
            user_content.append({
                "type": "text",
                "text": f"\n### 语音片段 {i+1}: [{time_str}]\n**内容**: {speech_text}"
            })
        
        # 添加直接可视图像
        if direct_images:
            user_content.append({
                "type": "text",
                "text": "\n" + "="*60 + f"\n## 直接可视图像（{len(direct_images)}张关键截图）\n" + "="*60
            })
            
            image_count = 0
            for i, image_info in enumerate(direct_images):
                image_base64 = self.encode_image_to_base64(image_info['path'])
                if not image_base64:
                    continue
                
                time_str = self.format_time(image_info['timestamp']).replace('[', '').replace(']', '')
                
                user_content.append({
                    "type": "text",
                    "text": f"\n### 关键图像 {i+1}: [{time_str}] {image_info['filename']}"
                })
                
                user_content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                })
                image_count += 1
        
        # 添加文字描述图像
        if text_images:
            user_content.append({
                "type": "text",
                "text": "\n" + "="*60 + f"\n## 文字描述图像（{len(text_images)}张其他截图）\n" + "="*60
            })
            
            image_descriptions = self.describe_images_as_text(text_images)
            user_content.append({
                "type": "text",
                "text": f"\n**其他截图时间点**: {image_descriptions}\n\n"
            })
        
        # 添加最后的分析要求
        user_content.append({
            "type": "text",
            "text": """\n\n## 分析要求
请根据以上所有信息，以语音内容为主要依据，综合分析整个视频各个时间段的具体知识点。

### 重要提示
1. 语音内容是知识点判断的主要依据
2. 直接可视图像提供关键视觉参考
3. 文字描述图像提供完整的时间点信息，帮助理解视频结构

### 输出格式
必须严格按照以下示例：
[00:00]-[03:22] 极限的定义
[03:23]-[07:45] 极限的计算方法
[07:46]-[12:30] 导数的概念

### 重要规则
1. 每个知识点时长应在30秒到5分钟之间
2. 知识点标题要简洁明确，不要包含"知识点："前缀
3. 当语音内容开始新主题时，应开始新知识点（主要依据）
4. 图像内容变化作为辅助参考
5. 确保输出的每一行都是"[开始时间]-[结束时间] 知识点标题"的格式
6. 不要输出任何解释或额外文字，只输出知识点分割行
7. 确保时间格式严格为[MM:SS]，分钟和秒都是两位数
8. 相邻且高度相关的知识点可以合并成同一段时间的知识点（非常重要）
9. 请综合考虑所有图像时间点信息，确保知识点覆盖完整视频

请直接输出知识点分割行，不要任何解释。"""
        })
        
        # 统一使用 GLM-4V 模型
        model = "glm-4.5v"
        
        # glm-4v 多模态API使用user-only消息格式（系统指令已包含在user content中）
        messages = [
            {
                "role": "user",
                "content": user_content
            }
        ]
        
        try:
            logger.info(f"调用GLM进行知识点分析（模型: {model}）...")
            logger.info(f"发送的图片数量: {len(direct_images)}, 语音片段数量: {len(key_speech_segments)}")
            
            # 打印 user_content 的结构以便调试
            content_summary = []
            for item in user_content:
                if item['type'] == 'text':
                    content_summary.append(f"text({len(item['text'])} chars)")
                elif item['type'] == 'image_url':
                    content_summary.append("image")
            logger.info(f"User content 结构: {', '.join(content_summary)}")
            
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=5000
            )
            analysis_result = response.choices[0].message.content
            logger.info(f"GLM返回结果长度: {len(analysis_result)} 字符")
            logger.info(f"GLM返回结果:\n{analysis_result}")
            knowledge_points = self.parse_batch_analysis_result(analysis_result)
            logger.info(f"解析出 {len(knowledge_points)} 个知识点")
            
            if knowledge_points:
                return knowledge_points
            else:
                logger.warning("GLM返回结果为空，使用回退方案")
                logger.warning(f"原始GLM返回: {analysis_result[:500]}")
                return self._fallback_split(stt_results)
                
        except ImportError as e:
            logger.error(f"导入错误 - 可能缺少依赖包: {e}", exc_info=True)
            logger.error("请检查 zhipuai 包是否已安装")
            return self._fallback_split(stt_results)
        except AttributeError as e:
            logger.error(f"属性错误 - API调用格式可能不正确: {e}", exc_info=True)
            return self._fallback_split(stt_results)
        except Exception as e:
            logger.error(f"GLM分析失败 - 错误类型: {type(e).__name__}", exc_info=True)
            logger.error(f"错误详情: {str(e)}")
            # 尝试获取更多错误信息
            if hasattr(e, 'response'):
                logger.error(f"API响应: {e.response}")
            if hasattr(e, 'status_code'):
                logger.error(f"状态码: {e.status_code}")
            return self._fallback_split(stt_results)
    
    def _fallback_split(self, stt_results):
        """回退方案：简单时间切分"""
        logger.info("使用回退方案进行简单切分")
        if not stt_results:
            return []
        total_duration = max([r.get('end', 0) for r in stt_results])
        segment_duration = 60
        segments = []
        current_time = 0
        index = 0
        while current_time < total_duration:
            end_time = min(current_time + segment_duration, total_duration)
            segments.append({
                'start_time': current_time,
                'end_time': end_time,
                'duration': end_time - current_time,
                'content': f'片段{index + 1}',
                'title': f'片段{index + 1}'
            })
            current_time = end_time
            index += 1
        return segments
