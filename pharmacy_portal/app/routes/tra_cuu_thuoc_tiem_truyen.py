from flask import Blueprint, render_template, request
from app.models.models import Thuoc, ThuocTiemTruyen

bp = Blueprint("tttt", __name__, url_prefix="/tra-cuu-thuoc-tiem-truyen")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    query = ThuocTiemTruyen.query.join(Thuoc)
    if tu_khoa:
        like_pattern = f"%{tu_khoa}%"
        query = query.filter(
            Thuoc.ten_thuoc.ilike(like_pattern) | Thuoc.hoat_chat.ilike(like_pattern)
        )

    ket_qua = query.order_by(Thuoc.ten_thuoc).limit(50).all()

    return render_template(
        "tra_cuu_thuoc_tiem_truyen.html",
        ket_qua=ket_qua,
        tu_khoa=tu_khoa,
    )
