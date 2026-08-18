"""
Script nạp dữ liệu MẪU để kiểm tra giao diện & luồng tra cứu hoạt động đúng.

QUAN TRỌNG: Đây KHÔNG phải dữ liệu dược lý thật. Tên thuốc, thông tin tương
tác/tương kỵ dưới đây là placeholder để test, KHÔNG được dùng cho mục đích
lâm sàng. Trước khi đưa vào sử dụng thật, xoá toàn bộ dữ liệu mẫu này và
nhập dữ liệu đã được dược sĩ lâm sàng kiểm duyệt.

Chạy: python seed_demo_data.py
"""

from app import create_app, db
from app.models.models import (
    Thuoc, ThuocTiemTruyen, TuongHopTuongKy, TuongTacThuoc,
    ThongTinThuoc, ThongTinBenhNhan, NguoiDung
)

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    # --- Danh mục thuốc mẫu ---
    thuoc_a = Thuoc(
        ten_thuoc="[MẪU] Thuốc A", hoat_chat="[MẪU] Hoạt chất A",
        ham_luong="500mg", dang_bao_che="Viên nén",
        nhom_thuoc="[MẪU] Nhóm dược lý", nha_san_xuat="[MẪU] Nhà sản xuất"
    )
    thuoc_b = Thuoc(
        ten_thuoc="[MẪU] Thuốc B (dạng tiêm)", hoat_chat="[MẪU] Hoạt chất B",
        ham_luong="10mg/mL", dang_bao_che="Dung dịch tiêm",
        nhom_thuoc="[MẪU] Nhóm dược lý", nha_san_xuat="[MẪU] Nhà sản xuất"
    )
    db.session.add_all([thuoc_a, thuoc_b])
    db.session.commit()

    # --- Thông tin tiêm truyền mẫu ---
    db.session.add(ThuocTiemTruyen(
        thuoc_id=thuoc_b.id,
        dung_moi_pha_loang="[MẪU] NaCl 0.9% hoặc Glucose 5%",
        toc_do_truyen="[MẪU] Truyền chậm trong 30-60 phút",
        do_on_dinh="[MẪU] 24 giờ ở nhiệt độ phòng",
        canh_bao="[MẪU] Đây là dữ liệu placeholder, cần dược sĩ xác nhận trước khi dùng."
    ))

    # --- Tương hợp/tương kỵ mẫu ---
    db.session.add(TuongHopTuongKy(
        thuoc_a_id=thuoc_a.id, thuoc_b_id=thuoc_b.id,
        trang_thai="tuong_ky",
        mo_ta="[MẪU] Ví dụ minh hoạ hiển thị badge trạng thái tương kỵ."
    ))

    # --- Tương tác thuốc mẫu ---
    db.session.add(TuongTacThuoc(
        thuoc_a_id=thuoc_a.id, thuoc_b_id=thuoc_b.id,
        muc_do="trung_binh",
        hau_qua_lam_sang="[MẪU] Ví dụ minh hoạ hiển thị badge mức độ.",
        xu_tri="[MẪU] Theo dõi lâm sàng, tham khảo dược sĩ."
    ))

    # --- Thông tin thuốc chi tiết mẫu ---
    db.session.add(ThongTinThuoc(
        thuoc_id=thuoc_a.id,
        chi_dinh="[MẪU] Nội dung minh hoạ",
        chong_chi_dinh="[MẪU] Nội dung minh hoạ",
        lieu_dung_nguoi_lon="[MẪU] Nội dung minh hoạ",
        tac_dung_phu="[MẪU] Nội dung minh hoạ"
    ))

    # --- Bài viết cho bệnh nhân mẫu ---
    db.session.add(ThongTinBenhNhan(
        tieu_de="[MẪU] Hướng dẫn dùng thuốc tại nhà",
        danh_muc="Dùng thuốc tại nhà",
        noi_dung="[MẪU] Đây là nội dung minh hoạ để kiểm tra hiển thị trang bài viết."
    ))

    # --- Tài khoản admin DEMO để test đăng nhập ---
    # ĐỔI MẬT KHẨU NÀY hoặc dùng create_admin.py để tạo tài khoản thật trước khi dùng thật.
    demo_admin = NguoiDung(ten_dang_nhap="admin", ho_ten="Admin Demo", vai_tro="quan_tri")
    demo_admin.set_password("DoiMatKhauNay123")
    db.session.add(demo_admin)

    db.session.commit()
    print("Đã nạp dữ liệu MẪU thành công. Nhớ xoá trước khi dùng thật (xem docstring đầu file).")
    print("Tài khoản admin demo: admin / DoiMatKhauNay123 — ĐỔI NGAY trước khi dùng thật.")
