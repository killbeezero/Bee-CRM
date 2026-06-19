import sys
import os
import subprocess
import platform
import threading
import json
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QHeaderView,
    QPushButton, QMessageBox, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QCheckBox,
    QSizePolicy, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4


# ── 資源路徑（PyInstaller 相容）──────────────────────────────
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


# ── 跨平台中文字體 ────────────────────────────────────────────
if platform.system() == "Windows":
    CHINESE_FONT_PATH = "C:\\Windows\\Fonts\\msyh.ttc"
else:
    CHINESE_FONT_PATH = "/System/Library/Fonts/STHeiti Light.ttc"

if not os.path.exists(CHINESE_FONT_PATH):
    pdfmetrics.registerFont(TTFont("ChineseFont", "STHeiti" if platform.system() != "Windows" else "MSJH"))
else:
    pdfmetrics.registerFont(TTFont("ChineseFont", CHINESE_FONT_PATH))


# ── 常數 ────────────────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = "1L5J_fIdRZidQpXIMBCRLYIzvyCp_1aTngROBE6M0DFc"

# i郵箱設定檔路徑（儲存帳密）
IBOX_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".蜜蜂CRM_ibox_config.json")

# 物品種類選項（對應 i郵箱 網站選單）
IBOX_ITEM_TYPES = ["空白文件", "食品", "零件", "貨樣", "禮品", "書籍", "衣物", "藥品", "日用品", "其他"]

# 包材尺寸（顯示名稱 → 網站標籤）
IBOX_SIZES = ["大 (34×24×45cm)", "中 (34×17×45cm)", "小 (14×17×45cm)"]
IBOX_SIZE_MAP = {"大 (34×24×45cm)": "大", "中 (34×17×45cm)": "中", "小 (14×17×45cm)": "小"}


# ── 台灣地址解析工具 ─────────────────────────────────────────
TAIWAN_COUNTIES = [
    "臺北市", "台北市", "新北市", "桃園市", "臺中市", "台中市",
    "臺南市", "台南市", "高雄市", "基隆市", "新竹市", "嘉義市",
    "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣",
    "屏東縣", "宜蘭縣", "花蓮縣", "臺東縣", "台東縣", "澎湖縣",
    "金門縣", "連江縣",
]
# 政府表單使用「臺」，CRM 可能存「台」→ 統一轉換
NORMALIZE_COUNTY = {
    "台北市": "臺北市", "台中市": "臺中市",
    "台南市": "臺南市", "台東縣": "臺東縣",
}


def parse_tw_address(full_addr: str):
    """
    解析完整台灣地址為 (縣市, 鄉鎮市區, 路街名, 號碼樓層)。
    例：「台北市信義區松仁路100號3樓」
     → ("臺北市", "信義區", "松仁路", "100號3樓")
    """
    county = district = road = detail = ""
    remaining = full_addr.strip()

    # 取出縣市
    for c in TAIWAN_COUNTIES:
        if remaining.startswith(c):
            county = NORMALIZE_COUNTY.get(c, c)
            remaining = remaining[len(c):]
            break

    # 取出鄉鎮市區（以「區/鎮/鄉/市」結尾）
    m = re.match(r'^(.+?[區鎮鄉市])(.*)', remaining)
    if m:
        district = m.group(1)
        remaining = m.group(2)

    # 切割路名與號碼（路名以「路/街/大道/道/巷」結尾）
    m2 = re.match(r'^(.+?[路街道])(.*)', remaining)
    if m2:
        road = m2.group(1)
        detail = m2.group(2)
    else:
        road = remaining  # 無法辨識時全放路名欄

    return county, district, road, detail


def clean_phone(phone: str) -> str:
    """移除電話號碼中的分隔符號，只保留數字"""
    return re.sub(r'[^0-9]', '', phone)


_CAPTCHA_PROMPT = "這是網頁圖形驗證碼，格式為五位數字（0–9），不含任何英文字母。請只輸出這五位數字，不要有空格、標點或任何說明。"


def solve_captcha_with_claude(captcha_path: str) -> str:
    """使用本地 oMLX (gemma-4-e2b-it-4bit) 判讀驗證碼；失敗則以 Claude Haiku 補底。"""
    import base64
    with open(captcha_path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    # ── 主要：本地 LLM（oMLX）────────────────────────────────
    try:
        import httpx
        resp = httpx.post(
            "http://127.0.0.1:8000/v1/chat/completions",
            headers={"Authorization": "Bearer killbee"},
            json={
                "model": "gemma-4-e2b-it-4bit",
                "max_tokens": 32,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image_url",
                         "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        {"type": "text", "text": _CAPTCHA_PROMPT},
                    ],
                }],
            },
            timeout=20,
        )
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if text:
            return text
    except Exception:
        pass

    # ── 備用：Claude Haiku API ────────────────────────────────
    try:
        import anthropic
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=32,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": _CAPTCHA_PROMPT},
                ],
            }],
        )
        return msg.content[0].text.strip()
    except Exception:
        return ""


