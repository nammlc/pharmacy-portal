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
        # File SQLite nằm trong thư mục instance/ - tự tạo khi chạy lần đầu
        SQLALCHEMY_DATABASE_URI = os.environ.get(
            "DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'pharmacy_portal.db')}"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Số kết quả tối đa hiển thị trên 1 trang tra cứu
    RESULTS_PER_PAGE = 20
