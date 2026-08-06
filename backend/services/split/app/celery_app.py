from celery import Celery
import logging

import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(project_root)

from common.config.settings import settings

logger = logging.getLogger(__name__)

# Broker/Backend 使用 Redis（从 settings 中读取 REDIS_URL 或 HOST/PORT）
redis_url = settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"

celery_app = Celery('split_tasks', broker=redis_url, backend=redis_url)


@celery_app.task(name='split.process_split_task')
def process_split_task(split_task_id: str):
    """Celery 任务：调用同步处理函数完成拆分逻辑（在 worker 中运行）。"""
    logger.info(f"Celery worker start processing split task: {split_task_id}")
    # 延迟导入以避免在启动 API 时触发不必要的依赖
    try:
        from common.database.connection import SessionLocal
        db = SessionLocal()
        try:
            # 导入并调用同步处理函数
            from .api.split import process_split_task_sync
            process_split_task_sync(split_task_id, db)
        finally:
            db.close()
    except Exception as e:
        logger.exception(f"Celery split task failed: {e}")
        raise
