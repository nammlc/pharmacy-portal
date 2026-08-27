"""
Nhập hàng loạt - Luồng 3 bước:
  1. Chọn loại (Danh mục thuốc / Nhà thuốc BV)
  2. Upload Excel → Preview từng dòng, chọn nhóm + hoạt chất + ảnh
  3. Xác nhận → Lưu vào DB
"""
import io
import json
import csv
import os
import uuid
import tempfile

from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, Response, session, current_app)
from flask_login import login_required
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import SubmitField

from app import db
from app.models.models import NhomThuoc, HoatChat, DanhMucThuoc, NhaThuocBV
from app.utils.nhap_hang_loat import doc_file_bang
from app.utils.upload_anh import upload_anh_danh_muc_thuoc, upload_anh_nha_thuoc_bv
from app.utils.lam_sach_html import lam_sach_html

bp = Blueprint("admin_nhap_hang_loat", __name__, url_prefix="/admin/nhap-hang-loat")

_DUOI_FILE = ["xlsx", "csv"]


class UploadForm(FlaskForm):
    file_du_lieu = FileField(
        "Chọn file Excel (.xlsx)",
        validators=[FileRequired(), FileAllowed(_DUOI_FILE, "Chỉ nhận file .xlsx hoặc .csv.")],
    )
    submit = SubmitField("Tiếp tục →")


# ── Bước 1: Trang chọn loại ────────────────────────────────────────────────
@bp.route("/")
@login_required
def trang_chinh():
    return render_template("admin/nhap_hang_loat/buoc1.html")


