from flask import Blueprint, render_template, request, abort, redirect, url_for
from sqlalchemy import or_
from app import db
from app.models.models import BaiViet, DanhMucBaiViet
from app.utils.tim_kiem import tim_bai_viet

bp = Blueprint("bv", __name__, url_prefix="/bai-viet")

SO_BAI_MOI_TRANG = 9      # số bài/trang khi xem theo 1 danh mục cụ thể
SO_BAI_MOI_KHOI = 9       # số bài mỗi khối danh mục ở trang chủ Bài viết
SO_BAI_PHU = 5            # số tiêu đề ở danh sách bên phải slideshow (vừa khít chiều cao ảnh 480px, thừa thì cuộn)
SO_MUC_UU_TIEN = 4        # có 4 mức ưu tiên: 1, 2, 3, 4


def _lay_bai_phu(loai_tru_id_bai=None, loai_tru_danh_muc_ids=None, gioi_han=SO_BAI_PHU):
    """Lấy tối đa `gioi_han` bài viết đã xuất bản, loại trừ theo id bài viết
    và/hoặc id danh mục được truyền vào (dùng cho khối 'Bài viết khác')."""
    query = BaiViet.query.filter(BaiViet.trang_thai == "da_xuat_ban")
    if loai_tru_id_bai:
        query = query.filter(BaiViet.id.notin_(loai_tru_id_bai))
    if loai_tru_danh_muc_ids:
        query = query.filter(
            or_(BaiViet.danh_muc_id.notin_(loai_tru_danh_muc_ids), BaiViet.danh_muc_id.is_(None))
        )
    return (query
            .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
            .limit(gioi_han)
            .all())


def _xay_dung_trang_chu_bai_viet():
    """
    Dựng dữ liệu cho khối đầu trang "Bài viết" (không lọc danh mục, không tìm kiếm):
    - slide_bai: tối đa 4 bài cho slideshow bên trái, lấy theo mức ưu tiên 1-2-3-4
      (admin gán ở trang sửa bài viết). Mức nào chưa gán thì bù bằng bài ghim/mới nhất.
    - bai_phu: danh sách tiêu đề bên phải, KHÔNG trùng bài trong slideshow và KHÁC
      danh mục với bài ưu tiên mức 1.
    - danh_sach_khoi_danh_muc: các khối lưới 3 cột bên dưới, mỗi khối 1 danh mục,
      tối đa 9 bài/khối. Thứ tự khối theo danh mục của các bài ưu tiên 1→2→3→4
      trước, các danh mục còn lại xếp sau theo thứ tự đã cấu hình.
    """
    da_xuat_ban = BaiViet.trang_thai == "da_xuat_ban"

    # --- Bài ưu tiên theo từng mức (mỗi mức lấy đúng 1 bài) ---
    bai_uu_tien_theo_muc = {}
    for b in (BaiViet.query.filter(da_xuat_ban, BaiViet.do_uu_tien.isnot(None))
              .order_by(BaiViet.do_uu_tien.asc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
              .all()):
        if b.do_uu_tien not in bai_uu_tien_theo_muc:
            bai_uu_tien_theo_muc[b.do_uu_tien] = b

    slide_bai = [bai_uu_tien_theo_muc[m] for m in range(1, SO_MUC_UU_TIEN + 1) if m in bai_uu_tien_theo_muc]

    # Bù cho đủ 4 slide nếu còn thiếu mức ưu tiên - lấy bài ghim/mới nhất chưa có.
    if len(slide_bai) < SO_MUC_UU_TIEN:
        ds_id_slide = [b.id for b in slide_bai]
        query_bu = BaiViet.query.filter(da_xuat_ban)
        if ds_id_slide:
            query_bu = query_bu.filter(BaiViet.id.notin_(ds_id_slide))
        bu = (query_bu
              .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
              .limit(SO_MUC_UU_TIEN - len(slide_bai))
              .all())
        slide_bai += bu

    # --- Danh sách tiêu đề bên phải: ưu tiên khác danh mục với bài ưu tiên
    # mức 1, và khác các bài đã có trong slideshow. Trang web có thể còn ít
    # bài viết nên lọc chặt dễ ra danh sách RỖNG (lỗi trước đây khiến khối
    # này "không hiện gì cả") — nới lỏng dần từng điều kiện một cho tới khi
    # có kết quả, để sidebar luôn có nội dung nếu còn bài nào khác trên hệ
    # thống, mà vẫn ưu tiên đúng ý: khác danh mục bài ưu tiên 1 trước tiên.
    ds_id_slide = [b.id for b in slide_bai]
    bai_uu_tien_1 = bai_uu_tien_theo_muc.get(1)
    danh_muc_uu_tien_1 = bai_uu_tien_1.danh_muc_id if bai_uu_tien_1 else None

    bai_phu = []
    for loai_tru_id_bai, loai_tru_dm in [
        (ds_id_slide, {danh_muc_uu_tien_1} if danh_muc_uu_tien_1 else None),  # 1) đẹp nhất: khác cả slideshow lẫn danh mục #1
        (ds_id_slide, None),                                                   # 2) bỏ điều kiện danh mục, vẫn khác slideshow
        ([bai_uu_tien_1.id] if bai_uu_tien_1 else None, {danh_muc_uu_tien_1} if danh_muc_uu_tien_1 else None),  # 3) chỉ loại đúng bài #1 + danh mục của nó
        ([bai_uu_tien_1.id] if bai_uu_tien_1 else None, None),                 # 4) chỉ loại đúng bài #1
    ]:
        bai_phu = _lay_bai_phu(loai_tru_id_bai=loai_tru_id_bai, loai_tru_danh_muc_ids=loai_tru_dm)
        if bai_phu:
            break

    # --- Thứ tự danh mục cho các khối lưới bên dưới ---
    tat_ca_danh_muc = DanhMucBaiViet.query.order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten).all()
    dm_theo_id = {dm.id: dm for dm in tat_ca_danh_muc}

    thu_tu_danh_muc = []
    da_xep = set()
    for m in range(1, SO_MUC_UU_TIEN + 1):
        b = bai_uu_tien_theo_muc.get(m)
        if b and b.danh_muc_id and b.danh_muc_id not in da_xep:
            thu_tu_danh_muc.append(b.danh_muc_id)
            da_xep.add(b.danh_muc_id)
    for dm in tat_ca_danh_muc:
        if dm.id not in da_xep:
            thu_tu_danh_muc.append(dm.id)
            da_xep.add(dm.id)

    danh_sach_khoi_danh_muc = []
    for dm_id in thu_tu_danh_muc:
        dm = dm_theo_id.get(dm_id)
        if not dm:
            continue
        bai_list = (BaiViet.query
                    .filter(da_xuat_ban, BaiViet.danh_muc_id == dm.id)
                    .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                    .limit(SO_BAI_MOI_KHOI)
                    .all())
        if bai_list:
            danh_sach_khoi_danh_muc.append({"danh_muc": dm, "bai_list": bai_list})

    # --- Bài chưa gán danh mục: gom vào 1 khối "Khác" ở cuối, không để mất bài ---
    bai_khong_danh_muc = (BaiViet.query
                           .filter(da_xuat_ban, BaiViet.danh_muc_id.is_(None))
                           .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                           .limit(SO_BAI_MOI_KHOI)
                           .all())
    if bai_khong_danh_muc:
        danh_sach_khoi_danh_muc.append({"danh_muc": None, "bai_list": bai_khong_danh_muc})

    return slide_bai, bai_phu, danh_sach_khoi_danh_muc


