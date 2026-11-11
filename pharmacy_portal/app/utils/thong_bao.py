"""Thông báo cho admin (chuông ở thanh trên trang quản trị). Mỗi admin 1 dòng riêng, nên đọc / bỏ qua độc lập."""
import random
from datetime import datetime, timedelta

from sqlalchemy import func

from app import db
from app.models.models import NguoiDung, ThongBao

TOI_DA_HIEN = 8


def _admin_dang_hoat_dong():
    return NguoiDung.query.filter(db.or_(NguoiDung.dang_hoat_dong.is_(True), NguoiDung.dang_hoat_dong.is_(None))).all()


def tao_cho_admin(loai, tieu_de, noi_dung, url, khoa_gop=None):
    """Tạo thông báo cho MỌI admin đang hoạt động. Cùng khoa_gop mà admin chưa đọc → gộp (tăng số lượng, đẩy lên đầu)
    thay vì tạo thêm dòng, để 1 khách nhắn 10 tin không làm ngập chuông. Chạy trong transaction của nơi gọi (chưa commit)."""
    bay_gio = datetime.utcnow()
    if random.random() < 0.02:                                  # thỉnh thoảng dọn thông báo ĐÃ ĐỌC cũ hơn 90 ngày
        ThongBao.query.filter(ThongBao.da_doc.is_(True), ThongBao.ngay_tao < bay_gio - timedelta(days=90)).delete(synchronize_session=False)
    for a in _admin_dang_hoat_dong():
        cu = (ThongBao.query.filter_by(nguoi_nhan_id=a.id, khoa_gop=khoa_gop, da_doc=False).first() if khoa_gop else None)
        if cu:
            cu.so_luong = (cu.so_luong or 1) + 1
            cu.tieu_de, cu.noi_dung, cu.url, cu.ngay_tao = tieu_de[:200], (noi_dung or "")[:300], url, bay_gio
        else:
            db.session.add(ThongBao(nguoi_nhan_id=a.id, loai=loai, tieu_de=tieu_de[:200], noi_dung=(noi_dung or "")[:300],
                                    url=url, khoa_gop=khoa_gop, ngay_tao=bay_gio))


def dem_chua_doc(admin_id) -> int:
    return db.session.query(func.count(ThongBao.id)).filter(ThongBao.nguoi_nhan_id == admin_id,
                                                            ThongBao.da_doc.is_(False)).scalar() or 0


def gan_day(admin_id, n=TOI_DA_HIEN):
    return (ThongBao.query.filter_by(nguoi_nhan_id=admin_id).order_by(ThongBao.da_doc.asc(), ThongBao.ngay_tao.desc())
            .limit(n).all())


def danh_dau_da_doc(admin_id, thong_bao_id=None):
    """Đánh dấu 1 thông báo (hoặc tất cả nếu thong_bao_id=None) của admin này là đã đọc. Trả số dòng đã đổi."""
    q = ThongBao.query.filter_by(nguoi_nhan_id=admin_id, da_doc=False)
    if thong_bao_id is not None:
        q = q.filter_by(id=thong_bao_id)
    n = q.update({"da_doc": True}, synchronize_session=False)
    db.session.commit()
    return n


def dong_bo_da_doc_theo_khoa(khoa_gop):
    """Việc đã được xử lý (duyệt ý kiến, trả lời khách) → thông báo tương ứng của MỌI admin thành đã đọc."""
    if khoa_gop:
        ThongBao.query.filter_by(khoa_gop=khoa_gop, da_doc=False).update({"da_doc": True}, synchronize_session=False)


def thanh_dict(tb, gio_vn):
    t = gio_vn(tb.ngay_tao)
    return {"id": tb.id, "loai": tb.loai, "tieu_de": tb.tieu_de, "noi_dung": tb.noi_dung or "", "so_luong": tb.so_luong or 1,
            "da_doc": bool(tb.da_doc), "gio": t.strftime("%H:%M %d/%m") if t else "", "url": tb.url or ""}
