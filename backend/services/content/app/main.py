#!/usr/bin/env python3
"""
Content服务 - 内容管理、推荐、互动服务
"""
import os
import sys
import logging
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(project_root)

# 导入共享库
from common.config.settings import settings
from common.database.connection import init_db, get_redis
from common.utils.response import error_response

# 导入API路由
from .api.feed import router as feed_router
from .api.interaction import router as interaction_router
from .api.follow import router as follow_router
from .api.learn import router as learn_router

# 配置日志
logging.basicConfig(
    level=logging.INFO if settings.is_development else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 初始化数据库
init_db()

# 测试Redis连接
try:
    redis_client = get_redis()
    if redis_client:
        redis_client.ping()
        logger.info("Redis连接测试成功")
except Exception as e:
    if settings.is_production:
        logger.error(f"生产环境Redis连接失败: {e}")
        raise
    else:
        logger.warning(f"开发环境Redis连接失败: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="Content服务 - 内容管理",
    version="1.0.0",
    description="短视频学习平台内容管理、推荐、互动服务",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理器"""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "验证失败")
        errors.append(f"{field}: {msg}")
    
    return error_response(
        message="请求参数验证失败",
        code=422,
        data={"errors": errors}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """数据库异常处理器"""
    logger.error(f"Database error: {exc}", exc_info=True)
    return error_response(
        message="数据库操作失败",
        code=500
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理器"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.is_production:
        return error_response(
            message="服务器内部错误",
            code=500
        )
    else:
        return error_response(
            message=f"服务器错误: {str(exc)}",
            code=500
        )


# 注册API路由
app.include_router(feed_router)
app.include_router(interaction_router)
app.include_router(follow_router)
app.include_router(learn_router)


@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    logger.info("✅ Content服务已启动")
    logger.info(f"   - 环境: {settings.ENVIRONMENT}")
    logger.info("   - 服务地址: http://localhost:8002")


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "content",
        "message": "Content服务 - 内容管理、推荐、互动",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "content",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动Content服务...")
    print(f"   服务地址: http://localhost:8002")
    print(f"   API文档: http://localhost:8002/docs")
    print("-" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8002)

