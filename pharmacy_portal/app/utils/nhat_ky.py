"""
Nhật ký hoạt động: ai (IP + cookie ẩn danh), lúc nào, làm gì - trên CẢ trang công khai và admin.

Đăng ký 2 hook toàn cục (before_request / after_request) + 1 tín hiệu template_rendered
nên các route cũ KHÔNG phải sửa gì. Các loại sự kiện (cột `loai`):
  truy_cap           : người dùng mở 1 trang công khai (trang chủ, danh sách, bài viết...)
  xem_thuoc          : người dùng mở trang chi tiết 1 thuốc (ghi tên + ID thuốc)
  tim_kiem           : người dùng tìm kiếm (ghi từ khoá)
  admin_truy_cap     : admin mở 1 trang quản trị (danh sách / form thêm / form sửa)
  sua_du_lieu        : admin thêm / sửa / xoá dữ liệu
  dang_nhap, dang_nhap_that_bai, dang_xuat, tai_khoan : sự kiện tài khoản

Giữ cho database không phình:
  - Không ghi: file tĩnh, /api/*, bot/crawler, trang 2+ của danh sách, F5 liên tục (dedup 10s).
  - Cột trình duyệt lưu bản rút gọn ("~📱|Android · SM-S918B|Chrome") thay vì cả User-Agent.
  - Tự xoá theo hạn: lượt xem 30 ngày, tìm kiếm 90 ngày, thao tác admin/tài khoản 365 ngày
    (đổi bằng biến môi trường) + trần tổng số dòng NHAT_KY_TOI_DA.

Ghi log dùng kết nối DB RIÊNG và bọc try/except: lỗi ghi log không làm hỏng request.
"""
import ipaddress
import random
import re
import time
import uuid
from datetime import datetime, timedelta

from flask import g, request, current_app, template_rendered
from flask_login import current_user
from sqlalchemy import select, func

from app import db
from app.models.models import NhatKy

COOKIE_TEN = "pp_vid"
COOKIE_DONG_Y = "pp_dongy"                      # lựa chọn của người dùng: "1" = đồng ý, "0" = từ chối
COOKIE_THOI_HAN = 60 * 60 * 24 * 365          # 1 năm
_RE_COOKIE = re.compile(r"^[0-9a-f]{32}$")
_RE_BOT = re.compile(r"bot|crawl|spider|slurp|uptime|monitor|health|preview|facebookexternalhit|curl|wget|python-requests|go-http-client", re.I)

LOAI_XEM = ("truy_cap", "xem_thuoc", "admin_truy_cap")   # loại "nhẹ", nhiều, giữ ngắn ngày

NHAN_DOI_TUONG = {
    "admin_dashboard": "Tổng quan",
    "admin_dmt": "Danh mục thuốc", "admin_ntbv": "Nhà thuốc BV",
    "admin_nhom_thuoc": "Nhóm thuốc", "admin_hoat_chat": "Hoạt chất",
    "admin_nhap_hang_loat": "Nhập hàng loạt", "admin_thuoc": "Thuốc tra cứu",
    "admin_tttt": "Thuốc tiêm truyền", "admin_thtk": "Tương hợp - Tương kỵ",
    "admin_ttt": "Tương tác thuốc", "admin_ttth": "Thông tin thuốc",
    "admin_bv": "Bài viết - Thông báo", "admin_dmbv": "Danh mục bài viết",
    "admin_ttbn": "Bài viết bệnh nhân", "admin_vct": "Về chúng tôi",
    "admin_nhat_ky": "Nhật ký truy cập", "admin_auth": "Tài khoản",
    "admin_ma_bao_mat": "Mã bảo mật", "admin_cong": "Cổng mã bảo mật",
}

NHAN_TRANG_CONG_KHAI = {
    "main.trang_chu": "Trang chủ", "main.ve_chung_toi": "Về chúng tôi", "main.tim_kiem": "Tìm kiếm gộp",
    "main": "Trang chính", "dmt": "Danh mục thuốc", "ntbv": "Nhà thuốc BV",
    "tttt": "Thuốc tiêm truyền", "ttt": "Tương tác thuốc", "thtk": "Tương hợp - Tương kỵ",
    "ttth": "Thông tin thuốc", "bv": "Bài viết - Thông báo", "ttbn": "Thông tin cho bệnh nhân",
}

