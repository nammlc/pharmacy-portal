-- Hỏi đáp công khai + chat riêng + thông báo admin (ứng dụng TỰ tạo các bảng này khi khởi động; file này để tạo tay nếu cần).
-- PostgreSQL:
CREATE TABLE IF NOT EXISTS khach_hang (
    id            SERIAL PRIMARY KEY,
    so_dien_thoai VARCHAR(15)  NOT NULL UNIQUE,
    ten           VARCHAR(100) NOT NULL,
    pin_hash      VARCHAR(255) NOT NULL,
    phien_ver     INTEGER      NOT NULL DEFAULT 1,
    so_lan_sai    INTEGER      NOT NULL DEFAULT 0,
    khoa_den      TIMESTAMP,
    bi_chan       BOOLEAN      NOT NULL DEFAULT FALSE,
    ngay_tao      TIMESTAMP    NOT NULL DEFAULT NOW(),
    lan_cuoi      TIMESTAMP
);
CREATE TABLE IF NOT EXISTS y_kien (
    id               SERIAL PRIMARY KEY,
    doi_tuong_loai   VARCHAR(10)  NOT NULL,
    doi_tuong_id     INTEGER      NOT NULL,
    doi_tuong_ten    VARCHAR(255),
    ten              VARCHAR(100) NOT NULL,
    so_dien_thoai    VARCHAR(15)  NOT NULL,
    noi_dung         TEXT         NOT NULL,
    trang_thai       VARCHAR(12)  NOT NULL DEFAULT 'cho_duyet',
    khoa_khach       VARCHAR(64),
    tra_loi          TEXT,
    nguoi_tra_loi_id INTEGER REFERENCES nguoi_dung(id) ON DELETE SET NULL,
    ngay_tra_loi     TIMESTAMP,
    nguoi_duyet_id   INTEGER REFERENCES nguoi_dung(id) ON DELETE SET NULL,
    ngay_duyet       TIMESTAMP,
    ngay_tao         TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_y_kien_doi_tuong ON y_kien (doi_tuong_loai, doi_tuong_id);
CREATE INDEX IF NOT EXISTS ix_y_kien_trang_thai ON y_kien (trang_thai);
CREATE INDEX IF NOT EXISTS ix_y_kien_khoa_khach ON y_kien (khoa_khach);
CREATE INDEX IF NOT EXISTS ix_y_kien_ngay_tao ON y_kien (ngay_tao);
CREATE TABLE IF NOT EXISTS tin_nhan_rieng (
    id            SERIAL PRIMARY KEY,
    khach_id      INTEGER      NOT NULL REFERENCES khach_hang(id) ON DELETE CASCADE,
    tu            VARCHAR(8)   NOT NULL,
    noi_dung      TEXT         NOT NULL,
    loai          VARCHAR(10)  NOT NULL DEFAULT 'ho_tro',
    ngu_canh      VARCHAR(200),
    ngu_canh_url  VARCHAR(300),
    admin_id      INTEGER REFERENCES nguoi_dung(id) ON DELETE SET NULL,
    da_doc_khach  BOOLEAN      NOT NULL DEFAULT FALSE,
    da_doc_admin  BOOLEAN      NOT NULL DEFAULT FALSE,
    ngay_tao      TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tin_nhan_rieng_khach ON tin_nhan_rieng (khach_id);
CREATE INDEX IF NOT EXISTS ix_tin_nhan_rieng_ngay_tao ON tin_nhan_rieng (ngay_tao);
CREATE TABLE IF NOT EXISTS thong_bao (
    id             SERIAL PRIMARY KEY,
    nguoi_nhan_id  INTEGER      NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    loai           VARCHAR(20)  NOT NULL,
    tieu_de        VARCHAR(200) NOT NULL,
    noi_dung       VARCHAR(300),
    url            VARCHAR(300),
    khoa_gop       VARCHAR(64),
    so_luong       INTEGER      NOT NULL DEFAULT 1,
    da_doc         BOOLEAN      NOT NULL DEFAULT FALSE,
    ngay_tao       TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_thong_bao_nguoi_nhan ON thong_bao (nguoi_nhan_id);
CREATE INDEX IF NOT EXISTS ix_thong_bao_khoa_gop ON thong_bao (khoa_gop);
CREATE INDEX IF NOT EXISTS ix_thong_bao_da_doc ON thong_bao (da_doc);
CREATE TABLE IF NOT EXISTS chat_lan_thu (
    id         SERIAL PRIMARY KEY,
    khoa       VARCHAR(64) NOT NULL,
    loai       VARCHAR(12) NOT NULL,
    thoi_gian  TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_chat_lan_thu_khoa ON chat_lan_thu (khoa);
CREATE INDEX IF NOT EXISTS ix_chat_lan_thu_thoi_gian ON chat_lan_thu (thoi_gian);
