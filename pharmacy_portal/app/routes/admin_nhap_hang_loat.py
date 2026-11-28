"""
Nhập hàng loạt - Luồng 3 bước:
  1. Chọn loại (Danh mục thuốc / Nhà thuốc BV)
  2. Upload Excel → Preview từng dòng, chọn nhóm + hoạt chất + ảnh
  3. Xác nhận → Lưu vào DB
"""
import io
import json
from dataclasses import asdict
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
from app.utils import nhap_tuong_tac as nt
from app.utils import tuong_tac_hc as tthc

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


# ════════════════════════════════════════════════════════════════════════════
#  TƯƠNG TÁC THUỐC (cặp HOẠT CHẤT)  —  tải file → xem trước & xử lý trùng → xác nhận → báo cáo
#  Logic chống trùng nằm trong app/utils/nhap_tuong_tac.py (thuần, có test) và tuong_tac_hc.py (ghi CSDL).
# ════════════════════════════════════════════════════════════════════════════
def _xoa_tmp(duong_dan):
    try:
        if duong_dan and os.path.basename(duong_dan).startswith("nhap_tt_") and os.path.exists(duong_dan):
            os.remove(duong_dan)
    except OSError:
        pass


def _doc_dong_tuong_tac():
    """Đọc các dòng đã tải lên từ file tạm; None nếu phiên hết hạn."""
    tmp_path = session.get("nhap_tt_tmp")
    if not tmp_path or not os.path.exists(tmp_path):
        return None
    with open(tmp_path, encoding="utf-8") as f:
        return [nt.DongNhap(**d) for d in json.load(f)]


def _dung_ke_hoach(dongs, form):
    """Dựng kế hoạch từ các lựa chọn người nhập gửi lên (luôn tính lại ở server, không tin phân loại từ trình duyệt)."""
    quyet_dinh = {}
    for i, khoa in enumerate(form.getlist("ten_khoa")):
        hd = form.get(f"hd_{i}", "tao")
        if hd in ("ghep", "bo"):
            quyet_dinh[khoa] = {"hanh_dong": hd, "dich": form.get(f"dich_{i}", "")}
    muc_do_chon = {}
    for k, v in form.items():
        if k.startswith("md_") and k[3:].isdigit():
            muc_do_chon[int(k[3:])] = v
    chon_xd = {}
    for i, ma in enumerate(form.getlist("xd_ma")):
        v = form.get(f"xd_{i}", type=int)
        if v:
            chon_xd[ma] = v
    che_do = nt.CHE_DO_GHI_DE if form.get("che_do_trung") == nt.CHE_DO_GHI_DE else nt.CHE_DO_BO_QUA
    hc_hien_co = tthc.tai_hoat_chat_hien_co()
    kh = nt.lap_ke_hoach(dongs, hc_hien_co, tthc.tai_cap_hien_co(), quyet_dinh, muc_do_chon, chon_xd, che_do)
    return kh, hc_hien_co, quyet_dinh, muc_do_chon, che_do


@bp.route("/tuong-tac-thuoc", methods=["GET", "POST"])
@login_required
def upload_tuong_tac():
    form = UploadForm()
    if form.validate_on_submit():
        try:
            dongs = nt.doc_file_tuong_tac(form.file_du_lieu.data)
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(request.url)
        except Exception as e:
            flash(f"Không đọc được file: {e}", "danger")
            return redirect(request.url)
        if not dongs:
            flash("File không có dòng dữ liệu nào.", "warning")
            return redirect(request.url)
        _xoa_tmp(session.get("nhap_tt_tmp"))
        tmp_path = os.path.join(tempfile.gettempdir(), f"nhap_tt_{uuid.uuid4().hex}.json")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in dongs], f, ensure_ascii=False)
        session["nhap_tt_tmp"] = tmp_path
        return redirect(url_for("admin_nhap_hang_loat.xem_truoc_tuong_tac"))
    return render_template("admin/nhap_hang_loat/tuong_tac_upload.html", form=form)


