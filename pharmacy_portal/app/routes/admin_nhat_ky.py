import csv
import io
import re
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.models.models import NhatKy

bp = Blueprint("admin_nhat_ky", __name__, url_prefix="/admin/nhat-ky")

NHAN_LOAI = {
    "tim_kiem": "Tìm kiếm",
    "sua_du_lieu": "Sửa dữ liệu",
    "dang_nhap": "Đăng nhập",
    "dang_nhap_that_bai": "Đăng nhập sai",
    "dang_xuat": "Đăng xuất",
    "tai_khoan": "Tài khoản",
}
NHAN_HANH_DONG = {
    "them": "Thêm", "sua": "Sửa", "xoa": "Xoá", "xoa_hang_loat": "Xoá hàng loạt",
    "xoa_tat_ca": "Xoá tất cả", "nhap": "Nhập hàng loạt",
}
TRANG_MOI_TRANG = 30
_RE_IP_DAY_DU = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


@bp.before_request
@login_required
def _chi_quan_tri():
    # Nhật ký chứa IP nên chỉ tài khoản quản trị mới xem được
    if current_user.vai_tro != "quan_tri":
        abort(403)


def _gio_vn_sang_utc(chuoi, cuoi_ngay=False):
    """'2026-10-22' (giờ VN) -> datetime UTC naive để so sánh với cột thoi_gian."""
    try:
        d = datetime.strptime(chuoi, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    if cuoi_ngay:
        d += timedelta(days=1)
    return d - timedelta(hours=7)


def _loc():
    q = NhatKy.query
    a = request.args
    if a.get("loai") in NHAN_LOAI:
        q = q.filter(NhatKy.loai == a["loai"])
    ip = (a.get("ip") or "").strip()
    if ip:
        q = q.filter(NhatKy.ip == ip) if (_RE_IP_DAY_DU.match(ip) or ":" in ip) else q.filter(NhatKy.ip.like(ip + "%"))
    cookie = (a.get("cookie") or "").strip()
    if cookie:
        q = q.filter(NhatKy.cookie_id.like(cookie + "%"))
    tu_khoa = (a.get("q") or "").strip()
    if tu_khoa:
        m = f"%{tu_khoa}%"
        q = q.filter(db.or_(NhatKy.tu_khoa.ilike(m), NhatKy.doi_tuong_ten.ilike(m),
                            NhatKy.doi_tuong.ilike(m), NhatKy.ten_nguoi_dung.ilike(m),
                            NhatKy.mo_ta.ilike(m)))
    tu = _gio_vn_sang_utc(a.get("tu_ngay"))
    den = _gio_vn_sang_utc(a.get("den_ngay"), cuoi_ngay=True)
    if tu:
        q = q.filter(NhatKy.thoi_gian >= tu)
    if den:
        q = q.filter(NhatKy.thoi_gian < den)
    return q


def _thong_ke():
    bay_ngay = datetime.utcnow() - timedelta(days=7)
    hom_nay = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    # "hôm nay" theo giờ VN: mốc 00:00 VN = 17:00 UTC hôm trước
    now_vn = datetime.utcnow() + timedelta(hours=7)
    dau_ngay_utc = now_vn.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=7)

    so_tim_hom_nay = NhatKy.query.filter(NhatKy.loai == "tim_kiem", NhatKy.thoi_gian >= dau_ngay_utc).count()
    so_ip_hom_nay = (db.session.query(func.count(func.distinct(NhatKy.ip)))
                     .filter(NhatKy.loai == "tim_kiem", NhatKy.thoi_gian >= dau_ngay_utc).scalar() or 0)
    so_sua_7_ngay = NhatKy.query.filter(NhatKy.loai == "sua_du_lieu", NhatKy.thoi_gian >= bay_ngay).count()
    so_dn_sai_7_ngay = NhatKy.query.filter(NhatKy.loai == "dang_nhap_that_bai", NhatKy.thoi_gian >= bay_ngay).count()

    top_tu_khoa = (db.session.query(NhatKy.tu_khoa, func.count(NhatKy.id).label("n"))
                   .filter(NhatKy.loai == "tim_kiem", NhatKy.thoi_gian >= bay_ngay, NhatKy.tu_khoa.isnot(None))
                   .group_by(NhatKy.tu_khoa).order_by(func.count(NhatKy.id).desc()).limit(5).all())
    top_ip = (db.session.query(NhatKy.ip, func.count(NhatKy.id).label("n"))
              .filter(NhatKy.thoi_gian >= bay_ngay, NhatKy.ip.isnot(None))
              .group_by(NhatKy.ip).order_by(func.count(NhatKy.id).desc()).limit(5).all())
    return dict(so_tim_hom_nay=so_tim_hom_nay, so_ip_hom_nay=so_ip_hom_nay,
                so_sua_7_ngay=so_sua_7_ngay, so_dn_sai_7_ngay=so_dn_sai_7_ngay,
                top_tu_khoa=top_tu_khoa, top_ip=top_ip)


