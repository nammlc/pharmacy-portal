"""
Tiện ích upload ảnh lên Cloudinary.
Dùng cho ảnh thuốc (folder: pharmacy/thuoc) và ảnh nhóm thuốc (folder: pharmacy/nhom_thuoc).
"""
import cloudinary
import cloudinary.uploader
from flask import current_app

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _ket_noi_cloudinary():
    """Khởi tạo kết nối Cloudinary từ config của Flask."""
    cloudinary.config(
        cloud_name=current_app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=current_app.config["CLOUDINARY_API_KEY"],
        api_secret=current_app.config["CLOUDINARY_API_SECRET"],
        secure=True,
    )


def _duoi_file_hop_le(ten_file: str) -> bool:
    return (
        "." in ten_file
        and ten_file.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def upload_anh_thuoc(file_object, public_id: str | None = None) -> str | None:
    """
    Upload ảnh thuốc lên Cloudinary.

    Args:
        file_object: FileStorage từ request.files
        public_id:   Tên định danh tuỳ chọn (vd: "thuoc_123")

    Returns:
        URL ảnh (secure_url) nếu thành công, None nếu lỗi.
    """
    if not file_object or not file_object.filename:
        return None
    if not _duoi_file_hop_le(file_object.filename):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    _ket_noi_cloudinary()
    options = {
        "folder": "pharmacy/thuoc",
        "transformation": [
            {"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
        ],
    }
    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True

    ket_qua = cloudinary.uploader.upload(file_object, **options)
    return ket_qua.get("secure_url")


def upload_anh_nhom_thuoc(file_object, public_id: str | None = None) -> str | None:
    """
    Upload ảnh nhóm thuốc lên Cloudinary.

    Args:
        file_object: FileStorage từ request.files
        public_id:   Tên định danh tuỳ chọn (vd: "nhom_5")

    Returns:
        URL ảnh (secure_url) nếu thành công, None nếu lỗi.
    """
    if not file_object or not file_object.filename:
        return None
    if not _duoi_file_hop_le(file_object.filename):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    _ket_noi_cloudinary()
    options = {
        "folder": "pharmacy/nhom_thuoc",
        "transformation": [
            {"width": 400, "height": 400, "crop": "fill", "gravity": "center", "quality": "auto"}
        ],
    }
    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True

    ket_qua = cloudinary.uploader.upload(file_object, **options)
    return ket_qua.get("secure_url")


def upload_anh_danh_muc_thuoc(file_object, public_id: str | None = None) -> str | None:
    """
    Upload ảnh thuốc (mục Danh mục thuốc) lên Cloudinary.

    Args:
        file_object: FileStorage từ request.files
        public_id:   Tên định danh tuỳ chọn (vd: "dmt_12")

    Returns:
        URL ảnh (secure_url) nếu thành công, None nếu lỗi.
    """
    if not file_object or not file_object.filename:
        return None
    if not _duoi_file_hop_le(file_object.filename):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    _ket_noi_cloudinary()
    options = {
        "folder": "pharmacy/danh_muc_thuoc",
        "transformation": [
            {"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
        ],
    }
    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True

    ket_qua = cloudinary.uploader.upload(file_object, **options)
    return ket_qua.get("secure_url")


def upload_anh_nha_thuoc_bv(file_object, public_id: str | None = None) -> str | None:
    """
    Upload ảnh thuốc (mục Nhà thuốc BV) lên Cloudinary.

    Args:
        file_object: FileStorage từ request.files
        public_id:   Tên định danh tuỳ chọn (vd: "ntbv_12")

    Returns:
        URL ảnh (secure_url) nếu thành công, None nếu lỗi.
    """
    if not file_object or not file_object.filename:
        return None
    if not _duoi_file_hop_le(file_object.filename):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    _ket_noi_cloudinary()
    options = {
        "folder": "pharmacy/nha_thuoc_bv",
        "transformation": [
            {"width": 800, "height": 800, "crop": "limit", "quality": "auto"}
        ],
    }
    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True

    ket_qua = cloudinary.uploader.upload(file_object, **options)
    return ket_qua.get("secure_url")


def xoa_anh_cloudinary(url_anh: str) -> bool:
    """
    Xoá ảnh khỏi Cloudinary dựa vào URL.

    Returns:
        True nếu xoá thành công.
    """
    if not url_anh:
        return False
    try:
        _ket_noi_cloudinary()
        # Lấy public_id từ URL: ...pharmacy/thuoc/abc123
        phan = url_anh.rsplit("/upload/", 1)
        if len(phan) < 2:
            return False
        public_id_raw = phan[1].rsplit(".", 1)[0]      # bỏ đuôi .jpg / .png
        # Nếu có version (v1234567/) thì bỏ qua
        if public_id_raw.startswith("v") and "/" in public_id_raw:
            public_id_raw = public_id_raw.split("/", 1)[1]
        cloudinary.uploader.destroy(public_id_raw)
        return True
    except Exception:
        return False
