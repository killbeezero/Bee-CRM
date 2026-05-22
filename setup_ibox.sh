#!/bin/bash
# ─────────────────────────────────────────────────────────────
# 蜜蜂CRM × i郵箱 — 環境設定腳本
# 執行方式：在終端機切換到 CRM 資料夾後執行 bash setup_ibox.sh
# ─────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🐝 蜜蜂CRM i郵箱整合 — 環境設定"
echo "=================================="

# 找到正確的 Python（優先用 venv）
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
    PIP="venv/bin/pip"
    echo "✅ 使用 venv Python：$PYTHON"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
    PIP="pip3"
    echo "⚠️  未找到 venv，使用系統 Python3"
else
    echo "❌ 找不到 Python，請先安裝 Python 3.9+"
    exit 1
fi

echo ""
echo "📦 安裝 playwright..."
$PIP install playwright -q
echo "✅ playwright 套件安裝完成"

echo ""
echo "🌐 下載 Chromium 瀏覽器核心..."
$PYTHON -m playwright install chromium
echo "✅ Chromium 安裝完成"

echo ""
echo "🔍 驗證安裝..."
$PYTHON -c "from playwright.sync_api import sync_playwright; print('✅ playwright 匯入正常')"

echo ""
echo "════════════════════════════════════"
echo "✅ 設定完成！"
echo ""
echo "現在可以啟動 CRM 系統："
echo "  python main.py"
echo ""
echo "首次使用 i郵箱功能時，系統會："
echo "  1. 詢問你的 EZPost 帳號密碼（儲存後下次免填）"
echo "  2. 自動開啟瀏覽器並填入帳密"
echo "  3. 等你在瀏覽器輸入圖形驗證碼後，自動繼續填單"
echo "  4. 寄件完成後顯示 QR Code"
echo "════════════════════════════════════"
