from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.route("/")
def trang_chu():
    return render_template("trang_chu.html")
