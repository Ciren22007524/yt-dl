# pyproject.toml 解析

> **路徑：** `pyproject.toml`
>
> **角色：** Poetry 專案設定檔，定義專案名稱、Python 版本需求、所有依賴套件及版本範圍。
>
> **重要度：** ⭐（一般不需修改，除非新增套件或調整版本）

---

## 檔案結構

```toml
[project]           # 專案基本資訊
[tool.poetry]       # Poetry 特定設定
[build-system]      # 建構系統設定
```

---

## 依賴套件解析

| 套件 | 版本範圍 | 角色 |
|------|----------|------|
| **fastapi** | `>=0.135.1,<0.136.0` | Web 框架，提供 API 路由、WebSocket、BackgroundTasks |
| **uvicorn** | `>=0.42.0,<0.43.0` | ASGI 伺服器，運行 FastAPI 應用 |
| **jinja2** | `>=3.1.6,<4.0.0` | 模板引擎，渲染 `index.html` |
| **aiofiles** | `>=25.1.0,<26.0.0` | 非同步檔案操作（FastAPI StaticFiles 依賴） |
| **yt-dlp** | `>=2026.3.13,<2027.0.0` | 核心下載引擎，支援上千個影音平台 |
| **python-multipart** | `>=0.0.22,<0.0.23` | 解析 `multipart/form-data`（FastAPI Form 依賴） |
| **imageio-ffmpeg** | `>=0.6.0,<0.7.0` | 內建 FFmpeg binary，用於音訊轉檔與音量標準化 |
| **websockets** | `>=16.0,<17.0` | WebSocket 協定實作（FastAPI WebSocket 依賴） |

---

## 關鍵設定

```toml
requires-python = ">=3.13,<3.15"
```
- 限制 Python 版本在 3.13 到 3.14 之間
- Python 3.13 是較新的版本需求，確保使用最新的語言特性

```toml
[tool.poetry]
package-mode = false
```
- 設為非套件模式 — 這是一個應用程式，不是要發布到 PyPI 的套件

---

## Enhancement 注意

### 版本鎖定策略
目前大部分依賴使用 **patch-level 鎖定**（如 `>=0.135.1,<0.136.0`），優點是穩定可預測，缺點是不會自動取得安全性更新。

### 新增套件的方式
```bash
# 使用 Poetry 新增（會自動更新 pyproject.toml 和 poetry.lock）
poetry add <package-name>

# 例如新增 AI 功能所需的套件
poetry add chromadb sentence-transformers
```

### feature-ai_recommend 分支額外需要的套件
AI 分支需要但基礎版 `pyproject.toml` 中未列出的套件：
- `chromadb` — 向量資料庫
- `sentence-transformers` — AI 語意嵌入模型

切換到該分支時需要重新 `poetry install`。
