# websocket.js 解析

> **路徑：** `static/js/websocket.js`
>
> **角色：** 負責建立 WebSocket 連線，接收後端推送的下載進度與狀態訊息，即時更新前端 UI。
>
> **重要度：** ⭐⭐（即時通訊的前端部分，結構簡潔但不可或缺）

---

## 檔案結構概覽

```
websocket.js
├── [L1-2]    WebSocket 連線建立
└── [L4-33]   onmessage 事件處理
              ├── progress 訊息 → 更新進度條
              └── status 訊息 → 更新文字 / 完成通知
```

---

## 逐段解析

### 1. WebSocket 連線建立（L1-2）

```javascript
// const socket = new WebSocket(`ws://${window.location.host}/ws`);
const socket = new WebSocket("ws://127.0.0.1:8000/ws");
```

- 硬編碼連線到 `127.0.0.1:8000`
- 被註解的那行是正確的動態寫法

**Enhancement 注意：** 
- ❗ 目前是硬編碼 localhost，部署到其他環境會連不上。應改用被註解掉的動態寫法：
  ```javascript
  const socket = new WebSocket(`ws://${window.location.host}/ws`);
  ```
- 沒有斷線重連機制。如果 WebSocket 斷線，用戶不會收到任何進度更新，也不會有提示。建議加入自動重連邏輯。

---

### 2. 訊息處理（L4-33）

```javascript
socket.onmessage = function(event) {
    const msg = JSON.parse(event.data);
    // ...
};
```

後端透過 WebSocket 推送兩種類型的 JSON 訊息：

#### 訊息格式定義

| type | data 範例 | 觸發時機 |
|------|-----------|----------|
| `progress` | `"45"` | yt-dlp 下載過程中，每變化 1% 推送一次 |
| `status` | `"下載完成，正在轉檔與優化音量..."` | 下載完成、開始後處理 |
| `status` | `"✅ 下載已完成！"` | 整個流程結束 |

#### progress 處理

```javascript
if (msg.type === 'progress') {
    bar.style.width = msg.data + '%';
    status.innerText = `下載中: ${msg.data}%`;
}
```

- 直接將百分比數值設為進度條的寬度
- 更新文字顯示

#### status 處理

```javascript
else if (msg.type === 'status') {
    status.innerText = msg.data;
    if (msg.data.includes('✅')) {
        submitBtn.disabled = false;     // 恢復按鈕
        footer.classList.add('d-none'); // 隱藏進度區
        alert(msg.data);               // 彈窗通知
    }
}
```

- 判斷方式：用 `msg.data.includes('✅')` 檢查是否為完成訊息
- 完成時：恢復下載按鈕 → 隱藏進度區 → 彈窗通知

**Enhancement 注意：**
- 用 emoji `✅` 做訊息判斷比較脆弱。建議改為結構化的狀態碼（如 `msg.status === 'completed'`），前後端約定 enum。
- `alert()` 會阻塞頁面。建議改為 Bootstrap Toast 或自訂通知元件。
- 沒有處理錯誤訊息。如果後端下載失敗，前端不會得到通知，按鈕會永遠保持 disabled 狀態。

---

## 與其他檔案的協作關係

```
main.py                          websocket.js
┌─────────────────┐              ┌──────────────────┐
│ ConnectionManager│   WebSocket  │                  │
│   .broadcast()  │ ───────────▶ │  socket.onmessage│
│                 │              │                  │
│ progress_hook() │              │  → 更新進度條     │
│ run_download()  │              │  → 更新狀態文字   │
└─────────────────┘              │  → 恢復按鈕狀態   │
                                 └──────────────────┘
                                        │
                                        │ 操作 DOM
                                        ▼
                                 index.html
                                 (progress-bar, status-text,
                                  submit button, status-footer)
```

---

## 完整訊息生命週期

```
1. 用戶點擊下載
   └→ index.js POST /download

2. 後端啟動 BackgroundTask
   └→ run_download() 開始執行

3. yt-dlp 下載中
   └→ progress_hook() 每 1% 觸發一次
      └→ manager.broadcast({"type":"progress","data":"45"})
         └→ websocket.js 收到 → 進度條更新到 45%

4. yt-dlp 下載完成（開始 FFmpeg 後處理）
   └→ progress_hook(status='finished')
      └→ broadcast({"type":"status","data":"下載完成，正在轉檔..."})
         └→ websocket.js 收到 → 顯示轉檔中文字

5. FFmpeg 處理完成
   └→ run_download() 結束
      └→ broadcast({"type":"status","data":"✅ 下載已完成！"})
         └→ websocket.js 收到 → 恢復按鈕 + 隱藏進度 + alert
```
