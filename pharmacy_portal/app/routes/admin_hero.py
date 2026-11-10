import logging

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from app import db
from app.models.models import CaiDat
from app.utils import hero as H
from app.utils.upload_anh import upload_anh_hero, xoa_anh_cloudinary

bp = Blueprint("admin_hero", __name__, url_prefix="/admin/anh-trang-chu")
log = logging.getLogger(__name__)


@bp.route("/", methods=["GET", "POST"])
@login_required
def chinh_sua():
    if request.method == "POST":
        url_cu = CaiDat.lay(H.K_ANH)
        file_anh = request.files.get("file_anh")

        if file_anh and file_anh.filename:
            # Tải ảnh MỚI lên trước, thành công rồi mới xoá ảnh cũ -> lỡ lỗi mạng thì trang chủ vẫn còn ảnh cũ.
            try:
                url_moi = upload_anh_hero(file_anh, url_cu=None)
            except ValueError as e:
                flash(str(e), "warning")
                url_moi = None
            except Exception:
                log.exception("Upload ảnh hero lỗi")
                flash("Không tải được ảnh lên Cloudinary. Kiểm tra lại kết nối/khoá Cloudinary rồi thử lại.", "danger")
                url_moi = None
            if url_moi:
                if url_cu:
                    xoa_anh_cloudinary(url_cu)
                CaiDat.dat(H.K_ANH, url_moi)
        elif request.form.get("xoa_anh") and url_cu:
            xoa_anh_cloudinary(url_cu)
            CaiDat.dat(H.K_ANH, "")

        CaiDat.dat(H.K_DO_PHU, str(H.kep_do_phu(request.form.get("do_phu"))))
        vi_tri = request.form.get("vi_tri")
        CaiDat.dat(H.K_VI_TRI, vi_tri if vi_tri in H.VI_TRI else H.VI_TRI_MAC_DINH)
        CaiDat.dat(H.K_ALT, (request.form.get("alt") or "").strip()[:150])
        db.session.commit()
        flash("Đã lưu ảnh nền trang chủ.", "success")
        return redirect(url_for("admin_hero.chinh_sua"))

    return render_template("admin/hero/form.html", cd=H.doc_cai_dat(), H=H)
