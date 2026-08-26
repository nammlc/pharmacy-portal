from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import ThuocTiemTruyen, Thuoc
from app.forms import ThuocTiemTruyenForm
from app.utils.lam_sach_html import lam_sach_html

bp = Blueprint("admin_tttt", __name__, url_prefix="/admin/thuoc-tiem-truyen")


def _gan_lua_chon_thuoc(form):
    form.thuoc_id.choices = [(t.id, t.ten_thuoc) for t in Thuoc.query.order_by(Thuoc.ten_thuoc).all()]


@bp.route("/")
@login_required
def danh_sach():
    from flask import request as req
    trang = req.args.get("trang", 1, type=int)
    phan_trang = (ThuocTiemTruyen.query.join(Thuoc)
                  .order_by(Thuoc.ten_thuoc)
                  .paginate(page=trang, per_page=10, error_out=False))
    return render_template("admin/tiem_truyen/danh_sach.html",
                           items=phan_trang.items, phan_trang=phan_trang)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThuocTiemTruyenForm()
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        item = ThuocTiemTruyen()
        form.populate_obj(item)
        item.canh_bao = lam_sach_html(item.canh_bao)
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
        item.canh_bao = lam_sach_html(item.canh_bao)
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


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = request.form.getlist("ids", type=int)
    if not ids:
        flash("Chưa chọn bản ghi nào để xoá.", "warning")
        return redirect(url_for("admin_tttt.danh_sach"))
    items = ThuocTiemTruyen.query.filter(ThuocTiemTruyen.id.in_(ids)).all()
    so_luong = len(items)
    for item in items:
        db.session.delete(item)
    db.session.commit()
    flash(f"Đã xoá {so_luong} bản ghi.", "success")
    return redirect(url_for("admin_tttt.danh_sach"))
