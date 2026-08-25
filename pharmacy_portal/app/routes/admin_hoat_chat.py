from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import HoatChat
from app.forms import HoatChatForm

bp = Blueprint("admin_hoat_chat", __name__, url_prefix="/admin/hoat-chat")


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("trang", 1, type=int)
    query = HoatChat.query
    if tu_khoa:
        query = query.filter(HoatChat.ten_hoat_chat.ilike(f"%{tu_khoa}%"))
    phan_trang = query.order_by(HoatChat.ten_hoat_chat).paginate(page=trang, per_page=10, error_out=False)
    return render_template("admin/hoat_chat/danh_sach.html",
                           danh_sach_hc=phan_trang.items,
                           phan_trang=phan_trang,
                           tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = HoatChatForm()
    if form.validate_on_submit():
        if HoatChat.query.filter_by(ten_hoat_chat=form.ten_hoat_chat.data.strip()).first():
            flash("Hoạt chất này đã tồn tại.", "danger")
        else:
            hc = HoatChat(ten_hoat_chat=form.ten_hoat_chat.data.strip())
            db.session.add(hc)
            db.session.commit()
            flash(f'Đã thêm hoạt chất "{hc.ten_hoat_chat}".', "success")
            return redirect(url_for("admin_hoat_chat.danh_sach"))
    return render_template("admin/hoat_chat/form.html", form=form, tieu_de="Thêm hoạt chất")


@bp.route("/<int:hc_id>/sua", methods=["GET", "POST"])
@login_required
def sua(hc_id):
    hc = HoatChat.query.get_or_404(hc_id)
    form = HoatChatForm(obj=hc)
    if form.validate_on_submit():
        hc.ten_hoat_chat = form.ten_hoat_chat.data.strip()
        db.session.commit()
        flash(f'Đã cập nhật "{hc.ten_hoat_chat}".', "success")
        return redirect(url_for("admin_hoat_chat.danh_sach"))
    return render_template("admin/hoat_chat/form.html", form=form, tieu_de="Sửa hoạt chất")


@bp.route("/<int:hc_id>/xoa", methods=["POST"])
@login_required
def xoa(hc_id):
    hc = HoatChat.query.get_or_404(hc_id)
    if hc.danh_muc_thuoc_co_hoat_chat.first() or hc.nha_thuoc_bv_co_hoat_chat.first():
        flash(f'Không thể xoá "{hc.ten_hoat_chat}" vì vẫn còn thuốc gắn với hoạt chất này.', "danger")
        return redirect(url_for("admin_hoat_chat.danh_sach"))
    ten = hc.ten_hoat_chat
    db.session.delete(hc)
    db.session.commit()
    flash(f'Đã xoá hoạt chất "{ten}".', "success")
    return redirect(url_for("admin_hoat_chat.danh_sach"))
