from flask import Blueprint, render_template
from flask_login import login_required
from app.models.models import (
    Thuoc, ThuocTiemTruyen, TuongHopTuongKy, TuongTacThuoc,
    ThongTinThuoc, ThongTinBenhNhan, DanhMucThuoc, NhaThuocBV
)

bp = Blueprint("admin_dashboard", __name__, url_prefix="/admin")


@bp.route("/")
@login_required
def trang_chinh():
    so_luong = {
        "danh_muc_thuoc": DanhMucThuoc.query.count(),
        "nha_thuoc_bv": NhaThuocBV.query.count(),
        "thuoc": Thuoc.query.count(),
        "tiem_truyen": ThuocTiemTruyen.query.count(),
        "tuong_hop_tuong_ky": TuongHopTuongKy.query.count(),
        "tuong_tac": TuongTacThuoc.query.count(),
        "thong_tin_thuoc": ThongTinThuoc.query.count(),
        "benh_nhan": ThongTinBenhNhan.query.count(),
    }
    return render_template("admin/trang_chinh.html", so_luong=so_luong)
