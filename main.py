from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel
import subprocess
import httpx
import asyncio
import os
import tempfile
import uuid
from datetime import datetime
from typing import List, Optional

app = FastAPI(title="FFmpeg Video Merge Microservice")

# 持久化存储目录（需要挂载卷）
STORAGE_DIR = os.environ.get("STORAGE_DIR", "/data")


class MergeRequest(BaseModel):
    urls: List[str]
    save_to_disk: bool = False  # 是否保存到磁盘
    filename: Optional[str] = None  # 自定义文件名


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


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "storage_dir": STORAGE_DIR}


@app.post("/merge")
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


@app.get("/files/{filename}")
async def download_file_endpoint(filename: str):
    """下载已保存的文件"""
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=filename
    )


@app.get("/files")
async def list_files():
    """列出所有已保存的文件"""
    if not os.path.exists(STORAGE_DIR):
        return {"files": []}
    
    files = []
    for f in os.listdir(STORAGE_DIR):
        if f.endswith(".mp4"):
            file_path = os.path.join(STORAGE_DIR, f)
            files.append({
                "filename": f,
                "size_mb": round(os.path.getsize(file_path) / 1024 / 1024, 2),
                "download_url": f"/files/{f}"
            })
    return {"files": files}


@app.delete("/files/{filename}")
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
