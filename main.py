from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import StreamingResponse
import subprocess
import httpx
import asyncio
import os
import tempfile
from typing import List

app = FastAPI()


async def download_file(client, url, path):
    """异步下载单个文件"""
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download {url}: {str(e)}")


@app.post("/merge")
async def merge_videos(urls: List[str] = Body(..., embed=True)):
    """
    接收 {"urls": ["url1", "url2", "url3"]}
    返回合并后的 MP4 流
    """
    if len(urls) < 2:
        raise HTTPException(status_code=400, detail="At least 2 URLs are required")

    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        file_paths = []
        download_tasks = []

        # 1. 并发下载视频 (这是 Python 方案比 Shell 快的关键)
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(urls):
                file_path = os.path.join(temp_dir, f"{i}.mp4")
                file_paths.append(file_path)
                # 创建下载任务
                download_tasks.append(download_file(client, url, file_path))

            # 等待所有下载完成
            await asyncio.gather(*download_tasks)

        # 2. 生成 FFmpeg 列表文件
        list_txt_path = os.path.join(temp_dir, "list.txt")
        with open(list_txt_path, "w") as f:
            for path in file_paths:
                f.write(f"file '{path}'\n")

        # 3. 调用 FFmpeg (Pipe 输出到 Stdout)
        # -c copy: 不转码，极速拼接
        # -movflags frag_keyframe+empty_moov: 让 MP4 能够流式传输
        command = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", list_txt_path,
            "-c", "copy",
            "-movflags", "frag_keyframe+empty_moov",
            "-f", "mp4", "-"
        ]

        # 启动 FFmpeg 进程
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # 4. 返回流式响应
        return StreamingResponse(
            process.stdout,
            media_type="video/mp4",
            headers={"Content-Disposition": "attachment; filename=merged.mp4"}
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
