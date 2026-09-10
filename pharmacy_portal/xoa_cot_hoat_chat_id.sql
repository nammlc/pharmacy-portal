-- Chạy file này 1 lần trên Neon SQL Editor để xoá cột hoat_chat_id cũ
-- (cột này không còn dùng trong code, chỉ chiếm dung lượng và tạo FK thừa)
-- ⚠️ Backup dữ liệu trước khi chạy nếu cần

-- Kiểm tra cột có tồn tại không trước khi xoá
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'danh_muc_thuoc' AND column_name = 'hoat_chat_id'
  ) THEN
    ALTER TABLE danh_muc_thuoc DROP COLUMN hoat_chat_id;
    RAISE NOTICE 'Đã xoá cột hoat_chat_id khỏi danh_muc_thuoc';
  ELSE
    RAISE NOTICE 'Cột hoat_chat_id không tồn tại trong danh_muc_thuoc (đã xoá trước đó)';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'nha_thuoc_bv' AND column_name = 'hoat_chat_id'
  ) THEN
    ALTER TABLE nha_thuoc_bv DROP COLUMN hoat_chat_id;
    RAISE NOTICE 'Đã xoá cột hoat_chat_id khỏi nha_thuoc_bv';
  ELSE
    RAISE NOTICE 'Cột hoat_chat_id không tồn tại trong nha_thuoc_bv (đã xoá trước đó)';
  END IF;
END $$;
