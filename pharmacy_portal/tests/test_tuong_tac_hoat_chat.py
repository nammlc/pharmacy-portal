"""Tương tác thuốc theo cặp HOẠT CHẤT: thêm tay, CHỐNG TRÙNG, nhập Excel, tra cứu, thùng rác."""
import io
import os
import tempfile
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from openpyxl import Workbook                                                # noqa: E402
from sqlalchemy.exc import IntegrityError                                    # noqa: E402

from app import create_app, db                                               # noqa: E402
from app.models.models import (DanhMucThuoc, HoatChat, NguoiDung, NhomThuoc,  # noqa: E402
                               ThungRac, TuongTacHoatChat)
from config import Config                                                    # noqa: E402

U = "/admin/tuong-tac-thuoc"
HEADER = ["STT", "Hoạt chất 1", "Hoạt chất 2", "Mức độ", "Cơ chế", "Hậu quả", "Xử trí"]


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


def xlsx_bytes(rows):
    wb = Workbook(); ws = wb.active
    ws.append(HEADER)
    for r in rows:
        ws.append(list(r))
    b = io.BytesIO(); wb.save(b)
    return b.getvalue()


class TuongTacHoatChatTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.tmp}/t.db", "SQLALCHEMY_ENGINE_OPTIONS": {}})
        self.app = create_app(cfg)
        with self.app.app_context():
            db.create_all()
            u = NguoiDung(ten_dang_nhap="admin1", vai_tro="quan_tri"); u.set_password("mat-khau-123456")
            self.hc = {n: HoatChat(ten_hoat_chat=n) for n in ("Warfarin", "Aspirin", "Paracetamol", "Cafein")}
            db.session.add_all([u, *self.hc.values()]); db.session.commit()
            self.id = {n: h.id for n, h in self.hc.items()}
        self.c = self.app.test_client()
        self.c.post("/admin/dang-nhap", data={"ten_dang_nhap": "admin1", "mat_khau": "mat-khau-123456"})

    # ---------- tiện ích ----------
    def them(self, a, b, muc="nang"):
        return self.c.post(f"{U}/them", data={"hoat_chat_a_id": self.id[a], "hoat_chat_b_id": self.id[b], "muc_do": muc,
                                              "hau_qua_lam_sang": "<p>x</p>", "xu_tri": "<p>y</p>"})

    def so_cap(self):
        with self.app.app_context():
            return TuongTacHoatChat.query.count()

    def tai_len(self, rows):
        return self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc",
                           data={"file_du_lieu": (io.BytesIO(xlsx_bytes(rows)), "tt.xlsx")}, content_type="multipart/form-data")

    # ---------- thêm tay + chống trùng ----------
    def test_them_tay_luu_theo_thu_tu_id_nho_truoc(self):
        r = self.them("Warfarin", "Aspirin")
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            x = TuongTacHoatChat.query.one()
            self.assertLess(x.hoat_chat_a_id, x.hoat_chat_b_id)

    def test_them_lai_cap_da_co_ke_ca_dao_thu_tu_bi_chan_va_chi_duong_mo_ban_ghi_cu(self):
        self.assertEqual(self.them("Warfarin", "Aspirin").status_code, 302)
        for a, b in (("Warfarin", "Aspirin"), ("Aspirin", "Warfarin")):
            r = self.them(a, b)
            self.assertEqual(r.status_code, 200)                            # ở lại form, không lưu
            h = r.get_data(as_text=True)
            self.assertIn("Cặp này đã có trong hệ thống", h)
            self.assertIn("Mở bản ghi đã có để sửa", h)
        self.assertEqual(self.so_cap(), 1)

    def test_hai_hoat_chat_giong_nhau_bi_chan(self):
        r = self.them("Warfarin", "Warfarin")
        self.assertEqual(r.status_code, 200); self.assertIn("phải khác nhau", r.get_data(as_text=True))
        self.assertEqual(self.so_cap(), 0)

    def test_sua_thanh_cap_da_ton_tai_bi_chan_nhung_sua_noi_dung_cua_chinh_no_thi_duoc(self):
        self.them("Warfarin", "Aspirin"); self.them("Warfarin", "Cafein")
        with self.app.app_context():
            tu = TuongTacHoatChat.query.filter_by(muc_do="nang").all()
            ids = [x.id for x in tu]
        # đổi cặp thứ hai thành cặp của cặp thứ nhất -> bị chặn
        r = self.c.post(f"{U}/{ids[1]}/sua", data={"hoat_chat_a_id": self.id["Aspirin"], "hoat_chat_b_id": self.id["Warfarin"], "muc_do": "nang"})
        self.assertEqual(r.status_code, 200); self.assertIn("đã có trong hệ thống", r.get_data(as_text=True))
        # sửa mức độ của chính nó, giữ nguyên cặp -> được
        r = self.c.post(f"{U}/{ids[0]}/sua", data={"hoat_chat_a_id": self.id["Warfarin"], "hoat_chat_b_id": self.id["Aspirin"], "muc_do": "nhe"})
        self.assertEqual(r.status_code, 302)

    def test_rang_buoc_csdl_la_chot_chan_cuoi(self):
        a, b = self.id["Warfarin"], self.id["Aspirin"]
        lo, hi = min(a, b), max(a, b)
        with self.app.app_context():
            db.session.add(TuongTacHoatChat(hoat_chat_a_id=hi, hoat_chat_b_id=lo, muc_do="nhe"))   # sai thứ tự
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()
            db.session.add(TuongTacHoatChat(hoat_chat_a_id=lo, hoat_chat_b_id=hi, muc_do="nhe")); db.session.commit()
            db.session.add(TuongTacHoatChat(hoat_chat_a_id=lo, hoat_chat_b_id=hi, muc_do="nang"))  # trùng cặp
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_kiem_tra_cap_json(self):
        self.them("Warfarin", "Aspirin")
        g = lambda a, b: self.c.get(f"{U}/kiem-tra-cap?a={self.id[a]}&b={self.id[b]}").get_json()
        self.assertEqual(g("Aspirin", "Warfarin")["trang_thai"], "da_co")
        self.assertEqual(g("Warfarin", "Cafein")["trang_thai"], "chua_co")
        self.assertEqual(g("Warfarin", "Warfarin")["trang_thai"], "giong_nhau")
        self.assertEqual(self.c.get(f"{U}/kiem-tra-cap?a=0&b=0").get_json()["trang_thai"], "chua_du")

    def test_danh_sach_co_tim_kiem_va_nhan_nghiem_trong(self):
        self.them("Warfarin", "Aspirin", "nang"); self.them("Paracetamol", "Cafein", "nhe")
        h = self.c.get(f"{U}/?q=warf").get_data(as_text=True)
        self.assertIn("Warfarin", h); self.assertNotIn("Cafein", h); self.assertIn("Nghiêm trọng", h)

    def test_khong_xoa_duoc_hoat_chat_dang_co_tuong_tac(self):
        self.them("Warfarin", "Aspirin")
        self.c.post(f"/admin/hoat-chat/{self.id['Warfarin']}/xoa")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(HoatChat, self.id["Warfarin"]))

    # ---------- nhập Excel ----------
    FILE = [
        (1, "Methotrexat", "Aspirin ", "Chống chỉ định", "cc", "hq", "1. a\n2. b"),
        (2, "aspirin", "METHOTREXAT", "Chống chỉ định", "cc", "hq", "1. a\n2. b"),   # đảo + hoa/thường + y hệt -> gộp
        (3, "Warfarin", "Cafein", "Nghiêm trọng", "", "hq2", "xt2"),
        (4, "Warfarin", "Cafein", "Nghiêm trọng", "", "hq3", "xt3"),                  # cùng cặp khác nội dung -> xung đột
        (5, "Paracetamol", "Cafein", "", "", "", ""),                                 # thiếu mức độ -> bỏ qua
    ]

    def test_nhap_excel_xem_truoc_va_luu_dung_so_luong(self):
        self.assertEqual(self.tai_len(self.FILE).status_code, 302)
        h = self.c.get("/admin/nhap-hang-loat/tuong-tac-thuoc/xem-truoc").get_data(as_text=True)
        self.assertIn("Xem trước", h); self.assertIn("nhóm xung đột", h); self.assertIn("Methotrexat", h)
        r = self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            self.assertEqual(TuongTacHoatChat.query.count(), 2)                       # (Methotrexat,Aspirin) + (Warfarin,Cafein)
            self.assertEqual(HoatChat.query.filter(HoatChat.ten_hoat_chat.in_(["Methotrexat"])).count(), 1)
            x = [t for t in TuongTacHoatChat.query.all() if {t.hoat_chat_a.ten_hoat_chat, t.hoat_chat_b.ten_hoat_chat} == {"Warfarin", "Cafein"}][0]
            self.assertEqual(x.xu_tri, "<p>xt2</p>")                                  # mặc định dùng dòng đứng trước
            self.assertEqual(x.muc_do, "nang")
            y = [t for t in TuongTacHoatChat.query.all() if t is not x][0]
            self.assertEqual(y.xu_tri, "<p>1. a</p><p>2. b</p>")
            self.assertLess(y.hoat_chat_a_id, y.hoat_chat_b_id)
        self.assertIn("Đã nhập xong", self.c.get("/admin/nhap-hang-loat/tuong-tac-thuoc/ket-qua").get_data(as_text=True))

    def test_nhap_lai_cung_file_khong_tao_trung_va_ghi_de_chi_khi_duoc_chon(self):
        self.tai_len(self.FILE); self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={})
        so = self.so_cap()
        self.tai_len(self.FILE)
        r = self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={})   # mặc định BỎ QUA cặp đã có
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.so_cap(), so)
        moi = [(1, "Methotrexat", "Aspirin", "Nhẹ", "", "hq-moi", "")]
        self.tai_len(moi)
        self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={"che_do_trung": "ghi_de"})
        with self.app.app_context():
            self.assertEqual(self.so_cap_(), so)
            x = [t for t in TuongTacHoatChat.query.all() if "Methotrexat" in (t.hoat_chat_a.ten_hoat_chat, t.hoat_chat_b.ten_hoat_chat)][0]
            self.assertEqual((x.muc_do, x.hau_qua_lam_sang), ("nhe", "<p>hq-moi</p>"))
            self.assertEqual(x.xu_tri, "<p>1. a</p><p>2. b</p>")                      # ô trống trong file KHÔNG xoá chữ cũ

    def so_cap_(self):
        return TuongTacHoatChat.query.count()

    def test_chon_dong_xung_dot_va_ghep_ten(self):
        self.tai_len(self.FILE)
        h = self.c.get("/admin/nhap-hang-loat/tuong-tac-thuoc/xem-truoc").get_data(as_text=True)
        self.assertIn('name="xd_ma"', h)
        ma = h.split('name="xd_ma" value="')[1].split('"')[0]
        self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={"xd_ma": ma, "xd_0": "5"})   # dòng 5 trong file = dòng dữ liệu thứ 4
        with self.app.app_context():
            x = [t for t in TuongTacHoatChat.query.all() if {t.hoat_chat_a.ten_hoat_chat, t.hoat_chat_b.ten_hoat_chat} == {"Warfarin", "Cafein"}][0]
            self.assertEqual(x.xu_tri, "<p>xt3</p>")

    def test_file_sai_mau_bao_loi_ro_rang(self):
        wb = Workbook(); ws = wb.active; ws.append(["A", "B"]); ws.append([1, 2])
        b = io.BytesIO(); wb.save(b)
        r = self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc", data={"file_du_lieu": (io.BytesIO(b.getvalue()), "x.xlsx")},
                        content_type="multipart/form-data", follow_redirects=True)
        self.assertIn("Không tìm thấy dòng tiêu đề đúng mẫu", r.get_data(as_text=True))

    def test_file_mau_tai_duoc_va_nhap_lai_duoc(self):
        r = self.c.get("/admin/nhap-hang-loat/mau-tuong-tac-thuoc.xlsx")
        self.assertEqual(r.status_code, 200)
        self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc", data={"file_du_lieu": (io.BytesIO(r.data), "mau.xlsx")},
                    content_type="multipart/form-data")
        self.assertEqual(self.c.post("/admin/nhap-hang-loat/tuong-tac-thuoc/xac-nhan", data={}).status_code, 302)
        self.assertEqual(self.so_cap(), 2)

    # ---------- tra cứu công khai ----------
    def test_tra_cuu_theo_hoat_chat_va_theo_ten_biet_duoc(self):
        with self.app.app_context():
            nhom = NhomThuoc(ten_nhom="Giảm đau"); db.session.add(nhom); db.session.flush()
            dm = DanhMucThuoc(ten_biet_duoc="Panadol Extra", nhom_thuoc_id=nhom.id)
            dm.hoat_chat_list = [db.session.get(HoatChat, self.id["Paracetamol"]), db.session.get(HoatChat, self.id["Cafein"])]
            db.session.add(dm); db.session.commit()
        self.them("Paracetamol", "Warfarin", "chong_chi_dinh")
        h = self.c.get("/tra-cuu-tuong-tac-thuoc/?q=Warfarin").get_data(as_text=True)
        self.assertIn("Paracetamol", h); self.assertIn("Chống chỉ định", h)
        h = self.c.get("/tra-cuu-tuong-tac-thuoc/?q=Panadol").get_data(as_text=True)
        self.assertIn("Warfarin", h); self.assertIn("chứa:", h); self.assertIn("Cafein", h)

    # ---------- thùng rác ----------
    def test_xoa_roi_khoi_phuc_va_khong_khoi_phuc_khi_cap_da_duoc_them_lai(self):
        self.them("Warfarin", "Aspirin")
        with self.app.app_context():
            tid = TuongTacHoatChat.query.one().id
        self.c.post(f"{U}/{tid}/xoa")
        self.assertEqual(self.so_cap(), 0)
        with self.app.app_context():
            rid = ThungRac.query.one().id
        self.assertEqual(self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc").status_code, 302)
        self.assertEqual(self.so_cap(), 1)
        # xoá lần nữa, thêm lại cùng cặp, rồi thử khôi phục -> không tạo trùng
        with self.app.app_context():
            tid = TuongTacHoatChat.query.one().id
        self.c.post(f"{U}/{tid}/xoa"); self.them("Aspirin", "Warfarin")
        with self.app.app_context():
            rid = ThungRac.query.one().id
        self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc")
        self.assertEqual(self.so_cap(), 1)


if __name__ == "__main__":
    unittest.main()
