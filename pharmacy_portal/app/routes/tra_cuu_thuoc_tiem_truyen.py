from flask import Blueprint, render_template, request
from app.models.models import Thuoc, ThuocTiemTruyen

bp = Blueprint("tttt", __name__, url_prefix="/tra-cuu-thuoc-tiem-truyen")

SO_THUOC_MOI_TRANG = 15


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("page", 1, type=int)

    query = ThuocTiemTruyen.query.join(Thuoc)
    if tu_khoa:
        like_pattern = f"%{tu_khoa}%"
        query = query.filter(
            Thuoc.ten_thuoc.ilike(like_pattern) | Thuoc.hoat_chat.ilike(like_pattern)
        )

    phan_trang = query.order_by(Thuoc.ten_thuoc).paginate(
        page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False
    )

    return render_template(
        "tra_cuu_thuoc_tiem_truyen.html",
        phan_trang=phan_trang,
        tu_khoa=tu_khoa,
    )
