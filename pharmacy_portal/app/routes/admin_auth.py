import hashlib
from html import escape

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func
from app.models.models import NguoiDung
from app.forms import (
    DangNhapForm, DoiMatKhauForm, QuenMatKhauForm, DatLaiMatKhauForm, CapNhatEmailForm,
)
from app.utils.gui_email import gui_email

bp = Blueprint("admin_auth", __name__, url_prefix="/admin")


@bp.route("/dang-nhap", methods=["GET", "POST"])
def dang_nhap():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard.trang_chinh"))

    form = DangNhapForm()
    if form.validate_on_submit():
        nguoi_dung = NguoiDung.query.filter_by(ten_dang_nhap=form.ten_dang_nhap.data.strip()).first()

        # So sánh chung 1 thông báo lỗi cho cả 2 trường hợp (sai tên đăng nhập
        # HOẶC sai mật khẩu) để tránh lộ thông tin tài khoản nào tồn tại.
        if nguoi_dung is None or not nguoi_dung.check_password(form.mat_khau.data):
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
            return render_template("admin/dang_nhap.html", form=form)

        if not nguoi_dung.dang_hoat_dong:
            flash("Tài khoản này đã bị khoá. Liên hệ quản trị viên.", "error")
            return render_template("admin/dang_nhap.html", form=form)

        login_user(nguoi_dung)
        next_page = request.args.get("next")
        return redirect(next_page or url_for("admin_dashboard.trang_chinh"))

    return render_template("admin/dang_nhap.html", form=form)


@bp.route("/dang-xuat")
@login_required
def dang_xuat():
    logout_user()
    flash("Đã đăng xuất.", "success")
    return redirect(url_for("admin_auth.dang_nhap"))


@bp.route("/doi-mat-khau", methods=["GET", "POST"])
@login_required
def doi_mat_khau():
    from app import db
    form = DoiMatKhauForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.mat_khau_hien_tai.data):
            flash("Mật khẩu hiện tại không đúng.", "error")
            return render_template("admin/doi_mat_khau.html", form=form)

        if form.mat_khau_moi.data != form.xac_nhan_mat_khau_moi.data:
            flash("Mật khẩu mới nhập lại không khớp.", "error")
            return render_template("admin/doi_mat_khau.html", form=form)

        current_user.set_password(form.mat_khau_moi.data)
        db.session.commit()
        flash("Đã đổi mật khẩu thành công.", "success")
        return redirect(url_for("admin_dashboard.trang_chinh"))

    return render_template("admin/doi_mat_khau.html", form=form)


# ---------------------------------------------------------------------------
# Quên mật khẩu (gửi link đặt lại qua Resend)
# ---------------------------------------------------------------------------
def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="dat-lai-mat-khau")


def _dau_van_tay_mat_khau(nguoi_dung):
    """Băm từ hash mật khẩu hiện tại: khi mật khẩu đổi thì token cũ tự vô hiệu
    (link chỉ dùng được 1 lần, không cần lưu token trong database)."""
    return hashlib.sha256(nguoi_dung.mat_khau_hash.encode()).hexdigest()[:16]


def _tao_token(nguoi_dung):
    return _serializer().dumps({"id": nguoi_dung.id, "v": _dau_van_tay_mat_khau(nguoi_dung)})


def _kiem_tra_token(token):
    """Trả về NguoiDung nếu token hợp lệ, còn hạn, chưa dùng; ngược lại None."""
    from app import db
    try:
        du_lieu = _serializer().loads(token, max_age=current_app.config["RESET_TOKEN_MAX_AGE"])
    except (BadSignature, SignatureExpired):
        return None
    nguoi_dung = db.session.get(NguoiDung, du_lieu.get("id"))
    if nguoi_dung is None or not nguoi_dung.dang_hoat_dong:
        return None
    if du_lieu.get("v") != _dau_van_tay_mat_khau(nguoi_dung):
        return None
    return nguoi_dung


