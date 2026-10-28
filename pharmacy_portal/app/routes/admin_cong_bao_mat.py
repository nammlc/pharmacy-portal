import re
import time
"""Cổng mã bảo mật 6 số trước trang admin + thiết lập lần đầu + quên mã (qua email) + đổi mã trong admin.
Mọi thao tác đều làm trên web, KHÔNG cần truy cập Render hay Neon."""
import hashlib
from html import escape

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for)
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import check_password_hash

from app.forms import DoiMaBaoMatForm
from app.models.models import NguoiDung
from app.utils import cong_bao_mat as cong
from app.utils.gui_email import gui_email
from app.utils.nhat_ky import ghi, lay_ip

# --- Các trang CỔNG (công khai, nằm trước đăng nhập) ---
bp = Blueprint("admin_cong", __name__, url_prefix="/admin/ma-bao-mat")


RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _loi_ma_moi(ma, xac_nhan):
    """Trả về thông báo lỗi nếu mã mới không hợp lệ, ngược lại None."""
    if not cong.RE_PIN.match(ma or ""):
        return "Mã bảo mật gồm đúng 6 chữ số."
    if ma != xac_nhan:
        return "Mã nhập lại không khớp."
    if cong.pin_yeu(ma):
        return "Mã quá dễ đoán (vd 123456, 111111, 121212). Hãy chọn mã khác."
    return None


@bp.route("/", methods=["GET", "POST"])
def nhap_ma():
    dich = cong.an_toan_next(request.values.get("next")) or url_for("admin_auth.dang_nhap")

    if cong.da_qua_cong():
        return redirect(dich)

    hash_, _ = cong.doc_cau_hinh()
    if hash_ is None:      # chưa có mã nào -> form thiết lập lần đầu (cần tài khoản admin)
        return render_template("admin/cong_ma_bao_mat.html", next=dich, chua_cau_hinh=True)

    if request.method == "POST":
        ip = lay_ip()
        phut = cong.phut_bi_khoa(ip)
        if phut:
            ghi("ma_bao_mat_sai", mo_ta=f"Bị khoá tạm thời ({phut} phút) do nhập sai nhiều lần")
            flash(f"Nhập sai quá nhiều lần. Vui lòng thử lại sau khoảng {phut} phút.", "error")
            return render_template("admin/cong_ma_bao_mat.html", next=dich), 429

        ma = (request.form.get("ma") or "").strip()
        if cong.RE_PIN.match(ma) and check_password_hash(hash_, ma):
            cong.xoa_lan_sai(ip)
            cong.mo_cong()
            ghi("ma_bao_mat_dung", mo_ta="Nhập đúng mã bảo mật")
            return redirect(dich)

        dau = cong.dau_lan_thu(ma)
        gan = session.get("_gate_lan_sai")
        if gan and gan[0] == dau and time.time() - gan[1] < 3:
            con_lai = cong.con_lai_hien_tai(ip)      # cùng một lần gửi bị lặp: không đếm thêm
        else:
            con_lai = cong.ghi_lan_sai(ip)
            session["_gate_lan_sai"] = [dau, time.time()]
        ghi("ma_bao_mat_sai", mo_ta=f"Nhập sai mã bảo mật (còn {con_lai} lần thử)")
        if con_lai:
            flash(f"Mã bảo mật không đúng. Còn {con_lai} lần thử.", "error")
        else:
            flash(f"Nhập sai quá nhiều lần. Vui lòng thử lại sau {current_app.config['ADMIN_GATE_KHOA_PHUT']} phút.", "error")
        return render_template("admin/cong_ma_bao_mat.html", next=dich)

    return render_template("admin/cong_ma_bao_mat.html", next=dich)


