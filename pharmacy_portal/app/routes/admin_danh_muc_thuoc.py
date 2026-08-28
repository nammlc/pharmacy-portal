from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import DanhMucThuoc, NhomThuoc, HoatChat
from app.forms import DanhMucThuocForm, _tuy_chon_rong
from app.utils.lam_sach_html import lam_sach_html
from app.utils.upload_anh import upload_anh_danh_muc_thuoc, xoa_anh_cloudinary
from app.utils.xoa_hang_loat_crud import lay_id_tu_form, xoa_theo_danh_sach_id, xoa_toan_bo, flash_ket_qua_xoa

bp = Blueprint("admin_dmt", __name__, url_prefix="/admin/danh-muc-thuoc")


def _nap_lua_chon(form):
    form.nhom_thuoc_id.choices = [_tuy_chon_rong()] + [
        (n.id, n.ten_nhom)
        for n in NhomThuoc.query.filter_by(loai="danh_muc_thuoc").order_by(NhomThuoc.ten_nhom).all()
    ]
    form.hoat_chat_ids.choices = [
        (h.id, h.ten_hoat_chat) for h in HoatChat.query.order_by(HoatChat.ten_hoat_chat).all()
    ]


@bp.route("/")
@login_required
def danh_sach():
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("trang", 1, type=int)
    query = DanhMucThuoc.query
    if tu_khoa:
        query = query.filter(DanhMucThuoc.ten_biet_duoc.ilike(f"%{tu_khoa}%"))
    phan_trang = query.order_by(DanhMucThuoc.ten_biet_duoc).paginate(page=trang, per_page=10, error_out=False)
    return render_template("admin/danh_muc_thuoc/danh_sach.html",
                           danh_sach_thuoc=phan_trang.items,
                           phan_trang=phan_trang,
                           tu_khoa=tu_khoa)


@bp.route("/them", methods=["GET", "POST"])
@login_required
def them():
    form = DanhMucThuocForm()
    _nap_lua_chon(form)
    if form.validate_on_submit():
        thuoc = DanhMucThuoc()
        form.populate_obj(thuoc)
        thuoc.thanh_phan = lam_sach_html(thuoc.thanh_phan)
        thuoc.chi_dinh = lam_sach_html(thuoc.chi_dinh)
        thuoc.chong_chi_dinh = lam_sach_html(thuoc.chong_chi_dinh)
        thuoc.cach_dung_lieu_dung = lam_sach_html(thuoc.cach_dung_lieu_dung)
        thuoc.nhom_thuoc_id = form.nhom_thuoc_id.data or None
        thuoc.hoat_chat_list = HoatChat.query.filter(HoatChat.id.in_(form.hoat_chat_ids.data or [])).all()
        db.session.add(thuoc)
        db.session.flush()

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            try:
                url = upload_anh_danh_muc_thuoc(file_anh)
                if url:
                    thuoc.hinh_anh = url
            except ValueError as e:
                flash(str(e), "warning")

        db.session.commit()
        flash(f'Đã thêm thuốc "{thuoc.ten_biet_duoc}" vào Danh mục thuốc.', "success")
        return redirect(url_for("admin_dmt.danh_sach"))
    return render_template("admin/danh_muc_thuoc/form.html", form=form, tieu_de="Thêm thuốc — Danh mục thuốc")


@bp.route("/<int:thuoc_id>/sua", methods=["GET", "POST"])
@login_required
def sua(thuoc_id):
    thuoc = DanhMucThuoc.query.get_or_404(thuoc_id)
    form = DanhMucThuocForm(obj=thuoc)
    _nap_lua_chon(form)
    if request.method == "GET":
        form.nhom_thuoc_id.data = thuoc.nhom_thuoc_id or 0
        form.hoat_chat_ids.data = [hc.id for hc in thuoc.hoat_chat_list]
    if form.validate_on_submit():
        form.populate_obj(thuoc)
        thuoc.thanh_phan = lam_sach_html(thuoc.thanh_phan)
        thuoc.chi_dinh = lam_sach_html(thuoc.chi_dinh)
        thuoc.chong_chi_dinh = lam_sach_html(thuoc.chong_chi_dinh)
        thuoc.cach_dung_lieu_dung = lam_sach_html(thuoc.cach_dung_lieu_dung)
        thuoc.nhom_thuoc_id = form.nhom_thuoc_id.data or None
        thuoc.hoat_chat_list = HoatChat.query.filter(HoatChat.id.in_(form.hoat_chat_ids.data or [])).all()

        file_anh = request.files.get("file_anh")
        if file_anh and file_anh.filename:
            # upload_anh_danh_muc_thuoc tự xoá url_cu trước khi upload mới
            try:
                url_moi = upload_anh_danh_muc_thuoc(file_anh, url_cu=thuoc.hinh_anh)
                if url_moi:
                    thuoc.hinh_anh = url_moi
            except ValueError as e:
                flash(str(e), "warning")
        elif request.form.get("xoa_anh") and thuoc.hinh_anh:
            xoa_anh_cloudinary(thuoc.hinh_anh)
            thuoc.hinh_anh = None

        db.session.commit()
        flash(f'Đã cập nhật "{thuoc.ten_biet_duoc}".', "success")
        return redirect(url_for("admin_dmt.danh_sach"))
    return render_template("admin/danh_muc_thuoc/form.html", form=form,
                           tieu_de="Sửa thuốc — Danh mục thuốc", thuoc=thuoc)


@bp.route("/<int:thuoc_id>/xoa", methods=["POST"])
@login_required
def xoa(thuoc_id):
    thuoc = DanhMucThuoc.query.get_or_404(thuoc_id)
    ten = thuoc.ten_biet_duoc
    if thuoc.hinh_anh:
        xoa_anh_cloudinary(thuoc.hinh_anh)
    db.session.delete(thuoc)
    db.session.commit()
    flash(f'Đã xoá "{ten}" khỏi Danh mục thuốc.', "success")
    return redirect(url_for("admin_dmt.danh_sach"))


def _xoa_anh_thuoc(thuoc):
    if thuoc.hinh_anh:
        xoa_anh_cloudinary(thuoc.hinh_anh)


@bp.route("/xoa-hang-loat", methods=["POST"])
@login_required
def xoa_hang_loat():
    ids = lay_id_tu_form(request)
    so_da_xoa, bo_qua = xoa_theo_danh_sach_id(
        DanhMucThuoc, ids,
        xoa_anh=_xoa_anh_thuoc,
        hien_thi=lambda t: t.ten_biet_duoc,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="thuốc trong Danh mục thuốc")
    return redirect(url_for("admin_dmt.danh_sach"))


@bp.route("/xoa-tat-ca", methods=["POST"])
@login_required
def xoa_tat_ca():
    so_da_xoa, bo_qua = xoa_toan_bo(
        DanhMucThuoc,
        xoa_anh=_xoa_anh_thuoc,
        hien_thi=lambda t: t.ten_biet_duoc,
    )
    flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="thuốc trong Danh mục thuốc")
    return redirect(url_for("admin_dmt.danh_sach"))
