"""
Làm sạch HTML từ trình soạn thảo rich-text (Quill) trước khi lưu vào DB.

Trình soạn thảo cho phép người dùng gõ định dạng kiểu Word (in đậm, in
nghiêng, gạch chân, danh sách, tiêu đề, link...) - dữ liệu gửi lên server
là HTML thô. Vì đây là nội dung do người dùng nhập (kể cả khi chỉ có
admin mới nhập được), vẫn nên lọc bỏ các thẻ/thuộc tính nguy hiểm
(script, iframe, onclick...) trước khi lưu, để tránh rủi ro XSS lưu trữ
nếu tài khoản admin bị lộ hoặc vô tình dán nội dung độc hại từ nơi khác.
"""

import bleach

# Các thẻ được phép - khớp với thanh công cụ của trình soạn thảo
# (không cho phép "style"/màu chữ tuỳ ý để tránh phải xử lý CSS sanitizer)
_THE_DUOC_PHEP = [
    "p", "br", "strong", "b", "em", "i", "u", "s", "strike",
    "h1", "h2", "h3", "blockquote",
    "ul", "ol", "li",
    "a",
]

_THUOC_TINH_DUOC_PHEP = {
    "a": ["href", "target", "rel"],
}


def lam_sach_html(html_content):
    """
    Lọc HTML từ trình soạn thảo, chỉ giữ lại thẻ/thuộc tính an toàn.

    Trả về None nếu đầu vào rỗng/None, để không ghi đè dữ liệu bằng
    chuỗi rỗng một cách không cần thiết.
    """
    if html_content is None:
        return None
    html_content = html_content.strip()
    if not html_content:
        return None

    da_loc = bleach.clean(
        html_content,
        tags=_THE_DUOC_PHEP,
        attributes=_THUOC_TINH_DUOC_PHEP,
        strip=True,
    )
    return da_loc
