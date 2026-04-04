# TODO 2：自動標籤分類器 — Implementation Plan

## 目標概述

建立標籤（tag）分類系統，讓每首歌可以同時屬於多個分類維度（歌手、作品、曲目類型等），取代傳統的資料夾分類。標籤資訊存在向量資料庫 + SQLite 中，實體檔案不搬移。

---

## 1. 現況分析

### 目前系統的限制

```python
# main.py - 目前 ChromaDB 只存檔名和向量，沒有任何分類資訊
collection.add(
    documents=files,           # 只有檔名
    embeddings=embeddings,     # 只有向量
    ids=[f"file_{i}" for i in range(len(files))]
)
```

- 側邊欄「音樂庫管理」只有一個扁平的檔案清單
- 沒有任何分類、篩選、分組功能
- ChromaDB 的 `metadatas` 欄位完全沒用到

### 為什麼需要 SQLite

ChromaDB 的 metadata 查詢有以下限制：

| 操作 | ChromaDB 支援度 | 說明 |
|------|-----------------|------|
| 單欄位精確查詢 | ✅ | `where={"artist": "LiSA"}` |
| AND 條件 | ✅ | `where={"$and": [{...}, {...}]}` |
| OR 條件 | ✅ | `where={"$or": [{...}, {...}]}` |
| 陣列欄位 | ❌ | metadata value 不支援 list 型別 |
| 部分匹配 | ⚠️ | 只有 `$contains` 可用，容易誤匹配 |
| 聚合查詢 | ❌ | 無法 COUNT / GROUP BY |
| 多對多關係 | ❌ | 一首歌多個標籤需要多行，但 ChromaDB ID 唯一 |

**結論：** ChromaDB 負責語意向量搜尋，SQLite 負責結構化的標籤管理。

---

## 2. 資料庫設計

### SQLite Schema

```sql
-- 歌曲主表
CREATE TABLE songs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL UNIQUE,          -- "紅蓮華 - LiSA.mp3"
    filepath    TEXT NOT NULL,                 -- "E:/mp3/mp4/Pending/紅蓮華 - LiSA.mp3"
    title       TEXT,                          -- yt-dlp 取得的影片標題
    source_url  TEXT,                          -- 下載來源 URL
    duration    INTEGER,                       -- 時長（秒）
    format      TEXT,                          -- "mp3" / "mp4"
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 標籤主表
CREATE TABLE tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,                 -- "LiSA"
    category    TEXT NOT NULL,                 -- "artist" / "anime" / "type" / "custom"
    parent_id   INTEGER REFERENCES tags(id),   -- 階層式標籤：火影忍者 → 疾風傳
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, category)
);

-- 歌曲-標籤 多對多關聯表
CREATE TABLE song_tags (
    song_id     INTEGER REFERENCES songs(id) ON DELETE CASCADE,
    tag_id      INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    confidence  REAL DEFAULT 1.0,             -- 自動標記的信心度（0~1）
    source      TEXT DEFAULT 'auto',          -- "auto" / "manual" / "ytdlp"
    PRIMARY KEY (song_id, tag_id)
);

-- 標籤同義詞表
CREATE TABLE tag_synonyms (
    tag_id      INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    synonym     TEXT NOT NULL,                -- "NARUTO", "ナルト"
    PRIMARY KEY (tag_id, synonym)
);

-- 建立索引
CREATE INDEX idx_tags_category ON tags(category);
CREATE INDEX idx_song_tags_song ON song_tags(song_id);
CREATE INDEX idx_song_tags_tag ON song_tags(tag_id);
CREATE INDEX idx_tag_synonyms ON tag_synonyms(synonym);
```

### 為什麼這樣設計

1. **songs 表** — 歌曲的基本資訊，`filename` 唯一。與 ChromaDB 透過 filename 關聯
2. **tags 表** — 標籤定義，`(name, category)` 唯一避免重複。`parent_id` 支援階層
3. **song_tags 表** — 多對多關聯，一首歌可以有多個標籤。`confidence` 記錄自動標記的信心度，`source` 區分自動/手動
4. **tag_synonyms 表** — 同義詞查找，query 時先經過這張表正規化

