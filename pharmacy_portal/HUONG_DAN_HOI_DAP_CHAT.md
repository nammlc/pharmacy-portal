# Hỏi đáp công khai · Chat riêng · Thông báo admin

## Có gì
| Chức năng | Ở đâu | Ghi chú |
|---|---|---|
| **Hỏi đáp / bình luận công khai** | Cuối trang chi tiết: Danh mục thuốc, Nhà thuốc BV, Thuốc tra cứu, Bài viết, Bài viết bệnh nhân | Cần **tên + SĐT**. Ý kiến ở trạng thái *chờ duyệt*, admin duyệt mới hiện. Chỉ hiện tên, **không bao giờ hiện SĐT**. Admin có thể trả lời công khai. |
| **Chat riêng tư** | Menu "💬 Hỗ trợ & góp ý" (`/ho-tro`) | Mỗi **số điện thoại = 1 tài khoản**, **không có mã bí mật**: khách nhập SĐT → số đã đăng ký thì hiện lại cuộc trò chuyện cũ, số mới thì tự đăng ký (cần họ tên). Thiết bị được nhớ 30 ngày bằng cookie đã ký. |
| **Báo lỗi thông tin** | Thanh vàng ở đầu trang Tương tác thuốc, Thuốc tiêm truyền, Tương hợp – Tương kỵ | Mở chat riêng, đính kèm sẵn trang bị báo lỗi. |
| **Chuông thông báo** | Thanh trên trang quản trị | Số chưa đọc + danh sách, tự cập nhật ~15 giây; trang "Thông báo" xem tất cả. Mỗi ý kiến mới = 1 thông báo; nhiều tin của cùng 1 khách gộp thành "×N". |
| **Quản trị** | Menu "Phản hồi": Hỏi đáp & bình luận · Tin nhắn riêng · Thông báo | Duyệt / từ chối / spam / xoá / trả lời / thao tác hàng loạt; chat với khách; chặn khách. Mọi thao tác ghi vào Nhật ký truy cập. |

## Lưu ý quyền riêng tư (không có mã bí mật)
SĐT không được xác minh bằng SMS, nên **ai biết số điện thoại đều xem được cuộc trò chuyện của số đó**. Đã giảm thiểu: mỗi thiết bị chỉ thử tối đa 30 lần / 15 phút và đăng ký tối đa 5 số mới / 24 giờ (chống dò hàng loạt số); số bị admin chặn thì không vào được; trang nhắc khách không gửi thông tin sức khoẻ cá nhân. Nếu cần bảo mật hơn, hãy thêm xác minh qua SMS/OTP hoặc mã bí mật.

## Chống spam
Giới hạn 3 ý kiến / 10 phút / thiết bị và 10 ý kiến / 24 giờ / SĐT · ô bẫy bot (honeypot) · thời gian điền tối thiểu 3 giây · chặn gửi trùng nội dung · chỉ nhận chữ thuần, chặn link · bỏ ký tự điều khiển / ký tự đảo chiều · bot (Googlebot...) bị từ chối. Trang `/ho-tro` và `/api/` không được lập chỉ mục.

## Triển khai
1. Đẩy code, Redeploy. Các bảng `y_kien`, `khach_hang`, `tin_nhan_rieng`, `thong_bao`, `chat_lan_thu` **tự được tạo** khi khởi động (hoặc chạy tay `them_bang_y_kien_chat.sql`).
2. Mở trang quản trị: thấy mục "Phản hồi" ở menu bên trái và chuông ở thanh trên.
3. Thử: mở một trang thuốc → gửi ý kiến → chuông admin có số → duyệt → ý kiến hiện ra trang công khai.

## Giới hạn cần biết
- **Không có cách báo cho khách khi Khoa Dược trả lời** (chưa có SMS / email): khách phải mở lại `/ho-tro`. Với ý kiến cần gấp, admin gọi điện theo SĐT khách để lại.
- Số điện thoại khách chỉ admin thấy. Hãy dặn nhân viên không chia sẻ ra ngoài (Nghị định 13/2023 về dữ liệu cá nhân).
- Muốn thêm chỗ có hỏi đáp: thêm 1 dòng vào `DOI_TUONG` trong `app/utils/phan_hoi.py`, 1 nhánh trong `url_doi_tuong()`, và `{% include "_hoi_dap.html" %}` vào template trang đó.

## Báo ra điện thoại khi có ý kiến mới (không cần mở trang quản trị)
Chuông chỉ chạy khi có admin đang đăng nhập và mở trang, nên hệ thống còn 2 kênh báo ra ngoài. Mỗi kênh tự tắt nếu chưa cấu hình.
Vào trang quản trị → **Thông báo** để xem kênh nào đang bật, **admin nào đã / chưa đăng ký email**, và bấm **Gửi thử cho tôi**.

