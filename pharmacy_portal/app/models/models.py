from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


class NguoiDung(UserMixin, db.Model):
    """Tài khoản quản trị (admin) - dùng để đăng nhập vào trang quản lý dữ liệu."""
    __tablename__ = "nguoi_dung"

    id = db.Column(db.Integer, primary_key=True)
    ten_dang_nhap = db.Column(db.String(100), unique=True, nullable=False, index=True)
    mat_khau_hash = db.Column(db.String(255), nullable=False)
    ho_ten = db.Column(db.String(150))
    # Email dùng để nhận link đặt lại mật khẩu (gửi qua Resend). Có thể để trống.
    email = db.Column(db.String(255), unique=True, index=True)
    vai_tro = db.Column(db.String(50), default="duoc_si")   # duoc_si, quan_tri...
    dang_hoat_dong = db.Column(db.Boolean, default=True)
    ngay_tao = db.Column(db.DateTime, default=datetime.utcnow)

    # --- Xác thực 2 lớp (OTP Google Authenticator / TOTP) ---
    # Secret lưu dạng MÃ HOÁ (Fernet), xem app/utils/otp.py. Sửa cột ở đây thì cũng sửa
    # danh sách cột trong otp.CAC_COT_OTP và file them_cot_otp_nguoi_dung.sql.
    totp_secret = db.Column(db.Text)
    totp_bat = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    totp_buoc_cuoi = db.Column(db.BigInteger)        # bước 30s của mã OTP vừa dùng (chống dùng lại mã)
    totp_ma_du_phong = db.Column(db.Text)            # JSON: danh sách BĂM của các mã dự phòng còn lại
    totp_ngay_bat = db.Column(db.DateTime)

    def set_password(self, mat_khau):
        self.mat_khau_hash = generate_password_hash(mat_khau)

    def check_password(self, mat_khau):
        return check_password_hash(self.mat_khau_hash, mat_khau)

    def __repr__(self):
        return f"<NguoiDung {self.ten_dang_nhap}>"


class NhomThuoc(db.Model):
    """Nhóm thuốc theo dược lý, phân cấp cha-con (vd: Kháng sinh > Beta-lactam).
    Dùng chung cho cả 'Danh mục thuốc' và 'Nhà thuốc BV' (phân biệt bằng cột loai)."""
    __tablename__ = "nhom_thuoc"

    id = db.Column(db.Integer, primary_key=True)
    ten_nhom = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255), index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("nhom_thuoc.id"), nullable=True)
    loai = db.Column(db.String(30), default="danh_muc_thuoc")  # danh_muc_thuoc | nha_thuoc_bv
    thu_tu = db.Column(db.Integer, default=0)
    hinh_anh = db.Column(db.String(500))   # URL ảnh đại diện nhóm thuốc (Cloudinary)

    con = db.relationship("NhomThuoc", backref=db.backref("cha", remote_side=[id]))

    def __repr__(self):
        return f"<NhomThuoc {self.ten_nhom}>"


class HoatChat(db.Model):
    """Danh mục hoạt chất (tên chung quốc tế / INN) - dùng chung cho cả
    'Danh mục thuốc' và 'Nhà thuốc BV' (1 hoạt chất có thể có nhiều biệt dược)."""
    __tablename__ = "hoat_chat"

    id = db.Column(db.Integer, primary_key=True)
    ten_hoat_chat = db.Column(db.String(255), nullable=False, unique=True, index=True)

    def __repr__(self):
        return f"<HoatChat {self.ten_hoat_chat}>"


# --------------------------------------------------------------------------
# Bảng trung gian (nhiều-nhiều): 1 biệt dược có thể được cấu thành từ NHIỀU
# hoạt chất (thuốc phối hợp, vd: Panadol Extra = Paracetamol + Cafein), và
# 1 hoạt chất có thể xuất hiện trong nhiều biệt dược.
# --------------------------------------------------------------------------
danh_muc_thuoc_hoat_chat = db.Table(
    "danh_muc_thuoc_hoat_chat",
    db.Column("danh_muc_thuoc_id", db.Integer, db.ForeignKey("danh_muc_thuoc.id", ondelete="CASCADE"), primary_key=True),
    db.Column("hoat_chat_id", db.Integer, db.ForeignKey("hoat_chat.id", ondelete="CASCADE"), primary_key=True),
)

