from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import Thuoc
from app.forms import ThuocForm

bp = Blueprint("admin_thuoc", __name__, url_prefix="/admin/thuoc")


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    query = Thuoc.query
    if tu_khoa:
        query = query.filter(Thuoc.ten_thuoc.ilike(f"%{tu_khoa}%"))
    danh_sach_thuoc = query.order_by(Thuoc.ten_thuoc).all()
    return render_template("admin/thuoc/danh_sach.html", danh_sach_thuoc=danh_sach_thuoc, tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThuocForm()
    if form.validate_on_submit():
        thuoc = Thuoc()
        form.populate_obj(thuoc)
        db.session.add(thuoc)
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
        form.populate_obj(thuoc)
        db.session.commit()
        flash(f'Đã cập nhật "{thuoc.ten_thuoc}".', "success")
        return redirect(url_for("admin_thuoc.danh_sach"))
    return render_template("admin/thuoc/form.html", form=form, tieu_de="Sửa thuốc")


@bp.route("/<int:thuoc_id>/xoa", methods=["POST"])
@login_required
def xoa(thuoc_id):
    thuoc = Thuoc.query.get_or_404(thuoc_id)
    ten = thuoc.ten_thuoc
    db.session.delete(thuoc)
    db.session.commit()
    flash(f'Đã xoá "{ten}" và toàn bộ dữ liệu liên quan.', "success")
    return redirect(url_for("admin_thuoc.danh_sach"))
