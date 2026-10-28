"""Tạo câu SQL để đặt mã bảo mật 6 số của cổng admin thẳng vào database (vd Neon SQL Editor).

Cách dùng (chạy trên máy của bạn, mã không bị gửi đi đâu):
    python tao_sql_ma_bao_mat.py            # sẽ hỏi mã (gõ không hiện)
    python tao_sql_ma_bao_mat.py 482915     # hoặc truyền thẳng mã (sẽ lưu trong lịch sử lệnh)
Rồi copy toàn bộ SQL in ra, dán vào Neon > SQL Editor > Run.
Database chỉ lưu BĂM của mã, không lưu chính mã.
"""
import getpass
import hashlib
import re
import secrets
import sys
from datetime import datetime, timezone

_DAY = "0123456789"


def pin_yeu(pin):
    return (len(set(pin)) == 1 or pin in _DAY or pin in _DAY[::-1] or pin in (_DAY + _DAY)
            or pin[:2] * 3 == pin or pin[:3] * 2 == pin)


def bam(pin):
    try:                                           # dùng đúng hàm của Flask nếu đã cài
        from werkzeug.security import generate_password_hash
        return generate_password_hash(pin)
    except ImportError:                            # không có Flask: tự tạo cùng định dạng pbkdf2
        muoi = secrets.token_hex(8)
        lap = 600000
        h = hashlib.pbkdf2_hmac("sha256", pin.encode(), muoi.encode(), lap).hex()
        return f"pbkdf2:sha256:{lap}${muoi}${h}"


def main():
    pin = sys.argv[1] if len(sys.argv) > 1 else getpass.getpass("Nhập mã bảo mật 6 chữ số: ")
    pin = pin.strip()
    if not re.fullmatch(r"\d{6}", pin):
        sys.exit("Mã phải gồm đúng 6 chữ số.")
    if pin_yeu(pin):
        sys.exit("Mã quá dễ đoán (vd 123456, 111111, 121212). Chọn mã khác.")
    h = bam(pin).replace("'", "''")
    bay_gio = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    print(f"""-- Dán đoạn này vào Neon > SQL Editor rồi bấm Run
CREATE TABLE IF NOT EXISTS cai_dat_he_thong (
    khoa VARCHAR(80) PRIMARY KEY, gia_tri TEXT, ngay_cap_nhat TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cong_bao_mat_lan_sai (
    id SERIAL PRIMARY KEY, ip VARCHAR(64), thoi_gian TIMESTAMP NOT NULL
);

INSERT INTO cai_dat_he_thong (khoa, gia_tri, ngay_cap_nhat) VALUES
    ('admin_gate_pin_hash',  '{h}', NOW()),
    ('admin_gate_changed_at', '{bay_gio}', NOW())
ON CONFLICT (khoa) DO UPDATE SET gia_tri = EXCLUDED.gia_tri, ngay_cap_nhat = NOW();

-- Tăng "phiên bản mã" để mọi trình duyệt đang mở cổng phải nhập lại mã mới
INSERT INTO cai_dat_he_thong (khoa, gia_tri, ngay_cap_nhat) VALUES ('admin_gate_version', '1', NOW())
ON CONFLICT (khoa) DO UPDATE
    SET gia_tri = (COALESCE(NULLIF(cai_dat_he_thong.gia_tri, ''), '0')::int + 1)::text, ngay_cap_nhat = NOW();""")


if __name__ == "__main__":
    main()