nha_thuoc_bv_hoat_chat = db.Table(
    "nha_thuoc_bv_hoat_chat",
    db.Column("nha_thuoc_bv_id", db.Integer, db.ForeignKey("nha_thuoc_bv.id", ondelete="CASCADE"), primary_key=True),
    db.Column("hoat_chat_id", db.Integer, db.ForeignKey("hoat_chat.id", ondelete="CASCADE"), primary_key=True),
)


class DanhMucThuoc(db.Model):
    """Danh mục thuốc (biệt dược) hiển thị công khai - mỗi thuốc thuộc 1 nhóm
    thuốc, có thể cấu thành từ NHIỀU hoạt chất (thuốc phối hợp), kèm thông
    tin chỉ định/chống chỉ định/cách dùng."""
    __tablename__ = "danh_muc_thuoc"

    id = db.Column(db.Integer, primary_key=True)
    nhom_thuoc_id = db.Column(db.Integer, db.ForeignKey("nhom_thuoc.id"), nullable=True)
    ten_biet_duoc = db.Column(db.String(255), nullable=False, index=True)
    thanh_phan = db.Column(db.Text)
    chi_dinh = db.Column(db.Text)
    chong_chi_dinh = db.Column(db.Text)
    cach_dung_lieu_dung = db.Column(db.Text)
    link_chi_tiet = db.Column(db.String(500))
    hinh_anh = db.Column(db.String(500))
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhom = db.relationship("NhomThuoc", backref="danh_muc_thuoc_list")
    hoat_chat_list = db.relationship(
        "HoatChat", secondary=danh_muc_thuoc_hoat_chat,
        backref=db.backref("danh_muc_thuoc_co_hoat_chat", lazy="dynamic"),
        order_by="HoatChat.ten_hoat_chat",
    )

    @property
    def ten_hoat_chat_hien_thi(self):
        """Chuỗi hiển thị: 'Paracetamol + Cafein' hoặc rỗng nếu chưa gán."""
        return " + ".join(hc.ten_hoat_chat for hc in self.hoat_chat_list)

    def __repr__(self):
        return f"<DanhMucThuoc {self.ten_biet_duoc}>"


class NhaThuocBV(db.Model):
    """Danh mục thuốc bán tại Nhà thuốc Bệnh viện - cùng cấu trúc phân loại
    (nhóm thuốc + nhiều hoạt chất) như Danh mục thuốc, nhưng dữ liệu gọn hơn."""
    __tablename__ = "nha_thuoc_bv"

    id = db.Column(db.Integer, primary_key=True)
    nhom_thuoc_id = db.Column(db.Integer, db.ForeignKey("nhom_thuoc.id"), nullable=True)
    ten_biet_duoc = db.Column(db.String(255), nullable=False, index=True)
    link_tham_khao = db.Column(db.String(500))
    hinh_anh = db.Column(db.String(500))
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhom = db.relationship("NhomThuoc", backref="nha_thuoc_bv_list")
    hoat_chat_list = db.relationship(
        "HoatChat", secondary=nha_thuoc_bv_hoat_chat,
        backref=db.backref("nha_thuoc_bv_co_hoat_chat", lazy="dynamic"),
        order_by="HoatChat.ten_hoat_chat",
    )

    @property
    def ten_hoat_chat_hien_thi(self):
        return " + ".join(hc.ten_hoat_chat for hc in self.hoat_chat_list)

    def __repr__(self):
        return f"<NhaThuocBV {self.ten_biet_duoc}>"


class Thuoc(db.Model):
    """Bảng danh mục thuốc gốc - trung tâm, các bảng khác tham chiếu tới đây."""
    __tablename__ = "thuoc"

    id = db.Column(db.Integer, primary_key=True)
    ten_thuoc = db.Column(db.String(255), nullable=False, index=True)   # tên biệt dược
    hoat_chat = db.Column(db.String(255), index=True)                   # tên hoạt chất
    thanh_phan = db.Column(db.Text)                                     # thành phần dược chất + tá dược
    ham_luong = db.Column(db.String(100))
    dang_bao_che = db.Column(db.String(150))
    nhom_thuoc_id = db.Column(db.Integer, db.ForeignKey("nhom_thuoc.id"), nullable=True)
    nha_san_xuat = db.Column(db.String(255))
    so_dang_ky = db.Column(db.String(100))
    link_tham_khao = db.Column(db.String(500))
    hinh_anh = db.Column(db.Text)    # URL ảnh gốc (Google CDN) hoặc tên file local sau này
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhom = db.relationship("NhomThuoc", backref="danh_sach_thuoc")

    def __repr__(self):
        return f"<Thuoc {self.ten_thuoc}>"


