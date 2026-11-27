"""Tạo bảng tuong_tac_hoat_chat (nếu chưa có) bằng SQLAlchemy - tương đương them_bang_tuong_tac_hoat_chat.sql.

Dùng khi không tiện chạy SQL thủ công:  python tao_bang_tuong_tac_hoat_chat.py
An toàn chạy lại nhiều lần: db.create_all() chỉ tạo bảng CHƯA tồn tại, không đụng dữ liệu cũ.
"""
from app import create_app, db
from app.models.models import TuongTacHoatChat

app = create_app()
with app.app_context():
    db.create_all()
    print("OK - bảng", TuongTacHoatChat.__tablename__, "đã sẵn sàng.")
