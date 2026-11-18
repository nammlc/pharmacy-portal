"""Phục vụ ảnh / tệp đính kèm lưu trên máy chủ:  GET /uploads/<đường dẫn>[?w=480][&c=1]

* Ảnh: ?w=<cỡ> xin bản thu nhỏ (WebP, tạo 1 lần rồi lưu đệm); ?c=1 => cắt vuông w x w (dùng cho ảnh gợi ý).
* Tên file có chuỗi ngẫu nhiên và không bao giờ bị ghi đè => cho trình duyệt lưu đệm 1 năm (immutable).
* Chỉ phục vụ đúng các đuôi ảnh / tệp đính kèm đã định nghĩa; thư mục ẩn (.cache) và đường dẫn lạ -> 404.
* Tệp đính kèm (trừ PDF) luôn tải về, kèm nosniff, để file giả mạo không thể chạy như trang web trên tên miền này.
"""
from flask import Blueprint, abort, request, send_file

from app.utils import luu_tru_anh as LT

bp = Blueprint("anh", __name__)

_NAM = 31536000


@bp.get("/uploads/<path:duong_dan>")
def phuc_vu(duong_dan):
    p = LT.duong_dan_tu_url(LT.TIEN_TO_URL + duong_dan)
    if p is None or not p.is_file():
        abort(404)
    duoi = p.suffix.lower().lstrip(".")

    if duoi in LT.DUOI_ANH:
        mime = LT.MIME_ANH[duoi]
        rong = request.args.get("w", type=int)
        if rong and duoi != "gif":
            vuong = request.args.get("c") == "1"
            rong = LT.gan_nhat(rong, LT.CANH_VUONG_CHO_PHEP if vuong else LT.RONG_CHO_PHEP)
            try:
                bt = LT.ban_thu_nho(p, rong, vuong)
            except Exception:                 # tạo bản thu nhỏ lỗi => trả ảnh gốc, không làm hỏng trang
                bt = None
            if bt:
                p, mime = bt, "image/webp"
        resp = send_file(p, mimetype=mime, conditional=True, max_age=_NAM)
        resp.headers["Cache-Control"] = f"public, max-age={_NAM}, immutable"
    elif duoi in LT.DUOI_TEP:
        resp = send_file(p, mimetype=LT.MIME_TEP[duoi], conditional=True, max_age=_NAM,
                         as_attachment=(duoi != "pdf"), download_name=p.name)
        resp.headers["Cache-Control"] = f"public, max-age={_NAM}, immutable"
    else:
        abort(404)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp
