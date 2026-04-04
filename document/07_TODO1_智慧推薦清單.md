# TODO 1：智慧推薦清單 — Implementation Plan

## 目標概述

讓系統能自動辨識歌曲內容，跨越不同命名風格（動漫標題 vs 歌手標題）建立推薦關聯，在使用者貼上網址或瀏覽音樂庫時，推薦相關歌曲。

---

## 1. 現況分析

### 目前系統已有的能力

```python
# main.py - preview 路由已能做向量比對
query_vec = embedding_model.encode([title]).tolist()
results = collection.query(query_embeddings=query_vec, n_results=total_count)
```

- ChromaDB 已存所有檔案的語意向量
- SentenceTransformer 可以把標題轉成 384 維向量
- preview 路由已能回傳 `similar_files`（相似度 > 60%）

### 目前的不足

1. **向量只編碼檔名** — 缺少歌手、動漫名等結構化資訊
2. **沒有「推薦」的概念** — 只有「重複偵測」（相似度高 = 可能重複），沒有「你可能也喜歡」
3. **沒有元資料** — ChromaDB 裡只存 `documents`（檔名）和 `embeddings`（向量），沒有 metadata

---

## 2. 核心難題：標題解析

### 問題本質

同一首歌可能有完全不同的標題格式：

```
標題 A: "火影忍者疾風傳OP 8 Diver [HD] [Full]"
標題 B: "Diver · NICO Touches the Walls"
標題 C: "Naruto Shippuden OP 8 Full - Diver by NICO Touches the Walls"
標題 D: "【MAD】ナルト疾風伝 / Diver"
標題 E: "diver nico touches the walls lyrics"
```

要做推薦，就必須從這些標題中提取出：
- 歌曲名：Diver
- 歌手：NICO Touches the Walls
- 作品：火影忍者疾風傳 / Naruto Shippuden
- 類型：OP
- 編號：8

### 解決方案比較

| 方案 | 優點 | 缺點 | 適合度 |
|------|------|------|--------|
| **A. Regex 規則解析** | 本地、免費、快 | 格式太多，永遠寫不完 | ❌ 不可行 |
| **B. yt-dlp metadata** | 免費、已有資料 | YouTube 不一定有填 artist/album | ⭐ 首選 fallback |
| **C. 呼叫 LLM API** | 最準確、能理解任意格式 | 需要 API key、有費用、需網路 | ⭐ 最佳但有門檻 |
| **D. 本地小型 NER 模型** | 本地、免費 | 需要訓練資料、準確度不確定 | ⚠️ 備選 |
| **E. 純語意向量** | 已有基礎設施 | 不理解領域知識（見下方分析） | ⚠️ 不夠用 |

### 語意向量的局限（為什麼純向量不夠）

測試場景：
```
"火影忍者疾風傳 OP8 Diver" vs "Diver · NICO Touches the Walls"
```

`paraphrase-multilingual-MiniLM-L12-v2` 是通用文本模型：
- 「火影忍者疾風傳」→ 編碼為「日本動漫」相關的語意空間
- 「NICO Touches the Walls」→ 編碼為「樂團名稱」相關的語意空間
- 唯一交集是 "Diver"，但 "Diver" 在通用語意中也是「潛水員」的意思

**結論：** 純向量比對可能會把這兩個標題的相似度計算得**比預期低**，因為模型不理解「OP8 = 這首歌是片頭曲」這種領域知識。

### 建議採用的方案：yt-dlp metadata + Regex fallback + 可選 LLM

```
優先順序：
1. yt-dlp extract_info 回傳的 artist / album / track
2. Regex 規則擷取常見格式（OP/ED/歌手名等）
3. （可選）呼叫 LLM API 做最終解析
4. 若都失敗，只用原始標題向量
```

---

## 3. Implementation Steps

### Phase 1：擷取 yt-dlp 完整 metadata（低成本，高價值）

**改動位置：** `main.py` — `run_download()` 和 `/preview` 路由