class ThuocTiemTruyen(db.Model):
    """Tra cứu thuốc tiêm truyền: dung môi pha, tốc độ truyền, độ ổn định..."""
    __tablename__ = "thuoc_tiem_truyen"

    id = db.Column(db.Integer, primary_key=True)
    thuoc_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False)
    dung_moi_pha_loang = db.Column(db.String(255))      # NaCl 0.9%, Glucose 5%...
    nong_do_toi_da = db.Column(db.String(100))
    toc_do_truyen = db.Column(db.String(255))
    thoi_gian_truyen = db.Column(db.String(100))
    do_on_dinh = db.Column(db.String(255))              # thời gian ổn định sau pha
    dieu_kien_bao_quan = db.Column(db.String(255))
    canh_bao = db.Column(db.Text)                       # lưu ý đặc biệt khi truyền
    nguon_tham_khao = db.Column(db.String(255))

    thuoc = db.relationship("Thuoc", backref="thong_tin_tiem_truyen")


class TuongHopTuongKy(db.Model):
    """Tra cứu tương hợp - tương kỵ giữa 2 thuốc khi phối hợp/pha chung."""
    __tablename__ = "tuong_hop_tuong_ky"

    id = db.Column(db.Integer, primary_key=True)
    thuoc_a_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False)
    thuoc_b_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False)
    trang_thai = db.Column(db.Enum("tuong_hop", "tuong_ky", "chua_xac_dinh", name="trang_thai_enum"),
                            nullable=False, default="chua_xac_dinh")
    mo_ta = db.Column(db.Text)
    nguon_tham_khao = db.Column(db.String(255))

    thuoc_a = db.relationship("Thuoc", foreign_keys=[thuoc_a_id])
    thuoc_b = db.relationship("Thuoc", foreign_keys=[thuoc_b_id])


class TuongTacThuoc(db.Model):
    """Tra cứu tương tác thuốc - thuốc khi dùng đồng thời."""
    __tablename__ = "tuong_tac_thuoc"

    id = db.Column(db.Integer, primary_key=True)
    thuoc_a_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False)
    thuoc_b_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False)
    muc_do = db.Column(db.Enum("nhe", "trung_binh", "nang", "chong_chi_dinh", name="muc_do_enum"),
                        nullable=False, default="trung_binh")
    co_che = db.Column(db.Text)
    hau_qua_lam_sang = db.Column(db.Text)
    xu_tri = db.Column(db.Text)
    nguon_tham_khao = db.Column(db.String(255))

    thuoc_a = db.relationship("Thuoc", foreign_keys=[thuoc_a_id])
    thuoc_b = db.relationship("Thuoc", foreign_keys=[thuoc_b_id])


class ThongTinThuoc(db.Model):
    """Tra cứu thông tin thuốc chi tiết: chỉ định, liều dùng, chống chỉ định..."""
    __tablename__ = "thong_tin_thuoc"

    id = db.Column(db.Integer, primary_key=True)
    thuoc_id = db.Column(db.Integer, db.ForeignKey("thuoc.id"), nullable=False, unique=True)
    chi_dinh = db.Column(db.Text)
    chong_chi_dinh = db.Column(db.Text)
    lieu_dung_nguoi_lon = db.Column(db.Text)
    lieu_dung_tre_em = db.Column(db.Text)
    tac_dung_phu = db.Column(db.Text)
    than_trong = db.Column(db.Text)
    phu_nu_co_thai_cho_con_bu = db.Column(db.Text)
    nguon_tham_khao = db.Column(db.String(255))

    thuoc = db.relationship("Thuoc", backref="thong_tin_chi_tiet", uselist=False)