# ════════════════════════════════════════════════════════════
#  i郵箱跨執行緒信號橋
# ════════════════════════════════════════════════════════════
class IBoxSignals(QObject):
    log          = pyqtSignal(str)   # 進度訊息（更新進度對話框）
    captcha_needed = pyqtSignal()    # 已填帳密，等待使用者輸入驗證碼
    login_done   = pyqtSignal()      # 登入成功
    qr_ready     = pyqtSignal(str)   # 傳回 QR Code 圖片路徑
    error        = pyqtSignal(str)   # 錯誤訊息
    finished     = pyqtSignal()      # 流程結束（不論成功或失敗）


# ════════════════════════════════════════════════════════════
#  Playwright 自動化工作執行緒
# ════════════════════════════════════════════════════════════
class IBoxWorker(threading.Thread):
    """
    在背景執行緒中使用 Playwright 驅動 i郵箱寄件流程。
    流程：EZPost 登入 → 選 i郵箱 → 注意事項 → Step1 帶入會員
         → Step2 填收件人 → Step3 填包裹 → 確認 → 取得 QR Code
    """

    def __init__(self, credentials: dict, sender: dict, customer: dict,
                 package_info: dict, signals: IBoxSignals):
        super().__init__(daemon=True)
        self.credentials  = credentials   # {"username": ..., "password": ...}
        self.sender       = sender        # CRM sender_info dict
        self.customer     = customer      # CRM customer_info dict
        self.package_info = package_info  # {"item_type": ..., "description": ..., "size": ...}
        self.signals      = signals

    # ── 主流程 ────────────────────────────────────────────────
    def run(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.signals.error.emit(
                "找不到 playwright 套件。\n"
                "請在終端機執行：\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )
            self.signals.finished.emit()
            return

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                    headless=False,
                )
                context = browser.new_context()
                page    = context.new_page()
                page.set_default_timeout(30_000)

                # ① 直接前往登入頁並填入帳密
                self.signals.log.emit("正在連線 EZPost 登入頁...")
                page.goto("https://ezpost.post.gov.tw/Account/Login")
                page.wait_for_load_state("networkidle", timeout=20_000)
                self._do_login(page)

                # ② 選擇「i郵箱自助寄件」→ 前往注意事項
                self.signals.log.emit("選擇 i郵箱自助寄件...")
                self._select_ibox_type(page)

                # ③ 注意事項頁：捲底 → 同意（判斷是否有 #termsContainer）
                if page.locator("#termsContainer").count() > 0:
                    self._agree_terms(page)

                # ④ Step 1：寄件人 → 帶入會員資料 → 填 CRM 寄件人 → 下一步
                page.wait_for_url("**/Mail/IBoxMailEdit**", timeout=15_000)
                self.signals.log.emit("Step 1：填入寄件人資料...")
                page.wait_for_selector("button:has-text('帶入會員資料')", timeout=10_000)
                page.click("button:has-text('帶入會員資料')")
                page.wait_for_timeout(800)
                self._fill_sender(page)
                page.click("button:has-text('下一步')")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)

                # ⑤ Step 2：收件人
                self.signals.log.emit("Step 2：填入收件人資料...")
                self._fill_recipient(page)
                page.wait_for_selector("#next-button-step", timeout=5_000)
                page.click("#next-button-step")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)

                # ⑥ Step 3：內裝物品
                self.signals.log.emit("Step 3：填入包裹資料...")
                self._fill_package(page)
                page.wait_for_selector("#next-button-step", timeout=5_000)
                page.click("#next-button-step")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(500)

                # ⑦ 確認寄件（按鈕 #ConfirmSendMailInfo，URL 仍在 IBoxMailEdit）
                self.signals.log.emit("確認寄件資訊...")
                page.wait_for_load_state("networkidle", timeout=15_000)
                page.wait_for_selector("#ConfirmSendMailInfo", timeout=30_000)
                page.click("#ConfirmSendMailInfo")
                page.wait_for_selector(".confirm-btn-alert", timeout=8_000)
                page.click(".confirm-btn-alert")
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(1_000)

                # ⑧ 完成頁：下載 QR Code
                page.wait_for_url("**/MailShipCompleted**", timeout=30_000)
                self.signals.log.emit("✅ 寄件成功！正在下載 QR Code...")
                page.wait_for_timeout(1_000)

                qr_path = self._download_qr(page)
                if qr_path:
                    self.signals.qr_ready.emit(qr_path)
                else:
                    self.signals.error.emit("無法下載 QR Code，請手動前往瀏覽器下載。")

                page.wait_for_timeout(2_000)
                browser.close()

        except Exception as e:
            self.signals.error.emit(f"自動化流程發生錯誤：\n{e}")
        finally:
            self.signals.finished.emit()

    # ── Step 1：填寄件人（覆蓋「帶入會員資料」預設值）────────────
    def _fill_sender(self, page):
        s = self.sender
        county, district, road, detail = parse_tw_address(s["addr"])
        phone = clean_phone(s["phone"])

        try:
            page.fill("input[placeholder*='寄件人姓名']", s["name"], timeout=3_000)
        except Exception:
            pass
        try:
            page.fill("input[placeholder*='手機']", phone, timeout=3_000)
        except Exception:
            pass
        if county:
            try:
                page.select_option("#MAIL_SADD_CITY", county, timeout=5_000)
                page.wait_for_timeout(1_000)
            except Exception:
                pass
        if district:
            try:
                page.wait_for_function(
                    "document.querySelector('#MAIL_SADD_AREA').options.length > 1",
                    timeout=8_000,
                )
                page.select_option("#MAIL_SADD_AREA", label=district, timeout=5_000)
            except Exception:
                pass
        if road:
            try:
                page.fill("#MAIL_SADD_ROAD", road, timeout=3_000)
            except Exception:
                pass
        if detail:
            try:
                page.fill("#MAIL_SADD_OTHER", detail, timeout=3_000)
            except Exception:
                pass

    # ── 登入 ──────────────────────────────────────────────────
    def _do_login(self, page):
        self.signals.log.emit("填入帳號密碼，等待圖形驗證碼...")
        try:
            page.fill("#inputEmail", self.credentials["username"], timeout=5_000)
        except Exception:
            pass
        try:
            page.fill("#inputPd", self.credentials["password"], timeout=5_000)
        except Exception:
            pass

        # 截圖驗證碼並嘗試 Claude 自動判讀（最多 3 次）
        captcha_path = os.path.join(os.path.expanduser("~"), "Downloads", "captcha.png")
        for attempt in range(1, 4):
            try:
                page.wait_for_selector("#imgCode", timeout=5_000)
                page.locator("#imgCode").screenshot(path=captcha_path)
                captcha_text = solve_captcha_with_claude(captcha_path)
                if not captcha_text:
                    break  # API 無回應，直接退到手動
                self.signals.log.emit(f"驗證碼自動判讀（第 {attempt} 次）：{captcha_text}")
                page.fill("#inputCaptcha", captcha_text, timeout=3_000)
                for btn_sel in ["#btnLogin", "button[type='submit']",
                                "input[type='submit']", "button:has-text('登入')"]:
                    try:
                        page.click(btn_sel, timeout=3_000)
                        break
                    except Exception:
                        pass
                try:
                    page.wait_for_url(
                        lambda url: "Login" not in url and "login" not in url,
                        timeout=15_000,
                    )
                    self.signals.login_done.emit()
                    return  # 自動登入成功
                except Exception:
                    self.signals.log.emit(f"第 {attempt} 次驗證碼錯誤，重新取得...")
                    page.wait_for_timeout(1_000)
            except Exception:
                break

        # 手動登入：通知 UI 顯示驗證碼提示，等使用者完成（最多 2 分鐘）
        self.signals.captcha_needed.emit()
        page.wait_for_url(
            lambda url: "Login" not in url and "login" not in url,
            timeout=120_000,
        )
        self.signals.login_done.emit()

    # ── 選 i郵箱自助寄件 ──────────────────────────────────────
    def _select_ibox_type(self, page):
        if "/SingleShip" not in page.url:
            page.goto("https://ezpost.post.gov.tw/SingleShip")
            page.wait_for_load_state("networkidle")
        # 點選 i郵箱選項（可能有空格或全形）
        for text in ["i 郵箱自助寄件", "i郵箱自助寄件"]:
            try:
                page.click(f"text={text}", timeout=4_000)
                break
            except Exception:
                pass
        try:
            page.wait_for_selector("#btn-green", timeout=5_000)
            page.click("#btn-green")
            page.wait_for_load_state("networkidle")
        except Exception:
            pass

    # ── 注意事項：捲底 → 同意 ────────────────────────────────
    def _agree_terms(self, page):
        self.signals.log.emit("處理注意事項頁面...")
        try:
            page.wait_for_selector("#termsContainer", timeout=10_000)
            page.evaluate("document.querySelector('#termsContainer').scrollTop = document.querySelector('#termsContainer').scrollHeight;")
            page.wait_for_timeout(800)
            page.wait_for_selector("#submitButton:not([disabled])", timeout=10_000)
            page.click("#submitButton")
            page.wait_for_load_state("networkidle")
        except Exception:
            pass

    # ── Step 2：填收件人 ──────────────────────────────────────
    def _fill_recipient(self, page):
        cust = self.customer
        county, district, road, detail = parse_tw_address(cust["addr"])
        phone = clean_phone(cust["phone"])

        try:
            page.fill("input[placeholder*='收件人姓名']", cust["display_name"], timeout=5_000)
        except Exception:
            pass

        try:
            page.fill("input[placeholder*='手機']", phone, timeout=5_000)
        except Exception:
            pass

        try:
            page.select_option("#MAIL_RADD_TYPE", "001", timeout=5_000)
        except Exception:
            pass

        if county:
            try:
                page.select_option("#MAIL_RADD_CITY", county, timeout=5_000)
                page.wait_for_timeout(1_000)
            except Exception:
                pass

        if district:
            try:
                page.wait_for_function(
                    "document.querySelector('#MAIL_RADD_AREA').options.length > 1",
                    timeout=8_000,
                )
                page.select_option("#MAIL_RADD_AREA", label=district, timeout=5_000)
            except Exception:
                pass

        if road:
            try:
                page.fill("#MAIL_RADD_ROAD", road, timeout=5_000)
            except Exception:
                pass

        if detail:
            try:
                page.fill("#MAIL_RADD_OTHER", detail, timeout=5_000)
            except Exception:
                pass

    # ── Step 3：填包裹 ────────────────────────────────────────
    def _fill_package(self, page):
        pkg = self.package_info

        # 物品種類（#categoryDropdown）
        try:
            page.select_option("#categoryDropdown", label=pkg["item_type"], timeout=5_000)
            page.wait_for_timeout(800)
            try:
                page.click("button:has-text('確認')", timeout=3_000)
                page.wait_for_timeout(500)
            except Exception:
                pass
        except Exception:
            pass

        # 包材尺寸（#sizeDropdown，選項含「大」/「中」/「小」字）
        size_label = IBOX_SIZE_MAP.get(pkg.get("size", "大 (34×24×45cm)"), "大")
        try:
            opts = page.locator("#sizeDropdown option").all_inner_texts()
            match = next((o for o in opts if size_label in o), None)
            if match:
                page.select_option("#sizeDropdown", label=match)
                page.wait_for_timeout(300)
                try:
                    page.wait_for_selector(".confirm-btn-alert", timeout=5_000)
                    page.click(".confirm-btn-alert")
                    page.wait_for_timeout(500)
                except Exception:
                    pass
        except Exception:
            pass

        # 內裝物品描述
        for sel in ["input[placeholder*='內裝物品']", "input[placeholder*='物品']",
                    "input[placeholder*='品名']", "textarea[placeholder*='物品']"]:
            try:
                page.fill(sel, pkg["description"], timeout=3_000)
                break
            except Exception:
                pass

    # ── 下載 QR Code ──────────────────────────────────────────
    def _download_qr(self, page) -> str:
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        os.makedirs(download_dir, exist_ok=True)

        # 方法一：攔截下載事件
        try:
            with page.expect_download(timeout=15_000) as dl_info:
                page.click(
                    "button:has-text('下載寄件 QR Code'), a:has-text('下載寄件 QR Code')"
                )
            dl = dl_info.value
            fname = dl.suggested_filename or "ibox_qr.png"
            save_path = os.path.join(download_dir, fname)
            dl.save_as(save_path)
            return save_path
        except Exception:
            pass

        # 方法二：截圖 QR Code 元素
        try:
            qr_el = page.locator("img[src*='qr'], img[alt*='QR'], canvas").first
            save_path = os.path.join(download_dir, "ibox_qr.png")
            qr_el.screenshot(path=save_path)
            return save_path
        except Exception:
            return ""


