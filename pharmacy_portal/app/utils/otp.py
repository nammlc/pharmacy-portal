"""Xác thực 2 lớp bằng OTP (TOTP - Google Authenticator, Microsoft Authenticator, Authy, 1Password...).

Luồng đăng nhập admin:
  1) /admin/dang-nhap      : nhập tên đăng nhập + mật khẩu  -> đúng thì CHƯA đăng nhập, chỉ ghi "đang chờ OTP"
                             vào session cookie đã ký (hết hạn sau OTP_CHO_PHUT phút).
  2) /admin/xac-thuc-otp   : nhập mã 6 số trong app (hoặc 1 mã dự phòng)  -> đúng mới login_user().
     Tài khoản CHƯA bật OTP (và ADMIN_2FA_BAT_BUOC=1) bị đưa sang /admin/thiet-lap-otp: quét QR, nhập thử 1 mã,
     nhận 8 mã dự phòng, rồi mới vào được.

Lưu trữ (bảng nguoi_dung):
  - totp_secret      : secret TOTP, MÃ HOÁ Fernet (khoá lấy từ OTP_ENC_KEY, mặc định dẫn xuất từ SECRET_KEY).
                       Phải lưu đọc lại được (server cần tính mã) nên khác mật khẩu - không băm một chiều được.
  - totp_buoc_cuoi   : bước thời gian 30s của mã đã dùng gần nhất -> 1 mã không dùng được 2 lần.
  - totp_ma_du_phong : JSON các BĂM (HMAC-SHA256) của mã dự phòng; dùng xong là bị xoá khỏi danh sách.

Chống dò: đếm lần sai trong bảng cong_bao_mat_lan_sai (GateLanThu), khoá theo TÀI KHOẢN (chính) và theo IP.
Khoá theo tài khoản là lớp chắc nhất vì IP có thể bị làm giả header X-Forwarded-For nếu proxy cấu hình lỏng.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from flask import current_app, session
from sqlalchemy import inspect, text

from app import db
from app.models.models import GateLanThu

RE_OTP = re.compile(r"^\d{6}$")
RE_DU_PHONG = re.compile(r"^[A-Z0-9]{4}-?[A-Z0-9]{4}$")
_BANG_CHU = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # bỏ I, O, 0, 1 cho khỏi nhầm
BUOC_GIAY = 30

# Session keys
S_CHO_UID = "_otp_cho_uid"          # id người đã đúng mật khẩu, đang chờ OTP
S_CHO_T = "_otp_cho_t"              # mốc thời gian (hết hạn sau OTP_CHO_PHUT)
S_CHO_NEXT = "_otp_cho_next"        # trang admin muốn vào sau khi đăng nhập xong
S_SECRET_MOI = "_otp_secret_moi"    # secret vừa tạo, chưa xác nhận
S_CHO_DAT_LAI = "_otp_cho_dat_lai"  # mốc: người đã đăng nhập vừa nhập đúng mật khẩu+OTP để đổi thiết bị


# ------------------------------------------------------------ Mã hoá secret
def _fernet():
    khoa = current_app.config.get("OTP_ENC_KEY") or ""
    if khoa:
        try:
            return Fernet(khoa.encode())
        except Exception:      # khoá tuỳ ý (không phải Fernet key) -> băm thành khoá hợp lệ
            pass
        goc = khoa
    else:
        goc = current_app.config["SECRET_KEY"]
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(("otp-enc|" + goc).encode()).digest()))


def ma_hoa(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def giai_ma(token: str):
    """Trả về secret hoặc None nếu không giải mã được (vd đã đổi SECRET_KEY/OTP_ENC_KEY)."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, AttributeError, ValueError):
        return None


# ------------------------------------------------------------ TOTP
def tao_secret() -> str:
    return pyotp.random_base32()          # 32 ký tự base32 = 160 bit


def uri_quet(secret: str, nguoi_dung) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=nguoi_dung.ten_dang_nhap, issuer_name=current_app.config["OTP_ISSUER"])


