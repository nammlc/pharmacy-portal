from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import ThongTinThuoc, Thuoc
from app.forms import ThongTinThuocForm
from app.utils.lam_sach_html import lam_sach_html
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_ttth", __name__, url_prefix="/admin/thong-tin-thuoc")


def _gan_lua_chon_thuoc(form):
    form.thuoc_id.choices = [(t.id, t.ten_thuoc) for t in Thuoc.query.order_by(Thuoc.ten_thuoc).all()]


@bp.route("/")
@login_required
def danh_sach():
    from flask import request as req
    trang = req.args.get("trang", 1, type=int)
    phan_trang = (ThongTinThuoc.query.join(Thuoc)
                  .order_by(Thuoc.ten_thuoc)
                  .paginate(page=trang, per_page=10, error_out=False))
    return render_template("admin/thong_tin_thuoc/danh_sach.html",
                           items=phan_trang.items, phan_trang=phan_trang)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = ThongTinThuocForm()
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        item = ThongTinThuoc()
        form.populate_obj(item)
        item.chi_dinh = lam_sach_html(item.chi_dinh)
        item.chong_chi_dinh = lam_sach_html(item.chong_chi_dinh)
        item.lieu_dung_nguoi_lon = lam_sach_html(item.lieu_dung_nguoi_lon)
        item.lieu_dung_tre_em = lam_sach_html(item.lieu_dung_tre_em)
        item.tac_dung_phu = lam_sach_html(item.tac_dung_phu)
        item.than_trong = lam_sach_html(item.than_trong)
        item.phu_nu_co_thai_cho_con_bu = lam_sach_html(item.phu_nu_co_thai_cho_con_bu)
        db.session.add(item)
        db.session.commit()
        flash("Đã thêm thông tin thuốc chi tiết.", "success")
        return redirect(url_for("admin_ttth.danh_sach"))
    return render_template("admin/thong_tin_thuoc/form.html", form=form, tieu_de="Thêm thông tin thuốc")


@bp.route("/<int:item_id>/sua", methods=["GET", "POST"])
@login_required
def sua(item_id):
    item = ThongTinThuoc.query.get_or_404(item_id)
    form = ThongTinThuocForm(obj=item)
    _gan_lua_chon_thuoc(form)
    if form.validate_on_submit():
        form.populate_obj(item)
        item.chi_dinh = lam_sach_html(item.chi_dinh)
        item.chong_chi_dinh = lam_sach_html(item.chong_chi_dinh)
        item.lieu_dung_nguoi_lon = lam_sach_html(item.lieu_dung_nguoi_lon)
        item.lieu_dung_tre_em = lam_sach_html(item.lieu_dung_tre_em)
        item.tac_dung_phu = lam_sach_html(item.tac_dung_phu)
        item.than_trong = lam_sach_html(item.than_trong)
        item.phu_nu_co_thai_cho_con_bu = lam_sach_html(item.phu_nu_co_thai_cho_con_bu)
        db.session.commit()
        flash("Đã cập nhật.", "success")
        return redirect(url_for("admin_ttth.danh_sach"))
    return render_template("admin/thong_tin_thuoc/form.html", form=form, tieu_de="Sửa thông tin thuốc")


@bp.route("/<int:item_id>/xoa", methods=["POST"])
@login_required
def xoa(item_id):
    item = ThongTinThuoc.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Đã xoá.", "success")
    return redirect(url_for("admin_ttth.danh_sach"))


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(
        ThongTinThuoc, ids,
        hien_thi=lambda t: t.thuoc.ten_thuoc if t.thuoc else f"#{t.id}",
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="bản ghi thông tin thuốc")
    return redirect(url_for("admin_ttth.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(
        ThongTinThuoc,
        hien_thi=lambda t: t.thuoc.ten_thuoc if t.thuoc else f"#{t.id}",
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="bản ghi thông tin thuốc")
    return redirect(url_for("admin_ttth.danh_sach"))