**現況：** `extract_info()` 已經在呼叫了，但只取了 `title` 和 `thumbnail`。

**改動：** extract_info 回傳的 dict 其實包含大量資訊：

```python
info = ydl.extract_info(url, download=False)

# yt-dlp 可能回傳的欄位（視影片而定）
metadata = {
    "title":       info.get("title"),           # "Diver · NICO Touches the Walls"
    "artist":      info.get("artist"),           # "NICO Touches the Walls"（不一定有）
    "album":       info.get("album"),            # 可能是動漫名
    "track":       info.get("track"),            # 歌曲名
    "uploader":    info.get("uploader"),          # 上傳者頻道名
    "channel":     info.get("channel"),           # 頻道名
    "description": info.get("description", ""),   # 影片描述（常包含歌曲資訊）
    "tags":        info.get("tags", []),           # 影片標籤
    "categories":  info.get("categories", []),     # 影片分類
    "duration":    info.get("duration"),           # 時長（秒）
}
```

**具體 TODO：**
1. 在 `/preview` 路由中，把這些欄位一起回傳給前端
2. 在 `run_download()` 中，把這些 metadata 存進 ChromaDB 的 `metadatas` 欄位
3. 前端顯示已知的歌手/作品資訊（如果 yt-dlp 有回傳的話）

**預估改動量：** main.py ~30 行，index.js ~20 行

---

### Phase 2：Regex 規則擷取常見格式

**改動位置：** 新增 `utils/title_parser.py`

從標題中用 regex 擷取結構化資訊，作為 yt-dlp metadata 的補充：

```python
import re

def parse_title(title: str) -> dict:
    """
    從影片標題中擷取結構化資訊。
    回傳 dict，每個欄位可能為 None。
    """
    result = {
        "anime": None,
        "song_type": None,    # OP / ED / IN / OST
        "type_number": None,  # 第幾首 OP/ED
        "artist": None,
        "song_name": None,
    }

    # 擷取 OP/ED 編號
    # 匹配: "OP 8", "OP8", "ED 3", "Opening 2"
    op_ed_match = re.search(
        r'\b(OP|ED|Opening|Ending|IN|Insert|OST)\s*(\d+)?\b',
        title, re.IGNORECASE
    )
    if op_ed_match:
        type_map = {
            'op': 'OP', 'opening': 'OP',
            'ed': 'ED', 'ending': 'ED',
            'in': 'IN', 'insert': 'IN',
            'ost': 'OST'
        }
        result["song_type"] = type_map.get(op_ed_match.group(1).lower(), op_ed_match.group(1))
        result["type_number"] = int(op_ed_match.group(2)) if op_ed_match.group(2) else None

    # 擷取「歌手 - 歌名」或「歌名 · 歌手」格式
    # "Diver · NICO Touches the Walls"
    dot_match = re.match(r'^(.+?)\s*[·・]\s*(.+?)$', title)
    if dot_match:
        result["song_name"] = dot_match.group(1).strip()
        result["artist"] = dot_match.group(2).strip()

    # "NICO Touches the Walls - Diver"
    dash_match = re.match(r'^(.+?)\s*[-–—]\s*(.+?)$', title)
    if dash_match and not result["artist"]:
        result["artist"] = dash_match.group(1).strip()
        result["song_name"] = dash_match.group(2).strip()

    # 清理常見雜訊
    noise_patterns = [
        r'\[HD\]', r'\[Full\]', r'\[Official\s*(?:MV|Video)?\]',
        r'\(Official\s*(?:MV|Video)?\)', r'【.*?】',
        r'\bFull\s*(?:Version|Ver\.?|Size)\b',
        r'\blyrics?\b', r'\bMV\b', r'\bHD\b',
    ]
    # ... 進一步清理

    return result
```

**注意事項：**
- Regex 不可能覆蓋所有格式，這是 fallback 而不是主力
- 每個 regex 都要寫測試案例
- 遇到解析不到的格式就留 None，不要猜

**預估改動量：** 新增 `utils/title_parser.py` ~100 行，搭配測試 ~150 行

