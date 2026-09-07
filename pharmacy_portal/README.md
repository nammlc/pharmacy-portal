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
