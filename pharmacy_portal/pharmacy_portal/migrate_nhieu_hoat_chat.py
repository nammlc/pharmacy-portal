"""
Script migration: chuyển quan hệ "1 biệt dược - 1 hoạt chất" (cột
hoat_chat_id) sang "1 biệt dược - NHIỀU hoạt chất" (bảng trung gian
danh_muc_thuoc_hoat_chat / nha_thuoc_bv_hoat_chat), để hỗ trợ thuốc
phối hợp (vd: Panadol Extra = Paracetamol + Cafein).

Chạy 1 lần duy nhất sau khi deploy code mới lên Render/Neon:
    python migrate_nhieu_hoat_chat.py

Script AN TOÀN - không xoá cột hoat_chat_id cũ, không mất dữ liệu:
- Tạo 2 bảng trung gian mới nếu chưa có (không đụng bảng cũ).
- Với các thuốc đã có hoat_chat_id (nhập từ trước), tự động thêm
  đúng hoạt chất đó vào bảng trung gian mới, để không bị "mất" hoạt
  chất đã gán trước đây.
- Chạy lại nhiều lần không sao (idempotent) - không tạo dữ liệu trùng.
"""

from app import create_app, db
from app.models.models import DanhMucThuoc, NhaThuocBV, HoatChat

app = create_app()

with app.app_context():
    # 1) Tạo các bảng còn thiếu (bao gồm 2 bảng trung gian mới khai báo
    # trong models.py). db.create_all() chỉ tạo bảng CHƯA tồn tại,
    # không đụng tới bảng/dữ liệu đã có.
    db.create_all()
    print("✅ Đã đảm bảo đủ bảng (bao gồm 2 bảng trung gian nhiều-nhiều).")

    # 2) Chuyển dữ liệu cũ: với thuốc đã có hoat_chat_id (1 hoạt chất),
    # thêm hoạt chất đó vào hoat_chat_list nếu chưa có.
    so_chuyen_dmt = 0
    for thuoc in DanhMucThuoc.query.filter(DanhMucThuoc.hoat_chat_id.isnot(None)).all():
        hc = db.session.get(HoatChat, thuoc.hoat_chat_id)
        if hc and hc not in thuoc.hoat_chat_list:
            thuoc.hoat_chat_list.append(hc)
            so_chuyen_dmt += 1

    so_chuyen_ntbv = 0
    for thuoc in NhaThuocBV.query.filter(NhaThuocBV.hoat_chat_id.isnot(None)).all():
        hc = db.session.get(HoatChat, thuoc.hoat_chat_id)
        if hc and hc not in thuoc.hoat_chat_list:
            thuoc.hoat_chat_list.append(hc)
            so_chuyen_ntbv += 1

    db.session.commit()
    print(f"✅ Danh mục thuốc: đã chuyển {so_chuyen_dmt} thuốc sang quan hệ nhiều-nhiều.")
    print(f"✅ Nhà thuốc BV: đã chuyển {so_chuyen_ntbv} thuốc sang quan hệ nhiều-nhiều.")
    print("Xong. Giờ có thể vào trang admin để thêm/sửa nhiều hoạt chất cho 1 biệt dược.")
