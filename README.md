# Bee CRM 🐝🦞

這是一套基於 Python PyQt6 開發的跨平台桌面 CRM 寄件標籤管理系統。

## 🌟 核心特色
- **跨平台支援**: 支援 Windows (.exe) 與 macOS (.app) 打包。
- **雲端資料庫**: 直接與 Google Sheets 同步，無需維護本地資料庫。
- **批量列印**: 支援連續排版 PDF 產出，方便列印後裁切。
- **智慧排版**: 自動偵測公司名與收件人關係，自動帶入地址與電話。

## 📊 Google Sheets 結構要求
在您的 Google 試算表中，請建立以下兩個分頁：

### 1. 「客戶」分頁 (欄位順序)
| A (ID) | B (公司名稱) | C (收件人) | D (地址) | E (郵遞區號) | F (電話) | G (統編) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |

### 2. 「寄件者」分頁 (欄位順序)
| A (ID) | B (姓名) | C (地址) | D (郵遞區號) | E (電話) |
| :--- | :--- | :--- | :--- | :--- |

## 🛠️ 開發環境搭建
1. 安裝 Python 3.12+
2. 建立虛擬環境並安裝依賴:
   ```bash
   pip install PyQt6 google-api-python-client google-auth-oauthlib reportlab pyinstaller
   ```
3. 放入您的 `credentials.json` (從 Google Cloud Console 取得)。

## 🚀 打包方法
請參考專案中的 `PLAN.md` 獲取詳細打包指令。

---
*Powered by 龍蝦夥計 🦞*
