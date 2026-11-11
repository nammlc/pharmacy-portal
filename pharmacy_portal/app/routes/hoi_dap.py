"""API hỏi đáp / bình luận CÔNG KHAI dưới thuốc và bài viết. Ý kiến mới ở trạng thái 'chờ duyệt', admin duyệt mới hiện."""
from flask import Blueprint, current_app, jsonify, request

from app import db
from app.models.models import YKien
from app.utils import phan_hoi as PH
from app.utils import thong_bao as TB
from app.utils.online import khoa_khach, la_bot
from app.utils.thoi_gian import gio_vn

bp = Blueprint("hoi_dap", __name__, url_prefix="/api/hoi-dap")
MOI_TRANG = 10


def _json(d, ma=200):
    r = jsonify(d)
    r.status_code = ma
    r.headers["Cache-Control"] = "no-store"
    return r


def _loi(thong_bao, ma=400):
    return _json({"ok": False, "loi": thong_bao}, ma)


@bp.get("/")
def danh_sach():
    """Các ý kiến ĐÃ DUYỆT của 1 thuốc / bài viết, mới nhất trước, phân trang."""
    loai, obj_id = request.args.get("loai", ""), request.args.get("id", "")
    if PH.lay_doi_tuong(loai, obj_id) is None:
        return _loi("Không tìm thấy nội dung.", 404)
    try:
        trang = max(1, int(request.args.get("trang", 1)))
    except ValueError:
        trang = 1
    q = YKien.query.filter_by(doi_tuong_loai=loai, doi_tuong_id=int(obj_id), trang_thai="da_duyet")
    tong = q.count()
    muc = q.order_by(YKien.ngay_tao.desc(), YKien.id.desc()).offset((trang - 1) * MOI_TRANG).limit(MOI_TRANG).all()
    return _json({
        "ok": True, "tong": tong, "co_them": trang * MOI_TRANG < tong,
        "muc": [{"id": y.id, "ten": y.ten, "noi_dung": y.noi_dung,              # KHÔNG trả SĐT
                 "ngay": gio_vn(y.ngay_tao).strftime("%d/%m/%Y"),
                 "tra_loi": y.tra_loi or "",
                 "ngay_tra_loi": gio_vn(y.ngay_tra_loi).strftime("%d/%m/%Y") if y.ngay_tra_loi else ""} for y in muc],
    })


@bp.post("/")
def gui():
    """Gửi ý kiến mới (cần tên + SĐT). Ô 'website' là bẫy bot: bot điền thì giả vờ thành công nhưng không lưu."""
    d = request.get_json(silent=True) or request.form
    loai, obj_id = str(d.get("loai", "")), d.get("id", "")

    if str(d.get("website", "")).strip():                               # honeypot
        return _json({"ok": True, "thong_bao": "Cảm ơn bạn. Ý kiến sẽ hiển thị sau khi được Khoa Dược duyệt."})
    if la_bot():
        return _loi("Yêu cầu không hợp lệ.", 400)
    try:
        giay = float(d.get("thoi_gian_dien", 0))
    except (TypeError, ValueError):
        giay = 0
    if giay < PH.MOI_PHUT_TOI_THIEU_DIEN_FORM:
        return _loi("Bạn gửi quá nhanh, vui lòng kiểm tra lại nội dung rồi gửi.", 400)

    obj = PH.lay_doi_tuong(loai, obj_id)
    if obj is None:
        return _loi("Không tìm thấy nội dung cần góp ý.", 404)
    ten, loi = PH.kiem_tra_ten(d.get("ten"))
    if loi:
        return _loi(loi)
    sdt = PH.chuan_hoa_sdt(d.get("sdt"))
    if not sdt:
        return _loi("Số điện thoại chưa đúng. Nhập 10 số, bắt đầu bằng số 0.")
    nd, loi = PH.kiem_tra_noi_dung(d.get("noi_dung"), PH.TOI_DA_BINH_LUAN)
    if loi:
        return _loi(loi)

    khoa = khoa_khach()
    if PH.qua_gioi_han(khoa, sdt):
        return _loi("Bạn gửi hơi nhiều ý kiến liên tiếp. Vui lòng đợi ít phút rồi gửi tiếp.", 429)
    if PH.trung_noi_dung(khoa, nd):
        return _loi("Bạn đã gửi nội dung này rồi, Khoa Dược sẽ duyệt sớm.", 409)

    yk = YKien(doi_tuong_loai=loai, doi_tuong_id=obj.id, doi_tuong_ten=PH.ten_doi_tuong(loai, obj),
               ten=ten, so_dien_thoai=sdt, noi_dung=nd, trang_thai="cho_duyet", khoa_khach=khoa)
    db.session.add(yk)
    db.session.flush()                                                       # có yk.id cho thông báo
    nhan = PH.DOI_TUONG[loai][2]
    TB.tao_cho_admin("y_kien_moi", f"Ý kiến mới: {yk.doi_tuong_ten}"[:200],
                     f"{ten}: {nd}".replace("\n", " "),
                     f"/admin/y-kien/?trang_thai=cho_duyet#yk-{yk.id}", khoa_gop=f"yk:{yk.id}")
    db.session.commit()
    return _json({"ok": True, "thong_bao": "Cảm ơn bạn. Ý kiến sẽ hiển thị sau khi được Khoa Dược duyệt."})
