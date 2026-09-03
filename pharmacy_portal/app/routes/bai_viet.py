from flask import Blueprint, render_template, request, abort
from sqlalchemy import or_
from app import db
from app.models.models import BaiViet, DanhMucBaiViet

bp = Blueprint("bv", __name__, url_prefix="/bai-viet")

SO_BAI_MOI_TRANG = 9
SO_BAI_CUNG_DANH_MUC = 3   # grid-3 bên dưới bài lớn, cùng danh mục với bài lớn
SO_BAI_KHAC_DANH_MUC = 6   # danh sách tiêu đề bên cạnh bài lớn, KHÁC danh mục với bài lớn


@bp.route("/")
def index():
    """
    Danh sách bài viết/thông báo đã xuất bản, có thể lọc theo danh mục.

    Ở trang 1 (không lọc theo danh mục), hiển thị thêm khối "nổi bật":
    - 1 bài viết LỚN (bài được admin ghim gần nhất; nếu chưa ghim bài nào
      thì lấy bài mới xuất bản nhất) - ảnh có lớp overlay chứa tiêu đề/mô tả.
    - Bên dưới bài lớn: lưới 3 bài viết CÙNG danh mục với bài lớn.
    - Bên cạnh bài lớn: danh sách tiêu đề các bài viết KHÁC danh mục với bài lớn.
    Các bài còn lại (chưa xuất hiện ở khối trên) hiển thị dạng lưới bên dưới
    như bình thường, có phân trang.
    """
    danh_muc_slug = request.args.get("danh_muc", "").strip()
    trang = request.args.get("trang", 1, type=int)

    query = BaiViet.query.filter(BaiViet.trang_thai == "da_xuat_ban")

    danh_muc_hien_tai = None
    if danh_muc_slug:
        danh_muc_hien_tai = DanhMucBaiViet.query.filter_by(slug=danh_muc_slug).first_or_404()
        query = query.filter(BaiViet.danh_muc_id == danh_muc_hien_tai.id)

    hien_thi_khoi_noi_bat = trang == 1 and not danh_muc_hien_tai

    bai_noi_bat = None
    bai_cung_danh_muc = []
    bai_khac_danh_muc = []
    ds_id_da_dung = []

    if hien_thi_khoi_noi_bat:
        bai_noi_bat = (
            query.filter(BaiViet.ghim.is_(True))
            .order_by(BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
            .first()
        )
        if not bai_noi_bat:
            bai_noi_bat = query.order_by(BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc()).first()

        if bai_noi_bat:
            ds_id_da_dung.append(bai_noi_bat.id)

            if bai_noi_bat.danh_muc_id:
                bai_cung_danh_muc = (
                    query.filter(
                        BaiViet.danh_muc_id == bai_noi_bat.danh_muc_id,
                        BaiViet.id.notin_(ds_id_da_dung),
                    )
                    .order_by(BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                    .limit(SO_BAI_CUNG_DANH_MUC)
                    .all()
                )
                ds_id_da_dung += [b.id for b in bai_cung_danh_muc]

                bai_khac_danh_muc = (
                    query.filter(
                        or_(BaiViet.danh_muc_id != bai_noi_bat.danh_muc_id, BaiViet.danh_muc_id.is_(None)),
                        BaiViet.id.notin_(ds_id_da_dung),
                    )
                    .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                    .limit(SO_BAI_KHAC_DANH_MUC)
                    .all()
                )
            else:
                # Bài lớn chưa gán danh mục -> không có khái niệm "cùng danh mục",
                # danh sách bên cạnh lấy các bài mới nhất còn lại.
                bai_khac_danh_muc = (
                    query.filter(BaiViet.id.notin_(ds_id_da_dung))
                    .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                    .limit(SO_BAI_KHAC_DANH_MUC)
                    .all()
                )
            ds_id_da_dung += [b.id for b in bai_khac_danh_muc]

    query_luoi = query
    if ds_id_da_dung:
        query_luoi = query_luoi.filter(BaiViet.id.notin_(ds_id_da_dung))

    phan_trang = (
        query_luoi.order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
        .paginate(page=trang, per_page=SO_BAI_MOI_TRANG, error_out=False)
    )

    danh_sach_danh_muc = DanhMucBaiViet.query.order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten).all()

    return render_template(
        "bai_viet/index.html",
        bai_viet_list=phan_trang.items,
        phan_trang=phan_trang,
        danh_sach_danh_muc=danh_sach_danh_muc,
        danh_muc_hien_tai=danh_muc_hien_tai,
        bai_noi_bat=bai_noi_bat,
        bai_cung_danh_muc=bai_cung_danh_muc,
        bai_khac_danh_muc=bai_khac_danh_muc,
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
