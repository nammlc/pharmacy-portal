from flask import Blueprint, render_template, redirect, url_for, request
from sqlalchemy import text
from app import db
from app.models.models import CaiDat, DanhMucThuoc, NhaThuocBV, HoatChat
from app.utils.tim_kiem import tim_danh_muc_thuoc, tim_nha_thuoc_bv
import re

# Số thuốc tối đa xử lý trong 1 lần tìm kiếm hàng loạt (an toàn hiệu năng,
# phòng trường hợp mã QR/URL bị chỉnh sửa nhồi quá nhiều từ khoá).
SO_THUOC_TOI_DA_HANG_LOAT = 30

# Số kết quả xem trước cho MỖI thuốc trong chế độ hàng loạt — mỗi thuốc chỉ
# cần vài gợi ý để bệnh nhân nhận ra đúng thuốc, không cần đầy đủ như tìm 1 từ.
SO_XEM_TRUOC_HANG_LOAT = 4


def _tach_danh_sach_thuoc(q: str) -> list[str]:
    """
    Tách chuỗi q thành danh sách tên thuốc riêng lẻ, dùng cho tìm kiếm hàng
    loạt (mã QR trên đơn thuốc). Chấp nhận nhiều kiểu phân tách để phần mềm
    bên thứ ba tạo QR không bị bó buộc 1 định dạng cứng nhắc:
      - dấu phẩy ","      vd:  ?q=Lidocain,Paracetamol,Amoxicillin
      - dấu chấm phẩy ";"  vd:  ?q=Lidocain;Paracetamol
      - dấu gạch đứng "|"  vd:  ?q=Lidocain|Paracetamol
      - xuống dòng (%0A)   vd:  đơn thuốc nhiều dòng, mỗi dòng 1 thuốc
    Loại bỏ khoảng trắng thừa, mục rỗng, mục trùng lặp (không phân biệt hoa
    thường/dấu), và giới hạn tối đa SO_THUOC_TOI_DA_HANG_LOAT thuốc.
    """
    if not q:
        return []
    phan_manh = re.split(r"[,;|\n\r]+", q)
    ket_qua, da_gap = [], set()
    for tho in phan_manh:
        tho = tho.strip()
        if not tho:
            continue
        khoa = tho.lower()
        if khoa in da_gap:
            continue
        da_gap.add(khoa)
        ket_qua.append(tho)
        if len(ket_qua) >= SO_THUOC_TOI_DA_HANG_LOAT:
            break
    return ket_qua

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

    TÌM KIẾM HÀNG LOẠT (quét mã QR trên đơn thuốc): nếu tham số q chứa
    NHIỀU tên thuốc phân tách bằng dấu phẩy/chấm phẩy/gạch đứng/xuống dòng
    (vd: /tim-kiem?q=Lidocain,Paracetamol,Amoxicillin — phần mềm bên thứ 3
    tự tạo URL này khi bệnh nhân quét QR trên đơn thuốc), trang sẽ tự động
    chuyển sang hiển thị kết quả riêng cho TỪNG thuốc một, thay vì gộp
    chung 1 từ khoá như tìm kiếm bình thường. Tìm 1 từ khoá như cũ (gõ tay
    trên ô tìm kiếm) không bị ảnh hưởng gì — vẫn hoạt động y như trước."""
    tu_khoa = request.args.get("q", "").strip()
    if not tu_khoa:
        return redirect(url_for("main.trang_chu"))

    danh_sach_thuoc = _tach_danh_sach_thuoc(tu_khoa)

    # --- Chế độ HÀNG LOẠT: q có từ 2 tên thuốc trở lên ---
    if len(danh_sach_thuoc) > 1:
        ket_qua_hang_loat = []
        for ten_thuoc in danh_sach_thuoc:
            phan_trang_dmt = tim_danh_muc_thuoc(ten_thuoc, per_page=SO_XEM_TRUOC_HANG_LOAT, page=1)
            phan_trang_ntbv = tim_nha_thuoc_bv(ten_thuoc, per_page=SO_XEM_TRUOC_HANG_LOAT, page=1)
            # Gộp sẵn 2 nguồn kèm nhãn + endpoint link — để template chỉ
            # cần lặp 1 danh sách duy nhất, không phải so khớp "in" tốn kém.
            items = (
                [{"thuoc": t, "nguon": "Danh mục thuốc", "endpoint": "dmt.xem_thuoc"} for t in phan_trang_dmt.items]
                + [{"thuoc": t, "nguon": "Nhà thuốc BV", "endpoint": "ntbv.xem_thuoc"} for t in phan_trang_ntbv.items]
            )
            tong = phan_trang_dmt.total + phan_trang_ntbv.total
            ket_qua_hang_loat.append({
                "ten_thuoc": ten_thuoc,
                "items": items,
                "tong": tong,
            })
        so_thuoc_tim_thay = sum(1 for k in ket_qua_hang_loat if k["tong"] > 0)
        return render_template(
            "tim_kiem_hang_loat.html",
            danh_sach_goc=tu_khoa,
            ket_qua_hang_loat=ket_qua_hang_loat,
            so_thuoc_tim_thay=so_thuoc_tim_thay,
        )

    # --- Chế độ bình thường: 1 từ khoá (giữ nguyên như cũ) ---
    SO_XEM_TRUOC = 8

    phan_trang_dmt = tim_danh_muc_thuoc(tu_khoa, per_page=SO_XEM_TRUOC, page=1)
    phan_trang_ntbv = tim_nha_thuoc_bv(tu_khoa, per_page=SO_XEM_TRUOC, page=1)

    return render_template(
        "tim_kiem_tong_hop.html",
        tu_khoa=tu_khoa,
        phan_trang_dmt=phan_trang_dmt,
        phan_trang_ntbv=phan_trang_ntbv,
    )


@bp.route("/ve-chung-toi")
def ve_chung_toi():
    du_lieu = {k: CaiDat.lay(k, VCT_MAC_DINH.get(k, "")) for k in VCT_KEYS}
    return render_template("ve_chung_toi.html", d=du_lieu)
