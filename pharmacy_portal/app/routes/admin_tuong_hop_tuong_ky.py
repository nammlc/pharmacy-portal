from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.models import TuongHopTuongKy, Thuoc
from app.forms import TuongHopTuongKyForm
from app.utils.lam_sach_html import lam_sach_html

bp = Blueprint("admin_thtk", __name__, url_prefix="/admin/tuong-hop-tuong-ky")


def _gan_lua_chon_thuoc(form):
    lua_chon = [(t.id, t.ten_thuoc) for t in Thuoc.query.order_by(Thuoc.ten_thuoc).all()]
    form.thuoc_a_id.choices = lua_chon
    form.thuoc_b_id.choices = lua_chon


@bp.route("/")
@login_required
def danh_sach():
    items = TuongHopTuongKy.query.all()
    return render_template("admin/tuong_hop_tuong_ky/danh_sach.html", items=items)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = TuongHopTuongKyForm()
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        item = TuongHopTuongKy()
        form.populate_obj(item)
        item.mo_ta = lam_sach_html(item.mo_ta)
        db.session.add(item)
        db.session.commit()
        flash("Đã thêm cặp tương hợp/tương kỵ.", "success")
        return redirect(url_for("admin_thtk.danh_sach"))
    return render_template("admin/tuong_hop_tuong_ky/form.html", form=form, tieu_de="Thêm tương hợp/tương kỵ")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = TuongHopTuongKy.query.get_or_404(item_id)
    form = TuongHopTuongKyForm(obj=item)
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        form.populate_obj(item)
        item.mo_ta = lam_sach_html(item.mo_ta)
        db.session.commit()
        flash("Đã cập nhật.", "success")
        return redirect(url_for("admin_thtk.danh_sach"))
    return render_template("admin/tuong_hop_tuong_ky/form.html", form=form, tieu_de="Sửa tương hợp/tương kỵ")


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = TuongHopTuongKy.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá.", "success")
    return redirect(url_for("admin_thtk.danh_sach"))