class ThongTinBenhNhan(db.Model):
    """Bài viết / tài liệu hướng dẫn dành cho bệnh nhân (không phải cho CBYT)."""
    __tablename__ = "thong_tin_benh_nhan"

    id = db.Column(db.Integer, primary_key=True)
    tieu_de = db.Column(db.String(255), nullable=False)
    danh_muc = db.Column(db.String(150))               # vd: dùng thuốc tại nhà, dinh dưỡng...
    noi_dung = db.Column(db.Text, nullable=False)
    ngay_dang = db.Column(db.DateTime, default=datetime.utcnow)


class DanhMucBaiViet(db.Model):
    """Danh mục cho bài viết / thông báo (vd: Thông báo, Tin tức, Bài báo khoa học...)."""
    __tablename__ = "danh_muc_bai_viet"

    id = db.Column(db.Integer, primary_key=True)
    ten = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True)
    mo_ta = db.Column(db.String(255))
    mau_sac = db.Column(db.String(20), default="#1a4d8f")
    thu_tu = db.Column(db.Integer, default=0)
    ngay_tao = db.Column(db.DateTime, default=datetime.utcnow)

    bai_viet_list = db.relationship("BaiViet", backref="danh_muc")

    def __repr__(self):
        return f"<DanhMucBaiViet {self.ten}>"


class BaiViet(db.Model):
    """Bài viết / thông báo đăng công khai trên trang web (tin tức, thông báo nội bộ,
    bài báo khoa học, hướng dẫn chuyên môn...)."""
    __tablename__ = "bai_viet"

    id = db.Column(db.Integer, primary_key=True)
    danh_muc_id = db.Column(db.Integer, db.ForeignKey("danh_muc_bai_viet.id", ondelete="SET NULL"), nullable=True)
    nguoi_dung_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id", ondelete="SET NULL"), nullable=True)

    tieu_de = db.Column(db.String(500), nullable=False)
    slug = db.Column(db.String(520), unique=True)
    mo_ta_ngan = db.Column(db.String(500))
    noi_dung = db.Column(db.Text)

    anh_dai_dien = db.Column(db.String(500))
    file_dinh_kem = db.Column(db.String(500))
    ten_file = db.Column(db.String(255))

    # nhap: bản nháp (chưa hiển thị công khai) | da_xuat_ban: hiển thị công khai | an: đã ẩn
    trang_thai = db.Column(
        db.Enum("nhap", "da_xuat_ban", "an", name="trang_thai_bai_viet"),
        nullable=False, default="nhap",
    )
    ghim = db.Column(db.Boolean, default=False)
    luot_xem = db.Column(db.Integer, default=0)
    do_uu_tien = db.Column(db.Integer, nullable=True)  # 1..4 - mức ưu tiên hiển thị trang chủ Bài viết (None = không ưu tiên)

    ngay_tao = db.Column(db.DateTime, default=datetime.utcnow)
    ngay_xuat_ban = db.Column(db.DateTime)
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tac_gia = db.relationship("NguoiDung")

    def __repr__(self):
        return f"<BaiViet {self.tieu_de}>"


class CaiDat(db.Model):
    """Lưu cài đặt hệ thống dạng key-value, dùng cho trang Về chúng tôi và các nội dung tĩnh."""
    __tablename__ = "cai_dat"

    id = db.Column(db.Integer, primary_key=True)
    khoa = db.Column(db.String(100), unique=True, nullable=False, index=True)
    gia_tri = db.Column(db.Text)
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def lay(cls, khoa: str, mac_dinh: str = "") -> str:
        """Lấy giá trị theo key, trả về mac_dinh nếu chưa có."""
        obj = cls.query.filter_by(khoa=khoa).first()
        return obj.gia_tri if obj and obj.gia_tri else mac_dinh

    @classmethod
    def dat(cls, khoa: str, gia_tri: str):
        """Ghi hoặc cập nhật một key."""
        obj = cls.query.filter_by(khoa=khoa).first()
        if obj:
            obj.gia_tri = gia_tri
        else:
            obj = cls(khoa=khoa, gia_tri=gia_tri)
            db.session.add(obj)


