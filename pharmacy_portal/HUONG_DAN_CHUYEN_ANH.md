# Chuyển ảnh từ Cloudinary về máy chủ (web chạy bằng Docker / Coolify)

Mục tiêu: **đủ ảnh, không lỗi, quay lại được.** Nguyên tắc: chỉ SAO CHÉP ảnh về, không xoá gì trên Cloudinary; chỉ sửa
database khi đủ 100% ảnh; luôn có file sao lưu để hoàn tác.

> **Quan trọng với Docker/Coolify:** file ghi vào bên trong container sẽ **mất mỗi lần deploy lại**. Vì vậy ảnh PHẢI nằm trên một
> *Persistent Storage* (ổ lưu trữ cố định) do Coolify gắn vào container. Không dùng `mkdir` trong container để chứa ảnh.

## Script quét những gì

Mọi cột chữ của mọi bảng (trừ `nhat_ky`): ảnh các mục thuốc/nhóm thuốc/danh mục/nhà thuốc, ảnh đại diện bài viết, **ảnh hero và
ảnh "Về chúng tôi" (bảng `cai_dat`)**, **ảnh chèn trong nội dung bài viết (HTML)** và **tệp đính kèm**. Ảnh ở nơi khác (Google...) giữ nguyên.

## Bước 0. Sao lưu database (bắt buộc)

Coolify → Project → resource **`pharmacy`** (Database) → tab **Backups** → tạo lịch sao lưu (nếu chưa có) rồi bấm chạy sao lưu ngay.
Kiểm tra có file mới, dung lượng > 0. (Chú ý chọn đúng database `pharmacy`, không phải `dashboard_kham_uu_tien`.)
Nên **tải file sao lưu về máy** làm bản dự phòng thứ hai.

## Bước 1. Tạo ổ lưu trữ cố định cho ảnh

Coolify → resource **`pharmacy-portal`** (Application) → tab **Persistent Storage** → thêm 1 mục:
- Kiểu **Volume Mount** (hoặc Directory Mount nếu muốn thấy thư mục ngay trên server để dễ sao lưu).
- **Destination path (trong container): `/data`**
- Volume name: `pharmacy-data` (đặt tuỳ ý).

Thư mục `/data` này chứa cả `uploads` (ảnh) lẫn `chuyen_anh` (file làm việc/sao lưu của script), nên cả hai đều không mất khi deploy.

## Bước 2. Biến môi trường

Application → tab **Environment Variables** → thêm:
```
UPLOAD_DIR=/data/uploads
```
(Chưa thêm `ANH_LUU_TRU`; mặc định vẫn là `cloudinary`, web chạy như cũ.) Bấm **Redeploy** để áp dụng ổ lưu trữ và biến.

## Bước 3. Kiểm tra ổ lưu trữ

Application → tab **Terminal** (hoặc menu trái **Terminal** → chọn container của `pharmacy-portal`), chạy:
```bash
mkdir -p /data/uploads && touch /data/uploads/thu.txt && echo GHI_DUOC && rm /data/uploads/thu.txt
df -h /data
```
Phải thấy `GHI_DUOC`. Để chắc ảnh không mất, bấm **Redeploy** thêm một lần rồi vào lại Terminal: `ls -la /data` vẫn còn thư mục `uploads`.

## Bước 4. Kiểm kê (chỉ đếm, không đổi gì)

Trong Terminal của container (đã có sẵn mọi biến môi trường của web, không cần cài gì thêm):
```bash
cd /app          # thư mục code (nếu khác, dùng: cd "$(dirname "$(find / -name chuyen_anh_tu_cloudinary.py 2>/dev/null | head -1)")")
python chuyen_anh_tu_cloudinary.py kiem-ke
```
Đầu kết quả in 4 dòng: **Database / Thư mục ảnh / Tài khoản Cloudinary / Thư mục làm việc**. Đọc kỹ: database phải là của `pharmacy`,
thư mục ảnh phải là `/data/uploads`. **Ghi lại "Tổng cộng N ảnh/tệp khác nhau".**

## Bước 5. Tải ảnh về (chưa đổi database)

```bash
nohup python chuyen_anh_tu_cloudinary.py tai-ve > /data/tai-ve.log 2>&1 &
tail -f /data/tai-ve.log          # Ctrl+C để thoát xem log; tiến trình vẫn chạy nền
```
Kết quả đúng: **"Tải xong: N thành công, 0 lỗi"** (N khớp bước 4) và "Database CHƯA bị thay đổi".
- Ảnh báo `[LỖI] ... HTTP 404` là ảnh đã chết sẵn trên Cloudinary; cần tự tìm bản gốc tải lại hoặc bỏ khỏi bài viết.
- Terminal bị ngắt / mất mạng: chạy lại đúng lệnh, ảnh đã tải sẽ không tải lại.

