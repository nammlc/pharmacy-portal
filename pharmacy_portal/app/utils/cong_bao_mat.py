"""
Cổng mã bảo mật 6 chữ số đặt TRƯỚC toàn bộ trang quản trị (/admin/...).

Luồng: vào /admin/... -> chưa qua cổng -> chuyển tới /admin/ma-bao-mat nhập 6 số -> mới thấy
trang đăng nhập (tên đăng nhập + mật khẩu). Trang công khai không bị ảnh hưởng.

  - Mã chỉ lưu dạng BĂM (không xem lại được) trong bảng cai_dat_he_thong.
  - Qua cổng được ghi trong session cookie đã ký của Flask: gồm "phiên bản mã" + mốc thời gian.
    Đổi mã -> phiên bản tăng -> mọi trình duyệt khác bị hỏi lại mã.
  - Cổng tự đóng lại khi: không thao tác > ADMIN_GATE_IDLE_MINUTES, tự đăng xuất vì hết phiên,
    hoặc bấm đăng xuất (nếu ADMIN_GATE_DONG_KHI_DANG_XUAT bật).
  - Chống dò mã: sai ADMIN_GATE_MAX_SAI lần -> khoá IP đó ADMIN_GATE_KHOA_PHUT phút; ngoài ra có
    ngưỡng chung toàn hệ thống (phòng kẻ dò bằng nhiều IP).
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timedelta

from flask import current_app, jsonify, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models.models import CaiDatHeThong, GateLanThu

K_HASH = "admin_gate_pin_hash"
K_VER = "admin_gate_version"
K_ENV = "admin_gate_env_marker"
K_DOI = "admin_gate_changed_at"
S_VER = "_gate_v"
S_T = "_gate_t"
RE_PIN = re.compile(r"^\d{6}$")
_DAY = "0123456789"


# ------------------------------------------------------------ Mã yếu
def pin_yeu(pin: str) -> bool:
    """Từ chối các mã dễ đoán: 111111, 123456, 654321, 121212, 123123..."""
    if len(set(pin)) == 1:
        return True
    if pin in _DAY or pin in _DAY[::-1] or pin in (_DAY + _DAY):
        return True
    if pin[:2] * 3 == pin or pin[:3] * 2 == pin:
        return True
    return False


def tao_ma_ngau_nhien() -> str:
    while True:
        pin = f"{secrets.randbelow(10 ** 6):06d}"
        if not pin_yeu(pin):
            return pin


# ------------------------------------------------------------ Cấu hình trong DB
def _dat(khoa, gia_tri):
    h = db.session.get(CaiDatHeThong, khoa)
    if h is None:
        db.session.add(CaiDatHeThong(khoa=khoa, gia_tri=gia_tri))
    else:
        h.gia_tri = gia_tri


def doc_cau_hinh():
    """(băm_mã | None, phiên_bản:int)"""
    hang = {r.khoa: r.gia_tri for r in
            CaiDatHeThong.query.filter(CaiDatHeThong.khoa.in_([K_HASH, K_VER])).all()}
    try:
        ver = int(hang.get(K_VER) or 0)
    except ValueError:
        ver = 0
    return hang.get(K_HASH), ver


def ngay_doi_gan_nhat():
    h = db.session.get(CaiDatHeThong, K_DOI)
    try:
        return datetime.fromisoformat(h.gia_tri) if h and h.gia_tri else None
    except ValueError:
        return None


def dat_ma(pin: str) -> int:
    """Đặt mã mới (đã kiểm tra hợp lệ ở nơi gọi), tăng phiên bản. Trả về phiên bản mới."""
    _, ver = doc_cau_hinh()
    _dat(K_HASH, generate_password_hash(pin))
    _dat(K_VER, str(ver + 1))
    _dat(K_DOI, datetime.utcnow().isoformat())
    db.session.commit()
    return ver + 1


def khoi_tao(app):
    """Gọi 1 lần khi app khởi động (trong app_context):
       1) Có biến ADMIN_GATE_PIN mới (chưa áp dụng) -> đặt/đặt lại mã theo biến đó.
       2) Chưa có mã nào -> cổng hiện form "Thiết lập mã lần đầu" (bắt buộc đăng nhập bằng tài khoản admin),
          KHÔNG cần truy cập Render/Neon."""
    try:
        env = os.environ.get("ADMIN_GATE_PIN", "").strip()
        if env:
            if not RE_PIN.match(env):
                app.logger.warning("ADMIN_GATE_PIN không hợp lệ (cần đúng 6 chữ số) - bỏ qua.")
            else:
                dau = hmac.new(app.config["SECRET_KEY"].encode(), env.encode(), hashlib.sha256).hexdigest()
                da_ap = db.session.get(CaiDatHeThong, K_ENV)
                if da_ap is None or da_ap.gia_tri != dau:
                    dat_ma(env)
                    _dat(K_ENV, dau)
                    db.session.commit()
                    app.logger.warning("Đã đặt mã bảo mật cổng admin theo biến ADMIN_GATE_PIN.")

        hash_, _ = doc_cau_hinh()
        if hash_ is None:
            app.logger.warning("Chưa có mã bảo mật cổng admin: mở /admin để thiết lập (cần tài khoản admin), "
                               "hoặc đặt biến ADMIN_GATE_PIN.")
    except Exception as e:
        db.session.rollback()
        app.logger.warning(f"Khởi tạo mã bảo mật cổng admin lỗi: {e}")


# ------------------------------------------------------------ Trạng thái qua cổng (session)
def da_qua_cong() -> bool:
    hash_, ver = doc_cau_hinh()
    if hash_ is None:
        return False
    t = session.get(S_T)
    if session.get(S_VER) != ver or not isinstance(t, (int, float)):
        return False
    return time.time() - t <= current_app.config["ADMIN_GATE_IDLE_MINUTES"] * 60


def mo_cong():
    _, ver = doc_cau_hinh()
    session[S_VER] = ver
    session[S_T] = time.time()


def dong_cong():
    session.pop(S_VER, None)
    session.pop(S_T, None)


# ------------------------------------------------------------ Khoá khi nhập sai nhiều lần
def _phut_con_lai(moc_het_han):
    return max(1, int((moc_het_han - datetime.utcnow()).total_seconds() // 60) + 1)


def phut_bi_khoa(ip: str) -> int:
    """0 nếu được phép thử; ngược lại số phút còn bị khoá."""
    cfg = current_app.config
    cua_so = timedelta(minutes=cfg["ADMIN_GATE_KHOA_PHUT"])
    moc = datetime.utcnow() - cua_so
    con_lai = 0

    cua_ip = (GateLanThu.query.filter(GateLanThu.ip == ip, GateLanThu.thoi_gian > moc)
              .order_by(GateLanThu.thoi_gian.asc()).all())
    n_ip = cfg["ADMIN_GATE_MAX_SAI"]
    if len(cua_ip) >= n_ip:
        con_lai = max(con_lai, _phut_con_lai(cua_ip[len(cua_ip) - n_ip].thoi_gian + cua_so))

    toan_cuc = (GateLanThu.query.filter(GateLanThu.thoi_gian > moc, ~GateLanThu.ip.like("#%"))
                .order_by(GateLanThu.thoi_gian.asc()).all())
    n_tc = cfg["ADMIN_GATE_MAX_SAI_TOAN_CUC"]
    if len(toan_cuc) >= n_tc:
        con_lai = max(con_lai, _phut_con_lai(toan_cuc[len(toan_cuc) - n_tc].thoi_gian + cua_so))
    return con_lai


def ghi_lan_sai(ip: str) -> int:
    """Ghi 1 lần sai, trả về số lần còn được thử của IP này trong cửa sổ hiện tại."""
    db.session.add(GateLanThu(ip=ip, thoi_gian=datetime.utcnow()))
    # dọn các lần sai cũ hơn 1 ngày
    GateLanThu.query.filter(GateLanThu.thoi_gian < datetime.utcnow() - timedelta(days=1)) \
        .delete(synchronize_session=False)
    db.session.commit()
    return con_lai_hien_tai(ip)


def con_lai_hien_tai(ip: str) -> int:
    """Số lần còn được thử của IP này (không ghi thêm lần sai nào)."""
    moc = datetime.utcnow() - timedelta(minutes=current_app.config["ADMIN_GATE_KHOA_PHUT"])
    so = GateLanThu.query.filter(GateLanThu.ip == ip, GateLanThu.thoi_gian > moc).count()
    return max(0, current_app.config["ADMIN_GATE_MAX_SAI"] - so)


def dau_lan_thu(ma: str) -> str:
    """Dấu của lần nhập, dùng để nhận ra cùng một lần gửi bị lặp (có khoá bí mật, không lộ mã)."""
    return hmac.new(current_app.config["SECRET_KEY"].encode(), ma.encode(), hashlib.sha256).hexdigest()[:16]


def vuot_gioi_han(khoa: str, toi_da: int, phut: int) -> bool:
    """Giới hạn tần suất chung. `khoa` dạng '#q:<ip>', '#e:<băm email>', '#s:<ip>' (bắt đầu bằng '#',
    không bao giờ trùng IP thật) -> không tính vào ngưỡng khoá toàn hệ thống."""
    moc = datetime.utcnow() - timedelta(minutes=phut)
    return GateLanThu.query.filter(GateLanThu.ip == khoa, GateLanThu.thoi_gian > moc).count() >= toi_da


def ghi_lan(khoa: str):
    db.session.add(GateLanThu(ip=khoa[:64], thoi_gian=datetime.utcnow()))
    db.session.commit()


def xoa_lan_sai(ip: str):
    GateLanThu.query.filter(GateLanThu.ip == ip).delete(synchronize_session=False)
    db.session.commit()


# ------------------------------------------------------------ Link "quên mã" qua email
def _dau_van_tay_ma():
    """Đổi theo mã hiện tại: khi mã đã đổi thì link cũ tự vô hiệu (dùng được đúng 1 lần)."""
    hash_, ver = doc_cau_hinh()
    return hashlib.sha256(f"{hash_}|{ver}".encode()).hexdigest()[:16]


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="dat-lai-ma-bao-mat")


def tao_token_dat_lai(nguoi_dung) -> str:
    return _serializer().dumps({"id": nguoi_dung.id, "v": _dau_van_tay_ma()})


def kiem_tra_token_dat_lai(token):
    """Trả về NguoiDung nếu token hợp lệ, còn hạn, chưa dùng; ngược lại None."""
    from app.models.models import NguoiDung
    try:
        du_lieu = _serializer().loads(token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
    except (BadSignature, SignatureExpired):
        return None
    nd = db.session.get(NguoiDung, du_lieu.get("id"))
    if nd is None or not nd.dang_hoat_dong or du_lieu.get("v") != _dau_van_tay_ma():
        return None
    return nd


# ------------------------------------------------------------ Hook chặn mọi trang /admin
def an_toan_next(gia_tri):
    """Chỉ cho phép chuyển về đường dẫn nội bộ trong /admin (chống open-redirect)."""
    if gia_tri and gia_tri.startswith("/admin") and not gia_tri.startswith("//") and "\\" not in gia_tri:
        return gia_tri
    return None


def dang_ky(app):
    @app.before_request
    def _chan_neu_chua_qua_cong():
        if request.endpoint in (None, "static"):
            return None
        duong_dan = request.path
        if not (duong_dan == "/admin" or duong_dan.startswith("/admin/")):
            return None
        if request.blueprint == "admin_cong":      # nhập mã, thiết lập lần đầu, quên mã, đặt lại mã
            return None

        if da_qua_cong():
            session[S_T] = time.time()          # trượt cửa sổ không-hoạt-động
            return None

        if request.endpoint == "admin_auth.keep_alive":
            resp = jsonify(active=False)
            resp.status_code = 401
            resp.headers["Cache-Control"] = "no-store"
            return resp
        if request.method == "GET":
            return redirect(url_for("admin_cong.nhap_ma", next=request.full_path.rstrip("?")))
        return redirect(url_for("admin_cong.nhap_ma"))
