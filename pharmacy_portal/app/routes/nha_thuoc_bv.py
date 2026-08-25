from flask import Blueprint, render_template, request
from sqlalchemy import func
from app import db
from app.models.models import NhomThuoc, HoatChat, NhaThuocBV

bp = Blueprint("ntbv", __name__, url_prefix="/nha-thuoc-bv")

SO_THUOC_MOI_TRANG = 12
SO_NHOM_MOI_TRANG = 8


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    if tu_khoa:
        trang = request.args.get("page", 1, type=int)
        like_pattern = f"%{tu_khoa}%"
        phan_trang = (
            NhaThuocBV.query.outerjoin(HoatChat, NhaThuocBV.hoat_chat_id == HoatChat.id)
            .filter(
                NhaThuocBV.ten_biet_duoc.ilike(like_pattern)
                | HoatChat.ten_hoat_chat.ilike(like_pattern)
            )
            .order_by(NhaThuocBV.ten_biet_duoc)
            .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
        )
        return render_template("nha_thuoc_bv/tim_kiem.html", phan_trang=phan_trang, tu_khoa=tu_khoa)

    trang = request.args.get("page", 1, type=int)
    phan_trang_nhom = (
        NhomThuoc.query.filter_by(loai="nha_thuoc_bv")
        .order_by(NhomThuoc.thu_tu, NhomThuoc.ten_nhom)
        .paginate(page=trang, per_page=SO_NHOM_MOI_TRANG, error_out=False)
    )
    counts = dict(
        db.session.query(NhaThuocBV.nhom_thuoc_id, func.count(NhaThuocBV.id))
        .group_by(NhaThuocBV.nhom_thuoc_id)
        .all()
    )
    return render_template("nha_thuoc_bv/index.html", phan_trang_nhom=phan_trang_nhom, counts=counts)


@bp.route("/nhom/<int:nhom_id>")
def xem_nhom(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    trang = request.args.get("page", 1, type=int)
    phan_trang = (
        NhaThuocBV.query.filter_by(nhom_thuoc_id=nhom.id)
        .order_by(NhaThuocBV.ten_biet_duoc)
        .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
    )
    return render_template("nha_thuoc_bv/nhom.html", nhom=nhom, phan_trang=phan_trang)


@bp.route("/thuoc/<int:thuoc_id>")
def xem_thuoc(thuoc_id):
    thuoc = NhaThuocBV.query.get_or_404(thuoc_id)
    return render_template("nha_thuoc_bv/chi_tiet.html", thuoc=thuoc)
