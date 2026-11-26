-- Bảng thùng rác admin. App tự tạo bảng này khi khởi động (create checkfirst);
-- file này chỉ dùng nếu muốn tạo thủ công. Cú pháp PostgreSQL; MySQL đổi SERIAL -> INT AUTO_INCREMENT, TEXT giữ nguyên.
CREATE TABLE IF NOT EXISTS thung_rac (
    id             SERIAL PRIMARY KEY,
    loai           VARCHAR(30)  NOT NULL,
    doi_tuong_id   INTEGER      NOT NULL,
    ten            VARCHAR(300) NOT NULL,
    anh            VARCHAR(500),
    du_lieu        TEXT         NOT NULL,
    nguoi_xoa_id   INTEGER,
    ten_nguoi_xoa  VARCHAR(100),
    ngay_xoa       TIMESTAMP    NOT NULL,
    het_han        TIMESTAMP    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_thung_rac_loai    ON thung_rac (loai);
CREATE INDEX IF NOT EXISTS ix_thung_rac_ngay_xoa ON thung_rac (ngay_xoa);
CREATE INDEX IF NOT EXISTS ix_thung_rac_het_han ON thung_rac (het_han);
