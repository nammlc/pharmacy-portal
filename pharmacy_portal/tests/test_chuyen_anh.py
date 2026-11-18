"""Script chuyển ảnh Cloudinary -> máy chủ: nhận diện URL, thay URL, tải, áp dụng, kiểm tra, hoàn tác.

Chạy độc lập (không cần SQLAlchemy / mạng): dùng 'kho' giả và hàm tải giả.
    python -m unittest tests.test_chuyen_anh
"""
import argparse
import copy
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace as NS

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("chuyen_anh", os.path.join(ROOT, "chuyen_anh_tu_cloudinary.py"))
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

C = "https://res.cloudinary.com/demo"
ANH1 = f"{C}/image/upload/v100/pharmacy/thuoc/thuoc_aaa111.jpg"
ANH2 = f"{C}/image/upload/v200/pharmacy/bai_viet_noi_dung/bai_viet_noi_dung_bbb222.png"
HERO = f"{C}/image/upload/v300/pharmacy/hero/hero_ccc333.jpg"
PDF = f"{C}/raw/upload/v400/pharmacy/bai_viet_dinh_kem/bai_viet_dinh_kem_ddd444.pdf"
HONG = f"{C}/image/upload/v500/pharmacy/thuoc/thuoc_eee555.jpg"
NGOAI = "https://res.cloudinary.com/nguoi-la/image/upload/v1/x/y.jpg"


def anh(dinh_dang, mau, kich=(40, 30)):
    bo = io.BytesIO()
    Image.new("RGB", kich, mau).save(bo, dinh_dang)
    return bo.getvalue()


NOI_DUNG = {
    ANH1: (anh("JPEG", "red"), "image/jpeg"),
    ANH2: (anh("PNG", "blue"), "image/png"),
    HERO: (anh("JPEG", "green", (80, 40)), "image/jpeg"),
    PDF: (b"%PDF-1.4 noi dung", "application/pdf"),
}


class KhoGia:
    bang_khong_khoa = []

    def __init__(self, bang):
        self.bang = bang

    def quet(self, mau):
        for ten, b in self.bang.items():
            for h in b["hang"]:
                for cot, v in h.items():
                    if cot != b["pk"] and isinstance(v, str) and mau in v:
                        yield ten, {b["pk"]: h[b["pk"]]}, cot, v

    def cap_nhat_nhieu(self, ds):
        ban_sao = copy.deepcopy(self.bang)
        for tc in ds:
            b = ban_sao[tc["bang"]]
            (hang,) = [h for h in b["hang"] if all(h[k] == v for k, v in tc["khoa"].items())]
            if hang[tc["cot"]] != tc["cu"]:
                raise RuntimeError("đã bị đổi")
            hang[tc["cot"]] = tc["moi"]
        self.bang = ban_sao                       # giao dịch: chỉ gán khi tất cả đều ổn


def du_lieu_goc():
    html = (f'<p>Xin chào</p><img src="{ANH2}"><p>tiếp</p>'
            f"<img src='{ANH2.replace('/upload/', '/upload/c_fill,w_300,h_200,f_auto,q_auto/')}' alt='trùng ảnh, khác biến đổi'>"
            f'<a href="{PDF}?_a=BAABAAAA">tải</a><div style="background:url({ANH1})"></div>'
            f'<img src="{ANH1}&quot;"> <img src="{NGOAI}">')
    return {
        "thuoc": {"pk": "id", "hang": [{"id": 1, "ten": "A", "hinh_anh": ANH1}, {"id": 2, "ten": "B", "hinh_anh": ""},
                                       {"id": 3, "ten": "C", "hinh_anh": "https://lh3.googleusercontent.com/zzz"}]},
        "bai_viet": {"pk": "id", "hang": [{"id": 7, "tieu_de": "t", "noi_dung": html, "file_dinh_kem": PDF}]},
        "cai_dat": {"pk": "khoa", "hang": [{"khoa": "hero_hinh_anh", "gia_tri": HERO}, {"khoa": "hero_do_phu", "gia_tri": "66"}]},
    }


