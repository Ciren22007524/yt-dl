# index.js 解析

> **路徑：** `static/js/index.js`
>
> **角色：** 前端互動核心，負責格式切換、影片預覽、下載表單送出三大功能。
>
> **重要度：** ⭐⭐⭐（前端所有用戶互動邏輯都在這裡）

---

## 檔案結構概覽

```
index.js
├── [L1-6]    DOM 元素取得
├── [L8-43]   功能 1：格式切換（MP4 ↔ MP3 品質選項動態生成）
├── [L45-59]  功能 2：影片封面預覽（input → /preview API）
└── [L61-95]  功能 3：下載表單送出（submit → /download API）
```

---

## 逐段解析

### 1. DOM 元素取得（L1-6）

```javascript
const urlInput = document.getElementById('url-input');
const formatSelect = document.getElementById('format-select');
const qualitySelect = document.getElementById('quality-select');
const videoPreview = document.getElementById('video-preview');
const downloadForm = document.getElementById('download-form');
const footer = document.getElementById('status-footer');
```

一次性取得所有需要操作的 DOM 元素，避免重複查詢。

---

### 2. 格式切換（L8-43）

```javascript
formatSelect.addEventListener('change', () => {
    qualitySelect.innerHTML = '';  // 清空選項
    if (formatSelect.value === 'mp3') {
        // 動態生成 MP3 音質選項
    } else {
        // 動態生成 MP4 解析度選項
    }
});
```

切換格式時，動態重建品質下拉選單：

| 格式 | 品質選項 |
|------|----------|
| MP4 | 最佳品質 / 1080p / 720p / 480p |
| MP3 | 最佳音質 (value=`0`) / 320kbps / 256kbps / 192kbps / 128kbps |

**設計細節：**
- MP3 的 `value='0'` 對應 yt-dlp 的「最佳音質」設定（不限制 bitrate）
- 選項用 JavaScript 動態生成而非寫死在 HTML，方便程式化控制

**Enhancement 注意：**
- 品質選項是硬編碼的。如果要根據影片實際的可用格式動態顯示，需要在 `/preview` API 回傳 `formats` 資訊，再由前端動態渲染。
- 可以考慮加入 `WAV`、`FLAC` 等無損格式選項。

---

### 3. 影片封面預覽（L45-59）

```javascript
urlInput.addEventListener('input', async () => {
    const url = urlInput.value;
    if (url.includes('youtube.com/') || url.includes('youtu.be/')) {
        const response = await fetch(`/preview?url=${encodeURIComponent(url)}`);
        const data = await response.json();
        if (data.thumbnail) {
            videoPreview.src = data.thumbnail;
            videoPreview.classList.remove('d-none');
        }
    }
});
```

**行為：** 監聽輸入框的 `input` 事件，當偵測到 URL 包含特定關鍵字時，自動向後端 `/preview` API 取得縮圖。

**Enhancement 注意：**
- 目前只檢查 `youtube.com` 和 `youtu.be`，但 yt-dlp 支援上千個平台。建議移除平台限制，改為任何 URL 都去呼叫 `/preview`，由後端判斷是否支援。
- 沒有 debounce 機制 — 用戶每打一個字就觸發一次 API 呼叫。建議加入 300-500ms 的 debounce 避免頻繁請求。
- `encodeURIComponent(url)` 正確處理了 URL 編碼，這是必要的安全措施。

---

### 4. 下載表單送出（L61-95）

```javascript
downloadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    footer.classList.remove('d-none');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    const formData = new FormData(e.target);
    const response = await fetch('/download', { method: 'POST', body: formData });
    const result = await response.json();
    // ...
});
```

**流程：**
1. 阻止表單預設行為（避免頁面重新整理）
2. 顯示進度區域 + 禁用按鈕（防止重複點擊）
3. 用 `FormData` 自動收集表單資料（`url`, `format_type`, `quality`）
4. POST 到 `/download`
5. 根據回傳的 `status` 判斷是否啟動成功
6. 按鈕的恢復交由 `websocket.js` 處理（收到 ✅ 完成訊息才恢復）

**設計巧思：** 
- 按鈕不在 `finally` 中恢復，而是等 WebSocket 收到完成訊息才恢復 — 這避免了「背景還在下載但按鈕已可再次點擊」的問題。

**Enhancement 注意：**
- 錯誤處理只有 `alert('連線失敗')`，沒有具體的錯誤訊息。建議改為更友善的 Toast 通知。
- 目前不支援取消正在進行的下載。可以加一個「取消」按鈕。
- 沒有下載前的確認步驟（如顯示影片標題、預估檔案大小）。

---

## 與其他檔案的協作關係

```
index.js
    │
    ├── 讀取 → index.html 中的 DOM 元素 (id 對應)
    │
    ├── 呼叫 → main.py 的 GET /preview API
    │
    ├── 呼叫 → main.py 的 POST /download API
    │
    └── 配合 → websocket.js（按鈕狀態由 WS 完成訊息控制）
```
