from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.models import CaiDat
from app.utils.upload_anh import upload_anh_ve_chung_toi, xoa_anh_cloudinary

bp = Blueprint("admin_vct", __name__, url_prefix="/admin/ve-chung-toi")

# Các key lưu trong bảng cai_dat
KEYS = [
    "vct_tieu_de",
    "vct_mo_ta_ngan",
    "vct_gioi_thieu",
    "vct_su_menh",
    "vct_tam_nhin",
    "vct_hinh_anh_1",
    "vct_hinh_anh_2",
    "vct_ten_lien_he",
    "vct_chuc_vu_lien_he",
    "vct_dien_thoai",
    "vct_email",
    "vct_dia_chi",
]


@bp.route("/", methods=["GET", "POST"])
@login_required
def chinh_sua():
    if request.method == "POST":
        # Lưu các trường text
        for key in KEYS:
            if key.startswith("vct_hinh_anh"):
                continue  # ảnh xử lý riêng
            gia_tri = request.form.get(key, "").strip()
            CaiDat.dat(key, gia_tri)

        # Xử lý ảnh 1
        _xu_ly_anh(request, "file_anh_1", "vct_hinh_anh_1", "xoa_anh_1")
        # Xử lý ảnh 2
        _xu_ly_anh(request, "file_anh_2", "vct_hinh_anh_2", "xoa_anh_2")

        db.session.commit()
        flash("Đã lưu thông tin trang Về chúng tôi.", "success")
        return redirect(url_for("admin_vct.chinh_sua"))

    du_lieu = {k: CaiDat.lay(k) for k in KEYS}
    return render_template("admin/ve_chung_toi/form.html", du_lieu=du_lieu)


def _xu_ly_anh(req, field_name: str, key: str, xoa_field: str):
    url_cu = CaiDat.lay(key)
    file_anh = req.files.get(field_name)
    if file_anh and file_anh.filename:
        try:
            url_moi = upload_anh_ve_chung_toi(file_anh, url_cu=url_cu)
            if url_moi:
                CaiDat.dat(key, url_moi)
        except ValueError as e:
            flash(str(e), "warning")
    elif req.form.get(xoa_field) and url_cu:
        xoa_anh_cloudinary(url_cu)
        CaiDat.dat(key, "")