@bp.route("/thiet-lap", methods=["POST"])
def thiet_lap():
    """Thiết lập mã LẦN ĐẦU ngay trên web. Chỉ mở khi hệ thống chưa có mã, và bắt buộc
    nhập đúng tên đăng nhập + mật khẩu của 1 tài khoản admin đang hoạt động."""
    hash_, _ = cong.doc_cau_hinh()
    if hash_ is not None:
        return redirect(url_for("admin_cong.nhap_ma"))

    dich = cong.an_toan_next(request.form.get("next")) or url_for("admin_auth.dang_nhap")
    khoa = "#s:" + lay_ip()
    if cong.vuot_gioi_han(khoa, 5, 15):
        flash("Thử quá nhiều lần. Vui lòng quay lại sau ít phút.", "error")
        return render_template("admin/cong_ma_bao_mat.html", next=dich, chua_cau_hinh=True), 429

    ten = (request.form.get("ten_dang_nhap") or "").strip()
    nd = NguoiDung.query.filter_by(ten_dang_nhap=ten).first() if ten else None
    if nd is None or not nd.dang_hoat_dong or not nd.check_password(request.form.get("mat_khau") or ""):
        cong.ghi_lan(khoa)
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "error")
        return render_template("admin/cong_ma_bao_mat.html", next=dich, chua_cau_hinh=True)

    loi = _loi_ma_moi((request.form.get("ma_moi") or "").strip(), (request.form.get("xac_nhan") or "").strip())
    if loi:
        flash(loi, "error")
        return render_template("admin/cong_ma_bao_mat.html", next=dich, chua_cau_hinh=True)

    cong.dat_ma(request.form["ma_moi"].strip())
    cong.mo_cong()
    ghi("doi_ma_bao_mat", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap, mo_ta="Thiết lập mã bảo mật lần đầu")
    flash("Đã thiết lập mã bảo mật. Hãy ghi nhớ mã này.", "success")
    return redirect(dich)


