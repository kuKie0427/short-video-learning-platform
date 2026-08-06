FROM python:3.11-slim

WORKDIR /app

# 先复制 common 模块
COPY common/ ./common/

# 复制服务代码和依赖
COPY services/upload/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=100 --retries=5 -r requirements.txt

COPY services/upload/ ./services/upload/

# 设置工作目录到服务目录
WORKDIR /app/services/upload

# 设置 PYTHONPATH 以便能找到 common 模块
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8003

# 启动服务
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8003"]