class Co(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.up = os.path.join(self.tmp, "uploads")
        self.lv = os.path.join(self.tmp, "chuyen_anh")
        os.environ["UPLOAD_DIR"] = self.up
        self.kho = KhoGia(du_lieu_goc())
        self.cfg = NS(CLOUDINARY_CLOUD_NAME="demo")
        self.args = argparse.Namespace(thu_muc=self.lv, luong=3, yes=True, bo_qua_loi=False, goi_thu="", tep="")
        self.hong = True                                         # mô phỏng 1 ảnh bị lỗi 404
        self.goc_tai = M.tai_bytes
        M.tai_bytes = self.tai_gia
        self.in_ra = io.StringIO()

    def tearDown(self):
        M.tai_bytes = self.goc_tai
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tai_gia(self, url, *a, **k):
        if url == HONG:
            if self.hong:
                raise OSError("HTTP 404")
            return anh("JPEG", "black"), "image/jpeg"
        if url in NOI_DUNG:
            return NOI_DUNG[url]
        raise OSError("HTTP 404")

    def chay(self, ham):
        import contextlib
        with contextlib.redirect_stdout(self.in_ra):
            return ham(self.args, self.kho, self.cfg)

    def ban_do(self):
        with open(os.path.join(self.lv, M.BAN_DO), encoding="utf-8") as f:
            return json.load(f)["muc"]


class NhanDien(unittest.TestCase):
    def test_url_thuong_va_url_bien_doi_cung_mot_anh(self):
        a = M.phan_tich(ANH1)
        b = M.phan_tich(ANH1.replace("/upload/", "/upload/c_fill,w_112,h_112,f_auto,q_auto/"))
        c = M.phan_tich(ANH1.replace("/upload/", "/upload/f_auto,q_auto,c_limit,w_960/"))
        self.assertEqual(a["goc"], ANH1)
        self.assertEqual({a["goc"], b["goc"], c["goc"]}, {ANH1})
        self.assertEqual(a["public"], "pharmacy/thuoc/thuoc_aaa111.jpg")

    def test_url_khong_co_phien_ban(self):
        t = M.phan_tich(f"{C}/image/upload/c_fill,w_100/pharmacy/thuoc/a.jpg")
        self.assertEqual(t["public"], "pharmacy/thuoc/a.jpg")
        t = M.phan_tich(f"{C}/image/upload/my_folder/a.jpg")                 # thư mục tên my_folder KHÔNG phải biến đổi
        self.assertEqual(t["public"], "my_folder/a.jpg")

    def test_tim_url_trong_html(self):
        ds = M.tim_url(du_lieu_goc()["bai_viet"]["hang"][0]["noi_dung"], "demo")
        cua_toi = {t["goc"] for t in ds if t["cua_toi"]}
        self.assertEqual(cua_toi, {ANH1, ANH2, PDF})
        self.assertEqual([t["goc"] for t in ds if not t["cua_toi"]], [NGOAI])
        self.assertEqual(M.tim_url("không có gì", "demo"), [])
        self.assertEqual(M.tim_url(None, "demo"), [])

    def test_thay_url_giu_nguyen_dau_nhay_thuc_the_va_anh_khac(self):
        bd = {ANH1: {"ok": True, "local": "/uploads/pharmacy/thuoc/thuoc_aaa111.jpg"},
              ANH2: {"ok": True, "local": "/uploads/pharmacy/bai_viet_noi_dung/b.png"},
              PDF: {"ok": True, "local": "/uploads/pharmacy/bai_viet_dinh_kem/d.pdf"}}
        moi, n = M.thay_url(du_lieu_goc()["bai_viet"]["hang"][0]["noi_dung"], bd, "demo")
        self.assertEqual(n, 5)
        self.assertIn('<img src="/uploads/pharmacy/bai_viet_noi_dung/b.png">', moi)
        self.assertIn("<img src='/uploads/pharmacy/bai_viet_noi_dung/b.png' alt=", moi)
        self.assertIn('href="/uploads/pharmacy/bai_viet_dinh_kem/d.pdf"', moi)           # bỏ ?_a=...
        self.assertIn("url(/uploads/pharmacy/thuoc/thuoc_aaa111.jpg)", moi)
        self.assertIn('src="/uploads/pharmacy/thuoc/thuoc_aaa111.jpg&quot;"', moi)         # giữ thực thể &quot;
        self.assertIn(NGOAI, moi)                                                          # tài khoản khác: không đụng
        self.assertNotIn("res.cloudinary.com/demo", moi)

    def test_query_cua_cloudinary_dung_truoc_thuc_the_html(self):
        bd = {ANH1: {"ok": True, "local": "/uploads/a.jpg"}}
        moi, n = M.thay_url(f'<div style="background:url(&quot;{ANH1}?_a=BAAB&quot;)"></div>', bd, "demo")
        self.assertEqual((moi, n), ('<div style="background:url(&quot;/uploads/a.jpg&quot;)"></div>', 1))
        moi, n = M.thay_url(f"Xem ảnh tại {ANH1}.", bd, "demo")                  # dấu chấm cuối câu không dính vào URL
        self.assertEqual((moi, n), ("Xem ảnh tại /uploads/a.jpg.", 1))

    def test_anh_loi_thi_giu_nguyen_url(self):
        moi, n = M.thay_url(f'<img src="{ANH1}">', {ANH1: {"ok": False, "local": ""}}, "demo")
        self.assertEqual((moi, n), (f'<img src="{ANH1}">', 0))


class ToanTrinh(Co):
    def test_loi_tai_thi_khong_sua_database(self):
        truoc = copy.deepcopy(self.kho.bang)
        self.hong = True
        self.kho.bang["thuoc"]["hang"][1]["hinh_anh"] = HONG
        truoc = copy.deepcopy(self.kho.bang)
        self.assertEqual(self.chay(M.lenh_tai_ve), 2)
        self.assertEqual(self.chay(M.lenh_ap_dung), 2)
        self.assertEqual(self.kho.bang, truoc)                                   # database nguyên vẹn
        self.assertFalse(self.ban_do()[HONG]["ok"])
        self.assertTrue(self.ban_do()[ANH1]["ok"])                               # ảnh khác vẫn đã tải

    def test_bo_qua_loi_chi_chuyen_anh_da_tai(self):
        self.kho.bang["thuoc"]["hang"][1]["hinh_anh"] = HONG
        self.args.bo_qua_loi = True
        self.assertEqual(self.chay(M.lenh_ap_dung), 0)
        self.assertEqual(self.kho.bang["thuoc"]["hang"][1]["hinh_anh"], HONG)    # ảnh lỗi còn trên Cloudinary
        self.assertTrue(self.kho.bang["thuoc"]["hang"][0]["hinh_anh"].startswith("/uploads/"))

    def test_quy_trinh_day_du(self):
        goc = copy.deepcopy(self.kho.bang)
        self.assertEqual(self.chay(M.lenh_kiem_ke), 0)
        self.assertEqual(self.chay(M.lenh_tai_ve), 0)
        self.assertEqual(self.kho.bang, goc)                                     # tai-ve không đụng database
        self.assertEqual(self.chay(M.lenh_ap_dung), 0)

        t = self.kho.bang
        url1 = t["thuoc"]["hang"][0]["hinh_anh"]
        self.assertEqual(url1, "/uploads/pharmacy/thuoc/thuoc_aaa111.jpg")
        self.assertEqual(t["thuoc"]["hang"][2]["hinh_anh"], "https://lh3.googleusercontent.com/zzz")   # nơi khác: giữ
        self.assertEqual(t["cai_dat"]["hang"][0]["gia_tri"], "/uploads/pharmacy/hero/hero_ccc333.jpg")
        self.assertEqual(t["cai_dat"]["hang"][1]["gia_tri"], "66")
        self.assertEqual(t["bai_viet"]["hang"][0]["file_dinh_kem"], "/uploads/pharmacy/bai_viet_dinh_kem/bai_viet_dinh_kem_ddd444.pdf")
        html = t["bai_viet"]["hang"][0]["noi_dung"]
        self.assertNotIn("res.cloudinary.com/demo", html)
        self.assertIn(NGOAI, html)

        # file giống HỆT từng byte với bản gốc (không nén lại)
        for goc_url, (du_lieu, _) in NOI_DUNG.items():
            local = self.ban_do()[goc_url]["local"]
            with open(os.path.join(self.up, local[len("/uploads/"):]), "rb") as f:
                self.assertEqual(f.read(), du_lieu, goc_url)
        # sao lưu để hoàn tác
        sao = [f for f in os.listdir(self.lv) if f.startswith("sao_luu_db_")]
        self.assertEqual(len(sao), 1)

        self.assertEqual(self.chay(M.lenh_kiem_tra), 0)
        self.assertEqual(self.chay(M.lenh_ap_dung), 0)                           # chạy lại: không còn gì để làm
        self.assertEqual(len([f for f in os.listdir(self.lv) if f.startswith("sao_luu_db_")]), 1)

        # mất file -> kiem-tra phải báo
        os.remove(os.path.join(self.up, "pharmacy/hero/hero_ccc333.jpg"))
        self.assertEqual(self.chay(M.lenh_kiem_tra), 1)
        self.assertIn("THIẾU file", self.in_ra.getvalue())

        # hoàn tác
        self.args.tep = os.path.join(self.lv, sao[0])
        self.assertEqual(self.chay(M.lenh_hoan_tac), 0)
        self.assertEqual(self.kho.bang, goc)

    def test_giao_dich_ca_goi_neu_co_o_bi_doi(self):
        goc = copy.deepcopy(self.kho.bang)
        thay = [{"bang": "thuoc", "khoa": {"id": 1}, "cot": "hinh_anh", "cu": ANH1, "moi": "/uploads/x.jpg"},
                {"bang": "cai_dat", "khoa": {"khoa": "hero_hinh_anh"}, "cot": "gia_tri", "cu": "ĐÃ BỊ ĐỔI", "moi": "/uploads/y.jpg"}]
        with self.assertRaises(RuntimeError):
            self.kho.cap_nhat_nhieu(thay)
        self.assertEqual(self.kho.bang, goc)                                     # ô thứ nhất cũng không bị sửa

    def test_khong_co_gi_de_chuyen(self):
        self.kho = KhoGia({"thuoc": {"pk": "id", "hang": [{"id": 1, "hinh_anh": "/uploads/a.jpg"}]}})
        self.assertEqual(self.chay(M.lenh_ap_dung), 0)


class TenFile(Co):
    def test_trung_ten_khac_anh_khong_de_len_nhau(self):
        v1 = f"{C}/image/upload/v1/pharmacy/thuoc/trung.jpg"
        v2 = f"{C}/image/upload/v2/pharmacy/thuoc/trung.jpg"
        NOI_DUNG[v1] = (anh("JPEG", "red"), "image/jpeg")
        NOI_DUNG[v2] = (anh("JPEG", "blue"), "image/jpeg")
        try:
            self.kho = KhoGia({"t": {"pk": "id", "hang": [{"id": 1, "a": v1, "b": v2}]}})
            self.assertEqual(self.chay(M.lenh_ap_dung), 0)
            h = self.kho.bang["t"]["hang"][0]
            self.assertNotEqual(h["a"], h["b"])
            for u, k in ((h["a"], v1), (h["b"], v2)):
                with open(os.path.join(self.up, u[len("/uploads/"):]), "rb") as f:
                    self.assertEqual(f.read(), NOI_DUNG[k][0])
        finally:
            NOI_DUNG.pop(v1), NOI_DUNG.pop(v2)

    def test_sua_duoi_theo_noi_dung_that_va_them_duoi_thieu(self):
        a = f"{C}/image/upload/v1/pharmacy/x/giaumat.jpeg"         # đuôi .jpeg nhưng thật ra là PNG
        b = f"{C}/image/upload/v1/pharmacy/x/khong_duoi"            # không có đuôi
        NOI_DUNG[a] = (anh("PNG", "red"), "image/png")
        NOI_DUNG[b] = (anh("JPEG", "red"), "image/jpeg")
        try:
            self.kho = KhoGia({"t": {"pk": "id", "hang": [{"id": 1, "a": a, "b": b}]}})
            self.assertEqual(self.chay(M.lenh_ap_dung), 0)
            h = self.kho.bang["t"]["hang"][0]
            self.assertEqual((h["a"], h["b"]), ("/uploads/pharmacy/x/giaumat.png", "/uploads/pharmacy/x/khong_duoi.jpg"))
        finally:
            NOI_DUNG.pop(a), NOI_DUNG.pop(b)

    def test_tu_choi_noi_dung_gia_mao(self):
        gia = f"{C}/image/upload/v1/pharmacy/x/gia.jpg"
        NOI_DUNG[gia] = (b"<html>khong phai anh</html>", "image/jpeg")
        try:
            self.kho = KhoGia({"t": {"pk": "id", "hang": [{"id": 1, "a": gia}]}})
            self.assertEqual(self.chay(M.lenh_ap_dung), 2)
            self.assertEqual(self.kho.bang["t"]["hang"][0]["a"], gia)
        finally:
            NOI_DUNG.pop(gia)

    def test_ten_co_dau_cach_va_ky_tu_la(self):
        a = f"{C}/image/upload/v1/pharmacy/x/%E1%BA%A3nh%20thu%E1%BB%91c.jpg"
        NOI_DUNG[a] = (anh("JPEG", "red"), "image/jpeg")
        try:
            self.kho = KhoGia({"t": {"pk": "id", "hang": [{"id": 1, "a": a}]}})
            self.assertEqual(self.chay(M.lenh_ap_dung), 0)
            u = self.kho.bang["t"]["hang"][0]["a"]
            self.assertRegex(u, r"^/uploads/pharmacy/x/[A-Za-z0-9._\-]+\.jpg$")
            self.assertTrue(os.path.isfile(os.path.join(self.up, u[len("/uploads/"):])))
        finally:
            NOI_DUNG.pop(a)


if __name__ == "__main__":
    unittest.main()
