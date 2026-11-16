"""
Báo cho admin NGOÀI hệ thống — để không phải mở trang quản trị mới biết.

Chuông trên trang quản trị chỉ chạy khi có admin đang đăng nhập và mở trang. Hai kênh dưới đây đẩy thông báo ra điện thoại:
  • Telegram — tức thì, miễn phí. Cấu hình TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID (1 nhóm của Khoa Dược là đủ).
  • Email    — gửi cho TẤT CẢ admin đang hoạt động đã đăng ký email (Gmail hay email khác đều được). Dùng lại cách gửi mail
               đang cấu hình (Apps Script / Resend). Mỗi sự kiện = 1 email tới từng admin; mỗi admin tối đa
               THONG_BAO_EMAIL_TOI_DA_GIO email / giờ (chặn an toàn, phần vượt được gom vào email kế tiếp).

Các sự kiện được báo:
  1. Có ý kiến công khai / tin nhắn riêng MỚI                   → bao_admin_moi()
  2. Có admin TRẢ LỜI (để người khác biết, không trả lời trùng)   → bao_da_tra_loi()
  3. Còn ý kiến / tin nhắn CHƯA AI TRẢ LỜI quá N giờ (nhắc việc) → nhac_viec()  (chạy bằng lệnh flask nhac-chua-tra-loi)

Gửi chạy NỀN (không làm chậm người đang gửi ý kiến); mọi lỗi chỉ ghi log, không bao giờ làm hỏng yêu cầu của khách.

Riêng tư: tin nhắn RIÊNG của khách (có thể chứa thông tin sức khoẻ) KHÔNG gửi nội dung ra ngoài — chỉ báo "có tin nhắn mới từ
<tên>". Ý kiến CÔNG KHAI gửi kèm đoạn đầu (vì sẽ hiển thị công khai sau khi duyệt). Số điện thoại không bao giờ gửi ra ngoài.
"""
import collections
import html
import json
import logging
import threading
import time
import urllib.error
import urllib.request

from flask import current_app, has_request_context, request

from app import db
from app.models.models import NguoiDung

log = logging.getLogger(__name__)

TELEGRAM_CHO_MOI_CUOC_TRO_CHUYEN_GIAY = 300       # 1 cuộc trò chuyện chỉ báo Telegram tối đa 1 lần / 5 phút
_TG_LAN_CUOI = {}                                 # khoa_gop -> thời điểm (monotonic)
_EMAIL_DA_GUI = collections.defaultdict(collections.deque)   # email -> các thời điểm đã gửi (trong 1 giờ gần nhất)
_EMAIL_BI_GOM = {}                                # email -> số thông báo đã gom (vượt mức / giờ, chưa gửi)
_khoa = threading.Lock()