class NhatKy(db.Model):
    """Nhật ký truy cập / thao tác: ai (IP + cookie ẩn danh), lúc nào, làm gì.
    - loai = tim_kiem      : người dùng công khai tra cứu (tu_khoa = nội dung tìm)
    - loai = sua_du_lieu   : admin thêm/sửa/xoá dữ liệu (hanh_dong + doi_tuong + doi_tuong_id)
    - loai = dang_nhap / dang_nhap_that_bai / dang_xuat / tai_khoan : sự kiện tài khoản admin
    """
    __tablename__ = "nhat_ky"

    id = db.Column(db.Integer, primary_key=True)
    thoi_gian = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)  # UTC
    loai = db.Column(db.String(30), nullable=False, index=True)
    ip = db.Column(db.String(64), index=True)
    cookie_id = db.Column(db.String(40), index=True)     # mã ẩn danh trong cookie trình duyệt
    nguoi_dung_id = db.Column(db.Integer)
    ten_nguoi_dung = db.Column(db.String(100))
    phuong_thuc = db.Column(db.String(10))
    duong_dan = db.Column(db.String(500))
    tu_khoa = db.Column(db.String(500))
    hanh_dong = db.Column(db.String(30))                  # them | sua | xoa | xoa_hang_loat | ...
    doi_tuong = db.Column(db.String(80))                  # vd: "Danh mục thuốc"
    doi_tuong_id = db.Column(db.Integer)
    doi_tuong_ten = db.Column(db.String(255))
    mo_ta = db.Column(db.String(500))
    ma_trang_thai = db.Column(db.Integer)
    trinh_duyet = db.Column(db.String(300))

    def __repr__(self):
        return f"<NhatKy {self.loai} {self.ip}>"


class CaiDatHeThong(db.Model):
    """Bảng cài đặt dạng khoá-giá trị. Hiện dùng cho mã bảo mật cổng admin (chỉ lưu dạng băm)."""
    __tablename__ = "cai_dat_he_thong"

    khoa = db.Column(db.String(80), primary_key=True)
    gia_tri = db.Column(db.Text)
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DangOnline(db.Model):
    """Ai đang trực tuyến: mỗi thiết bị / tài khoản 1 dòng, trình duyệt báo "còn ở đây" mỗi ~45 giây.
    Đếm = số dòng có lan_cuoi trong ONLINE_CUA_SO_GIAY giây gần nhất. KHÔNG lưu IP thô (khách chỉ lưu mã băm có muối),
    dòng cũ tự xoá. Xem app/utils/online.py."""
    __tablename__ = "dang_online"

    khoa = db.Column(db.String(64), primary_key=True)          # a:<id admin> | v:<cookie ẩn danh> | k:<mã băm thiết bị>
    loai = db.Column(db.String(10), nullable=False, index=True)    # "admin" | "khach"
    ten = db.Column(db.String(150))                              # tên admin (để hiện danh sách), khách để trống
    lan_cuoi = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class GateLanThu(db.Model):
    """Mỗi dòng = 1 lần nhập SAI mã bảo mật cổng admin (để khoá tạm theo IP / toàn hệ thống)."""
    __tablename__ = "cong_bao_mat_lan_sai"

    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(64), index=True)
    thoi_gian = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


