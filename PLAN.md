# CRM 桌面板專案開發計畫 🦞🚀

## 1. 專案願景
將原有的 Flask Web 版 CRM 轉化為跨平台桌面應用程式 (Mac + PC)，並使用 Google Sheets 作為即時雲端後端資料庫。

## 2. 核心技術棧 (Tech Stack)
- **程式語言**: Python 3.12+
- **桌面 UI 框架**: PyQt6 (提供流暢、現代的跨平台介面)
- **雲端整合**: Google Sheets API v4
- **本地緩存**: JSON (用於斷網時的基礎讀取)
- **列印引擎**: ReportLab (產生成為 PDF 標籤) 或 Qt Print Support

## 3. 改寫架構分析
### A. 資料層 (Data Layer)
- **Google Sheets API**: 取代原本的 `customers.json`。
- **認證機制**: 使用 OAuth 2.0 (透過 `credentials.json`)。

### B. 功能模組 (Modules)
1. **MainWindow**: 主視窗導覽。
2. **CustomerManager**: 客戶清單展示、搜尋、新增與編輯。
3. **SenderConfig**: 寄件者資料設定與切換。
4. **LabelGenerator**: 根據所選客戶自動排版並產生物流標籤。
5. **AutoSync**: 定期將本地修改同步回雲端試算表。

## 4. 執行階段 (Milestones)
### 第一階段：環境搭建與 API 驗證
- [ ] 建立專案目錄結構。
- [ ] 整合 Google Cloud 認證 (OAuth)。
- [ ] 測試從 Google Sheets 成功讀取資料到 Python 變數。

### 第二階段：桌面 UI 開發
- [ ] 使用 PyQt6 建立基礎列表視窗。
- [ ] 實作資料表格 (QTableWidget) 與 Google Sheets 對接。

### 第三階段：標籤列印功能
- [ ] 移植 Flask 的 HTML 套版邏輯至 Pdf 產生器。
- [ ] 實作一鍵預覽與列印功能。

### 第四階段：打包與優化
- [ ] 使用 `PyInstaller` 打包為 .app (Mac) 與 .exe (PC)。

---
*龍蝦備註：本計畫將持續依據主人反饋進行滾動式更新。* 🦾🦞✨