# ── Bước 2a: Upload cho Danh mục thuốc ────────────────────────────────────
@bp.route("/danh-muc-thuoc", methods=["GET", "POST"])
@login_required
def upload_dmt():
    form = UploadForm()
    if form.validate_on_submit():
        try:
            rows = doc_file_bang(form.file_du_lieu.data)
        except Exception as e:
            flash(f"Không đọc được file: {e}", "danger")
            return redirect(request.url)
        if not rows:
            flash("File không có dữ liệu.", "warning")
            return redirect(request.url)

        # Lưu vào file tạm để tránh giới hạn cookie session 4KB
        tmp_id = uuid.uuid4().hex
        tmp_path = os.path.join(tempfile.gettempdir(), f"nhap_{tmp_id}.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, default=str, ensure_ascii=False)
        session["nhap_tmp"] = tmp_path
        session["nhap_loai"] = "dmt"
        return redirect(url_for("admin_nhap_hang_loat.preview"))

    nhom_ds = NhomThuoc.query.filter_by(loai="danh_muc_thuoc").order_by(NhomThuoc.ten_nhom).all()
    return render_template("admin/nhap_hang_loat/buoc2.html",
                           form=form, loai="dmt",
                           tieu_de="Danh mục thuốc",
                           nhom_ds=nhom_ds)


# ── Bước 2b: Upload cho Nhà thuốc BV ───────────────────────────────────────
@bp.route("/nha-thuoc-bv", methods=["GET", "POST"])
@login_required
def upload_ntbv():
    form = UploadForm()
    if form.validate_on_submit():
        try:
            rows = doc_file_bang(form.file_du_lieu.data)
        except Exception as e:
            flash(f"Không đọc được file: {e}", "danger")
            return redirect(request.url)
        if not rows:
            flash("File không có dữ liệu.", "warning")
            return redirect(request.url)

        tmp_id = uuid.uuid4().hex
        tmp_path = os.path.join(tempfile.gettempdir(), f"nhap_{tmp_id}.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, default=str, ensure_ascii=False)
        session["nhap_tmp"] = tmp_path
        session["nhap_loai"] = "ntbv"
        return redirect(url_for("admin_nhap_hang_loat.preview"))

    nhom_ds = NhomThuoc.query.filter_by(loai="nha_thuoc_bv").order_by(NhomThuoc.ten_nhom).all()
    return render_template("admin/nhap_hang_loat/buoc2.html",
                           form=form, loai="ntbv",
                           tieu_de="Nhà thuốc BV",
                           nhom_ds=nhom_ds)


# ── Bước 3: Preview + chọn nhóm/hoạt chất/ảnh ─────────────────────────────
@bp.route("/preview", methods=["GET"])
@login_required
def preview():
    tmp_path = session.get("nhap_tmp")
    loai = session.get("nhap_loai")
    if not tmp_path or not loai or not os.path.exists(tmp_path):
        flash("Phiên làm việc hết hạn. Vui lòng upload lại.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    with open(tmp_path, encoding="utf-8") as f:
        rows = json.load(f)

    if loai == "dmt":
        nhom_ds = NhomThuoc.query.filter_by(loai="danh_muc_thuoc").order_by(NhomThuoc.ten_nhom).all()
        url_xac_nhan = url_for("admin_nhap_hang_loat.xac_nhan_dmt")
        url_quay_lai = url_for("admin_nhap_hang_loat.upload_dmt")
        tieu_de = "Danh mục thuốc"
        cols_hien_thi = ["ten_biet_duoc", "thanh_phan", "chi_dinh",
                         "chong_chi_dinh", "cach_dung_lieu_dung", "link_chi_tiet"]
    else:
        nhom_ds = NhomThuoc.query.filter_by(loai="nha_thuoc_bv").order_by(NhomThuoc.ten_nhom).all()
        url_xac_nhan = url_for("admin_nhap_hang_loat.xac_nhan_ntbv")
        url_quay_lai = url_for("admin_nhap_hang_loat.upload_ntbv")
        tieu_de = "Nhà thuốc BV"
        cols_hien_thi = ["ten_biet_duoc", "link_tham_khao"]

    hoat_chat_ds = HoatChat.query.order_by(HoatChat.ten_hoat_chat).all()

    return render_template("admin/nhap_hang_loat/buoc3_preview.html",
                           rows=rows,
                           loai=loai,
                           tieu_de=tieu_de,
                           nhom_ds=nhom_ds,
                           hoat_chat_ds=hoat_chat_ds,
                           cols_hien_thi=cols_hien_thi,
                           url_xac_nhan=url_xac_nhan,
                           url_quay_lai=url_quay_lai)


# ── Bước 4a: Xác nhận lưu Danh mục thuốc ──────────────────────────────────
@bp.route("/xac-nhan/danh-muc-thuoc", methods=["POST"])
@login_required
def xac_nhan_dmt():
    tmp_path = session.get("nhap_tmp")
    if not tmp_path or not os.path.exists(tmp_path):
        flash("Phiên làm việc hết hạn.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    with open(tmp_path, encoding="utf-8") as f:
        rows = json.load(f)
    so_thanh_cong = 0
    loi_list = []

    for idx, row in enumerate(rows):
        ten = str(row.get("ten_biet_duoc") or "").strip()
        if not ten:
            loi_list.append(f"Dòng {idx+2}: thiếu tên biệt dược")
            continue

        # Lấy dữ liệu từ form preview (prefix theo index)
        prefix = f"r{idx}_"
        nhom_id = request.form.get(f"{prefix}nhom_thuoc_id", type=int) or None
        hc_ids = request.form.getlist(f"{prefix}hoat_chat_ids")
        hc_ids = [int(i) for i in hc_ids if str(i).isdigit()]

        try:
            thuoc = DanhMucThuoc.query.filter(
                db.func.lower(DanhMucThuoc.ten_biet_duoc) == ten.lower()
            ).first()
            is_new = thuoc is None
            if is_new:
                thuoc = DanhMucThuoc(ten_biet_duoc=ten)
                db.session.add(thuoc)

            thuoc.nhom_thuoc_id = nhom_id
            thuoc.hoat_chat_list = HoatChat.query.filter(HoatChat.id.in_(hc_ids)).all() if hc_ids else []

            if row.get("thanh_phan"):
                thuoc.thanh_phan = lam_sach_html(str(row["thanh_phan"]))
            if row.get("chi_dinh"):
                thuoc.chi_dinh = lam_sach_html(str(row["chi_dinh"]))
            if row.get("chong_chi_dinh"):
                thuoc.chong_chi_dinh = lam_sach_html(str(row["chong_chi_dinh"]))
            if row.get("cach_dung_lieu_dung"):
                thuoc.cach_dung_lieu_dung = lam_sach_html(str(row["cach_dung_lieu_dung"]))
            if row.get("link_chi_tiet"):
                lnk = str(row["link_chi_tiet"]).strip()
                if lnk and not lnk.startswith("http"):
                    lnk = "https://" + lnk
                thuoc.link_chi_tiet = lnk

            db.session.flush()

            # Upload ảnh nếu có
            file_anh = request.files.get(f"{prefix}file_anh")
            if file_anh and file_anh.filename:
                try:
                    url = upload_anh_danh_muc_thuoc(file_anh, url_cu=thuoc.hinh_anh)
                    if url:
                        thuoc.hinh_anh = url
                except Exception:
                    pass

            so_thanh_cong += 1
        except Exception as e:
            db.session.rollback()
            loi_list.append(f"Dòng {idx+2} ({ten}): {e}")

    db.session.commit()
    # Xoá file tạm
    try:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass
    session.pop("nhap_tmp", None)
    session.pop("nhap_loai", None)

    flash(f"Đã lưu thành công {so_thanh_cong} thuốc vào Danh mục thuốc.", "success")
    if loi_list:
        flash(f"{len(loi_list)} dòng bị lỗi: " + " | ".join(loi_list[:5]), "warning")
    return redirect(url_for("admin_dmt.danh_sach"))


# ── Bước 4b: Xác nhận lưu Nhà thuốc BV ────────────────────────────────────
@bp.route("/xac-nhan/nha-thuoc-bv", methods=["POST"])
@login_required
def xac_nhan_ntbv():
    tmp_path = session.get("nhap_tmp")
    if not tmp_path or not os.path.exists(tmp_path):
        flash("Phiên làm việc hết hạn.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))

    with open(tmp_path, encoding="utf-8") as f:
        rows = json.load(f)
    so_thanh_cong = 0
    loi_list = []

    for idx, row in enumerate(rows):
        ten = str(row.get("ten_biet_duoc") or "").strip()
        if not ten:
            loi_list.append(f"Dòng {idx+2}: thiếu tên biệt dược")
            continue

        prefix = f"r{idx}_"
        nhom_id = request.form.get(f"{prefix}nhom_thuoc_id", type=int) or None
        hc_ids = request.form.getlist(f"{prefix}hoat_chat_ids")
        hc_ids = [int(i) for i in hc_ids if str(i).isdigit()]

        try:
            thuoc = NhaThuocBV.query.filter(
                db.func.lower(NhaThuocBV.ten_biet_duoc) == ten.lower()
            ).first()
            if thuoc is None:
                thuoc = NhaThuocBV(ten_biet_duoc=ten)
                db.session.add(thuoc)

            thuoc.nhom_thuoc_id = nhom_id
            thuoc.hoat_chat_list = HoatChat.query.filter(HoatChat.id.in_(hc_ids)).all() if hc_ids else []

            if row.get("link_tham_khao"):
                lnk = str(row["link_tham_khao"]).strip()
                if lnk and not lnk.startswith("http"):
                    lnk = "https://" + lnk
                thuoc.link_tham_khao = lnk

            db.session.flush()

            file_anh = request.files.get(f"{prefix}file_anh")
            if file_anh and file_anh.filename:
                try:
                    url = upload_anh_nha_thuoc_bv(file_anh, url_cu=thuoc.hinh_anh)
                    if url:
                        thuoc.hinh_anh = url
                except Exception:
                    pass

            so_thanh_cong += 1
        except Exception as e:
            db.session.rollback()
            loi_list.append(f"Dòng {idx+2} ({ten}): {e}")

    db.session.commit()
    try:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
    except Exception:
        pass
    session.pop("nhap_tmp", None)
    session.pop("nhap_loai", None)

    flash(f"Đã lưu thành công {so_thanh_cong} thuốc vào Nhà thuốc BV.", "success")
    if loi_list:
        flash(f"{len(loi_list)} dòng bị lỗi: " + " | ".join(loi_list[:5]), "warning")
    return redirect(url_for("admin_ntbv.danh_sach"))


# ── File mẫu Excel ─────────────────────────────────────────────────────────
def _tai_mau_csv(headers, ten_file, dong_mau):
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerow(dong_mau)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={ten_file}"})


@bp.route("/mau-danh-muc-thuoc.csv")
@login_required
def tai_mau_dmt():
    # Không có cột nhóm_thuoc và hoạt_chất - sẽ chọn trên giao diện preview
    return _tai_mau_csv(
        ["ten_biet_duoc", "thanh_phan", "chi_dinh",
         "chong_chi_dinh", "cach_dung_lieu_dung", "link_chi_tiet"],
        "mau_danh_muc_thuoc.csv",
        ["Panadol Extra", "Paracetamol 500mg, Cafein 65mg",
         "Giảm đau, hạ sốt", "Quá mẫn thành phần",
         "Uống 1-2 viên/lần, 4-6 giờ/lần", "https://vi-du.vn/panadol"],
    )


@bp.route("/mau-nha-thuoc-bv.csv")
@login_required
def tai_mau_ntbv():
    return _tai_mau_csv(
        ["ten_biet_duoc", "link_tham_khao"],
        "mau_nha_thuoc_bv.csv",
        ["Panadol Extra", "https://vi-du.vn/panadol"],
    )
