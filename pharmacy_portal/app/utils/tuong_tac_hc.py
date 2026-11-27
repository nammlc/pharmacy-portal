"""
Tầng CSDL cho tương tác giữa 2 HOẠT CHẤT (bảng tuong_tac_hoat_chat).

Mọi chỗ thêm / sửa / nhập hàng loạt đều đi qua đây để dùng CHUNG một quy tắc chống trùng:
  - cặp (A,B) == (B,A): luôn lưu id nhỏ trước (TuongTacHoatChat.sap_xep);
  - hỏi trước (tim_cap) rồi mới lưu; nếu vẫn lọt (2 admin thêm cùng lúc) thì ràng buộc UNIQUE của CSDL
    chặn lại và ta báo "đã có" thay vì lỗi 500.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.models import HoatChat, TuongTacHoatChat
from app.utils import nhap_tuong_tac as nt
from app.utils.lam_sach_html import lam_sach_html


# ---------------------------------------------------------------------------
# Tìm / kiểm tra trùng
# ---------------------------------------------------------------------------
def tim_cap(a_id: int, b_id: int, bo_qua_id: int | None = None):
    """Cặp (a, b) đã có chưa (không phân biệt thứ tự)? bo_qua_id: bỏ qua chính bản ghi đang sửa."""
    a, b = TuongTacHoatChat.sap_xep(a_id, b_id)
    q = TuongTacHoatChat.query.filter_by(hoat_chat_a_id=a, hoat_chat_b_id=b)
    if bo_qua_id:
        q = q.filter(TuongTacHoatChat.id != bo_qua_id)
    return q.first()


def tai_hoat_chat_hien_co() -> dict:
    """khoá so khớp -> (id, tên). Hai hoạt chất chỉ khác hoa/thường/dấu thì lấy cái có id nhỏ hơn."""
    ket: dict = {}
    for hc in HoatChat.query.order_by(HoatChat.id).all():
        ket.setdefault(nt.khoa_ten(hc.ten_hoat_chat), (hc.id, hc.ten_hoat_chat))
    return ket


def tai_cap_hien_co() -> dict:
    """(id nhỏ, id lớn) -> id bản ghi."""
    return {(a, b): i for i, a, b in db.session.query(
        TuongTacHoatChat.id, TuongTacHoatChat.hoat_chat_a_id, TuongTacHoatChat.hoat_chat_b_id).all()}


def mo_ta_cap_trung(ban_ghi) -> str:
    return (f"Cặp «{ban_ghi.hoat_chat_a.ten_hoat_chat} + {ban_ghi.hoat_chat_b.ten_hoat_chat}» đã có "
            f"(mức độ {nt.NHAN_MUC_DO.get(ban_ghi.muc_do, ban_ghi.muc_do)}).")


# ---------------------------------------------------------------------------
# Thêm / sửa tay (form admin)
# ---------------------------------------------------------------------------
def luu_tay(form, ban_ghi=None):
    """Lưu từ TuongTacHoatChatForm. Trả về (bản_ghi | None, bản_ghi_trùng | None).

    - Hợp lệ: (bản_ghi, None)
    - Cặp đã có: (None, bản_ghi_đang_có) -> route hiển thị cảnh báo + nút "Mở bản ghi đã có để sửa".
    Caller đã kiểm tra hai hoạt chất khác nhau.
    """
    a, b = TuongTacHoatChat.sap_xep(form.hoat_chat_a_id.data, form.hoat_chat_b_id.data)
    trung = tim_cap(a, b, bo_qua_id=ban_ghi.id if ban_ghi else None)
    if trung:
        return None, trung

    moi = ban_ghi is None
    item = ban_ghi or TuongTacHoatChat()
    item.hoat_chat_a_id, item.hoat_chat_b_id = a, b
    item.muc_do = form.muc_do.data
    item.co_che = lam_sach_html(form.co_che.data)
    item.hau_qua_lam_sang = lam_sach_html(form.hau_qua_lam_sang.data)
    item.xu_tri = lam_sach_html(form.xu_tri.data)
    item.nguon_tham_khao = (form.nguon_tham_khao.data or "").strip() or None
    try:
        if moi:
            db.session.add(item)
        db.session.commit()
    except IntegrityError:               # ai đó vừa thêm cùng cặp trong lúc ta lưu
        db.session.rollback()
        return None, tim_cap(a, b, bo_qua_id=ban_ghi.id if ban_ghi else None)
    return item, None


# ---------------------------------------------------------------------------
# Nhập hàng loạt
# ---------------------------------------------------------------------------
def _noi_dung(r) -> dict:
    d = r.dong
    return dict(
        muc_do=r.muc_do_cuoi,
        co_che=lam_sach_html(nt.van_ban_sang_html(d.co_che)) or None,
        hau_qua_lam_sang=lam_sach_html(nt.van_ban_sang_html(d.hau_qua)) or None,
        xu_tri=lam_sach_html(nt.van_ban_sang_html(d.xu_tri)) or None,
        nguon_tham_khao=d.nguon or None,
    )


def thuc_hien_nhap(ke_hoach: "nt.KeHoach") -> dict:
    """Ghi kế hoạch đã duyệt vào CSDL trong MỘT giao dịch (lỗi -> không lưu gì cả)."""
    kq = {"hoat_chat_moi": 0, "tao": 0, "cap_nhat": 0, "bo_qua": 0, "trung_luc_nhap": 0}
    try:
        # 1) Hoạt chất mới (chỉ những cái thực sự dùng trong các cặp sẽ tạo)
        id_moi: dict[str, int] = {}
        for khoa, ten in ke_hoach.hoat_chat_moi.items():
            hc = HoatChat.query.filter(func.lower(HoatChat.ten_hoat_chat) == ten.lower()).first()
            if hc is None:
                hc = HoatChat(ten_hoat_chat=ten[:255])
                db.session.add(hc)
                db.session.flush()
                kq["hoat_chat_moi"] += 1
            id_moi[khoa] = hc.id

        def _id(e):
            return id_moi[e[1]] if e[0] == "moi" else e[1]

        # 2) Phân loại các dòng cần ghi
        can_tao, can_sua = [], []
        for r in ke_hoach.ket_qua:
            if r.trang_thai != nt.OK:
                continue
            if r.hanh_dong == "bo":
                kq["bo_qua"] += 1
                continue
            a, b = TuongTacHoatChat.sap_xep(_id(r.thuc_the_a), _id(r.thuc_the_b))
            (can_tao if r.hanh_dong == "tao" else can_sua).append((a, b, _noi_dung(r)))

        # 3) Ghi đè các cặp đã có (chỉ ghi các ô có dữ liệu trong file, KHÔNG xoá chữ cũ bằng ô trống)
        if can_sua:
            hien_co = {(x.hoat_chat_a_id, x.hoat_chat_b_id): x for x in TuongTacHoatChat.query.filter(
                TuongTacHoatChat.hoat_chat_a_id.in_(list({a for a, _, _ in can_sua}))).all()}
            for a, b, nd in can_sua:
                x = hien_co.get((a, b))
                if x is None:
                    can_tao.append((a, b, nd))
                    continue
                for cot, v in nd.items():
                    if v:
                        setattr(x, cot, v)
                kq["cap_nhat"] += 1

        # 4) Tạo cặp mới. Đường nhanh: ghi cả lô; nếu có ai vừa thêm trùng thì thử lại từng dòng.
        if can_tao:
            try:
                with db.session.begin_nested():
                    db.session.add_all(TuongTacHoatChat(hoat_chat_a_id=a, hoat_chat_b_id=b, **nd)
                                       for a, b, nd in can_tao)
                    db.session.flush()
                kq["tao"] += len(can_tao)
            except IntegrityError:
                for a, b, nd in can_tao:
                    try:
                        with db.session.begin_nested():
                            db.session.add(TuongTacHoatChat(hoat_chat_a_id=a, hoat_chat_b_id=b, **nd))
                            db.session.flush()
                        kq["tao"] += 1
                    except IntegrityError:
                        kq["trung_luc_nhap"] += 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return kq
