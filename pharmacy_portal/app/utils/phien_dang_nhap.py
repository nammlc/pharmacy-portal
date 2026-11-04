"""Tự đăng xuất admin sau một khoảng thời gian KHÔNG hoạt động (mặc định 15 phút).

Cách làm: lưu mốc thời gian hoạt động gần nhất ("_last_active") ngay trong session cookie
đã ký của Flask (người ngoài không sửa được). Mỗi request của người đang đăng nhập:
  - nếu cách mốc đó > giới hạn  -> đăng xuất;
  - nếu chưa quá hạn            -> làm mới mốc (trượt cửa sổ 15 phút).
Chỉ tác động tới session ĐÃ đăng nhập; khách xem trang công khai và form (CSRF) không bị ảnh hưởng.
"""
import time

from flask import flash, redirect, request, session, url_for
from flask_login import logout_user

KHOA = "_last_active"
# Các endpoint KHÔNG bị chuyển hướng khi hết phiên (tự xử lý riêng)
_KHONG_CHUYEN_HUONG = ("admin_auth.keep_alive", "admin_auth.dang_nhap")


def danh_dau_hoat_dong():
    """Gọi ngay sau login_user() để bắt đầu tính giờ."""
    session[KHOA] = time.time()


def dang_ky(app):
    @app.before_request
    def _het_phien_khi_khong_hoat_dong():
        if request.endpoint == "static" or "_user_id" not in session:
            return None

        gioi_han = app.config["ADMIN_IDLE_TIMEOUT_MINUTES"] * 60
        bay_gio = time.time()
        lan_cuoi = session.get(KHOA)

        # Thiếu mốc (phiên cũ trước khi có tính năng này) hoặc quá hạn -> đăng xuất
        if not isinstance(lan_cuoi, (int, float)) or bay_gio - lan_cuoi > gioi_han:
            logout_user()
            session.pop(KHOA, None)
            if request.path.startswith("/admin"):
                flash(f"Phiên đăng nhập đã hết hạn do không hoạt động quá "
                      f"{app.config['ADMIN_IDLE_TIMEOUT_MINUTES']} phút. Vui lòng đăng nhập lại.", "warning")
                if request.endpoint not in _KHONG_CHUYEN_HUONG:
                    return redirect(url_for("admin_auth.dang_nhap"))
            return None

        session[KHOA] = bay_gio
        return None