@bp.route("/tuong-tac-thuoc/xem-truoc", methods=["GET", "POST"])
@login_required
def xem_truoc_tuong_tac():
    """GET: xem trước với lựa chọn mặc định. POST: 'Cập nhật xem trước' sau khi người nhập đổi lựa chọn."""
    dongs = _doc_dong_tuong_tac()
    if dongs is None:
        flash("Phiên làm việc hết hạn. Vui lòng tải file lên lại.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.upload_tuong_tac"))
    form = request.form if request.method == "POST" else {}
    if request.method == "POST":
        kh, hc_hien_co, qd, md_chon, che_do = _dung_ke_hoach(dongs, request.form)
    else:
        hc_hien_co = tthc.tai_hoat_chat_hien_co()
        kh = nt.lap_ke_hoach(dongs, hc_hien_co, tthc.tai_cap_hien_co())
        qd, md_chon, che_do = {}, {}, nt.CHE_DO_BO_QUA

    ten_moi = sorted((t for k, t in kh.ten_file.items() if k not in hc_hien_co), key=lambda t: t.ten.lower())
    # Chỉ khớp tên GIỐNG HỆT (đã bỏ hoa/thường, dấu, khoảng trắng thừa). Tên khác -> tự thêm mới, không gợi ý/ghép.
    ten_khop = sorted(((t.ten, hc_hien_co[k][1]) for k, t in kh.ten_file.items() if k in hc_hien_co), key=lambda x: x[0].lower())
    post = request.method == "POST"
    ui = {"nhom_dong": request.form.get("nhom_dong", "") if post else "",       # nhớ nhóm lọc + trang của bảng chi tiết
          "trang_dong": request.form.get("trang_dong", type=int) if post else None}
    return render_template("admin/nhap_hang_loat/tuong_tac_xem_truoc.html",
                           kh=kh, dong_theo_so={d.so_dong: d for d in dongs}, ten_moi=ten_moi, ten_khop=ten_khop, ui=ui,
                           qd=qd, md_chon=md_chon, che_do=che_do, nhan_muc=nt.NHAN_MUC_DO,
                           so_hien_co=len(hc_hien_co), nt=nt)


@bp.route("/tuong-tac-thuoc/xac-nhan", methods=["POST"])
@login_required
def xac_nhan_tuong_tac():
    dongs = _doc_dong_tuong_tac()
    if dongs is None:
        flash("Phiên làm việc hết hạn. Vui lòng tải file lên lại.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.upload_tuong_tac"))
    kh = _dung_ke_hoach(dongs, request.form)[0]
    if kh.so_lieu["tao"] + kh.so_lieu["cap_nhat"] == 0:
        flash("Không có cặp nào để nhập. Hãy kiểm tra lại các lựa chọn.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.xem_truoc_tuong_tac"))
    try:
        kq = tthc.thuc_hien_nhap(kh)
    except Exception:
        current_app.logger.exception("Nhập hàng loạt tương tác thuốc lỗi")
        flash("Có lỗi khi lưu vào cơ sở dữ liệu — chưa có gì được lưu. Vui lòng thử lại.", "danger")
        return redirect(url_for("admin_nhap_hang_loat.xem_truoc_tuong_tac"))

    # Báo cáo CSV các dòng KHÔNG được nhập (kèm lý do) để người nhập sửa file rồi nhập lại phần còn thiếu
    bao_cao = None
    khong_nhap = [r for r in kh.ket_qua if not (r.trang_thai == nt.OK and r.hanh_dong != "bo")]
    if khong_nhap:
        bao_cao = os.path.join(tempfile.gettempdir(), f"nhap_tt_bc_{uuid.uuid4().hex}.csv")
        with open(bao_cao, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Dòng trong file", "Hoạt chất 1", "Hoạt chất 2", "Mức độ (file)", "Kết quả", "Lý do"])
            for r in khong_nhap:
                w.writerow([r.dong.so_dong, r.dong.ten_a, r.dong.ten_b, r.dong.muc_do_goc,
                            _NHAN_TRANG_THAI.get(r.trang_thai, r.trang_thai) if r.trang_thai != nt.OK else "Đã có — bỏ qua",
                            r.ly_do])
    _xoa_tmp(session.pop("nhap_tt_tmp", None))
    _xoa_tmp(session.get("nhap_tt_bao_cao"))
    session["nhap_tt_bao_cao"] = bao_cao
    session["nhap_tt_ket_qua"] = {**kq, **{k: kh.so_lieu[k] for k in
                                           ("tong_dong", "trung_giong", "loai_xung_dot", "thieu_muc_do", "loi", "bo_qua_ten")},
                                  "khong_nhap": len(khong_nhap)}
    return redirect(url_for("admin_nhap_hang_loat.ket_qua_tuong_tac"))


_NHAN_TRANG_THAI = {
    nt.TRUNG_GIONG: "Trùng y hệt — đã gộp", nt.LOAI_XUNG_DOT: "Xung đột — không dùng",
    nt.THIEU_MUC_DO: "Thiếu mức độ — bỏ qua", nt.LOI: "Lỗi", nt.BO_QUA_TEN: "Bỏ theo lựa chọn",
}


@bp.route("/tuong-tac-thuoc/ket-qua")
@login_required
def ket_qua_tuong_tac():
    kq = session.get("nhap_tt_ket_qua")
    if not kq:
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))
    return render_template("admin/nhap_hang_loat/tuong_tac_ket_qua.html", kq=kq,
                           co_bao_cao=bool(session.get("nhap_tt_bao_cao")))


