# Hỏi đáp công khai · Chat riêng · Thông báo admin

## Có gì
| Chức năng | Ở đâu | Ghi chú |
|---|---|---|
| **Hỏi đáp / bình luận công khai** | Cuối trang chi tiết: Danh mục thuốc, Nhà thuốc BV, Thuốc tra cứu, Bài viết, Bài viết bệnh nhân | Cần **tên + SĐT**. Ý kiến ở trạng thái *chờ duyệt*, admin duyệt mới hiện. Chỉ hiện tên, **không bao giờ hiện SĐT**. Admin có thể trả lời công khai. |
| **Chat riêng tư** | Menu "💬 Hỗ trợ & góp ý" (`/ho-tro`) | Khách chỉ nhập **họ tên + SĐT + tin nhắn** (không có mã bí mật). Cuộc trò chuyện **gắn với thiết bị/trình duyệt** tạo ra nó (cookie đã ký, nhớ 30 ngày); SĐT chỉ để Khoa Dược liên hệ. |
| **Báo lỗi thông tin** | Thanh vàng ở đầu trang Tương tác thuốc, Thuốc tiêm truyền, Tương hợp – Tương kỵ | Mở chat riêng, đính kèm sẵn trang bị báo lỗi. |
| **Chuông thông báo** | Thanh trên trang quản trị | Số chưa đọc + danh sách, tự cập nhật ~15 giây; trang "Thông báo" xem tất cả. Mỗi ý kiến mới = 1 thông báo; nhiều tin của cùng 1 khách gộp thành "×N". |
| **Quản trị** | Menu "Phản hồi": Hỏi đáp & bình luận · Tin nhắn riêng · Thông báo | Duyệt / từ chối / spam / xoá / trả lời / thao tác hàng loạt; chat với khách; chặn khách. Mọi thao tác ghi vào Nhật ký truy cập. |

## Vì sao không còn "mã bí mật 6 số" mà cuộc trò chuyện lại gắn với thiết bị
SĐT không được xác minh bằng SMS, nên nếu dùng SĐT để vào xem thì **ai biết số cũng đọc được cuộc trò chuyện** (có thể chứa thông tin sức khoẻ). Vì vậy SĐT chỉ là thông tin liên hệ; quyền xem thuộc về trình duyệt đã tạo cuộc trò chuyện (cookie đã ký, không đoán / sửa được).
Hệ quả: **đổi thiết bị hoặc xoá dữ liệu trình duyệt thì khách bắt đầu một cuộc trò chuyện mới** (Khoa Dược vẫn thấy tất cả, theo từng cuộc). Cùng 1 SĐT có thể có nhiều cuộc. Mỗi thiết bị mở tối đa 5 cuộc mới / 24 giờ; SĐT đã bị admin chặn thì không mở được cuộc mới.
**Khi nâng cấp từ bản cũ:** chạy `bo_ma_bi_mat.sql` một lần để bỏ ràng buộc UNIQUE trên số điện thoại. Khách cũ còn cookie hợp lệ vẫn dùng tiếp được; ai không còn cookie sẽ bắt đầu cuộc trò chuyện mới.

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
