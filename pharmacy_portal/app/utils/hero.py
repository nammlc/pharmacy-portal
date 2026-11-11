"""Ảnh nền (hero) trang chủ: đọc cài đặt từ bảng cai_dat và tính sẵn các giá trị để hiển thị.

Có 2 ảnh riêng: ảnh MÁY TÍNH (PC) và ảnh ĐIỆN THOẠI. Ảnh luôn được KÉO GIÃN cho vừa khít khung hero (object-fit: fill):
KHÔNG cắt ảnh, và kích thước trang KHÔNG phụ thuộc ảnh (ảnh chỉ là lớp nền tuyệt đối). Ảnh sai tỉ lệ sẽ bị méo / mờ chứ
không làm trang to nhỏ khác đi; admin tự chọn ảnh có tỉ lệ hợp với từng loại màn hình.

Cài đặt (bảng cai_dat, khoá -> giá trị):
  hero_hinh_anh        : URL ảnh Cloudinary cho MÁY TÍNH (rỗng = không có)
  hero_hinh_anh_mobile : URL ảnh Cloudinary cho ĐIỆN THOẠI (rỗng = không có)
  hero_do_phu          : độ phủ lớp xanh navy lên ảnh, 55..95 (%)  - càng cao chữ càng dễ đọc, ảnh càng mờ
  hero_alt             : mô tả ảnh (cho người khiếm thị và Google Images)
Thiếu 1 trong 2 ảnh thì dùng ảnh còn lại cho cả hai loại màn hình; thiếu cả hai thì trang chủ giữ nền xanh gradient mặc định.
(Khoá cũ hero_vi_tri không còn dùng vì không còn cắt ảnh; nếu còn trong DB thì bỏ qua.)

Vì sao độ phủ mặc định 66%: chữ trắng cần tương phản >= 4.5:1 với nền. Phủ navy #0b1f3a 66% thì chữ đạt
khoảng 5.3:1 ngay cả khi ảnh phía sau là trời trắng. Phủ dưới ~55% chữ nhỏ bắt đầu khó đọc trên ảnh sáng
nên thanh trượt trong admin không cho kéo thấp hơn.
"""
import re

from app.models.models import CaiDat
from app.utils.upload_anh import anh_theo_chieu_rong

K_ANH = "hero_hinh_anh"                 # ảnh máy tính (giữ khoá cũ để không mất ảnh đã tải)
K_ANH_MOBILE = "hero_hinh_anh_mobile"   # ảnh điện thoại
K_DO_PHU = "hero_do_phu"
K_ALT = "hero_alt"
CAC_KHOA = (K_ANH, K_ANH_MOBILE, K_DO_PHU, K_ALT)

DO_PHU_MIN, DO_PHU_MAX, DO_PHU_MAC_DINH = 55, 95, 66
ALT_MAC_DINH = "Toàn cảnh Bệnh viện Đa khoa Tâm Đức Cầu Quan"
CHIEU_RONG_PC = (640, 960, 1440, 1920, 2400)
CHIEU_RONG_MOBILE = (480, 720, 960, 1200, 1600)
MOBILE_MAX_WIDTH = 700                  # PHẢI khớp @media (max-width: 700px) của .hero--anh trong style.css

# Chỉ nhận https, không có dấu nháy/ngoặc/khoảng trắng -> không thể "thoát" khỏi thuộc tính HTML/CSS.
_RE_URL_AN_TOAN = re.compile(r"^https://[\w.~:/?#@!$&*+,;=%\-]+$")


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
    pc = url_an_toan(hang.get(K_ANH))
    mb = url_an_toan(hang.get(K_ANH_MOBILE))
    return {
        "anh": pc,
        "anh_xem_truoc": anh_theo_chieu_rong(pc, 1440) if pc else "",
        "anh_mobile": mb,
        "anh_mobile_xem_truoc": anh_theo_chieu_rong(mb, 960) if mb else "",
        "do_phu": kep_do_phu(hang.get(K_DO_PHU) or DO_PHU_MAC_DINH),
        "alt": hang.get(K_ALT) or "",
    }


def _srcset(url, chieu_rong):
    s = ", ".join(f"{anh_theo_chieu_rong(url, w)} {w}w" for w in chieu_rong)
    return s if s.count("/f_auto,") else ""   # không phải ảnh Cloudinary -> không có bản thu nhỏ


def lay_hero():
    """Dữ liệu cho trang chủ; None nếu chưa đặt ảnh nào (khi đó trang chủ giữ nền xanh như cũ)."""
    cd = doc_cai_dat()
    pc, mb = cd["anh"], cd["anh_mobile"]
    if not pc and not mb:
        return None
    a1, a2, a3 = tinh_alpha(cd["do_phu"])
    anh_chinh = pc or mb                                   # thiếu ảnh máy tính -> dùng ảnh điện thoại cho tất cả
    hero = {
        "src": anh_theo_chieu_rong(anh_chinh, 1920),
        "srcset": _srcset(anh_chinh, CHIEU_RONG_PC if pc else CHIEU_RONG_MOBILE),
        "mobile_src": "", "mobile_srcset": "",
        "mobile_max": MOBILE_MAX_WIDTH,
        "alt": cd["alt"] or ALT_MAC_DINH,
        "a1": a1, "a2": a2, "a3": a3,
    }
    if pc and mb:                                          # có cả 2 ảnh -> điện thoại dùng ảnh riêng
        hero["mobile_src"] = anh_theo_chieu_rong(mb, 1200)
        hero["mobile_srcset"] = _srcset(mb, CHIEU_RONG_MOBILE)
    return hero
