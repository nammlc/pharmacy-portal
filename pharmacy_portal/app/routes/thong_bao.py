"""Thông báo cho admin: API chuông (JSON, hỏi định kỳ) và trang xem tất cả."""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models.models import ThongBao, YKien, TinNhanRieng
from app.utils import thong_bao as TB
from app.utils import kenh_ngoai as KN
from app.utils.phan_hoi import duong_dan_noi_bo
from app.utils.thoi_gian import gio_vn

bp = Blueprint("tb_api", __name__, url_prefix="/api/thong-bao")
bp_admin = Blueprint("admin_thong_bao", __name__, url_prefix="/admin/thong-bao", cli_group=None)   # cli_group=None: lệnh flask nằm ở cấp cao nhất
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
    muc = TB.gan_day(current_user.id)
    tl = TB.trang_thai_tra_loi(muc, gio_vn)                     # đã được trả lời chưa, bởi ai
    return _json({"ok": True, "chua_doc": TB.dem_chua_doc(current_user.id),
                  "muc": [TB.thanh_dict(t, gio_vn, tl.get(t.id)) for t in muc]})


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
                           tra_loi=TB.trang_thai_tra_loi(muc, gio_vn),
                           chua_doc=TB.dem_chua_doc(current_user.id), kenh=KN.trang_thai_kenh())


@bp_admin.post("/gui-thu")
def gui_thu():
    """Gửi thử Telegram + email để kiểm tra cấu hình đúng chưa."""
    for muc, noi_dung in KN.gui_thu(current_user):
        flash(noi_dung, {"ok": "success", "error": "error"}.get(muc, "info"))
    return redirect(url_for("admin_thong_bao.danh_sach"))


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


# ── Lệnh nhắc việc: chạy định kỳ (vd mỗi 4 giờ) bằng "Scheduled Task" của Coolify / cron ──
import click                                                        # noqa: E402
from datetime import datetime, timedelta                            # noqa: E402


@bp_admin.cli.command("nhac-chua-tra-loi")
@click.option("--gio", type=int, default=None, help="Nhắc các mục chưa ai trả lời quá N giờ (mặc định NHAC_CHUA_TRA_LOI_GIO = 4)")
def nhac_chua_tra_loi(gio):
    """Gửi 1 bản tóm tắt (Telegram + email tới TẤT CẢ admin đã đăng ký) về các ý kiến / tin nhắn riêng CHƯA AI TRẢ LỜI quá N giờ."""
    from flask import current_app
    from app.models.models import KhachHang
    gio = gio or int(current_app.config.get("NHAC_CHUA_TRA_LOI_GIO", 4))
    if not current_app.config.get("APP_BASE_URL"):
        raise click.ClickException("Cần đặt biến APP_BASE_URL (địa chỉ website, vd https://www.tracuuduoc-bvdktamduccauquan.com) để làm link trong thông báo.")
    bay_gio = datetime.utcnow()
    moc = bay_gio - timedelta(hours=gio)
    muc = []
    # ý kiến công khai: chưa duyệt hoặc đã duyệt nhưng chưa có câu trả lời
    yks = (YKien.query.filter(YKien.trang_thai.in_(("cho_duyet", "da_duyet")), db.or_(YKien.tra_loi.is_(None), YKien.tra_loi == ""),
                              YKien.ngay_tao <= moc).order_by(YKien.ngay_tao.asc()).limit(100).all())
    for y in yks:
        muc.append({"tieu_de": f"Ý kiến: {y.doi_tuong_ten} ({y.ten})", "tuoi_gio": int((bay_gio - y.ngay_tao).total_seconds() // 3600),
                    "rieng_tu": False})
    # chat riêng: tin cuối là của khách và đã quá hạn (KHÔNG đưa nội dung vào thông báo)
    from sqlalchemy import func
    cuoi = db.session.query(TinNhanRieng.khach_id, func.max(TinNhanRieng.id).label("mid")).group_by(TinNhanRieng.khach_id).subquery()
    for tn, k in (db.session.query(TinNhanRieng, KhachHang).join(cuoi, cuoi.c.mid == TinNhanRieng.id)
                  .join(KhachHang, KhachHang.id == TinNhanRieng.khach_id)
                  .filter(TinNhanRieng.tu == "khach", TinNhanRieng.ngay_tao <= moc).order_by(TinNhanRieng.ngay_tao.asc()).limit(100).all()):
        muc.append({"tieu_de": f"Tin nhắn riêng: {k.ten}", "tuoi_gio": int((bay_gio - tn.ngay_tao).total_seconds() // 3600), "rieng_tu": True})
    muc.sort(key=lambda m: -m["tuoi_gio"])
    n = KN.nhac_viec(muc)
    click.echo(f"Đã nhắc {n} mục chưa trả lời quá {gio} giờ." if n else f"Không có mục nào chưa trả lời quá {gio} giờ (hoặc chưa cấu hình kênh nhận).")
