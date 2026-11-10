"""Ảnh nền (hero) trang chủ: đọc cài đặt từ bảng cai_dat và tính sẵn các giá trị để hiển thị.

Cài đặt (bảng cai_dat, khoá -> giá trị):
  hero_hinh_anh : URL ảnh Cloudinary (rỗng = dùng nền xanh gradient mặc định)
  hero_do_phu   : độ phủ lớp xanh navy lên ảnh, 55..95 (%)  - càng cao chữ càng dễ đọc, ảnh càng mờ
  hero_vi_tri   : tren | giua | duoi - phần nào của ảnh được giữ lại khi khung bị cắt bớt
  hero_alt      : mô tả ảnh (cho người khiếm thị và Google Images)

Vì sao độ phủ mặc định 66%: chữ trắng cần tương phản >= 4.5:1 với nền. Phủ navy #0b1f3a 66% thì chữ đạt
khoảng 5.3:1 ngay cả khi ảnh phía sau là trời trắng. Phủ dưới ~55% chữ nhỏ bắt đầu khó đọc trên ảnh sáng
nên thanh trượt trong admin không cho kéo thấp hơn.
"""
import re

from app.models.models import CaiDat
from app.utils.upload_anh import anh_theo_chieu_rong

K_ANH = "hero_hinh_anh"
K_DO_PHU = "hero_do_phu"
K_VI_TRI = "hero_vi_tri"
K_ALT = "hero_alt"
CAC_KHOA = (K_ANH, K_DO_PHU, K_VI_TRI, K_ALT)

DO_PHU_MIN, DO_PHU_MAX, DO_PHU_MAC_DINH = 55, 95, 66
# khoá -> (nhãn hiển thị, giá trị object-position)
VI_TRI = {"tren": ("Phần trên", "50% 15%"), "giua": ("Chính giữa", "50% 50%"), "duoi": ("Phần dưới", "50% 85%")}
VI_TRI_MAC_DINH = "giua"
ALT_MAC_DINH = "Toàn cảnh Bệnh viện Đa khoa Tâm Đức Cầu Quan"
CHIEU_RONG_SRCSET = (640, 960, 1440, 1920, 2400)

# Chỉ nhận https, không có dấu nháy/ngoặc/khoảng trắng -> không thể "thoát" khỏi thuộc tính HTML/CSS.
_RE_URL_AN_TOAN = re.compile(r"^https://[\w.~:/?#@!$&*+,;=%\-]+$")


def vi_tri_css():
    """{khoá: giá trị object-position} - đưa cho JS trong trang admin."""
    return {k: v[1] for k, v in VI_TRI.items()}


def url_an_toan(url):
    url = (url or "").strip()
    return url if _RE_URL_AN_TOAN.match(url) else ""


def kep_do_phu(gia_tri):
    try:
        so = int(float(gia_tri))
    except (TypeError, ValueError):
        so = DO_PHU_MAC_DINH
    return max(DO_PHU_MIN, min(DO_PHU_MAX, so))


def tinh_alpha(do_phu):
    """(trên, giữa, dưới): lớp phủ đậm dần từ trên xuống. 'Giữa' = đúng giá trị người dùng chọn,
    là chỗ đặt chữ. Công thức này PHẢI khớp với tinhAlpha() trong admin/hero/form.html (xem trước)."""
    giua = kep_do_phu(do_phu) / 100
    return round(max(giua - 0.06, 0.45), 2), round(giua, 2), round(min(giua + 0.12, 0.96), 2)


def doc_cai_dat():
    """Giá trị thô (đã kẹp về khoảng hợp lệ) để đổ vào form admin."""
    hang = {c.khoa: c.gia_tri for c in CaiDat.query.filter(CaiDat.khoa.in_(CAC_KHOA)).all()}
    vi_tri = hang.get(K_VI_TRI) or VI_TRI_MAC_DINH
    anh = url_an_toan(hang.get(K_ANH))
    return {
        "anh": anh,
        "anh_xem_truoc": anh_theo_chieu_rong(anh, 1440) if anh else "",
        "do_phu": kep_do_phu(hang.get(K_DO_PHU) or DO_PHU_MAC_DINH),
        "vi_tri": vi_tri if vi_tri in VI_TRI else VI_TRI_MAC_DINH,
        "alt": hang.get(K_ALT) or "",
    }


def lay_hero():
    """Dữ liệu cho trang chủ; None nếu chưa đặt ảnh (khi đó trang chủ giữ nền xanh như cũ)."""
    cd = doc_cai_dat()
    if not cd["anh"]:
        return None
    a1, a2, a3 = tinh_alpha(cd["do_phu"])
    srcset = ", ".join(f"{anh_theo_chieu_rong(cd['anh'], w)} {w}w" for w in CHIEU_RONG_SRCSET)
    return {
        "src": anh_theo_chieu_rong(cd["anh"], 1920),
        "srcset": srcset if srcset.count("/f_auto,") else "",
        "alt": cd["alt"] or ALT_MAC_DINH,
        "vi_tri": VI_TRI[cd["vi_tri"]][1],
        "a1": a1, "a2": a2, "a3": a3,
    }
