"""
Chat riêng giữa khách và Khoa Dược. KHÔNG có mã bí mật: khách chỉ nhập họ tên + SĐT + tin nhắn.

SĐT KHÔNG được xác minh (không có SMS), nên SĐT chỉ là thông tin LIÊN HỆ cho Khoa Dược, KHÔNG dùng để vào xem cuộc trò chuyện
(nếu dùng thì ai biết số cũng đọc được, mà nội dung có thể chứa thông tin sức khoẻ). Thay vào đó:
  - mỗi cuộc trò chuyện (1 dòng KhachHang) gắn với THIẾT BỊ / trình duyệt tạo ra nó, qua cookie ĐÃ KÝ nhớ 30 ngày (không đoán / sửa được)
  - cùng 1 SĐT có thể có nhiều cuộc trò chuyện (mỗi thiết bị một cuộc); người khác nhập SĐT của bạn chỉ mở được cuộc trò chuyện MỚI, trống
  - giới hạn số cuộc trò chuyện mới theo thiết bị; SĐT đã bị admin chặn thì không mở cuộc mới được
  - admin chặn → mọi thiết bị của khách đó bị vô hiệu (phien_ver tăng)
"""
import random
from datetime import datetime, timedelta

from flask import current_app, g, request, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.models import ChatLanThu, KhachHang, TinNhanRieng
from app.utils import thong_bao as TB
from app.utils.online import khoa_khach
from app.utils.phan_hoi import (TOI_DA_TIN_NHAN, chuan_hoa_sdt, duong_dan_noi_bo, kiem_tra_noi_dung, kiem_tra_ten, lam_sach)

COOKIE = "pp_chat"
THOI_HAN_COOKIE = 30 * 24 * 3600
LOAI_TIN = {"ho_tro": "Hỗ trợ", "gop_y": "Góp ý", "bao_loi": "Báo lỗi thông tin"}
TIN_MOI_10_PHUT = 8
TIN_MOI_24_GIO = 60
TAO_MOI_TOI_DA_THIET_BI = 5           # số cuộc trò chuyện mới tối đa / thiết bị / 24 giờ


# ───────────────────────────── phiên đăng nhập của khách (cookie ký) ─────────────────────────────
def _tao_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="pp-khach-chat")


def cap_phien(resp, khach):
    token = _tao_serializer().dumps({"k": khach.id, "v": khach.phien_ver})
    resp.set_cookie(COOKIE, token, max_age=THOI_HAN_COOKIE, httponly=True, samesite="Lax",
                    secure=request.is_secure, path="/")
    return resp


def xoa_phien(resp):
    resp.delete_cookie(COOKIE, path="/")
    return resp


def khach_hien_tai():
    """Khách đang đăng nhập trên thiết bị này (hoặc None). Cookie sai / hết hạn / đã đổi mã / bị chặn → None."""
    if hasattr(g, "_khach_chat"):
        return g._khach_chat
    khach = None
    token = request.cookies.get(COOKIE)
    if token:
        try:
            d = _tao_serializer().loads(token, max_age=THOI_HAN_COOKIE)
            k = db.session.get(KhachHang, int(d.get("k")))
            if k and not k.bi_chan and k.phien_ver == d.get("v"):
                khach = k
        except (BadSignature, SignatureExpired, TypeError, ValueError):
            khach = None
    g._khach_chat = khach
    return khach


# ───────────────────────────── bắt đầu cuộc trò chuyện mới (không mã bí mật) ─────────────────────────────
def _so_lan(khoa, loai, phut):
    return ChatLanThu.query.filter(ChatLanThu.khoa == khoa, ChatLanThu.loai == loai,
                                   ChatLanThu.thoi_gian >= datetime.utcnow() - timedelta(minutes=phut)).count()


def _ghi_lan(khoa, loai):
    db.session.add(ChatLanThu(khoa=khoa, loai=loai))
    if random.random() < 0.02:                                  # thỉnh thoảng dọn các lượt thử cũ hơn 2 ngày để bảng không phình
        ChatLanThu.query.filter(ChatLanThu.thoi_gian < datetime.utcnow() - timedelta(days=2)).delete(synchronize_session=False)


def bat_dau(sdt_tho, ten_tho):
    """Mở 1 cuộc trò chuyện MỚI gắn với thiết bị này (không cần mã bí mật). Trả về (khach, loi). Hàm tự commit."""
    sdt = chuan_hoa_sdt(sdt_tho)
    if not sdt:
        return None, "Số điện thoại chưa đúng. Nhập 10 số, bắt đầu bằng số 0."
    ten, loi = kiem_tra_ten(ten_tho)
    if loi:
        return None, loi
    if KhachHang.query.filter_by(so_dien_thoai=sdt, bi_chan=True).first() is not None:
        return None, "Không thể mở cuộc trò chuyện với số điện thoại này."
    khoa = khoa_khach()
    if _so_lan(khoa, "tao_moi", 24 * 60) >= TAO_MOI_TOI_DA_THIET_BI:
        return None, "Thiết bị này đã mở quá nhiều cuộc trò chuyện hôm nay."
    khach = KhachHang(so_dien_thoai=sdt, ten=ten, pin_hash="")          # pin_hash: cột cũ, không còn dùng (giữ để khỏi phải đổi DB)
    db.session.add(khach)
    _ghi_lan(khoa, "tao_moi")
    try:
        db.session.commit()
    except IntegrityError:                                               # DB cũ còn ràng buộc UNIQUE trên số điện thoại → cần chạy bo_ma_bi_mat.sql
        db.session.rollback()
        current_app.logger.error("khach_hang.so_dien_thoai còn UNIQUE: hãy chạy bo_ma_bi_mat.sql")
        return None, "Hệ thống đang được cập nhật, vui lòng thử lại sau hoặc liên hệ Khoa Dược."
    return khach, None


