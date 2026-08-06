#!/usr/bin/env python3
"""Search服务 - 搜索服务"""
import os
import sys
import logging
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.append(project_root)

from common.config.settings import settings
from common.database.connection import init_db
from common.utils.response import error_response

from .api.search import router as search_router

logging.basicConfig(level=logging.INFO if settings.is_development else logging.WARNING)
logger = logging.getLogger(__name__)

init_db()

app = FastAPI(title="Search服务", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(search_router)

@app.get("/")
async def root():
    return {"service": "search", "status": "running", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "search"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

