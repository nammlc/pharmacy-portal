from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import NhomThuoc
from app.forms import NhomThuocForm
from app.utils.upload_anh import upload_anh_nhom_thuoc, xoa_anh_cloudinary

bp = Blueprint("admin_nhom_thuoc", __name__, url_prefix="/admin/nhom-thuoc")


@bp.route("/")
@login_required
def danh_sach():
    danh_sach_nhom = NhomThuoc.query.order_by(NhomThuoc.loai, NhomThuoc.thu_tu, NhomThuoc.ten_nhom).all()
    return render_template("admin/nhom_thuoc/danh_sach.html", danh_sach_nhom=danh_sach_nhom)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = NhomThuocForm()
    if form.validate_on_submit():
        nhom = NhomThuoc(
            ten_nhom=form.ten_nhom.data,
            loai=form.loai.data,
            thu_tu=_so_nguyen(form.thu_tu.data),
        )
        db.session.add(nhom)
        db.session.flush()  # lấy nhom.id

        # Xử lý upload ảnh
        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_nhom_thuoc(file_anh, public_id=f"nhom_{nhom.id}")
                if url:
                    nhom.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        db.session.commit()
        flash(f'Đã thêm nhóm thuốc "{nhom.ten_nhom}".', "success")
        return redirect(url_for("admin_nhom_thuoc.danh_sach"))
    return render_template("admin/nhom_thuoc/form.html", form=form, tieu_de="Thêm nhóm thuốc")


@bp.route("/<int:nhom_id>/sua", methods=["GET", "POST"])
@login_required
def sua(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    form = NhomThuocForm(obj=nhom)
    if request.method == "GET":
        form.thu_tu.data = str(nhom.thu_tu or 0)
    if form.validate_on_submit():
        nhom.ten_nhom = form.ten_nhom.data
        nhom.loai = form.loai.data
        nhom.thu_tu = _so_nguyen(form.thu_tu.data)

        # Xử lý upload ảnh mới
        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_nhom_thuoc(file_anh, public_id=f"nhom_{nhom.id}")
                if url:
                    nhom.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        # Xoá ảnh nếu người dùng tích vào checkbox "xoá ảnh"
        if request.form.get("xoa_anh") and nhom.hinh_anh:
            xoa_anh_cloudinary(nhom.hinh_anh)
            nhom.hinh_anh = None

        db.session.commit()
        flash(f'Đã cập nhật "{nhom.ten_nhom}".', "success")
        return redirect(url_for("admin_nhom_thuoc.danh_sach"))
    return render_template("admin/nhom_thuoc/form.html", form=form, tieu_de="Sửa nhóm thuốc", nhom=nhom)


@bp.route("/<int:nhom_id>/xoa", methods=["POST"])
@login_required
def xoa(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    if nhom.danh_muc_thuoc_list or nhom.nha_thuoc_bv_list:
        flash(f'Không thể xoá "{nhom.ten_nhom}" vì vẫn còn thuốc thuộc nhóm này.', "danger")
        return redirect(url_for("admin_nhom_thuoc.danh_sach"))
    ten = nhom.ten_nhom
    # Xoá ảnh Cloudinary trước
    if nhom.hinh_anh:
        xoa_anh_cloudinary(nhom.hinh_anh)
    db.session.delete(nhom)
    db.session.commit()
    flash(f'Đã xoá nhóm thuốc "{ten}".', "success")
    return redirect(url_for("admin_nhom_thuoc.danh_sach"))


def _so_nguyen(gia_tri):
    try:
        return int(gia_tri)
    except (TypeError, ValueError):
        return 0