# Các trường form thường chứa "tên" của đối tượng đang sửa -> ghi lại cho dễ tra
_TRUONG_TEN = ("ten_thuoc", "ten_biet_duoc", "ten_nhom", "ten_hoat_chat", "tieu_de", "ten")
# Các biến template có thể chứa đối tượng đang xem
_BIEN_DOI_TUONG = ("thuoc", "bai_viet", "nhom", "item", "hoat_chat")
_THUOC_ATTR = ("ten_biet_duoc", "ten_thuoc")
_TEN_ATTR = ("ten_biet_duoc", "ten_thuoc", "tieu_de", "ten_nhom", "ten_hoat_chat", "ten")


# ---------------------------------------------------------------- IP
def _ip_hop_le(gia_tri):
    try:
        ipaddress.ip_address(gia_tri)
        return True
    except ValueError:
        return False


def _ip_noi_bo(gia_tri):
    """IP nội bộ/proxy (10.x, 192.168.x, 127.x...) - không phải IP của người truy cập."""
    try:
        d = ipaddress.ip_address(gia_tri)
        return d.is_private or d.is_loopback or d.is_link_local or d.is_reserved
    except ValueError:
        return True


def lay_ip():
    """IP thật của người truy cập, khi chạy sau Cloudflare/Render.
    1) CF-Connecting-IP / True-Client-IP  2) IP công cộng đầu tiên trong X-Forwarded-For
    3) request.remote_addr (chạy local / không qua proxy)."""
    h = request.headers
    for ten in ("CF-Connecting-IP", "True-Client-IP"):
        v = (h.get(ten) or "").strip()
        if _ip_hop_le(v) and not _ip_noi_bo(v):
            return v[:64]
    for v in [x.strip() for x in (h.get("X-Forwarded-For") or "").split(",")]:
        if _ip_hop_le(v) and not _ip_noi_bo(v):
            return v[:64]
    return (request.remote_addr or "")[:64]


# ---------------------------------------------------------------- Thiết bị
def thiet_bi(ua):
    """User-Agent -> (biểu tượng, tên thiết bị dễ đọc, trình duyệt)."""
    if not ua:
        return "❔", "Không rõ", ""
    u = ua.lower()
    if _RE_BOT.search(u):
        return "🤖", "Bot / công cụ tự động", ""

    if "edg/" in u or "edga/" in u or "edgios/" in u:
        trinh = "Edge"
    elif "opr/" in u or "opera" in u:
        trinh = "Opera"
    elif "zalo" in u:
        trinh = "Zalo"
    elif "samsungbrowser" in u:
        trinh = "Samsung Internet"
    elif "firefox" in u or "fxios" in u:
        trinh = "Firefox"
    elif "chrome" in u or "crios" in u:
        trinh = "Chrome"
    elif "safari" in u:
        trinh = "Safari"
    else:
        trinh = "Khác"

    if "iphone" in u:
        return "📱", "iPhone", trinh
    if "ipad" in u:
        return "📱", "iPad", trinh
    if "android" in u:
        m = re.search(r"android [\d.]+; ([^;)]+)", ua, re.I)
        mau = m.group(1).strip() if m else ""
        ten = f"Android · {mau}" if (mau and mau.upper() not in ("K", "U") and len(mau) > 1) else "Android"
        return ("📱" if "mobile" in u else "📲"), ten, trinh
    if "windows" in u:
        return "💻", "Windows", trinh
    if "mac os" in u or "macintosh" in u:
        return "💻", "Mac", trinh
    if "cros" in u:
        return "💻", "ChromeOS", trinh
    if "linux" in u:
        return "💻", "Linux", trinh
    return "❔", "Không rõ", trinh


def nen_thiet_bi(ua):
    """Bản rút gọn để lưu DB (~30-60 byte thay vì cả User-Agent ~150-300 byte)."""
    icon, ten, trinh = thiet_bi(ua)
    return f"~{icon}|{ten}|{trinh}"[:120]


def doc_thiet_bi(da_luu):
    """Đọc giá trị cột trinh_duyet (kiểu rút gọn '~icon|ten|trinh' hoặc User-Agent thô của log cũ)."""
    if da_luu and da_luu.startswith("~"):
        phan = da_luu[1:].split("|")
        phan += [""] * (3 - len(phan))
        return phan[0], phan[1], phan[2]
    return thiet_bi(da_luu)


