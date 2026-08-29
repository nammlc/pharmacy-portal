from flask import Blueprint, render_template, request
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from app import db
from app.models.models import NhomThuoc, NhaThuocBV
from app.utils.tim_kiem import tim_nha_thuoc_bv

bp = Blueprint("ntbv", __name__, url_prefix="/nha-thuoc-bv")

SO_THUOC_MOI_TRANG = 12
SO_NHOM_MOI_TRANG = 8


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    if tu_khoa:
        trang = request.args.get("page", 1, type=int)
        phan_trang = tim_nha_thuoc_bv(tu_khoa, per_page=SO_THUOC_MOI_TRANG, page=trang)
        return render_template("nha_thuoc_bv/tim_kiem.html",
                               phan_trang=phan_trang, tu_khoa=tu_khoa)

    trang = request.args.get("page", 1, type=int)
    phan_trang_nhom = (
        NhomThuoc.query.filter_by(loai="nha_thuoc_bv")
        .order_by(NhomThuoc.thu_tu, NhomThuoc.ten_nhom)
        .paginate(page=trang, per_page=SO_NHOM_MOI_TRANG, error_out=False)
    )
    counts = dict(
        db.session.query(NhaThuocBV.nhom_thuoc_id, func.count(NhaThuocBV.id))
        .group_by(NhaThuocBV.nhom_thuoc_id).all()
    )
    return render_template("nha_thuoc_bv/index.html",
                           phan_trang_nhom=phan_trang_nhom, counts=counts)


@bp.route("/nhom/<int:nhom_id>")
def xem_nhom(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    trang = request.args.get("page", 1, type=int)
    tu_khoa = request.args.get("q", "").strip()
    if tu_khoa:
        from app.models.models import HoatChat
        from app.utils.tim_kiem import _build_filter
        cols = [NhaThuocBV.ten_biet_duoc, HoatChat.ten_hoat_chat]
        f = _build_filter(cols, tu_khoa)
        phan_trang = (
            NhaThuocBV.query
            .options(selectinload(NhaThuocBV.hoat_chat_list))
            .outerjoin(NhaThuocBV.hoat_chat_list)
            .filter(NhaThuocBV.nhom_thuoc_id == nhom_id, f)
            .distinct()
            .order_by(NhaThuocBV.ten_biet_duoc)
            .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
        )
    else:
        phan_trang = (
            NhaThuocBV.query
            .options(selectinload(NhaThuocBV.hoat_chat_list))
            .filter_by(nhom_thuoc_id=nhom.id)
            .order_by(NhaThuocBV.ten_biet_duoc)
            .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
        )
    return render_template("nha_thuoc_bv/nhom.html",
                           nhom=nhom, phan_trang=phan_trang, tu_khoa=tu_khoa)


@bp.route("/thuoc/<int:thuoc_id>")
def xem_thuoc(thuoc_id):
    thuoc = NhaThuocBV.query.get_or_404(thuoc_id)
    return render_template("nha_thuoc_bv/chi_tiet.html", thuoc=thuoc)
