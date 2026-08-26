from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    import os
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    csrf.init_app(app)

    @app.template_filter("chuan_hoa_url")
    def chuan_hoa_url(url):
        """
        Chuẩn hoá URL để dùng trong href="...": nếu người dùng nhập thiếu
        http://  hoặc https:// (vd: "nhathuoclongchau.com.vn/thuoc/abc.html"),
        trình duyệt sẽ hiểu nhầm thành link tương đối và nối vào domain hiện
        tại. Thêm "https://" phía trước nếu url chưa có scheme.
        """
        if not url:
            return url
        url = url.strip()
        if url.startswith(("http://", "https://", "//", "mailto:", "tel:")):
            return url
        return "https://" + url

    login_manager.init_app(app)
    login_manager.login_view = "admin_auth.dang_nhap"
    login_manager.login_message = "Vui lòng đăng nhập để tiếp tục."
    login_manager.login_message_category = "warning"

    from app.models.models import NguoiDung

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(NguoiDung, int(user_id))

    # --- Trang công khai ---
    from app.routes.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.routes.tra_cuu_thuoc_tiem_truyen import bp as tttt_bp
    app.register_blueprint(tttt_bp)

    from app.routes.tra_cuu_tuong_hop_tuong_ky import bp as thtk_bp
    app.register_blueprint(thtk_bp)

    from app.routes.tra_cuu_tuong_tac_thuoc import bp as ttt_bp
    app.register_blueprint(ttt_bp)

    from app.routes.tra_cuu_thong_tin_thuoc import bp as ttth_bp
    app.register_blueprint(ttth_bp)

    from app.routes.thong_tin_benh_nhan import bp as ttbn_bp
    app.register_blueprint(ttbn_bp)

    from app.routes.danh_muc_thuoc import bp as dmt_bp
    app.register_blueprint(dmt_bp)

    from app.routes.nha_thuoc_bv import bp as ntbv_bp
    app.register_blueprint(ntbv_bp)

    # --- Trang quản trị (admin) - yêu cầu đăng nhập ---
    from app.routes.admin_auth import bp as admin_auth_bp
    app.register_blueprint(admin_auth_bp)

    from app.routes.admin_dashboard import bp as admin_dashboard_bp
    app.register_blueprint(admin_dashboard_bp)

    from app.routes.admin_thuoc import bp as admin_thuoc_bp
    app.register_blueprint(admin_thuoc_bp)

    from app.routes.admin_nhom_thuoc import bp as admin_nhom_thuoc_bp
    app.register_blueprint(admin_nhom_thuoc_bp)

    from app.routes.admin_hoat_chat import bp as admin_hoat_chat_bp
    app.register_blueprint(admin_hoat_chat_bp)

    from app.routes.admin_danh_muc_thuoc import bp as admin_dmt_bp
    app.register_blueprint(admin_dmt_bp)

    from app.routes.admin_nha_thuoc_bv import bp as admin_ntbv_bp
    app.register_blueprint(admin_ntbv_bp)

    from app.routes.admin_tiem_truyen import bp as admin_tttt_bp
    app.register_blueprint(admin_tttt_bp)

    from app.routes.admin_tuong_hop_tuong_ky import bp as admin_thtk_bp
    app.register_blueprint(admin_thtk_bp)

    from app.routes.admin_tuong_tac import bp as admin_ttt_bp
    app.register_blueprint(admin_ttt_bp)

    from app.routes.admin_thong_tin_thuoc import bp as admin_ttth_bp
    app.register_blueprint(admin_ttth_bp)

    from app.routes.admin_benh_nhan import bp as admin_ttbn_bp
    app.register_blueprint(admin_ttbn_bp)

    from app.routes.admin_ve_chung_toi import bp as admin_vct_bp
    app.register_blueprint(admin_vct_bp)

    from app.routes.admin_nhap_hang_loat import bp as admin_nhap_hang_loat_bp
    app.register_blueprint(admin_nhap_hang_loat_bp)

    _tao_tai_khoan_dau_tien_neu_can(app)

    return app


def _tao_tai_khoan_dau_tien_neu_can(app):
    """Tự tạo 1 tài khoản admin khi khởi động, nếu:
    - Chưa có tài khoản admin nào trong database, VÀ
    - Đã đặt 2 biến môi trường ADMIN_USERNAME + ADMIN_PASSWORD

    Dùng cho hosting free (như Render free tier) không có Shell/Console
    để chạy create_admin.py thủ công. Idempotent - chạy lại nhiều lần
    không tạo trùng, vì chỉ tạo khi bảng nguoi_dung đang rỗng.
    """
    import os
    from app.models.models import NguoiDung

    ten_dang_nhap = os.environ.get("ADMIN_USERNAME")
    mat_khau = os.environ.get("ADMIN_PASSWORD")

    if not ten_dang_nhap or not mat_khau:
        return

    with app.app_context():
        db.create_all()
        if NguoiDung.query.count() == 0:
            nguoi_dung = NguoiDung(ten_dang_nhap=ten_dang_nhap, vai_tro="quan_tri")
            nguoi_dung.set_password(mat_khau)
            db.session.add(nguoi_dung)
            db.session.commit()
            app.logger.info(f"Đã tự tạo tài khoản admin '{ten_dang_nhap}' từ biến môi trường.")
