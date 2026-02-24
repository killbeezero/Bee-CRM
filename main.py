import sys
import os
import subprocess
import platform
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QHeaderView, QPushButton, QMessageBox, QListWidget
from PyQt6.QtCore import Qt
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 跨平台字體適配 ---
if platform.system() == "Windows":
    CHINESE_FONT_PATH = "C:\\Windows\\Fonts\\msyh.ttc" # 微軟正黑體
else:
    CHINESE_FONT_PATH = "/System/Library/Fonts/STHeiti Light.ttc" # Mac 黑體

if not os.path.exists(CHINESE_FONT_PATH):
    # 最後備案: 如果找不到預設，就不指定路徑 (可能導致亂碼，但不會崩潰)
    pdfmetrics.registerFont(TTFont("ChineseFont", "STHeiti" if platform.system() != "Windows" else "MSJH"))
else:
    pdfmetrics.registerFont(TTFont("ChineseFont", CHINESE_FONT_PATH))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = "1L5J_fIdRZidQpXIMBCRLYIzvyCp_1aTngROBE6M0DFc"

class CRMDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("蜜蜂CRM寄件系統")
        self.resize(1100, 850)
        self.pending_list_data = []
        main_layout = QVBoxLayout()
        self.main_widget = QWidget()
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
        self.status_label = QLabel("正在連線雲端...")
        main_layout.addWidget(self.status_label)
        content_layout = QHBoxLayout()
        self.sender_table = QTableWidget()
        self.sender_table.setColumnCount(5)
        self.sender_table.setHorizontalHeaderLabels(["ID", "姓名", "地址", "郵編", "電話"])
        self.sender_table.hideColumn(0)
        self.customer_table = QTableWidget()
        self.customer_table.setColumnCount(7)
        self.customer_table.setHorizontalHeaderLabels(["ID", "公司名", "人名", "地址", "區號", "電話", "統編"])
        self.customer_table.hideColumn(0)
        content_layout.addWidget(self.sender_table, 1)
        content_layout.addWidget(self.customer_table, 1)
        main_layout.addLayout(content_layout)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜尋地址或收件人...")
        self.search_input.textChanged.connect(self.filter_customers)
        main_layout.addWidget(self.search_input)
        self.add_btn = QPushButton("➕ 新增配對")
        self.add_btn.setStyleSheet("background-color: #2ecc71; color: white; padding: 10px; font-weight: bold;")
        self.add_btn.clicked.connect(self.add_to_pending)
        main_layout.addWidget(self.add_btn)
        self.pending_list_widget = QListWidget()
        main_layout.addWidget(self.pending_list_widget)
        self.output_btn = QPushButton("輸出PDF")
        self.output_btn.setStyleSheet("background-color: #26a9e1; color: white; padding: 15px; font-weight: bold;")
        self.output_btn.clicked.connect(self.generate_batch_pdf)
        main_layout.addWidget(self.output_btn)
        self.load_all_data()

    def set_table_style(self, table):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setAlternatingRowColors(True)

    def load_all_data(self):
        creds = None
        cred_file = resource_path("credentials.json")
        token_file = os.path.join(os.path.expanduser("~"), ".蜜蜂CRM_token.json")
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(cred_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w") as token: token.write(creds.to_json())
        try:
            service = build("sheets", "v4", credentials=creds)
            sheet = service.spreadsheets()
            res_cust = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="客戶!A2:G300").execute()
            self.customers = res_cust.get("values", [])
            self.fill_table(self.customer_table, self.customers, 7)
            res_send = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range="寄件者!A2:E50").execute()
            self.senders = res_send.get("values", [])
            self.fill_table(self.sender_table, self.senders, 5)
            self.status_label.setText(f"同步完成 ✅")
            self.set_table_style(self.customer_table); self.set_table_style(self.sender_table)
        except Exception as e: self.status_label.setText(f"連線失敗: {e}")

    def fill_table(self, table, data, cols):
        table.setRowCount(len(data))
        for r, row_data in enumerate(data):
            for c in range(cols):
                val = row_data[c] if c < len(row_data) else ""
                table.setItem(r, c, QTableWidgetItem(str(val)))

    def filter_customers(self, text):
        text = text.lower()
        for i in range(self.customer_table.rowCount()):
            match = any(text in (self.customer_table.item(i, j).text() if self.customer_table.item(i, j) else "").lower() for j in [1, 2, 3])
            self.customer_table.setRowHidden(i, not match)

    def add_to_pending(self):
        s_row = self.sender_table.currentRow()
        c_row = self.customer_table.currentRow()
        if s_row < 0 or c_row < 0: return
        def gt(t, r, c): return t.item(r, c).text() if t.item(r, c) else ""
        s_info = {"name": gt(self.sender_table, s_row, 1), "addr": gt(self.sender_table, s_row, 2), "zip": gt(self.sender_table, s_row, 3), "phone": gt(self.sender_table, s_row, 4)}
        comp = gt(self.customer_table, c_row, 1); recp = gt(self.customer_table, c_row, 2)
        customer_info = {"display_name": comp if comp == recp else f"{comp}{recp}", "addr": gt(self.customer_table, c_row, 3), "zip": gt(self.customer_table, c_row, 4), "phone": gt(self.customer_table, c_row, 5)}
        self.pending_list_data.append({"sender": s_info, "customer": customer_info})
        self.pending_list_widget.addItem(f"{s_info['name']} -> {customer_info['display_name']}")

    def generate_batch_pdf(self):
        if not self.pending_list_data: return
        pdf_file = os.path.join(os.path.expanduser("~"), "Desktop", "shipping_labels.pdf") 
        width, height = A4
        c = canvas.Canvas(pdf_file, pagesize=(width, height))
        y_cursor, label_height, margin = height - 20, 130, 15
        for pair in self.pending_list_data:
            if y_cursor < label_height + 20: c.showPage(); y_cursor = height - 20
            s, cust = pair["sender"], pair["customer"]
            c.setFont("ChineseFont", 15)
            c.drawString(margin, y_cursor - 20, f"{s['zip']} {s['addr']}")
            c.drawString(margin, y_cursor - 45, f"寄件人：{s['name']} {s['phone']}")
            c.setFont("ChineseFont", 15)
            c.drawRightString(width - margin, y_cursor - 80, f"{cust['zip']} {cust['addr']}")
            c.setFont("ChineseFont", 20)
            c.drawRightString(width - margin, y_cursor - 105, f"{cust['display_name']} 收 {cust['phone']}")
            c.setDash(1, 2); c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(margin, y_cursor - 125, width - margin, y_cursor - 125); c.setDash()
            y_cursor -= label_height
        c.save()
        self.pending_list_data, self.pending_list_widget.clear()
        if platform.system() == "Windows": os.startfile(pdf_file)
        else: subprocess.run(["open", "-a", "Preview", pdf_file])
        self.activateWindow()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CRMDesktopApp()
    window.show()
    sys.exit(app.exec())
