"""
Redis工具模块
提供验证码存储等Redis操作
"""
import logging
import time
from typing import Optional, Dict
from datetime import timedelta
from ..database.connection import get_redis
from ..config.settings import settings

# 内存存储（仅测试环境使用，当Redis不可用时作为fallback）
_memory_store: Dict[str, Dict] = {}


def _cleanup_expired():
    """清理过期的内存存储"""
    current_time = time.time()
    expired_keys = [k for k, v in _memory_store.items() 
                    if 'expire_at' in v and v['expire_at'] < current_time]
    for key in expired_keys:
        del _memory_store[key]


def store_sms_code(phone: str, code: str, expire_seconds: Optional[int] = None) -> bool:
    """存储短信验证码到Redis，失败时使用内存存储"""
    expire = expire_seconds or settings.SMS_CODE_EXPIRE_SECONDS
    
    try:
        redis_client = get_redis()
        if redis_client is None:
            # Fallback到内存存储
            _memory_store[f"sms_code:{phone}"] = {
                "code": code,
                "attempts": "0",  # Redis hgetall返回字符串
                "expire_at": time.time() + expire
            }
            logging.warning(f"Redis unavailable, using memory store for SMS code")
            return True
        
        key = f"sms_code:{phone}"
        
        # 存储验证码和尝试次数
        data = {
            "code": code,
            "attempts": 0
        }
        
        # 使用hash存储，设置过期时间
        redis_client.hset(key, mapping=data)
        redis_client.expire(key, expire)
        
        return True
    except Exception as e:
        logging.error(f"Failed to store SMS code in Redis: {e}")
        # Fallback到内存存储
        _memory_store[f"sms_code:{phone}"] = {
            "code": code,
            "attempts": "0",
            "expire_at": time.time() + expire
        }
        logging.warning(f"Using memory store as fallback for SMS code")
        return True


def get_sms_code(phone: str) -> Optional[dict]:
    """从Redis获取短信验证码，失败时从内存获取"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            # 从内存获取
            _cleanup_expired()
            key = f"sms_code:{phone}"
            data = _memory_store.get(key)
            if data:
                return {
                    "code": data.get("code"),
                    "attempts": int(data.get("attempts", 0))
                }
            return None
        
        key = f"sms_code:{phone}"
        data = redis_client.hgetall(key)
        
        if not data:
            return None
        
        return {
            "code": data.get("code"),
            "attempts": int(data.get("attempts", 0))
        }
    except Exception as e:
        logging.error(f"Failed to get SMS code from Redis: {e}")
        # Fallback到内存
        _cleanup_expired()
        key = f"sms_code:{phone}"
        data = _memory_store.get(key)
        if data:
            return {
                "code": data.get("code"),
                "attempts": int(data.get("attempts", 0))
            }
        return None


def increment_sms_code_attempts(phone: str) -> Optional[int]:
    """增加验证码尝试次数"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            # 从内存增加
            key = f"sms_code:{phone}"
            if key in _memory_store:
                current = int(_memory_store[key].get("attempts", 0))
                _memory_store[key]["attempts"] = str(current + 1)
                return current + 1
            return None
        
        key = f"sms_code:{phone}"
        attempts = redis_client.hincrby(key, "attempts", 1)
        return attempts
    except Exception as e:
        logging.error(f"Failed to increment SMS code attempts: {e}")
        # Fallback到内存
        key = f"sms_code:{phone}"
        if key in _memory_store:
            current = int(_memory_store[key].get("attempts", 0))
            _memory_store[key]["attempts"] = str(current + 1)
            return current + 1
        return None


def delete_sms_code(phone: str) -> bool:
    """删除短信验证码"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            # 从内存删除
            key = f"sms_code:{phone}"
            if key in _memory_store:
                del _memory_store[key]
            return True
        
        key = f"sms_code:{phone}"
        redis_client.delete(key)
        return True
    except Exception as e:
        logging.error(f"Failed to delete SMS code from Redis: {e}")
        # Fallback到内存
        key = f"sms_code:{phone}"
        if key in _memory_store:
            del _memory_store[key]
        return True


def check_sms_code_exists(phone: str) -> bool:
    """检查验证码是否存在"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            # 从内存检查
            _cleanup_expired()
            key = f"sms_code:{phone}"
            return key in _memory_store
        
        key = f"sms_code:{phone}"
        return redis_client.exists(key) > 0
    except Exception as e:
        logging.error(f"Failed to check SMS code existence: {e}")
        # Fallback到内存
        _cleanup_expired()
        key = f"sms_code:{phone}"
        return key in _memory_store


def get_recommendation_cache(user_id: str, algorithm: str) -> Optional[list]:
    """获取推荐结果缓存"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            return None
        
        # 处理匿名用户
        cache_user_id = user_id or "anonymous"
        key = f"recommend:user:{cache_user_id}:{algorithm}"
        cached_data = redis_client.get(key)
        
        if cached_data:
            import json
            return json.loads(cached_data)
        return None
    except Exception as e:
        logging.error(f"Failed to get recommendation cache from Redis: {e}")
        return None


def set_recommendation_cache(user_id: str, algorithm: str, video_ids: list, expire_seconds: int = 3600) -> bool:
    """设置推荐结果缓存"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            return False
        
        # 处理匿名用户
        cache_user_id = user_id or "anonymous"
        key = f"recommend:user:{cache_user_id}:{algorithm}"
        import json
        redis_client.setex(key, expire_seconds, json.dumps(video_ids))
        return True
    except Exception as e:
        logging.error(f"Failed to set recommendation cache in Redis: {e}")
        return False


def invalidate_recommendation_cache(user_id: str, algorithm: Optional[str] = None) -> bool:
    """使推荐缓存失效"""
    try:
        redis_client = get_redis()
        if redis_client is None:
            return False
        
        # 处理匿名用户
        cache_user_id = user_id or "anonymous"
        
        if algorithm:
            # 清除特定算法的缓存
            key = f"recommend:user:{cache_user_id}:{algorithm}"
            redis_client.delete(key)
        else:
            # 清除该用户的所有推荐缓存
            pattern = f"recommend:user:{cache_user_id}:*"
            keys = redis_client.keys(pattern)
            if keys:
                redis_client.delete(*keys)
        return True
    except Exception as e:
        logging.error(f"Failed to invalidate recommendation cache in Redis: {e}")
        return False

