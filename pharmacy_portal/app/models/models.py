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
    vai_tro = db.Column(db.String(50), default="duoc_si")   # duoc_si, quan_tri...
    dang_hoat_dong = db.Column(db.Boolean, default=True)
    ngay_tao = db.Column(db.DateTime, default=datetime.utcnow)

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
    # CHÚ Ý: hoat_chat_id giữ lại để tương thích dữ liệu cũ / không phá schema,
    # nhưng KHÔNG còn dùng trong code - quan hệ hoạt chất giờ dùng
    # `hoat_chat_list` (nhiều-nhiều) bên dưới.
    hoat_chat_id = db.Column(db.Integer, db.ForeignKey("hoat_chat.id"), nullable=True)
    ten_biet_duoc = db.Column(db.String(255), nullable=False, index=True)
    thanh_phan = db.Column(db.Text)
    chi_dinh = db.Column(db.Text)
    chong_chi_dinh = db.Column(db.Text)
    cach_dung_lieu_dung = db.Column(db.Text)
    link_chi_tiet = db.Column(db.String(500))
    hinh_anh = db.Column(db.String(500))
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhom = db.relationship("NhomThuoc", backref="danh_muc_thuoc_list")
    hoat_chat = db.relationship("HoatChat", foreign_keys=[hoat_chat_id])  # cũ - giữ tương thích
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
    # CHÚ Ý: hoat_chat_id giữ lại để tương thích dữ liệu cũ / không phá schema,
    # nhưng KHÔNG còn dùng trong code - quan hệ hoạt chất giờ dùng
    # `hoat_chat_list` (nhiều-nhiều) bên dưới.
    hoat_chat_id = db.Column(db.Integer, db.ForeignKey("hoat_chat.id"), nullable=True)
    ten_biet_duoc = db.Column(db.String(255), nullable=False, index=True)
    link_tham_khao = db.Column(db.String(500))
    hinh_anh = db.Column(db.String(500))
    ngay_cap_nhat = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    nhom = db.relationship("NhomThuoc", backref="nha_thuoc_bv_list")
    hoat_chat = db.relationship("HoatChat", foreign_keys=[hoat_chat_id])  # cũ - giữ tương thích
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
