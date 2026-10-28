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

    # --- Phiên đăng nhập admin: tự đăng xuất sau N phút KHÔNG hoạt động (mặc định 15) ---
    # Tính từ request gần nhất của admin (trình duyệt tự gửi tín hiệu "còn đang làm việc"
    # mỗi vài phút khi có thao tác chuột/bàn phím, nên đang soạn bài dài không bị đá ra).
    ADMIN_IDLE_TIMEOUT_MINUTES = max(1, int(os.environ.get("ADMIN_IDLE_TIMEOUT_MINUTES", "15")))

    # --- Gửi email qua Resend (chức năng quên mật khẩu) ---
    # RESEND_API_KEY : tạo tại https://resend.com/api-keys
    # MAIL_FROM      : địa chỉ gửi. Thử nghiệm dùng "Khoa Dược <onboarding@resend.dev>"
    #                  (chỉ gửi được tới email chủ tài khoản Resend). Muốn gửi cho
    #                  email khác phải verify domain riêng trên Resend.
    # APP_BASE_URL   : địa chỉ gốc của web, dùng để tạo link trong email,
    #                  vd https://tracuuduoc-bvdktamduccauquan.com (không có dấu / cuối)
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "Khoa Dược <onboarding@resend.dev>")
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "").strip()
    # Tên miền chính (không có https://), vd tracuuduoc-bvdktamduccauquan.com.
    # Nếu đặt: ai vào bằng địa chỉ *.onrender.com cũ sẽ được chuyển hướng (301) sang tên miền này.
    # Để trống = tắt chuyển hướng.
    CANONICAL_HOST = os.environ.get("CANONICAL_HOST", "").strip().lower()
    # Link đặt lại mật khẩu có hiệu lực bao nhiêu giây (mặc định 30 phút)
    RESET_TOKEN_MAX_AGE = int(os.environ.get("RESET_TOKEN_MAX_AGE", "1800"))

    # --- Cách 2: gửi email qua Google Apps Script (không cần tên miền) ---
    # Render free chặn cổng SMTP nên không gửi Gmail trực tiếp được; thay vào đó
    # gọi 1 Apps Script (chạy trên tài khoản Gmail của bạn) qua HTTPS.
    # Xem hướng dẫn trong HUONG_DAN_GUI_MAIL_GMAIL.md. Nếu đặt GAS_MAIL_URL thì
    # ưu tiên dùng cách này, bỏ qua Resend.
    # .strip() để phòng trường hợp copy-paste giá trị vào Render bị dính thừa
    # khoảng trắng/xuống dòng ở đầu-cuối (rất dễ gặp, và sẽ khiến URL gọi tới
    # sai địa chỉ -> Apps Script trả về trang lỗi 404 dạng HTML thay vì JSON).
    GAS_MAIL_URL = os.environ.get("GAS_MAIL_URL", "").strip()
    GAS_MAIL_SECRET = os.environ.get("GAS_MAIL_SECRET", "").strip()
    MAIL_NAME = os.environ.get("MAIL_NAME", "Cổng Tra Cứu Dược").strip()

    # --- Nhật ký truy cập: giữ bao lâu (ngày; 0 = không tự xoá) ---
    # Lượt xem trang (nhiều, nhẹ) giữ ngắn; tìm kiếm giữ vừa; thao tác admin/tài khoản giữ lâu nhất.
    NHAT_KY_GIU_NGAY_TRUY_CAP = int(os.environ.get("NHAT_KY_GIU_NGAY_TRUY_CAP", "14"))
    NHAT_KY_GIU_NGAY_TIM_KIEM = int(os.environ.get("NHAT_KY_GIU_NGAY_TIM_KIEM", "90"))
    NHAT_KY_GIU_NGAY = int(os.environ.get("NHAT_KY_GIU_NGAY", "365"))
    # Trần tổng số dòng nhật ký (mặc định 100.000 dòng ≈ 50 MB, an toàn cho gói free 500 MB): vượt thì xoá bớt lượt xem cũ nhất.
    NHAT_KY_TOI_DA = int(os.environ.get("NHAT_KY_TOI_DA", "100000"))

    # --- Cổng mã bảo mật 6 số trước trang admin ---
    # Mã đặt/đổi trong admin (menu "Mã bảo mật"). Biến môi trường ADMIN_GATE_PIN (6 số) dùng để
    # ĐẶT mã lần đầu hoặc ĐẶT LẠI khi quên mã: mỗi giá trị mới của biến này được áp dụng đúng 1 lần.
    ADMIN_GATE_IDLE_MINUTES = int(os.environ.get("ADMIN_GATE_IDLE_MINUTES", "30"))     # không thao tác > N phút -> hỏi lại mã
    ADMIN_GATE_MAX_SAI = int(os.environ.get("ADMIN_GATE_MAX_SAI", "5"))                # sai quá N lần / 1 IP ...
    ADMIN_GATE_KHOA_PHUT = int(os.environ.get("ADMIN_GATE_KHOA_PHUT", "15"))           # ... thì khoá IP đó N phút
    ADMIN_GATE_MAX_SAI_TOAN_CUC = int(os.environ.get("ADMIN_GATE_MAX_SAI_TOAN_CUC", "40"))  # chặn dò mã bằng nhiều IP
    ADMIN_GATE_DONG_KHI_DANG_XUAT = os.environ.get("ADMIN_GATE_DONG_KHI_DANG_XUAT", "1") != "0"  # đăng xuất xong phải nhập lại mã
    # Mặc định MỌI tài khoản admin đang đăng nhập đều đổi được mã bảo mật. Đặt "1" nếu chỉ muốn vai trò quan_tri đổi.
    ADMIN_GATE_CHI_QUAN_TRI_DOI = os.environ.get("ADMIN_GATE_CHI_QUAN_TRI_DOI", "0") == "1"
