-- Thêm cột email cho chức năng "Quên mật khẩu" (PostgreSQL / Neon).
-- Chạy 1 lần trong Neon > SQL Editor TRƯỚC khi deploy code mới. Chạy lại nhiều lần vẫn an toàn.
ALTER TABLE nguoi_dung ADD COLUMN IF NOT EXISTS email VARCHAR(255);
CREATE UNIQUE INDEX IF NOT EXISTS ix_nguoi_dung_email ON nguoi_dung (email);

-- Gán email cho tài khoản admin hiện có (sửa lại tên đăng nhập + email thật của bạn):
-- UPDATE nguoi_dung SET email = 'email-cua-ban@gmail.com' WHERE ten_dang_nhap = 'admin';
