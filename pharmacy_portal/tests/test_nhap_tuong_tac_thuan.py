"""Logic THUẦN của nhập hàng loạt tương tác thuốc (không cần CSDL): đọc file, ghép tên, CHỐNG TRÙNG."""
import io
import unittest

from openpyxl import Workbook

from app.utils import nhap_tuong_tac as nt


class _File:
    def __init__(self, ten, data):
        self.filename, self.stream = ten, io.BytesIO(data)


def xlsx(rows, header=("STT", "Hoạt chất 1", "Hoạt chất 2", "Mức độ", "Cơ chế", "Hậu quả", "Xử trí")):
    wb = Workbook(); ws = wb.active
    ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    b = io.BytesIO(); wb.save(b)
    return _File("f.xlsx", b.getvalue())


def dong(so, a, b, muc="Chống chỉ định", xu_tri="x"):
    d = nt.DongNhap(so_dong=so, ten_a=a, ten_b=b, muc_do_goc=muc, xu_tri=xu_tri)
    d.muc_do, hop_le = nt.anh_xa_muc_do(muc); d.muc_do_la = bool(muc) and not hop_le
    return d


def ke_hoach(dongs, hc=None, cap=None, **kw):
    return nt.lap_ke_hoach(dongs, hc or {}, cap or {}, **kw)


class ChuanHoaTen(unittest.TestCase):
    def test_khoa_khong_phan_biet_hoa_thuong_dau_khoang_trang(self):
        self.assertEqual(nt.khoa_ten("Ceftriaxon"), nt.khoa_ten("  ceftriaxon "))
        self.assertEqual(nt.khoa_ten("Đường  Glucose"), nt.khoa_ten("duong glucose"))
        self.assertEqual(nt.khoa_ten("Grazoprevir/ elbasvir"), nt.khoa_ten("Grazoprevir/elbasvir"))

    def test_muc_do(self):
        self.assertEqual(nt.anh_xa_muc_do("Nghiêm trọng")[0], "nang")
        self.assertEqual(nt.anh_xa_muc_do("  chống chỉ định ")[0], "chong_chi_dinh")
        self.assertEqual(nt.anh_xa_muc_do("Vừa phải")[0], "trung_binh")
        self.assertEqual(nt.anh_xa_muc_do(""), (None, True))
        self.assertEqual(nt.anh_xa_muc_do("kỳ lạ"), (None, False))

    def test_noi_dung_o_duoc_escape_va_tach_doan(self):
        self.assertEqual(nt.van_ban_sang_html("1. a\n2. <b>b</b>"), "<p>1. a</p><p>2. &lt;b&gt;b&lt;/b&gt;</p>")


class DocFile(unittest.TestCase):
    def test_doc_bo_dong_trong_va_bo_qua_stt(self):
        f = xlsx([(1, "A", "B", "Nghiêm trọng", "cc", "hq", "xt"), (None, None, None, None, None, None, None), (633, "C", "D", "Nhẹ", "", "", "")])
        ds = nt.doc_file_tuong_tac(f)
        self.assertEqual([(d.so_dong, d.ten_a, d.ten_b, d.muc_do) for d in ds], [(2, "A", "B", "nang"), (4, "C", "D", "nhe")])

    def test_thieu_cot_bat_buoc_bao_loi_de_hieu(self):
        with self.assertRaises(ValueError) as e:
            nt.doc_file_tuong_tac(xlsx([], header=("STT", "Hoạt chất 1", "Cơ chế")))
        self.assertIn("Hoạt chất 2", str(e.exception))


