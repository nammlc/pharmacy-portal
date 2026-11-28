"""
Tiện ích upload ảnh: Cloudinary (mặc định) HOẶC lưu ngay trên máy chủ.

Chọn bằng cấu hình ANH_LUU_TRU = "cloudinary" | "local" (xem config.py). Ở chế độ "local", ảnh được lưu trong
UPLOAD_DIR và trong database chỉ có đường dẫn /uploads/... (xem app/utils/luu_tru_anh.py). Mọi hàm bên dưới giữ NGUYÊN TÊN
và chữ ký cũ nên các route admin không phải sửa. Xoá ảnh / tạo bản thu nhỏ tự nhận biết URL Cloudinary hay /uploads/...
Logic Cloudinary: luôn xoá ảnh cũ TRƯỚC khi upload ảnh mới để tránh CDN cache giữ ảnh cũ.
"""
try:                                   # thư viện cloudinary là TUỲ CHỌN khi đã chuyển hẳn sang lưu trên máy chủ
    import cloudinary
    import cloudinary.uploader
except ImportError:                    # pragma: no cover
    cloudinary = None
from flask import current_app
import re
import uuid

from app.utils import luu_tru_anh as LT

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _che_do_local() -> bool:
    try:
        return str(current_app.config.get("ANH_LUU_TRU", "cloudinary")).strip().lower() == "local"
    except RuntimeError:               # ngoài app context
        return False


def _ket_noi_cloudinary():
    if cloudinary is None:
        raise RuntimeError("Chưa cài thư viện cloudinary (pip install cloudinary) mà ANH_LUU_TRU đang là 'cloudinary'.")
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def _duoi_file_hop_le(ten_file: str) -> bool:
    return "." in ten_file and ten_file.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _lay_public_id_tu_url(url_anh: str) -> str | None:
    """Trích public_id từ Cloudinary URL để xoá."""
    if not url_anh:
        return None
    try:
        phan = url_anh.rsplit("/upload/", 1)
        if len(phan) < 2:
            return None
        public_id_raw = phan[1].rsplit(".", 1)[0]
        if public_id_raw.startswith("v") and "/" in public_id_raw:
            public_id_raw = public_id_raw.split("/", 1)[1]
        return public_id_raw
    except Exception:
        return None


def anh_thu_nho(url_anh: str, canh: int = 112) -> str:
    """URL ảnh vuông thu nhỏ cho danh sách gợi ý (tải nhanh trên điện thoại).
    Ảnh Cloudinary dạng .../upload/v123/... → chèn biến đổi c_fill,w,h,f_auto,q_auto; ảnh ở nơi khác hoặc đã có sẵn
    biến đổi thì giữ nguyên. Rỗng → rỗng."""
    if not url_anh:
        return ""
    if LT.la_url_local(url_anh):                      # ảnh trên máy chủ: xin bản vuông thu nhỏ đã lưu đệm
        return url_anh if "?" in url_anh else f"{url_anh}?w={int(canh)}&c=1"
    if "res.cloudinary.com" not in url_anh or "/upload/" not in url_anh:
        return url_anh
    dau, duoi = url_anh.split("/upload/", 1)
    if not re.match(r"v\d+/", duoi):                 # đã có biến đổi / dạng lạ → không đụng vào
        return url_anh
    return f"{dau}/upload/c_fill,w_{canh},h_{canh},f_auto,q_auto/{duoi}"


def anh_theo_chieu_rong(url_anh: str, rong: int) -> str:
    """URL ảnh Cloudinary thu về chiều rộng `rong` px (tự chọn WebP/AVIF + chất lượng tối ưu).
    Dùng cho ảnh nền lớn (hero) để điện thoại không phải tải ảnh 2400px. Ảnh không phải Cloudinary,
    hoặc đã có sẵn biến đổi → giữ nguyên."""
    if LT.la_url_local(url_anh):                      # ảnh trên máy chủ: xin bản rộng `rong` px đã lưu đệm
        return url_anh if "?" in url_anh else f"{url_anh}?w={int(rong)}"
    if not url_anh or "res.cloudinary.com" not in url_anh or "/upload/" not in url_anh:
        return url_anh or ""
    dau, duoi = url_anh.split("/upload/", 1)
    if not re.match(r"v\d+/", duoi):
        return url_anh
    return f"{dau}/upload/f_auto,q_auto,c_limit,w_{int(rong)}/{duoi}"