# ════════════════════════════════════════════════════════════
#  待寄清單自訂列（含「📦 i郵箱」按鈕）
# ════════════════════════════════════════════════════════════
class PendingItemWidget(QWidget):
    """
    待寄清單中每一列的 Widget：
    左側顯示「寄件人 → 收件人」，右側為「📦 i郵箱」按鈕。
    """

    def __init__(self, index: int, text: str, ship_callback, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        self.label = QLabel(text)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.ibox_btn = QPushButton("📦 i郵箱")
        self.ibox_btn.setFixedWidth(95)
        self.ibox_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 5px 8px;"
            "font-weight: bold; border-radius: 5px;"
        )
        self.ibox_btn.setToolTip("透過 i郵箱自動寄出這筆訂單")
        self.ibox_btn.clicked.connect(lambda: ship_callback(index))

        layout.addWidget(self.label)
        layout.addWidget(self.ibox_btn)


# ════════════════════════════════════════════════════════════
#  對話框：設定 i郵箱帳號密碼
# ════════════════════════════════════════════════════════════
class IBoxCredDialog(QDialog):
    def __init__(self, saved_username: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ i郵箱帳號設定")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        note = QLabel("帳號密碼僅儲存在本機，不會上傳至任何伺服器。")
        note.setStyleSheet("color: #888; font-size: 11px;")
        layout.addRow(note)

        self.username_input = QLineEdit(saved_username)
        self.username_input.setPlaceholderText("EZPost 帳號（電子信箱）")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("EZPost 密碼")

        self.save_check = QCheckBox("記住這組帳密（下次不需再輸入）")
        self.save_check.setChecked(True)

        layout.addRow("帳號：", self.username_input)
        layout.addRow("密碼：", self.password_input)
        layout.addRow("", self.save_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> dict:
        return {
            "username": self.username_input.text().strip(),
            "password": self.password_input.text(),
            "save":     self.save_check.isChecked(),
        }


# ════════════════════════════════════════════════════════════
#  對話框：輸入包裹內容
# ════════════════════════════════════════════════════════════
class IBoxPackageDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📦 設定包裹內容")
        self.setMinimumWidth(400)
        layout = QFormLayout(self)

        self.item_type_combo = QComboBox()
        self.item_type_combo.addItems(IBOX_ITEM_TYPES)
        self.item_type_combo.setCurrentText("零件")

        self.description_input = QLineEdit("零件")
        self.description_input.setPlaceholderText("例：保養品 ×2、面膜 ×5")

        self.size_combo = QComboBox()
        self.size_combo.addItems(IBOX_SIZES)
        self.size_combo.setCurrentIndex(0)  # 預設「大」

        layout.addRow("物品種類：",     self.item_type_combo)
        layout.addRow("內裝物品描述：", self.description_input)
        layout.addRow("包材尺寸：",     self.size_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _on_accept(self):
        if not self.description_input.text().strip():
            QMessageBox.warning(self, "提示", "請輸入內裝物品描述（不可空白）")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "item_type":   self.item_type_combo.currentText(),
            "description": self.description_input.text().strip(),
            "size":        self.size_combo.currentText(),
        }


# ════════════════════════════════════════════════════════════
#  對話框：自動化進度 + 驗證碼提示
# ════════════════════════════════════════════════════════════
class IBoxProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("i郵箱寄件中...")
        self.setMinimumWidth(420)
        # 禁止使用者手動關閉（避免中途終止）
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        layout = QVBoxLayout(self)

        self.status_label = QLabel("正在啟動自動化流程...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)  # 不確定進度動畫
        layout.addWidget(self.bar)

        # 驗證碼提示（登入時才顯示）
        self.captcha_label = QLabel("")
        self.captcha_label.setWordWrap(True)
        self.captcha_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.captcha_label.setStyleSheet(
            "color: #c0392b; font-weight: bold; padding: 8px;"
            "background: #fdecea; border-radius: 6px;"
        )
        self.captcha_label.hide()
        layout.addWidget(self.captcha_label)

    def set_status(self, msg: str):
        self.status_label.setText(msg)

    def show_captcha_hint(self):
        self.captcha_label.setText(
            "⚠️ 瀏覽器視窗已開啟並自動填入帳號密碼。\n"
            "請切換到瀏覽器，輸入圖形驗證碼後點擊「登入」。\n"
            "登入完成後，自動化流程將繼續執行。"
        )
        self.captcha_label.show()

    def hide_captcha_hint(self):
        self.captcha_label.setText("✅ 登入成功！繼續自動化流程...")
        self.captcha_label.setStyleSheet(
            "color: #27ae60; font-weight: bold; padding: 8px;"
            "background: #eafaf1; border-radius: 6px;"
        )


# ════════════════════════════════════════════════════════════
#  對話框：顯示 QR Code 結果
# ════════════════════════════════════════════════════════════
class IBoxResultDialog(QDialog):
    def __init__(self, qr_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✅ i郵箱寄件成功")
        self.qr_path = qr_path
        layout = QVBoxLayout(self)

        # QR Code 圖片
        img_label = QLabel()
        pix = QPixmap(qr_path)
        if not pix.isNull():
            img_label.setPixmap(
                pix.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            img_label.setText("（無法載入 QR Code 圖片）")
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(img_label)

        # 路徑說明
        path_label = QLabel(f"QR Code 已儲存至：\n{qr_path}")
        path_label.setWordWrap(True)
        path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path_label.setStyleSheet("color: #555; font-size: 11px; margin: 4px;")
        layout.addWidget(path_label)

        # 按鈕
        btn_row = QHBoxLayout()
        open_btn = QPushButton("🖨️ 開啟 QR Code 檔案")
        open_btn.clicked.connect(self._open_file)
        close_btn = QPushButton("✅ 完成")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _open_file(self):
        if platform.system() == "Windows":
            os.startfile(self.qr_path)
        else:
            subprocess.run(["open", self.qr_path])


# ════════════════════════════════════════════════════════════
#  主視窗
# ════════════════════════════════════════════════════════════
class CRMDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("蜜蜂CRM寄件系統 v1.3")
        self.resize(1100, 850)
        self.pending_list_data   = []
        self._progress_dialog    = None

        main_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)

        # 狀態列 + 帳密設定按鈕（右側小按鈕）
        top_row = QHBoxLayout()
        self.status_label = QLabel("正在連線雲端...")
        top_row.addWidget(self.status_label, 1)
        self.cred_btn = QPushButton("⚙️ i郵箱帳密設定")
        self.cred_btn.setFixedWidth(140)
        self.cred_btn.setStyleSheet("padding: 4px; font-size: 12px;")
        self.cred_btn.clicked.connect(self._open_cred_dialog)
        top_row.addWidget(self.cred_btn)
        main_layout.addLayout(top_row)

        # 上方：寄件者 & 客戶兩張表格
        content_layout = QHBoxLayout()
        self.sender_table = QTableWidget()
        self.sender_table.setColumnCount(5)
        self.sender_table.setHorizontalHeaderLabels(["ID", "姓名", "地址", "郵編", "電話"])
        self.sender_table.hideColumn(0)

        self.customer_table = QTableWidget()
        self.customer_table.setColumnCount(7)
        self.customer_table.setHorizontalHeaderLabels(
            ["ID", "公司名", "人名", "地址", "區號", "電話", "統編"]
        )
        self.customer_table.hideColumn(0)

        content_layout.addWidget(self.sender_table, 1)
        content_layout.addWidget(self.customer_table, 1)
        main_layout.addLayout(content_layout)

        # 搜尋
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜尋地址或收件人...")
        self.search_input.textChanged.connect(self.filter_customers)
        main_layout.addWidget(self.search_input)

        # 新增配對按鈕（左側附「附加公司名稱」核選方塊）
        add_row = QHBoxLayout()
        self.append_company_check = QCheckBox("附加公司名稱")
        self.append_company_check.setChecked(True)
        self.append_company_check.setToolTip("勾選時，收件人欄位會帶入「公司名 人名」；取消勾選則只帶人名")
        add_row.addWidget(self.append_company_check)
        self.add_btn = QPushButton("➕ 新增配對")
        self.add_btn.setStyleSheet(
            "background-color: #2ecc71; color: white; padding: 10px; font-weight: bold;"
        )
        self.add_btn.clicked.connect(self.add_to_pending)
        add_row.addWidget(self.add_btn)
        main_layout.addLayout(add_row)

        # 待寄清單（使用自訂 Widget 列，每列右側有「📦 i郵箱」按鈕）
        self.pending_list_widget = QListWidget()
        self.pending_list_widget.setMinimumHeight(160)
        main_layout.addWidget(self.pending_list_widget)

        # ── 底部操作按鈕列：清空清單 / 輸出 PDF（並排顯示）─────────
        action_layout = QHBoxLayout()

        # 「清空清單」按鈕：紅色警示色，提醒使用者這是會清除資料的動作
        self.clear_btn = QPushButton("🗑️ 清空清單")
        self.clear_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 15px; font-weight: bold;"
        )
        self.clear_btn.setToolTip("清除所有目前待寄的配對（不會影響 Google Sheets 上的資料）")
        self.clear_btn.clicked.connect(self.clear_pending_list)
        action_layout.addWidget(self.clear_btn, 1)  # 佔 1 份寬度

        # 輸出 PDF 按鈕
        self.output_btn = QPushButton("輸出PDF")
        self.output_btn.setStyleSheet(
            "background-color: #26a9e1; color: white; padding: 15px; font-weight: bold;"
        )
        self.output_btn.clicked.connect(self.generate_batch_pdf)
        action_layout.addWidget(self.output_btn, 2)  # 主要動作，佔 2 份寬度

        main_layout.addLayout(action_layout)

        self.load_all_data()

    # ── 表格樣式 ──────────────────────────────────────────────
    def set_table_style(self, table):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)

    # ── 載入 Google Sheets 資料 ───────────────────────────────
    def load_all_data(self):
        creds = None
        cred_file  = resource_path("credentials.json")
        token_file = os.path.join(os.path.expanduser("~"), ".蜜蜂CRM_token.json")
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w") as token:
                token.write(creds.to_json())
        try:
            service  = build("sheets", "v4", credentials=creds)
            sheet    = service.spreadsheets()
            res_cust = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID, range="客戶!A2:G300"
            ).execute()
            self.customers = res_cust.get("values", [])
            self.fill_table(self.customer_table, self.customers, 7)
            res_send = sheet.values().get(
                spreadsheetId=SPREADSHEET_ID, range="寄件者!A2:E50"
            ).execute()
            self.senders = res_send.get("values", [])
            self.fill_table(self.sender_table, self.senders, 5)
            self.status_label.setText("同步完成 ✅")
            self.set_table_style(self.customer_table)
            self.set_table_style(self.sender_table)
        except Exception as e:
            self.status_label.setText(f"連線失敗：{e}")

    def fill_table(self, table, data, cols):
        table.setRowCount(len(data))
        for r, row_data in enumerate(data):
            for c in range(cols):
                val = row_data[c] if c < len(row_data) else ""
                table.setItem(r, c, QTableWidgetItem(str(val)))

    # ── 搜尋過濾 ──────────────────────────────────────────────
    def filter_customers(self, text):
        text = text.lower()
        for i in range(self.customer_table.rowCount()):
            match = any(
                text in (self.customer_table.item(i, j).text()
                         if self.customer_table.item(i, j) else "").lower()
                for j in [1, 2, 3]
            )
            self.customer_table.setRowHidden(i, not match)

    # ── 新增配對（使用自訂列 Widget）─────────────────────────
    def add_to_pending(self):
        s_row = self.sender_table.currentRow()
        c_row = self.customer_table.currentRow()
        if s_row < 0 or c_row < 0:
            return

        def gt(t, r, c):
            return t.item(r, c).text() if t.item(r, c) else ""

        s_info = {
            "name":  gt(self.sender_table, s_row, 1),
            "addr":  gt(self.sender_table, s_row, 2),
            "zip":   gt(self.sender_table, s_row, 3),
            "phone": gt(self.sender_table, s_row, 4),
        }
        comp = gt(self.customer_table, c_row, 1)
        recp = gt(self.customer_table, c_row, 2)
        if self.append_company_check.isChecked():
            display_name = comp if comp == recp else f"{comp} {recp}"
        else:
            display_name = recp
        customer_info = {
            "display_name": display_name,
            "addr":  gt(self.customer_table, c_row, 3),
            "zip":   gt(self.customer_table, c_row, 4),
            "phone": gt(self.customer_table, c_row, 5),
        }

        idx = len(self.pending_list_data)
        self.pending_list_data.append({"sender": s_info, "customer": customer_info})

        # 建立自訂 Widget 列
        text   = f"{s_info['name']}  →  {customer_info['display_name']}"
        widget = PendingItemWidget(idx, text, self.ship_with_ibox)
        item   = QListWidgetItem()
        item.setSizeHint(widget.sizeHint())
        self.pending_list_widget.addItem(item)
        self.pending_list_widget.setItemWidget(item, widget)

    # ── 清空待寄清單 ──────────────────────────────────────────
    def clear_pending_list(self):
        """
        手動清空目前的待寄清單（同時清空底層資料 self.pending_list_data
        與 UI 上的 QListWidget 顯示），避免再次「輸出 PDF」時把舊配對重複帶出。

        為避免誤按造成資料遺失，會先跳出 Yes/No 確認對話框，
        且預設按鈕為 No（必須主動選 Yes 才會清除）。
        """
        # 如果清單原本就是空的，直接提示即可，不必再問。
        if not self.pending_list_data:
            QMessageBox.information(self, "提示", "目前清單是空的，沒有東西需要清除喔 🦞")
            return

        reply = QMessageBox.question(
            self,
            "確認清空",
            f"確定要清空目前清單中的 {len(self.pending_list_data)} 筆配對嗎？\n此動作無法復原。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,  # 預設游標停在「No」，避免誤按 Enter
        )
        if reply == QMessageBox.StandardButton.Yes:
            # 同時清空「資料模型」與「UI 顯示」，確保下一次輸出 PDF 從零開始
            self.pending_list_data.clear()
            self.pending_list_widget.clear()
            self.status_label.setText("清單已清空 🗑️")

    # ── 輸出 PDF ──────────────────────────────────────────────
    def generate_batch_pdf(self):
        if not self.pending_list_data:
            return
        pdf_file = os.path.join(os.path.expanduser("~"), "Desktop", "shipping_labels.pdf")
        width, height = A4
        c = canvas.Canvas(pdf_file, pagesize=(width, height))
        y_cursor, label_height, margin = height - 20, 130, 15

        for pair in self.pending_list_data:
            if y_cursor < label_height + 20:
                c.showPage()
                y_cursor = height - 20
            s, cust = pair["sender"], pair["customer"]
            c.setFont("ChineseFont", 15)
            c.drawString(margin, y_cursor - 20, f"{s['zip']} {s['addr']}")
            c.drawString(margin, y_cursor - 45, f"寄件人：{s['name']} {s['phone']}")
            c.drawRightString(width - margin, y_cursor - 80, f"{cust['zip']} {cust['addr']}")
            c.setFont("ChineseFont", 20)
            c.drawRightString(width - margin, y_cursor - 105,
                              f"{cust['display_name']} 收 {cust['phone']}")
            c.setDash(1, 2)
            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(margin, y_cursor - 125, width - margin, y_cursor - 125)
            c.setDash()
            y_cursor -= label_height

        c.save()
        self.pending_list_data = []
        self.pending_list_widget.clear()

        if platform.system() == "Windows":
            os.startfile(pdf_file)
        else:
            subprocess.run(["open", "-a", "Preview", pdf_file])
        self.activateWindow()

    # ── i郵箱帳密：讀取 / 儲存 ───────────────────────────────
    def load_ibox_credentials(self) -> dict:
        if os.path.exists(IBOX_CONFIG_PATH):
            try:
                with open(IBOX_CONFIG_PATH, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_ibox_credentials(self, username: str, password: str):
        try:
            with open(IBOX_CONFIG_PATH, "w") as f:
                json.dump({"username": username, "password": password}, f)
        except Exception:
            pass

    # ── 開啟帳密設定對話框 ─────────────────────────────────────
    def _open_cred_dialog(self):
        saved = self.load_ibox_credentials()
        dlg   = IBoxCredDialog(saved.get("username", ""), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data["save"]:
                self.save_ibox_credentials(data["username"], data["password"])
            else:
                # 使用者取消儲存 → 刪除舊的
                if os.path.exists(IBOX_CONFIG_PATH):
                    os.remove(IBOX_CONFIG_PATH)
            QMessageBox.information(self, "完成", "i郵箱帳密已更新。")

    # ── 主入口：點「📦 i郵箱」按鈕 ──────────────────────────
    def ship_with_ibox(self, index: int):
        if index >= len(self.pending_list_data):
            QMessageBox.warning(self, "錯誤", "找不到對應的配對資料。")
            return

        pair = self.pending_list_data[index]

        # ① 取得帳密（已存則直接用，否則先詢問）
        saved = self.load_ibox_credentials()
        if not saved.get("username") or not saved.get("password"):
            dlg = IBoxCredDialog(saved.get("username", ""), parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            data = dlg.get_data()
            if not data["username"] or not data["password"]:
                QMessageBox.warning(self, "提示", "帳號或密碼不可空白。")
                return
            if data["save"]:
                self.save_ibox_credentials(data["username"], data["password"])
            credentials = {"username": data["username"], "password": data["password"]}
        else:
            credentials = saved

        # ② 詢問包裹內容
        pkg_dlg = IBoxPackageDialog(parent=self)
        if pkg_dlg.exec() != QDialog.DialogCode.Accepted:
            return
        package_info = pkg_dlg.get_data()

        # ③ 顯示進度對話框
        self._progress_dialog = IBoxProgressDialog(parent=self)
        self._progress_dialog.show()

        # ④ 建立信號橋，連接到 UI slots
        signals = IBoxSignals()
        signals.log.connect(self._progress_dialog.set_status)
        signals.captcha_needed.connect(self._progress_dialog.show_captcha_hint)
        signals.login_done.connect(self._progress_dialog.hide_captcha_hint)
        signals.qr_ready.connect(self._on_qr_ready)
        signals.error.connect(self._on_ibox_error)
        signals.finished.connect(self._on_ibox_finished)

        # ⑤ 啟動背景執行緒
        worker = IBoxWorker(
            credentials=credentials,
            sender=pair["sender"],
            customer=pair["customer"],
            package_info=package_info,
            signals=signals,
        )
        worker.start()
        self._ibox_worker = worker  # 保持引用，避免被 GC

    # ── 自動化完成回呼 ────────────────────────────────────────
    def _on_qr_ready(self, qr_path: str):
        if self._progress_dialog:
            self._progress_dialog.close()
        result_dlg = IBoxResultDialog(qr_path, parent=self)
        result_dlg.exec()

    def _on_ibox_error(self, msg: str):
        if self._progress_dialog:
            self._progress_dialog.close()
        QMessageBox.critical(self, "i郵箱錯誤", msg)

    def _on_ibox_finished(self):
        if self._progress_dialog and self._progress_dialog.isVisible():
            self._progress_dialog.close()


# ════════════════════════════════════════════════════════════
#  程式進入點
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app    = QApplication(sys.argv)
    window = CRMDesktopApp()
    window.show()
    sys.exit(app.exec())
