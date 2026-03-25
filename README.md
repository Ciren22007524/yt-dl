## 如何執行專案

### 1. **安裝依賴套件**
   ```bash
   poetry install
   ```

---

### 2. **執行方式**
   ```bash
   poetry run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

---

### 3. 進階小技巧：使用 `poetry shell`
如果你不想每次都打 `poetry run`，你可以先進入虛擬環境：

1. 輸入 `poetry shell`（進入環境）。
2. 直接輸入 `uvicorn main:app --reload`（不用加 host/port，除非你要改預設值）。

---

### 4. 注意事項（檢查清單）
* **檔名對應：** 你的指令寫 `main:app`，請確保你的主程式檔名真的是 `main.py`，且裡面定義的 FastAPI 實例變數名稱是 `app`。
* **.gitignore：** 因為你用了 Poetry，記得要把 `.venv/` 資料夾加到 `.gitignore` 中，不要推到 GitHub，別人只要有 `pyproject.toml` 就能透過 `poetry install` 還原環境。
* **Host 設定：** `--host 127.0.0.1` 代表只允許你自己電腦連線。如果你之後要把 `yt-downloader` 丟到 Docker 或是雲端主機（如 Render/GCP），記得要改成 `--host 0.0.0.0` 才能對外連線。

---

### 5. 自動化小撇步 (選用)
如果你覺得啟動指令太長，可以在 `pyproject.toml` 加入一個腳本設定，但最簡單的方式還是在 README 寫清楚就好。
