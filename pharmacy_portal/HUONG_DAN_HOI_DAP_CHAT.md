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
