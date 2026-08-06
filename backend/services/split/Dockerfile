FROM python:3.11-slim

WORKDIR /app

# 系统依赖（包含 ffmpeg 和 opencv 依赖，以及 libmagic1）
RUN apt-get update && apt-get install -y ffmpeg libgl1 libglib2.0-0 libmagic1 && rm -rf /var/lib/apt/lists/*

# 先复制 common 模块
COPY common/ ./common/

# 复制服务代码和依赖
COPY services/split/requirements.txt .

# 配置 pip 镜像源并安装依赖
# 1. 先安装 torch CPU 版本以减小体积
# 2. 安装服务依赖
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY services/split/ ./services/split/

# 设置工作目录到服务目录
WORKDIR /app/services/split

# 设置 PYTHONPATH 以便能找到 common 模块
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8004

# 启动服务
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