def _gui_link_dat_lai(nguoi_dung):
    goc = (current_app.config.get("APP_BASE_URL") or request.url_root).rstrip("/")
    link = goc + url_for("admin_auth.dat_lai_mat_khau", token=_tao_token(nguoi_dung))
    phut = current_app.config["RESET_TOKEN_MAX_AGE"] // 60
    ten = escape(nguoi_dung.ho_ten or nguoi_dung.ten_dang_nhap)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;line-height:1.6;color:#1a2233">
      <h2 style="margin:0 0 12px">Đặt lại mật khẩu</h2>
      <p>Xin chào {ten},</p>
      <p>Chúng tôi nhận được yêu cầu đặt lại mật khẩu tài khoản quản trị Cổng Tra Cứu Dược.
         Bấm nút bên dưới để đặt mật khẩu mới (link có hiệu lực {phut} phút, chỉ dùng được 1 lần):</p>
      <p style="margin:24px 0">
        <a href="{link}" style="background:#2f6f5e;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold">Đặt lại mật khẩu</a>
      </p>
      <p style="font-size:13px;color:#667">Nếu nút không bấm được, dán link này vào trình duyệt:<br>{link}</p>
      <p style="font-size:13px;color:#667">Nếu bạn không yêu cầu, hãy bỏ qua email này — mật khẩu hiện tại vẫn giữ nguyên.</p>
    </div>"""
    text = (
        f"Xin chào {nguoi_dung.ho_ten or nguoi_dung.ten_dang_nhap},\n\n"
        f"Đặt lại mật khẩu (hiệu lực {phut} phút, dùng 1 lần):\n{link}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )
    return gui_email(nguoi_dung.email, "Đặt lại mật khẩu — Cổng Tra Cứu Dược", html, text)


@bp.route("/quen-mat-khau", methods=["GET", "POST"])
def quen_mat_khau():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard.trang_chinh"))

    form = QuenMatKhauForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        nguoi_dung = NguoiDung.query.filter(func.lower(NguoiDung.email) == email).first()
        if nguoi_dung is not None and nguoi_dung.dang_hoat_dong:
            if not _gui_link_dat_lai(nguoi_dung):
                current_app.logger.error("Gửi email đặt lại mật khẩu thất bại cho user id=%s", nguoi_dung.id)

        # Luôn báo cùng 1 thông báo dù email có tồn tại hay không (chống dò tài khoản).
        flash("Nếu email này đã được đăng ký cho một tài khoản, link đặt lại mật khẩu vừa được gửi. "
              "Vui lòng kiểm tra hộp thư (kể cả mục Spam).", "success")
        return redirect(url_for("admin_auth.dang_nhap"))

    return render_template("admin/quen_mat_khau.html", form=form)


@bp.route("/dat-lai-mat-khau/<token>", methods=["GET", "POST"])
def dat_lai_mat_khau(token):
    from app import db
    nguoi_dung = _kiem_tra_token(token)
    if nguoi_dung is None:
        flash("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu link mới.", "error")
        return redirect(url_for("admin_auth.quen_mat_khau"))

    form = DatLaiMatKhauForm()
    if form.validate_on_submit():
        nguoi_dung.set_password(form.mat_khau_moi.data)
        db.session.commit()
        flash("Đã đặt lại mật khẩu. Hãy đăng nhập bằng mật khẩu mới.", "success")
        return redirect(url_for("admin_auth.dang_nhap"))

    return render_template("admin/dat_lai_mat_khau.html", form=form)


@bp.route("/cap-nhat-email", methods=["GET", "POST"])
@login_required
def cap_nhat_email():
    from app import db
    form = CapNhatEmailForm()
    if request.method == "GET":
        form.email.data = current_user.email

    if form.validate_on_submit():
        if not current_user.check_password(form.mat_khau_hien_tai.data):
            flash("Mật khẩu hiện tại không đúng.", "error")
            return render_template("admin/cap_nhat_email.html", form=form)
        email = form.email.data.strip().lower()
        trung = NguoiDung.query.filter(
            func.lower(NguoiDung.email) == email, NguoiDung.id != current_user.id
        ).first()
        if trung:
            flash("Email này đã được dùng cho tài khoản khác.", "error")
            return render_template("admin/cap_nhat_email.html", form=form)
        current_user.email = email
        db.session.commit()
        flash("Đã lưu email khôi phục mật khẩu.", "success")
        return redirect(url_for("admin_dashboard.trang_chinh"))

    return render_template("admin/cap_nhat_email.html", form=form)
