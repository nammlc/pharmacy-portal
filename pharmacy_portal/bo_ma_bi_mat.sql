-- BỎ MÃ BÍ MẬT 6 SỐ của chat riêng: số điện thoại không còn là khoá duy nhất (1 SĐT có thể có nhiều cuộc trò chuyện, mỗi thiết bị một cuộc).
-- BẮT BUỘC chạy 1 lần trên DB đã có sẵn bảng khach_hang, TRƯỚC / CÙNG LÚC deploy bản mới; nếu không, người dùng mở cuộc trò chuyện
-- bằng SĐT đã từng dùng sẽ gặp lỗi "Hệ thống đang được cập nhật". DB mới tạo (khởi động lần đầu) không cần chạy file này.

-- ── PostgreSQL ──
DROP INDEX IF EXISTS ix_khach_hang_so_dien_thoai;                                -- unique index do ứng dụng tự tạo
ALTER TABLE khach_hang DROP CONSTRAINT IF EXISTS khach_hang_so_dien_thoai_key;   -- hoặc ràng buộc UNIQUE nếu tạo tay bằng them_bang_y_kien_chat.sql cũ
CREATE INDEX IF NOT EXISTS ix_khach_hang_so_dien_thoai ON khach_hang (so_dien_thoai);
ALTER TABLE khach_hang ALTER COLUMN pin_hash SET DEFAULT '';

-- ── MySQL (chạy thay cho khối PostgreSQL; tên index có thể khác, xem bằng SHOW INDEX FROM khach_hang) ──
-- ALTER TABLE khach_hang DROP INDEX ix_khach_hang_so_dien_thoai;
-- ALTER TABLE khach_hang ADD INDEX ix_khach_hang_so_dien_thoai (so_dien_thoai);
-- ALTER TABLE khach_hang ALTER COLUMN pin_hash SET DEFAULT '';

-- ── SQLite (demo) ── không sửa được ràng buộc tại chỗ: xoá file instance/*.db để ứng dụng tạo lại, hoặc tạo lại bảng khach_hang.
