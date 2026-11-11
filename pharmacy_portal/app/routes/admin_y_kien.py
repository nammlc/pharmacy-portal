"""Admin: duyệt / từ chối / trả lời hỏi đáp công khai dưới thuốc và bài viết."""
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models.models import YKien
from app.utils import phan_hoi as PH
from app.utils import thong_bao as TB
from app.utils.nhat_ky import ghi

bp = Blueprint("admin_y_kien", __name__, url_prefix="/admin/y-kien")
MOI_TRANG = 20
HANH_DONG = {"duyet": "da_duyet", "tu_choi": "tu_choi", "spam": "spam", "cho_duyet": "cho_duyet"}


def _nhat_ky(yk, hanh_dong):
    """Thông tin để ghi nhật ký SAU khi đã commit (ghi() dùng kết nối riêng; ghi lúc còn giao dịch mở dễ bị khoá trên SQLite)."""
    return (hanh_dong[:30], yk.id, (yk.doi_tuong_ten or "")[:255], f"{yk.ten}: {(yk.noi_dung or '')[:200]}")


def _ghi_sau(muc):
    for hanh_dong, yid, ten_dt, mo_ta in muc:
        ghi("sua_du_lieu", nguoi_dung_id=current_user.id, ten_nguoi_dung=current_user.ten_dang_nhap, hanh_dong=hanh_dong,
            doi_tuong="Ý kiến hỏi đáp", doi_tuong_id=yid, doi_tuong_ten=ten_dt, mo_ta=mo_ta)     # ghi() tự nuốt lỗi


def _ap_dung(yk, hanh_dong):
    """Áp dụng 1 thao tác lên ý kiến (chưa commit). Trả về bản ghi nhật ký cần ghi sau khi commit."""
    log = _nhat_ky(yk, "xoa" if hanh_dong == "xoa" else hanh_dong)
    if hanh_dong == "xoa":
        TB.dong_bo_da_doc_theo_khoa(f"yk:{yk.id}")
        db.session.delete(yk)
        return log
    moi = HANH_DONG[hanh_dong]
    yk.trang_thai = moi
    if moi == "da_duyet":
        yk.nguoi_duyet_id, yk.ngay_duyet = current_user.id, datetime.utcnow()
    if moi != "cho_duyet":
        TB.dong_bo_da_doc_theo_khoa(f"yk:{yk.id}")           # đã xử lý → thông báo của mọi admin thành đã đọc
    return log


@bp.before_request
@login_required
def _yeu_cau_dang_nhap():
    return None


@bp.get("/")
def danh_sach():
    trang_thai = request.args.get("trang_thai", "cho_duyet")
    loai = request.args.get("loai", "")
    q = request.args.get("q", "").strip()[:80]
    try:
        trang = max(1, int(request.args.get("trang", 1)))
    except ValueError:
        trang = 1

    truy_van = YKien.query
    if trang_thai in PH.TRANG_THAI:
        truy_van = truy_van.filter(YKien.trang_thai == trang_thai)
    else:
        trang_thai = "tat_ca"
    if loai in PH.DOI_TUONG:
        truy_van = truy_van.filter(YKien.doi_tuong_loai == loai)
    if q:
        like = f"%{q}%"
        truy_van = truy_van.filter(db.or_(YKien.ten.ilike(like), YKien.so_dien_thoai.ilike(like),
                                          YKien.noi_dung.ilike(like), YKien.doi_tuong_ten.ilike(like)))
    tong = truy_van.count()
    muc = truy_van.order_by(YKien.ngay_tao.desc(), YKien.id.desc()).offset((trang - 1) * MOI_TRANG).limit(MOI_TRANG).all()
    dem = dict(db.session.query(YKien.trang_thai, func.count(YKien.id)).group_by(YKien.trang_thai).all())
    lien_ket = {}                                           # đường dẫn tới trang công khai của thuốc / bài viết bị góp ý
    for y in muc:
        obj = PH.lay_doi_tuong(y.doi_tuong_loai, y.doi_tuong_id)
        if obj is not None:
            lien_ket[y.id] = PH.url_doi_tuong(y.doi_tuong_loai, obj)
    return render_template("admin/y_kien.html", muc=muc, tong=tong, trang=trang, moi_trang=MOI_TRANG, lien_ket=lien_ket,
                           trang_thai=trang_thai, loai=loai, q=q, dem=dem, nhan_trang_thai=PH.TRANG_THAI,
                           nhan_loai={k: v[2] for k, v in PH.DOI_TUONG.items()})


@bp.post("/<int:yk_id>/<hanh_dong>")
def thao_tac(yk_id, hanh_dong):
    if hanh_dong not in HANH_DONG and hanh_dong != "xoa":
        abort(404)
    yk = db.session.get(YKien, yk_id) or abort(404)
    log = _ap_dung(yk, hanh_dong)
    db.session.commit()
    _ghi_sau([log])
    flash({"duyet": "Đã duyệt, ý kiến đã hiện ra trang công khai.", "tu_choi": "Đã từ chối ý kiến.", "spam": "Đã đánh dấu spam.",
           "cho_duyet": "Đã chuyển lại về chờ duyệt.", "xoa": "Đã xoá ý kiến."}[hanh_dong], "success")
    return redirect(request.form.get("quay_lai") or url_for("admin_y_kien.danh_sach"))


@bp.post("/<int:yk_id>/tra-loi")
def tra_loi(yk_id):
    """Trả lời CÔNG KHAI dưới ý kiến. Trả lời cũng là duyệt: ý kiến và câu trả lời cùng hiện ra trang công khai."""
    yk = db.session.get(YKien, yk_id) or abort(404)
    nd, loi = PH.kiem_tra_noi_dung(request.form.get("tra_loi"), PH.TOI_DA_TIN_NHAN, cho_phep_link=True)
    if loi:
        flash(loi, "error")
        return redirect(request.form.get("quay_lai") or url_for("admin_y_kien.danh_sach"))
    yk.tra_loi, yk.nguoi_tra_loi_id, yk.ngay_tra_loi = nd, current_user.id, datetime.utcnow()
    logs = [_nhat_ky(yk, "tra_loi")]
    if yk.trang_thai != "da_duyet":
        logs.append(_ap_dung(yk, "duyet"))
    db.session.commit()
    _ghi_sau(logs)
    flash("Đã đăng câu trả lời.", "success")
    return redirect(request.form.get("quay_lai") or url_for("admin_y_kien.danh_sach"))


@bp.post("/hang-loat")
def hang_loat():
    hanh_dong = request.form.get("hanh_dong", "")
    if hanh_dong not in HANH_DONG and hanh_dong != "xoa":
        flash("Hãy chọn thao tác.", "error")
        return redirect(url_for("admin_y_kien.danh_sach"))
    ids = [int(x) for x in request.form.getlist("ids") if x.isdigit()][:200]
    logs = [_ap_dung(yk, hanh_dong) for yk in (YKien.query.filter(YKien.id.in_(ids)).all() if ids else [])]
    n = len(logs)
    db.session.commit()
    _ghi_sau(logs)
    flash(f"Đã xử lý {n} ý kiến.", "success")
    return redirect(request.form.get("quay_lai") or url_for("admin_y_kien.danh_sach"))
