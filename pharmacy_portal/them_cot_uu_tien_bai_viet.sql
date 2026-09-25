-- =============================================================================
-- Migration: Thêm cột mức độ ưu tiên hiển thị cho bài viết
-- Chạy 1 lần trên Neon SQL Editor (sau khi đã chạy tao_bang_bai_viet.sql)
-- =============================================================================

ALTER TABLE bai_viet ADD COLUMN IF NOT EXISTS do_uu_tien INTEGER;

-- Verify
SELECT id, tieu_de, do_uu_tien FROM bai_viet WHERE do_uu_tien IS NOT NULL ORDER BY do_uu_tien;
