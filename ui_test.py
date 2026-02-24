import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton
from PyQt6.QtCore import Qt

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CRM 桌面版 測試 🦞")
        self.setGeometry(100, 100, 400, 200)

        # 建立佈局
        layout = QVBoxLayout()
        
        self.label = QLabel("正在測試 Mac 版 UI 渲染...", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("font-size: 18px; color: #26a9e1; font-weight: bold;")
        
        btn = QPushButton("點擊測試龍蝦戰力", self)
        btn.clicked.connect(self.on_clicked)
        
        layout.addWidget(self.label)
        layout.addWidget(btn)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def on_clicked(self):
        self.label.setText("測試成功！龍蝦甲殼萬歲！🦞✨")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())