# ---------------------------------------------------------------- Ghi log
def _cat(s, n):
    return (s or "")[:n] or None


def _bao_loi(e):
    """Lỗi ghi log: in đầy đủ ra console/log server + nhớ lại để trang Nhật ký hiển thị cảnh báo."""
    try:
        current_app.logger.exception(f"Ghi nhật ký lỗi: {e}")
        current_app.extensions["nhat_ky_loi_cuoi"] = (
            f"{datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC — {type(e).__name__}: {e}"
        )
    except Exception:
        pass


def don_log_cu(conn):
    """Xoá log quá hạn theo từng nhóm + giữ tổng số dòng không vượt NHAT_KY_TOI_DA."""
    cfg = current_app.config
    T = NhatKy.__table__
    bay_gio = datetime.utcnow()
    han = {
        "xem": int(cfg.get("NHAT_KY_GIU_NGAY_TRUY_CAP", 30)),
        "tim": int(cfg.get("NHAT_KY_GIU_NGAY_TIM_KIEM", 90)),
        "khac": int(cfg.get("NHAT_KY_GIU_NGAY", 365)),
    }
    if han["xem"] > 0:
        conn.execute(T.delete().where(T.c.loai.in_(LOAI_XEM), T.c.thoi_gian < bay_gio - timedelta(days=han["xem"])))
    if han["tim"] > 0:
        conn.execute(T.delete().where(T.c.loai == "tim_kiem", T.c.thoi_gian < bay_gio - timedelta(days=han["tim"])))
    if han["khac"] > 0:
        conn.execute(T.delete().where(
            T.c.loai.notin_(LOAI_XEM + ("tim_kiem",)), T.c.thoi_gian < bay_gio - timedelta(days=han["khac"])))

    toi_da = int(cfg.get("NHAT_KY_TOI_DA", 300000))
    if toi_da > 0:
        tong = conn.execute(select(func.count()).select_from(T)).scalar() or 0
        if tong > toi_da:
            ids = [r[0] for r in conn.execute(
                select(T.c.id).where(T.c.loai.in_(LOAI_XEM)).order_by(T.c.thoi_gian.asc()).limit(tong - toi_da))]
            for i in range(0, len(ids), 500):
                conn.execute(T.delete().where(T.c.id.in_(ids[i:i + 500])))


def _chen(gia_tri):
    with db.engine.begin() as conn:
        conn.execute(NhatKy.__table__.insert().values(**gia_tri))
        if random.random() < 0.01:          # ~1% lượt ghi kèm dọn dẹp
            don_log_cu(conn)


def ghi(loai, **truong):
    """Ghi 1 dòng nhật ký bằng kết nối riêng (không đụng tới db.session của request).
    Nếu lỗi (vd: bảng chưa tồn tại) thì thử tạo bảng rồi ghi lại 1 lần; vẫn lỗi thì báo rõ."""
    try:
        gia_tri = dict(
            thoi_gian=datetime.utcnow(),
            loai=loai,
            ip=lay_ip(),
            cookie_id=getattr(g, "vid", None),
            phuong_thuc=request.method,
            duong_dan=_cat(request.full_path.rstrip("?"), 255),
            trinh_duyet=nen_thiet_bi(request.headers.get("User-Agent")),
        )
        gia_tri.update(truong)
    except Exception as e:
        _bao_loi(e)
        return
    try:
        _chen(gia_tri)
    except Exception:
        try:
            NhatKy.__table__.create(bind=db.engine, checkfirst=True)
            _chen(gia_tri)
        except Exception as e2:
            _bao_loi(e2)


_DEDUP = {}


def _trung_lap(loai, giay):
    """True nếu cùng IP + thiết bị + URL + loại vừa được ghi trong `giay` giây (F5 / bấm đúp)."""
    k = (lay_ip(), getattr(g, "vid", None), loai, request.full_path)
    bay_gio = time.monotonic()
    lan_cuoi = _DEDUP.get(k)
    if lan_cuoi is not None and bay_gio - lan_cuoi < giay:
        return True
    if len(_DEDUP) > 5000:
        for kk in [kk for kk, v in _DEDUP.items() if bay_gio - v > 60]:
            _DEDUP.pop(kk, None)
        if len(_DEDUP) > 5000:
            _DEDUP.clear()
    _DEDUP[k] = bay_gio
    return False


