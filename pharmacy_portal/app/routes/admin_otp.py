"""Các trang xác thực 2 lớp (OTP) cho admin. Logic nằm ở app/utils/otp.py.

  /admin/xac-thuc-otp            nhập mã 6 số (hoặc mã dự phòng) sau khi đã đúng mật khẩu
  /admin/thiet-lap-otp           quét QR + xác nhận 1 mã -> bật OTP, nhận 8 mã dự phòng
  /admin/bao-mat-2-lop           (đã đăng nhập) xem trạng thái, tạo lại mã dự phòng, đổi thiết bị, tắt OTP
"""
import re
import time

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user

from app.utils import otp
from app.utils.nhat_ky import ghi, lay_ip
from app.utils.phien_dang_nhap import danh_dau_hoat_dong

bp = Blueprint("admin_otp", __name__, url_prefix="/admin")


@bp.after_request
def _khong_luu_cache(resp):
    # Trang có QR / secret / mã dự phòng: không cho trình duyệt hay proxy lưu lại
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


def _chuan_hoa(ma: str) -> str:
    return re.sub(r"[\s-]+", "", (ma or "")) if (ma or "").strip()[:1].isdigit() else (ma or "").strip()


def _cho_neu_bi_khoa(nd) -> int:
    cfg = current_app.config
    return max(otp.da_vuot(otp.khoa_tai_khoan_otp(nd.id), cfg["OTP_MAX_SAI"]),
               otp.da_vuot(otp.khoa_ip_otp(lay_ip()), cfg["OTP_MAX_SAI_IP"]))


def _ghi_sai(nd):
    otp.ghi_sai(otp.khoa_tai_khoan_otp(nd.id))
    otp.ghi_sai(otp.khoa_ip_otp(lay_ip()))


def _con_lai(nd) -> int:
    return otp.con_lai(otp.khoa_tai_khoan_otp(nd.id), current_app.config["OTP_MAX_SAI"])


def _thong_bao_khoa(nd, phut):
    flash(f"Nhập sai quá nhiều lần. Vui lòng thử lại sau khoảng {phut} phút.", "error")
    ghi("otp_sai", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
        mo_ta="Đang bị khoá tạm do nhập sai quá nhiều lần", ma_trang_thai=429)


def _hoan_tat_dang_nhap(nd, mo_ta=None):
    """Đã qua đủ 2 lớp -> đăng nhập thật sự."""
    next_page = otp.lay_next_roi_xoa()
    otp.xoa_cho()
    login_user(nd)
    danh_dau_hoat_dong()
    ghi("dang_nhap", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap, mo_ta=mo_ta, ma_trang_thai=302)
    return redirect(otp.an_toan_next(next_page) or url_for("admin_dashboard.trang_chinh"))


# ----------------------------------------------------------------------------- Bước 2: nhập OTP
@bp.route("/xac-thuc-otp", methods=["GET", "POST"])
def xac_thuc():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard.trang_chinh"))
    nd = otp.nguoi_dang_cho()
    if nd is None:
        flash("Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.", "warning")
        return redirect(url_for("admin_auth.dang_nhap"))
    if not nd.totp_bat:
        return redirect(url_for("admin_otp.thiet_lap"))

    du_phong = request.values.get("du_phong") == "1"
    if request.method == "POST":
        phut = _cho_neu_bi_khoa(nd)
        if phut:
            _thong_bao_khoa(nd, phut)
            return render_template("admin/otp_xac_thuc.html", nd=nd, du_phong=du_phong), 429

        ma = _chuan_hoa(request.form.get("ma"))
        dung = otp.dung_ma_du_phong(nd, ma) if du_phong else otp.kiem_tra_ma(nd, ma)
        if dung:
            otp.xoa_sai(otp.khoa_tai_khoan_otp(nd.id))
            if du_phong:
                flash(f"Bạn vừa dùng 1 mã dự phòng, còn {otp.so_ma_du_phong_con(nd)} mã. "
                      f"Nên vào \"Bảo mật 2 lớp\" để tạo lại mã dự phòng hoặc đổi thiết bị.", "warning")
            return _hoan_tat_dang_nhap(nd, mo_ta="Dùng mã dự phòng" if du_phong else None)

        _ghi_sai(nd)
        ghi("otp_sai", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
            mo_ta="Mã dự phòng sai" if du_phong else "Mã OTP sai", ma_trang_thai=200)
        flash(f"Mã không đúng hoặc đã hết hạn. Còn {_con_lai(nd)} lần thử trước khi bị khoá tạm.", "error")
    return render_template("admin/otp_xac_thuc.html", nd=nd, du_phong=du_phong)


