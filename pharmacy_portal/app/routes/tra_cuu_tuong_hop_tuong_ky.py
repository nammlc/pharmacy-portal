from flask import Blueprint, render_template, request
from sqlalchemy import or_
from app.models.models import Thuoc, TuongHopTuongKy

bp = Blueprint("thtk", __name__, url_prefix="/tra-cuu-tuong-hop-tuong-ky")


@bp.route("/")
def index():
    thuoc_a = request.args.get("thuoc_a", "").strip()
    thuoc_b = request.args.get("thuoc_b", "").strip()

    ket_qua = []
    if thuoc_a and thuoc_b:
        # Tìm theo cả 2 chiều: A-B hoặc B-A đều tính là 1 cặp
        ThuocA = Thuoc.__table__.alias("ta")
        ThuocB = Thuoc.__table__.alias("tb")

        pattern_a = f"%{thuoc_a}%"
        pattern_b = f"%{thuoc_b}%"

        ket_qua = (
            TuongHopTuongKy.query.join(Thuoc, TuongHopTuongKy.thuoc_a_id == Thuoc.id)
            .filter(
                or_(
                    Thuoc.ten_thuoc.ilike(pattern_a),
                    Thuoc.ten_thuoc.ilike(pattern_b),
                )
            )
            .limit(50)
            .all()
        )

    return render_template(
        "tra_cuu_tuong_hop_tuong_ky.html",
        ket_qua=ket_qua,
        thuoc_a=thuoc_a,
        thuoc_b=thuoc_b,
    )
