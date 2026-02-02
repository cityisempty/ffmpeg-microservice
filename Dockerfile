# 使用官方轻量级 Python 镜像
FROM python:3.9-slim

# 1. 安装系统级依赖：FFmpeg
# 这一步非常关键，赋予了 Python 调用底层视频处理的能力
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 2. 设置工作目录
WORKDIR /app

# 3. 安装 Python 库
# fastapi: API 框架
# uvicorn: 服务器
# httpx: 异步 HTTP 请求 (下载用)
# python-multipart: 处理表单数据
RUN pip install --no-cache-dir fastapi uvicorn httpx python-multipart

# 4. 复制代码
COPY main.py .

# 5. 暴露端口
EXPOSE 8000

# 6. 启动命令
CMD ["python", "main.py"]
