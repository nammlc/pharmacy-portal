"""
Ghi nhật ký truy cập (IP + cookie ẩn danh) và thao tác của admin.

Cách hoạt động: đăng ký 2 hook toàn cục (before_request / after_request) nên các
route cũ KHÔNG phải sửa gì.
  - Trang công khai: GET có tham số tìm kiếm (q, thuoc_a/thuoc_b) -> loai "tim_kiem".
  - Trang admin: POST thành công (server trả redirect) -> loai "sua_du_lieu";
    kèm sự kiện đăng nhập / đăng xuất.
  - Mỗi trình duyệt được gắn 1 cookie ngẫu nhiên "pp_vid" (không chứa thông tin cá nhân)
    để biết các lượt tìm kiếm có cùng 1 thiết bị, kể cả khi IP đổi (4G/Wi-Fi).

Việc ghi log dùng kết nối DB RIÊNG và bọc try/except: lỗi ghi log không bao giờ
làm hỏng request của người dùng.
"""
import random
import re
import uuid
from datetime import datetime, timedelta

from flask import g, request, current_app
from flask_login import current_user

from app import db
from app.models.models import NhatKy

COOKIE_TEN = "pp_vid"
COOKIE_THOI_HAN = 60 * 60 * 24 * 365          # 1 năm
_RE_COOKIE = re.compile(r"^[0-9a-f]{32}$")

NHAN_DOI_TUONG = {
    "admin_dmt": "Danh mục thuốc", "admin_ntbv": "Nhà thuốc BV",
    "admin_nhom_thuoc": "Nhóm thuốc", "admin_hoat_chat": "Hoạt chất",
    "admin_nhap_hang_loat": "Nhập hàng loạt", "admin_thuoc": "Thuốc tra cứu",
    "admin_tttt": "Thuốc tiêm truyền", "admin_thtk": "Tương hợp - Tương kỵ",
    "admin_ttt": "Tương tác thuốc", "admin_ttth": "Thông tin thuốc",
    "admin_bv": "Bài viết - Thông báo", "admin_dmbv": "Danh mục bài viết",
    "admin_ttbn": "Bài viết bệnh nhân", "admin_vct": "Về chúng tôi",
    "admin_nhat_ky": "Nhật ký truy cập", "admin_auth": "Tài khoản",
}

NHAN_TRANG_TIM_KIEM = {
    "main": "Tìm kiếm gộp", "dmt": "Danh mục thuốc", "ntbv": "Nhà thuốc BV",
    "tttt": "Thuốc tiêm truyền", "ttt": "Tương tác thuốc", "thtk": "Tương hợp - Tương kỵ",
    "ttth": "Thông tin thuốc", "bv": "Bài viết",
}

# Các trường form thường chứa "tên" của đối tượng đang sửa -> ghi lại cho dễ tra
_TRUONG_TEN = ("ten_thuoc", "ten_biet_duoc", "ten_nhom", "ten_hoat_chat", "tieu_de", "ten")


def lay_ip():
    """IP của người truy cập. Đằng sau proxy (Render...) cần ProxyFix - xem create_app()."""
    return (request.remote_addr or "")[:64]


def _cat(s, n):
    return (s or "")[:n] or None


def _hanh_dong_tu_ten_ham(ten_ham: str) -> str:
    t = (ten_ham or "").lower()
    if "xoa_tat_ca" in t:
        return "xoa_tat_ca"
    if "xoa_hang_loat" in t:
        return "xoa_hang_loat"
    if "xoa" in t:
        return "xoa"
    if "them" in t:
        return "them"
    if "sua" in t or "chinh_sua" in t:
        return "sua"
    if "luu" in t or "nhap" in t:
        return "nhap"
    return t[:30] or "khac"


def ghi(loai, **truong):
    """Ghi 1 dòng nhật ký bằng kết nối riêng (không đụng tới db.session của request)."""
    try:
        gia_tri = dict(
            thoi_gian=datetime.utcnow(),
            loai=loai,
            ip=lay_ip(),
            cookie_id=getattr(g, "vid", None),
            phuong_thuc=request.method,
            duong_dan=_cat(request.full_path.rstrip("?"), 500),
            trinh_duyet=_cat(request.headers.get("User-Agent"), 300),
        )
        gia_tri.update(truong)
        with db.engine.begin() as conn:
            conn.execute(NhatKy.__table__.insert().values(**gia_tri))
            # Thỉnh thoảng tự dọn log quá hạn (mặc định giữ 180 ngày)
            if random.random() < 0.002:
                ngay = int(current_app.config.get("NHAT_KY_GIU_NGAY", 180))
                if ngay > 0:
                    conn.execute(
                        NhatKy.__table__.delete().where(
                            NhatKy.__table__.c.thoi_gian < datetime.utcnow() - timedelta(days=ngay)
                        )
                    )
    except Exception as e:  # không bao giờ làm hỏng request
        try:
            current_app.logger.warning(f"Ghi nhật ký lỗi: {e}")
        except Exception:
            pass