# ───────────────────────────── tin nhắn ─────────────────────────────
def gui_tin_nhan(khach, noi_dung_tho, loai="ho_tro", ngu_canh=None, ngu_canh_url=None):
    """Khách gửi 1 tin nhắn cho Khoa Dược. Trả (TinNhanRieng | None, lỗi). Hàm tự commit; tạo thông báo cho admin."""
    nd, loi = kiem_tra_noi_dung(noi_dung_tho, TOI_DA_TIN_NHAN, cho_phep_link=True)
    if loi:
        return None, loi
    bay_gio = datetime.utcnow()
    n10 = TinNhanRieng.query.filter(TinNhanRieng.khach_id == khach.id, TinNhanRieng.tu == "khach",
                                    TinNhanRieng.ngay_tao >= bay_gio - timedelta(minutes=10)).count()
    n24 = TinNhanRieng.query.filter(TinNhanRieng.khach_id == khach.id, TinNhanRieng.tu == "khach",
                                    TinNhanRieng.ngay_tao >= bay_gio - timedelta(hours=24)).count()
    if n10 >= TIN_MOI_10_PHUT or n24 >= TIN_MOI_24_GIO:
        return None, "Bạn gửi hơi nhiều tin liên tiếp. Vui lòng đợi ít phút rồi gửi tiếp."
    if loai not in LOAI_TIN:
        loai = "ho_tro"
    tn = TinNhanRieng(khach_id=khach.id, tu="khach", noi_dung=nd, loai=loai,
                      ngu_canh=lam_sach(ngu_canh).replace("\n", " ")[:200] or None,
                      ngu_canh_url=duong_dan_noi_bo(ngu_canh_url),
                      da_doc_khach=True, da_doc_admin=False, ngay_tao=bay_gio)
    db.session.add(tn)
    khach.lan_cuoi = bay_gio
    tieu_de = f"{LOAI_TIN[loai]} từ {khach.ten}"
    TB.tao_cho_admin("tin_nhan_moi", tieu_de, nd.replace("\n", " "),
                     url_for("admin_tin_nhan.xem", khach_id=khach.id), khoa_gop=f"chat:{khach.id}")
    db.session.commit()
    return tn, None


def admin_tra_loi(khach, admin, noi_dung_tho):
    nd, loi = kiem_tra_noi_dung(noi_dung_tho, TOI_DA_TIN_NHAN, cho_phep_link=True)
    if loi:
        return None, loi
    bay_gio = datetime.utcnow()
    tn = TinNhanRieng(khach_id=khach.id, tu="admin", noi_dung=nd, loai="ho_tro", admin_id=admin.id,
                      da_doc_khach=False, da_doc_admin=True, ngay_tao=bay_gio)
    db.session.add(tn)
    TinNhanRieng.query.filter_by(khach_id=khach.id, tu="khach", da_doc_admin=False).update({"da_doc_admin": True})
    khach.lan_cuoi = bay_gio
    TB.dong_bo_da_doc_theo_khoa(f"chat:{khach.id}")        # đã có người trả lời → thông báo của mọi admin thành đã đọc
    db.session.commit()
    return tn, None


def danh_sach_tin(khach, sau_id=0, danh_dau_khach_da_doc=False, gioi_han=300):
    q = TinNhanRieng.query.filter(TinNhanRieng.khach_id == khach.id, TinNhanRieng.id > (sau_id or 0))
    tin = q.order_by(TinNhanRieng.id.asc()).limit(gioi_han).all()
    if danh_dau_khach_da_doc and any(t.tu == "admin" and not t.da_doc_khach for t in tin):
        TinNhanRieng.query.filter_by(khach_id=khach.id, tu="admin", da_doc_khach=False).update({"da_doc_khach": True})
        db.session.commit()
    return tin


def tin_thanh_dict(t, gio_vn, ten_admin=None):
    gio = gio_vn(t.ngay_tao)
    return {"id": t.id, "tu": t.tu, "noi_dung": t.noi_dung, "loai": t.loai, "ngu_canh": t.ngu_canh or "",
            "ngu_canh_url": t.ngu_canh_url or "", "gio": gio.strftime("%H:%M %d/%m/%Y") if gio else "",
            "ten": (ten_admin or "Khoa Dược") if t.tu == "admin" else ""}
