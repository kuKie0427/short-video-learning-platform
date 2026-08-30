"""
配置管理模块
使用pydantic-settings进行配置验证和管理
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict, field_validator


def get_env_file_path() -> Optional[str]:
    """获取.env文件路径，如果文件不存在或无法读取则返回None"""
    env_file = ".env"
    if os.path.exists(env_file) and os.access(env_file, os.R_OK):
        return env_file
    return None


class Settings(BaseSettings):
    """应用配置"""
    
    # 环境配置
    ENVIRONMENT: str = Field(default="development", description="运行环境: development, production")
    
    # JWT配置（支持JWT_SECRET和JWT_SECRET_KEY两种环境变量名）
    JWT_SECRET_KEY: Optional[str] = Field(default=None, description="JWT密钥")
    JWT_SECRET: Optional[str] = Field(default=None, description="JWT密钥（别名）")
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT算法")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, description="JWT过期时间（分钟）")
    
    # CORS配置
    CORS_ORIGINS: str = Field(default="*", description="CORS允许的来源，多个用逗号分隔")
    
    # 数据库配置
    DATABASE_URL: Optional[str] = Field(default=None, description="数据库连接URL")
    DB_HOST: str = Field(default="postgres", description="数据库主机")
    DB_PORT: str = Field(default="5432", description="数据库端口")
    DB_NAME: str = Field(default="short_video_platform", description="数据库名称")
    DB_USER: str = Field(default="app_user", description="数据库用户")
    DB_PASSWORD: str = Field(default="app_password_2025", description="数据库密码")
    
    # Redis配置
    REDIS_HOST: str = Field(default="localhost", description="Redis主机")
    REDIS_PORT: int = Field(default=6379, description="Redis端口")
    REDIS_DB: int = Field(default=0, description="Redis数据库编号")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis密码")
    REDIS_URL: Optional[str] = Field(default=None, description="Redis连接URL（如果提供则优先使用）")
    
    # Kafka配置
    KAFKA_BOOTSTRAP_SERVERS: str = Field(default="localhost:9092", description="Kafka服务器地址")
    KAFKA_CLIENT_ID: str = Field(default="short_video_platform", description="Kafka客户端ID")
    
    # 短信验证码配置
    SMS_CODE_EXPIRE_SECONDS: int = Field(default=300, description="短信验证码过期时间（秒）")
    SMS_CODE_MAX_ATTEMPTS: int = Field(default=5, description="短信验证码最大尝试次数")
    
    # GLM AI 配置（未设置时 AI 知识点分析自动走降级切分，不再内置默认密钥）
    GLM_API_KEY: Optional[str] = Field(default=None, description="GLM API密钥（通过环境变量 GLM_API_KEY 配置）")
    
    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v, info):
        """生产环境必须设置JWT密钥"""
        jwt_secret = v or info.data.get("JWT_SECRET")
        environment = info.data.get("ENVIRONMENT", "development")
        if environment == "production" and (not jwt_secret or jwt_secret == "your-secret-key-change-in-production"):
            raise ValueError("生产环境必须设置JWT_SECRET_KEY或JWT_SECRET环境变量")
        return jwt_secret or "your-secret-key-change-in-production"

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v, info):
        """生产环境禁止使用*"""
        environment = info.data.get("ENVIRONMENT", "development")
        if environment == "production" and v == "*":
            raise ValueError("生产环境禁止使用CORS_ORIGINS=*，必须明确指定允许的来源")
        return v
    
    @property
    def cors_origins_list(self) -> List[str]:
        """获取CORS来源列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENVIRONMENT == "production"
    
    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENVIRONMENT == "development"
    
    model_config = ConfigDict(
        env_file=get_env_file_path(),  # 如果文件不存在或无法读取则返回None
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # 忽略未定义的额外字段（如S3_*, API_PORT等）
    )


# 全局配置实例
settings = Settings()

