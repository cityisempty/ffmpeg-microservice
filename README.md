# FFmpeg Video Merge Microservice

基于 Python FastAPI 的视频处理微服务，支持多个视频的并发下载与无损拼接。

## 功能特性

- ✅ **并发下载**：使用 `httpx` 异步下载多个视频文件
- ✅ **极速拼接**：FFmpeg `-c copy` 无转码拼接
- ✅ **双模式支持**：流式返回 或 保存到磁盘
- ✅ **文件管理**：列出、下载、删除已保存的文件

## 快速开始

### 使用 Docker

```bash
# 构建镜像
docker build -t ffmpeg-microservice .

# 运行容器（流式模式，不挂载卷）
docker run -d -p 8000:8000 ffmpeg-microservice

# 运行容器（带挂载卷，支持文件持久化）
docker run -d -p 8000:8000 -v $(pwd)/videos:/data ffmpeg-microservice
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 设置存储目录（可选）
export STORAGE_DIR=./videos

# 启动服务
python main.py
```

## API 使用

### GET /health

健康检查。

### POST /merge

合并多个视频文件。

**Header:**
`X-API-Key: your_secret_key`

**请求体：**

```json
{
  "urls": ["https://example.com/v1.mp4", "https://example.com/v2.mp4"],
  "save_to_disk": false,
  "filename": "my_video"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `urls` | array | 必填 | 视频 URL 列表（至少2个） |
| `save_to_disk` | bool | `false` | `true` 保存到磁盘，`false` 流式返回 |
| `filename` | string | 自动生成 | 自定义文件名（仅 save_to_disk=true 时有效） |

**响应：**

- `save_to_disk=false`：返回 MP4 视频流
- `save_to_disk=true`：返回 JSON

```json
{
  "status": "success",
  "filename": "my_video.mp4",
  "download_url": "/files/my_video.mp4",
  "file_path": "/data/my_video.mp4"
}
```

**示例：**

```bash
# 流式下载
curl -X POST http://localhost:8000/merge \
  -H "Content-Type: application/json" \
  -d '{"urls": ["url1.mp4", "url2.mp4"]}' \
  --output merged.mp4

# 保存到服务器
curl -X POST http://localhost:8000/merge \
  -H "Content-Type: application/json" \
  -d '{"urls": ["url1.mp4", "url2.mp4"], "save_to_disk": true, "filename": "demo"}'
```

### POST /extract-frame

提取视频及其最后一帧图片（极速模式）。

**请求体：**

```json
{
  "url": "https://example.com/video.mp4",
  "save_to_disk": true,
  "filename": "my_frame"
}
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | string | 必填 | 视频源 URL |
| `save_to_disk` | bool | `true` | `true` 保存到磁盘，`false` 流式返回 |
| `filename` | string | 自动生成 | 自定义文件名（仅 save_to_disk=true 时有效） |

**响应：**

- `save_to_disk=false`：返回 JPEG 图片流
- `save_to_disk=true`：返回 JSON 结构体

**示例：**

```bash
# 获取图片并保存到服务器
curl -X POST http://localhost:8000/extract-frame \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_key" \
  -d '{"url": "https://example.com/v.mp4", "save_to_disk": true}'
```

### GET /files

列出所有已保存的文件。

### GET /files/{filename}

下载指定文件。

### DELETE /files/{filename}

删除指定文件。

## 技术栈

- **FastAPI**: 高性能 Python Web 框架
- **httpx**: 异步 HTTP 客户端
- **FFmpeg**: 强大的多媒体处理工具
- **uvicorn**: ASGI 服务器

## License

MIT License
