from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import Thuoc
from app.forms import ThuocForm
from app.utils.upload_anh import upload_anh_thuoc, xoa_anh_cloudinary
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_thuoc", __name__, url_prefix="/admin/thuoc")


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("trang", 1, type=int)
    query = Thuoc.query
    if tu_khoa:
        query = query.filter(Thuoc.ten_thuoc.ilike(f"%{tu_khoa}%"))
    phan_trang = query.order_by(Thuoc.ten_thuoc).paginate(page=trang, per_page=10, error_out=False)
    return render_template("admin/thuoc/danh_sach.html",
                           danh_sach_thuoc=phan_trang.items,
                           phan_trang=phan_trang,
                           tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThuocForm()
    if form.validate_on_submit():
        thuoc = Thuoc()
        # Điền các trường text thủ công (bỏ qua file_anh)
        thuoc.ten_thuoc = form.ten_thuoc.data
        thuoc.hoat_chat = form.hoat_chat.data
        thuoc.ham_luong = form.ham_luong.data
        thuoc.dang_bao_che = form.dang_bao_che.data
        thuoc.nhom_thuoc_id = None  # ThuocForm dùng trường nhom_thuoc text riêng
        thuoc.nha_san_xuat = form.nha_san_xuat.data
        thuoc.so_dang_ky = form.so_dang_ky.data
        db.session.add(thuoc)
        db.session.flush()  # lấy thuoc.id trước khi upload

        # Xử lý upload ảnh
        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_thuoc(file_anh)
                if url:
                    thuoc.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        db.session.commit()
        flash(f'Đã thêm thuốc "{thuoc.ten_thuoc}".', "success")
        return redirect(url_for("admin_thuoc.danh_sach"))
    return render_template("admin/thuoc/form.html", form=form, tieu_de="Thêm thuốc")


@bp.route("/<int:thuoc_id>/sua", methods=["GET", "POST"])
@login_required
def sua(thuoc_id):
    thuoc = Thuoc.query.get_or_404(thuoc_id)
    form = ThuocForm(obj=thuoc)
    if form.validate_on_submit():
        thuoc.ten_thuoc = form.ten_thuoc.data
        thuoc.hoat_chat = form.hoat_chat.data
        thuoc.ham_luong = form.ham_luong.data
        thuoc.dang_bao_che = form.dang_bao_che.data
        thuoc.nha_san_xuat = form.nha_san_xuat.data
        thuoc.so_dang_ky = form.so_dang_ky.data

        # --- Xử lý ảnh: ảnh mới luôn được ưu tiên, tự xoá ảnh cũ trên
        # Cloudinary trước khi thay để tránh rác. Checkbox "xoá ảnh" chỉ
        # có tác dụng khi KHÔNG có ảnh mới đi kèm.
        file_anh = request.files.get("file_anh")
        anh_moi_url = None
        if file_anh and file_anh.filename:
            try:
                anh_moi_url = upload_anh_thuoc(file_anh)
            except ValueError as e:
                flash(str(e), "warning")

        if anh_moi_url:
            if thuoc.hinh_anh and thuoc.hinh_anh != anh_moi_url:
                xoa_anh_cloudinary(thuoc.hinh_anh)
            thuoc.hinh_anh = anh_moi_url
        elif request.form.get("xoa_anh") and thuoc.hinh_anh:
            xoa_anh_cloudinary(thuoc.hinh_anh)
            thuoc.hinh_anh = None

        db.session.commit()
        flash(f'Đã cập nhật "{thuoc.ten_thuoc}".', "success")
        return redirect(url_for("admin_thuoc.danh_sach"))
    return render_template("admin/thuoc/form.html", form=form, tieu_de="Sửa thuốc", thuoc=thuoc)


@bp.route("/<int:thuoc_id>/xoa", methods=["POST"])
@login_required
def xoa(thuoc_id):
    thuoc = Thuoc.query.get_or_404(thuoc_id)
    ten = thuoc.ten_thuoc
    # Xoá ảnh trên Cloudinary trước khi xoá record
    if thuoc.hinh_anh:
        xoa_anh_cloudinary(thuoc.hinh_anh)
    db.session.delete(thuoc)
    db.session.commit()
    flash(f'Đã xoá "{ten}" và toàn bộ dữ liệu liên quan.', "success")
    return redirect(url_for("admin_thuoc.danh_sach"))


def _xoa_anh_thuoc(thuoc):
    if thuoc.hinh_anh:
        xoa_anh_cloudinary(thuoc.hinh_anh)


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(
        Thuoc, ids,
        xoa_anh=_xoa_anh_thuoc,
        hien_thi=lambda t: t.ten_thuoc,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="thuốc")
    return redirect(url_for("admin_thuoc.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(
        Thuoc,
        xoa_anh=_xoa_anh_thuoc,
        hien_thi=lambda t: t.ten_thuoc,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="thuốc")
    return redirect(url_for("admin_thuoc.danh_sach"))
