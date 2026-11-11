import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app import db
from app.models.models import CaiDat
from app.utils import hero as H
from app.utils.upload_anh import upload_anh_hero, upload_anh_hero_mobile, xoa_anh_cloudinary

bp = Blueprint("admin_hero", __name__, url_prefix="/admin/anh-trang-chu")
log = logging.getLogger(__name__)


def _xu_ly_mot_anh(ten_file, ten_xoa, khoa, ham_upload, nhan):
    """Thay hoặc xoá 1 ảnh (máy tính / điện thoại). Trả về True nếu có lỗi tải ảnh."""
    url_cu = CaiDat.lay(khoa)
    file_anh = request.files.get(ten_file)

    if file_anh and file_anh.filename:
        # Tải ảnh MỚI lên trước, thành công rồi mới xoá ảnh cũ -> lỡ lỗi mạng thì trang chủ vẫn còn ảnh cũ.
        try:
            url_moi = ham_upload(file_anh, url_cu=None)
        except ValueError as e:
            flash(f"Ảnh {nhan}: {e}", "warning")
            return True
        except Exception:
            log.exception("Upload ảnh hero (%s) lỗi", nhan)
            flash(f"Không tải được ảnh {nhan} lên Cloudinary. Kiểm tra lại kết nối/khoá Cloudinary rồi thử lại.", "danger")
            return True
        if url_moi:
            if url_cu:
                xoa_anh_cloudinary(url_cu)
            CaiDat.dat(khoa, url_moi)
    elif request.form.get(ten_xoa) and url_cu:
        xoa_anh_cloudinary(url_cu)
        CaiDat.dat(khoa, "")
    return False


@bp.route("/", methods=["GET", "POST"])
@login_required
def chinh_sua():
    if request.method == "POST":
        loi_pc = _xu_ly_mot_anh("file_anh", "xoa_anh", H.K_ANH, upload_anh_hero, "máy tính")
        loi_mb = _xu_ly_mot_anh("file_anh_mobile", "xoa_anh_mobile", H.K_ANH_MOBILE, upload_anh_hero_mobile, "điện thoại")

        CaiDat.dat(H.K_DO_PHU, str(H.kep_do_phu(request.form.get("do_phu"))))
        CaiDat.dat(H.K_ALT, (request.form.get("alt") or "").strip()[:150])
        db.session.commit()
        if loi_pc or loi_mb:
            flash("Đã lưu các cài đặt khác; ảnh bị lỗi chưa được thay đổi.", "warning")
        else:
            flash("Đã lưu ảnh nền trang chủ.", "success")
        return redirect(url_for("admin_hero.chinh_sua"))

    return render_template("admin/hero/form.html", cd=H.doc_cai_dat(), H=H)
