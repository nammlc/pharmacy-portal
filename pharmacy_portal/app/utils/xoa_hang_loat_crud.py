"""
Tiện ích dùng chung cho chức năng "Xoá đã chọn" và "Xoá toàn bộ" ở các
trang danh sách CRUD trong khu vực quản trị.
"""
from sqlalchemy.exc import IntegrityError
from app import db


def lay_id_tu_form(request):
    """Đọc danh sách id được tick chọn từ form (checkbox name='ids')."""
    ids = []
    for gia_tri in request.form.getlist("ids"):
        try:
            ids.append(int(gia_tri))
        except (TypeError, ValueError):
            continue
    return ids


def xoa_theo_danh_sach_id(Model, ids, xoa_anh=None, kiem_tra_rang_buoc=None, hien_thi=None):
    """
    Xoá nhiều bản ghi theo danh sách id (xoá từng bản ghi một, tự bỏ qua
    và ghi nhận lại nếu bản ghi đó gặp lỗi ràng buộc dữ liệu -> không
    làm hỏng cả thao tác xoá hàng loạt).

    - xoa_anh: callable(item) -> None — dùng để dọn ảnh Cloudinary trước khi xoá record (nếu cần).
    - kiem_tra_rang_buoc: callable(item) -> str | None — trả về lý do KHÔNG xoá được
      (nếu có ràng buộc dữ liệu), hoặc None nếu xoá được bình thường.
    - hien_thi: callable(item) -> str — tên hiển thị cho item trong thông báo (mặc định: str(item)).

    Trả về (so_da_xoa, danh_sach_bo_qua) — danh_sach_bo_qua là list[(ten_hien_thi, ly_do)].
    """
    if not ids:
        return 0, []

    items = Model.query.filter(Model.id.in_(ids)).all()
    so_da_xoa = 0
    bo_qua = []

    for item in items:
        ten_hien_thi = hien_thi(item) if hien_thi else str(item)

        if kiem_tra_rang_buoc:
            ly_do = kiem_tra_rang_buoc(item)
            if ly_do:
                bo_qua.append((ten_hien_thi, ly_do))
                continue

        try:
            if xoa_anh:
                xoa_anh(item)
            db.session.delete(item)
            db.session.commit()
            so_da_xoa += 1
        except IntegrityError:
            db.session.rollback()
            bo_qua.append((ten_hien_thi, "vẫn còn dữ liệu khác liên kết tới"))

    return so_da_xoa, bo_qua


def xoa_toan_bo(Model, xoa_anh=None, kiem_tra_rang_buoc=None, hien_thi=None):
    """Xoá TẤT CẢ bản ghi hiện có trong bảng (bỏ qua bản ghi vướng ràng buộc nếu có kiểm tra)."""
    ids = [item.id for item in Model.query.with_entities(Model.id).all()]
    return xoa_theo_danh_sach_id(Model, ids, xoa_anh=xoa_anh, kiem_tra_rang_buoc=kiem_tra_rang_buoc, hien_thi=hien_thi)


def flash_ket_qua_xoa(flash, so_da_xoa, bo_qua, danh_tu="bản ghi"):
    """Hiển thị flash message tổng kết sau khi xoá hàng loạt / xoá toàn bộ."""
    if so_da_xoa:
        flash(f"Đã xoá {so_da_xoa} {danh_tu}.", "success")
    if bo_qua:
        ds = ", ".join(f'"{ten}" ({ly_do})' for ten, ly_do in bo_qua[:5])
        con_lai = f" và {len(bo_qua) - 5} mục khác" if len(bo_qua) > 5 else ""
        flash(f"Bỏ qua {len(bo_qua)} mục không thể xoá: {ds}{con_lai}.", "warning")
    if not so_da_xoa and not bo_qua:
        flash("Không có mục nào được chọn để xoá.", "warning")