def _nguoi_dung():
    try:
        if current_user.is_authenticated:
            return current_user.id, current_user.ten_dang_nhap
    except Exception:
        pass
    return None, None


def _doi_tuong_dang_xem():
    """(đối tượng, tên, có phải thuốc) lấy từ biến template của trang vừa render."""
    ctx = getattr(g, "ngu_canh", None) or {}
    for khoa in _BIEN_DOI_TUONG:
        obj = ctx.get(khoa)
        if obj is None or not hasattr(obj, "id"):
            continue
        ten = next((getattr(obj, a) for a in _TEN_ATTR if getattr(obj, a, None)), None)
        la_thuoc = any(getattr(obj, a, None) for a in _THUOC_ATTR)
        return obj, _cat(ten, 255), la_thuoc
    return None, None, False


def _view_id():
    return next((v for v in (request.view_args or {}).values() if isinstance(v, int)), None)


def _la_trang_html(response):
    return response.status_code == 200 and response.mimetype == "text/html"


# ---------------------------------------------------------------- Trang công khai
def _ghi_cong_khai(response):
    if request.method != "GET" or not _la_trang_html(response):
        return
    if request.path.startswith("/api/"):
        return
    # Chỉ ghi trang đầu của danh sách, không ghi mỗi lần bấm sang trang
    if (request.args.get("page", 1, type=int) or 1) > 1 or (request.args.get("trang", 1, type=int) or 1) > 1:
        return

    bp = request.blueprint or ""
    ep = request.endpoint or ""

    # ---- tìm kiếm ----
    tu_khoa = (request.args.get("q") or "").strip()
    if not tu_khoa:
        a, b = (request.args.get("thuoc_a") or "").strip(), (request.args.get("thuoc_b") or "").strip()
        tu_khoa = f"{a} + {b}" if (a or b) else ""
    if tu_khoa:
        if _trung_lap("tim_kiem", 3):
            return
        mo_ta = None
        try:
            from app.routes.main import _tach_danh_sach_thuoc
            ds = _tach_danh_sach_thuoc(tu_khoa)
            if len(ds) > 1:
                mo_ta = f"Tìm hàng loạt {len(ds)} thuốc (đơn thuốc / mã QR)"
        except Exception:
            pass
        ghi("tim_kiem", tu_khoa=_cat(tu_khoa, 500),
            doi_tuong=NHAN_TRANG_CONG_KHAI.get(ep) or NHAN_TRANG_CONG_KHAI.get(bp, ep),
            mo_ta=mo_ta, ma_trang_thai=response.status_code)
        return

    # ---- xem chi tiết thuốc / mở trang ----
    if _trung_lap("truy_cap", 10):
        return
    obj, ten, la_thuoc = _doi_tuong_dang_xem()
    nhan = NHAN_TRANG_CONG_KHAI.get(ep) or NHAN_TRANG_CONG_KHAI.get(bp, ep)
    if obj is not None and la_thuoc and _view_id() is not None:
        ghi("xem_thuoc", doi_tuong=nhan, doi_tuong_id=_view_id(), doi_tuong_ten=ten,
            ma_trang_thai=response.status_code)
    else:
        ghi("truy_cap", doi_tuong=nhan, doi_tuong_id=_view_id() if obj is not None else None,
            doi_tuong_ten=ten, ma_trang_thai=response.status_code)


# ---------------------------------------------------------------- Admin
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


