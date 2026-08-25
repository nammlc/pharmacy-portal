from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.models import TuongTacThuoc, Thuoc
from app.forms import TuongTacThuocForm
from app.utils.lam_sach_html import lam_sach_html

bp = Blueprint("admin_ttt", __name__, url_prefix="/admin/tuong-tac-thuoc")


def _gan_lua_chon_thuoc(form):
    lua_chon = [(t.id, t.ten_thuoc) for t in Thuoc.query.order_by(Thuoc.ten_thuoc).all()]
    form.thuoc_a_id.choices = lua_chon
    form.thuoc_b_id.choices = lua_chon


@bp.route("/")
@login_required
def danh_sach():
    from flask import request as req
    trang = req.args.get("trang", 1, type=int)
    phan_trang = TuongTacThuoc.query.paginate(page=trang, per_page=10, error_out=False)
    return render_template("admin/tuong_tac/danh_sach.html",
                           items=phan_trang.items, phan_trang=phan_trang)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = TuongTacThuocForm()
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        item = TuongTacThuoc()
        form.populate_obj(item)
        item.co_che = lam_sach_html(item.co_che)
        item.hau_qua_lam_sang = lam_sach_html(item.hau_qua_lam_sang)
        item.xu_tri = lam_sach_html(item.xu_tri)
        db.session.add(item)
        db.session.commit()
        flash("Đã thêm tương tác thuốc.", "success")
        return redirect(url_for("admin_ttt.danh_sach"))
    return render_template("admin/tuong_tac/form.html", form=form, tieu_de="Thêm tương tác thuốc")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = TuongTacThuoc.query.get_or_404(item_id)
    form = TuongTacThuocForm(obj=item)
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        form.populate_obj(item)
        item.co_che = lam_sach_html(item.co_che)
        item.hau_qua_lam_sang = lam_sach_html(item.hau_qua_lam_sang)
        item.xu_tri = lam_sach_html(item.xu_tri)
        db.session.commit()
        flash("Đã cập nhật.", "success")
        return redirect(url_for("admin_ttt.danh_sach"))
    return render_template("admin/tuong_tac/form.html", form=form, tieu_de="Sửa tương tác thuốc")


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = TuongTacThuoc.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá.", "success")
    return redirect(url_for("admin_ttt.danh_sach"))
