import yt_dlp
import os
import sys
import asyncio
import imageio_ffmpeg
import json
import re
from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

if getattr(sys, 'frozen', False):
    # 如果是打包後的 exe 執行環境
    BASE_DIR = Path(sys._MEIPASS)
else:
    # 如果是平常開發環境
    BASE_DIR = Path(__file__).parent

ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

## 回下載進度用
# 存放啟動中的 WebSocket 連線
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections[:]:
            try:
                await asyncio.wait_for(connection.send_text(message), timeout=1.0)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # 維持連線
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 下載任務的核心邏輯 (同步執行)
def run_download(url, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if manager.loop:
            message = json.dumps({"type": "status", "data": "✅ 下載已完成！"})
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), manager.loop)
    except Exception as e:
        print(f"Download Error: {e}")

# yt-dlp 的進度鉤子
last_percent = ""
def progress_hook(d):
    global last_percent
    if manager.loop and d['status'] == 'downloading':
        p_raw = d.get('_percent_str', '0').replace('%', '').strip()
        p_clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', p_raw)

        current_p = p_clean.split('.')[0]
        if current_p != last_percent:
            last_percent = current_p
            message = json.dumps({"type": "progress", "data": p_clean})
            asyncio.run_coroutine_threadsafe(manager.broadcast(message), manager.loop)

    elif manager.loop and d['status'] == 'finished':
        message = json.dumps({"type": "status", "data": "下載完成，正在轉檔與優化音量..."})
        asyncio.run_coroutine_threadsafe(manager.broadcast(message), manager.loop)

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "name": "鐘啓仁"})

@app.get("/preview")
async def get_preview(url: str):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return {"thumbnail": info.get('thumbnail'), "title": info.get('title')}
    except Exception as e:
        return {"error": str(e)}

@app.post("/download")
async def download_video(
        background_tasks: BackgroundTasks, # 注入背景任務
        url: str = Form(...),
        format_type: str = Form(...),
        quality: str = Form(...)
):
    if format_type == 'mp4':
        video_format = f'bestvideo[height<={quality}]+bestaudio/best' if quality != 'best' else 'bestvideo+bestaudio/best'
        ydl_opts = {
            'format': video_format,
            'merge_output_format': 'mp4',
        }
    else:
        # MP3 邏輯：接收前端傳來的 kbps
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': quality,
            }],
        }

    ydl_opts.update({
        # 'ffmpeg_location': str(BASE_DIR),
        'ffmpeg_location': ffmpeg_exe,
        'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',
        'restrictfilenames': False,
        'windowsfilenames': True,
        'noplaylist': True,
        'overwrites': True,
        'fixup': 'detect_or_warn',
        # 'verbose': True,
        # 'noprogress': False,
        'postprocessor_args': [
            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11'
        ],
        'progress_hooks': [progress_hook]
    })
    background_tasks.add_task(run_download, url, ydl_opts)

    return {"status": "started"}
