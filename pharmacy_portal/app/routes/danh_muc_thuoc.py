from flask import Blueprint, render_template, request
from app.models.models import NhomThuoc, Thuoc

bp = Blueprint("dmt", __name__, url_prefix="/danh-muc-thuoc")


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    if tu_khoa:
        like_pattern = f"%{tu_khoa}%"
        ket_qua = Thuoc.query.filter(
            Thuoc.ten_thuoc.ilike(like_pattern) | Thuoc.hoat_chat.ilike(like_pattern)
        ).order_by(Thuoc.ten_thuoc).limit(60).all()
        return render_template("danh_muc_thuoc/tim_kiem.html", ket_qua=ket_qua, tu_khoa=tu_khoa)

    # Cây nhóm thuốc cấp cao nhất (không có nhóm cha)
    nhom_goc = (
        NhomThuoc.query.filter_by(loai="danh_muc_thuoc", parent_id=None)
        .order_by(NhomThuoc.thu_tu, NhomThuoc.ten_nhom)
        .all()
    )
    return render_template("danh_muc_thuoc/index.html", nhom_goc=nhom_goc)


@bp.route("/nhom/<int:nhom_id>")
def xem_nhom(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    danh_sach_thuoc = Thuoc.query.filter_by(nhom_thuoc_id=nhom.id).order_by(Thuoc.ten_thuoc).all()
    return render_template("danh_muc_thuoc/nhom.html", nhom=nhom, danh_sach_thuoc=danh_sach_thuoc)


@bp.route("/thuoc/<int:thuoc_id>")
def xem_thuoc(thuoc_id):
    thuoc = Thuoc.query.get_or_404(thuoc_id)
    return render_template("danh_muc_thuoc/chi_tiet.html", thuoc=thuoc)
