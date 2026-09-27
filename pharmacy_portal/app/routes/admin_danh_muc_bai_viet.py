from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import DanhMucBaiViet
from app.forms import DanhMucBaiVietForm
from app.utils.slug import tao_slug_duy_nhat
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_dmbv", __name__, url_prefix="/admin/danh-muc-bai-viet")


def _so_nguyen(gia_tri):
    try:
        return int(gia_tri)
    except (TypeError, ValueError):
        return 0


@bp.route("/")
@login_required
def danh_sach():
    trang = request.args.get("trang", 1, type=int)
    phan_trang = (DanhMucBaiViet.query
                  .order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten)
                  .paginate(page=trang, per_page=10, error_out=False))
    return render_template("admin/danh_muc_bai_viet/danh_sach.html",
                           danh_sach_dm=phan_trang.items, phan_trang=phan_trang)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = DanhMucBaiVietForm()
    if form.validate_on_submit():
        dm = DanhMucBaiViet(
            ten=form.ten.data.strip(),
            mo_ta=form.mo_ta.data,
            mau_sac=form.mau_sac.data or "#1a4d8f",
            thu_tu=_so_nguyen(form.thu_tu.data),
        )
        dm.slug = tao_slug_duy_nhat(DanhMucBaiViet, dm.ten)
        db.session.add(dm)
        db.session.commit()
        flash(f'Đã thêm danh mục "{dm.ten}".', "success")
        return redirect(url_for("admin_dmbv.danh_sach"))
    return render_template("admin/danh_muc_bai_viet/form.html", form=form, tieu_de="Thêm danh mục bài viết")


@bp.route("/<int:dm_id>/sua", methods=["GET", "POST"])
@login_required
def sua(dm_id):
    dm = DanhMucBaiViet.query.get_or_404(dm_id)
    form = DanhMucBaiVietForm(obj=dm)
    if request.method == "GET":
        form.thu_tu.data = str(dm.thu_tu or 0)
    if form.validate_on_submit():
        dm.ten = form.ten.data.strip()
        dm.mo_ta = form.mo_ta.data
        dm.mau_sac = form.mau_sac.data or "#1a4d8f"
        dm.thu_tu = _so_nguyen(form.thu_tu.data)
        if not dm.slug:
            dm.slug = tao_slug_duy_nhat(DanhMucBaiViet, dm.ten, item_id=dm.id)
        db.session.commit()
        flash(f'Đã cập nhật "{dm.ten}".', "success")
        return redirect(url_for("admin_dmbv.danh_sach"))
    return render_template("admin/danh_muc_bai_viet/form.html", form=form, tieu_de="Sửa danh mục bài viết", dm=dm)


@bp.route("/<int:dm_id>/xoa", methods=["POST"])
@login_required
def xoa(dm_id):
    dm = DanhMucBaiViet.query.get_or_404(dm_id)
    ten = dm.ten
    db.session.delete(dm)
    db.session.commit()
    flash(f'Đã xoá danh mục "{ten}". Các bài viết thuộc danh mục này chuyển về "chưa phân loại".', "success")
    return redirect(url_for("admin_dmbv.danh_sach"))


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(
        DanhMucBaiViet, ids,
        hien_thi=lambda d: d.ten,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="danh mục bài viết")
    return redirect(url_for("admin_dmbv.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(
        DanhMucBaiViet,
        hien_thi=lambda d: d.ten,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="danh mục bài viết")
    return redirect(url_for("admin_dmbv.danh_sach"))
