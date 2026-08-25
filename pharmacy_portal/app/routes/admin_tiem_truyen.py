from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.models import ThuocTiemTruyen, Thuoc
from app.forms import ThuocTiemTruyenForm

bp = Blueprint("admin_tttt", __name__, url_prefix="/admin/thuoc-tiem-truyen")


def _gan_lua_chon_thuoc(form):
    form.thuoc_id.choices = [(t.id, t.ten_thuoc) for t in Thuoc.query.order_by(Thuoc.ten_thuoc).all()]


@bp.route("/")
@login_required
def danh_sach():
    items = ThuocTiemTruyen.query.join(Thuoc).order_by(Thuoc.ten_thuoc).all()
    return render_template("admin/tiem_truyen/danh_sach.html", items=items)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThuocTiemTruyenForm()
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        item = ThuocTiemTruyen()
        form.populate_obj(item)
        db.session.add(item)
        db.session.commit()
        flash("Đã thêm thông tin tiêm truyền.", "success")
        return redirect(url_for("admin_tttt.danh_sach"))
    return render_template("admin/tiem_truyen/form.html", form=form, tieu_de="Thêm thông tin tiêm truyền")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = ThuocTiemTruyen.query.get_or_404(item_id)
    form = ThuocTiemTruyenForm(obj=item)
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        form.populate_obj(item)
        db.session.commit()
        flash("Đã cập nhật.", "success")
        return redirect(url_for("admin_tttt.danh_sach"))
    return render_template("admin/tiem_truyen/form.html", form=form, tieu_de="Sửa thông tin tiêm truyền")


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = ThuocTiemTruyen.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá.", "success")
    return redirect(url_for("admin_tttt.danh_sach"))