### 與 ChromaDB 的分工

```
ChromaDB:                          SQLite:
├── 語意向量（embeddings）           ├── 歌曲基本資訊（songs）
├── 檔名（documents）               ├── 標籤定義（tags）
├── 向量搜尋（query）                ├── 歌曲-標籤關聯（song_tags）
└── 相似度計算                      ├── 同義詞（tag_synonyms）
                                    └── 結構化篩選（SQL query）
```

---

## 3. Implementation Steps

### Phase 1：SQLite 基礎建設

**新增檔案：** `database.py`

```python
import sqlite3
import os
from contextlib import contextmanager

DB_FILE = "mediadl.db"

def init_db():
    """建立資料庫和表結構（如果不存在）"""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            filepath TEXT NOT NULL,
            title TEXT,
            source_url TEXT,
            duration INTEGER,
            format TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            parent_id INTEGER REFERENCES tags(id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name, category)
        );
        CREATE TABLE IF NOT EXISTS song_tags (
            song_id INTEGER REFERENCES songs(id) ON DELETE CASCADE,
            tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'auto',
            PRIMARY KEY (song_id, tag_id)
        );
        CREATE TABLE IF NOT EXISTS tag_synonyms (
            tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
            synonym TEXT NOT NULL,
            PRIMARY KEY (tag_id, synonym)
        );
        CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category);
        CREATE INDEX IF NOT EXISTS idx_song_tags_song ON song_tags(song_id);
        CREATE INDEX IF NOT EXISTS idx_song_tags_tag ON song_tags(tag_id);
    """)
    conn.commit()
    conn.close()

@contextmanager
def get_db():
    """取得 DB 連線的 context manager"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**改動位置：** `main.py` — app 啟動時呼叫 `init_db()`

```python
from database import init_db, get_db
init_db()  # 加在 app = FastAPI() 之後
```

**注意事項：**
- SQLite 是 thread-safe 的（WAL mode），但每個 thread 要用自己的 connection
- FastAPI 的背景任務（`run_download`）在不同 thread 執行，要確保用 `get_db()` context manager
- `mediadl.db` 要加入 `.gitignore`

**預估改動量：** 新增 `database.py` ~80 行，main.py ~5 行

---

### Phase 2：標籤 CRUD API

**改動位置：** `main.py` — 新增 API 端點

```python
# === 標籤管理 API ===

@app.get("/tags")
async def get_all_tags(category: str = None):
    """取得所有標籤，可按 category 篩選"""
    with get_db() as db:
        if category:
            rows = db.execute(
                "SELECT t.*, COUNT(st.song_id) as song_count "
                "FROM tags t LEFT JOIN song_tags st ON t.id = st.tag_id "
                "WHERE t.category = ? GROUP BY t.id ORDER BY song_count DESC",
                (category,)
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT t.*, COUNT(st.song_id) as song_count "
                "FROM tags t LEFT JOIN song_tags st ON t.id = st.tag_id "
                "GROUP BY t.id ORDER BY song_count DESC"
            ).fetchall()
        return [dict(r) for r in rows]

@app.get("/tags/{tag_id}/songs")
async def get_songs_by_tag(tag_id: int):
    """取得某標籤下的所有歌曲"""
    with get_db() as db:
        rows = db.execute(
            "SELECT s.*, st.confidence, st.source "
            "FROM songs s JOIN song_tags st ON s.id = st.song_id "
            "WHERE st.tag_id = ?",
            (tag_id,)
        ).fetchall()
        return [dict(r) for r in rows]

@app.post("/songs/{song_id}/tags")
async def add_tag_to_song(song_id: int, tag_name: str = Form(...), category: str = Form(...)):
    """手動為歌曲新增標籤"""
    with get_db() as db:
        # 找或建立 tag
        tag = db.execute(
            "SELECT id FROM tags WHERE name = ? AND category = ?",
            (tag_name, category)
        ).fetchone()
        if not tag:
            cursor = db.execute(
                "INSERT INTO tags (name, category) VALUES (?, ?)",
                (tag_name, category)
            )
            tag_id = cursor.lastrowid
        else:
            tag_id = tag["id"]

        # 建立關聯
        db.execute(
            "INSERT OR IGNORE INTO song_tags (song_id, tag_id, source) VALUES (?, ?, 'manual')",
            (song_id, tag_id)
        )
    return {"status": "success"}

