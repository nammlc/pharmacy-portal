from flask import Blueprint, render_template, request
from app.utils.tim_kiem import tim_tuong_tac

bp = Blueprint("ttt", __name__, url_prefix="/tra-cuu-tuong-tac-thuoc")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()
    ket_qua = tim_tuong_tac(tu_khoa) if tu_khoa else []
    return render_template("tra_cuu_tuong_tac_thuoc.html",
                           ket_qua=ket_qua, tu_khoa=tu_khoa)