# ============================================================================================
# HỎI ĐÁP / BÌNH LUẬN CÔNG KHAI + CHAT RIÊNG TƯ + THÔNG BÁO ADMIN
# ============================================================================================
class YKien(db.Model):
    """Hỏi đáp / bình luận CÔNG KHAI dưới 1 thuốc hoặc bài viết. Chỉ hiện ra trang công khai khi admin DUYỆT.
    SĐT chỉ để Khoa Dược liên hệ, KHÔNG bao giờ hiển thị công khai."""
    __tablename__ = "y_kien"

    id = db.Column(db.Integer, primary_key=True)
    doi_tuong_loai = db.Column(db.String(10), nullable=False, index=True)    # dmt | ntbv | tt | bv | ttbn (xem utils/phan_hoi.py)
    doi_tuong_id = db.Column(db.Integer, nullable=False, index=True)
    doi_tuong_ten = db.Column(db.String(255))                                # tên lúc gửi, để admin đọc nhanh
    ten = db.Column(db.String(100), nullable=False)
    so_dien_thoai = db.Column(db.String(15), nullable=False)
    noi_dung = db.Column(db.Text, nullable=False)
    trang_thai = db.Column(db.String(12), nullable=False, default="cho_duyet", index=True)   # cho_duyet | da_duyet | tu_choi | spam
    khoa_khach = db.Column(db.String(64), index=True)                       # mã băm thiết bị (chống spam), không phải IP thô
    tra_loi = db.Column(db.Text)                                             # câu trả lời công khai của Khoa Dược
    nguoi_tra_loi_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id", ondelete="SET NULL"))
    ngay_tra_loi = db.Column(db.DateTime)
    nguoi_duyet_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id", ondelete="SET NULL"))
    ngay_duyet = db.Column(db.DateTime)
    ngay_tao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class KhachHang(db.Model):
    """Tài khoản chat riêng của khách: mỗi SỐ ĐIỆN THOẠI 1 tài khoản, tự đăng ký khi nhập số mới. KHÔNG có mã bí mật
    (SĐT không xác minh qua SMS nên ai biết số đều vào xem được; có giới hạn thử theo thiết bị)."""
    __tablename__ = "khach_hang"

    id = db.Column(db.Integer, primary_key=True)
    so_dien_thoai = db.Column(db.String(15), unique=True, nullable=False, index=True)
    ten = db.Column(db.String(100), nullable=False)
    pin_hash = db.Column(db.String(255), nullable=False, default="")   # CỘT CŨ, không còn dùng (giữ để khỏi phải đổi DB)
    phien_ver = db.Column(db.Integer, nullable=False, default=1)      # tăng lên khi admin chặn → mọi thiết bị của khách bị đăng xuất
    so_lan_sai = db.Column(db.Integer, nullable=False, default=0)     # CỘT CŨ, không còn dùng
    khoa_den = db.Column(db.DateTime)                                  # CỘT CŨ, không còn dùng
    bi_chan = db.Column(db.Boolean, nullable=False, default=False)
    ngay_tao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    lan_cuoi = db.Column(db.DateTime, default=datetime.utcnow)


class TinNhanRieng(db.Model):
    """Tin nhắn trong cuộc trò chuyện riêng giữa 1 khách (theo SĐT) và Khoa Dược."""
    __tablename__ = "tin_nhan_rieng"

    id = db.Column(db.Integer, primary_key=True)
    khach_id = db.Column(db.Integer, db.ForeignKey("khach_hang.id", ondelete="CASCADE"), nullable=False, index=True)
    tu = db.Column(db.String(8), nullable=False)                      # khach | admin
    noi_dung = db.Column(db.Text, nullable=False)
    loai = db.Column(db.String(10), nullable=False, default="ho_tro")  # ho_tro | gop_y | bao_loi
    ngu_canh = db.Column(db.String(200))                              # vd "Báo lỗi: Tương tác thuốc"
    ngu_canh_url = db.Column(db.String(300))                          # đường dẫn nội bộ của trang bị báo lỗi
    admin_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id", ondelete="SET NULL"))
    da_doc_khach = db.Column(db.Boolean, nullable=False, default=False)
    da_doc_admin = db.Column(db.Boolean, nullable=False, default=False)
    ngay_tao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class ThongBao(db.Model):
    """Thông báo cho TỪNG admin (chuông ở thanh trên trang quản trị). Cùng 1 nguồn (khoa_gop) mà chưa đọc thì gộp lại."""
    __tablename__ = "thong_bao"

    id = db.Column(db.Integer, primary_key=True)
    nguoi_nhan_id = db.Column(db.Integer, db.ForeignKey("nguoi_dung.id", ondelete="CASCADE"), nullable=False, index=True)
    loai = db.Column(db.String(20), nullable=False)                   # y_kien_moi | tin_nhan_moi
    tieu_de = db.Column(db.String(200), nullable=False)
    noi_dung = db.Column(db.String(300))
    url = db.Column(db.String(300))
    khoa_gop = db.Column(db.String(64), index=True)
    so_luong = db.Column(db.Integer, nullable=False, default=1)
    da_doc = db.Column(db.Boolean, nullable=False, default=False, index=True)
    ngay_tao = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)


class ChatLanThu(db.Model):
    """Đếm số lần nhập SĐT / đăng ký mới theo THIẾT BỊ (mã băm) để chống dò số và spam."""
    __tablename__ = "chat_lan_thu"

    id = db.Column(db.Integer, primary_key=True)
    khoa = db.Column(db.String(64), nullable=False, index=True)
    loai = db.Column(db.String(12), nullable=False)                   # sai_ma | tao_moi
    thoi_gian = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
