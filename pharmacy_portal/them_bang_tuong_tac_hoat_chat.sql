-- Tương tác thuốc theo cặp HOẠT CHẤT. Chạy 1 lần trên Neon (SQL Editor) TRƯỚC khi dùng tính năng mới.
-- An toàn khi chạy lại (IF NOT EXISTS). Không đụng tới bảng cũ tuong_tac_thuoc.
--
-- Quy ước: luôn lưu hoat_chat_a_id < hoat_chat_b_id, nên (A,B) và (B,A) là MỘT cặp.
-- UNIQUE + CHECK bên dưới là chốt chặn cuối cùng chống trùng, dù code có sót.
-- (Kiểu muc_do_enum thường đã có sẵn từ bảng tuong_tac_thuoc cũ; khối DO bên dưới tạo nếu chưa có.)

DO $$ BEGIN
    CREATE TYPE muc_do_enum AS ENUM ('nhe', 'trung_binh', 'nang', 'chong_chi_dinh');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS tuong_tac_hoat_chat (
    id                SERIAL PRIMARY KEY,
    hoat_chat_a_id    INTEGER NOT NULL REFERENCES hoat_chat(id) ON DELETE CASCADE,
    hoat_chat_b_id    INTEGER NOT NULL REFERENCES hoat_chat(id) ON DELETE CASCADE,
    muc_do            muc_do_enum NOT NULL DEFAULT 'trung_binh',
    co_che            TEXT,
    hau_qua_lam_sang  TEXT,
    xu_tri            TEXT,
    nguon_tham_khao   VARCHAR(255),
    ngay_cap_nhat     TIMESTAMP,
    CONSTRAINT uq_tuong_tac_hc_cap UNIQUE (hoat_chat_a_id, hoat_chat_b_id),
    CONSTRAINT ck_tuong_tac_hc_thu_tu CHECK (hoat_chat_a_id < hoat_chat_b_id)
);

CREATE INDEX IF NOT EXISTS ix_tuong_tac_hoat_chat_hoat_chat_a_id ON tuong_tac_hoat_chat (hoat_chat_a_id);
CREATE INDEX IF NOT EXISTS ix_tuong_tac_hoat_chat_hoat_chat_b_id ON tuong_tac_hoat_chat (hoat_chat_b_id);
