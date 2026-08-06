"""
统一响应格式工具
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    message: str = "success"
    data: Optional[Any] = None


def success_response(data: Any = None, message: str = "success", code: int = 200) -> JSONResponse:
    """成功响应"""
    return JSONResponse(
        status_code=200,
        content={
            "code": code,
            "message": message,
            "data": data
        }
    )


def error_response(message: str, code: int = 400, data: Any = None) -> JSONResponse:
    """错误响应"""
    return JSONResponse(
        status_code=code if 400 <= code < 600 else 400,
        content={
            "code": code,
            "message": message,
            "data": data
        }
    )


def not_found_response(message: str = "资源不存在") -> JSONResponse:
    """404响应"""
    return error_response(message, code=404)


def unauthorized_response(message: str = "未授权") -> JSONResponse:
    """401响应"""
    return error_response(message, code=401)


def forbidden_response(message: str = "无权限") -> JSONResponse:
    """403响应"""
    return error_response(message, code=403)