def _thiet_bi(ua):
    """User-Agent -> (biểu tượng, tên thiết bị dễ đọc, trình duyệt). Vd: ('📱', 'Android · SM-S918B', 'Chrome')."""
    if not ua:
        return "❔", "Không rõ", ""
    u = ua.lower()

    if "bot" in u or "crawler" in u or "spider" in u:
        return "🤖", "Bot / công cụ tự động", ""

    if "edg/" in u or "edga/" in u or "edgios/" in u:
        trinh = "Edge"
    elif "opr/" in u or "opera" in u:
        trinh = "Opera"
    elif "zalo" in u:
        trinh = "Zalo"
    elif "samsungbrowser" in u:
        trinh = "Samsung Internet"
    elif "firefox" in u or "fxios" in u:
        trinh = "Firefox"
    elif "chrome" in u or "crios" in u:
        trinh = "Chrome"
    elif "safari" in u:
        trinh = "Safari"
    else:
        trinh = "Khác"

    if "iphone" in u:
        return "📱", "iPhone", trinh
    if "ipad" in u:
        return "📱", "iPad", trinh
    if "android" in u:
        m = re.search(r"android [\d.]+; ([^;)]+)", ua, re.I)
        mau = m.group(1).strip() if m else ""
        if mau and mau.upper() not in ("K", "U") and len(mau) > 1:
            ten = f"Android · {mau}"
        else:
            ten = "Android"
        icon = "📱" if "mobile" in u else "📲"
        return icon, ten, trinh
    if "windows" in u:
        return "💻", "Windows", trinh
    if "mac os" in u or "macintosh" in u:
        return "💻", "Mac", trinh
    if "cros" in u:
        return "💻", "ChromeOS", trinh
    if "linux" in u:
        return "💻", "Linux", trinh
    return "❔", "Không rõ", trinh


@bp.route("/")
def danh_sach():
    trang = request.args.get("trang", 1, type=int)
    phan_trang = (_loc().order_by(NhatKy.thoi_gian.desc(), NhatKy.id.desc())
                  .paginate(page=trang, per_page=TRANG_MOI_TRANG, error_out=False))
    tham_so = {k: v for k, v in request.args.items() if k != "trang" and v}
    return render_template("admin/nhat_ky/danh_sach.html",
                           items=phan_trang.items, phan_trang=phan_trang,
                           tham_so=tham_so, nhan_loai=NHAN_LOAI, nhan_hanh_dong=NHAN_HANH_DONG,
                           thiet_bi=_thiet_bi, tk=_thong_ke(), f=request.args)


@bp.route("/xuat-csv")
def xuat_csv():
    from app.utils.thoi_gian import gio_vn
    dong = _loc().order_by(NhatKy.thoi_gian.desc()).limit(50000).all()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Thời gian (GMT+7)", "Loại", "IP", "Cookie ẩn danh", "Người dùng", "Hành động",
                "Đối tượng", "ID", "Tên", "Từ khoá tìm", "Mô tả", "Đường dẫn", "Trình duyệt"])
    for r in dong:
        w.writerow([gio_vn(r.thoi_gian).strftime("%d/%m/%Y %H:%M:%S"), NHAN_LOAI.get(r.loai, r.loai),
                    r.ip, r.cookie_id, r.ten_nguoi_dung,
                    NHAN_HANH_DONG.get(r.hanh_dong, r.hanh_dong or ""), r.doi_tuong,
                    r.doi_tuong_id, r.doi_tuong_ten, r.tu_khoa, r.mo_ta, r.duong_dan, r.trinh_duyet])
    ten_file = f"nhat_ky_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={ten_file}"})


@bp.route("/xoa-cu", methods=["POST"])
def xoa_cu():
    ngay = request.form.get("ngay", type=int)
    if not ngay or ngay < 1:
        flash("Số ngày không hợp lệ.", "danger")
        return redirect(url_for("admin_nhat_ky.danh_sach"))
    moc = datetime.utcnow() - timedelta(days=ngay)
    so = NhatKy.query.filter(NhatKy.thoi_gian < moc).delete(synchronize_session=False)
    db.session.commit()
    flash(f"Đã xoá {so} dòng nhật ký cũ hơn {ngay} ngày.", "success")
    return redirect(url_for("admin_nhat_ky.danh_sach"))
