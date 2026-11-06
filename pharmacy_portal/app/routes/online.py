"""API đếm người đang online. Chỉ có 2 đường dẫn, đều trả JSON / 204, không có trang HTML."""
from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user

from app.utils import online as _online

bp = Blueprint("online", __name__, url_prefix="/api/online")


def _khong_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/ping", methods=["POST"])
def ping():
    """Trình duyệt báo "tôi còn đang xem trang". Người đã đăng nhập tính là admin, còn lại là khách.
    ?khu=admin (gửi từ trang quản trị): nếu phiên đã hết hạn thì KHÔNG tính thành khách, trả 401 để trình duyệt dừng."""
    khu = request.args.get("khu", "cong_khai")
    if _online.la_bot():
        return ("", 204)
    if current_user.is_authenticated:
        ten = getattr(current_user, "ho_ten", None) or current_user.ten_dang_nhap
        _online.ghi_hien_dien("admin", f"a:{current_user.id}", ten)
        return _khong_cache(current_app.response_class("", 204))
    if khu == "admin":
        return _khong_cache(jsonify(active=False)), 401
    _online.ghi_hien_dien("khach", _online.khoa_khach())
    return _khong_cache(current_app.response_class("", 204))


@bp.route("/thong-ke")
def thong_ke():
    """Số admin / người dùng đang online — chỉ cho người đã đăng nhập (ô thống kê ở trang quản trị)."""
    if not current_user.is_authenticated:
        return _khong_cache(jsonify(loi="chua_dang_nhap")), 401
    try:
        return _khong_cache(jsonify(_online.dem()))
    except Exception as e:                                # noqa: BLE001
        current_app.logger.warning(f"Không đọc được số người online: {e}")
        return _khong_cache(jsonify(loi="khong_doc_duoc")), 503
