from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, SelectField, PasswordField, SubmitField
)
from wtforms.validators import DataRequired, Length, Optional


class DangNhapForm(FlaskForm):
    ten_dang_nhap = StringField("Tên đăng nhập", validators=[DataRequired()])
    mat_khau = PasswordField("Mật khẩu", validators=[DataRequired()])
    submit = SubmitField("Đăng nhập")


class DoiMatKhauForm(FlaskForm):
    mat_khau_hien_tai = PasswordField("Mật khẩu hiện tại", validators=[DataRequired()])
    mat_khau_moi = PasswordField("Mật khẩu mới", validators=[DataRequired(), Length(min=8, message="Mật khẩu mới cần ít nhất 8 ký tự.")])
    xac_nhan_mat_khau_moi = PasswordField("Nhập lại mật khẩu mới", validators=[DataRequired()])
    submit = SubmitField("Đổi mật khẩu")


class ThuocForm(FlaskForm):
    ten_thuoc = StringField("Tên thuốc", validators=[DataRequired(), Length(max=255)])
    hoat_chat = StringField("Hoạt chất", validators=[Optional(), Length(max=255)])
    ham_luong = StringField("Hàm lượng", validators=[Optional(), Length(max=100)])
    dang_bao_che = StringField("Dạng bào chế", validators=[Optional(), Length(max=100)])
    nhom_thuoc = StringField("Nhóm dược lý", validators=[Optional(), Length(max=150)])
    nha_san_xuat = StringField("Nhà sản xuất", validators=[Optional(), Length(max=255)])
    so_dang_ky = StringField("Số đăng ký", validators=[Optional(), Length(max=100)])
    submit = SubmitField("Lưu")


class ThuocTiemTruyenForm(FlaskForm):
    thuoc_id = SelectField("Thuốc", coerce=int, validators=[DataRequired()])
    dung_moi_pha_loang = StringField("Dung môi pha loãng", validators=[Optional()])
    nong_do_toi_da = StringField("Nồng độ tối đa", validators=[Optional()])
    toc_do_truyen = StringField("Tốc độ truyền", validators=[Optional()])
    thoi_gian_truyen = StringField("Thời gian truyền", validators=[Optional()])
    do_on_dinh = StringField("Độ ổn định", validators=[Optional()])
    dieu_kien_bao_quan = StringField("Điều kiện bảo quản", validators=[Optional()])
    canh_bao = TextAreaField("Cảnh báo", validators=[Optional()])
    nguon_tham_khao = StringField("Nguồn tham khảo", validators=[Optional()])
    submit = SubmitField("Lưu")


class TuongHopTuongKyForm(FlaskForm):
    thuoc_a_id = SelectField("Thuốc A", coerce=int, validators=[DataRequired()])
    thuoc_b_id = SelectField("Thuốc B", coerce=int, validators=[DataRequired()])
    trang_thai = SelectField(
        "Trạng thái",
        choices=[("tuong_hop", "Tương hợp"), ("tuong_ky", "Tương kỵ"), ("chua_xac_dinh", "Chưa xác định")],
        validators=[DataRequired()],
    )
    mo_ta = TextAreaField("Mô tả", validators=[Optional()])
    nguon_tham_khao = StringField("Nguồn tham khảo", validators=[Optional()])
    submit = SubmitField("Lưu")


class TuongTacThuocForm(FlaskForm):
    thuoc_a_id = SelectField("Thuốc A", coerce=int, validators=[DataRequired()])
    thuoc_b_id = SelectField("Thuốc B", coerce=int, validators=[DataRequired()])
    muc_do = SelectField(
        "Mức độ",
        choices=[
            ("nhe", "Nhẹ"), ("trung_binh", "Trung bình"),
            ("nang", "Nặng"), ("chong_chi_dinh", "Chống chỉ định"),
        ],
        validators=[DataRequired()],
    )
    co_che = TextAreaField("Cơ chế", validators=[Optional()])
    hau_qua_lam_sang = TextAreaField("Hậu quả lâm sàng", validators=[Optional()])
    xu_tri = TextAreaField("Xử trí", validators=[Optional()])
    nguon_tham_khao = StringField("Nguồn tham khảo", validators=[Optional()])
    submit = SubmitField("Lưu")


class ThongTinThuocForm(FlaskForm):
    thuoc_id = SelectField("Thuốc", coerce=int, validators=[DataRequired()])
    chi_dinh = TextAreaField("Chỉ định", validators=[Optional()])
    chong_chi_dinh = TextAreaField("Chống chỉ định", validators=[Optional()])
    lieu_dung_nguoi_lon = TextAreaField("Liều dùng người lớn", validators=[Optional()])
    lieu_dung_tre_em = TextAreaField("Liều dùng trẻ em", validators=[Optional()])
    tac_dung_phu = TextAreaField("Tác dụng phụ", validators=[Optional()])
    than_trong = TextAreaField("Thận trọng", validators=[Optional()])
    phu_nu_co_thai_cho_con_bu = TextAreaField("Phụ nữ có thai / cho con bú", validators=[Optional()])
    nguon_tham_khao = StringField("Nguồn tham khảo", validators=[Optional()])
    submit = SubmitField("Lưu")


class ThongTinBenhNhanForm(FlaskForm):
    tieu_de = StringField("Tiêu đề", validators=[DataRequired(), Length(max=255)])
    danh_muc = StringField("Danh mục", validators=[Optional(), Length(max=150)])
    noi_dung = TextAreaField("Nội dung", validators=[DataRequired()])
    submit = SubmitField("Lưu")
