import os

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

    # --- Connection pool — fix lỗi "connection closed" sau thời gian không dùng ---
    # Neon (và nhiều PaaS) đóng kết nối idle sau ~5 phút.
    # pool_pre_ping=True: kiểm tra connection còn sống trước mỗi request.
    # pool_recycle=300: tái tạo connection sau 300 giây (trước khi Neon đóng).
    # pool_size + max_overflow: giới hạn số kết nối đồng thời (phù hợp free tier).
    # pool_pre_ping + recycle: fix lỗi "connection closed" sau idle
    # connect_args keepalives chỉ dùng cho PostgreSQL (psycopg2), không dùng cho SQLite/MySQL
    if DB_TYPE == "mysql":
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_size": 3,
            "max_overflow": 5,
            "pool_timeout": 20,
        }
    elif "postgresql" in (
        os.environ.get("DATABASE_URL", "")
    ):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 280,
            "pool_size": 3,
            "max_overflow": 5,
            "pool_timeout": 20,
            "connect_args": {
                "connect_timeout": 10,
                "keepalives": 1,
                "keepalives_idle": 60,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
        }
    else:
        # SQLite: không cần pool phức tạp
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
        }

    # Số kết quả tối đa hiển thị trên 1 trang tra cứu
    RESULTS_PER_PAGE = 20

    # --- Cloudinary (lưu ảnh thuốc / nhóm thuốc) ---
    # Đăng ký miễn phí tại https://cloudinary.com, lấy 3 giá trị này trong Dashboard
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    # Kích thước file tối đa cho phép upload.
    # Ảnh đã được nén ở trình duyệt trước khi gửi lên (xem app/static/js/nen_anh.js)
    # nên thường chỉ còn vài trăm KB, nhưng màn hình "Nhập hàng loạt" có thể gửi
    # nhiều ảnh cùng lúc (nhiều thuốc trong 1 lần lưu) nên để dư ra 40 MB cho cả request.
    MAX_CONTENT_LENGTH = 40 * 1024 * 1024