---

### Phase 3：改造 ChromaDB 資料結構

**改動位置：** `main.py` — `run_download()` 和 `/db/sync`

**現在的 collection.add：**
```python
collection.add(
    documents=files,
    embeddings=embeddings,
    ids=[f"file_{i}" for i in range(len(files))]
)
```

**改成：**
```python
collection.add(
    documents=files,
    embeddings=embeddings,
    ids=[f"file_{i}" for i in range(len(files))],
    metadatas=[{
        "artist": parsed.get("artist") or ytdlp_meta.get("artist") or "",
        "anime": parsed.get("anime") or "",
        "song_type": parsed.get("song_type") or "",
        "song_name": parsed.get("song_name") or "",
        "source_url": url,
        "download_date": datetime.now().isoformat(),
    } for ...]
)
```

**注意事項：**
- ChromaDB metadata value 只支援 `str`、`int`、`float`、`bool`，不支援 list
- 所以不能存 `"tags": ["LiSA", "鬼滅"]`，要拆成獨立欄位或用逗號分隔字串
- 同步資料夾時（`/db/sync`），舊檔案沒有 yt-dlp metadata，只能靠 regex 解析檔名

**Migration 策略：**
- 加入 metadata 後，舊索引需要重建（刪除再重建 collection）
- `db/sync` 端點已有重建邏輯，不需要額外的 migration

---

### Phase 4：推薦 API 端點

**改動位置：** `main.py` — 新增 `/recommend` 路由

```python
@app.get("/recommend")
async def get_recommendations(filename: str, limit: int = 10):
    """
    根據指定歌曲，推薦相關歌曲。
    推薦邏輯：
    1. 同歌手的其他歌
    2. 同動漫作品的其他歌
    3. 向量空間中的近鄰（語意相似）
    """
    # 1. 先從 metadata 找同歌手/同作品
    target = collection.get(
        where={"$or": [...]},
        include=["metadatas", "documents"]
    )

    # 2. 再用向量找語意相近的
    target_embedding = collection.get(
        where={"documents": filename},
        include=["embeddings"]
    )
    similar = collection.query(
        query_embeddings=target_embedding,
        n_results=limit
    )

    # 3. 合併去重，按相關性排序
    return {"recommendations": merged_results}
```

**注意事項：**
- ChromaDB 的 `$or` 查詢語法有限制，複雜查詢可能需要多次 query 再合併
- 推薦結果要排除自己
- 要處理 metadata 為空的情況（fallback 到純向量推薦）

---

### Phase 5：前端推薦 UI

**改動位置：** `templates/index.html`、`static/js/index.js`

**UI 設計：**
- 在側邊欄的檔案清單中，點選某首歌後展開「推薦相關歌曲」區塊
- 或在下載完成後，自動顯示「你的庫裡還有這些相關歌曲」
- 推薦結果顯示：歌名、相關原因（同歌手 / 同作品 / 語意相似）、相似度分數

---

### Phase 6（可選）：LLM 加強解析

**前置條件：** 使用者設定 API key（存入 config.json）

```python
# utils/llm_parser.py
import httpx

async def parse_title_with_llm(title: str, api_key: str) -> dict:
    """用 LLM 從標題中擷取結構化資訊"""
    prompt = f"""
    從以下影片標題中擷取資訊，回傳 JSON：
    - song_name: 歌曲名
    - artist: 歌手/樂團
    - anime: 動漫作品名（如果有）
    - song_type: OP/ED/IN/OST（如果有）

    標題：{title}
    """
    # 呼叫 OpenAI / Claude / 本地 LLM
    ...
```

**注意事項：**
- 這是可選功能，系統必須在沒有 LLM 的情況下也能運作
- 要設定 timeout 和 error handling
- 考慮快取結果，同一個標題不重複呼叫
- 注意 prompt injection：標題可能包含惡意內容

---

## 4. 資料流圖

