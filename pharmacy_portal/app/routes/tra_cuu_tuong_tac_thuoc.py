from flask import Blueprint, render_template, request
from sqlalchemy import or_
from app.models.models import Thuoc, TuongTacThuoc

bp = Blueprint("ttt", __name__, url_prefix="/tra-cuu-tuong-tac-thuoc")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    ket_qua = []
    if tu_khoa:
        like_pattern = f"%{tu_khoa}%"
        ThuocA = Thuoc.__table__.alias("thuoc_a_tbl")

        ket_qua = (
            TuongTacThuoc.query.join(Thuoc, TuongTacThuoc.thuoc_a_id == Thuoc.id)
            .filter(Thuoc.ten_thuoc.ilike(like_pattern))
            .limit(50)
            .all()
        )

    return render_template(
        "tra_cuu_tuong_tac_thuoc.html",
        ket_qua=ket_qua,
        tu_khoa=tu_khoa,
    )
