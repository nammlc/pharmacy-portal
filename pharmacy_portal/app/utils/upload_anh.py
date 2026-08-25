"""
Tiện ích upload ảnh lên Cloudinary.
Logic: luôn xoá ảnh cũ TRƯỚC khi upload ảnh mới để tránh CDN cache giữ ảnh cũ.
"""
import cloudinary
import cloudinary.uploader
from flask import current_app
import uuid

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


def _ket_noi_cloudinary():
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


def xoa_anh_cloudinary(url_anh: str) -> bool:
    """Xoá ảnh khỏi Cloudinary dựa vào URL. Trả về True nếu thành công."""
    if not url_anh:
        return False
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
