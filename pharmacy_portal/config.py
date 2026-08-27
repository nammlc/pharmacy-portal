import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Bí mật dùng cho session, CSRF token... - khi deploy thật, đặt qua biến môi trường
    SECRET_KEY = os.environ.get("SECRET_KEY", "doi-chuoi-nay-truoc-khi-deploy-that")

    # --- Loại database ---
    # "sqlite" (mặc định - không cần cài server, chạy được ngay trên hosting free
    #           như Render free tier, dữ liệu lưu trong 1 file)
    # "mysql"  (dùng khi đã có server MySQL thật, đổi qua bằng biến môi trường DB_TYPE=mysql)
    DB_TYPE = os.environ.get("DB_TYPE", "sqlite")

    if DB_TYPE == "mysql":
        DB_USER = os.environ.get("DB_USER", "root")
        DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
        DB_HOST = os.environ.get("DB_HOST", "localhost")
        DB_PORT = os.environ.get("DB_PORT", "3306")
        DB_NAME = os.environ.get("DB_NAME", "pharmacy_portal")
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
    else:
        database_url = os.environ.get(
            "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'pharmacy_portal.db')}"
        )
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        SQLALCHEMY_DATABASE_URI = database_url

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Số kết quả tối đa hiển thị trên 1 trang tra cứu
    RESULTS_PER_PAGE = 20

    # --- Cloudinary (lưu ảnh thuốc / nhóm thuốc) ---
    # Đăng ký miễn phí tại https://cloudinary.com, lấy 3 giá trị này trong Dashboard
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    # Kích thước file tối đa cho phép upload (5 MB)
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # --- Tự động đăng xuất khi không hoạt động ---
    # Phiên đăng nhập admin hết hạn sau 15 phút không thao tác gì (không phải
    # 15 phút kể từ lúc đăng nhập - mỗi request sẽ tự làm mới lại đồng hồ này,
    # xem SESSION_REFRESH_EACH_REQUEST + session.permanent=True trong admin_auth.py).
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=15)
    SESSION_REFRESH_EACH_REQUEST = True
    # Cookie phiên chỉ gửi qua HTTPS khi chạy production (Render luôn có HTTPS).
    # Đặt False khi chạy local (http://127.0.0.1) để không bị mất cookie lúc test.
    SESSION_COOKIE_SECURE = os.environ.get("DB_TYPE") == "postgres"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
