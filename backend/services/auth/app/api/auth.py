"""
认证API
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import random
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session
from jose import JWTError, jwt

import sys
import os
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.append(project_root)

from common.database.connection import get_db
from common.models.user import User
from common.utils.response import success_response, error_response
from common.utils.auth import get_current_user
from common.config.settings import settings
from common.utils.redis_client import (
    store_sms_code, get_sms_code, increment_sms_code_attempts,
    delete_sms_code, check_sms_code_exists
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# JWT配置 - 从配置模块读取
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES

security = HTTPBearer()


class PhoneLoginRequest(BaseModel):
    phone: str
    
    @validator('phone')
    def validate_phone(cls, v):
        if not v or len(v) < 10:
            raise ValueError('手机号格式不正确')
        return v


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


class UserProfile(BaseModel):
    id: str
    phone: str
    nickname: str
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    language: str
    roles: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    school: Optional[str] = None
    language: Optional[str] = None


def generate_sms_code() -> str:
    """生成6位数字验证码"""
    return str(random.randint(100000, 999999))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/send-code", summary="发送短信验证码")
async def send_sms_code(request: PhoneLoginRequest):
    """发送短信验证码"""
    # 生成验证码
    code = generate_sms_code()
    
    # 存储验证码到Redis，设置过期时间
    stored = store_sms_code(request.phone, code, settings.SMS_CODE_EXPIRE_SECONDS)
    if not stored:
        return error_response("验证码存储失败，请稍后重试", code=500)
    
    # 发送短信验证码
    from ..services.sms_service import get_sms_service
    sms_service = get_sms_service()
    send_success = sms_service.send_sms(request.phone, code)
    
    if not send_success:
        return error_response("短信发送失败，请稍后重试", code=500)
    
    response_data = {
        "success": True,
        "expires_in": settings.SMS_CODE_EXPIRE_SECONDS
    }
    
    # 开发环境返回验证码用于测试，生产环境不返回
    if settings.is_development:
        response_data["code"] = code
    
    return success_response(
        data=response_data,
        message="验证码已发送"
    )


@router.post("/login", summary="手机号验证码登录")
async def phone_login(
    request: VerifyCodeRequest,
    db: Session = Depends(get_db)
):
    """手机号验证码登录"""
    # 从Redis获取验证码
    code_data = get_sms_code(request.phone)
    if not code_data:
        return error_response("验证码已过期或未发送", code=400)
    
    # 检查验证码是否正确
    if code_data["code"] != request.code:
        attempts = increment_sms_code_attempts(request.phone)
        if attempts and attempts >= settings.SMS_CODE_MAX_ATTEMPTS:
            delete_sms_code(request.phone)  # 超过最大尝试次数，删除验证码
            return error_response("验证码错误次数过多，请重新获取", code=400)
        return error_response("验证码错误", code=400)
    
    # 验证成功后删除验证码
    delete_sms_code(request.phone)
    
    # 查找或创建用户
    user = db.query(User).filter(User.phone == request.phone).first()
    
    if not user:
        # 新用户自动注册
        user = User(
            phone=request.phone,
            nickname=f"用户{request.phone[-4:]}",  # 默认昵称
            language="zh-CN",
            roles=["learner"]
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return success_response(
        data={
            "token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": str(user.id),
                "phone": user.phone,
                "nickname": user.nickname,
                "avatar": user.avatar_url,
                "roles": user.roles
            }
        },
        message="登录成功"
    )


@router.get("/profile", summary="获取用户资料")
async def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户资料"""
    return success_response(
        data={
            "id": str(current_user.id),
            "phone": current_user.phone,
            "nickname": current_user.nickname,
            "avatar": current_user.avatar_url,
            "bio": current_user.bio,
            "gender": current_user.gender,
            "location": current_user.location,
            "school": current_user.school,
            "language": current_user.language,
            "roles": current_user.roles,
            "created_at": current_user.created_at.isoformat()
        }
    )


@router.put("/profile", summary="更新用户资料")
async def update_profile(
    profile_data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    # 允许更新的字段
    if profile_data.nickname is not None:
        current_user.nickname = profile_data.nickname
    if profile_data.avatar_url is not None:
        current_user.avatar_url = profile_data.avatar_url
    if profile_data.bio is not None:
        current_user.bio = profile_data.bio
    if profile_data.gender is not None:
        current_user.gender = profile_data.gender
    if profile_data.location is not None:
        current_user.location = profile_data.location
    if profile_data.school is not None:
        current_user.school = profile_data.school
    if profile_data.language is not None:
        current_user.language = profile_data.language
    
    db.commit()
    db.refresh(current_user)
    
    return success_response(
        data={
            "id": str(current_user.id),
            "phone": current_user.phone,
            "nickname": current_user.nickname,
            "avatar": current_user.avatar_url,
            "bio": current_user.bio,
            "gender": current_user.gender,
            "location": current_user.location,
            "school": current_user.school,
            "language": current_user.language,
            "roles": current_user.roles,
            "created_at": current_user.created_at.isoformat()
        },
        message="用户资料已更新"
    )


@router.post("/refresh", summary="刷新访问令牌")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """刷新访问令牌"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user.id)}, expires_delta=access_token_expires
    )
    
    return success_response(
        data={
            "token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user_id": str(current_user.id)
        },
        message="令牌已刷新"
    )