**Ba loại thông báo ra ngoài**
1. **Có ý kiến / tin nhắn mới** → Telegram + email tới **tất cả admin đã đăng ký email** (kèm dòng "⏳ Chưa ai trả lời").
2. **Có admin trả lời** → các admin **còn lại** nhận "✔ ADMIN1 đã trả lời…" để không ai trả lời trùng (người vừa trả lời không bị báo). Chỉ báo ở lần trả lời đầu; sửa lại câu trả lời hoặc nhắn thêm khi khách chưa nhắn lại thì không báo nữa.
3. **Nhắc việc** → bản tóm tắt các ý kiến / tin nhắn **chưa ai trả lời quá N giờ** (xem mục dưới).

**Đánh dấu đã trả lời** (hiện ở mọi nơi, tự đúng, không cần bấm tay)
- Trang *Hỏi đáp & bình luận*: mỗi ý kiến có nhãn `⏳ Chưa trả lời` hoặc `✔ Đã trả lời bởi <tên> · <giờ>`, kèm bộ lọc "Chưa trả lời / Đã trả lời" có số đếm.
- Trang *Tin nhắn riêng*: `⏳ Chờ trả lời` (tin cuối là của khách) hoặc `✔ Đã trả lời bởi <tên>` (tin cuối là của Khoa Dược), kèm tab lọc.
- Chuông và trang *Thông báo*: mỗi thông báo ghi đã được ai trả lời chưa. Khi có người trả lời, thông báo của mọi admin tự chuyển thành đã đọc.

**1. Telegram (khuyến nghị — tức thì, miễn phí)**
1. Mở Telegram, nhắn `@BotFather` → `/newbot` → đặt tên → nhận **token** (dạng `123456:ABC...`).
2. Tạo 1 nhóm Telegram cho Khoa Dược, thêm bot vào nhóm và mời các admin vào.
3. Gửi 1 tin bất kỳ trong nhóm, mở `https://api.telegram.org/bot<TOKEN>/getUpdates`, tìm `"chat":{"id":-100...}` → đó là **chat id** của nhóm.
4. Đặt biến môi trường: `TELEGRAM_BOT_TOKEN=<token>` và `TELEGRAM_CHAT_ID=<chat id>` (nhiều nơi nhận: cách nhau bằng dấu phẩy). Redeploy.

**2. Email**
Dùng lại cách gửi mail đã có (Google Apps Script / Resend). **Mỗi admin tự đăng ký email** ở menu tài khoản → "Cập nhật email" (Gmail hay email khác đều được); admin chưa đăng ký sẽ không nhận được thư. Mỗi sự kiện = 1 thư tới từng admin. Chặn an toàn: mỗi admin tối đa `THONG_BAO_EMAIL_TOI_DA_GIO` thư / giờ (mặc định 20), phần vượt được gom vào thư kế tiếp ("Và N thông báo khác") để không ngập hộp thư và không quá hạn mức gửi mail trong ngày. Tắt bằng `THONG_BAO_EMAIL=0`.

**3. Nhắc việc định kỳ (câu hỏi chưa ai trả lời)**
Lệnh: `flask --app run nhac-chua-tra-loi` (thêm `--gio 6` để đổi ngưỡng; mặc định `NHAC_CHUA_TRA_LOI_GIO` = 4 giờ). Gửi 1 bản tóm tắt tối đa 10 mục (tin nhắn riêng chỉ ghi tên khách, không ghi nội dung) qua Telegram + email tới tất cả admin đã đăng ký. Cần biến `APP_BASE_URL` (địa chỉ website) để tạo link.
Đặt chạy tự động trên Coolify: *Application → Scheduled Tasks → Add* — Name `Nhắc chưa trả lời`, Command `flask --app run nhac-chua-tra-loi`, Frequency `0 */4 * * *` (mỗi 4 giờ; có thể thêm giới hạn giờ làm việc như `0 7-19/4 * * *`). Không có mục nào quá hạn thì lệnh không gửi gì.

**Riêng tư:** tin nhắn riêng của khách (có thể chứa thông tin sức khoẻ) chỉ báo "có tin mới từ <tên>", **không gửi nội dung** ra Telegram / email (kể cả khi nhắc việc). Ý kiến công khai gửi kèm đoạn đầu. Nội dung câu trả lời không gửi ra ngoài. Số điện thoại không bao giờ gửi ra ngoài.
