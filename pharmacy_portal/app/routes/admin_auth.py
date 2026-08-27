from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.models.models import NguoiDung
from app.forms import DangNhapForm, DoiMatKhauForm

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
        # Đánh dấu phiên là "permanent" để áp dụng PERMANENT_SESSION_LIFETIME
        # (tự đăng xuất sau 15 phút không hoạt động - xem config.py). Không
        # dùng remember-cookie (login_user mặc định remember=False) vì
        # remember-cookie sẽ ghi đè, khiến phiên không bao giờ tự hết hạn.
        session.permanent = True
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