@bp.route("/quen", methods=["GET", "POST"])
def quen_ma():
    """Quên mã: gửi link đặt mã mới tới email của tài khoản admin. Luôn trả cùng 1 thông báo
    (không tiết lộ email nào có tồn tại)."""
    hash_, _ = cong.doc_cau_hinh()
    if hash_ is None:
        return redirect(url_for("admin_cong.nhap_ma"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        # Chỉ kiểm tra ĐỊNH DẠNG email (không tiết lộ email nào có trong hệ thống)
        if not RE_EMAIL.match(email):
            flash("Email không đúng định dạng. Ví dụ đúng: ten@gmail.com", "error")
            return render_template("admin/cong_quen_ma.html", email=email), 400
        khoa_ip = "#q:" + lay_ip()
        khoa_email = "#e:" + hashlib.sha256(email.encode()).hexdigest()[:16]

        if cong.vuot_gioi_han(khoa_ip, 3, 60) or cong.vuot_gioi_han(khoa_email, 3, 60):
            flash("Bạn đã yêu cầu quá nhiều lần. Vui lòng thử lại sau 1 giờ.", "error")
            return render_template("admin/cong_quen_ma.html"), 429

        cong.ghi_lan(khoa_ip)
        cong.ghi_lan(khoa_email)
        nd = NguoiDung.query.filter(func.lower(NguoiDung.email) == email).first() if email else None
        if nd is not None and nd.dang_hoat_dong:
            _gui_link_dat_lai_ma(nd)
            ghi("doi_ma_bao_mat", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap,
                mo_ta="Yêu cầu link đặt lại mã bảo mật qua email")
        flash("Nếu email khớp với một tài khoản quản trị, link đặt mã mới đã được gửi. "
              "Vui lòng kiểm tra hộp thư (kể cả mục Spam).", "success")
        return redirect(url_for("admin_cong.nhap_ma"))

    return render_template("admin/cong_quen_ma.html")


def _gui_link_dat_lai_ma(nd):
    goc = (current_app.config.get("APP_BASE_URL") or request.url_root).rstrip("/")
    link = goc + url_for("admin_cong.dat_lai_ma", token=cong.tao_token_dat_lai(nd))
    phut = current_app.config["RESET_TOKEN_MAX_AGE"] // 60
    ten = escape(nd.ho_ten or nd.ten_dang_nhap)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;line-height:1.6;color:#1a2233">
      <h2 style="margin:0 0 12px">Đặt lại mã bảo mật</h2>
      <p>Xin chào {ten},</p>
      <p>Chúng tôi nhận được yêu cầu đặt lại <strong>mã bảo mật 6 số</strong> của cổng quản trị Cổng Tra Cứu Dược.
         Bấm nút bên dưới để đặt mã mới (link có hiệu lực {phut} phút, chỉ dùng được 1 lần):</p>
      <p style="margin:24px 0">
        <a href="{link}" style="background:#2f6f5e;color:#fff;padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:bold">Đặt mã bảo mật mới</a>
      </p>
      <p style="font-size:13px;color:#667">Nếu nút không bấm được, dán link này vào trình duyệt:<br>{link}</p>
      <p style="font-size:13px;color:#667">Nếu bạn không yêu cầu, hãy bỏ qua email này — mã hiện tại vẫn giữ nguyên.</p>
    </div>"""
    text = (f"Xin chào {nd.ho_ten or nd.ten_dang_nhap},\n\n"
            f"Đặt lại mã bảo mật cổng quản trị (hiệu lực {phut} phút, dùng 1 lần):\n{link}\n\n"
            "Nếu bạn không yêu cầu, hãy bỏ qua email này.")
    if not gui_email(nd.email, "Đặt lại mã bảo mật — Cổng Tra Cứu Dược", html, text):
        current_app.logger.error("Gửi email đặt lại mã bảo mật thất bại cho user id=%s", nd.id)


@bp.route("/dat-lai/<token>", methods=["GET", "POST"])
def dat_lai_ma(token):
    nd = cong.kiem_tra_token_dat_lai(token)
    if nd is None:
        flash("Link đặt lại mã không hợp lệ hoặc đã hết hạn. Vui lòng yêu cầu link mới.", "error")
        return redirect(url_for("admin_cong.quen_ma"))

    if request.method == "POST":
        ma = (request.form.get("ma_moi") or "").strip()
        loi = _loi_ma_moi(ma, (request.form.get("xac_nhan") or "").strip())
        if loi:
            flash(loi, "error")
            return render_template("admin/cong_dat_lai_ma.html", token=token)
        cong.dat_ma(ma)
        ghi("doi_ma_bao_mat", nguoi_dung_id=nd.id, ten_nguoi_dung=nd.ten_dang_nhap, mo_ta="Đặt lại mã bảo mật qua email")
        flash("Đã đặt mã bảo mật mới. Hãy nhập mã mới để tiếp tục.", "success")
        return redirect(url_for("admin_cong.nhap_ma"))

    return render_template("admin/cong_dat_lai_ma.html", token=token)


# --- Trang ĐỔI MÃ (trong admin, khi đã đăng nhập) ---
bp_doi = Blueprint("admin_ma_bao_mat", __name__, url_prefix="/admin/doi-ma-bao-mat")


@bp_doi.before_request
@login_required
def _kiem_tra_quyen():
    if current_app.config.get("ADMIN_GATE_CHI_QUAN_TRI_DOI") and current_user.vai_tro != "quan_tri":
        abort(403)


@bp_doi.route("/", methods=["GET", "POST"])
def doi_ma():
    form = DoiMaBaoMatForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.mat_khau_hien_tai.data):
            flash("Mật khẩu tài khoản không đúng.", "error")
        elif cong.pin_yeu(form.ma_moi.data):
            flash("Mã quá dễ đoán (vd 123456, 111111, 121212). Hãy chọn mã khác hoặc bấm “Tạo mã ngẫu nhiên”.", "error")
        else:
            cong.dat_ma(form.ma_moi.data)
            cong.mo_cong()          # giữ phiên của chính người đổi, các thiết bị khác phải nhập mã mới
            ghi("doi_ma_bao_mat", nguoi_dung_id=current_user.id, ten_nguoi_dung=current_user.ten_dang_nhap,
                mo_ta="Đổi mã bảo mật cổng admin")
            flash("Đã đổi mã bảo mật. Các trình duyệt/thiết bị khác sẽ phải nhập mã mới.", "success")
            return redirect(url_for("admin_dashboard.trang_chinh"))
    return render_template("admin/doi_ma_bao_mat.html", form=form, ngay_doi=cong.ngay_doi_gan_nhat())
