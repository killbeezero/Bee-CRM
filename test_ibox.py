"""
i郵箱自動化流程測試腳本
用途：不啟動完整 CRM，直接在終端機測試 Playwright 自動化每個步驟
執行：python test_ibox.py
"""

import os
import sys
import re
import json
import getpass

# ── 引入共用工具 ─────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import parse_tw_address, clean_phone, IBOX_SIZE_MAP, solve_captcha_with_claude

IBOX_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".蜜蜂CRM_ibox_config.json")


# ── 輔助 ────────────────────────────────────────────────────
def step(n, total, msg):
    print(f"\n[{n}/{total}] {msg}")

def ok(msg=""):
    print(f"  ✅ {msg}" if msg else "  ✅ 成功")

def fail(msg):
    print(f"  ❌ {msg}")

def info(msg):
    print(f"  ℹ️  {msg}")

def warn(msg):
    print(f"  ⚠️  {msg}")


# ── 取得帳密 ─────────────────────────────────────────────────
def get_credentials():
    if os.path.exists(IBOX_CONFIG_PATH):
        try:
            with open(IBOX_CONFIG_PATH) as f:
                creds = json.load(f)
            if creds.get("username") and creds.get("password"):
                print(f"✅ 使用已儲存帳號：{creds['username']}")
                return creds
        except Exception:
            pass

    print("\n請輸入 EZPost 帳號密碼：")
    username = input("  帳號（Email）：").strip()
    password = getpass.getpass("  密碼：")

    save = input("  要儲存帳密供下次使用嗎？[y/N] ").strip().lower()
    if save == "y":
        with open(IBOX_CONFIG_PATH, "w") as f:
            json.dump({"username": username, "password": password}, f)
        print("  已儲存")

    return {"username": username, "password": password}


# ── 取得收件人資料 ────────────────────────────────────────────
def get_customer():
    return {
        "display_name": "鐘慶峯",
        "phone":        "0928686295",
        "addr":         "高雄市仁武區澄仁西街210號",
        "zip":          "814",
    }


