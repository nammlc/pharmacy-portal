from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import NhaThuocBV, NhomThuoc, HoatChat
from app.forms import NhaThuocBVForm, _tuy_chon_rong
from app.utils.upload_anh import upload_anh_nha_thuoc_bv, xoa_anh_cloudinary

bp = Blueprint("admin_ntbv", __name__, url_prefix="/admin/nha-thuoc-bv")


def _nap_lua_chon(form):
    form.nhom_thuoc_id.choices = [_tuy_chon_rong()] + [
        (n.id, n.ten_nhom)
        for n in NhomThuoc.query.filter_by(loai="nha_thuoc_bv").order_by(NhomThuoc.ten_nhom).all()
    ]
    form.hoat_chat_id.choices = [_tuy_chon_rong()] + [
        (h.id, h.ten_hoat_chat) for h in HoatChat.query.order_by(HoatChat.ten_hoat_chat).all()
    ]


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    query = NhaThuocBV.query
    if tu_khoa:
        query = query.filter(NhaThuocBV.ten_biet_duoc.ilike(f"%{tu_khoa}%"))
    ds = query.order_by(NhaThuocBV.ten_biet_duoc).all()
    return render_template("admin/nha_thuoc_bv/danh_sach.html", danh_sach_thuoc=ds, tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = NhaThuocBVForm()
    _nap_lua_chon(form)
    if form.validate_on_submit():
        thuoc = NhaThuocBV()
        form.populate_obj(thuoc)
        thuoc.nhom_thuoc_id = form.nhom_thuoc_id.data or None
        thuoc.hoat_chat_id = form.hoat_chat_id.data or None
        db.session.add(thuoc)
        db.session.flush()  # lấy thuoc.id trước khi upload

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_nha_thuoc_bv(file_anh, public_id=f"ntbv_{thuoc.id}")
                if url:
                    thuoc.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        db.session.commit()
        flash(f'Đã thêm thuốc "{thuoc.ten_biet_duoc}" vào Nhà thuốc BV.', "success")
        return redirect(url_for("admin_ntbv.danh_sach"))
    return render_template("admin/nha_thuoc_bv/form.html", form=form, tieu_de="Thêm thuốc — Nhà thuốc BV")


@bp.route("/<int:thuoc_id>/sua", methods=["GET", "POST"])
@login_required
def sua(thuoc_id):
    thuoc = NhaThuocBV.query.get_or_404(thuoc_id)
    form = NhaThuocBVForm(obj=thuoc)
    _nap_lua_chon(form)
    if request.method == "GET":
        form.nhom_thuoc_id.data = thuoc.nhom_thuoc_id or 0
        form.hoat_chat_id.data = thuoc.hoat_chat_id or 0
    if form.validate_on_submit():
        form.populate_obj(thuoc)
        thuoc.nhom_thuoc_id = form.nhom_thuoc_id.data or None
        thuoc.hoat_chat_id = form.hoat_chat_id.data or None

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_nha_thuoc_bv(file_anh, public_id=f"ntbv_{thuoc.id}")
                if url:
                    thuoc.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        if request.form.get("xoa_anh") and thuoc.hinh_anh:
            xoa_anh_cloudinary(thuoc.hinh_anh)
            thuoc.hinh_anh = None

        db.session.commit()
        flash(f'Đã cập nhật "{thuoc.ten_biet_duoc}".', "success")
        return redirect(url_for("admin_ntbv.danh_sach"))
    return render_template("admin/nha_thuoc_bv/form.html", form=form, tieu_de="Sửa thuốc — Nhà thuốc BV", thuoc=thuoc)


@bp.route("/<int:thuoc_id>/xoa", methods=["POST"])
@login_required
def xoa(thuoc_id):
    thuoc = NhaThuocBV.query.get_or_404(thuoc_id)
    ten = thuoc.ten_biet_duoc
    if thuoc.hinh_anh:
        xoa_anh_cloudinary(thuoc.hinh_anh)
    db.session.delete(thuoc)
    db.session.commit()
    flash(f'Đã xoá "{ten}" khỏi Nhà thuốc BV.', "success")
    return redirect(url_for("admin_ntbv.danh_sach"))
