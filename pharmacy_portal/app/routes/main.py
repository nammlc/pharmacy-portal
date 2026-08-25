from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def trang_chu():
    return render_template("trang_chu.html")


@bp.route("/ve-chung-toi")
def ve_chung_toi():
    return render_template("ve_chung_toi.html")
