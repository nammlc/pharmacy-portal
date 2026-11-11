"""
Hỏi đáp / bình luận CÔNG KHAI dưới thuốc và bài viết (cần admin duyệt mới hiện) — dùng chung: kiểm tra dữ liệu, chống spam.

Nguyên tắc
  - Chỉ nhận CHỮ THUẦN (không HTML); hiển thị luôn được escape. Không cho đường dẫn (chống quảng cáo / lừa đảo).
  - SĐT chỉ để Khoa Dược liên hệ, không hiển thị ra ngoài.
  - Giới hạn tốc độ theo thiết bị (mã băm, không phải IP thô) và theo SĐT; chặn gửi trùng nội dung.
"""
import re
import unicodedata
from datetime import datetime, timedelta

from flask import url_for

from app import db
from app.models.models import (YKien, DanhMucThuoc, NhaThuocBV, Thuoc, BaiViet, ThongTinBenhNhan)

TOI_DA_BINH_LUAN = 1000
TOI_DA_TIN_NHAN = 2000
TOI_THIEU_NOI_DUNG = 5
MOI_PHUT_TOI_THIEU_DIEN_FORM = 3          # giây: điền form nhanh hơn mức này gần như chắc là bot
GIOI_HAN_10_PHUT = 3                      # ý kiến công khai / thiết bị / 10 phút
GIOI_HAN_SDT_NGAY = 10                    # ý kiến công khai / SĐT / 24 giờ

# loai -> (model, cột tên, nhãn). Thêm trang mới có hỏi đáp: thêm 1 dòng ở đây + endpoint trong url_doi_tuong().
DOI_TUONG = {
    "dmt":  (DanhMucThuoc,     "ten_biet_duoc", "Danh mục thuốc"),
    "ntbv": (NhaThuocBV,       "ten_biet_duoc", "Nhà thuốc BV"),
    "tt":   (Thuoc,            "ten_thuoc",     "Thuốc tra cứu"),
    "bv":   (BaiViet,          "tieu_de",       "Bài viết"),
    "ttbn": (ThongTinBenhNhan, "tieu_de",       "Bài viết bệnh nhân"),
}
TRANG_THAI = {"cho_duyet": "Chờ duyệt", "da_duyet": "Đã duyệt", "tu_choi": "Từ chối", "spam": "Spam"}

_RE_DIEU_KHIEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]")
_RE_URL = re.compile(
    r"(https?:|www\.|t\.me/|zalo\.me/|bit\.ly|[a-z0-9-]+\.(com|vn|net|org|info|xyz|top|club|online|site|shop|link|me|io|co|app|biz)\b)",
    re.I)
_RE_URL_NOI_BO = re.compile(r"^/[A-Za-z0-9_\-./%?=&+~:,#]*$")


