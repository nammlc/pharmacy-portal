from flask import Blueprint, render_template, request, abort
from app import db
from app.models.models import BaiViet, DanhMucBaiViet

bp = Blueprint("bv", __name__, url_prefix="/bai-viet")

SO_BAI_MOI_TRANG = 9


@bp.route("/")
def index():
    """Danh sách bài viết/thông báo đã xuất bản, có thể lọc theo danh mục."""
    danh_muc_slug = request.args.get("danh_muc", "").strip()
    trang = request.args.get("trang", 1, type=int)

    query = BaiViet.query.filter(BaiViet.trang_thai == "da_xuat_ban")

    danh_muc_hien_tai = None
    if danh_muc_slug:
        danh_muc_hien_tai = DanhMucBaiViet.query.filter_by(slug=danh_muc_slug).first_or_404()
        query = query.filter(BaiViet.danh_muc_id == danh_muc_hien_tai.id)

    phan_trang = (query
                  .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                  .paginate(page=trang, per_page=SO_BAI_MOI_TRANG, error_out=False))

    danh_sach_danh_muc = DanhMucBaiViet.query.order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten).all()

    return render_template(
        "bai_viet/index.html",
        bai_viet_list=phan_trang.items,
        phan_trang=phan_trang,
        danh_sach_danh_muc=danh_sach_danh_muc,
        danh_muc_hien_tai=danh_muc_hien_tai,
    )


@bp.route("/<slug>")
def chi_tiet(slug):
    """Chi tiết 1 bài viết - chỉ xem được nếu đã xuất bản."""
    bai_viet = BaiViet.query.filter_by(slug=slug).first_or_404()
    if bai_viet.trang_thai != "da_xuat_ban":
        abort(404)

    # Tăng lượt xem - không quan trọng nếu commit lệch do 2 request đồng thời
    bai_viet.luot_xem = (bai_viet.luot_xem or 0) + 1
    db.session.commit()

    bai_lien_quan = (
        BaiViet.query
        .filter(
            BaiViet.trang_thai == "da_xuat_ban",
            BaiViet.id != bai_viet.id,
            BaiViet.danh_muc_id == bai_viet.danh_muc_id,
        )
        .order_by(BaiViet.ngay_xuat_ban.desc())
        .limit(4)
        .all()
    )

    return render_template("bai_viet/chi_tiet.html", bai_viet=bai_viet, bai_lien_quan=bai_lien_quan)
