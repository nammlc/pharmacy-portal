from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.models import BaiViet, DanhMucBaiViet
from app.forms import BaiVietForm, _tuy_chon_rong
from app.utils.lam_sach_html import lam_sach_html
from app.utils.slug import tao_slug_duy_nhat
from app.utils.upload_anh import (
    upload_anh_bai_viet, xoa_anh_cloudinary,
    upload_tep_dinh_kem_bai_viet, xoa_tep_dinh_kem_cloudinary,
)
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_bv", __name__, url_prefix="/admin/bai-viet")


def _nap_lua_chon(form):
    form.danh_muc_id.choices = [_tuy_chon_rong()] + [
        (d.id, d.ten) for d in DanhMucBaiViet.query.order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten).all()
    ]


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("trang", 1, type=int)
    query = BaiViet.query
    if tu_khoa:
        query = query.filter(BaiViet.tieu_de.ilike(f"%{tu_khoa}%"))
    phan_trang = (query
                  .order_by(BaiViet.ghim.desc(), BaiViet.ngay_tao.desc())
                  .paginate(page=trang, per_page=8, error_out=False))
    return render_template("admin/bai_viet/danh_sach.html",
                           items=phan_trang.items, phan_trang=phan_trang, tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = BaiVietForm()
    _nap_lua_chon(form)
    if request.method == "GET":
        form.trang_thai.data = "nhap"
    if form.validate_on_submit():
        bai_viet = BaiViet()
        form.populate_obj(bai_viet)
        bai_viet.danh_muc_id = form.danh_muc_id.data or None
        bai_viet.noi_dung = lam_sach_html(bai_viet.noi_dung)
        bai_viet.nguoi_dung_id = current_user.id
        bai_viet.slug = tao_slug_duy_nhat(BaiViet, form.tieu_de.data)
        if bai_viet.trang_thai == "da_xuat_ban":
            bai_viet.ngay_xuat_ban = datetime.utcnow()
        db.session.add(bai_viet)
        db.session.flush()  # lấy bai_viet.id trước khi commit

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_bai_viet(file_anh)
                if url:
                    bai_viet.anh_dai_dien = url
            except ValueError as e:
                flash(str(e), "warning")

        tep = request.files.get("file_dinh_kem")
        if tep and tep.filename:
            try:
                url_tep, ten_goc = upload_tep_dinh_kem_bai_viet(tep)
                if url_tep:
                    bai_viet.file_dinh_kem = url_tep
                    bai_viet.ten_file = ten_goc
            except ValueError as e:
                flash(str(e), "warning")

        db.session.commit()
        flash(f'Đã đăng bài viết "{bai_viet.tieu_de}".', "success")
        return redirect(url_for("admin_bv.danh_sach"))
    return render_template("admin/bai_viet/form.html", form=form, tieu_de="Thêm bài viết")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    bai_viet = BaiViet.query.get_or_404(item_id)
    form = BaiVietForm(obj=bai_viet)
    _nap_lua_chon(form)
    if request.method == "GET":
        form.danh_muc_id.data = bai_viet.danh_muc_id or 0
    if form.validate_on_submit():
        trang_thai_cu = bai_viet.trang_thai
        form.populate_obj(bai_viet)
        bai_viet.danh_muc_id = form.danh_muc_id.data or None
        bai_viet.noi_dung = lam_sach_html(bai_viet.noi_dung)

        # Giữ nguyên slug đã có (không đổi URL khi sửa tiêu đề) — chỉ sinh mới nếu chưa có
        if not bai_viet.slug:
            bai_viet.slug = tao_slug_duy_nhat(BaiViet, bai_viet.tieu_de, item_id=bai_viet.id)

        if bai_viet.trang_thai == "da_xuat_ban" and trang_thai_cu != "da_xuat_ban":
            bai_viet.ngay_xuat_ban = datetime.utcnow()

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url_moi = upload_anh_bai_viet(file_anh, url_cu=bai_viet.anh_dai_dien)
                if url_moi:
                    bai_viet.anh_dai_dien = url_moi
            except ValueError as e:
                flash(str(e), "warning")
        elif request.form.get("xoa_anh") and bai_viet.anh_dai_dien:
            xoa_anh_cloudinary(bai_viet.anh_dai_dien)
            bai_viet.anh_dai_dien = None

        tep = request.files.get("file_dinh_kem")
        if tep and tep.filename:
            try:
                url_tep, ten_goc = upload_tep_dinh_kem_bai_viet(tep, url_cu=bai_viet.file_dinh_kem)
                if url_tep:
                    bai_viet.file_dinh_kem = url_tep
                    bai_viet.ten_file = ten_goc
            except ValueError as e:
                flash(str(e), "warning")
        elif request.form.get("xoa_tep") and bai_viet.file_dinh_kem:
            xoa_tep_dinh_kem_cloudinary(bai_viet.file_dinh_kem)
            bai_viet.file_dinh_kem = None
            bai_viet.ten_file = None

        db.session.commit()
        flash(f'Đã cập nhật "{bai_viet.tieu_de}".', "success")
        return redirect(url_for("admin_bv.danh_sach"))
    return render_template("admin/bai_viet/form.html", form=form, tieu_de="Sửa bài viết", bai_viet=bai_viet)


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    bai_viet = BaiViet.query.get_or_404(item_id)
    ten = bai_viet.tieu_de
    _xoa_tai_nguyen_bai_viet(bai_viet)
    db.session.delete(bai_viet)
    db.session.commit()
    flash(f'Đã xoá bài viết "{ten}".', "success")
    return redirect(url_for("admin_bv.danh_sach"))


def _xoa_tai_nguyen_bai_viet(bai_viet):
    if bai_viet.anh_dai_dien:
        xoa_anh_cloudinary(bai_viet.anh_dai_dien)
    if bai_viet.file_dinh_kem:
        xoa_tep_dinh_kem_cloudinary(bai_viet.file_dinh_kem)


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(
        BaiViet, ids,
        xoa_anh=_xoa_tai_nguyen_bai_viet,
        hien_thi=lambda b: b.tieu_de,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="bài viết")
    return redirect(url_for("admin_bv.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(
        BaiViet,
        xoa_anh=_xoa_tai_nguyen_bai_viet,
        hien_thi=lambda b: b.tieu_de,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="bài viết")
    return redirect(url_for("admin_bv.danh_sach"))
