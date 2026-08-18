"""
Tạo tài khoản admin đầu tiên để đăng nhập trang quản trị.

Chạy: python create_admin.py
"""
import getpass
from app import create_app, db
from app.models.models import NguoiDung

app = create_app()

with app.app_context():
    db.create_all()  # đảm bảo bảng đã tồn tại (không xoá dữ liệu cũ)

    print("=== Tạo tài khoản quản trị ===")
    ten_dang_nhap = input("Tên đăng nhập: ").strip()

    if NguoiDung.query.filter_by(ten_dang_nhap=ten_dang_nhap).first():
        print(f"Tài khoản '{ten_dang_nhap}' đã tồn tại. Dừng lại.")
        raise SystemExit(1)

    ho_ten = input("Họ tên hiển thị (có thể để trống): ").strip()
    mat_khau = getpass.getpass("Mật khẩu (tối thiểu 8 ký tự): ")

    if len(mat_khau) < 8:
        print("Mật khẩu quá ngắn (cần tối thiểu 8 ký tự). Dừng lại.")
        raise SystemExit(1)

    mat_khau_xac_nhan = getpass.getpass("Nhập lại mật khẩu: ")
    if mat_khau != mat_khau_xac_nhan:
        print("Mật khẩu xác nhận không khớp. Dừng lại.")
        raise SystemExit(1)

    nguoi_dung = NguoiDung(ten_dang_nhap=ten_dang_nhap, ho_ten=ho_ten or None, vai_tro="quan_tri")
    nguoi_dung.set_password(mat_khau)
    db.session.add(nguoi_dung)
    db.session.commit()

    print(f"Đã tạo tài khoản '{ten_dang_nhap}'. Đăng nhập tại /admin/dang-nhap")