# ───────────────────────────── cấu hình ─────────────────────────────
def _snapshot(cfg):
    """Lấy riêng các giá trị cấu hình cần dùng (luồng nền không có app context)."""
    return {
        "token": (cfg.get("TELEGRAM_BOT_TOKEN") or "").strip(),
        "chat_ids": [c.strip() for c in (cfg.get("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()],
        "email_bat": bool(cfg.get("THONG_BAO_EMAIL", True)),
        "email_toi_da_gio": max(1, int(cfg.get("THONG_BAO_EMAIL_TOI_DA_GIO", 20))),
        "nhac_gio": max(1, int(cfg.get("NHAC_CHUA_TRA_LOI_GIO", 4))),
    }


def _admin_dang_hoat_dong():
    return NguoiDung.query.filter(db.or_(NguoiDung.dang_hoat_dong.is_(True), NguoiDung.dang_hoat_dong.is_(None))).all()


def che_email(e):
    """a1@gmail.com → a1***@gmail.com (hiển thị trong trang cài đặt, không lộ cả địa chỉ)."""
    e = (e or "").strip()
    if "@" not in e:
        return ""
    ten, mien = e.split("@", 1)
    return ten[:2] + "***@" + mien


def trang_thai_kenh():
    """Cho trang cài đặt: kênh nào đang bật, admin nào đã / chưa đăng ký email."""
    s = _snapshot(current_app.config)
    admin = _admin_dang_hoat_dong()
    chi_tiet = [{"ten": a.ho_ten or a.ten_dang_nhap, "co_email": bool((a.email or "").strip()), "email": che_email(a.email)} for a in admin]
    return {"telegram": bool(s["token"] and s["chat_ids"]), "so_nhom_telegram": len(s["chat_ids"]),
            "email_bat": s["email_bat"], "email_toi_da_gio": s["email_toi_da_gio"], "nhac_gio": s["nhac_gio"],
            "admin_co_email": sum(1 for c in chi_tiet if c["co_email"]), "admin_tong": len(admin), "admin_chi_tiet": chi_tiet}


# ───────────────────────────── Telegram ─────────────────────────────
def _post_telegram(token, chat_id, text):
    """Gửi 1 tin Telegram (chữ thuần, không parse_mode nên nội dung không bao giờ bị hiểu là mã). Trả (ok, lỗi)."""
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": True}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "pharmacy-portal/1.0"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8", "replace") or "{}")
        return (True, "") if d.get("ok") else (False, str(d.get("description", "Telegram trả về lỗi")))
    except urllib.error.HTTPError as e:
        try:
            mo_ta = json.loads(e.read().decode("utf-8", "replace")).get("description", "")
        except Exception:                                   # noqa: BLE001
            mo_ta = ""
        return False, f"HTTP {e.code} {mo_ta}".strip()
    except Exception as e:                                   # noqa: BLE001
        return False, str(e)[:200]


def _gui_telegram(s, text):
    kq = []
    for cid in s["chat_ids"]:
        ok, loi = _post_telegram(s["token"], cid, text)
        if not ok:
            log.warning("Telegram lỗi (chat %s): %s", cid, loi)
        kq.append((cid, ok, loi))
    return kq


# ───────────────────────────── Email ─────────────────────────────
def _soan_email(tieu_de, tom_tat, url, them=0, nut="Mở trang quản trị", dong_phu=None):
    them_txt = f"\n(Và {them} thông báo khác trong thời gian qua.)" if them else ""
    text = f"{tieu_de}\n" + (f"{tom_tat}\n" if tom_tat else "") + "".join(f"{d}\n" for d in (dong_phu or [])) + f"\n{nut}: {url}{them_txt}\n"
    them_html = f"<p style='color:#6b7280;font-size:13px'>Và {them} thông báo khác trong thời gian qua.</p>" if them else ""
    phu_html = "".join(f"<p style='margin:0 0 6px;color:#374151'>{html.escape(d)}</p>" for d in (dong_phu or []))
    h = (f"<div style='font-family:Arial,sans-serif;max-width:520px'><h3 style='margin:0 0 8px'>{html.escape(tieu_de)}</h3>"
         + (f"<p style='margin:0 0 10px;color:#374151'>{html.escape(tom_tat)}</p>" if tom_tat else "") + phu_html
         + f"<p style='margin-top:14px'><a href='{html.escape(url, quote=True)}' style='background:#0f2642;color:#fff;padding:10px 18px;"
           f"border-radius:8px;text-decoration:none;display:inline-block'>{html.escape(nut)}</a></p>{them_html}"
         + "<p style='color:#9ca3af;font-size:12px'>Thư tự động từ Cổng Tra Cứu Dược. Cần đăng nhập để xem chi tiết.</p></div>")
    return h, text


def _gui_email_admin(s, emails, tieu_de, tom_tat, url, nut="Mở trang quản trị", dong_phu=None):
    """Gửi cho từng email trong danh sách (mỗi sự kiện 1 thư). Mỗi địa chỉ tối đa `email_toi_da_gio` thư / giờ."""
    from app.utils.gui_email import gui_email
    bay_gio = time.monotonic()
    for e in emails:
        e = e.strip(); k = e.lower()
        with _khoa:
            ds = _EMAIL_DA_GUI[k]
            while ds and bay_gio - ds[0] > 3600:
                ds.popleft()
            if len(ds) >= s["email_toi_da_gio"]:                                     # vượt mức an toàn → gom, thư sau sẽ nhắc
                _EMAIL_BI_GOM[k] = _EMAIL_BI_GOM.get(k, 0) + 1
                continue
            them = _EMAIL_BI_GOM.pop(k, 0)
            ds.append(bay_gio)
        h, t = _soan_email(tieu_de, tom_tat, url, them, nut, dong_phu)
        try:
            if not gui_email(e, f"[Khoa Dược] {tieu_de}"[:150], h, t):
                log.warning("Không gửi được email thông báo tới %s", e)
        except Exception:                                    # noqa: BLE001
            log.exception("Lỗi gửi email thông báo tới %s", e)


# ───────────────────────────── điểm vào ─────────────────────────────
def _chay_nen(ham):
    """Chạy trong luồng nền (không làm chậm yêu cầu của khách); khi TESTING thì chạy tuần tự cho dễ kiểm tra."""
    def an_toan():
        try:
            ham()
        except Exception:                                                   # noqa: BLE001
            log.exception("Lỗi báo ngoài hệ thống")
    if current_app.config.get("TESTING"):
        an_toan()
    else:
        app = current_app._get_current_object()

        def trong_app():
            with app.app_context():
                an_toan()
        threading.Thread(target=trong_app, daemon=True).start()


def _chuan_bi(duong_dan, bo_qua_email=None):
    """Cấu hình + người nhận + link tuyệt đối. Trả None nếu không có kênh nào để gửi."""
    s = _snapshot(current_app.config)
    co_telegram = bool(s["token"] and s["chat_ids"])
    bo = (bo_qua_email or "").strip().lower()
    emails = ([a.email.strip() for a in _admin_dang_hoat_dong()
               if (a.email or "").strip() and a.email.strip().lower() != bo] if s["email_bat"] else [])
    if not co_telegram and not emails:
        return None
    goc = (current_app.config.get("APP_BASE_URL") or (request.url_root if has_request_context() else "")).rstrip("/")
    if not goc:                                                             # ngoài yêu cầu web (lệnh nhắc việc) cần APP_BASE_URL để làm link
        return None
    return s, co_telegram, emails, goc + duong_dan


def bao_admin_moi(loai, tieu_de, tom_tat, duong_dan, khoa_gop=None):
    """1) Báo ra ngoài (Telegram + email TỚI TẤT CẢ admin đã đăng ký email) về 1 ý kiến / tin nhắn MỚI. GỌI SAU KHI ĐÃ COMMIT.
    loai: y_kien_moi | tin_nhan_moi.  tom_tat: nội dung được phép gửi ra ngoài (để trống nếu riêng tư). Không ném lỗi."""
    try:
        cb = _chuan_bi(duong_dan)
        if cb is None:
            return
        s, co_telegram, emails, url = cb
        tom_tat = " ".join((tom_tat or "").split())[:140]
        bieu_tuong = "💬" if loai == "y_kien_moi" else "✉️"
        text = f"{bieu_tuong} {tieu_de}\n⏳ Chưa ai trả lời" + (f"\n{tom_tat}" if tom_tat else "") + f"\n👉 {url}"
        if co_telegram and khoa_gop:                                        # 1 cuộc trò chuyện không báo Telegram dồn dập
            bay_gio = time.monotonic()
            with _khoa:
                lan_cuoi = _TG_LAN_CUOI.get(khoa_gop)
                if lan_cuoi is not None and bay_gio - lan_cuoi < TELEGRAM_CHO_MOI_CUOC_TRO_CHUYEN_GIAY:
                    co_telegram = False
                else:
                    _TG_LAN_CUOI[khoa_gop] = bay_gio
        if not co_telegram and not emails:
            return

        def chay():
            if co_telegram:
                _gui_telegram(s, text)
            if emails:
                _gui_email_admin(s, emails, tieu_de, tom_tat, url, dong_phu=["⏳ Trạng thái: chưa ai trả lời."])
        _chay_nen(chay)
    except Exception:                                                       # noqa: BLE001
        log.exception("Không chuẩn bị được thông báo ngoài hệ thống")


def bao_da_tra_loi(tieu_de, nguoi_tra_loi, duong_dan, email_nguoi_tra_loi=None, rieng_tu=False):
    """2) Có admin vừa TRẢ LỜI → báo cho các admin còn lại (Telegram + email, trừ chính người trả lời) để không ai trả lời trùng.
    rieng_tu=True (chat riêng): chỉ báo "đã trả lời", không kèm nội dung. GỌI SAU KHI ĐÃ COMMIT."""
    try:
        cb = _chuan_bi(duong_dan, bo_qua_email=email_nguoi_tra_loi)
        if cb is None:
            return
        s, co_telegram, emails, url = cb
        tieu = f"✔ Đã trả lời: {tieu_de}"
        dong = f"{nguoi_tra_loi or 'Một admin'} đã trả lời" + (" tin nhắn riêng này." if rieng_tu else " ý kiến này.")
        text = f"✔ {tieu_de}\n{dong}\n👉 {url}"

        def chay():
            if co_telegram:
                _gui_telegram(s, text)
            if emails:
                _gui_email_admin(s, emails, tieu, "", url, nut="Xem lại", dong_phu=[f"✔ {dong}"])
        _chay_nen(chay)
    except Exception:                                                       # noqa: BLE001
        log.exception("Không chuẩn bị được thông báo 'đã trả lời'")


def nhac_viec(muc):
    """3) Nhắc việc: `muc` = [{"tieu_de", "tuoi_gio", "url" (đường dẫn nội bộ), "rieng_tu": bool}] — những ý kiến / tin nhắn CHƯA AI TRẢ LỜI.
    Gửi 1 bản tóm tắt qua Telegram + email (tới tất cả admin đã đăng ký). Trả số mục đã nhắc. Gọi từ lệnh flask nhac-chua-tra-loi."""
    if not muc:
        return 0
    cb = _chuan_bi("/admin/y-kien/?trang_thai=tat_ca&tra_loi=chua")
    if cb is None:
        return 0
    s, co_telegram, emails, url_chung = cb
    goc = url_chung.split("/admin/", 1)[0]
    dong = [f"• {m['tieu_de']} — chờ {m['tuoi_gio']} giờ" for m in muc[:10]] + ([f"… và {len(muc) - 10} mục khác"] if len(muc) > 10 else [])
    tieu_de = f"⏰ Còn {len(muc)} ý kiến / tin nhắn chưa ai trả lời"
    text = tieu_de + "\n" + "\n".join(dong) + f"\n👉 {goc}/admin/thong-bao/"
    if co_telegram:
        _gui_telegram(s, text)
    if emails:
        _gui_email_admin(s, emails, tieu_de, "", goc + "/admin/thong-bao/", nut="Mở danh sách", dong_phu=dong)
    return len(muc)


def gui_thu(admin):
    """Nút "Gửi thử" ở trang cài đặt: gửi 1 tin thử qua từng kênh (ĐỒNG BỘ) và trả về kết quả dễ hiểu."""
    s = _snapshot(current_app.config)
    kq = []
    if s["token"] and s["chat_ids"]:
        for cid, ok, loi in _gui_telegram(s, "✅ Tin thử từ Cổng Tra Cứu Dược: Telegram đã nhận được thông báo."):
            kq.append(("ok", f"Telegram ({cid}): đã gửi.") if ok else ("error", f"Telegram ({cid}) lỗi: {loi}"))
    else:
        kq.append(("info", "Telegram: chưa cấu hình (thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID)."))
    email = (admin.email or "").strip()
    if not s["email_bat"]:
        kq.append(("info", "Email: đang tắt (THONG_BAO_EMAIL=0)."))
    elif not email:
        kq.append(("info", "Email: bạn chưa đăng ký email (vào menu tài khoản → Cập nhật email)."))
    else:
        from app.utils.gui_email import gui_email
        h, t = _soan_email("Tin thử: email thông báo hoạt động", "Nếu bạn đọc được thư này, email thông báo đã cấu hình đúng.",
                           (current_app.config.get("APP_BASE_URL") or request.url_root).rstrip("/") + "/admin/")
        ok = gui_email(email, "[Khoa Dược] Tin thử: email thông báo", h, t)
        kq.append(("ok", f"Email ({email}): đã gửi.") if ok else ("error", f"Email ({email}): gửi không được, xem nhật ký máy chủ."))
    return kq
