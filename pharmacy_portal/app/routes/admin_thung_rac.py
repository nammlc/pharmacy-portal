from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from sqlalchemy import func

from app import db
from app.models.models import ThungRac
from app.utils import thung_rac as TR
from app.utils.xoa_hang_loat_crud import lay_id_tu_form

bp = Blueprint("admin_thung_rac", __name__, url_prefix="/admin/thung-rac")

MOI_TRANG = 20


@bp.before_request
@login_required
def _yeu_cau_dang_nhap():
    return None


def _quay_lai():
    """Về đúng bộ lọc / trang đang xem (chỉ nhận đường dẫn nội bộ của trang thùng rác)."""
    loai = request.form.get("loai", "")
    q = request.form.get("q", "").strip()
    tham_so = {}
    if loai in TR.REGISTRY:
        tham_so["loai"] = loai
    if q:
        tham_so["q"] = q
    return redirect(url_for("admin_thung_rac.danh_sach", **tham_so))


@bp.get("/")
def danh_sach():
    TR.don_het_han()
    loai = request.args.get("loai", "")
    tu_khoa = request.args.get("q", "").strip()[:80]
    trang = request.args.get("trang", 1, type=int)

    truy_van = TR.con_han()
    if loai in TR.REGISTRY:
        truy_van = truy_van.filter(ThungRac.loai == loai)
    else:
        loai = ""
    if tu_khoa:
        truy_van = truy_van.filter(ThungRac.ten.ilike(f"%{tu_khoa}%"))
    phan_trang = truy_van.order_by(ThungRac.ngay_xoa.desc(), ThungRac.id.desc()).paginate(
        page=trang, per_page=MOI_TRANG, error_out=False)

    dem = dict(TR.con_han().with_entities(ThungRac.loai, func.count(ThungRac.id)).group_by(ThungRac.loai).all())
    tong = sum(dem.values())
    muc = [(b, TR.REGISTRY.get(b.loai), TR.so_ngay_con_lai(b)) for b in phan_trang.items]
    return render_template("admin/thung_rac/danh_sach.html", muc=muc, phan_trang=phan_trang, loai=loai,
                           tu_khoa=tu_khoa, dem=dem, tong=tong, loai_tat_ca=TR.REGISTRY, so_ngay=TR.so_ngay_giu())


def _lay_muc(rac_id):
    return TR.con_han().filter(ThungRac.id == rac_id).first_or_404()


@bp.post("/<int:rac_id>/khoi-phuc")
def khoi_phuc(rac_id):
    ok, thong_diep, muc_do = TR.khoi_phuc(_lay_muc(rac_id))
    flash(thong_diep, muc_do)
    return _quay_lai()


@bp.post("/khoi-phuc-nhieu")
def khoi_phuc_nhieu():
    ids = lay_id_tu_form(request)
    so_ok, loi = 0, []
    for b in TR.con_han().filter(ThungRac.id.in_(ids)).order_by(ThungRac.ngay_xoa.desc(), ThungRac.id.desc()).all():
        ok, thong_diep, _ = TR.khoi_phuc(b)
        if ok:
            so_ok += 1
        else:
            loi.append(thong_diep)
    if so_ok:
        flash(f"Đã khôi phục {so_ok} mục.", "success")
    for t in loi[:5]:
        flash(t, "warning")
    if len(loi) > 5:
        flash(f"Và {len(loi) - 5} mục khác không khôi phục được.", "warning")
    if not so_ok and not loi:
        flash("Chưa chọn mục nào để khôi phục.", "warning")
    return _quay_lai()


@bp.post("/<int:rac_id>/huy-vinh-vien")
def huy_vinh_vien(rac_id):
    b = ThungRac.query.get_or_404(rac_id)
    ten = b.ten
    TR.xoa_vinh_vien(b)
    db.session.commit()
    flash(f'Đã xoá vĩnh viễn "{ten}".', "success")
    return _quay_lai()


@bp.post("/huy-nhieu")
def huy_nhieu():
    ids = lay_id_tu_form(request)
    cac_muc = ThungRac.query.filter(ThungRac.id.in_(ids)).all() if ids else []
    for b in cac_muc:
        TR.xoa_vinh_vien(b)
    db.session.commit()
    flash(f"Đã xoá vĩnh viễn {len(cac_muc)} mục." if cac_muc else "Chưa chọn mục nào để xoá.",
          "success" if cac_muc else "warning")
    return _quay_lai()


@bp.post("/don-sach")
def don_sach():
    tat_ca = ThungRac.query.all()
    for b in tat_ca:
        TR.xoa_vinh_vien(b)
    db.session.commit()
    flash(f"Đã dọn sạch thùng rác ({len(tat_ca)} mục)." if tat_ca else "Thùng rác đang trống.",
          "success" if tat_ca else "warning")
    return redirect(url_for("admin_thung_rac.danh_sach"))
