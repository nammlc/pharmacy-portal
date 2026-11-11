"""Admin: xem và trả lời chat riêng của khách; chặn / xoá cuộc trò chuyện."""
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models.models import KhachHang, NguoiDung, TinNhanRieng
from app.utils import chat_rieng as CR
from app.utils import thong_bao as TB
from app.utils.nhat_ky import ghi
from app.utils.phan_hoi import che_sdt
from app.utils.thoi_gian import gio_vn

bp = Blueprint("admin_tin_nhan", __name__, url_prefix="/admin/tin-nhan")
MOI_TRANG = 20


def _ghi(hanh_dong, khach, mo_ta=""):
    ghi("sua_du_lieu", nguoi_dung_id=current_user.id, ten_nguoi_dung=current_user.ten_dang_nhap, hanh_dong=hanh_dong[:30],
        doi_tuong="Chat riêng", doi_tuong_id=khach.id, doi_tuong_ten=f"{khach.ten} ({che_sdt(khach.so_dien_thoai)})", mo_ta=mo_ta[:480])


@bp.before_request
@login_required
def _yeu_cau_dang_nhap():
    return None


def _ten_admin(admin_id, cache={}):
    if admin_id not in cache:
        a = db.session.get(NguoiDung, admin_id) if admin_id else None
        cache[admin_id] = (a.ho_ten or a.ten_dang_nhap) if a else "Khoa Dược"
    return cache[admin_id]


@bp.get("/")
def danh_sach():
    q = request.args.get("q", "").strip()[:60]
    chi_cho_tra_loi = request.args.get("cho_tra_loi") == "1"
    try:
        trang = max(1, int(request.args.get("trang", 1)))
    except ValueError:
        trang = 1

    # tin cuối của mỗi khách, để biết ai đang CHỜ Khoa Dược trả lời
    cuoi = (db.session.query(TinNhanRieng.khach_id, func.max(TinNhanRieng.id).label("mid")).group_by(TinNhanRieng.khach_id).subquery())
    tn_cuoi = db.aliased(TinNhanRieng)
    truy_van = (db.session.query(KhachHang, tn_cuoi).outerjoin(cuoi, cuoi.c.khach_id == KhachHang.id)
                .outerjoin(tn_cuoi, tn_cuoi.id == cuoi.c.mid))
    if q:
        like = f"%{q}%"
        truy_van = truy_van.filter(db.or_(KhachHang.ten.ilike(like), KhachHang.so_dien_thoai.ilike(like)))
    if chi_cho_tra_loi:
        truy_van = truy_van.filter(tn_cuoi.tu == "khach")
    tong = truy_van.count()
    dong = (truy_van.order_by(tn_cuoi.ngay_tao.desc().nullslast(), KhachHang.id.desc()) if db.engine.dialect.name == "postgresql"
            else truy_van.order_by(KhachHang.lan_cuoi.desc(), KhachHang.id.desc()))
    dong = dong.offset((trang - 1) * MOI_TRANG).limit(MOI_TRANG).all()
    ids = [k.id for k, _ in dong]
    chua_doc = dict(db.session.query(TinNhanRieng.khach_id, func.count(TinNhanRieng.id))
                    .filter(TinNhanRieng.khach_id.in_(ids), TinNhanRieng.tu == "khach", TinNhanRieng.da_doc_admin.is_(False))
                    .group_by(TinNhanRieng.khach_id).all()) if ids else {}
    return render_template("admin/tin_nhan_ds.html", dong=dong, chua_doc=chua_doc, tong=tong, trang=trang, moi_trang=MOI_TRANG,
                           q=q, chi_cho_tra_loi=chi_cho_tra_loi, che_sdt=che_sdt)


def _khach_hoac_404(khach_id):
    return db.session.get(KhachHang, khach_id) or abort(404)


def _dict_tin(tin):
    return [CR.tin_thanh_dict(t, gio_vn, _ten_admin(t.admin_id) if t.tu == "admin" else None) for t in tin]


@bp.get("/<int:khach_id>")
def xem(khach_id):
    khach = _khach_hoac_404(khach_id)
    TinNhanRieng.query.filter_by(khach_id=khach.id, tu="khach", da_doc_admin=False).update({"da_doc_admin": True})
    from app.models.models import ThongBao
    ThongBao.query.filter_by(nguoi_nhan_id=current_user.id, khoa_gop=f"chat:{khach.id}", da_doc=False).update({"da_doc": True})
    db.session.commit()
    tin = CR.danh_sach_tin(khach)
    return render_template("admin/tin_nhan_chat.html", khach=khach, tin_nhan=_dict_tin(tin), loai_tin=CR.LOAI_TIN, che_sdt=che_sdt)


@bp.get("/<int:khach_id>/tin-nhan")
def tin_moi(khach_id):
    """Tin mới sau id `sau` (trang đang mở hỏi định kỳ) — đồng thời đánh dấu đã đọc."""
    khach = _khach_hoac_404(khach_id)
    try:
        sau = int(request.args.get("sau", 0))
    except ValueError:
        sau = 0
    tin = CR.danh_sach_tin(khach, sau)
    if any(t.tu == "khach" for t in tin):
        TinNhanRieng.query.filter_by(khach_id=khach.id, tu="khach", da_doc_admin=False).update({"da_doc_admin": True})
        db.session.commit()
    r = jsonify({"ok": True, "tin": _dict_tin(tin)})
    r.headers["Cache-Control"] = "no-store"
    return r


@bp.post("/<int:khach_id>/gui")
def gui(khach_id):
    khach = _khach_hoac_404(khach_id)
    d = request.get_json(silent=True) or request.form
    tn, loi = CR.admin_tra_loi(khach, current_user, d.get("noi_dung"))
    if loi:
        return jsonify({"ok": False, "loi": loi}), 400
    _ghi("tra_loi", khach, tn.noi_dung[:200])
    return jsonify({"ok": True, "tin": _dict_tin([tn])})


@bp.post("/<int:khach_id>/chan")
def chan(khach_id):
    khach = _khach_hoac_404(khach_id)
    khach.bi_chan = request.form.get("bo_chan") != "1"
    khach.phien_ver = (khach.phien_ver or 1) + 1
    db.session.commit()
    _ghi("chan" if khach.bi_chan else "bo_chan", khach)
    flash("Đã chặn khách này." if khach.bi_chan else "Đã bỏ chặn.", "success")
    return redirect(url_for("admin_tin_nhan.xem", khach_id=khach.id))


@bp.post("/<int:khach_id>/xoa")
def xoa(khach_id):
    khach = _khach_hoac_404(khach_id)
    _ghi("xoa", khach, "Xoá toàn bộ cuộc trò chuyện và tài khoản khách")
    TB.dong_bo_da_doc_theo_khoa(f"chat:{khach.id}")
    TinNhanRieng.query.filter_by(khach_id=khach.id).delete()
    db.session.delete(khach)
    db.session.commit()
    flash("Đã xoá cuộc trò chuyện.", "success")
    return redirect(url_for("admin_tin_nhan.danh_sach"))
