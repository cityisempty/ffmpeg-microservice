from fastapi import FastAPI, HTTPException, Body, Query, Header, Depends
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
import subprocess
import httpx
import asyncio
import os
import tempfile
import uuid
import mimetypes
from datetime import datetime
from typing import List, Optional

app = FastAPI(title="FFmpeg Video Merge Microservice")

# 环境变量配置
STORAGE_DIR = os.environ.get("STORAGE_DIR", "/data")
API_KEY = os.environ.get("API_KEY")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    if not API_KEY:
        return  # 如果未设置 API_KEY，则跳过校验（仅用于测试环境）
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate credentials")


class MergeRequest(BaseModel):
    urls: List[str]
    save_to_disk: bool = False  # 是否保存到磁盘
    filename: Optional[str] = None  # 自定义文件名


class ExtractFrameRequest(BaseModel):
    url: str
    save_to_disk: bool = True
    filename: Optional[str] = None


async def download_file(client, url, path):
    """异步下载单个文件"""
    try:
        response = await client.get(url, follow_redirects=True, timeout=300.0)
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download {url}: {str(e)}")


def run_ffmpeg_merge(list_txt_path: str, output_path: Optional[str] = None):
    """执行 FFmpeg 合并"""
    if output_path:
        # 输出到文件
        command = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_txt_path,
            "-c", "copy", output_path
        ]
        process = subprocess.run(command, capture_output=True)
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {process.stderr.decode()}")
        return None
    else:
        # 流式输出
        command = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_txt_path,
            "-c", "copy",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4", "-"
        ]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def run_ffmpeg_extract_frame(input_url: str, output_path: Optional[str] = None):
    """执行 FFmpeg 提取视频最后一帧"""
    if output_path:
        # 输出到文件
        command = [
            "ffmpeg", "-y", "-sseof", "-1", "-i", input_url,
            "-update", "1", "-q:v", "2", output_path
        ]
        process = subprocess.run(command, capture_output=True)
        if process.returncode != 0:
            raise HTTPException(status_code=500, detail=f"FFmpeg error: {process.stderr.decode()}")
        return None
    else:
        # 流式输出 (输出 jpg 到 stdout)
        command = [
            "ffmpeg", "-sseof", "-1", "-i", input_url,
            "-update", "1", "-q:v", "2", "-f", "image2pipe", "-"
        ]
        return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "storage_dir": STORAGE_DIR}


@app.post("/merge", dependencies=[Depends(verify_api_key)])
async def merge_videos(request: MergeRequest):
    """
    合并多个视频
    
    - save_to_disk=false: 流式返回合并后的视频
    - save_to_disk=true: 保存到磁盘并返回下载链接
    """
    if len(request.urls) < 2:
        raise HTTPException(status_code=400, detail="At least 2 URLs are required")

    with tempfile.TemporaryDirectory() as temp_dir:
        file_paths = []
        download_tasks = []

        # 1. 并发下载视频
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(request.urls):
                file_path = os.path.join(temp_dir, f"{i}.mp4")
                file_paths.append(file_path)
                download_tasks.append(download_file(client, url, file_path))
            await asyncio.gather(*download_tasks)

        # 2. 生成 FFmpeg 列表文件
        list_txt_path = os.path.join(temp_dir, "list.txt")
        with open(list_txt_path, "w") as f:
            for path in file_paths:
                f.write(f"file '{path}'\n")

        # 3. 根据模式处理
        if request.save_to_disk:
            # 保存到挂载卷
            os.makedirs(STORAGE_DIR, exist_ok=True)
            
            if request.filename:
                filename = request.filename if request.filename.endswith(".mp4") else f"{request.filename}.mp4"
            else:
                filename = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.mp4"
            
            output_path = os.path.join(STORAGE_DIR, filename)
            run_ffmpeg_merge(list_txt_path, output_path)
            
            return JSONResponse({
                "status": "success",
                "filename": filename,
                "download_url": f"/files/{filename}",
                "file_path": output_path
            })
        else:
            # 流式返回
            process = run_ffmpeg_merge(list_txt_path)
            return StreamingResponse(
                process.stdout,
                media_type="video/mp4",
                headers={"Content-Disposition": "attachment; filename=merged.mp4"}
            )


@app.post("/extract-frame", dependencies=[Depends(verify_api_key)])
async def extract_frame(request: ExtractFrameRequest):
    """
    提取视频最后一帧图片
    
    - save_to_disk=false: 流式返回图片
    - save_to_disk=true: 保存到磁盘并返回查看链接
    """
    if request.save_to_disk:
        os.makedirs(STORAGE_DIR, exist_ok=True)
        
        if request.filename:
            filename = request.filename if request.filename.lower().endswith(".jpg") else f"{request.filename}.jpg"
        else:
            filename = f"framed_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        
        output_path = os.path.join(STORAGE_DIR, filename)
        run_ffmpeg_extract_frame(request.url, output_path)
        
        return JSONResponse({
            "status": "success",
            "filename": filename,
            "download_url": f"/files/{filename}",
            "file_path": output_path
        })
    else:
        # 流式返回
        process = run_ffmpeg_extract_frame(request.url)
        return StreamingResponse(
            process.stdout,
            media_type="image/jpeg",
            headers={"Content-Disposition": "inline; filename=frame.jpg"}
        )


@app.get("/files/{filename}", dependencies=[Depends(verify_api_key)])
async def download_file_endpoint(filename: str):
    """下载已保存的文件"""
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    content_type, _ = mimetypes.guess_type(filename)
    return FileResponse(
        file_path,
        media_type=content_type or "application/octet-stream",
        filename=filename
    )


@app.get("/files", dependencies=[Depends(verify_api_key)])
async def list_files():
    """列出所有已保存的文件"""
    if not os.path.exists(STORAGE_DIR):
        return {"files": []}
    
    files = []
    for f in os.listdir(STORAGE_DIR):
        if f.lower().endswith((".mp4", ".jpg", ".jpeg")):
            file_path = os.path.join(STORAGE_DIR, f)
            files.append({
                "filename": f,
                "size_mb": round(os.path.getsize(file_path) / 1024 / 1024, 2),
                "download_url": f"/files/{f}"
            })
    return {"files": files}


@app.delete("/files/{filename}", dependencies=[Depends(verify_api_key)])
async def delete_file(filename: str):
    """删除已保存的文件"""
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(file_path)
    return {"status": "deleted", "filename": filename}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
