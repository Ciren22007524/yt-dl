# 🎬 MediaDL

一個基於 Web 的影音下載工具，提供簡潔的瀏覽器介面，讓你貼上影片網址就能快速下載 MP4 影片或 MP3 音訊檔案。後端採用 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 引擎，支援上千個影音平台。本專案透過不同分支提供 **基礎下載** 與 **AI 智慧重複偵測** 兩種版本。

---

## 這個工具在幹嘛？

這是一個 **本地自架的影音下載工具**，後端使用 Python 的 [FastAPI](https://fastapi.tiangolo.com/) 框架搭配 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 引擎，前端提供 Bootstrap 美化的網頁介面。你只要在瀏覽器中打開頁面、貼上影片連結，就能直接下載影片或純音訊到本機。yt-dlp 支援上千個影音平台，不限於單一來源。

**核心運作流程：**

1. 使用者在網頁貼上影片網址 → 自動抓取影片縮圖並預覽
2. 選擇輸出格式（MP4 / MP3）和品質
3. 點擊「開始下載」→ 後端以背景任務執行 yt-dlp 下載
4. 透過 WebSocket 即時回傳下載進度條到前端
5. 下載完成後自動進行 FFmpeg 轉檔與 **loudnorm 音量標準化**
6. 前端彈窗通知完成

---

## 分支說明

本專案有三個分支，提供不同層級的功能：

| 分支 | 說明 |
|------|------|
| **`main`** / **`feature-basic_function`** | 基礎版本 — 完整的影音下載功能（兩者程式碼完全相同） |
| **`feature-ai_recommend`** | AI 進階版 — 在基礎版之上加入向量資料庫與 AI 相似度比對，下載前自動偵測庫中是否已有相似檔案 |

---

## 功能特色

### 基礎功能（`main` / `feature-basic_function`）

| 功能 | 說明 |
|------|------|
| **MP4 影片下載** | 支援最佳畫質、1080p、720p、480p 等解析度選擇 |
| **MP3 音訊下載** | 支援最佳音質、320kbps、256kbps、192kbps、128kbps |
| **影片預覽** | 貼上網址後自動載入影片縮圖顯示在頁面上 |
| **即時進度條** | 透過 WebSocket 即時顯示下載百分比，不用重新整理頁面 |
| **音量標準化** | 下載後自動套用 FFmpeg `loudnorm` 濾鏡，統一音量大小 |
| **背景下載** | 使用 FastAPI BackgroundTasks，下載不會阻塞 Web 伺服器 |
| **內建 FFmpeg** | 透過 `imageio-ffmpeg` 自動取得 FFmpeg，不需另外安裝 |
| **可打包為 exe** | 支援 PyInstaller 打包成獨立執行檔（已有 frozen 環境判斷） |

### AI 進階功能（`feature-ai_recommend`）

在基礎功能之上，額外提供：

| 功能 | 說明 |
|------|------|
| **AI 重複偵測** | 貼上網址時，自動用 AI 語意比對庫中已有檔案，若相似度 > 60% 則顯示警告，避免重複下載 |
| **向量資料庫** | 使用 [ChromaDB](https://www.trychroma.com/) 持久化儲存檔案名稱的向量嵌入 |
| **多語言語意模型** | 使用 [SentenceTransformer](https://www.sbert.net/) 的 `paraphrase-multilingual-MiniLM-L12-v2` 模型，支援中英日等多語言的語意比對 |
| **相似度分級顯示** | 相似度 > 80% 標紅色高風險、60%–80% 標黃色中風險，一目瞭然 |
| **自動索引更新** | 每次下載完成後，自動將新檔案加入向量資料庫 |
| **手動同步索引** | 側邊欄提供「同步本地資料夾」按鈕，可手動重建索引 |
| **自訂下載路徑** | 可透過側邊欄設定本地音樂庫路徑，設定存入 `config.json` 持久保存 |
| **音樂庫管理面板** | 左側 Offcanvas 側邊欄，顯示庫中檔案數量與完整清單 |

---

## 系統需求

- **Python** >= 3.13
- **Poetry**（套件管理工具）

> **注意：** `feature-ai_recommend` 分支額外需要下載 SentenceTransformer 模型（首次啟動會自動下載至 `./models/` 目錄）。

---

## 安裝與執行（Windows）

### 0. 前置條件

確認已安裝 Python 3.13+ 和 Poetry：

```powershell
python --version    # 需要 >= 3.13
poetry --version    # 如果沒有，請先安裝 Poetry
```

> **安裝 Poetry：** 在 PowerShell 執行 `(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -`

### 1. 選擇分支

```powershell
# 基礎版（預設）
git checkout main

# AI 進階版
git checkout feature-ai_recommend
```

### 2. 安裝依賴套件

```powershell
poetry install
```

### 3. 啟動伺服器

```powershell
poetry run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

啟動後終端會顯示：
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### 4. 開啟瀏覽器使用

前往 [http://127.0.0.1:8000](http://127.0.0.1:8000)，在網頁上貼上影片網址即可下載。

> **不需要在終端輸入影片連結！** 所有操作都在瀏覽器的網頁介面上完成。

### 5. 查看 Debug Log

下載過程中的所有 log 會同時輸出到終端和 `debug.log` 檔案：

```powershell
# 即時監看 log（另開一個 PowerShell 視窗）
Get-Content debug.log -Wait
```

---

## 使用方式

### 基礎版操作

1. **貼上網址** — 將影片網址貼到輸入框，頁面會自動顯示影片封面縮圖
2. **選擇格式** — 從下拉選單選擇 `MP4 (影片)` 或 `MP3 (音訊)`
3. **選擇品質**
   - MP4：最佳品質 / 1080p / 720p / 480p
   - MP3：最佳音質 / 320kbps / 256kbps / 192kbps / 128kbps
4. **點擊「🚀 開始下載」** — 進度條會即時顯示下載進度
5. **等待完成** — 下載完成後會彈窗通知，檔案存放在 `downloads/` 資料夾

### AI 進階版額外操作

1. **設定音樂庫路徑** — 點擊左上角「📂 檔案管理」開啟側邊欄 → 輸入本地音樂庫路徑（如 `D:/Music`）→ 點擊「儲存」
2. **建立索引** — 在側邊欄點擊「🔄 同步本地資料夾」，掃描資料夾內所有 `.mp3` / `.mp4` 檔案並建立向量索引
3. **智慧偵測** — 貼上影片網址後，除了顯示縮圖，還會自動比對庫中是否有相似檔案：
   - 若偵測到相似檔案，會列出檔名與相似度百分比
   - 紅色標籤 = 高度相似（> 80%），很可能是重複的
   - 黃色標籤 = 中度相似（60%–80%），可能相關但不一定重複
   - 若確定要下載，忽略提示直接點擊下載按鈕即可
4. **自動更新** — 每次下載完成後，向量資料庫會自動更新，不需手動重新同步

---

## 進階用法

### 使用 Poetry Shell

```powershell
poetry shell
uvicorn main:app --reload
```

### 對外開放連線（部署用）

將 `--host` 改為 `0.0.0.0`：

```powershell
poetry run uvicorn main:app --host 0.0.0.0 --port 8000
```

### Debug Log 說明

啟動伺服器後，`debug.log` 會自動記錄：
- 啟動時的環境資訊（BASE_DIR、FFmpeg 路徑）
- 每次預覽請求（URL 和影片標題）
- 每次下載請求（格式、品質、URL）
- 下載錯誤（含完整堆疊追蹤）

Log 會同時輸出到終端和檔案，不需額外設定。

---

## 專案結構

### 基礎版（`main`）

```
MediaDL/
├── main.py               # FastAPI 後端主程式（API 路由、下載邏輯、WebSocket）
├── pyproject.toml         # Poetry 專案設定與依賴
├── poetry.lock            # 鎖定的依賴版本
├── templates/
│   └── index.html         # Jinja2 前端頁面模板
├── static/
│   ├── css/
│   │   ├── bootstrap.min.css
│   │   └── index.css      # 自定義樣式
│   └── js/
│       ├── bootstrap.bundle.min.js
│       ├── index.js        # 前端互動邏輯（格式切換、預覽、表單送出）
│       └── websocket.js    # WebSocket 連線處理（進度條即時更新）
└── downloads/             # 下載檔案存放目錄（自動建立，已 gitignore）
```

### AI 進階版額外檔案（`feature-ai_recommend`）

```
MediaDL/
├── config.json            # 使用者設定（下載路徑等，自動產生，已 gitignore）
├── models/                # SentenceTransformer 模型快取（首次啟動自動下載）
├── music_vector_db/       # ChromaDB 向量資料庫持久化目錄
└── ...                    # 其餘同基礎版
```

---

## API 端點

### 基礎版

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/` | 首頁（Web 介面） |
| `GET` | `/preview?url=...` | 取得影片標題與縮圖 |
| `POST` | `/download` | 開始下載（表單：`url`, `format_type`, `quality`） |
| `WS` | `/ws` | WebSocket 連線，接收即時下載進度 |

### AI 進階版額外端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/preview?url=...` | 同上，但額外回傳 `similar_files` 相似檔案清單 |
| `POST` | `/config/path` | 更新下載路徑（表單：`path`） |
| `GET` | `/db/status` | 取得向量資料庫狀態（檔案數量、清單、目前路徑） |
| `POST` | `/db/sync` | 手動觸發資料夾掃描與向量索引重建 |

---

## 技術棧

| 層級 | 基礎版 | AI 進階版額外使用 |
|------|--------|-------------------|
| **後端框架** | FastAPI | — |
| **下載引擎** | yt-dlp | — |
| **音訊處理** | imageio-ffmpeg (loudnorm) | — |
| **前端** | Bootstrap 5 + 原生 JavaScript | — |
| **即時通訊** | WebSocket | — |
| **模板引擎** | Jinja2 | — |
| **套件管理** | Poetry | — |
| **向量資料庫** | — | ChromaDB |
| **AI 語意模型** | — | SentenceTransformer (paraphrase-multilingual-MiniLM-L12-v2) |