# ----------------------------------------------------------------------------- Thiết lập / đổi thiết bị
@bp.route("/thiet-lap-otp", methods=["GET", "POST"])
def thiet_lap():
    cho_dang_nhap = False
    if current_user.is_authenticated:
        nd = current_user._get_current_object()
        if nd.totp_bat:        # đổi thiết bị: phải vừa xác nhận lại mật khẩu + OTP hiện tại (xem quan_ly)
            t = session.get(otp.S_CHO_DAT_LAI)
            if not isinstance(t, (int, float)) or time.time() - t > 600:
                flash("Để đổi thiết bị, hãy xác nhận lại mật khẩu và mã OTP hiện tại.", "warning")
                return redirect(url_for("admin_otp.quan_ly"))
    else:
        nd = otp.nguoi_dang_cho()
        if nd is None:
            flash("Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.", "warning")
            return redirect(url_for("admin_auth.dang_nhap"))
        if nd.totp_bat:        # đã có OTP thì không cho "đăng ký lại" chỉ bằng mật khẩu
            return redirect(url_for("admin_otp.xac_thuc"))
        cho_dang_nhap = True

    secret = session.get(otp.S_SECRET_MOI)
    if not secret:
        secret = otp.tao_secret()
        session[otp.S_SECRET_MOI] = secret

    if request.method == "POST":
        phut = _cho_neu_bi_khoa(nd)
        if phut:
            _thong_bao_khoa(nd, phut)
        else:
            buoc = otp.kiem_tra_ma_secret_moi(secret, _chuan_hoa(request.form.get("ma")))
            if buoc is None:
                _ghi_sai(nd)
                flash(f"Mã không khớp. Kiểm tra đã quét đúng QR và đồng hồ điện thoại chuẩn giờ. "
                      f"Còn {_con_lai(nd)} lần thử.", "error")
            else:
                da_co = bool(nd.totp_bat)
                ds = otp.bat_otp(nd, secret, buoc)
                session.pop(otp.S_SECRET_MOI, None)
                session.pop(otp.S_CHO_DAT_LAI, None)
                otp.xoa_sai(otp.khoa_tai_khoan_otp(nd.id))
                ghi("doi_otp" if da_co else "otp_bat", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
                    mo_ta="Đổi thiết bị OTP" if da_co else "Bật xác thực 2 lớp", ma_trang_thai=200)
                if cho_dang_nhap:
                    next_page = otp.lay_next_roi_xoa()
                    otp.xoa_cho()
                    login_user(nd)
                    danh_dau_hoat_dong()
                    ghi("dang_nhap", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
                        mo_ta="Đăng nhập sau khi thiết lập OTP lần đầu", ma_trang_thai=302)
                    tiep = otp.an_toan_next(next_page) or url_for("admin_dashboard.trang_chinh")
                else:
                    tiep = url_for("admin_otp.quan_ly")
                return render_template("admin/otp_ma_du_phong.html", ds=ds, tiep=tiep, lan_dau=True)

    uri = otp.uri_quet(secret, nd)
    return render_template("admin/otp_thiet_lap.html", nd=nd, cho_dang_nhap=cho_dang_nhap,
                           qr=otp.qr_svg(uri), secret_hien=" ".join(secret[i:i + 4] for i in range(0, len(secret), 4)))


# ----------------------------------------------------------------------------- Quản lý (đã đăng nhập)
@bp.route("/bao-mat-2-lop")
@login_required
def quan_ly():
    return render_template("admin/otp_quan_ly.html", nd=current_user,
                           so_du_phong=otp.so_ma_du_phong_con(current_user))


def _xac_nhan_lai(nd) -> bool:
    """Việc nhạy cảm (đổi thiết bị, tạo lại mã dự phòng, tắt OTP) -> phải nhập lại mật khẩu + mã OTP hiện tại."""
    phut = _cho_neu_bi_khoa(nd)
    if phut:
        _thong_bao_khoa(nd, phut)
        return False
    if nd.check_password(request.form.get("mat_khau") or "") and otp.kiem_tra_ma(nd, _chuan_hoa(request.form.get("ma"))):
        otp.xoa_sai(otp.khoa_tai_khoan_otp(nd.id))
        return True
    _ghi_sai(nd)
    ghi("otp_sai", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
        mo_ta="Xác nhận lại mật khẩu/OTP sai (trang Bảo mật 2 lớp)", ma_trang_thai=200)
    flash(f"Mật khẩu hoặc mã OTP không đúng. Còn {_con_lai(nd)} lần thử.", "error")
    return False


@bp.route("/bao-mat-2-lop/doi-thiet-bi", methods=["POST"])
@login_required
def doi_thiet_bi():
    nd = current_user._get_current_object()
    if not nd.totp_bat or not _xac_nhan_lai(nd):
        return redirect(url_for("admin_otp.quan_ly"))
    session.pop(otp.S_SECRET_MOI, None)          # luôn tạo QR mới
    session[otp.S_CHO_DAT_LAI] = time.time()
    return redirect(url_for("admin_otp.thiet_lap"))


@bp.route("/bao-mat-2-lop/tao-lai-ma-du-phong", methods=["POST"])
@login_required
def tao_lai_du_phong():
    nd = current_user._get_current_object()
    if not nd.totp_bat or not _xac_nhan_lai(nd):
        return redirect(url_for("admin_otp.quan_ly"))
    ds = otp.tao_lai_ma_du_phong(nd)
    ghi("doi_otp", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap, mo_ta="Tạo lại mã dự phòng", ma_trang_thai=200)
    return render_template("admin/otp_ma_du_phong.html", ds=ds, tiep=url_for("admin_otp.quan_ly"), lan_dau=False)


@bp.route("/bao-mat-2-lop/tat", methods=["POST"])
@login_required
def tat():
    nd = current_user._get_current_object()
    if current_app.config["ADMIN_2FA_BAT_BUOC"]:
        flash("Hệ thống đang bắt buộc xác thực 2 lớp nên không tắt được.", "error")
    elif nd.totp_bat and _xac_nhan_lai(nd):
        otp.tat_otp(nd)
        ghi("doi_otp", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap, mo_ta="Tắt xác thực 2 lớp", ma_trang_thai=200)
        flash("Đã tắt xác thực 2 lớp cho tài khoản này.", "success")
    return redirect(url_for("admin_otp.quan_ly"))
