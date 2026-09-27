from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from sqlalchemy import text
from app import db
from app.models.models import DanhMucThuoc, NhaThuocBV
from app.utils.upload_anh import upload_anh_noi_dung

bp = Blueprint("admin_dashboard", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
def trang_chinh():
    # Gộp 8 COUNT thành 1 query duy nhất — giảm từ 8 round-trip xuống 1
    result = db.session.execute(text("""
        SELECT 'danh_muc_thuoc'     AS ten, COUNT(*) FROM danh_muc_thuoc
        UNION ALL
        SELECT 'nha_thuoc_bv',               COUNT(*) FROM nha_thuoc_bv
        UNION ALL
        SELECT 'thuoc',                       COUNT(*) FROM thuoc
        UNION ALL
        SELECT 'tiem_truyen',                 COUNT(*) FROM thuoc_tiem_truyen
        UNION ALL
        SELECT 'tuong_hop_tuong_ky',          COUNT(*) FROM tuong_hop_tuong_ky
        UNION ALL
        SELECT 'tuong_tac',                   COUNT(*) FROM tuong_tac_thuoc
        UNION ALL
        SELECT 'thong_tin_thuoc',             COUNT(*) FROM thong_tin_thuoc
        UNION ALL
        SELECT 'benh_nhan',                   COUNT(*) FROM thong_tin_benh_nhan
    """)).fetchall()

    so_luong = {row[0]: row[1] for row in result}

    # Lấy 5 thuốc cập nhật gần nhất (danh_muc_thuoc + nha_thuoc_bv)
    cap_nhat_dmt = (
        DanhMucThuoc.query
        .filter(DanhMucThuoc.ngay_cap_nhat.isnot(None))
        .order_by(DanhMucThuoc.ngay_cap_nhat.desc())
        .limit(5).all()
    )
    cap_nhat_ntbv = (
        NhaThuocBV.query
        .filter(NhaThuocBV.ngay_cap_nhat.isnot(None))
        .order_by(NhaThuocBV.ngay_cap_nhat.desc())
        .limit(5).all()
    )

    return render_template("admin/trang_chinh.html",
                           so_luong=so_luong,
                           cap_nhat_dmt=cap_nhat_dmt,
                           cap_nhat_ntbv=cap_nhat_ntbv)


@bp.route("/upload-anh-noi-dung", methods=["POST"])
@login_required
def upload_anh_noi_dung_view():
    """API AJAX dùng chung cho MỌI trình soạn thảo rich-text (Quill) trong
    trang quản trị: bấm nút chèn ảnh -> JS gửi file lên đây -> trả về URL
    Cloudinary -> JS chèn thẻ <img> vào đúng vị trí con trỏ trong nội dung.
    Cho phép chèn NHIỀU ảnh mô tả xen giữa các đoạn văn (khác ảnh đại diện,
    vốn chỉ có 1 ảnh cho cả bài viết)."""
    file_anh = request.files.get("anh")
    if not file_anh or not file_anh.filename:
        return jsonify({"loi": "Không nhận được file ảnh."}), 400
    try:
        url = upload_anh_noi_dung(file_anh)
    except ValueError as e:
        return jsonify({"loi": str(e)}), 400
    if not url:
        return jsonify({"loi": "Upload ảnh thất bại, thử lại sau."}), 500
    return jsonify({"url": url})
