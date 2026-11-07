"""
Đếm người đang trực tuyến (hiện ở ô thống kê góc dưới trang quản trị).

Cách hoạt động
  - Trình duyệt (static/js/online.js) gửi tín hiệu "còn ở đây" ~20 giây/lần, CHỈ khi tab đang hiện và người dùng
    có thao tác gần đây (tab bỏ quên không tính). Khi đóng tab / rời trang, trình duyệt báo "tôi rời" (sendBeacon)
    → số liệu giảm gần như ngay, không phải đợi hết cửa sổ.
  - Server ghi/cập nhật 1 dòng trong bảng `dang_online` cho mỗi tài khoản admin hoặc mỗi thiết bị khách.
  - Đang online = có tín hiệu trong ONLINE_CUA_SO_GIAY giây gần nhất (mặc định 60).
  - Ô thống kê ở trang quản trị hỏi lại server mỗi 5 giây (không cần tải lại trang).

Phân loại
  - "admin": người đã đăng nhập (kể cả khi đang xem trang công khai). Đếm theo TÀI KHOẢN (mở 2 tab vẫn là 1).
  - "khach": người chưa đăng nhập. Khoá = cookie ẩn danh pp_vid (nếu người dùng đã đồng ý cookie), nếu không thì
    mã băm có muối của (IP + trình duyệt + ngày) — KHÔNG lưu IP thô. Nhiều máy cùng 1 IP + cùng loại trình duyệt
    (vd. wifi bệnh viện) có thể bị gộp thành 1 → con số khách là ước lượng, có thể thấp hơn thực tế.

Ghi dùng kết nối DB riêng, lỗi không làm hỏng request. Có giảm tần suất ghi để nhẹ database.
"""
import hashlib
import random
import time
from datetime import datetime, timedelta

from flask import current_app, g, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.models import DangOnline
from app.utils.nhat_ky import _RE_BOT, lay_ip

GIU_DONG_CU_GIO = 1              # dòng không còn tín hiệu quá 1 giờ thì xoá
_GHI_LAN_CUOI = {}               # khoá -> thời điểm (monotonic) đã ghi, để không ghi quá dày khi nhiều tab / bấm liên tục
_GIAN_CACH_GHI = 10              # giây
ROI_GIU_GIAY = 6                 # báo "rời trang": còn được tính thêm ngần này giây, nếu trang kế tiếp báo lại thì không bị tụt


def la_bot():
    return bool(_RE_BOT.search(request.headers.get("User-Agent") or ""))


def khoa_khach():
    """Khoá ẩn danh của 1 khách (xem mô tả đầu file)."""
    vid = getattr(g, "vid", None)
    if vid:
        return f"v:{vid}"[:64]
    muoi = current_app.config.get("SECRET_KEY", "")
    tho = f"{muoi}|{datetime.utcnow():%Y-%m-%d}|{lay_ip()}|{request.headers.get('User-Agent', '')}"
    return "k:" + hashlib.sha256(tho.encode("utf-8")).hexdigest()[:40]


def nhan_dien(khu):
    """Ai đang gửi tín hiệu? Trả (loai, khoa, ten); None nếu là bot; 'het_phien' nếu là tab quản trị mà phiên đã hết hạn."""
    from flask_login import current_user
    if la_bot():
        return None
    if current_user.is_authenticated:
        ten = getattr(current_user, "ho_ten", None) or current_user.ten_dang_nhap
        return ("admin", f"a:{current_user.id}", ten)
    if khu == "admin":
        return "het_phien"
    return ("khach", khoa_khach(), None)


def danh_dau_roi(khoa):
    """Người dùng đóng tab / rời trang: rút ngắn thời gian còn được tính xuống ROI_GIU_GIAY giây.
    (Không xoá hẳn: chuyển giữa 2 trang của site sẽ có tín hiệu mới ngay sau đó, tránh số nhảy xuống rồi lên.)"""
    _GHI_LAN_CUOI.pop(khoa, None)                  # để tín hiệu kế tiếp của khoá này luôn được ghi, không bị giảm tần suất
    cua_so = int(current_app.config.get("ONLINE_CUA_SO_GIAY", 60))
    T = DangOnline.__table__
    try:
        with db.engine.begin() as conn:
            conn.execute(T.update().where(T.c.khoa == khoa).values(
                lan_cuoi=datetime.utcnow() - timedelta(seconds=max(0, cua_so - ROI_GIU_GIAY))))
    except Exception as e:                          # noqa: BLE001
        current_app.logger.warning(f"Không ghi được tín hiệu rời trang: {e}")


def ghi_hien_dien(loai, khoa, ten=None):
    """Ghi / làm mới tín hiệu online. Trả True nếu đã ghi (hoặc vừa ghi gần đây), False nếu lỗi."""
    bay_gio = time.monotonic()
    lan_cuoi = _GHI_LAN_CUOI.get(khoa)
    if lan_cuoi is not None and bay_gio - lan_cuoi < _GIAN_CACH_GHI:
        return True
    if len(_GHI_LAN_CUOI) > 5000:
        for k in [k for k, v in _GHI_LAN_CUOI.items() if bay_gio - v > 300]:
            _GHI_LAN_CUOI.pop(k, None)
        if len(_GHI_LAN_CUOI) > 5000:
            _GHI_LAN_CUOI.clear()

    T = DangOnline.__table__
    gia_tri = dict(loai=loai, ten=(ten or None) and ten[:150], lan_cuoi=datetime.utcnow())
    try:
        with db.engine.begin() as conn:
            capnhat = conn.execute(T.update().where(T.c.khoa == khoa).values(**gia_tri))
            if capnhat.rowcount == 0:
                try:
                    with conn.begin_nested():            # 2 tín hiệu cùng lúc: bên thua cuộc đua bị trùng khoá → bỏ qua
                        conn.execute(T.insert().values(khoa=khoa, **gia_tri))
                except IntegrityError:
                    pass
            if random.random() < 0.02:                    # ~2% lượt ghi kèm dọn dòng cũ
                conn.execute(T.delete().where(T.c.lan_cuoi < datetime.utcnow() - timedelta(hours=GIU_DONG_CU_GIO)))
    except Exception as e:                                # noqa: BLE001
        current_app.logger.warning(f"Không ghi được tín hiệu online: {e}")
        return False
    _GHI_LAN_CUOI[khoa] = bay_gio
    return True


def dem():
    """{'admin': n, 'khach': m, 'ten_admin': [...], 'cua_so': giây}. Lỗi DB → ném ngoại lệ cho nơi gọi xử lý."""
    cua_so = int(current_app.config.get("ONLINE_CUA_SO_GIAY", 60))
    moc = datetime.utcnow() - timedelta(seconds=cua_so)
    T = DangOnline.__table__
    with db.engine.connect() as conn:
        dong = conn.execute(select(T.c.loai, T.c.ten).where(T.c.lan_cuoi >= moc)).all()
    ten_admin = sorted({(t or "—") for loai, t in dong if loai == "admin"}, key=str.lower)
    return {
        "admin": sum(1 for loai, _ in dong if loai == "admin"),
        "khach": sum(1 for loai, _ in dong if loai == "khach"),
        "ten_admin": ten_admin,
        "cua_so": cua_so,
    }
