-- Bảng nhật ký truy cập. App tự tạo bảng này khi khởi động (db create checkfirst);
-- file này chỉ dùng nếu muốn tạo thủ công. Cú pháp PostgreSQL (Neon); MySQL đổi SERIAL -> INT AUTO_INCREMENT.
CREATE TABLE IF NOT EXISTS nhat_ky (
    id              SERIAL PRIMARY KEY,
    thoi_gian       TIMESTAMP NOT NULL,
    loai            VARCHAR(30) NOT NULL,
    ip              VARCHAR(64),
    cookie_id       VARCHAR(40),
    nguoi_dung_id   INTEGER,
    ten_nguoi_dung  VARCHAR(100),
    phuong_thuc     VARCHAR(10),
    duong_dan       VARCHAR(500),
    tu_khoa         VARCHAR(500),
    hanh_dong       VARCHAR(30),
    doi_tuong       VARCHAR(80),
    doi_tuong_id    INTEGER,
    doi_tuong_ten   VARCHAR(255),
    mo_ta           VARCHAR(500),
    ma_trang_thai   INTEGER,
    trinh_duyet     VARCHAR(300)
);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_thoi_gian ON nhat_ky (thoi_gian);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_loai      ON nhat_ky (loai);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_ip        ON nhat_ky (ip);
CREATE INDEX IF NOT EXISTS ix_nhat_ky_cookie_id ON nhat_ky (cookie_id);
