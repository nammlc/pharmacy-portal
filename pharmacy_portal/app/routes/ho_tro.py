"""Chat riêng tư giữa khách và Khoa Dược (không mã bí mật; cuộc trò chuyện gắn với thiết bị bằng cookie đã ký). Trang và API đều không được lập chỉ mục."""
from flask import Blueprint, current_app, jsonify, make_response, render_template, request

from app import db
from app.utils import chat_rieng as CR
from app.utils.online import la_bot
from app.utils.phan_hoi import duong_dan_noi_bo, lam_sach
from app.utils.thoi_gian import gio_vn

bp = Blueprint("ho_tro", __name__)


def _json(d, ma=200):
    r = jsonify(d)
    r.status_code = ma
    r.headers["Cache-Control"] = "no-store"
    return r


def _loi(t, ma=400):
    return _json({"ok": False, "loi": t}, ma)


def _tin_dict(tin):
    return [CR.tin_thanh_dict(t, gio_vn) for t in tin]


@bp.get("/ho-tro")
def trang():
    """Trang chat riêng. Chưa có cuộc trò chuyện trên thiết bị này → form (họ tên + SĐT + tin nhắn). Đã có → cuộc trò chuyện."""
    khach = CR.khach_hien_tai()
    loai = request.args.get("loai", "ho_tro")
    ngu_canh = lam_sach(request.args.get("ngu_canh", "")).replace("\n", " ")[:200]
    ngu_canh_url = duong_dan_noi_bo(request.args.get("url", "")) or ""
    tin = CR.danh_sach_tin(khach, danh_dau_khach_da_doc=True) if khach else []
    resp = make_response(render_template("ho_tro.html", khach=khach, tin_nhan=_tin_dict(tin), loai=loai if loai in CR.LOAI_TIN else "ho_tro",
                                         ngu_canh=ngu_canh, ngu_canh_url=ngu_canh_url, loai_tin=CR.LOAI_TIN))
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


@bp.post("/api/ho-tro/dang-nhap")
def dang_nhap():
    """Mở cuộc trò chuyện mới (họ tên + SĐT, không mã bí mật) rồi nhớ thiết bị 30 ngày bằng cookie đã ký.
    Thiết bị đã có cuộc trò chuyện thì dùng lại, không tạo thêm."""
    d = request.get_json(silent=True) or request.form
    if str(d.get("website", "")).strip() or la_bot():
        return _loi("Yêu cầu không hợp lệ.")
    khach = CR.khach_hien_tai()
    if khach is not None:
        return _json({"ok": True, "moi": False, "ten": khach.ten})
    khach, loi = CR.bat_dau(d.get("sdt"), d.get("ten"))
    if loi:
        return _loi(loi, 429 if "quá nhiều" in loi else 400)
    resp = _json({"ok": True, "moi": True, "ten": khach.ten})
    return CR.cap_phien(resp, khach)


@bp.post("/api/ho-tro/gui")
def gui():
    khach = CR.khach_hien_tai()
    if khach is None:
        return _loi("Phiên đã hết hạn, vui lòng nhập lại họ tên và số điện thoại để bắt đầu lại.", 401)
    d = request.get_json(silent=True) or request.form
    if str(d.get("website", "")).strip():
        return _json({"ok": True, "tin": []})
    tn, loi = CR.gui_tin_nhan(khach, d.get("noi_dung"), str(d.get("loai", "ho_tro")), d.get("ngu_canh"), d.get("ngu_canh_url"))
    if loi:
        return _loi(loi, 429 if "nhiều tin" in loi else 400)
    return _json({"ok": True, "tin": _tin_dict([tn])})


@bp.get("/api/ho-tro/tin-nhan")
def tin_nhan():
    """Tin mới sau id `sau` (trình duyệt hỏi định kỳ khi đang mở cuộc trò chuyện)."""
    khach = CR.khach_hien_tai()
    if khach is None:
        return _loi("Phiên đã hết hạn.", 401)
    try:
        sau = int(request.args.get("sau", 0))
    except ValueError:
        sau = 0
    return _json({"ok": True, "tin": _tin_dict(CR.danh_sach_tin(khach, sau, danh_dau_khach_da_doc=True))})


@bp.post("/api/ho-tro/thoat")
def thoat():
    return CR.xoa_phien(_json({"ok": True}))