def qr_svg(uri: str) -> str:
    """Mã QR dạng SVG (không cần Pillow). Chuỗi này do server tạo từ secret nên an toàn khi chèn |safe."""
    import io
    import qrcode
    from qrcode.image.svg import SvgPathImage
    img = qrcode.make(uri, image_factory=SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.index("<svg"):]        # bỏ khai báo <?xml ...?>


def _buoc_khop(secret: str, ma: str):
    """Trả về bước 30s khớp với `ma` (cho lệch ±1 bước = ±30 giây), hoặc None."""
    if not RE_OTP.match(ma or ""):
        return None
    totp = pyotp.TOTP(secret)
    hien_tai = int(time.time() // BUOC_GIAY)
    ket_qua = None
    for lech in (-1, 0, 1):                # luôn thử đủ 3 bước (không thoát sớm) để thời gian xử lý đều nhau
        buoc = hien_tai + lech
        if hmac.compare_digest(totp.at(buoc * BUOC_GIAY), ma) and ket_qua is None:
            ket_qua = buoc
    return ket_qua


def kiem_tra_ma(nguoi_dung, ma: str) -> bool:
    """Kiểm tra mã 6 số của tài khoản đã bật OTP. Đúng -> ghi nhận bước đã dùng (commit) để chặn dùng lại."""
    secret = giai_ma(nguoi_dung.totp_secret) if nguoi_dung.totp_secret else None
    if not secret:
        return False
    buoc = _buoc_khop(secret, ma)
    if buoc is None:
        return False
    if nguoi_dung.totp_buoc_cuoi is not None and buoc <= nguoi_dung.totp_buoc_cuoi:
        return False                        # mã này (hoặc mã cũ hơn) đã được dùng rồi
    nguoi_dung.totp_buoc_cuoi = buoc
    db.session.commit()
    return True


def kiem_tra_ma_secret_moi(secret: str, ma: str):
    """Dùng lúc thiết lập: kiểm tra mã với secret CHƯA lưu. Trả về bước khớp hoặc None."""
    return _buoc_khop(secret, ma)


# ------------------------------------------------------------ Mã dự phòng
def _bam_du_phong(ma: str) -> str:
    ma = ma.replace("-", "").upper()
    return hmac.new(current_app.config["SECRET_KEY"].encode(), ("otp-dp|" + ma).encode(), hashlib.sha256).hexdigest()


def tao_ma_du_phong(so_luong=8):
    """Trả về (danh sách mã hiển thị 1 lần, JSON băm để lưu)."""
    ds = []
    for _ in range(so_luong):
        s = "".join(secrets.choice(_BANG_CHU) for _ in range(8))
        ds.append(f"{s[:4]}-{s[4:]}")
    return ds, json.dumps([_bam_du_phong(m) for m in ds])


def so_ma_du_phong_con(nguoi_dung) -> int:
    try:
        return len(json.loads(nguoi_dung.totp_ma_du_phong or "[]"))
    except ValueError:
        return 0


def dung_ma_du_phong(nguoi_dung, ma: str) -> bool:
    """Mã đúng -> xoá khỏi danh sách (mỗi mã chỉ dùng 1 lần) và commit."""
    ma = (ma or "").strip().upper()
    if not RE_DU_PHONG.match(ma):
        return False
    try:
        ds = json.loads(nguoi_dung.totp_ma_du_phong or "[]")
    except ValueError:
        return False
    bam = _bam_du_phong(ma)
    khop = None
    for h in ds:
        if hmac.compare_digest(h, bam) and khop is None:
            khop = h
    if khop is None:
        return False
    ds.remove(khop)
    nguoi_dung.totp_ma_du_phong = json.dumps(ds)
    db.session.commit()
    return True


# ------------------------------------------------------------ Bật / tắt cho tài khoản
def bat_otp(nguoi_dung, secret: str, buoc_da_dung: int):
    """Lưu secret (mã hoá), bật OTP, tạo mã dự phòng mới. Trả về danh sách mã dự phòng (chỉ hiện 1 lần)."""
    ds, bam = tao_ma_du_phong()
    nguoi_dung.totp_secret = ma_hoa(secret)
    nguoi_dung.totp_bat = True
    nguoi_dung.totp_buoc_cuoi = buoc_da_dung
    nguoi_dung.totp_ma_du_phong = bam
    nguoi_dung.totp_ngay_bat = datetime.utcnow()
    db.session.commit()
    return ds


def tat_otp(nguoi_dung):
    nguoi_dung.totp_secret = None
    nguoi_dung.totp_bat = False
    nguoi_dung.totp_buoc_cuoi = None
    nguoi_dung.totp_ma_du_phong = None
    nguoi_dung.totp_ngay_bat = None
    db.session.commit()


def tao_lai_ma_du_phong(nguoi_dung):
    ds, bam = tao_ma_du_phong()
    nguoi_dung.totp_ma_du_phong = bam
    db.session.commit()
    return ds


# ------------------------------------------------------------ Trạng thái "đang chờ OTP" (session)
def an_toan_next(gia_tri):
    """Chỉ cho phép chuyển về đường dẫn nội bộ trong /admin (chống open-redirect)."""
    if gia_tri and gia_tri.startswith("/admin") and not gia_tri.startswith("//") and "\\" not in gia_tri:
        return gia_tri
    return None


def bat_dau_cho(nguoi_dung, next_page=None):
    for k in (S_SECRET_MOI, S_CHO_DAT_LAI):
        session.pop(k, None)
    session[S_CHO_UID] = nguoi_dung.id
    session[S_CHO_T] = time.time()
    session[S_CHO_NEXT] = an_toan_next(next_page)


def nguoi_dang_cho():
    """NguoiDung đã đúng mật khẩu và đang chờ OTP (còn hạn), hoặc None."""
    from app.models.models import NguoiDung
    uid, t = session.get(S_CHO_UID), session.get(S_CHO_T)
    if uid is None or not isinstance(t, (int, float)):
        return None
    if time.time() - t > current_app.config["OTP_CHO_PHUT"] * 60:
        xoa_cho()
        return None
    nd = db.session.get(NguoiDung, uid)
    if nd is None or not nd.dang_hoat_dong:
        xoa_cho()
        return None
    return nd


def xoa_cho():
    for k in (S_CHO_UID, S_CHO_T, S_SECRET_MOI, S_CHO_DAT_LAI):
        session.pop(k, None)


def lay_next_roi_xoa():
    return session.pop(S_CHO_NEXT, None)


def phai_dung_otp(nguoi_dung) -> bool:
    """Tài khoản này có phải qua bước OTP không? (đã bật OTP, hoặc hệ thống bắt buộc)."""
    return bool(nguoi_dung.totp_bat) or bool(current_app.config["ADMIN_2FA_BAT_BUOC"])


# ------------------------------------------------------------ Chống dò (đếm lần sai trong DB)
def _khoa_ten(ten: str) -> str:
    return "#u:" + hashlib.sha256((ten or "").strip().lower().encode()).hexdigest()[:20]


def khoa_tai_khoan_otp(nguoi_dung_id) -> str:
    return f"#otp-u:{nguoi_dung_id}"


def khoa_tai_khoan_mk(ten_dang_nhap) -> str:
    return "#pw" + _khoa_ten(ten_dang_nhap)


def khoa_ip_otp(ip) -> str:
    return "#otp-ip:" + ip


def khoa_ip_mk(ip) -> str:
    return "#pw-ip:" + ip


def da_vuot(khoa: str, toi_da: int) -> int:
    """0 nếu còn được thử; ngược lại số phút phải chờ."""
    phut = current_app.config["OTP_KHOA_PHUT"]
    cua_so = timedelta(minutes=phut)
    moc = datetime.utcnow() - cua_so
    ds = (GateLanThu.query.filter(GateLanThu.ip == khoa, GateLanThu.thoi_gian > moc)
          .order_by(GateLanThu.thoi_gian.asc()).all())
    if len(ds) < toi_da:
        return 0
    het = ds[len(ds) - toi_da].thoi_gian + cua_so
    return max(1, int((het - datetime.utcnow()).total_seconds() // 60) + 1)


def ghi_sai(khoa: str):
    db.session.add(GateLanThu(ip=khoa[:64], thoi_gian=datetime.utcnow()))
    GateLanThu.query.filter(GateLanThu.thoi_gian < datetime.utcnow() - timedelta(days=1)) \
        .delete(synchronize_session=False)
    db.session.commit()


def con_lai(khoa: str, toi_da: int) -> int:
    moc = datetime.utcnow() - timedelta(minutes=current_app.config["OTP_KHOA_PHUT"])
    so = GateLanThu.query.filter(GateLanThu.ip == khoa, GateLanThu.thoi_gian > moc).count()
    return max(0, toi_da - so)


def xoa_sai(khoa: str):
    GateLanThu.query.filter(GateLanThu.ip == khoa).delete(synchronize_session=False)
    db.session.commit()


# ------------------------------------------------------------ Ép thiết lập OTP (phiên đăng nhập có từ trước khi bật tính năng)
def dang_ky(app):
    from flask import redirect, request, url_for
    from flask_login import current_user

    cho_phep = ("static", "admin_otp.thiet_lap", "admin_auth.dang_xuat", "admin_auth.keep_alive")

    @app.before_request
    def _ep_thiet_lap_otp():
        if not request.path.startswith("/admin") or request.endpoint in cho_phep:
            return None
        if app.config["ADMIN_2FA_BAT_BUOC"] and current_user.is_authenticated and not current_user.totp_bat:
            return redirect(url_for("admin_otp.thiet_lap"))
        return None


# ------------------------------------------------------------ Tự thêm cột vào bảng nguoi_dung khi khởi động
# (tên cột, kiểu PostgreSQL, kiểu SQLite, kiểu MySQL). Chạy lại nhiều lần không sao (chỉ thêm cột còn thiếu).
CAC_COT_OTP = [
    ("totp_secret",      "TEXT",    "TEXT",    "TEXT"),
    ("totp_bat",         "BOOLEAN NOT NULL DEFAULT FALSE", "BOOLEAN NOT NULL DEFAULT 0", "BOOLEAN NOT NULL DEFAULT 0"),
    ("totp_buoc_cuoi",   "BIGINT",  "BIGINT",  "BIGINT"),
    ("totp_ma_du_phong", "TEXT",    "TEXT",    "TEXT"),
    ("totp_ngay_bat",    "TIMESTAMP", "DATETIME", "DATETIME"),
]


def khoi_tao(app):
    """Gọi 1 lần khi app khởi động (trong app_context), TRƯỚC mọi truy vấn bảng nguoi_dung."""
    try:
        insp = inspect(db.engine)
        if not insp.has_table("nguoi_dung"):
            return                          # DB mới: db.create_all() sẽ tạo bảng đã có sẵn các cột OTP
        co = {c["name"] for c in insp.get_columns("nguoi_dung")}
        dialect = db.engine.dialect.name
        idx = {"postgresql": 0, "mysql": 2}.get(dialect, 1)      # cột kiểu: [postgres, sqlite, mysql]
        for ten, *kieu in CAC_COT_OTP:
            if ten in co:
                continue
            try:
                db.session.execute(text(f"ALTER TABLE nguoi_dung ADD COLUMN {ten} {kieu[idx]}"))
                db.session.commit()
                app.logger.warning(f"Đã thêm cột nguoi_dung.{ten} (xác thực 2 lớp OTP).")
            except Exception as e:          # nhiều worker khởi động cùng lúc -> worker kia đã thêm rồi
                db.session.rollback()
                app.logger.warning(f"Thêm cột nguoi_dung.{ten} lỗi (có thể đã tồn tại): {e}")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Không kiểm tra/thêm được cột OTP cho bảng nguoi_dung: {e}. "
                         f"Hãy chạy them_cot_otp_nguoi_dung.sql thủ công.")
