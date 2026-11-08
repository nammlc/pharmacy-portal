"""API đếm người đang online. Chỉ có 3 đường dẫn, đều trả JSON / 204, không có trang HTML."""
from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user

from app.utils import online as _online

bp = Blueprint("online", __name__, url_prefix="/api/online")


def _khong_cache(resp):
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _204():
    return _khong_cache(current_app.response_class("", 204))


@bp.route("/ping", methods=["POST"])
def ping():
    """Trình duyệt báo "tôi còn đang xem trang". Người đã đăng nhập tính là admin, còn lại là khách.
    ?khu=admin (gửi từ trang quản trị): nếu phiên đã hết hạn thì KHÔNG tính thành khách, trả 401 để trình duyệt dừng."""
    kq = _online.nhan_dien(request.args.get("khu", "cong_khai"))
    if kq is None:                                         # bot
        return _204()
    if kq == "het_phien":
        return _khong_cache(jsonify(active=False)), 401
    loai, khoa, ten = kq
    _online.ghi_hien_dien(loai, khoa, ten)
    return _204()


@bp.route("/roi", methods=["POST"])
def roi():
    """Trình duyệt báo "tôi vừa đóng tab / rời trang" (sendBeacon) → số liệu giảm gần như ngay."""
    kq = _online.nhan_dien(request.args.get("khu", "cong_khai"))
    if kq and kq != "het_phien":
        _online.danh_dau_roi(kq[1])
    return _204()


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
