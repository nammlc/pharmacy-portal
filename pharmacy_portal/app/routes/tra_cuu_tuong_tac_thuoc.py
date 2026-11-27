from types import SimpleNamespace

from flask import Blueprint, render_template, request
from app.utils.tim_kiem import tim_tuong_tac

bp = Blueprint("ttt", __name__, url_prefix="/tra-cuu-tuong-tac-thuoc")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()
    kq = tim_tuong_tac(tu_khoa) if tu_khoa else SimpleNamespace(cap=[], tong=0, hoat_chat_khop=[], thuoc_khop=[])
    return render_template("tra_cuu_tuong_tac_thuoc.html", ket_qua=kq.cap, tong=kq.tong,
                           thuoc_khop=kq.thuoc_khop, tu_khoa=tu_khoa)
