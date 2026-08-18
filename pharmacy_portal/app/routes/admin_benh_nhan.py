from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.models import ThongTinBenhNhan
from app.forms import ThongTinBenhNhanForm

bp = Blueprint("admin_ttbn", __name__, url_prefix="/admin/thong-tin-benh-nhan")


@bp.route("/")
@login_required
def danh_sach():
    items = ThongTinBenhNhan.query.order_by(ThongTinBenhNhan.ngay_dang.desc()).all()
    return render_template("admin/benh_nhan/danh_sach.html", items=items)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThongTinBenhNhanForm()
    if form.validate_on_submit():
        item = ThongTinBenhNhan()
        form.populate_obj(item)
        db.session.add(item)
        db.session.commit()
        flash("Đã đăng bài viết.", "success")
        return redirect(url_for("admin_ttbn.danh_sach"))
    return render_template("admin/benh_nhan/form.html", form=form, tieu_de="Thêm bài viết")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = ThongTinBenhNhan.query.get_or_404(item_id)
    form = ThongTinBenhNhanForm(obj=item)
    if form.validate_on_submit():
        form.populate_obj(item)
        db.session.commit()
        flash("Đã cập nhật.", "success")
        return redirect(url_for("admin_ttbn.danh_sach"))
    return render_template("admin/benh_nhan/form.html", form=form, tieu_de="Sửa bài viết")


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = ThongTinBenhNhan.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá.", "success")
    return redirect(url_for("admin_ttbn.danh_sach"))
