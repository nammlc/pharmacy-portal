"""Tắt/đặt lại OTP của 1 tài khoản admin (khi mất điện thoại VÀ mất cả mã dự phòng).

Chạy trong Terminal của container trên Coolify (Application -> Terminal):
    python reset_otp.py <ten_dang_nhap>
Lần đăng nhập kế tiếp tài khoản đó sẽ phải quét QR mới (nếu ADMIN_2FA_BAT_BUOC=1).
Chỉ ai vào được máy chủ/container mới chạy được lệnh này.
"""
import sys

from app import create_app, db
from app.models.models import NguoiDung
from app.utils.otp import tat_otp

if len(sys.argv) != 2:
    print("Cách dùng: python reset_otp.py <ten_dang_nhap>")
    raise SystemExit(1)

app = create_app()
with app.app_context():
    nd = NguoiDung.query.filter_by(ten_dang_nhap=sys.argv[1].strip()).first()
    if nd is None:
        print(f"Không có tài khoản '{sys.argv[1]}'.")
        raise SystemExit(1)
    tat_otp(nd)
    print(f"Đã xoá OTP của '{nd.ten_dang_nhap}'. Lần đăng nhập tới sẽ phải thiết lập lại.")
