# Bee CRM 🐝

這是一套基於 Python PyQt6 開發的桌面 CRM 寄件標籤管理系統，直接串接 Google Sheets 作為資料來源。

---

## 🌟 核心特色

- **雲端資料庫**：直接與 Google Sheets 同步，無需維護本地資料庫
- **批量列印**：支援連續排版 PDF 產出，方便列印後裁切
- **智慧排版**：自動偵測公司名與收件人關係，自動帶入地址與電話
- **附加公司名稱**：新增配對時可選擇是否在收件人欄帶入公司名稱
- **i郵箱自動寄件**：透過 Playwright 自動驅動 EZPost 網站完成 i郵箱寄件流程（骨架完成，selector 待實測調整）

---

## 📋 版本紀錄

### v1.1（2026-05-22）
- 新增「附加公司名稱」核選方塊（位於「新增配對」按鈕左側）
  - 勾選：收件人欄帶入「公司名 人名」（原有格式）
  - 未勾選：收件人欄只帶人名
- 新增 i郵箱自動寄件功能架構
  - EZPost 帳密本機儲存（`~/.蜜蜂CRM_ibox_config.json`）
  - Playwright 自動化流程：登入 → 選 i郵箱 → 填收件人 → 填包裹 → 取得 QR Code
  - 跨執行緒進度對話框與驗證碼提示
- 更新 PyInstaller spec 至 macOS `.app` bundle 格式

### v1.0
- Google Sheets 資料同步（寄件者 / 客戶兩張表）
- 寄件人 × 客戶配對，批量輸出 PDF 標籤
- 待寄清單管理（新增、清空）
- 全文搜尋過濾

---

## 📊 Google Sheets 結構

### 「客戶」分頁
| A (ID) | B (公司名稱) | C (收件人) | D (地址) | E (郵遞區號) | F (電話) | G (統編) |
|:---|:---|:---|:---|:---|:---|:---|

### 「寄件者」分頁
| A (ID) | B (姓名) | C (地址) | D (郵遞區號) | E (電話) |
|:---|:---|:---|:---|:---|

---

## 🛠️ 開發環境

1. Python 3.12+
2. 建立虛擬環境並安裝依賴：
   ```bash
   pip install PyQt6 google-api-python-client google-auth-oauthlib reportlab pyinstaller playwright
   playwright install chromium
   ```
3. 放入你的 `credentials.json`（從 Google Cloud Console 取得，**請勿 commit**）

---

## 🚀 打包成 Mac App

```bash
python3 -m venv /tmp/build_venv
/tmp/build_venv/bin/pip install PyQt6 reportlab google-auth google-auth-oauthlib google-api-python-client playwright pyinstaller
/tmp/build_venv/bin/pyinstaller 蜜蜂CRM.spec --clean -y --distpath /tmp/crm_dist --workpath /tmp/crm_build
# 完成後 .app 在 /tmp/crm_dist/蜜蜂CRM.app
```

> 注意：首次開啟未簽署的 .app 請右鍵 → 開啟 → 再點開啟，繞過 Gatekeeper。

---

## ⚙️ i郵箱環境設定

```bash
bash setup_ibox.sh
```

---

*Powered by 龍蝦夥計 🦞*