@bp.route("/")
def index():
    """
    - Có ?q= : trang kết quả tìm kiếm.
    - Có ?danh_muc= : lưới bài viết phẳng theo 1 danh mục, có phân trang (như cũ).
    - Không có gì cả (trang chủ Bài viết): layout tạp chí - slideshow ưu tiên
      bên trái, danh sách tiêu đề bên phải, các khối lưới 3 cột theo danh mục
      bên dưới (xem hàm _xay_dung_trang_chu_bai_viet).
    """
    tu_khoa = request.args.get("q", "").strip()
    trang = request.args.get("page", 1, type=int)

    danh_sach_danh_muc = DanhMucBaiViet.query.order_by(DanhMucBaiViet.thu_tu, DanhMucBaiViet.ten).all()

    if tu_khoa:
        phan_trang = tim_bai_viet(tu_khoa, per_page=SO_BAI_MOI_TRANG, page=trang)
        return render_template(
            "bai_viet/tim_kiem.html",
            phan_trang=phan_trang,
            tu_khoa=tu_khoa,
            danh_sach_danh_muc=danh_sach_danh_muc,
        )

    danh_muc_slug = request.args.get("danh_muc", "").strip()
    danh_muc_hien_tai = None
    if danh_muc_slug:
        danh_muc_hien_tai = DanhMucBaiViet.query.filter_by(slug=danh_muc_slug).first_or_404()

    bai_viet_list = []
    phan_trang = None
    slide_bai, bai_phu, danh_sach_khoi_danh_muc = [], [], []

    if danh_muc_hien_tai:
        query = BaiViet.query.filter(
            BaiViet.trang_thai == "da_xuat_ban",
            BaiViet.danh_muc_id == danh_muc_hien_tai.id,
        )
        phan_trang = (query
                      .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc(), BaiViet.ngay_tao.desc())
                      .paginate(page=trang, per_page=SO_BAI_MOI_TRANG, error_out=False))
        bai_viet_list = phan_trang.items
    elif trang == 1:
        slide_bai, bai_phu, danh_sach_khoi_danh_muc = _xay_dung_trang_chu_bai_viet()
    else:
        # Trang chủ Bài viết (không lọc danh mục) không còn khái niệm "trang 2"
        # với layout tạp chí mới - quay lại trang 1.
        return redirect(url_for("bv.index"))

    return render_template(
        "bai_viet/index.html",
        bai_viet_list=bai_viet_list,
        phan_trang=phan_trang,
        danh_sach_danh_muc=danh_sach_danh_muc,
        danh_muc_hien_tai=danh_muc_hien_tai,
        slide_bai=slide_bai,
        bai_phu=bai_phu,
        danh_sach_khoi_danh_muc=danh_sach_khoi_danh_muc,
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
