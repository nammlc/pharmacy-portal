"""Thông báo cho admin: API chuông (JSON, hỏi định kỳ) và trang xem tất cả."""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models.models import ThongBao, YKien, TinNhanRieng
from app.utils import thong_bao as TB
from app.utils.phan_hoi import duong_dan_noi_bo
from app.utils.thoi_gian import gio_vn

bp = Blueprint("tb_api", __name__, url_prefix="/api/thong-bao")
bp_admin = Blueprint("admin_thong_bao", __name__, url_prefix="/admin/thong-bao")
MOI_TRANG = 30


def _json(d, ma=200):
    r = jsonify(d)
    r.status_code = ma
    r.headers["Cache-Control"] = "no-store"
    return r


@bp.get("/tom-tat")
def tom_tat():
    """Số chưa đọc + vài thông báo gần nhất cho chuông. Hỏi định kỳ nên KHÔNG làm mới giờ hoạt động của phiên (xem phien_dang_nhap)."""
    if not current_user.is_authenticated:
        return _json({"ok": False, "loi": "chua_dang_nhap"}, 401)
    return _json({"ok": True, "chua_doc": TB.dem_chua_doc(current_user.id),
                  "muc": [TB.thanh_dict(t, gio_vn) for t in TB.gan_day(current_user.id)]})


@bp.post("/doc/<int:tb_id>")
def doc_mot(tb_id):
    if not current_user.is_authenticated:
        return _json({"ok": False}, 401)
    TB.danh_dau_da_doc(current_user.id, tb_id)
    return _json({"ok": True, "chua_doc": TB.dem_chua_doc(current_user.id)})


@bp.post("/doc-tat-ca")
def doc_tat_ca():
    if not current_user.is_authenticated:
        return _json({"ok": False}, 401)
    TB.danh_dau_da_doc(current_user.id)
    return _json({"ok": True, "chua_doc": 0})


@bp_admin.before_request
@login_required
def _yeu_cau_dang_nhap():
    return None


@bp_admin.get("/")
def danh_sach():
    chi_chua_doc = request.args.get("chua_doc") == "1"
    try:
        trang = max(1, int(request.args.get("trang", 1)))
    except ValueError:
        trang = 1
    q = ThongBao.query.filter_by(nguoi_nhan_id=current_user.id)
    if chi_chua_doc:
        q = q.filter_by(da_doc=False)
    tong = q.count()
    muc = q.order_by(ThongBao.ngay_tao.desc(), ThongBao.id.desc()).offset((trang - 1) * MOI_TRANG).limit(MOI_TRANG).all()
    return render_template("admin/thong_bao.html", muc=muc, tong=tong, trang=trang, moi_trang=MOI_TRANG, chi_chua_doc=chi_chua_doc,
                           chua_doc=TB.dem_chua_doc(current_user.id))


@bp_admin.get("/mo/<int:tb_id>")
def mo(tb_id):
    """Bấm vào 1 thông báo: đánh dấu đã đọc rồi chuyển tới nơi cần xử lý (chỉ chuyển tới đường dẫn nội bộ)."""
    tb = ThongBao.query.filter_by(id=tb_id, nguoi_nhan_id=current_user.id).first() or abort(404)
    TB.danh_dau_da_doc(current_user.id, tb.id)
    return redirect(duong_dan_noi_bo(tb.url) or url_for("admin_thong_bao.danh_sach"))


@bp_admin.post("/doc-tat-ca")
def doc_tat_ca_trang():
    TB.danh_dau_da_doc(current_user.id)
    return redirect(url_for("admin_thong_bao.danh_sach"))


# Số liệu cho menu bên trái + chuông (chỉ chạy ở trang quản trị; lỗi DB không được làm hỏng trang)
@bp_admin.app_context_processor
def _so_lieu_admin():
    try:
        if request.path.startswith("/admin") and current_user.is_authenticated:
            return {
                "dem_y_kien_cho_duyet": YKien.query.filter_by(trang_thai="cho_duyet").count(),
                "dem_tin_nhan_chua_doc": db.session.query(func.count(func.distinct(TinNhanRieng.khach_id)))
                                         .filter(TinNhanRieng.tu == "khach", TinNhanRieng.da_doc_admin.is_(False)).scalar() or 0,
                "dem_thong_bao": TB.dem_chua_doc(current_user.id),
            }
    except Exception:                                                  # noqa: BLE001
        db.session.rollback()
    return {"dem_y_kien_cho_duyet": 0, "dem_tin_nhan_chua_doc": 0, "dem_thong_bao": 0}
