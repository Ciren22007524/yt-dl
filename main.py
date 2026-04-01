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
from chromadb import PersistentClient
from sentence_transformers import SentenceTransformer

CONFIG_FILE = "config.json"
DEFAULT_DOWNLOAD_DIR = "downloads"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"download_dir": DEFAULT_DOWNLOAD_DIR}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# 載入目前設定
current_config = load_config()
if not os.path.exists(current_config["download_dir"]):
    os.makedirs(current_config["download_dir"])

# --- 2. 向量資料庫與 AI 模型初始化 ---
vector_client = PersistentClient(path="./music_vector_db")
collection = vector_client.get_or_create_collection("my_music")
model_path = "./models/paraphrase-multilingual-MiniLM-L12-v2"
# 載入時指定 cache_folder
embedding_model = SentenceTransformer(
    'paraphrase-multilingual-MiniLM-L12-v2',
    cache_folder="./models"
)

app = FastAPI()

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

        # --- 💡 新增：下載完後自動更新向量庫 ---
        # 這裡直接呼叫我們寫好的 sync 邏輯 (簡化版)
        target_dir = current_config["download_dir"]
        files = [f for f in os.listdir(target_dir) if f.endswith(('.mp3', '.mp4'))]
        if files:
            global collection
            vector_client.delete_collection("my_music")
            collection = vector_client.get_or_create_collection(
                name="my_music",
                metadata={"hnsw:space": "cosine"}
            )
            embeddings = embedding_model.encode(files).tolist()
            collection.add(
                documents=files,
                embeddings=embeddings,
                ids=[f"file_{i}" for i in range(len(files))]
            )
        # ---------------------------------------

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
            title = info.get('title')

            # --- 💡 補上向量比對邏輯 ---
            similar_files = []
            total_count = collection.count()

            if total_count > 0:
                query_vec = embedding_model.encode([title]).tolist()
                results = collection.query(query_embeddings=query_vec, n_results=total_count)
                for doc, dist in zip(results['documents'][0], results['distances'][0]):
                    # 這裡將距離轉為相似度評分
                    score = 1 - dist
                    # 只收錄有一定相關性的（例如分數 > 0.3），避免列出完全無關的雜訊
                    if score > 0.6:
                        similar_files.append({"filename": doc, "score": round(score, 4)})

            similar_files.sort(key=lambda x: x['score'], reverse=True)
            return {
                "thumbnail": info.get('thumbnail'),
                "title": title,
                "similar_files": similar_files # 傳給前端顯示
            }
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
        'outtmpl': f'{current_config["download_dir"]}/%(title)s.%(ext)s',
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

@app.post("/config/path")
async def update_path(path: str = Form(...)):
    """更新下載路徑並存入 config.json"""
    normalized_path = path.replace("\\", "/")
    try:
        if not os.path.exists(normalized_path):
            os.makedirs(normalized_path)
        current_config["download_dir"] = normalized_path
        save_config(current_config)
        return {"status": "success", "path": normalized_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/db/status")
async def get_db_status():
    count = collection.count()
    results = collection.get()
    return {
        "count": count,
        "files": results['documents'] if count > 0 else [],
        "current_path": current_config["download_dir"]
    }

@app.post("/db/sync")
async def sync_library():
    """手動觸發：掃描並建立索引"""
    global collection # 💡 確保更新全域變數，讓 preview 路由也能抓到最新的

    # 💡 使用目前設定的動態路徑
    target_dir = current_config["download_dir"]

    try:
        # 1. 清空並重新建立索引 (確保資料一致性)
        vector_client.delete_collection("my_music")
        collection = vector_client.get_or_create_collection(
            name="my_music",
            metadata={"hnsw:space": "cosine"}
        )

        # 2. 掃描目標資料夾
        if not os.path.exists(target_dir):
            return {"status": "error", "message": "路徑不存在，請先設定正確路徑"}

        files = [f for f in os.listdir(target_dir) if f.endswith(('.mp3', '.mp4'))]

        if files:
            # 💡 關鍵：只拿檔名（不含副檔名）去算向量
            clean_names = [os.path.splitext(f)[0] for f in files]
            embeddings = embedding_model.encode(clean_names).tolist()

            collection.add(
                documents=files,  # 這裡還是存原始檔名，方便前端顯示
                embeddings=embeddings,
                ids=[f"file_{i}" for i in range(len(files))]
            )

        return {"status": "success", "count": len(files), "path": target_dir}
    except Exception as e:
        return {"status": "error", "message": str(e)}