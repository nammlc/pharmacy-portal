import re
from flask import Blueprint, render_template, redirect, url_for, request
from sqlalchemy import text
from app import db
from app.models.models import CaiDat, DanhMucThuoc, NhaThuocBV, HoatChat
from app.utils.tim_kiem import tim_danh_muc_thuoc, tim_nha_thuoc_bv

# Dấu phân cách được chấp nhận giữa các tên thuốc khi phần mềm bên thứ 3
# (đơn thuốc điện tử) tạo mã QR tìm kiếm hàng loạt, ví dụ:
#   /tim-kiem?q=Lidocain,Paracetamol,Amoxicillin
#   /tim-kiem?q=Lidocain;Paracetamol;Amoxicillin
# Chấp nhận cả dấu phẩy và chấm phẩy để linh hoạt với nhiều nhà cung cấp.
TACH_TU_KHOA_HANG_LOAT = re.compile(r"[,;]+")

SO_XEM_TRUOC_DON = 8
SO_XEM_TRUOC_HANG_LOAT = 5

bp = Blueprint("main", __name__)

VCT_KEYS = [
    "vct_tieu_de", "vct_mo_ta_ngan", "vct_gioi_thieu",
    "vct_su_menh", "vct_tam_nhin",
    "vct_hinh_anh_1", "vct_hinh_anh_2",
    "vct_ten_lien_he", "vct_chuc_vu_lien_he",
    "vct_dien_thoai", "vct_email", "vct_dia_chi",
]

VCT_MAC_DINH = {
    "vct_tieu_de": "Về chúng tôi",
    "vct_mo_ta_ngan": "Cổng tra cứu dược được Khoa Dược xây dựng và duy trì để tra cứu thông tin thuốc nhanh, chính xác, phục vụ công tác chuyên môn trong bệnh viện.",
    "vct_gioi_thieu": "Khoa Dược – Bệnh viện Đa khoa Tâm Đức Cầu Quan là đơn vị chịu trách nhiệm quản lý, cấp phát và tư vấn sử dụng thuốc an toàn, hợp lý cho toàn bệnh viện.",
    "vct_su_menh": "Cung cấp thông tin dược phẩm chính xác, kịp thời, hỗ trợ công tác điều trị an toàn.",
    "vct_tam_nhin": "Trở thành cổng tra cứu dược tin cậy, hiện đại, phục vụ tốt nhất cho cán bộ y tế và người bệnh.",
    "vct_ten_lien_he": "Ds. Tống Văn Tuấn",
    "vct_chuc_vu_lien_he": "Trưởng khoa Dược",
    "vct_dien_thoai": "0977 755 119",
}


@bp.route("/")
def vao_trang():
    # Vừa truy cập vào web ("/") thì đẩy thẳng vào trang Bài viết/Thông báo,
    # để thấy ngay tin tức/thông báo mới nhất. Trang chủ (thống kê) cũ vẫn
    # giữ nguyên, xem tại /trang-chu (nav "Trang chủ" trỏ vào đây).
    return redirect(url_for("bv.index"))


@bp.route("/trang-chu")
def trang_chu():
    # Lấy stat từ DB — dùng lại UNION ALL giống dashboard
    try:
        rows = db.session.execute(text("""
            SELECT 'dmt', COUNT(*) FROM danh_muc_thuoc
            UNION ALL SELECT 'ntbv', COUNT(*) FROM nha_thuoc_bv
            UNION ALL SELECT 'thuoc', COUNT(*) FROM thuoc
            UNION ALL SELECT 'thtk', COUNT(*) FROM tuong_hop_tuong_ky
        """)).fetchall()
        stat = {r[0]: r[1] for r in rows}
    except Exception:
        stat = {}
    # Lấy 4 bài viết mới nhất cho section homepage
    from app.models.models import BaiViet
    bai_viet_moi = (
        BaiViet.query
        .filter_by(trang_thai="da_xuat_ban")
        .order_by(BaiViet.ghim.desc(), BaiViet.ngay_xuat_ban.desc())
        .limit(4).all()
    )
    return render_template("trang_chu.html", stat=stat, bai_viet_moi=bai_viet_moi)


@bp.route("/tim-kiem")
def tim_kiem():
    """Tìm kiếm gộp: trả kết quả từ cả Danh mục thuốc và Nhà thuốc BV
    - dùng chung bộ máy fuzzy search (bắt lỗi chính tả, gõ thiếu dấu...)
    với ô tìm kiếm trong 2 trang Danh mục thuốc / Nhà thuốc BV, thay vì
    so khớp ilike đơn thuần như trước.

    Tìm kiếm hàng loạt (quét QR đơn thuốc): nếu tham số q chứa nhiều tên
    thuốc nối bằng dấu phẩy/chấm phẩy (vd: ?q=Lidocain,Paracetamol), trang
    sẽ tự chuyển sang chế độ hiển thị kết quả theo từng thuốc trong đơn.
    """
    tu_khoa_goc = request.args.get("q", "").strip()
    if not tu_khoa_goc:
        return redirect(url_for("main.trang_chu"))

    danh_sach_tu_khoa = [
        t.strip() for t in TACH_TU_KHOA_HANG_LOAT.split(tu_khoa_goc) if t.strip()
    ]

    # Chỉ 1 từ khoá (hoặc không tách được) -> giữ nguyên giao diện tìm kiếm đơn
    if len(danh_sach_tu_khoa) <= 1:
        tu_khoa = danh_sach_tu_khoa[0] if danh_sach_tu_khoa else tu_khoa_goc
        phan_trang_dmt = tim_danh_muc_thuoc(tu_khoa, per_page=SO_XEM_TRUOC_DON, page=1)
        phan_trang_ntbv = tim_nha_thuoc_bv(tu_khoa, per_page=SO_XEM_TRUOC_DON, page=1)

        return render_template(
            "tim_kiem_tong_hop.html",
            tu_khoa=tu_khoa,
            phan_trang_dmt=phan_trang_dmt,
            phan_trang_ntbv=phan_trang_ntbv,
        )

    # Từ 2 từ khoá trở lên -> chế độ tìm kiếm hàng loạt theo đơn thuốc
    ket_qua_hang_loat = []
    so_thuoc_khong_thay = 0
    for tu in danh_sach_tu_khoa:
        phan_trang_dmt = tim_danh_muc_thuoc(tu, per_page=SO_XEM_TRUOC_HANG_LOAT, page=1)
        phan_trang_ntbv = tim_nha_thuoc_bv(tu, per_page=SO_XEM_TRUOC_HANG_LOAT, page=1)
        co_ket_qua = bool(phan_trang_dmt.total or phan_trang_ntbv.total)
        if not co_ket_qua:
            so_thuoc_khong_thay += 1
        ket_qua_hang_loat.append({
            "tu_khoa": tu,
            "phan_trang_dmt": phan_trang_dmt,
            "phan_trang_ntbv": phan_trang_ntbv,
            "co_ket_qua": co_ket_qua,
        })

    return render_template(
        "tim_kiem_hang_loat.html",
        tu_khoa_goc=tu_khoa_goc,
        danh_sach_tu_khoa=danh_sach_tu_khoa,
        ket_qua_hang_loat=ket_qua_hang_loat,
        so_thuoc_khong_thay=so_thuoc_khong_thay,
    )


@bp.route("/ve-chung-toi")
def ve_chung_toi():
    du_lieu = {k: CaiDat.lay(k, VCT_MAC_DINH.get(k, "")) for k in VCT_KEYS}
    return render_template("ve_chung_toi.html", d=du_lieu)