def xoa_anh_cloudinary(url_anh: str) -> bool:
    """Xoá ảnh (Cloudinary hoặc /uploads/... trên máy chủ) dựa vào URL. Trả về True nếu thành công."""
    if not url_anh:
        return False
    if LT.la_url_local(url_anh):
        return LT.xoa(url_anh)
    try:
        _ket_noi_cloudinary()
        public_id = _lay_public_id_tu_url(url_anh)
        if not public_id:
            return False
        ket_qua = cloudinary.uploader.destroy(public_id)
        return ket_qua.get("result") == "ok"
    except Exception:
        return False


def _upload_len_cloudinary(file_object, folder: str, url_cu: str | None = None,
                            width: int = 800, height: int = 800,
                            crop: str = "limit") -> str | None:
    """
    Upload ảnh mới lên Cloudinary.
    - Xoá ảnh cũ TRƯỚC khi upload để tránh CDN cache.
    - Dùng public_id ngẫu nhiên mỗi lần để Cloudinary không cache URL cũ.
    """
    if not file_object or not file_object.filename:
        return None
    if not _duoi_file_hop_le(file_object.filename):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    # Xoá ảnh cũ trước (nếu có)
    if url_cu:
        xoa_anh_cloudinary(url_cu)

    if _che_do_local():
        return LT.luu_anh(file_object, folder, width=width, height=height, crop=crop)

    _ket_noi_cloudinary()
    # Dùng UUID để đảm bảo URL mới luôn khác URL cũ → không bị cache
    public_id = f"{folder.split('/')[-1]}_{uuid.uuid4().hex[:12]}"
    ket_qua = cloudinary.uploader.upload(
        file_object,
        folder=folder,
        public_id=public_id,
        overwrite=False,
        transformation=[
            {"width": width, "height": height, "crop": crop, "quality": "auto"}
        ],
    )
    return ket_qua.get("secure_url")


def upload_anh_danh_muc_thuoc(file_object, url_cu: str | None = None) -> str | None:
    return _upload_len_cloudinary(file_object, "pharmacy/danh_muc_thuoc", url_cu=url_cu)


def upload_anh_nha_thuoc_bv(file_object, url_cu: str | None = None) -> str | None:
    return _upload_len_cloudinary(file_object, "pharmacy/nha_thuoc_bv", url_cu=url_cu)


def upload_anh_nhom_thuoc(file_object, url_cu: str | None = None) -> str | None:
    return _upload_len_cloudinary(file_object, "pharmacy/nhom_thuoc",
                                   url_cu=url_cu, width=400, height=400, crop="fill")


def upload_anh_thuoc(file_object, url_cu: str | None = None) -> str | None:
    return _upload_len_cloudinary(file_object, "pharmacy/thuoc", url_cu=url_cu)


def upload_anh_ve_chung_toi(file_object, url_cu: str | None = None) -> str | None:
    return _upload_len_cloudinary(file_object, "pharmacy/ve_chung_toi",
                                   url_cu=url_cu, width=1200, height=800, crop="fill")


def upload_anh_hero(file_object, url_cu: str | None = None) -> str | None:
    """Ảnh nền trang chủ cho MÁY TÍNH: giữ nguyên tỉ lệ (không cắt), tối đa 2400px chiều rộng."""
    return _upload_len_cloudinary(file_object, "pharmacy/hero",
                                   url_cu=url_cu, width=2400, height=1600, crop="limit")


def upload_anh_hero_mobile(file_object, url_cu: str | None = None) -> str | None:
    """Ảnh nền trang chủ cho ĐIỆN THOẠI: giữ nguyên tỉ lệ (không cắt), tối đa 1600px chiều rộng / 2400px chiều cao."""
    return _upload_len_cloudinary(file_object, "pharmacy/hero_mobile",
                                   url_cu=url_cu, width=1600, height=2400, crop="limit")


