"""Lưu ảnh và tệp đính kèm NGAY TRÊN MÁY CHỦ (thay cho Cloudinary).

Cách hoạt động
--------------
* File nằm trong thư mục UPLOAD_DIR (mặc định: <dự án>/uploads, nên đặt ngoài thư mục code và sao lưu định kỳ).
* Trong database chỉ lưu đường dẫn TƯƠNG ĐỐI dạng  /uploads/<thư mục>/<tên file>  (đổi tên miền không hỏng).
* Route app/routes/anh.py phục vụ file; ảnh có thể xin bản thu nhỏ bằng ?w=480 (hoặc ?w=112&c=1 cho ảnh vuông).
  Bản thu nhỏ được tạo MỘT LẦN rồi lưu đệm trong UPLOAD_DIR/.cache (thay cho biến đổi tức thời của Cloudinary).

Module này không phụ thuộc database; chỉ dùng Pillow. Ngoài app context vẫn chạy được (đọc biến môi trường UPLOAD_DIR).
"""
import io
import os
import re
import uuid
from pathlib import Path
from urllib.parse import unquote

TIEN_TO_URL = "/uploads/"
DUOI_ANH = {"png", "jpg", "jpeg", "webp", "gif"}
DUOI_TEP = {"pdf", "doc", "docx", "xls", "xlsx", "zip"}
THU_MUC_CACHE = ".cache"

# Chỉ cho xin các cỡ này (tránh bị gọi hàng nghìn cỡ lạ làm đầy ổ đĩa). Cỡ khác được "kéo" về cỡ gần nhất.
RONG_CHO_PHEP = (112, 224, 480, 640, 720, 960, 1200, 1440, 1600, 1920, 2400)
CANH_VUONG_CHO_PHEP = (64, 96, 112, 128, 160, 224, 256)

MIME_ANH = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
MIME_TEP = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
}

_RE_DUONG_DAN = re.compile(r"^[A-Za-z0-9._\-/]+$")
MAX_PIXELS = 60_000_000          # chống "ảnh bom" (ảnh nhỏ file nhưng giải nén ra khổng lồ)


# --------------------------------------------------------------------------- đường dẫn
def thu_muc_goc() -> Path:
    """Thư mục gốc chứa mọi file: ưu tiên config của app, rồi biến môi trường UPLOAD_DIR, rồi <dự án>/uploads."""
    d = None
    try:
        from flask import current_app
        d = current_app.config.get("UPLOAD_DIR")
    except Exception:                      # ngoài app context
        d = None
    d = d or os.environ.get("UPLOAD_DIR")
    if not d:
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    return Path(d).resolve()


def la_url_local(url) -> bool:
    return isinstance(url, str) and url.startswith(TIEN_TO_URL)


def ten_an_toan(ten: str) -> str:
    """Chỉ giữ chữ không dấu, số, . _ - ; còn lại thành _ (tên file an toàn trên mọi hệ điều hành)."""
    ten = re.sub(r"[^A-Za-z0-9._\-]+", "_", ten or "").strip("._")
    return ten or "file"


def duong_dan_tu_url(url: str):
    """Đổi '/uploads/a/b.jpg?w=480' thành Path tuyệt đối trong UPLOAD_DIR. Trả None nếu đường dẫn không an toàn
    (có '..', bắt đầu bằng '.', ký tự lạ...). Không kiểm tra file có tồn tại hay không."""
    if not la_url_local(url):
        return None
    phan = unquote(url.split("?", 1)[0].split("#", 1)[0])[len(TIEN_TO_URL):]
    if not phan or phan.endswith("/") or not _RE_DUONG_DAN.match(phan):
        return None
    thanh_phan = phan.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in thanh_phan):
        return None
    goc = thu_muc_goc()
    dich = (goc / phan).resolve()
    try:
        dich.relative_to(goc)
    except ValueError:
        return None
    return dich


def url_tu_duong_dan(duong_dan_tuong_doi: str) -> str:
    return TIEN_TO_URL + duong_dan_tuong_doi.replace(os.sep, "/").lstrip("/")


def gan_nhat(gia_tri: int, tap) -> int:
    return min(tap, key=lambda x: abs(x - gia_tri))


def _ghi_nguyen_tu(dich: Path, du_lieu: bytes) -> None:
    """Ghi vào file tạm cùng thư mục rồi đổi tên: người xem không bao giờ thấy file ghi dở."""
    dich.parent.mkdir(parents=True, exist_ok=True)
    tam = dich.with_name(f".{dich.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(tam, "wb") as f:
            f.write(du_lieu)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tam, dich)
    finally:
        if tam.exists():
            try:
                tam.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------- ảnh
def _doc_bytes(file_object) -> bytes:
    nguon = getattr(file_object, "stream", file_object)
    try:
        nguon.seek(0)
    except Exception:
        pass
    return nguon.read()


def _mo_va_kiem_tra(du_lieu: bytes):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        Image.open(io.BytesIO(du_lieu)).verify()          # phát hiện file hỏng / không phải ảnh
        return Image.open(io.BytesIO(du_lieu))
    except Exception as e:
        raise ValueError("Tệp không phải ảnh hợp lệ hoặc bị hỏng.") from e


