"""Quản trị TƯƠNG TÁC THUỐC theo cặp HOẠT CHẤT.

Chống trùng khi thêm / sửa tay:
  - kiem_tra_cap(): JSON để form cảnh báo NGAY khi vừa chọn xong 2 hoạt chất;
  - them()/sua(): kiểm tra lại ở server (nguồn sự thật) qua app.utils.tuong_tac_hc.luu_tay();
  - cặp (A,B) và (B,A) là một; CSDL còn có UNIQUE làm chốt chặn cuối.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.orm import aliased

from app import db
from app.models.models import TuongTacHoatChat, HoatChat
from app.forms import TuongTacHoatChatForm
from app.utils.nhap_tuong_tac import NHAN_MUC_DO
from app.utils.tuong_tac_hc import luu_tay, tim_cap
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_ttt", __name__, url_prefix="/admin/tuong-tac-thuoc")

MOI_TRANG = 20


def _gan_lua_chon(form):
    form.hoat_chat_a_id.choices = [(0, "— Chọn hoạt chất —")] + [
        (h.id, h.ten_hoat_chat) for h in HoatChat.query.order_by(HoatChat.ten_hoat_chat).all()]
    form.hoat_chat_b_id.choices = list(form.hoat_chat_a_id.choices)


@bp.route("/")
@login_required
def danh_sach():
    trang = request.args.get("trang", 1, type=int)
    tu_khoa = request.args.get("q", "").strip()[:80]
    muc = request.args.get("muc", "")
    ha, hb = aliased(HoatChat), aliased(HoatChat)
    truy_van = (TuongTacHoatChat.query
                .join(ha, TuongTacHoatChat.hoat_chat_a_id == ha.id)
                .join(hb, TuongTacHoatChat.hoat_chat_b_id == hb.id))
    if tu_khoa:
        truy_van = truy_van.filter(or_(ha.ten_hoat_chat.ilike(f"%{tu_khoa}%"),
                                       hb.ten_hoat_chat.ilike(f"%{tu_khoa}%")))
    if muc in NHAN_MUC_DO:
        truy_van = truy_van.filter(TuongTacHoatChat.muc_do == muc)
    phan_trang = (truy_van.order_by(ha.ten_hoat_chat, hb.ten_hoat_chat)
                  .paginate(page=trang, per_page=MOI_TRANG, error_out=False))
    return render_template("admin/tuong_tac/danh_sach.html", items=phan_trang.items, phan_trang=phan_trang,
                           tu_khoa=tu_khoa, muc=muc, nhan_muc=NHAN_MUC_DO, moi_trang=MOI_TRANG)


@bp.route("/kiem-tra-cap")
@login_required
def kiem_tra_cap():
    """Form gọi khi người dùng chọn xong 2 hoạt chất: cặp này đã có chưa?"""
    a = request.args.get("a", 0, type=int)
    b = request.args.get("b", 0, type=int)
    bo_qua = request.args.get("bo_qua", 0, type=int) or None
    if not a or not b:
        return jsonify(trang_thai="chua_du")
    if a == b:
        return jsonify(trang_thai="giong_nhau")
    trung = tim_cap(a, b, bo_qua_id=bo_qua)
    if not trung:
        return jsonify(trang_thai="chua_co")
    return jsonify(trang_thai="da_co", id=trung.id, sua_url=url_for("admin_ttt.sua", item_id=trung.id),
                   cap=trung.ten_cap, muc_do=NHAN_MUC_DO.get(trung.muc_do, trung.muc_do))


def _xu_ly_form(form, item=None):
    """Trả về (bản_ghi_đã_lưu | None, bản_ghi_trùng | None). Dùng chung cho them() và sua()."""
    if form.hoat_chat_a_id.data == form.hoat_chat_b_id.data:
        form.hoat_chat_b_id.errors.append("Hai hoạt chất phải khác nhau.")
        return None, None
    return luu_tay(form, item)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = TuongTacHoatChatForm()
    _gan_lua_chon(form)
    trung = None
    if form.validate_on_submit():
        ket, trung = _xu_ly_form(form)
        if ket:
            flash("Đã thêm tương tác thuốc.", "success")
            return redirect(url_for("admin_ttt.danh_sach"))
    return render_template("admin/tuong_tac/form.html", form=form, tieu_de="Thêm tương tác thuốc",
                           trung=trung, item=None)


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = TuongTacHoatChat.query.get_or_404(item_id)
    form = TuongTacHoatChatForm(obj=item)
    _gan_lua_chon(form)
    trung = None
    if form.validate_on_submit():
        ket, trung = _xu_ly_form(form, item)
        if ket:
            flash("Đã cập nhật.", "success")
            return redirect(url_for("admin_ttt.danh_sach"))
    return render_template("admin/tuong_tac/form.html", form=form, tieu_de="Sửa tương tác thuốc",
                           trung=trung, item=item)


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = TuongTacHoatChat.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá. Có thể khôi phục trong Thùng rác.", "success")
    return redirect(url_for("admin_ttt.danh_sach"))


def _hien_thi_cap(item):
    return item.ten_cap


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(TuongTacHoatChat, ids, hien_thi=_hien_thi_cap)
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="cặp tương tác thuốc")
    return redirect(url_for("admin_ttt.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(TuongTacHoatChat, hien_thi=_hien_thi_cap)
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="cặp tương tác thuốc")
    return redirect(url_for("admin_ttt.danh_sach"))