@bp.route("/tuong-tac-thuoc/bao-cao.csv")
@login_required
def tai_bao_cao_tuong_tac():
    duong_dan = session.get("nhap_tt_bao_cao")
    if not duong_dan or not os.path.exists(duong_dan):
        flash("Báo cáo không còn nữa.", "warning")
        return redirect(url_for("admin_nhap_hang_loat.trang_chinh"))
    with open(duong_dan, "rb") as f:
        noi_dung = f.read()
    return Response(noi_dung, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tuong_tac_dong_khong_nhap.csv"})


@bp.route("/mau-tuong-tac-thuoc.xlsx")
@login_required
def tai_mau_tuong_tac():
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = "Tương tác thuốc"
    ws.append(["STT", "Hoạt chất 1", "Hoạt chất 2", "Mức độ", "Cơ chế", "Hậu quả", "Xử trí"])
    ws.append([1, "Aceclofenac", "Ketorolac", "Chống chỉ định",
               "Cùng nhóm NSAID, cộng gộp độc tính.", "Tăng nguy cơ xuất huyết tiêu hoá, suy thận.",
               "1. Không phối hợp.\n2. Chọn một thuốc thay thế."])
    ws.append([2, "Ephedrin", "Xanh methylen", "Nghiêm trọng", "", "Nguy cơ hội chứng serotonin.", "Theo dõi sát."])
    for c in ws[1]:
        c.font = Font(bold=True)
    for col, w in zip("ABCDEFG", (6, 26, 26, 18, 40, 44, 44)):
        ws.column_dimensions[col].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    hd = wb.create_sheet("Hướng dẫn")
    for dong in [
        ["Cột", "Ý nghĩa"],
        ["Hoạt chất 1, Hoạt chất 2", "Bắt buộc. Thứ tự không quan trọng: (A,B) và (B,A) là cùng một cặp."],
        ["Mức độ", "Bắt buộc: Chống chỉ định | Nghiêm trọng | Vừa phải (hoặc Trung bình) | Nhẹ."],
        ["Cơ chế, Hậu quả, Xử trí", "Không bắt buộc. Xuống dòng trong ô sẽ thành từng đoạn."],
        ["STT", "Bỏ qua (không dùng)."],
        ["Cặp bị trùng", "Hệ thống tự phát hiện: trùng y hệt thì gộp; khác nội dung thì bạn chọn dòng dùng."],
    ]:
        hd.append(dong)
    hd.column_dimensions["A"].width = 28
    hd.column_dimensions["B"].width = 90
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=mau_tuong_tac_thuoc.xlsx"})
