"""
Toàn bộ app lưu thời gian trong CSDL theo UTC (datetime.utcnow()) để tránh
rắc rối khi server chạy ở múi giờ khác nhau. Hàm ở đây CHỈ dùng để chuyển
sang giờ Việt Nam (GMT+7) khi hiển thị ra giao diện - không dùng khi lưu.
"""

from datetime import timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _MUI_GIO_VN = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:
    # Phòng khi môi trường thiếu dữ liệu tzdata hệ thống - VN không có giờ
    # mùa hè nên lệch cố định +7 luôn đúng, dùng làm phương án dự phòng.
    _MUI_GIO_VN = timezone(timedelta(hours=7))


def gio_vn(dt):
    """Chuyển 1 datetime naive (đang lưu theo UTC) sang giờ Việt Nam.
    Dùng làm bộ lọc Jinja: {{ (item.ngay_tao | gio_vn).strftime('%d/%m/%Y %H:%M') }}
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_MUI_GIO_VN)
