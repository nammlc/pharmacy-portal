from flask import Blueprint, render_template, request
from app.models.models import Thuoc, ThongTinThuoc

bp = Blueprint("ttth", __name__, url_prefix="/tra-cuu-thong-tin-thuoc")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    query = Thuoc.query
    if tu_khoa:
        like_pattern = f"%{tu_khoa}%"
        query = query.filter(
            Thuoc.ten_thuoc.ilike(like_pattern) | Thuoc.hoat_chat.ilike(like_pattern)
        )
    danh_sach_thuoc = query.order_by(Thuoc.ten_thuoc).limit(50).all()

    return render_template(
        "tra_cuu_thong_tin_thuoc.html",
        danh_sach_thuoc=danh_sach_thuoc,
        tu_khoa=tu_khoa,
    )


@bp.route("/<int:thuoc_id>")
def chi_tiet(thuoc_id):
    thuoc = Thuoc.query.get_or_404(thuoc_id)
    return render_template("chi_tiet_thuoc.html", thuoc=thuoc)
