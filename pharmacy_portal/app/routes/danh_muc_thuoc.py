from flask import Blueprint, render_template, request
from sqlalchemy import func
from app import db
from app.models.models import NhomThuoc, HoatChat, DanhMucThuoc

bp = Blueprint("dmt", __name__, url_prefix="/danh-muc-thuoc")

SO_THUOC_MOI_TRANG = 12


@bp.route("/")
def index():
    tu_khoa = request.args.get("q", "").strip()

    if tu_khoa:
        trang = request.args.get("page", 1, type=int)
        like_pattern = f"%{tu_khoa}%"
        phan_trang = (
            DanhMucThuoc.query.outerjoin(HoatChat, DanhMucThuoc.hoat_chat_id == HoatChat.id)
            .filter(
                DanhMucThuoc.ten_biet_duoc.ilike(like_pattern)
                | HoatChat.ten_hoat_chat.ilike(like_pattern)
            )
            .order_by(DanhMucThuoc.ten_biet_duoc)
            .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
        )
        return render_template("danh_muc_thuoc/tim_kiem.html", phan_trang=phan_trang, tu_khoa=tu_khoa)

    nhom_ds = (
        NhomThuoc.query.filter_by(loai="danh_muc_thuoc")
        .order_by(NhomThuoc.thu_tu, NhomThuoc.ten_nhom)
        .all()
    )
    counts = dict(
        db.session.query(DanhMucThuoc.nhom_thuoc_id, func.count(DanhMucThuoc.id))
        .group_by(DanhMucThuoc.nhom_thuoc_id)
        .all()
    )
    return render_template("danh_muc_thuoc/index.html", nhom_ds=nhom_ds, counts=counts)


@bp.route("/nhom/<int:nhom_id>")
def xem_nhom(nhom_id):
    nhom = NhomThuoc.query.get_or_404(nhom_id)
    trang = request.args.get("page", 1, type=int)
    phan_trang = (
        DanhMucThuoc.query.filter_by(nhom_thuoc_id=nhom.id)
        .order_by(DanhMucThuoc.ten_biet_duoc)
        .paginate(page=trang, per_page=SO_THUOC_MOI_TRANG, error_out=False)
    )
    return render_template("danh_muc_thuoc/nhom.html", nhom=nhom, phan_trang=phan_trang)


@bp.route("/thuoc/<int:thuoc_id>")
def xem_thuoc(thuoc_id):
    thuoc = DanhMucThuoc.query.get_or_404(thuoc_id)
    return render_template("danh_muc_thuoc/chi_tiet.html", thuoc=thuoc)
