# Cổng tra cứu thông tin Dược

Web app Flask + database (SQLite khi demo free / MySQL khi lên production),
6 trang công khai + trang quản trị (Admin) có đăng nhập bảo mật để nhập dữ liệu.

## 1. Chạy thử trên máy (development)

```bash
cd pharmacy_portal
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Mặc định app dùng **SQLite** (không cần cài server database gì cả, tự tạo
file `instance/pharmacy_portal.db` khi chạy lần đầu) — phù hợp cho giai
đoạn build FE + demo trước khi có dữ liệu thật.

Tạo tài khoản admin đầu tiên:

```bash
python create_admin.py
```

(Script sẽ hỏi tên đăng nhập + mật khẩu, không lưu mật khẩu dạng thô — chỉ
lưu bản hash.)

Chạy server:

```bash
python run.py
```

Mở trình duyệt:
- Trang công khai: http://localhost:5000
- Trang quản trị: http://localhost:5000/admin/dang-nhap

Muốn có dữ liệu MẪU để xem giao diện nhanh (không phải dữ liệu thật, xem
cảnh báo trong file):

```bash
python seed_demo_data.py
```

## 2. Bảo mật trang Admin

- Mật khẩu được **hash** bằng werkzeug (không bao giờ lưu plaintext).
- Toàn bộ route `/admin/*` (trừ trang đăng nhập) yêu cầu đăng nhập
  (`@login_required`), tự động chuyển hướng về trang đăng nhập nếu chưa
  đăng nhập.
- Mọi form (thêm/sửa/xoá) đều có **CSRF token** (Flask-WTF) — chặn giả
  mạo yêu cầu từ trang khác.
- Thông báo lỗi đăng nhập dùng chung 1 câu cho cả sai tên đăng nhập lẫn
  sai mật khẩu, tránh lộ thông tin tài khoản nào tồn tại.
- Tài khoản có cờ `dang_hoat_dong` — có thể khoá tài khoản mà không cần
  xoá (hữu ích khi nhân viên nghỉ việc).

**Việc bạn cần tự làm thêm khi lên production thật**: đổi `SECRET_KEY`
mặc định trong `config.py` (đặt qua biến môi trường), bật HTTPS (Render
tự cấp), và cân nhắc giới hạn số lần đăng nhập sai (rate limiting) nếu
public ra Internet.

## 3. Deploy free lên Render.com (giai đoạn hiện tại — chưa có dữ liệu thật)

1. Đẩy code lên GitHub (repo có thể để private).
2. Vào [render.com](https://render.com) > **New +** > **Web Service** > kết
   nối repo GitHub vừa tạo.
3. Cấu hình:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
   - **Plan**: Free
   - **Environment Variables**:
     - `SECRET_KEY` = (chuỗi bất kỳ, bấm "Generate")
     - `DB_TYPE` = `sqlite`
4. Bấm **Create Web Service**. Render build xong sẽ cho 1 URL dạng
   `https://ten-app.onrender.com`.
5. Vào Render > Shell (hoặc SSH) chạy `python create_admin.py` để tạo tài
   khoản admin đầu tiên trên môi trường production.

(File `render.yaml` trong repo cũng dùng được nếu bạn chọn deploy kiểu
"Blueprint" thay vì cấu hình tay.)

### Tên miền riêng

Tên miền hiện dùng: `tracuuduoc-bvdktamduccauquan.com` (mua ở Namecheap, đã
gắn vào Render ở Settings > Custom Domains). Trên Render > Environment cần có:

- `APP_BASE_URL` = `https://tracuuduoc-bvdktamduccauquan.com` (dùng tạo link trong email đặt lại mật khẩu)
- `CANONICAL_HOST` = `tracuuduoc-bvdktamduccauquan.com` (tuỳ chọn: tự chuyển link `onrender.com` cũ sang tên miền mới)

### ⚠️ Lưu ý quan trọng về giới hạn free tier

- **App sẽ "ngủ" sau 15 phút không có ai truy cập**, lần truy cập đầu tiên
  sau đó sẽ chậm (30-60 giây) do khởi động lại — bình thường ở free tier,
  không phải lỗi.
- **Ổ đĩa không cố định (ephemeral)**: dữ liệu SQLite có thể bị mất khi
  Render deploy lại code (mỗi lần bạn push code mới). Vì hiện tại **chưa
  có dữ liệu thật**, điều này không ảnh hưởng gì — đây đúng là giai đoạn
  để duyệt giao diện. Nhưng **khi bắt đầu nhập dữ liệu thật để dùng lâu
  dài, cần chuyển sang MySQL + hosting trả phí có ổ đĩa cố định** (xem
  mục 4), nếu không dữ liệu nhập vào có thể biến mất bất cứ lúc nào.

## 4. Khi có dữ liệu thật — chuyển sang MySQL + hosting trả phí

Không cần sửa code, chỉ đổi biến môi trường:

```
DB_TYPE=mysql
DB_USER=...
DB_PASSWORD=...
DB_HOST=...
DB_PORT=3306
DB_NAME=pharmacy_portal
```

Chạy `schema.sql` trên server MySQL thật (`mysql -u root -p < schema.sql`),
sau đó `python create_admin.py` lại 1 lần trên môi trường mới.

Vì đây là **thông tin dược dùng nội bộ bệnh viện**, nên ưu tiên máy chủ
nội bộ (mạng LAN bệnh viện) hoặc VPS trong nước (Viettel IDC, VNPT Cloud,
Vinahost...) thay vì để public trên hosting quốc tế — mình có thể tư vấn
kỹ hơn khi bạn tới bước này.

## 5. Cấu trúc thư mục

```
pharmacy_portal/
├── app/
│   ├── models/models.py           # 7 bảng: NguoiDung + 6 bảng dữ liệu
│   ├── forms.py                   # WTForms cho toàn bộ form (validate + CSRF)
│   ├── routes/
│   │   ├── admin_auth.py          # đăng nhập / đăng xuất
│   │   ├── admin_dashboard.py     # trang tổng quan
│   │   ├── admin_*.py             # CRUD cho từng bảng (6 file)
│   │   └── (route công khai)      # main.py, tra_cuu_*.py, thong_tin_benh_nhan.py
│   ├── templates/
│   │   ├── admin/                 # giao diện quản trị (sidebar + form)
│   │   └── (trang công khai)
│   └── static/css/style.css       # toàn bộ style, kể cả admin
├── config.py                      # chuyển đổi SQLite <-> MySQL qua DB_TYPE
├── schema.sql                     # tạo database MySQL bằng SQL thuần
├── create_admin.py                # tạo tài khoản admin đầu tiên
├── seed_demo_data.py              # dữ liệu MẪU để test (xoá trước khi dùng thật)
├── render.yaml                    # cấu hình deploy Render (tuỳ chọn)
├── run.py                         # điểm chạy chính
└── requirements.txt
```


## Phiên đăng nhập admin: tự đăng xuất khi không hoạt động

Admin tự bị đăng xuất sau **15 phút không thao tác** (đổi bằng biến môi trường `ADMIN_IDLE_TIMEOUT_MINUTES`).
- Máy chủ kiểm tra ở mọi request (`app/utils/phien_dang_nhap.py`), nên cửa sổ 15 phút là "trượt": còn thao tác thì phiên còn sống.
- Trình duyệt (`static/js/phien_het_han.js`) gửi tín hiệu `/admin/keep-alive` mỗi ≤5 phút khi có chuột/bàn phím, để đang soạn bài dài không bị đá ra,
  và tự chuyển về trang đăng nhập khi hết giờ. Nhiều tab admin dùng chung mốc hoạt động.
- Phiên đang mở trước khi cập nhật sẽ phải đăng nhập lại một lần.


## Soạn thảo văn bản trong form admin (modal)

Các ô văn bản dài (thành phần, chỉ định, cách dùng... — mọi `TextAreaField` đi qua macro `render_field`) hiện **bản xem trước**
trong form; bấm vào ô (hoặc Tab tới rồi Enter) sẽ mở **modal soạn thảo**: thanh công cụ nằm cố định ở trên cùng, chỉ vùng nội dung cuộn.
`Ctrl+Enter` = Xong, `Esc` = Huỷ (hỏi lại nếu đã sửa), bấm ra vùng tối không đóng để tránh mất bài. Code: `static/js/main.js`, CSS `.rich-modal*` / `.rich-preview*`.


## Xác thực 2 lớp (OTP - Google Authenticator) khi đăng nhập admin

Đăng nhập admin gồm 2 bước: **(1)** tên đăng nhập + mật khẩu, **(2)** mã 6 số trong app Google Authenticator / Microsoft Authenticator / Authy.
Mỗi tài khoản có secret OTP riêng (không dùng chung). Thay cho "cổng mã bảo mật 6 số" trước đây.

- **Lần đầu / tài khoản chưa bật OTP:** đúng mật khẩu xong sẽ được đưa tới trang quét QR → nhập thử 1 mã → nhận **8 mã dự phòng** (chỉ hiện 1 lần) → vào admin.
  Mặc định bắt buộc (`ADMIN_2FA_BAT_BUOC=1`). Đặt `0` thì OTP là tuỳ chọn (ai chưa bật vẫn đăng nhập bằng mật khẩu, bật ở menu **🔐 Bảo mật 2 lớp**).
  **Sau khi deploy bản này, hãy cho mọi admin đăng nhập và bật OTP ngay** (ai đăng nhập trước sẽ là người gắn OTP cho tài khoản đó).
- **Mất điện thoại:** ở bước nhập mã bấm **"Dùng mã dự phòng"** (mỗi mã 1 lần). Hết mã dự phòng → chạy trong Terminal của Coolify: `python reset_otp.py <ten_dang_nhap>`.
- **Đổi điện thoại / tạo lại mã dự phòng / tắt OTP:** menu **🔐 Bảo mật 2 lớp** (cần nhập lại mật khẩu + mã OTP hiện tại). Không tắt được khi `ADMIN_2FA_BAT_BUOC=1`.
- **Bảo mật:** secret OTP lưu **mã hoá** (Fernet) trong cột `nguoi_dung.totp_secret`; khoá lấy từ `OTP_ENC_KEY` (hoặc dẫn xuất từ `SECRET_KEY` nếu để trống — khi đó **không được đổi `SECRET_KEY`**, nếu đổi thì mọi người phải thiết lập lại OTP).
  Mỗi mã chỉ dùng được 1 lần (chống phát lại), chấp nhận lệch ±30 giây. Sai OTP 5 lần/tài khoản (hoặc 20 lần/IP) → khoá 15 phút. Trang đăng nhập cũng khoá tạm khi sai mật khẩu 8 lần/tên đăng nhập hoặc 30 lần/IP.
- **Cột DB mới:** `totp_secret`, `totp_bat`, `totp_buoc_cuoi`, `totp_ma_du_phong`, `totp_ngay_bat` (bảng `nguoi_dung`). Ứng dụng **tự thêm** khi khởi động; nếu DB user không có quyền ALTER thì chạy `them_cot_otp_nguoi_dung.sql`.
- **Biến môi trường:** `ADMIN_2FA_BAT_BUOC`, `OTP_ISSUER`, `OTP_ENC_KEY`, `OTP_CHO_PHUT`, `OTP_MAX_SAI`, `OTP_MAX_SAI_IP`, `OTP_KHOA_PHUT`, `DANG_NHAP_MAX_SAI`, `DANG_NHAP_MAX_SAI_IP` (xem `config.py`).
- **Chạy sau proxy (Coolify/Traefik):** đặt `TRUSTED_PROXIES=1` (mặc định). Máy chủ cloud phải **đồng bộ giờ** (NTP/`chrony`) vì OTP phụ thuộc đồng hồ.
- Mọi sự kiện (đăng nhập, OTP sai, bật/đổi OTP) được ghi trong **Nhật ký truy cập**.

