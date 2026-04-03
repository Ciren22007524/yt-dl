# main.py 解析

> **角色：** 整個專案的後端核心，所有 API 路由、下載邏輯、WebSocket 即時通訊都在這一份檔案裡。
>
> **重要度：** ⭐⭐⭐（任何功能新增或修改幾乎都會碰到這份檔案）

---

## 檔案結構概覽

```
main.py
├── [L1-12]   Import 區塊
├── [L14]     FastAPI app 實例建立
├── [L16-18]  下載目錄初始化
├── [L20-26]  BASE_DIR 環境判斷（開發 vs PyInstaller）
├── [L28]     FFmpeg 路徑取得
├── [L31-52]  ConnectionManager 類別（WebSocket 管理）
├── [L54]     manager 全域實例
├── [L56-62]  WebSocket 端點 /ws
├── [L64-65]  靜態檔案 & 模板掛載
├── [L67-76]  run_download() — 下載核心邏輯
├── [L78-95]  progress_hook() — yt-dlp 進度回呼
├── [L97-99]  GET / — 首頁路由
├── [L101-108] GET /preview — 影片預覽 API
├── [L110-150] POST /download — 下載觸發 API
```

---

## 逐段解析

### 1. 環境初始化（L1-28）

```python
app = FastAPI()

DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)
```

- 建立 FastAPI 實例
- 確保 `downloads/` 目錄存在
- 判斷 `sys.frozen`（PyInstaller 打包環境）來決定靜態檔案的基礎路徑
- 透過 `imageio_ffmpeg.get_ffmpeg_exe()` 取得內建 FFmpeg 路徑

**Enhancement 注意：** 如果要支援自訂下載路徑，`DOWNLOAD_DIR` 需要改為可配置的變數（`feature-ai_recommend` 分支已實作此功能）。

---

### 2. ConnectionManager 類別（L31-52）

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.loop = None
```

管理所有 WebSocket 連線的核心類別：

| 方法 | 功能 |
|------|------|
| `connect()` | 接受連線、加入清單、保存 event loop 參考 |
| `disconnect()` | 從清單移除斷線的連線 |
| `broadcast()` | 對所有連線廣播訊息，超時 1 秒自動斷線 |

**關鍵設計：** `self.loop` 儲存了 asyncio 的 event loop 參考，讓同步的 `progress_hook` 能透過 `asyncio.run_coroutine_threadsafe()` 跨執行緒推送訊息。

**Enhancement 注意：**
- 目前是廣播（broadcast）模式，所有連接的用戶都會收到同一個進度。若要支援多人同時下載且各自看各自的進度，需要改為每個下載任務對應一組 WebSocket。
- `broadcast()` 中的 `except:` 裸捕獲太寬泛，建議改為捕獲具體異常。

---

### 3. WebSocket 端點（L56-62）

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # 維持連線
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

- 用 `receive_text()` 的無限迴圈維持連線存活
- 斷線時自動從 manager 移除

---

### 4. run_download() — 下載核心（L67-76）

```python
def run_download(url, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        # 下載完成 → 透過 WebSocket 通知前端
    except Exception as e:
        print(f"Download Error: {e}")
```

- **同步函式**，由 `BackgroundTasks` 在背景執行緒中呼叫
- 完成後透過 `asyncio.run_coroutine_threadsafe` 跨執行緒推送完成訊息

**Enhancement 注意：**
- 錯誤處理只有 `print`，沒有回報給前端。建議加上錯誤訊息的 WebSocket 推送。
- 沒有下載取消機制。若要支援取消，需要在 yt-dlp 層級做中斷。

---

### 5. progress_hook() — 進度回呼（L78-95）

```python
def progress_hook(d):
    global last_percent
    if manager.loop and d['status'] == 'downloading':
        # 清除 ANSI 色碼 → 取整數百分比 → 避免重複推送
```

yt-dlp 在下載過程中會不斷呼叫這個 hook：

| 狀態 | 行為 |
|------|------|
| `downloading` | 解析百分比 → 去重 → 推送 `{"type": "progress", "data": "XX"}` |
| `finished` | 推送 `{"type": "status", "data": "下載完成，正在轉檔與優化音量..."}` |

**關鍵技術：**
- 用正規表達式 `re.sub(r'\x1B...')` 清除 yt-dlp 輸出中的 ANSI 終端色碼
- `last_percent` 全域變數做去重，避免同一百分比重複推送
- `finished` 狀態指的是「下載完成但後處理（FFmpeg）尚未結束」

**Enhancement 注意：**
- `global last_percent` 在多人同時下載時會互相干擾，應改為 per-task 的狀態追蹤。

---

### 6. GET /preview — 影片預覽 API（L101-108）

```python
@app.get("/preview")
async def get_preview(url: str):
    with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
        info = ydl.extract_info(url, download=False)
        return {"thumbnail": info.get('thumbnail'), "title": info.get('title')}
```

- `download=False`：只抓 metadata，不實際下載
- 回傳影片標題和縮圖 URL 給前端顯示

**Enhancement 注意：**
- 可以擴充回傳更多 metadata（時長、上傳者、觀看次數等）
- `feature-ai_recommend` 分支在這裡加入了向量比對邏輯，回傳 `similar_files`

---

### 7. POST /download — 下載觸發 API（L110-150）

```python
@app.post("/download")
async def download_video(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    format_type: str = Form(...),
    quality: str = Form(...)
):
```

根據 `format_type` 組裝不同的 `ydl_opts`：

| 格式 | ydl_opts 設定 |
|------|---------------|
| MP4 | `bestvideo[height<=品質]+bestaudio/best` → 合併為 mp4 |
| MP3 | `bestaudio/best` → FFmpegExtractAudio 後處理器 → 指定 kbps |

**共用設定：**
```python
'ffmpeg_location': ffmpeg_exe,          # 內建 FFmpeg 路徑
'outtmpl': f'{DOWNLOAD_DIR}/%(title)s.%(ext)s',  # 輸出檔名
'windowsfilenames': True,               # Windows 檔名相容
'noplaylist': True,                      # 不下載播放清單
'postprocessor_args': ['-af', 'loudnorm=I=-16:TP=-1.5:LRA=11'],  # 音量標準化
'progress_hooks': [progress_hook]        # 綁定進度回呼
```

**Enhancement 注意：**
- `url` 參數沒有做 URL 格式驗證，建議加入白名單或基本的 URL 檢查
- `loudnorm` 濾鏡套用在所有下載（含 MP4 影片），若只想處理音訊需加條件判斷
- 若要支援播放清單下載，需移除 `noplaylist: True` 並處理多檔案進度