def _ghi_admin(response):
    ep = request.endpoint or ""
    bp = request.blueprint or ""
    uid, ten = _nguoi_dung()

    # Cổng mã bảo mật & đổi mã tự ghi log riêng (ma_bao_mat_dung/sai, doi_ma_bao_mat) -> không ghi trùng
    if bp == "admin_cong" or (bp == "admin_ma_bao_mat" and request.method == "POST"):
        return

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

    # ---- admin MỞ trang (danh sách / form thêm / form sửa) ----
    if request.method == "GET":
        if bp in ("admin_auth", "admin_nhat_ky") or uid is None or not _la_trang_html(response):
            return
        if (request.args.get("trang", 1, type=int) or 1) > 1:
            return
        if _trung_lap("admin_truy_cap", 10):
            return
        ten_ham = ep.split(".", 1)[-1]
        if "sua" in ten_ham:
            mo_ta = "Mở form sửa"
        elif "them" in ten_ham:
            mo_ta = "Mở form thêm"
        else:
            mo_ta = None
        _, ten_dt, _ = _doi_tuong_dang_xem()
        ghi("admin_truy_cap", nguoi_dung_id=uid, ten_nguoi_dung=ten,
            doi_tuong=NHAN_DOI_TUONG.get(bp, bp), doi_tuong_id=_view_id(), doi_tuong_ten=ten_dt,
            mo_ta=mo_ta, ma_trang_thai=response.status_code)
        return

    # ---- admin GHI dữ liệu thành công = POST trả về redirect ----
    if request.method != "POST" or not (300 <= response.status_code < 400):
        return
    # Các bước trung gian của "Nhập hàng loạt" (tải file/xem trước) chưa phải lưu dữ liệu
    dich = response.headers.get("Location", "")
    if bp == "admin_nhap_hang_loat" and "/admin/nhap-hang-loat" in dich:
        return

    ten_ham = ep.split(".", 1)[-1]
    hanh_dong = _hanh_dong_tu_ten_ham(ten_ham)
    doi_tuong_ten = next((_cat(request.form.get(k), 255) for k in _TRUONG_TEN if request.form.get(k)), None)
    mo_ta = None
    if hanh_dong == "xoa_hang_loat":
        mo_ta = f"Xoá {len(request.form.getlist('ids'))} mục đã chọn"
    elif hanh_dong == "xoa_tat_ca":
        mo_ta = "Xoá toàn bộ"
    loai = "tai_khoan" if bp == "admin_auth" else "sua_du_lieu"
    ghi(loai, nguoi_dung_id=uid, ten_nguoi_dung=ten, hanh_dong=hanh_dong,
        doi_tuong=NHAN_DOI_TUONG.get(bp, bp), doi_tuong_id=_view_id(),
        doi_tuong_ten=doi_tuong_ten, mo_ta=mo_ta, ma_trang_thai=response.status_code)


# ---------------------------------------------------------------- Đăng ký hook
def dang_ky(app):
    @app.context_processor
    def _ngu_canh_cookie():
        # Banner hỏi cookie hiện ở trang công khai cho tới khi người dùng chọn
        return {"chua_chon_cookie": request.cookies.get(COOKIE_DONG_Y) not in ("0", "1")}

    def _bat_ngu_canh(sender, template, context, **extra):
        # Lấy đối tượng đang được render (thuốc, bài viết...) để ghi TÊN vào log, khỏi query thêm
        try:
            g.ngu_canh = context
        except Exception:
            pass

    template_rendered.connect(_bat_ngu_canh, app)

    @app.before_request
    def _gan_cookie_an_danh():
        if request.endpoint == "static":
            return
        dong_y = request.cookies.get(COOKIE_DONG_Y)
        vid = request.cookies.get(COOKIE_TEN, "")
        g.xoa_vid = False
        if dong_y == "1":
            if _RE_COOKIE.match(vid):
                g.vid, g.vid_moi = vid, False
            else:
                g.vid, g.vid_moi = uuid.uuid4().hex, True
        else:
            # Chưa chọn hoặc từ chối: KHÔNG đặt cookie định danh; IP + hoạt động vẫn được ghi.
            g.vid, g.vid_moi = None, False
            g.xoa_vid = (dong_y == "0" and bool(vid))     # từ chối -> xoá cookie cũ nếu có
        if request.endpoint == "admin_auth.dang_xuat":
            g.ten_truoc_dang_xuat = _nguoi_dung()[1]

    @app.after_request
    def _ghi_nhat_ky(response):
        try:
            if request.endpoint in (None, "static") or not hasattr(g, "vid"):
                return response
            if not _RE_BOT.search(request.headers.get("User-Agent") or ""):
                if (request.blueprint or "").startswith("admin_"):
                    _ghi_admin(response)
                else:
                    _ghi_cong_khai(response)
            if g.vid_moi:
                response.set_cookie(COOKIE_TEN, g.vid, max_age=COOKIE_THOI_HAN,
                                    httponly=True, samesite="Lax", secure=request.is_secure)
            elif g.xoa_vid:
                response.delete_cookie(COOKIE_TEN)
        except Exception as e:
            app.logger.warning(f"Hook nhật ký lỗi: {e}")
        return response
