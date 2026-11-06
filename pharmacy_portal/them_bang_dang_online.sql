-- Bảng đếm người đang online (ứng dụng TỰ tạo bảng này khi khởi động; file này để tạo tay nếu cần).
-- PostgreSQL (Neon):
CREATE TABLE IF NOT EXISTS dang_online (
    khoa     VARCHAR(64)  PRIMARY KEY,
    loai     VARCHAR(10)  NOT NULL,
    ten      VARCHAR(150),
    lan_cuoi TIMESTAMP    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_dang_online_loai     ON dang_online (loai);
CREATE INDEX IF NOT EXISTS ix_dang_online_lan_cuoi ON dang_online (lan_cuoi);
