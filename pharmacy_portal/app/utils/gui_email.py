"""Gửi email. Hỗ trợ 2 cách (chọn theo biến môi trường):

1. Google Apps Script (GAS_MAIL_URL + GAS_MAIL_SECRET): gửi từ chính Gmail của bạn,
   gửi được tới mọi email, không cần tên miền. Ưu tiên nếu được cấu hình.
2. Resend (RESEND_API_KEY + MAIL_FROM): cần verify tên miền mới gửi được tới email
   khác ngoài chủ tài khoản Resend.

Chỉ dùng thư viện chuẩn (urllib) nên không cần thêm package vào requirements.txt.
Cả hai đều gọi qua HTTPS, không dùng cổng SMTP (Render free chặn cổng SMTP).
"""
import json
import logging
import urllib.error
import urllib.request

from flask import current_app

RESEND_URL = "https://api.resend.com/emails"
log = logging.getLogger(__name__)


def gui_email(den, tieu_de, noi_dung_html, noi_dung_text=None):
    """Gửi 1 email. Trả về True nếu gửi thành công, False nếu lỗi.

    Không raise exception để luồng chính (quên mật khẩu) tự xử lý thông báo.
    """
    if current_app.config.get("GAS_MAIL_URL"):
        return _gui_qua_apps_script(den, tieu_de, noi_dung_html, noi_dung_text)
    return _gui_qua_resend(den, tieu_de, noi_dung_html, noi_dung_text)


def _gui_qua_apps_script(den, tieu_de, html, text):
    payload = {
        "secret": current_app.config.get("GAS_MAIL_SECRET", ""),
        "to": den,
        "subject": tieu_de,
        "html": html,
        "text": text or "",
        "name": current_app.config.get("MAIL_NAME", ""),
    }
    req = urllib.request.Request(
        current_app.config["GAS_MAIL_URL"],
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8", "User-Agent": "pharmacy-portal/1.0"},
        method="POST",
    )
    try:
        # Apps Script chạy script ngay khi nhận POST rồi trả 302 sang địa chỉ chứa kết quả;
        # urllib tự đi theo redirect (chuyển thành GET) để đọc kết quả JSON.
        with urllib.request.urlopen(req, timeout=20) as resp:
            kq = json.loads(resp.read().decode("utf-8", "replace"))
        if kq.get("ok"):
            return True
        log.error("Apps Script từ chối gửi mail: %s", kq.get("error"))
    except urllib.error.HTTPError as e:
        log.error("Apps Script trả lỗi %s: %s", e.code, e.read().decode("utf-8", "replace")[:300])
    except Exception as e:
        log.error("Không gọi được Apps Script: %s", e)
    return False


def _gui_qua_resend(den, tieu_de, html, text):
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        log.error("Chưa cấu hình GAS_MAIL_URL hoặc RESEND_API_KEY - không gửi được email.")
        return False

    payload = {
        "from": current_app.config["MAIL_FROM"],
        "to": [den],
        "subject": tieu_de,
        "html": html,
    }
    if text:
        payload["text"] = text

    req = urllib.request.Request(
        RESEND_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Resend nằm sau Cloudflare, User-Agent mặc định của urllib hay bị chặn (403)
            "User-Agent": "pharmacy-portal/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        log.error("Resend trả lỗi %s: %s", e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:
        log.error("Không gọi được Resend: %s", e)
    return False
