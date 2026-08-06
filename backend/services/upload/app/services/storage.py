"""
存储服务抽象层
支持本地存储和对象存储（S3/MinIO）
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, BinaryIO
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class StorageServiceInterface(ABC):
    """存储服务接口"""
    
    @abstractmethod
    def upload_file(self, file_data: bytes, object_key: str, content_type: str = None) -> str:
        """上传文件
        
        Args:
            file_data: 文件数据
            object_key: 对象键（文件路径）
            content_type: 内容类型
            
        Returns:
            文件URL
        """
        pass
    
    @abstractmethod
    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """获取预签名URL
        
        Args:
            object_key: 对象键
            expires_in: 过期时间（秒）
            
        Returns:
            预签名URL
        """
        pass
    
    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        """删除文件
        
        Args:
            object_key: 对象键
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在
        
        Args:
            object_key: 对象键
            
        Returns:
            是否存在
        """
        pass


class LocalStorageService(StorageServiceInterface):
    """本地存储服务（开发环境）"""
    
    def __init__(self, base_dir: str = "uploads"):
        """初始化本地存储服务
        
        Args:
            base_dir: 基础目录
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"使用本地存储服务，基础目录: {self.base_dir}")
    
    def upload_file(self, file_data: bytes, object_key: str, content_type: str = None) -> str:
        """上传文件到本地存储"""
        file_path = self.base_dir / object_key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        # 返回相对URL
        return f"/uploads/{object_key}"
    
    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """获取本地文件URL（本地存储不需要预签名）"""
        return f"/uploads/{object_key}"
    
    def delete_file(self, object_key: str) -> bool:
        """删除本地文件"""
        file_path = self.base_dir / object_key
        if file_path.exists():
            file_path.unlink()
            return True
        return False
    
    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在"""
        file_path = self.base_dir / object_key
        return file_path.exists()


class S3StorageService(StorageServiceInterface):
    """S3兼容对象存储服务（MinIO/AWS S3）"""
    
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
        region: str = None,
        use_ssl: bool = False
    ):
        """初始化S3存储服务
        
        Args:
            endpoint: S3端点URL
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket_name: 存储桶名称
            region: 区域（可选）
            use_ssl: 是否使用SSL
        """
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            logger.error("boto3未安装，无法使用S3存储服务")
            raise ImportError("请安装boto3: pip install boto3")
        
        self.bucket_name = bucket_name
        self.endpoint = endpoint
        
        # 配置S3客户端
        config = Config(signature_version='s3v4')
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or 'us-east-1',
            use_ssl=use_ssl,
            config=config
        )
        
        # 确保存储桶存在
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
        except:
            try:
                self.s3_client.create_bucket(Bucket=bucket_name)
            except Exception as e:
                logger.warning(f"无法创建存储桶 {bucket_name}: {e}")
        
        logger.info(f"使用S3存储服务，端点: {endpoint}, 存储桶: {bucket_name}")
    
    def upload_file(self, file_data: bytes, object_key: str, content_type: str = None) -> str:
        """上传文件到S3"""
        extra_args = {}
        if content_type:
            extra_args['ContentType'] = content_type
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=object_key,
            Body=file_data,
            **extra_args
        )
        
        # 返回文件URL
        if self.endpoint.startswith('http'):
            return f"{self.endpoint}/{self.bucket_name}/{object_key}"
        else:
            return f"https://{self.endpoint}/{self.bucket_name}/{object_key}"
    
    def get_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """获取预签名URL"""
        return self.s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': self.bucket_name, 'Key': object_key},
            ExpiresIn=expires_in
        )
    
    def delete_file(self, object_key: str) -> bool:
        """删除S3文件"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False
    
    def file_exists(self, object_key: str) -> bool:
        """检查文件是否存在"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except:
            return False


def get_storage_service() -> StorageServiceInterface:
    """获取存储服务实例（工厂函数）"""
    storage_type = os.getenv("STORAGE_TYPE", "local").lower()
    
    if storage_type == "s3":
        # 使用S3存储
        endpoint = os.getenv("S3_ENDPOINT", "http://localhost:9000")
        access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("S3_SECRET_KEY", "minioadmin123")
        bucket_name = os.getenv("S3_BUCKET", "videos")
        region = os.getenv("S3_REGION")
        use_ssl = os.getenv("S3_USE_SSL", "false").lower() == "true"
        
        return S3StorageService(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket_name,
            region=region,
            use_ssl=use_ssl
        )
    else:
        # 默认使用本地存储
        base_dir = os.getenv("UPLOAD_BASE_DIR", "/app/data/uploads")
        return LocalStorageService(base_dir=base_dir)


def calculate_file_hash(file_data: bytes) -> str:
    """计算文件MD5哈希值
    
    Args:
        file_data: 文件数据
        
    Returns:
        MD5哈希值（十六进制字符串）
    """
    return hashlib.md5(file_data).hexdigest()

