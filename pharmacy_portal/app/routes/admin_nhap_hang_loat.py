import io
import csv

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response
from flask_login import login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SubmitField

from app.utils.nhap_hang_loat import doc_file_bang, nhap_danh_muc_thuoc, nhap_nha_thuoc_bv

bp = Blueprint("admin_nhap_hang_loat", __name__, url_prefix="/admin/nhap-hang-loat")

_DUOI_FILE_HOP_LE = ["csv", "xlsx"]


class NhapFileForm(FlaskForm):
    file_du_lieu = FileField(
        "Chọn file CSV hoặc Excel (.xlsx)",
        validators=[FileRequired(), FileAllowed(_DUOI_FILE_HOP_LE, "Chỉ nhận file .csv hoặc .xlsx.")],
    )
    submit = SubmitField("Nhập dữ liệu")


@bp.route("/", methods=["GET"])
@login_required
def trang_chinh():
    form_dmt = NhapFileForm(prefix="dmt")
    form_ntbv = NhapFileForm(prefix="ntbv")
    return render_template(
        "admin/nhap_hang_loat/trang.html",
        form_dmt=form_dmt, form_ntbv=form_ntbv,
    )


@bp.route("/danh-muc-thuoc", methods=["POST"])
@login_required
def nhap_dmt():
    form = NhapFileForm(prefix="dmt")
    if not form.validate_on_submit():
        for e in form.file_du_lieu.errors:
            flash(e, "danger")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    try:
        rows = doc_file_bang(form.file_du_lieu.data)
    except Exception as e:
        flash(f"Không đọc được file: {e}", "danger")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    if not rows:
        flash("File không có dữ liệu (hoặc thiếu dòng tiêu đề cột).", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    kq = nhap_danh_muc_thuoc(rows)
    if kq.so_thanh_cong:
        flash(f"Đã nhập/cập nhật thành công {kq.so_thanh_cong} thuốc vào Danh mục thuốc.", "success")
    if kq.so_loi:
        flash(f"{kq.so_loi} dòng bị lỗi, xem chi tiết bên dưới.", "warning")

    return render_template(
        "admin/nhap_hang_loat/ket_qua.html",
        tieu_de="Kết quả nhập Danh mục thuốc",
        ket_qua=kq,
        quay_lai_url=url_for("admin_dmt.danh_sach"),
    )


@bp.route("/nha-thuoc-bv", methods=["POST"])
@login_required
def nhap_ntbv():
    form = NhapFileForm(prefix="ntbv")
    if not form.validate_on_submit():
        for e in form.file_du_lieu.errors:
            flash(e, "danger")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    try:
        rows = doc_file_bang(form.file_du_lieu.data)
    except Exception as e:
        flash(f"Không đọc được file: {e}", "danger")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    if not rows:
        flash("File không có dữ liệu (hoặc thiếu dòng tiêu đề cột).", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    kq = nhap_nha_thuoc_bv(rows)
    if kq.so_thanh_cong:
        flash(f"Đã nhập/cập nhật thành công {kq.so_thanh_cong} thuốc vào Nhà thuốc BV.", "success")
    if kq.so_loi:
        flash(f"{kq.so_loi} dòng bị lỗi, xem chi tiết bên dưới.", "warning")

    return render_template(
        "admin/nhap_hang_loat/ket_qua.html",
        tieu_de="Kết quả nhập Nhà thuốc BV",
        ket_qua=kq,
        quay_lai_url=url_for("admin_ntbv.danh_sach"),
    )


def _tai_mau_csv(headers, ten_file, dong_mau):
    output = io.StringIO()
    output.write("\ufeff")  # BOM để Excel Việt hoá mở đúng UTF-8, không lỗi font
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerow(dong_mau)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={ten_file}"},
    )


@bp.route("/mau-danh-muc-thuoc.csv")
@login_required
def tai_mau_dmt():
    return _tai_mau_csv(
        ["ten_biet_duoc", "nhom_thuoc", "hoat_chat", "thanh_phan", "chi_dinh", "chong_chi_dinh", "cach_dung_lieu_dung", "link_chi_tiet"],
        "mau_danh_muc_thuoc.csv",
        ["Panadol Extra", "Giảm đau hạ sốt", "Paracetamol + Cafein", "Paracetamol 500mg, Cafein 65mg", "Giảm đau, hạ sốt", "Quá mẫn với thành phần thuốc", "Uống 1-2 viên/lần, cách 4-6 giờ", "https://vi-du.vn/panadol-extra"],
    )


@bp.route("/mau-nha-thuoc-bv.csv")
@login_required
def tai_mau_ntbv():
    return _tai_mau_csv(
        ["ten_biet_duoc", "nhom_thuoc", "hoat_chat", "link_tham_khao"],
        "mau_nha_thuoc_bv.csv",
        ["Panadol Extra", "Giảm đau hạ sốt", "Paracetamol + Cafein", "https://vi-du.vn/panadol-extra"],
    )
