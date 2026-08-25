"""
Script migration: thêm cột hinh_anh vào bảng nhom_thuoc.

Chạy 1 lần duy nhất sau khi deploy code mới lên Render/Neon:
    python migrate_them_cot_hinh_anh.py

Script tự kiểm tra nếu cột đã tồn tại thì bỏ qua (idempotent).
"""

import os
from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Kiểm tra cột đã tồn tại chưa
        ket_qua = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'nhom_thuoc'
              AND column_name = 'hinh_anh'
        """))
        da_co = ket_qua.fetchone()

        if da_co:
            print("✅ Cột 'hinh_anh' đã tồn tại trong bảng 'nhom_thuoc' — bỏ qua.")
        else:
            conn.execute(text(
                "ALTER TABLE nhom_thuoc ADD COLUMN hinh_anh VARCHAR(500)"
            ))
            conn.commit()
            print("✅ Đã thêm cột 'hinh_anh' vào bảng 'nhom_thuoc' thành công.")