def upload_anh_bai_viet(file_object, url_cu: str | None = None) -> str | None:
    """Ảnh đại diện bài viết: GIỮ NGUYÊN TỈ LỆ, không cắt (chỉ thu nhỏ nếu cạnh dài hơn 1600px).
    Trước đây dùng crop='fill' 1200x800 nên ảnh bị cắt về 3:2 ngay lúc upload và phần bị cắt mất vĩnh viễn."""
    return _upload_len_cloudinary(file_object, "pharmacy/bai_viet",
                                   url_cu=url_cu, width=1600, height=1600, crop="limit")


def upload_anh_noi_dung(file_object) -> str | None:
    """Upload 1 ảnh MÔ TẢ được chèn giữa các đoạn văn trong nội dung bài viết
    (trình soạn thảo Quill). Khác ảnh đại diện: 1 bài viết có thể có NHIỀU
    ảnh loại này nên không có khái niệm "url_cu" để xoá — ảnh cũ (nếu bị gỡ
    khỏi nội dung khi sửa bài) chỉ đơn giản không còn được tham chiếu tới nữa.
    Giới hạn kích thước rộng hơn ảnh đại diện vì ảnh minh hoạ có thể cần nét hơn."""
    return _upload_len_cloudinary(file_object, "pharmacy/bai_viet_noi_dung",
                                   width=1600, height=1600, crop="limit")


# --------------------------------------------------------------------------
# Tệp đính kèm bài viết (PDF, Word, Excel, ZIP...) - upload dạng "raw" trên
# Cloudinary (không phải ảnh nên không qua transformation).
# --------------------------------------------------------------------------
_DUOI_TEP_DINH_KEM_HOP_LE = {"pdf", "doc", "docx", "xls", "xlsx", "zip"}


def _duoi_tep_hop_le(ten_file: str, duoi_hop_le: set) -> bool:
    return "." in ten_file and ten_file.rsplit(".", 1)[1].lower() in duoi_hop_le


def upload_tep_dinh_kem_bai_viet(file_object, url_cu: str | None = None):
    """Upload tệp đính kèm bài viết lên Cloudinary (resource_type='raw').
    Trả về tuple (url_moi, ten_file_goc) hoặc (None, None) nếu không có file."""
    if not file_object or not file_object.filename:
        return None, None
    ten_goc = file_object.filename
    if not _duoi_tep_hop_le(ten_goc, _DUOI_TEP_DINH_KEM_HOP_LE):
        raise ValueError("Chỉ chấp nhận file PDF, DOC, DOCX, XLS, XLSX, ZIP.")

    if url_cu:
        xoa_tep_dinh_kem_cloudinary(url_cu)

    duoi = ten_goc.rsplit(".", 1)[1].lower()
    if _che_do_local():
        return LT.luu_tep(file_object, "pharmacy/bai_viet_dinh_kem", duoi), ten_goc

    _ket_noi_cloudinary()
    public_id = f"bai_viet_dinh_kem_{uuid.uuid4().hex[:12]}.{duoi}"
    ket_qua = cloudinary.uploader.upload(
        file_object,
        folder="pharmacy/bai_viet_dinh_kem",
        public_id=public_id,
        resource_type="raw",
        overwrite=False,
    )
    return ket_qua.get("secure_url"), ten_goc


def xoa_tep_dinh_kem_cloudinary(url_tep: str) -> bool:
    """Xoá tệp đính kèm (resource_type='raw') khỏi Cloudinary dựa vào URL.
    Khác ảnh: với 'raw', public_id giữ nguyên phần đuôi file."""
    if not url_tep:
        return False
    if LT.la_url_local(url_tep):
        return LT.xoa(url_tep)
    try:
        _ket_noi_cloudinary()
        phan = url_tep.rsplit("/upload/", 1)
        if len(phan) < 2:
            return False
        public_id_raw = phan[1]
        if public_id_raw.startswith("v") and "/" in public_id_raw:
            public_id_raw = public_id_raw.split("/", 1)[1]
        ket_qua = cloudinary.uploader.destroy(public_id_raw, resource_type="raw")
        return ket_qua.get("result") == "ok"
    except Exception:
        return False
