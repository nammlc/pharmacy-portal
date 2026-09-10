"""
Tiện ích sinh slug (chuỗi dùng trong URL) từ tiếng Việt có dấu.
Dùng cho bài viết / danh mục bài viết: vd "Thông báo nghỉ lễ" -> "thong-bao-nghi-le".
"""
import re
import unicodedata


def tao_slug(chuoi: str) -> str:
    """Chuyển 1 chuỗi tiếng Việt bất kỳ thành slug chữ thường, không dấu,
    cách nhau bằng dấu gạch ngang."""
    if not chuoi:
        return ""
    chuoi = chuoi.strip().lower()
    chuoi = chuoi.replace("đ", "d")
    # Tách dấu ra khỏi ký tự gốc rồi loại bỏ (NFD: ký tự gốc + dấu riêng)
    chuoi = unicodedata.normalize("NFD", chuoi)
    chuoi = "".join(ky_tu for ky_tu in chuoi if unicodedata.category(ky_tu) != "Mn")
    chuoi = re.sub(r"[^a-z0-9\s-]", "", chuoi)
    chuoi = re.sub(r"[\s_-]+", "-", chuoi).strip("-")
    return chuoi or "muc"


def tao_slug_duy_nhat(Model, chuoi: str, item_id: int | None = None, cot: str = "slug") -> str:
    """Sinh slug duy nhất cho 1 bản ghi của Model (tự thêm hậu tố -2, -3... nếu bị trùng).

    - item_id: id của bản ghi đang sửa (để loại trừ chính nó khi kiểm tra trùng).
    - cot: tên cột slug trên Model.
    """
    slug_goc = tao_slug(chuoi)
    slug = slug_goc
    dem = 2
    while True:
        query = Model.query.filter(getattr(Model, cot) == slug)
        if item_id:
            query = query.filter(Model.id != item_id)
        if not query.first():
            return slug
        slug = f"{slug_goc}-{dem}"
        dem += 1
