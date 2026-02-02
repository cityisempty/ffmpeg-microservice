# FFmpeg Video Merge Microservice

基于 Python FastAPI 的视频处理微服务，支持多个视频的并发下载与无损拼接。

## 功能特性

- ✅ **并发下载**：使用 `httpx` 异步下载多个视频文件
- ✅ **极速拼接**：FFmpeg `-c copy` 无转码拼接
- ✅ **流式响应**：支持 MP4 流式传输，无需等待完整文件生成

## 快速开始

### 使用 Docker

```bash
# 构建镜像
docker build -t ffmpeg-microservice .

# 运行容器
docker run -d -p 8000:8000 ffmpeg-microservice
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

## API 使用

### POST /merge

合并多个视频文件。

**请求体：**

```json
{
  "urls": [
    "https://example.com/video1.mp4",
    "https://example.com/video2.mp4",
    "https://example.com/video3.mp4"
  ]
}
```

**响应：**

返回合并后的 MP4 视频流。

**示例：**

```bash
curl -X POST http://localhost:8000/merge \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/v1.mp4", "https://example.com/v2.mp4"]}' \
  --output merged.mp4
```

## 技术栈

- **FastAPI**: 高性能 Python Web 框架
- **httpx**: 异步 HTTP 客户端
- **FFmpeg**: 强大的多媒体处理工具
- **uvicorn**: ASGI 服务器

## License

MIT License