def _nguoi_dung():
    try:
        if current_user.is_authenticated:
            return current_user.id, current_user.ten_dang_nhap
    except Exception:
        pass
    return None, None


def _ghi_tim_kiem(response):
    if request.method != "GET" or response.status_code != 200:
        return
    if (request.args.get("page", 1, type=int) or 1) > 1 or (request.args.get("trang", 1, type=int) or 1) > 1:
        return  # chỉ ghi lần tìm đầu, không ghi mỗi lần bấm sang trang
    tu_khoa = (request.args.get("q") or "").strip()
    if not tu_khoa:
        a, b = (request.args.get("thuoc_a") or "").strip(), (request.args.get("thuoc_b") or "").strip()
        tu_khoa = f"{a} + {b}" if (a or b) else ""
    if not tu_khoa:
        return

    nhan = NHAN_TRANG_TIM_KIEM.get((request.blueprint or ""), request.endpoint)
    mo_ta = None
    try:
        from app.routes.main import _tach_danh_sach_thuoc
        ds = _tach_danh_sach_thuoc(tu_khoa)
        if len(ds) > 1:
            mo_ta = f"Tìm hàng loạt {len(ds)} thuốc (đơn thuốc / mã QR)"
    except Exception:
        pass
    ghi("tim_kiem", tu_khoa=_cat(tu_khoa, 500), doi_tuong=nhan, mo_ta=mo_ta,
        ma_trang_thai=response.status_code)


def _ghi_admin(response):
    ep = request.endpoint or ""
    bp = request.blueprint or ""
    uid, ten = _nguoi_dung()

    if ep == "admin_auth.dang_nhap" and request.method == "POST":
        ten_nhap = _cat(request.form.get("ten_dang_nhap"), 100)
        thanh_cong = 300 <= response.status_code < 400
        ghi("dang_nhap" if thanh_cong else "dang_nhap_that_bai",
            ten_nguoi_dung=ten or ten_nhap, nguoi_dung_id=uid,
            mo_ta=None if thanh_cong else "Sai tên đăng nhập hoặc mật khẩu",
            ma_trang_thai=response.status_code)
        return

    if ep == "admin_auth.dang_xuat":
        ghi("dang_xuat", ten_nguoi_dung=getattr(g, "ten_truoc_dang_xuat", None),
            ma_trang_thai=response.status_code)
        return

    # Thao tác ghi dữ liệu thành công = POST trả về redirect
    if request.method != "POST" or not (300 <= response.status_code < 400):
        return
    # Các bước trung gian của "Nhập hàng loạt" (tải file/xem trước) chưa phải lưu dữ liệu
    dich = response.headers.get("Location", "")
    if bp == "admin_nhap_hang_loat" and "/admin/nhap-hang-loat" in dich:
        return

    ten_ham = ep.split(".", 1)[-1]
    hanh_dong = _hanh_dong_tu_ten_ham(ten_ham)
    doi_tuong_id = next((v for v in (request.view_args or {}).values() if isinstance(v, int)), None)
    doi_tuong_ten = next((_cat(request.form.get(k), 255) for k in _TRUONG_TEN if request.form.get(k)), None)
    mo_ta = None
    if hanh_dong in ("xoa_hang_loat",):
        mo_ta = f"Xoá {len(request.form.getlist('ids'))} mục đã chọn"
    elif hanh_dong == "xoa_tat_ca":
        mo_ta = "Xoá toàn bộ"
    loai = "tai_khoan" if bp == "admin_auth" else "sua_du_lieu"
    ghi(loai, nguoi_dung_id=uid, ten_nguoi_dung=ten, hanh_dong=hanh_dong,
        doi_tuong=NHAN_DOI_TUONG.get(bp, bp), doi_tuong_id=doi_tuong_id,
        doi_tuong_ten=doi_tuong_ten, mo_ta=mo_ta, ma_trang_thai=response.status_code)


def dang_ky(app):
    @app.before_request
    def _gan_cookie_an_danh():
        if request.endpoint == "static":
            return
        vid = request.cookies.get(COOKIE_TEN, "")
        if _RE_COOKIE.match(vid):
            g.vid, g.vid_moi = vid, False
        else:
            g.vid, g.vid_moi = uuid.uuid4().hex, True
        if request.endpoint == "admin_auth.dang_xuat":
            g.ten_truoc_dang_xuat = _nguoi_dung()[1]

    @app.after_request
    def _ghi_nhat_ky(response):
        try:
            if request.endpoint in (None, "static") or not hasattr(g, "vid"):
                return response
            if (request.blueprint or "").startswith("admin_"):
                _ghi_admin(response)
            else:
                _ghi_tim_kiem(response)
            if g.vid_moi:
                response.set_cookie(COOKIE_TEN, g.vid, max_age=COOKIE_THOI_HAN,
                                    httponly=True, samesite="Lax", secure=request.is_secure)
        except Exception as e:
            app.logger.warning(f"Hook nhật ký lỗi: {e}")
        return response