# ── 主流程 ───────────────────────────────────────────────────
def run():
    print("=" * 50)
    print("  i郵箱自動化流程測試")
    print("=" * 50)

    creds   = get_credentials()
    cust    = get_customer()
    county, district, road, detail = parse_tw_address(cust["addr"])
    phone   = clean_phone(cust["phone"])

    print(f"\n地址解析結果：縣市={county!r}  區={district!r}  路={road!r}  號碼={detail!r}")
    print(f"電話清洗結果：{phone}")

    pkg = {
        "item_type":   "零件",
        "description": "零件",
        "size":        "小 (14×17×45cm)",
    }
    print(f"\n固定使用測試包裹：{pkg}")
    input("\n按 Enter 開始啟動瀏覽器...")

    from playwright.sync_api import sync_playwright

    TOTAL = 9
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            slow_mo=300,
        )
        context = browser.new_context()
        page    = context.new_page()
        page.set_default_timeout(30_000)

        # ① 前往登入頁並填入帳密
        step(1, TOTAL, "前往 EZPost 登入頁...")
        page.goto("https://ezpost.post.gov.tw/Account/Login")
        page.wait_for_load_state("networkidle", timeout=20_000)
        ok(f"目前 URL：{page.url}")

        step(2, TOTAL, "填入帳號密碼...")
        try:
            page.fill("#inputEmail", creds["username"], timeout=5_000)
            info("帳號欄填入完成（#inputEmail）")
        except Exception as e:
            warn(f"帳號欄填入失敗：{e}")

        try:
            page.fill("#inputPd", creds["password"], timeout=5_000)
            info("密碼欄填入完成（#inputPd）")
        except Exception as e:
            warn(f"密碼欄填入失敗：{e}")

        # 截圖驗證碼並嘗試 Claude 自動判讀（最多 3 次）
        captcha_path = os.path.join(os.path.expanduser("~"), "Downloads", "captcha.png")
        auto_logged_in = False
        for attempt in range(1, 4):
            try:
                page.wait_for_selector("#imgCode", timeout=5_000)
                page.locator("#imgCode").screenshot(path=captcha_path)
                info(f"驗證碼截圖已儲存（第 {attempt} 次）：{captcha_path}")

                captcha_text = solve_captcha_with_claude(captcha_path)
                if not captcha_text:
                    warn("Claude 自動判讀未取得結果（請確認 ANTHROPIC_API_KEY），切換為手動...")
                    break

                info(f"Claude 自動判讀驗證碼：{captcha_text!r}")
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
                    auto_logged_in = True
                    ok(f"自動登入成功！URL：{page.url}")
                    break
                except Exception:
                    warn(f"第 {attempt} 次驗證碼錯誤，重新取得...")
                    page.wait_for_timeout(1_000)
            except Exception as e:
                warn(f"驗證碼截圖失敗：{e}")
                break

        if not auto_logged_in:
            print("\n  ⚠️  請在瀏覽器視窗完成圖形驗證碼後按下「登入」")
            print("       登入完成後，回這裡按 Enter 繼續...")
            input()
            page.wait_for_load_state("networkidle", timeout=30_000)
            ok(f"登入後 URL：{page.url}")

        # ③ 選 i郵箱
        step(3, TOTAL, "選擇「i郵箱自助寄件」...")
        if "/SingleShip" not in page.url:
            page.goto("https://ezpost.post.gov.tw/SingleShip")
            page.wait_for_load_state("networkidle")

        clicked = False
        for text in ["i 郵箱自助寄件", "i郵箱自助寄件", "i郵箱"]:
            try:
                page.click(f"text={text}", timeout=4_000)
                info(f"點擊文字命中：{text!r}")
                clicked = True
                break
            except Exception:
                pass
        if not clicked:
            warn("找不到 i郵箱選項文字，請手動點選")
            input("  手動點選後按 Enter 繼續...")

        try:
            page.wait_for_selector("#btn-green", timeout=5_000)
            page.click("#btn-green")
            page.wait_for_load_state("networkidle")
            ok("點擊「下一步」成功（#btn-green）")
        except Exception as e:
            warn(f"找不到「下一步」按鈕：{e}，請手動點擊")
            input("  手動點擊後按 Enter 繼續...")

        # ④ 注意事項
        step(4, TOTAL, "處理注意事項頁面...")
        try:
            # 將 #termsContainer 捲到底，觸發 JS 解鎖同意按鈕
            page.wait_for_selector("#termsContainer", timeout=10_000)
            page.evaluate("""
                const box = document.querySelector('#termsContainer');
                box.scrollTop = box.scrollHeight;
            """)
            page.wait_for_timeout(800)
            # 等待按鈕從 disabled 變為可點擊
            page.wait_for_selector("#submitButton:not([disabled])", timeout=10_000)
            page.click("#submitButton")
            page.wait_for_load_state("networkidle")
            ok("同意注意事項成功（#submitButton）")
        except Exception as e:
            warn(f"自動同意失敗：{e}")
            input("  請手動捲底並點同意，完成後按 Enter...")

        # ⑤ Step1：帶入會員
        step(5, TOTAL, "Step 1：帶入會員寄件人資料...")
        try:
            page.wait_for_url("**/Mail/IBoxMailEdit**", timeout=15_000)
            page.wait_for_selector("button:has-text('帶入會員資料')", timeout=10_000)
            page.click("button:has-text('帶入會員資料')")
            page.wait_for_timeout(800)
            page.click("button:has-text('下一步')")
            page.wait_for_load_state("networkidle")
            ok("Step 1 完成")
        except Exception as e:
            warn(f"Step 1 自動化失敗：{e}")
            input("  請手動完成 Step 1 並到達 Step 2，然後按 Enter...")

        # ⑥ Step2：填收件人
        step(6, TOTAL, "Step 2：填入收件人...")

        # 姓名
        try:
            page.fill("input[placeholder*='收件人姓名']", cust["display_name"], timeout=5_000)
            info(f"姓名填入：{cust['display_name']}")
        except Exception as e:
            warn(f"姓名填入失敗：{e}")

        # 手機
        try:
            page.fill("input[placeholder*='手機']", phone, timeout=5_000)
            info(f"手機填入：{phone}")
        except Exception as e:
            warn(f"手機填入失敗：{e}")

        # 地址類型 → 一般地址 (001)
        try:
            page.select_option("#MAIL_RADD_TYPE", "001", timeout=5_000)
            info("地址類型選「一般地址」")
        except Exception as e:
            warn(f"地址類型失敗：{e}")

        # 縣市
        try:
            page.select_option("#MAIL_RADD_CITY", county, timeout=5_000)
            page.wait_for_timeout(1_000)  # 等 AJAX 載入鄉鎮市區
            info(f"縣市選「{county}」")
        except Exception as e:
            warn(f"縣市失敗：{e}")

        # 鄉鎮市區（AJAX 動態載入，等選項數量 > 1）
        try:
            page.wait_for_function(
                "document.querySelector('#MAIL_RADD_AREA').options.length > 1",
                timeout=8_000,
            )
            page.select_option("#MAIL_RADD_AREA", label=district, timeout=5_000)
            info(f"鄉鎮市區選「{district}」")
        except Exception as e:
            warn(f"鄉鎮市區失敗：{e}")

        # 路名（鄉道村里欄）
        try:
            page.fill("#MAIL_RADD_ROAD", road, timeout=5_000)
            info(f"路名填入：{road}")
        except Exception as e:
            warn(f"路名失敗：{e}")

        # 巷弄號碼樓層
        try:
            page.fill("#MAIL_RADD_OTHER", detail, timeout=5_000)
            info(f"號碼樓層填入：{detail}")
        except Exception as e:
            warn(f"號碼樓層失敗：{e}")

        try:
            page.wait_for_selector("#next-button-step", timeout=5_000)
            page.click("#next-button-step")
            page.wait_for_load_state("networkidle")
            ok("Step 2 下一步成功（#next-button-step）")
        except Exception as e:
            warn(f"下一步失敗：{e}")

        # ⑦ Step3：填包裹
        step(7, TOTAL, "Step 3：填入包裹資料...")

        # 物品種類（找含該品項的可見 select）
        try:
            for s in page.locator("select").all():
                if not s.is_visible():
                    continue
                if pkg["item_type"] in s.locator("option").all_inner_texts():
                    s.select_option(label=pkg["item_type"])
                    info(f"物品種類「{pkg['item_type']}」選取成功")
                    page.wait_for_timeout(800)
                    try:
                        page.click("button:has-text('確認')", timeout=3_000)
                        page.wait_for_timeout(500)
                    except Exception:
                        pass
                    break
        except Exception as e:
            warn(f"物品種類選取失敗：{e}")

        # 包材尺寸（#sizeDropdown）
        size_label = IBOX_SIZE_MAP.get(pkg["size"], "小")
        try:
            opts = page.locator("#sizeDropdown option").all_inner_texts()
            match = next((o for o in opts if size_label in o), None)
            if match:
                page.select_option("#sizeDropdown", label=match)
                info(f"包材尺寸選取成功：{match}")
                try:
                    page.wait_for_selector(".confirm-btn-alert", timeout=5_000)
                    page.click(".confirm-btn-alert")
                    page.wait_for_timeout(500)
                except Exception:
                    pass
        except Exception as e:
            warn(f"包材尺寸選取失敗：{e}")

        # 內裝物品描述
        for sel in ["input[placeholder*='內裝物品']", "input[placeholder*='物品']",
                    "input[placeholder*='品名']", "input[placeholder*='描述']", "textarea"]:
            try:
                page.fill(sel, pkg["description"], timeout=3_000)
                info(f"內裝物品描述填入：{pkg['description']}")
                break
            except Exception:
                pass

        try:
            page.wait_for_selector("#next-button-step", timeout=5_000)
            page.click("#next-button-step")
            page.wait_for_load_state("networkidle")
            ok("Step 3 下一步成功")
        except Exception as e:
            warn(f"下一步失敗：{e}")

        # ⑧ 確認寄件（按鈕 #ConfirmSendMailInfo，URL 仍在 IBoxMailEdit）
        step(8, TOTAL, "確認寄件...")
        try:
            page.wait_for_selector("#ConfirmSendMailInfo", timeout=10_000)
            page.click("#ConfirmSendMailInfo")
            page.wait_for_selector(".confirm-btn-alert", timeout=8_000)
            page.click(".confirm-btn-alert")
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1_000)
            ok("確認寄件送出")
        except Exception as e:
            warn(f"確認寄件失敗：{e}")

        # ⑨ QR Code
        step(9, TOTAL, "等待 QR Code 頁面...")
        try:
            page.wait_for_url("**/MailShipCompleted**", timeout=30_000)
            ok("已到達完成頁！")

            download_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(download_dir, exist_ok=True)

            try:
                with page.expect_download(timeout=15_000) as dl_info:
                    page.click(
                        "button:has-text('下載寄件 QR Code'), a:has-text('下載寄件 QR Code')"
                    )
                dl = dl_info.value
                fname = dl.suggested_filename or "ibox_qr.png"
                save_path = os.path.join(download_dir, fname)
                dl.save_as(save_path)
                ok(f"QR Code 已下載：{save_path}")
            except Exception:
                warn("下載按鈕失敗，嘗試截圖 QR Code...")
                try:
                    qr_el = page.locator("img[src*='qr'], img[alt*='QR'], canvas").first
                    save_path = os.path.join(download_dir, "ibox_qr.png")
                    qr_el.screenshot(path=save_path)
                    ok(f"截圖儲存：{save_path}")
                except Exception as e2:
                    fail(f"QR Code 取得失敗：{e2}")
        except Exception as e:
            fail(f"未到達完成頁：{e}")

        print("\n" + "=" * 50)
        print("  測試完成！")
        print("=" * 50)
        browser.close()


if __name__ == "__main__":
    run()