## Bước 6. Cho ảnh MỚI vào máy chủ

Environment Variables → thêm `ANH_LUU_TRU=local` → **Redeploy**. Từ giờ ảnh admin tải lên được lưu trong `/data/uploads`
(tự thu nhỏ như cũ). Làm bước này TRƯỚC bước 7 để không có ảnh mới nào còn nhảy lên Cloudinary.

## Bước 7. (Khuyến nghị) Thử trên bản sao database

Tạo database thử từ file sao lưu bước 0, trỏ web/script tạm vào đó, chạy bước 7–8 xong mới làm trên database thật.

## Bước 8. Áp dụng vào database

```bash
cd /app
python chuyen_anh_tu_cloudinary.py ap-dung
```
Script tải nốt ảnh phát sinh, **dừng nếu còn ảnh lỗi**, báo số ô sẽ sửa rồi hỏi: gõ `DONG Y`. Nó ghi file sao lưu giá trị cũ
`/data/chuyen_anh/sao_luu_db_<thời-gian>.json` rồi sửa database trong **một giao dịch** (lỗi giữa chừng = không đổi gì).
Ghi lại tên file sao lưu.

## Bước 9. Kiểm tra

```bash
python chuyen_anh_tu_cloudinary.py kiem-tra --goi-thu https://tracuuduoc-bvdktamduccauquan.com
```
Phải ra **"KẾT QUẢ: ĐẠT"** (0 Cloudinary còn lại, 0 file thiếu, mọi đường dẫn gọi qua web đều trả về ảnh). Sau đó xem bằng mắt: trang chủ
(hero PC + điện thoại), danh mục thuốc, nhà thuốc BV, bài viết có ảnh trong nội dung, tệp đính kèm, "Về chúng tôi". Trong admin:
đổi thử ảnh một thuốc và **chèn thử ảnh vào một bài viết mới** (phần làm sạch HTML cần xác nhận trên web thật).

## Bước 10. Nếu có sự cố

```bash
python chuyen_anh_tu_cloudinary.py hoan-tac /data/chuyen_anh/sao_luu_db_XXXX.json
```
Các ô quay về đường dẫn Cloudinary cũ (Cloudinary còn nguyên nên web chạy lại như trước). Nặng hơn thì khôi phục database từ file sao lưu bước 0.

## Sau khi ổn định

- **Sao lưu thư mục ảnh định kỳ.** Coolify chỉ sao lưu database, KHÔNG tự sao lưu volume ảnh. Dùng snapshot ổ đĩa của nhà cung cấp
  cloud hoặc cron trên server chép thư mục volume (thường `/var/lib/docker/volumes/<tên-volume>/_data`, hoặc thư mục đã chọn nếu dùng Directory Mount)
  sang nơi khác. Xoá resource trong Coolify có thể xoá luôn volume, nên cẩn thận.
- **Giữ tài khoản Cloudinary ít nhất 30 ngày** rồi mới xoá ảnh trên đó.

## Cách web phục vụ ảnh (khi cần chỉnh)

- Database lưu đường dẫn tương đối `/uploads/pharmacy/thuoc/thuoc_xxx.jpg` (đổi tên miền không hỏng).
- `?w=480` xin bản thu nhỏ WebP (tạo 1 lần rồi lưu đệm ở `UPLOAD_DIR/.cache`); `?w=112&c=1` là ảnh vuông. Chỉ nhận các cỡ
  `112, 224, 480, 640, 720, 960, 1200, 1440, 1600, 1920, 2400` (cỡ khác tự về cỡ gần nhất). Xoá `.cache` lúc nào cũng được.
- Trình duyệt lưu đệm ảnh 1 năm (tên file không bao giờ bị ghi đè). Tệp đính kèm (trừ PDF) luôn tải về, vì lý do an toàn.

## Giới hạn đã biết

- Chỉ hỗ trợ ảnh png/jpg/gif/webp và tệp pdf/doc/docx/xls/xlsx/zip; ảnh khác (svg, avif...) sẽ được báo lỗi để xử lý tay.
- Ảnh ở nơi khác (Google, trang khác) giữ nguyên, không tải về.
