-- Trang Bài viết nay chỉ có 3 slide ưu tiên (mức 1, 2, 3). Bài đang để mức 4 không còn vào slide.
-- Chạy 1 lần trên Neon nếu muốn dọn mức 4 cũ (không bắt buộc: mức 4 chỉ đơn giản bị bỏ qua).
UPDATE bai_viet SET do_uu_tien = NULL WHERE do_uu_tien > 3;
