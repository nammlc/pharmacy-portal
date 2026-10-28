-- Bảng cho cổng mã bảo mật 6 số của trang admin. App tự tạo khi khởi động; file này chỉ dùng nếu muốn tạo thủ công.
-- Cú pháp PostgreSQL (Neon); MySQL đổi SERIAL -> INT AUTO_INCREMENT.
CREATE TABLE IF NOT EXISTS cai_dat_he_thong (
    khoa           VARCHAR(80) PRIMARY KEY,
    gia_tri        TEXT,
    ngay_cap_nhat  TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cong_bao_mat_lan_sai (
    id         SERIAL PRIMARY KEY,
    ip         VARCHAR(64),
    thoi_gian  TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_cong_bao_mat_lan_sai_ip        ON cong_bao_mat_lan_sai (ip);
CREATE INDEX IF NOT EXISTS ix_cong_bao_mat_lan_sai_thoi_gian ON cong_bao_mat_lan_sai (thoi_gian);