```
使用者貼上 URL
      │
      ▼
yt-dlp extract_info(url, download=False)
      │
      ├── title, thumbnail（現有）
      ├── artist, album, track（新增擷取）
      │
      ▼
title_parser.parse_title(title)
      │
      ├── anime, song_type, artist, song_name（regex 擷取）
      │
      ▼
合併 yt-dlp metadata + regex 結果
      │
      ├──▶ 前端顯示元資料
      │
      ▼
向量比對 + metadata 查詢
      │
      ├── similar_files（現有 — 重複偵測）
      ├── recommendations（新增 — 同歌手/同作品/語意相近）
      │
      ▼
前端顯示推薦清單
```

---

## 5. Concern Points

### 5.1 效能

- **SentenceTransformer 編碼速度**：單次 encode 約 50-100ms，可接受
- **ChromaDB query**：小型資料庫（< 10000 首）延遲可忽略
- **LLM API 延遲**：500ms-3s，不適合同步呼叫。建議改為背景任務，先回傳基本結果，LLM 解析完再透過 WebSocket 更新

### 5.2 準確度

- Regex 解析預估覆蓋率：~40% 的標題能擷取到有用資訊
- yt-dlp metadata 填充率：YouTube 音樂影片約 ~60% 有 artist 欄位
- 兩者合計覆蓋率：~70%，剩下 30% 只能靠純向量

### 5.3 冷啟動

- 庫裡 < 5 首歌時，推薦沒有意義
- **建議：** 前端判斷，當庫檔案數 < 5 時隱藏推薦區塊
- 或顯示「歌曲數量不足，暫無推薦」

### 5.4 跨語言

- `paraphrase-multilingual-MiniLM-L12-v2` 支援中英日語，語意比對跨語言沒問題
- 但 regex 解析需要為中文、日文、英文分別寫規則
- 例如：「火影忍者」vs「ナルト」vs「Naruto」，regex 不可能知道這三個是同一個東西

### 5.5 推薦品質退化

- 隨著庫增長，純向量推薦會越來越不準（因為模型不懂音樂領域知識）
- **建議：** metadata 推薦（同歌手/同作品）優先，向量推薦只作為 fallback
- 前端明確標示推薦原因：「同歌手」vs「語意相似」，讓使用者自行判斷

### 5.6 隱私與安全

- 如果啟用 LLM API，影片標題會送到外部服務
- 要在設定頁面明確告知使用者
- 標題可能包含任意內容，送入 LLM 前要做基本的 input 清理

---

## 6. 測試計畫

### 單元測試

```python
# test_title_parser.py
def test_parse_op_format():
    result = parse_title("火影忍者疾風傳OP 8 Diver [HD] [Full]")
    assert result["song_type"] == "OP"
    assert result["type_number"] == 8

def test_parse_artist_dot():
    result = parse_title("Diver · NICO Touches the Walls")
    assert result["artist"] == "NICO Touches the Walls"
    assert result["song_name"] == "Diver"

def test_parse_unknown_format():
    result = parse_title("一些完全無法解析的標題")
    assert result["artist"] is None
    assert result["song_name"] is None
```

### 整合測試

1. 下載一首歌 → 確認 metadata 正確存入 ChromaDB
2. 下載同歌手的另一首歌 → 確認推薦 API 能回傳第一首
3. 同步一個有 20 首歌的資料夾 → 確認推薦結果合理
4. 庫裡只有 1 首歌 → 確認不會報錯

---

## 7. 優先順序建議

```
Phase 1（yt-dlp metadata）→ 最少工作量，最高價值
      ↓
Phase 3（ChromaDB 資料結構）→ 為後續功能打基礎
      ↓
Phase 2（Regex 解析）→ 補強 metadata 不足的部分
      ↓
Phase 4（推薦 API）→ 核心功能
      ↓
Phase 5（前端 UI）→ 使用者可見的產出
      ↓
Phase 6（LLM 加強）→ 錦上添花
```

先做 Phase 1 + 3，用最小成本驗證「metadata 對推薦有沒有幫助」，再決定是否繼續投入。
