# index.css 解析

> **路徑：** `static/css/index.css`
>
> **角色：** 自定義樣式，覆蓋或補充 Bootstrap 預設樣式，針對卡片外觀和進度條做微調。
>
> **重要度：** ⭐（樣式微調，改動頻率低）

---

## 完整程式碼解析

```css
/* 卡片圓角：覆蓋 Bootstrap 預設的小圓角，改為更大的 15px */
.card {
    border-radius: 15px;
    overflow: hidden;    /* 確保子元素（如縮圖）不會超出圓角 */
}

/* 進度條容器的內邊距 */
#progress-container {
    padding: 10px;
}

/* 進度條背景：淺灰底色 + 內陰影，營造「凹陷」效果 */
.progress {
    background-color: #f0f0f0;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.1);
}

/* 狀態文字：略小字體 + 字距加寬，提升可讀性 */
#status-text {
    font-size: 0.9rem;
    letter-spacing: 0.5px;
}
```

---

## 與 Bootstrap 的搭配關係

本專案的樣式幾乎完全依賴 Bootstrap 5，`index.css` 只做了最少的自定義：

| Bootstrap 負責 | index.css 負責 |
|----------------|----------------|
| 佈局系統 (grid, container) | 卡片圓角加大 |
| 按鈕、表單、下拉選單樣式 | 進度條背景凹陷效果 |
| 進度條動畫 (`progress-bar-animated`) | 狀態文字大小調整 |
| 顯示/隱藏工具 (`d-none`) | — |
| 間距系統 (`py-5`, `mb-3`) | — |

---

## Enhancement 注意

- `feature-ai_recommend` 分支大幅擴充了此檔案（增加約 80 行），新增了相似檔案列表、相似度標籤（紅/黃色）、側邊欄等樣式。
- 若要修改 UI 主題色（目前下載按鈕是 Bootstrap 的 `btn-danger` 紅色），直接在 HTML 改 class 即可，不需改此檔案。
- 若要做大規模的深色模式或主題切換，建議使用 CSS Custom Properties（變數）。
