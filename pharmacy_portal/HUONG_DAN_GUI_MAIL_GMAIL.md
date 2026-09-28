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
