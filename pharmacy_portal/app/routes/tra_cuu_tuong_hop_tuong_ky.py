from flask import Blueprint, render_template, request
from app.utils.tim_kiem import tim_tuong_hop_tuong_ky

bp = Blueprint("thtk", __name__, url_prefix="/tra-cuu-tuong-hop-tuong-ky")


@bp.route("/")
def index():
    thuoc_a = request.args.get("thuoc_a", "").strip()
    thuoc_b = request.args.get("thuoc_b", "").strip()
    ket_qua = tim_tuong_hop_tuong_ky(thuoc_a, thuoc_b) if thuoc_a else []
    return render_template("tra_cuu_tuong_hop_tuong_ky.html",
                           ket_qua=ket_qua, thuoc_a=thuoc_a, thuoc_b=thuoc_b)
