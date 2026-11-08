# Gửi email quên mật khẩu bằng Gmail (không cần tên miền)

Render free chặn cổng SMTP nên không gửi Gmail trực tiếp được. Cách làm: tạo 1 Google Apps Script
chạy trên tài khoản Gmail của bạn, web gọi script đó qua HTTPS. Miễn phí, gửi tới mọi email,
giới hạn khoảng 100 email/ngày với Gmail cá nhân (thừa cho chức năng quên mật khẩu).

## Bước 1 — Tạo script
1. Vào https://script.google.com (đăng nhập đúng Gmail muốn dùng để gửi) → **Dự án mới**.
2. Xoá code mặc định, dán đoạn dưới. Đổi `SECRET` thành 1 chuỗi bí mật dài do bạn tự đặt.

```javascript
const SECRET = 'DOI-CHUOI-BI-MAT-NAY-THANH-CHUOI-DAI-NGAU-NHIEN';

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.secret !== SECRET) return ra({ ok: false, error: 'unauthorized' });
    MailApp.sendEmail({
      to: d.to,
      subject: d.subject,
      htmlBody: d.html,
      body: d.text || '',
      name: d.name || 'Cổng Tra Cứu Dược'
    });
    return ra({ ok: true });
  } catch (err) {
    return ra({ ok: false, error: String(err) });
  }
}

function ra(o) {
  return ContentService.createTextOutput(JSON.stringify(o))
    .setMimeType(ContentService.MimeType.JSON);
}

// Chạy hàm này 1 lần (nút Chạy) để cấp quyền gửi mail cho script
function capQuyen() {
  Logger.log('Còn được gửi hôm nay: ' + MailApp.getRemainingDailyQuota());
}
```

## Bước 2 — Cấp quyền và triển khai
1. Chọn hàm `capQuyen` → bấm **Chạy** → cho phép quyền (Advanced → Go to ... (unsafe) → Allow).
2. **Triển khai (Deploy) → Tùy chọn triển khai mới → loại "Ứng dụng web"**:
   - Thực thi dưới tên: **Tôi**
   - Ai có quyền truy cập: **Bất kỳ ai**
3. Copy **URL ứng dụng web** (dạng `https://script.google.com/macros/s/.../exec`).

## Bước 3 — Biến môi trường trên Render
- `GAS_MAIL_URL` = URL vừa copy
- `GAS_MAIL_SECRET` = đúng chuỗi `SECRET` ở trên
- (tuỳ chọn) `MAIL_NAME` = tên người gửi hiển thị

Có `GAS_MAIL_URL` thì web dùng cách này, bỏ qua Resend. Lưu ý: nếu sửa code script sau này, phải
**Triển khai → Quản lý triển khai → Sửa → Phiên bản mới** thì URL cũ mới nhận code mới.

## Khắc phục lỗi thường gặp

**Log báo "Apps Script trả lỗi 404" kèm theo một đoạn HTML dài (có chữ
`ppConfig`, `productName`...)** — đây KHÔNG phải lỗi trong code Apps Script
bạn viết, mà là trang lỗi mặc định của Google khi không gọi được đúng ứng
dụng web. Kiểm tra lần lượt:

1. **URL có đúng kết thúc bằng `/exec` không** — không phải `/dev`, và
   không phải link mở trang soạn script (script.google.com/.../edit).
2. **Deployment còn tồn tại không** — vào Apps Script → Triển khai → Quản
   lý triển khai, xem deployment "Ứng dụng web" có còn trong danh sách
   không (nếu bạn lỡ xoá/tạo deployment mới mà quên cập nhật lại biến môi
   trường `GAS_MAIL_URL` trên Render, URL cũ sẽ gãy y hệt kiểu lỗi này).
3. **Quyền truy cập** — vẫn phải là "Bất kỳ ai" (Anyone), không phải "Chỉ
   mình tôi" hay "Bất kỳ ai trong tổ chức".
4. **Biến môi trường trên Render bị dính khoảng trắng/xuống dòng thừa khi
   copy-paste** — dán vào thường không thấy bằng mắt nhưng khiến URL sai.
   Xoá đi và dán lại, kiểm tra không có khoảng trắng ở đầu/cuối.

Nếu log ghi rõ `"Apps Script từ chối gửi mail: ..."` (có kèm lý do) thay vì
đoạn HTML — đó mới là lỗi THẬT trong code Apps Script (vd. sai `SECRET`,
hoặc `MailApp` hết quota gửi/ngày) chứ không phải lỗi URL/quyền truy cập.