# ───────────────────────────── làm sạch / kiểm tra ─────────────────────────────
def lam_sach(s) -> str:
    """Chuẩn hoá chữ: bỏ ký tự điều khiển / ký tự đảo chiều, gọn khoảng trắng, tối đa 2 dòng trống liên tiếp."""
    s = unicodedata.normalize("NFC", str(s or ""))
    s = _RE_DIEU_KHIEN.sub("", s).replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(re.sub(r"[ \t]+", " ", d).strip() for d in s.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def chuan_hoa_sdt(s):
    """'0912 345 678' / '+84912345678' / '84912345678' → '0912345678'. Không hợp lệ → None."""
    so = re.sub(r"[\s.\-()]", "", str(s or ""))
    if so.startswith("+84"):
        so = "0" + so[3:]
    elif so.startswith("84") and len(so) in (11, 12):
        so = "0" + so[2:]
    return so if re.fullmatch(r"0\d{9,10}", so) else None


def che_sdt(sdt) -> str:
    """0912345678 → 091****678 (để admin liếc nhanh trong danh sách, không lộ cả số)."""
    return (sdt[:3] + "*" * max(0, len(sdt) - 6) + sdt[-3:]) if sdt and len(sdt) >= 7 else (sdt or "")


def co_duong_dan(s) -> bool:
    return bool(_RE_URL.search(s or ""))


def duong_dan_noi_bo(s):
    """Chỉ nhận đường dẫn nội bộ dạng /abc/def?x=1 (chống chèn link ngoài vào tin nhắn / thông báo)."""
    s = (s or "").strip()
    return s if s and len(s) <= 300 and _RE_URL_NOI_BO.match(s) and not s.startswith("//") else None


def kiem_tra_ten(ten_tho):
    ten = lam_sach(ten_tho).replace("\n", " ")
    if len(ten) < 2 or len(ten) > 60:
        return None, "Họ tên cần từ 2 đến 60 ký tự."
    if co_duong_dan(ten) or not re.search(r"[^\W\d_]", ten):
        return None, "Họ tên chưa hợp lệ."
    return ten, None


def kiem_tra_noi_dung(noi_dung_tho, toi_da, cho_phep_link=False):
    nd = lam_sach(noi_dung_tho)
    if len(nd) < TOI_THIEU_NOI_DUNG:
        return None, f"Nội dung quá ngắn (tối thiểu {TOI_THIEU_NOI_DUNG} ký tự)."
    if len(nd) > toi_da:
        return None, f"Nội dung quá dài (tối đa {toi_da} ký tự)."
    if not cho_phep_link and co_duong_dan(nd):
        return None, "Nội dung không được chứa đường dẫn (link)."
    return nd, None


# ───────────────────────────── đối tượng được góp ý ─────────────────────────────
def lay_doi_tuong(loai, doi_tuong_id):
    """Trả về bản ghi thuốc / bài viết nếu hợp lệ và đang hiển thị công khai, ngược lại None."""
    if loai not in DOI_TUONG:
        return None
    try:
        doi_tuong_id = int(doi_tuong_id)
    except (TypeError, ValueError):
        return None
    model = DOI_TUONG[loai][0]
    obj = db.session.get(model, doi_tuong_id)
    if obj is None:
        return None
    if loai == "bv" and getattr(obj, "trang_thai", None) != "da_xuat_ban":      # bài nháp / đã ẩn không nhận ý kiến
        return None
    return obj


def ten_doi_tuong(loai, obj) -> str:
    return str(getattr(obj, DOI_TUONG[loai][1], "") or "")[:255]


def url_doi_tuong(loai, obj):
    if loai == "dmt":
        return url_for("dmt.xem_thuoc", thuoc_id=obj.id)
    if loai == "ntbv":
        return url_for("ntbv.xem_thuoc", thuoc_id=obj.id)
    if loai == "tt":
        return url_for("ttth.chi_tiet", thuoc_id=obj.id)
    if loai == "bv":
        return url_for("bv.chi_tiet", slug=obj.slug)
    if loai == "ttbn":
        return url_for("ttbn.chi_tiet", bai_viet_id=obj.id)
    return "/"


# ───────────────────────────── chống spam ─────────────────────────────
def qua_gioi_han(khoa, sdt):
    """True nếu thiết bị / SĐT này đã gửi quá nhiều ý kiến công khai gần đây."""
    bay_gio = datetime.utcnow()
    n_thiet_bi = YKien.query.filter(YKien.khoa_khach == khoa,
                                    YKien.ngay_tao >= bay_gio - timedelta(minutes=10)).count()
    if n_thiet_bi >= GIOI_HAN_10_PHUT:
        return True
    n_sdt = YKien.query.filter(YKien.so_dien_thoai == sdt, YKien.ngay_tao >= bay_gio - timedelta(hours=24)).count()
    return n_sdt >= GIOI_HAN_SDT_NGAY


def trung_noi_dung(khoa, noi_dung):
    return YKien.query.filter(YKien.khoa_khach == khoa, YKien.noi_dung == noi_dung,
                              YKien.ngay_tao >= datetime.utcnow() - timedelta(hours=24)).first() is not None