@app.delete("/songs/{song_id}/tags/{tag_id}")
async def remove_tag_from_song(song_id: int, tag_id: int):
    """移除歌曲的某個標籤"""
    with get_db() as db:
        db.execute(
            "DELETE FROM song_tags WHERE song_id = ? AND tag_id = ?",
            (song_id, tag_id)
        )
    return {"status": "success"}

@app.get("/songs/filter")
async def filter_songs(tags: str = ""):
    """
    多標籤篩選：?tags=1,3,5 → 回傳同時擁有 tag 1, 3, 5 的歌曲
    """
    if not tags:
        with get_db() as db:
            rows = db.execute("SELECT * FROM songs ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    tag_ids = [int(t) for t in tags.split(",")]
    placeholders = ",".join("?" * len(tag_ids))

    with get_db() as db:
        rows = db.execute(f"""
            SELECT s.* FROM songs s
            JOIN song_tags st ON s.id = st.song_id
            WHERE st.tag_id IN ({placeholders})
            GROUP BY s.id
            HAVING COUNT(DISTINCT st.tag_id) = ?
            ORDER BY s.created_at DESC
        """, tag_ids + [len(tag_ids)]).fetchall()
        return [dict(r) for r in rows]
```

**注意事項：**
- `filter_songs` 的 SQL 用 `HAVING COUNT = len(tag_ids)` 實現 AND 邏輯（必須擁有所有指定標籤）
- 如果要 OR 邏輯，拿掉 `HAVING` 即可
- tag_ids 從 query parameter 傳入時要驗證是否為合法整數，避免 SQL injection
- 使用參數化查詢（`?`），不直接拼接字串

**預估改動量：** main.py ~100 行

---

### Phase 3：下載流程整合自動標籤

**改動位置：** `main.py` — `run_download()` 函式

**現在的流程：**
```
下載 → 更新向量庫 → 通知完成
```

**改成：**
```
下載 → 擷取 metadata → 解析標題 → 存入 songs 表 → 自動打標籤 → 更新向量庫 → 通知完成
```

```python
def run_download(url, ydl_opts, requested_quality=None, format_type=None):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # === 新增：擷取 metadata 並自動標籤 ===
        title = info.get("title", "")
        artist = info.get("artist") or info.get("uploader") or ""
        album = info.get("album") or ""
        duration = info.get("duration")
        filename = ydl.prepare_filename(info)  # 取得實際檔名
        basename = os.path.basename(filename)
        ext = os.path.splitext(basename)[1].lstrip(".")

        # 1. 存入 songs 表
        with get_db() as db:
            db.execute("""
                INSERT OR REPLACE INTO songs (filename, filepath, title, source_url, duration, format)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (basename, filename, title, url, duration, ext))
            song_id = db.execute(
                "SELECT id FROM songs WHERE filename = ?", (basename,)
            ).fetchone()["id"]

        # 2. 自動打標籤
        auto_tag_song(song_id, title, artist, album)

        # 3. 更新向量庫（現有邏輯）
        ...
```

**自動標籤邏輯：**

```python
from utils.title_parser import parse_title

def auto_tag_song(song_id: int, title: str, artist: str, album: str):
    """自動為歌曲打標籤"""
    parsed = parse_title(title)

    tags_to_add = []

    # 歌手標籤
    final_artist = parsed.get("artist") or artist
    if final_artist:
        tags_to_add.append(("artist", final_artist, 0.9 if artist else 0.6))

    # 作品標籤
    anime = parsed.get("anime") or album
    if anime:
        tags_to_add.append(("anime", anime, 0.7))

    # 曲目類型標籤
    song_type = parsed.get("song_type")
    if song_type:
        tags_to_add.append(("type", song_type, 0.8))

    # 寫入資料庫
    with get_db() as db:
        for category, name, confidence in tags_to_add:
            # 檢查同義詞
            synonym_match = db.execute(
                "SELECT tag_id FROM tag_synonyms WHERE synonym = ?",
                (name,)
            ).fetchone()

            if synonym_match:
                tag_id = synonym_match["tag_id"]
            else:
                # 找或建立 tag
                tag = db.execute(
                    "SELECT id FROM tags WHERE name = ? AND category = ?",
                    (name, category)
                ).fetchone()
                if tag:
                    tag_id = tag["id"]
                else:
                    cursor = db.execute(
                        "INSERT INTO tags (name, category) VALUES (?, ?)",
                        (name, category)
                    )
                    tag_id = cursor.lastrowid

            db.execute(
                "INSERT OR REPLACE INTO song_tags (song_id, tag_id, confidence, source) "
                "VALUES (?, ?, ?, 'auto')",
                (song_id, tag_id, confidence)
            )
```

**注意事項：**
- `ydl.prepare_filename(info)` 取得的是 yt-dlp 預期的輸出檔名，但 postprocessor 可能改副檔名（例如 .webm → .mp3）
- 需要確認最終實際存在的檔名
- `confidence` 值：yt-dlp 原生 metadata = 0.9，regex 解析 = 0.6-0.8

**預估改動量：** main.py ~60 行，新增 `utils/auto_tagger.py` ~80 行

---

### Phase 4：同步資料夾時建立標籤

**改動位置：** `main.py` — `/db/sync` 端點

目前 `/db/sync` 只建向量索引。改成同時建立 songs 記錄和標籤。

```python
@app.post("/db/sync")
async def sync_library():
    global collection
    target_dir = current_config["download_dir"]

    # 1. 重建向量索引（現有邏輯）
    vector_client.delete_collection("my_music")
    collection = vector_client.get_or_create_collection(...)
    files = [f for f in os.listdir(target_dir) if f.endswith(('.mp3', '.mp4'))]
    ...

    # 2. 新增：同步 SQLite
    with get_db() as db:
        for f in files:
            filepath = os.path.join(target_dir, f)
            ext = os.path.splitext(f)[1].lstrip(".")

            # 插入或更新 songs 表
            db.execute("""
                INSERT OR IGNORE INTO songs (filename, filepath, format)
                VALUES (?, ?, ?)
            """, (f, filepath, ext))

            song = db.execute(
                "SELECT id FROM songs WHERE filename = ?", (f,)
            ).fetchone()

            # 對已有檔案用 regex 解析檔名自動標籤
            # （這些檔案沒有 yt-dlp metadata，只能靠檔名）
            auto_tag_song(song["id"], os.path.splitext(f)[0], "", "")

    # 3. 清理：刪除資料庫中存在但檔案已不存在的記錄
    with get_db() as db:
        existing_files = set(files)
        db_songs = db.execute("SELECT id, filename FROM songs").fetchall()
        for song in db_songs:
            if song["filename"] not in existing_files:
                db.execute("DELETE FROM songs WHERE id = ?", (song["id"],))
```

**注意事項：**
- 同步可能耗時較長（如果有幾百首歌），考慮回傳進度
- 清理孤立的 tag（沒有任何歌曲關聯的 tag）可以延後做
- 同步不應該覆蓋使用者手動打的標籤（`source = 'manual'`）

---

### Phase 5：同義詞偵測與合併

**改動位置：** 新增 `utils/synonym_detector.py`

```python
def detect_synonyms(embedding_model, db):
    """
    掃描所有標籤，用向量距離偵測可能的同義詞。
    回傳建議合併的標籤對。
    """
    tags = db.execute("SELECT id, name, category FROM tags").fetchall()

    if len(tags) < 2:
        return []

    names = [t["name"] for t in tags]
    embeddings = embedding_model.encode(names)

    suggestions = []
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            # 只比較同 category 的標籤
            if tags[i]["category"] != tags[j]["category"]:
                continue

            # 計算 cosine similarity
            sim = cosine_similarity(embeddings[i], embeddings[j])
            if sim > 0.85:  # 閾值可調整
                suggestions.append({
                    "tag_a": dict(tags[i]),
                    "tag_b": dict(tags[j]),
                    "similarity": round(float(sim), 4),
                })

    return suggestions
```

**API 端點：**

```python
@app.get("/tags/synonyms/detect")
async def detect_tag_synonyms():
    """偵測可能的同義標籤"""
    with get_db() as db:
        suggestions = detect_synonyms(embedding_model, db)
    return {"suggestions": suggestions}

@app.post("/tags/merge")
async def merge_tags(keep_id: int = Form(...), remove_id: int = Form(...)):
    """合併兩個標籤：將 remove_id 的所有關聯轉移到 keep_id"""
    with get_db() as db:
        # 取得被合併標籤的名稱，存為同義詞
        removed = db.execute("SELECT name FROM tags WHERE id = ?", (remove_id,)).fetchone()
        if removed:
            db.execute(
                "INSERT OR IGNORE INTO tag_synonyms (tag_id, synonym) VALUES (?, ?)",
                (keep_id, removed["name"])
            )

        # 轉移關聯
        db.execute(
            "UPDATE OR IGNORE song_tags SET tag_id = ? WHERE tag_id = ?",
            (keep_id, remove_id)
        )

        # 刪除已合併的標籤
        db.execute("DELETE FROM song_tags WHERE tag_id = ?", (remove_id,))
        db.execute("DELETE FROM tags WHERE id = ?", (remove_id,))

    return {"status": "success"}
```

**Concern：**
- 向量距離閾值（0.85）需要實測調整
- `NARUTO` 和 `火影忍者` 可能不夠近（跨語言翻譯而非同義詞）
- "Diver"（歌名）vs "Diver"（其他意思完全不同的東西）— 同名但不同義
- **建議：** 同義詞偵測只做「建議」，不自動合併，讓使用者確認

**預估改動量：** 新增 `utils/synonym_detector.py` ~60 行，main.py ~40 行

---

### Phase 6：前端標籤管理 UI

**改動位置：** `templates/index.html`、`static/js/index.js`、`static/css/index.css`

#### 6.1 側邊欄改造

現在側邊欄只有一個扁平的檔案清單。改成：

```
音樂庫管理
├── 📁 選擇資料夾          [選擇資料夾]
├── 🔄 同步本地資料夾       [同步按鈕]
├── ─────────────────────
├── 🏷️ 標籤篩選
│   ├── 歌手 ▼
│   │   ├── ☑ LiSA (5)
│   │   ├── ☐ NICO Touches the Walls (3)
│   │   └── 更多...
│   ├── 作品 ▼
│   │   ├── ☑ 鬼滅之刃 (4)
│   │   ├── ☐ 火影忍者 (8)
│   │   └── 更多...
│   └── 類型 ▼
│       ├── ☐ OP (12)
│       └── ☐ ED (7)
├── ─────────────────────
├── 📋 篩選結果 (5 首)
│   ├── 紅蓮華 - LiSA.mp3
│   │   └── 🏷 鬼滅之刃 · LiSA · OP    [✏️]
│   ├── 炎 - LiSA.mp3
│   │   └── 🏷 鬼滅之刃 · LiSA · IN    [✏️]
│   └── ...
```

#### 6.2 標籤顯示元件

每首歌下方顯示標籤（badge）：

```html
<div class="song-tags">
    <span class="badge bg-primary">LiSA</span>
    <span class="badge bg-success">鬼滅之刃</span>
    <span class="badge bg-info">OP</span>
    <button class="badge bg-light text-dark">+ 新增標籤</button>
</div>
```

#### 6.3 標籤編輯

點擊 ✏️ 或 「+ 新增標籤」彈出編輯面板：
- 下拉選單選擇 category（歌手/作品/類型/自訂）
- 文字輸入標籤名稱（帶 autocomplete，從現有標籤中建議）
- 顯示自動標記的信心度（低信心度的標籤用虛線邊框）

#### 6.4 同義詞合併 UI

設定頁面或側邊欄底部：
- 「🔍 偵測同義標籤」按鈕
- 顯示建議合併的標籤對，附相似度分數
- 使用者點擊「合併」或「忽略」

**預估改動量：** index.html ~80 行，index.js ~200 行，index.css ~40 行

---

## 4. 資料流圖

### 下載時的標籤流程

```
使用者點擊下載
      │
      ▼
yt-dlp extract_info + download
      │
      ├── info["title"]    → "火影忍者疾風傳 OP8 Diver [HD]"
      ├── info["artist"]   → "NICO Touches the Walls"（或 None）
      ├── info["album"]    → None
      │
      ▼
title_parser.parse_title(title)
      │
      ├── song_type: "OP"
      ├── type_number: 8
      ├── artist: None（regex 沒抓到）
      ├── song_name: "Diver"
      │
      ▼
合併 yt-dlp metadata + regex 結果
      │
      ├── artist = "NICO Touches the Walls"（來自 yt-dlp）
      ├── song_type = "OP"（來自 regex）
      │
      ▼
┌──────────────────────────────────┐
│ SQLite                            │
│ songs: INSERT 新歌曲              │
│ tags:  找或建 "NICO Touches..."   │
│        找或建 "OP"                │
│ song_tags: 建立關聯               │
└──────────────────────────────────┘
      │
      ▼
┌──────────────────────────────────┐
│ ChromaDB                          │
│ 更新向量索引（現有邏輯）            │
└──────────────────────────────────┘
      │
      ▼
WebSocket 通知完成
```

### 前端篩選流程

```
使用者在側邊欄勾選標籤（如 "LiSA" + "OP"）
      │
      ▼
GET /songs/filter?tags=3,7
      │
      ▼
SQLite 查詢：
SELECT s.* FROM songs s
JOIN song_tags st ON s.id = st.song_id
WHERE st.tag_id IN (3, 7)
GROUP BY s.id
HAVING COUNT(DISTINCT st.tag_id) = 2
      │
      ▼
回傳符合條件的歌曲清單
      │
      ▼
前端更新檔案清單
```

---

## 5. Concern Points

### 5.1 雙資料庫一致性

**問題：** ChromaDB 和 SQLite 是兩個獨立的資料庫，可能不一致。

**場景：**
- 使用者手動刪除了檔案，但兩個 DB 都還有記錄
- ChromaDB 同步了但 SQLite 沒同步，或反過來
- 程式在寫入 ChromaDB 後、寫入 SQLite 前 crash

**解決：**
- `/db/sync` 同時重建兩個資料庫
- 每次查詢時不信任 DB，檢查檔案是否實際存在
- 或者接受短暫不一致，因為 sync 會修正

### 5.2 前端效能

**問題：** 側邊欄同時需要載入：標籤清單（含計數）+ 篩選後的歌曲清單 + 每首歌的標籤

**建議：**
- 初始只載入 Top 20 標籤（按歌曲數排序）
- 歌曲清單分頁載入（每頁 50 首）
- 標籤的歌曲數用 SQL COUNT 在後端算好，不在前端計算

### 5.3 自動標籤準確度

**問題：** regex 解析和 yt-dlp metadata 都不可靠。

**預估準確度：**
| 來源 | 準確度 | 填充率 |
|------|--------|--------|
| yt-dlp `artist` | ~90% | ~60%（很多影片沒填） |
| yt-dlp `album` | ~70% | ~20%（很少填） |
| regex OP/ED | ~95% | ~30%（只有動漫歌有） |
| regex 歌手名 | ~60% | ~40%（格式太多樣） |

**建議：**
- 用 `confidence` 欄位記錄信心度
- 前端對低信心度的標籤（< 0.7）用不同樣式顯示（虛線邊框、淡化）
- 讓使用者一鍵確認或修改

### 5.4 非動漫內容

**問題：** 標籤維度（歌手/作品/OP/ED）為動漫音樂設計，不適用於所有音樂類型。

**解決：**
- 新增 `custom` category，讓使用者自訂標籤維度
- 例如「風格/搖滾」、「年代/2020s」、「播放清單/通勤用」
- 自動標籤只處理能辨識的部分，其餘交給使用者

### 5.5 SQLite 並發

**問題：** FastAPI 用多執行緒處理請求，SQLite 在 WAL mode 下支援一寫多讀，但多寫可能導致 `database is locked`。

**解決：**
- 使用 `timeout` 參數：`sqlite3.connect(DB_FILE, timeout=10)`
- 寫入操作盡量短，避免長時間持鎖
- 或使用 connection pool（例如 `aiosqlite`）

### 5.6 .gitignore

新增的檔案需要加入 `.gitignore`：
```
mediadl.db
mediadl.db-journal
mediadl.db-wal
mediadl.db-shm
```

---

## 6. 檔案異動清單

| 檔案 | 操作 | 說明 |
|------|------|------|
| `database.py` | 新增 | SQLite 初始化、連線管理 |
| `utils/__init__.py` | 新增 | Python package |
| `utils/title_parser.py` | 新增 | 標題解析（regex） |
| `utils/auto_tagger.py` | 新增 | 自動標籤邏輯 |
| `utils/synonym_detector.py` | 新增 | 同義詞偵測 |
| `main.py` | 修改 | 整合 DB 初始化、標籤 API、下載流程改造 |
| `templates/index.html` | 修改 | 側邊欄 UI 改造 |
| `static/js/index.js` | 修改 | 標籤篩選、編輯互動 |
| `static/css/index.css` | 修改 | 標籤 badge 樣式 |
| `.gitignore` | 修改 | 加入 mediadl.db |
| `pyproject.toml` | 不變 | SQLite 是 Python 內建，不需額外套件 |

---

## 7. 測試計畫

### 單元測試

```python
# test_database.py
def test_create_song():
    init_db()
    with get_db() as db:
        db.execute("INSERT INTO songs (filename, filepath, format) VALUES (?, ?, ?)",
                   ("test.mp3", "/path/test.mp3", "mp3"))
        song = db.execute("SELECT * FROM songs WHERE filename = ?", ("test.mp3",)).fetchone()
        assert song is not None
        assert song["format"] == "mp3"

def test_multi_tag():
    # 一首歌掛多個標籤
    ...

def test_filter_by_multiple_tags():
    # 多標籤 AND 篩選
    ...

def test_merge_tags():
    # 合併標籤後，歌曲關聯是否正確轉移
    ...
```

### 整合測試

1. 下載一首歌 → 確認 songs 表有記錄 → 確認自動標籤正確
2. 手動為歌曲添加標籤 → 確認 song_tags 有記錄
3. 篩選多個標籤 → 確認回傳結果正確
4. 同步資料夾 → 確認新檔案建立記錄、已刪除檔案清理
5. 偵測同義詞 → 確認建議合併的標籤合理
6. 合併標籤 → 確認歌曲關聯正確轉移、同義詞記錄正確

### 邊界測試

1. 空資料庫時所有 API 不報錯
2. 同一首歌重複下載不會建立重複記錄
3. 檔名含特殊字元（空格、括號、中文）時正常運作
4. 1000 首歌時的查詢效能

---

## 8. 優先順序建議

```
Phase 1（SQLite 基礎建設）→ 10 分鐘搞定，為其他 Phase 打基礎
      ↓
Phase 3（下載流程整合）→ 核心功能，讓新下載的歌自動有標籤
      ↓
Phase 4（同步整合）→ 讓舊歌也有標籤
      ↓
Phase 2（標籤 CRUD API）→ 提供前端需要的所有 API
      ↓
Phase 6（前端 UI）→ 使用者可見的功能
      ↓
Phase 5（同義詞偵測）→ 錦上添花，庫大了才需要
```

### 與 TODO 1（推薦清單）的依賴關係

```
TODO 2 Phase 1-4（標籤基礎建設）
      ↓
TODO 1 Phase 1-3（metadata + 推薦基礎）← 依賴標籤資料
      ↓
TODO 2 Phase 5-6（前端 + 同義詞）
      ↓
TODO 1 Phase 4-5（推薦 API + 前端）← 可以利用標籤做推薦
```

**結論：先做 TODO 2 的基礎建設（Phase 1-4），再做 TODO 1，最後回來補 TODO 2 的前端。**
