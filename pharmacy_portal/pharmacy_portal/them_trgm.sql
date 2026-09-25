-- Chạy 1 lần trên Neon để bật fuzzy search nâng cao
-- Vào Neon SQL Editor và chạy file này

-- Bật extension trigram
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Index trigram cho danh_muc_thuoc
CREATE INDEX IF NOT EXISTS idx_dmt_ten_trgm
    ON danh_muc_thuoc USING gin (ten_biet_duoc gin_trgm_ops);

-- Index trigram cho nha_thuoc_bv
CREATE INDEX IF NOT EXISTS idx_ntbv_ten_trgm
    ON nha_thuoc_bv USING gin (ten_biet_duoc gin_trgm_ops);

-- Index trigram cho hoat_chat
CREATE INDEX IF NOT EXISTS idx_hc_ten_trgm
    ON hoat_chat USING gin (ten_hoat_chat gin_trgm_ops);

-- Index trigram cho thuoc
CREATE INDEX IF NOT EXISTS idx_thuoc_ten_trgm
    ON thuoc USING gin (ten_thuoc gin_trgm_ops);

-- Verify
SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';
