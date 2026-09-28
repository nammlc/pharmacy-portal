"""Gửi email qua Resend (https://resend.com) bằng REST API.

Chỉ dùng thư viện chuẩn (urllib) nên không cần thêm package vào requirements.txt.
"""
import json
import logging
import urllib.error
import urllib.request

from flask import current_app

RESEND_URL = "https://api.resend.com/emails"
log = logging.getLogger(__name__)


def gui_email(den, tieu_de, noi_dung_html, noi_dung_text=None):
    """Gửi 1 email. Trả về True nếu Resend nhận thành công, False nếu lỗi.

    Không raise exception để luồng chính (quên mật khẩu) không bị lộ lỗi ra người dùng.
    """
    api_key = current_app.config.get("RESEND_API_KEY")
    if not api_key:
        log.error("Chưa cấu hình RESEND_API_KEY - không gửi được email.")
        return False

    payload = {
        "from": current_app.config["MAIL_FROM"],
        "to": [den],
        "subject": tieu_de,
        "html": noi_dung_html,
    }
    if noi_dung_text:
        payload["text"] = noi_dung_text

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
    except Exception as e:  # mạng lỗi, timeout...
        log.error("Không gọi được Resend: %s", e)
    return False
