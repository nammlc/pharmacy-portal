from flask import Blueprint, render_template
from app.models.models import CaiDat

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
def trang_chu():
    return render_template("trang_chu.html")


@bp.route("/ve-chung-toi")
def ve_chung_toi():
    du_lieu = {k: CaiDat.lay(k, VCT_MAC_DINH.get(k, "")) for k in VCT_KEYS}
    return render_template("ve_chung_toi.html", d=du_lieu)
