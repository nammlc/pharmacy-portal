from flask import Blueprint, render_template, request
from app.models.models import ThongTinBenhNhan

bp = Blueprint("ttbn", __name__, url_prefix="/thong-tin-cho-benh-nhan")


@bp.route("/")
def index():
    danh_muc = request.args.get("danh_muc", "").strip()

    query = ThongTinBenhNhan.query
    if danh_muc:
        query = query.filter(ThongTinBenhNhan.danh_muc == danh_muc)

    bai_viet = query.order_by(ThongTinBenhNhan.ngay_dang.desc()).all()

    return render_template("thong_tin_benh_nhan.html", bai_viet=bai_viet, danh_muc=danh_muc)


@bp.route("/<int:bai_viet_id>")
def chi_tiet(bai_viet_id):
    bai_viet = ThongTinBenhNhan.query.get_or_404(bai_viet_id)
    return render_template("chi_tiet_bai_viet.html", bai_viet=bai_viet)