class ChongTrung(unittest.TestCase):
    def test_cap_dao_thu_tu_la_mot_cap_va_giong_het_thi_gop(self):
        kh = ke_hoach([dong(2, "A", "B"), dong(3, "B", "A")])
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["trung_giong"], kh.so_lieu["nhom_xung_dot"]), (1, 1, 0))
        self.assertEqual([r.trang_thai for r in kh.ket_qua], [nt.OK, nt.TRUNG_GIONG])

    def test_khac_hoa_thuong_va_khoang_trang_van_la_mot_hoat_chat(self):
        kh = ke_hoach([dong(2, "Ceftriaxon", "Calci"), dong(3, " calci ", "CEFTRIAXON")])
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["trung_giong"], kh.so_lieu["hoat_chat_moi"]), (1, 1, 2))

    def test_cung_cap_khac_noi_dung_la_xung_dot_va_chon_duoc_dong(self):
        ds = [dong(2, "A", "B", xu_tri="cách 1"), dong(3, "B", "A", xu_tri="cách 2")]
        kh = ke_hoach(ds)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["nhom_xung_dot"], kh.so_lieu["loai_xung_dot"]), (1, 1, 1))
        self.assertEqual(kh.nhom_xung_dot[0]["dang_dung"], 2)             # mặc định dòng đứng trước
        ma = kh.nhom_xung_dot[0]["ma"]
        kh2 = ke_hoach(ds, chon_xung_dot={ma: 3})
        self.assertEqual(kh2.nhom_xung_dot[0]["dang_dung"], 3)
        dung = [r for r in kh2.ket_qua if r.trang_thai == nt.OK][0]
        self.assertEqual(dung.dong.xu_tri, "cách 2")

    def test_cap_da_co_trong_csdl_bo_qua_hoac_ghi_de(self):
        hc = {nt.khoa_ten("A"): (1, "A"), nt.khoa_ten("B"): (2, "B")}
        cap = {(1, 2): 99}
        kh = ke_hoach([dong(2, "B", "A")], hc, cap)                        # đảo thứ tự vẫn nhận ra
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["da_co_bo_qua"], kh.so_lieu["cap_nhat"]), (0, 1, 0))
        kh = ke_hoach([dong(2, "B", "A")], hc, cap, che_do_trung=nt.CHE_DO_GHI_DE)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["cap_nhat"]), (0, 1))

    def test_ghep_ten_lam_xuat_hien_trung_thi_van_bat_duoc(self):
        # "Ceftriaxone" (gõ sai) được ghép vào "Ceftriaxon" => 2 dòng thành cùng một cặp
        ds = [dong(2, "Ceftriaxon", "Calci"), dong(3, "Ceftriaxone", "Calci")]
        self.assertEqual(ke_hoach(ds).so_lieu["tao"], 2)
        qd = {nt.khoa_ten("Ceftriaxone"): {"hanh_dong": "ghep", "dich": "ceftriaxon"}}
        kh = ke_hoach(ds, quyet_dinh=qd)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["trung_giong"], kh.so_lieu["hoat_chat_moi"]), (1, 1, 2))

    def test_ghep_vao_hoat_chat_co_san_thi_nhan_ra_cap_da_co(self):
        hc = {nt.khoa_ten("Ceftriaxon"): (5, "Ceftriaxon"), nt.khoa_ten("Calci"): (6, "Calci")}
        qd = {nt.khoa_ten("Ceftriaxone"): {"hanh_dong": "ghep", "dich": "Ceftriaxon"}}
        kh = ke_hoach([dong(2, "Ceftriaxone", "Calci")], hc, {(5, 6): 1}, quyet_dinh=qd)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["da_co_bo_qua"]), (0, 1))

    def test_hai_ten_thanh_mot_sau_khi_ghep_la_loi_khong_tao_tu_tuong_tac(self):
        qd = {nt.khoa_ten("Ceftriaxone"): {"hanh_dong": "ghep", "dich": "Ceftriaxon"}}
        kh = ke_hoach([dong(2, "Ceftriaxon", "Ceftriaxone")], quyet_dinh=qd)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["loi"]), (0, 1))

    def test_cung_ten_hai_cot_la_loi(self):
        self.assertEqual(ke_hoach([dong(2, "A", "a")]).so_lieu["loi"], 1)

    def test_ghep_vao_ten_khong_ton_tai_la_loi_ro_rang(self):
        qd = {nt.khoa_ten("X"): {"hanh_dong": "ghep", "dich": "Không có"}}
        kh = ke_hoach([dong(2, "X", "B")], quyet_dinh=qd)
        self.assertEqual(kh.ket_qua[0].trang_thai, nt.LOI); self.assertIn("Không có", kh.ket_qua[0].ly_do)


class MucDoThieu(unittest.TestCase):
    def test_thieu_muc_do_mac_dinh_bo_qua_va_co_the_chon(self):
        ds = [dong(2, "A", "B", muc="")]
        kh = ke_hoach(ds)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["thieu_muc_do"]), (0, 1))
        kh = ke_hoach(ds, muc_do_chon={2: "nang"})
        self.assertEqual((kh.so_lieu["tao"], kh.ket_qua[0].muc_do_cuoi), (1, "nang"))
        self.assertEqual(ke_hoach(ds, muc_do_chon={2: "bo"}).so_lieu["tao"], 0)

    def test_chu_muc_do_la_khong_bi_doan(self):
        kh = ke_hoach([dong(2, "A", "B", muc="Rất xấu")])
        self.assertEqual(kh.ket_qua[0].trang_thai, nt.THIEU_MUC_DO)


class BoQuaTen(unittest.TestCase):
    def test_chon_bo_mot_hoat_chat_thi_bo_cac_dong_co_ten_do(self):
        qd = {nt.khoa_ten("A"): {"hanh_dong": "bo"}}
        kh = ke_hoach([dong(2, "A", "B"), dong(3, "C", "D")], quyet_dinh=qd)
        self.assertEqual((kh.so_lieu["tao"], kh.so_lieu["bo_qua_ten"], kh.so_lieu["hoat_chat_moi"]), (1, 1, 2))


if __name__ == "__main__":
    unittest.main()
