# index.html 解析

> **路徑：** `templates/index.html`
>
> **角色：** Jinja2 模板，定義前端頁面的 HTML 結構與 UI 佈局。
>
> **重要度：** ⭐⭐（UI 的骨架，新增任何 UI 元素都需要改這裡）

---

## 檔案結構概覽

```
index.html
├── <head>
│   ├── meta charset & viewport
│   ├── <title>
│   └── CSS 載入（bootstrap.min.css + index.css）
│
├── <body>
│   └── .container > .row > .col > .card
│       ├── <img#video-preview>          影片縮圖預覽區（預設隱藏）
│       ├── .card-body
│       │   ├── <h2>                     標題
│       │   └── <form#download-form>     下載表單
│       │       ├── url-input            網址輸入框
│       │       ├── format-select        格式選擇（MP4/MP3）
│       │       ├── quality-select       品質選擇
│       │       └── submit button        下載按鈕
│       │
│       └── #status-footer               進度顯示區（預設隱藏）
│           └── #progress-container
│               ├── .progress-bar        進度條
│               └── #status-text         狀態文字
│
└── JS 載入（bootstrap.bundle.min.js + index.js + websocket.js）
```

---

## 重要 DOM 元素對照表

以下列出所有帶 `id` 的元素，這些是 JavaScript 互動的入口：

| ID | 元素類型 | 由誰操作 | 用途 |
|----|----------|----------|------|
| `video-preview` | `<img>` | index.js | 顯示影片縮圖，預設 `d-none` 隱藏 |
| `url-input` | `<input type="url">` | index.js | 使用者輸入影片網址 |
| `format-select` | `<select>` | index.js | 選擇 MP4 / MP3 格式 |
| `quality-select` | `<select>` | index.js | 品質/位元率選擇（動態生成選項） |
| `download-form` | `<form>` | index.js | 下載表單，submit 事件被 JS 攔截 |
| `status-footer` | `<div>` | index.js / websocket.js | 進度區外層容器，控制顯示/隱藏 |
| `progress-container` | `<div>` | websocket.js | 進度條容器 |
| `progress-bar` | `<div>` | websocket.js | Bootstrap 進度條，用 `style.width` 控制 |
| `status-text` | `<p>` | websocket.js | 狀態文字（「下載中: 45%」、「轉檔中...」） |

---

## Jinja2 模板語法使用

```html
<!-- 靜態檔案的 URL 生成 -->
{{ url_for('static', path='/css/bootstrap.min.css') }}
{{ url_for('static', path='/js/index.js') }}

<!-- 模板變數（目前只有 name，未在頁面中使用） -->
{{ request }}
{{ name }}  <!-- 值為 "鐘啓仁"，由 main.py 傳入但頁面未顯示 -->
```

**Enhancement 注意：**
- `name` 變數被傳入模板但從未使用。可以移除，或用來顯示用戶名稱。
- `url_for('static', ...)` 搭配 `BASE_DIR` 判斷，確保打包為 exe 後靜態檔案仍可正確載入。

---

## UI 佈局解析

```
┌──────────────────────────────────┐
│          影片縮圖預覽             │  ← #video-preview (預設隱藏)
├──────────────────────────────────┤
│                                  │
│      🎬 YT 下載器               │  ← <h2> 標題
│                                  │
│  ┌────────────────────────────┐  │
│  │  影片網址: [____________]  │  │  ← #url-input
│  └────────────────────────────┘  │
│                                  │
│  ┌─────────┐  ┌─────────┐       │
│  │ 檔案格式 │  │ 品質設定 │       │  ← #format-select + #quality-select
│  │ [MP4 ▾] │  │ [最佳 ▾] │       │
│  └─────────┘  └─────────┘       │
│                                  │
│  ┌────────────────────────────┐  │
│  │      🚀 開始下載            │  │  ← submit button
│  └────────────────────────────┘  │
│                                  │
├──────────────────────────────────┤
│  ████████████░░░░░░ 45%          │  ← #progress-bar + #status-text
│  下載中: 45%                     │     (預設隱藏)
└──────────────────────────────────┘
```

---

## RWD 響應式設計

```html
<div class="col-12 col-md-8 col-lg-6">
```

| 螢幕寬度 | 卡片佔比 |
|----------|---------|
| < 768px (手機) | 100% 全寬 |
| 768px-992px (平板) | 8/12 = 66.7% |
| > 992px (桌面) | 6/12 = 50% |

---

## Enhancement 注意

- 頁面 `<title>` 還是寫 `YouTube Downloader`，應改為 `MediaDL`
- `<h2>` 標題寫 `🎬 YT 下載器`，應同步改名
- `<label>` 寫 `YouTube 影片網址`，應改為泛稱
- 格式選擇只有 MP4 / MP3 兩種，若要加新格式（如 WAV、FLAC）需在此新增 `<option>` 並同步修改 `main.py` 和 `index.js`
- 進度條用了 Bootstrap 的 `progress-bar-animated` 動畫效果 + `transition: width 0.3s` 過渡
