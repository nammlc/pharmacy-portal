"""Tìm thuốc cùng hoạt chất bằng đúng 1 truy vấn cho bảng liên kết,
thay vì so sánh từng thuốc (mỗi thuốc sinh thêm 1 truy vấn -> trang rất chậm)."""
from collections import defaultdict

from app import db


def tim_thuoc_cung_hoat_chat(thuoc, model, bang_lien_ket, cot_thuoc, gioi_han=8):
    """Trả về tối đa `gioi_han` thuốc khác có đúng cùng tập hoạt chất với `thuoc`.

    - thuoc: đối tượng thuốc đang xem
    - model: lớp thuốc (DanhMucThuoc hoặc NhaThuocBV)
    - bang_lien_ket: bảng nhiều-nhiều thuốc <-> hoạt chất
    - cot_thuoc: tên cột khoá ngoại tới thuốc trong bảng liên kết
    """
    ids_cua_toi = {hc.id for hc in thuoc.hoat_chat_list}
    if not ids_cua_toi:
        return []

    # 1 truy vấn duy nhất lấy toàn bộ cặp (thuốc, hoạt chất)
    cot = bang_lien_ket.c
    cap = db.session.query(cot[cot_thuoc], cot.hoat_chat_id).all()

    ds_hoat_chat = defaultdict(set)
    for thuoc_id, hc_id in cap:
        ds_hoat_chat[thuoc_id].add(hc_id)

    ung_vien = [tid for tid, tap in ds_hoat_chat.items()
                if tap == ids_cua_toi and tid != thuoc.id]
    ung_vien.sort()
    ung_vien = ung_vien[:gioi_han]
    if not ung_vien:
        return []

    ket_qua = {t.id: t for t in model.query.filter(model.id.in_(ung_vien)).all()}
    return [ket_qua[i] for i in ung_vien if i in ket_qua]
