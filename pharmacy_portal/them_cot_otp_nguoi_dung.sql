-- Thêm cột cho xác thực 2 lớp OTP vào bảng nguoi_dung.
-- ỨNG DỤNG TỰ CHẠY việc này khi khởi động (app/utils/otp.py -> khoi_tao), nên thường KHÔNG cần chạy tay.
-- Chỉ dùng file này khi tài khoản DB của app không có quyền ALTER TABLE.

-- ===== PostgreSQL =====
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS totp_secret TEXT;
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS totp_bat BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS totp_buoc_cuoi BIGINT;
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS totp_ma_du_phong TEXT;
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS totp_ngay_bat TIMESTAMP;

-- ===== MySQL / MariaDB (bỏ comment, và xoá khối PostgreSQL ở trên) =====
-- ALTER TABLE nguoi_dung ADD COLUMN totp_secret TEXT,
--   ADD COLUMN totp_bat BOOLEAN NOT NULL DEFAULT 0,
--   ADD COLUMN totp_buoc_cuoi BIGINT NULL,
--   ADD COLUMN totp_ma_du_phong TEXT,
--   ADD COLUMN totp_ngay_bat DATETIME NULL;

-- ===== SQLite: mỗi lệnh chạy riêng =====
-- ALTER TABLE nguoi_dung ADD COLUMN totp_secret TEXT;
-- ALTER TABLE nguoi_dung ADD COLUMN totp_bat BOOLEAN NOT NULL DEFAULT 0;
-- ALTER TABLE nguoi_dung ADD COLUMN totp_buoc_cuoi BIGINT;
-- ALTER TABLE nguoi_dung ADD COLUMN totp_ma_du_phong TEXT;
-- ALTER TABLE nguoi_dung ADD COLUMN totp_ngay_bat DATETIME;