def luu_anh(file_object, folder: str, width: int = 800, height: int = 800, crop: str = "limit") -> str:
    """Lưu ảnh upload vào UPLOAD_DIR/<folder>/ và trả về URL '/uploads/<folder>/<tên>.<đuôi>'.
    crop='limit': chỉ thu nhỏ, giữ tỉ lệ (như Cloudinary c_limit); crop='fill': cắt giữa cho đúng khung (c_fill).
    Đuôi file theo ĐỊNH DẠNG THẬT của ảnh (không tin đuôi người dùng gõ)."""
    from PIL import Image, ImageOps
    du_lieu = _doc_bytes(file_object)
    if not du_lieu:
        raise ValueError("Tệp ảnh rỗng.")
    im = _mo_va_kiem_tra(du_lieu)
    dinh_dang = (im.format or "").upper()
    if dinh_dang not in ("JPEG", "PNG", "WEBP", "GIF"):
        raise ValueError("Chỉ chấp nhận file PNG, JPG, JPEG, WEBP, GIF.")

    ten_goc = f"{folder.split('/')[-1]}_{uuid.uuid4().hex[:12]}"
    if dinh_dang == "GIF":
        duoi, ket_qua = "gif", du_lieu                      # giữ nguyên GIF (có thể là ảnh động)
    else:
        im = ImageOps.exif_transpose(im)
        if crop == "fill":
            im = ImageOps.fit(im, (int(width), int(height)), Image.LANCZOS)
        else:
            im.thumbnail((int(width), int(height)), Image.LANCZOS)
        bo = io.BytesIO()
        if dinh_dang == "JPEG":
            duoi = "jpg"
            im.convert("RGB").save(bo, "JPEG", quality=85, optimize=True, progressive=True)
        elif dinh_dang == "PNG":
            duoi = "png"
            im.save(bo, "PNG", optimize=True)
        else:
            duoi = "webp"
            im.save(bo, "WEBP", quality=85)
        ket_qua = bo.getvalue()

    thu_muc = folder.strip("/")
    _ghi_nguyen_tu(thu_muc_goc() / thu_muc / f"{ten_goc}.{duoi}", ket_qua)
    return url_tu_duong_dan(f"{thu_muc}/{ten_goc}.{duoi}")


def ban_thu_nho(duong_dan_goc: Path, rong: int, vuong: bool = False):
    """Trả Path file WebP đã thu nhỏ (tạo nếu chưa có). Không phóng to ảnh nhỏ hơn cỡ xin. GIF → None (dùng ảnh gốc)."""
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if duong_dan_goc.suffix.lower() == ".gif":
        return None
    goc = thu_muc_goc()
    tuong_doi = duong_dan_goc.relative_to(goc).as_posix()
    kieu = f"{int(rong)}{'s' if vuong else 'w'}"
    dich = goc / THU_MUC_CACHE / kieu / (tuong_doi + ".webp")
    try:
        if dich.is_file() and dich.stat().st_mtime >= duong_dan_goc.stat().st_mtime:
            return dich
    except OSError:
        pass

    with Image.open(duong_dan_goc) as im:
        im = ImageOps.exif_transpose(im)
        if vuong:
            im = ImageOps.fit(im, (int(rong), int(rong)), Image.LANCZOS)
        elif im.width > rong:
            im.thumbnail((int(rong), 100_000), Image.LANCZOS)
        co_alpha = "A" in im.getbands() or "transparency" in im.info
        im = im.convert("RGBA" if co_alpha else "RGB")
        bo = io.BytesIO()
        im.save(bo, "WEBP", quality=82, method=4)
    _ghi_nguyen_tu(dich, bo.getvalue())
    return dich


# --------------------------------------------------------------------------- tệp đính kèm
_MAGIC_TEP = {"pdf": (b"%PDF",), "zip": (b"PK\x03\x04", b"PK\x05\x06"), "docx": (b"PK\x03\x04",), "xlsx": (b"PK\x03\x04",)}


def luu_tep(file_object, folder: str, duoi: str, tien_to: str = "bai_viet_dinh_kem") -> str:
    """Lưu tệp đính kèm (PDF, Word, Excel, ZIP) và trả URL '/uploads/<folder>/<tên>'.
    PDF/ZIP/DOCX/XLSX được kiểm tra 'chữ ký' đầu file để không nhận file giả mạo đuôi."""
    duoi = duoi.lower().lstrip(".")
    if duoi not in DUOI_TEP:
        raise ValueError("Chỉ chấp nhận file PDF, DOC, DOCX, XLS, XLSX, ZIP.")
    du_lieu = _doc_bytes(file_object)
    if not du_lieu:
        raise ValueError("Tệp rỗng.")
    magic = _MAGIC_TEP.get(duoi)
    if magic and not du_lieu.startswith(magic):
        raise ValueError("Nội dung tệp không khớp với đuôi file.")
    ten = f"{tien_to}_{uuid.uuid4().hex[:12]}.{duoi}"
    thu_muc = folder.strip("/")
    _ghi_nguyen_tu(thu_muc_goc() / thu_muc / ten, du_lieu)
    return url_tu_duong_dan(f"{thu_muc}/{ten}")


# --------------------------------------------------------------------------- xoá
def xoa(url: str) -> bool:
    """Xoá file (và mọi bản thu nhỏ đã lưu đệm). True nếu file gốc đã bị xoá."""
    p = duong_dan_tu_url(url)
    if p is None or not p.is_file():
        return False
    goc = thu_muc_goc()
    tuong_doi = p.relative_to(goc).as_posix()
    try:
        p.unlink()
    except OSError:
        return False
    cache = goc / THU_MUC_CACHE
    if cache.is_dir():
        for thu_muc_kieu in cache.iterdir():
            bien_the = thu_muc_kieu / (tuong_doi + ".webp")
            try:
                if bien_the.is_file():
                    bien_the.unlink()
            except OSError:
                pass
    return True
