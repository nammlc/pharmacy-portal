"""Lưu ảnh trên máy chủ: lưu/thu nhỏ/xoá, route /uploads, chống đường dẫn lạ.

Chạy độc lập (không cần database): nạp trực tiếp các module cần thiết theo đường dẫn file.
    python -m unittest tests.test_luu_tru_anh
"""
import importlib.util
import io
import os
import re
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _nap(ten, duong_dan):
    """Nạp module theo đường dẫn, bỏ qua app/__init__.py (nặng, cần database)."""
    for goi in ("app", "app.utils", "app.routes"):
        if goi not in sys.modules:
            m = types.ModuleType(goi)
            m.__path__ = []
            sys.modules[goi] = m
    spec = importlib.util.spec_from_file_location(ten, os.path.join(ROOT, duong_dan))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[ten] = mod
    spec.loader.exec_module(mod)
    return mod


LT = _nap("app.utils.luu_tru_anh", "app/utils/luu_tru_anh.py")
sys.modules["app.utils"].luu_tru_anh = LT
UP = _nap("app.utils.upload_anh", "app/utils/upload_anh.py")
ANH = _nap("app.routes.anh", "app/routes/anh.py")

from flask import Flask                                                   # noqa: E402
from PIL import Image                                                      # noqa: E402


class Gia:
    """Giả FileStorage."""
    def __init__(self, du_lieu, ten="a.jpg"):
        self.stream = io.BytesIO(du_lieu)
        self.filename = ten


def anh_bytes(dinh_dang="JPEG", kich_thuoc=(3000, 2000), mau="red", mode="RGB"):
    bo = io.BytesIO()
    Image.new(mode, kich_thuoc, mau).save(bo, dinh_dang)
    return bo.getvalue()


class Co(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(UPLOAD_DIR=self.tmp.name, ANH_LUU_TRU="local", TESTING=True)
        self.app.register_blueprint(ANH.bp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.c = self.app.test_client()

    def tearDown(self):
        self.ctx.pop()
        self.tmp.cleanup()


class LuuAnh(Co):
    def test_jpeg_lon_bi_thu_nho_va_giu_ti_le(self):
        url = LT.luu_anh(Gia(anh_bytes()), "pharmacy/thuoc", 800, 800, "limit")
        self.assertRegex(url, r"^/uploads/pharmacy/thuoc/thuoc_[0-9a-f]{12}\.jpg$")
        with Image.open(LT.duong_dan_tu_url(url)) as im:
            self.assertEqual(im.size, (800, 533))

    def test_fill_cat_dung_khung(self):
        url = LT.luu_anh(Gia(anh_bytes()), "pharmacy/nhom_thuoc", 400, 400, "fill")
        with Image.open(LT.duong_dan_tu_url(url)) as im:
            self.assertEqual(im.size, (400, 400))

    def test_duoi_file_theo_dinh_dang_that(self):
        url = LT.luu_anh(Gia(anh_bytes("PNG", (50, 50), (0, 0, 0, 0), "RGBA"), "giaumat.jpg"), "pharmacy/x")
        self.assertTrue(url.endswith(".png"))
        with Image.open(LT.duong_dan_tu_url(url)) as im:
            self.assertEqual(im.mode, "RGBA")
        self.assertTrue(LT.luu_anh(Gia(anh_bytes("WEBP", (60, 60))), "pharmacy/x").endswith(".webp"))

    def test_gif_giu_nguyen(self):
        du_lieu = anh_bytes("GIF", (30, 30))
        url = LT.luu_anh(Gia(du_lieu), "pharmacy/x")
        self.assertEqual(LT.duong_dan_tu_url(url).read_bytes(), du_lieu)

    def test_file_khong_phai_anh_bi_tu_choi(self):
        for rac in (b"", b"<script>alert(1)</script>", b"GIF89a-hong", b"\xff\xd8\xff" + b"x" * 50):
            with self.assertRaises(ValueError):
                LT.luu_anh(Gia(rac, "a.jpg"), "pharmacy/x")
        self.assertEqual(list(__import__("pathlib").Path(self.tmp.name).rglob("*.*")), [])   # không để lại file rác

    def test_upload_anh_chon_che_do_local(self):
        url = UP.upload_anh_hero(Gia(anh_bytes(kich_thuoc=(4000, 1000))))
        self.assertTrue(url.startswith("/uploads/pharmacy/hero/"))
        with Image.open(LT.duong_dan_tu_url(url)) as im:
            self.assertEqual(im.size, (2400, 600))

    def test_thay_anh_xoa_anh_cu(self):
        cu = UP.upload_anh_thuoc(Gia(anh_bytes("JPEG", (200, 200))))
        moi = UP.upload_anh_thuoc(Gia(anh_bytes("JPEG", (200, 200))), url_cu=cu)
        self.assertNotEqual(cu, moi)
        self.assertFalse(LT.duong_dan_tu_url(cu).exists())            # ảnh cũ đã bị xoá
        self.assertTrue(LT.duong_dan_tu_url(moi).exists())


class DuongDan(Co):
    def test_chan_duong_dan_nguy_hiem(self):
        for xau in ("/uploads/../config.py", "/uploads/a/../../x.jpg", "/uploads/.cache/200w/a.jpg", "/uploads/a//b.jpg",
                    "/uploads/%2e%2e/x.jpg", "/uploads/a b.jpg", "/uploads/a\\b.jpg", "/uploads/", "/uploads/a/",
                    "/static/x.jpg", "https://res.cloudinary.com/x.jpg", "", None, "/uploads/.hidden.jpg"):
            self.assertIsNone(LT.duong_dan_tu_url(xau), xau)

    def test_duong_dan_hop_le(self):
        p = LT.duong_dan_tu_url("/uploads/pharmacy/thuoc/thuoc_ab12.jpg?w=480")
        self.assertEqual(p, LT.thu_muc_goc() / "pharmacy" / "thuoc" / "thuoc_ab12.jpg")


class Tep(Co):
    def test_pdf_hop_le_va_gia_mao(self):
        url = LT.luu_tep(Gia(b"%PDF-1.4 abc"), "pharmacy/bai_viet_dinh_kem", "pdf")
        self.assertRegex(url, r"bai_viet_dinh_kem_[0-9a-f]{12}\.pdf$")
        with self.assertRaises(ValueError):
            LT.luu_tep(Gia(b"<html><script>x</script>"), "pharmacy/bai_viet_dinh_kem", "pdf")
        with self.assertRaises(ValueError):
            LT.luu_tep(Gia(b"%PDF"), "pharmacy/bai_viet_dinh_kem", "exe")

    def test_upload_tep_qua_upload_anh(self):
        url, ten = UP.upload_tep_dinh_kem_bai_viet(Gia(b"PK\x03\x04zzz", "Bao cao.zip"))
        self.assertEqual(ten, "Bao cao.zip")
        self.assertTrue(url.startswith("/uploads/pharmacy/bai_viet_dinh_kem/"))
        self.assertTrue(UP.xoa_tep_dinh_kem_cloudinary(url))
        self.assertFalse(LT.duong_dan_tu_url(url).exists())


class Route(Co):
    def setUp(self):
        super().setUp()
        self.url = LT.luu_anh(Gia(anh_bytes(kich_thuoc=(3000, 2000))), "pharmacy/hero", 3000, 3000, "limit")

    def test_phuc_vu_anh_goc(self):
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "image/jpeg")
        self.assertIn("immutable", r.headers["Cache-Control"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")

    def test_ban_thu_nho_webp_va_luu_dem(self):
        r = self.c.get(self.url + "?w=480")
        self.assertEqual((r.status_code, r.mimetype), (200, "image/webp"))
        self.assertEqual(Image.open(io.BytesIO(r.data)).size, (480, 320))
        cache = LT.thu_muc_goc() / ".cache" / "480w"
        self.assertEqual(len(list(cache.rglob("*.webp"))), 1)
        self.assertEqual(self.c.get(self.url + "?w=480").status_code, 200)         # lần 2 dùng bản đã lưu

    def test_co_la_duoc_keo_ve_co_cho_phep(self):
        r = self.c.get(self.url + "?w=500")
        self.assertEqual(Image.open(io.BytesIO(r.data)).size[0], 480)
        for w in ("99999", "0", "-5", "abc"):
            self.assertEqual(self.c.get(self.url + f"?w={w}").status_code, 200)
        self.assertLessEqual(len(list((LT.thu_muc_goc() / ".cache").iterdir())), len(LT.RONG_CHO_PHEP))

    def test_khong_phong_to_anh_nho(self):
        nho = LT.luu_anh(Gia(anh_bytes(kich_thuoc=(300, 200))), "pharmacy/x")
        self.assertEqual(Image.open(io.BytesIO(self.c.get(nho + "?w=1200").data)).size, (300, 200))

    def test_anh_vuong(self):
        r = self.c.get(self.url + "?w=112&c=1")
        self.assertEqual(Image.open(io.BytesIO(r.data)).size, (112, 112))

    def test_304_khi_chua_doi(self):
        r = self.c.get(self.url)
        r2 = self.c.get(self.url, headers={"If-None-Match": r.headers["ETag"]})
        self.assertEqual(r2.status_code, 304)

    def test_404_cac_truong_hop_la(self):
        goc = LT.thu_muc_goc()
        (goc / "pharmacy").mkdir(exist_ok=True)
        (goc / "pharmacy" / "bi_mat.txt").write_text("x")
        (goc / "pharmacy" / "trang.html").write_text("<script>1</script>")
        self.c.get(self.url + "?w=480")
        for u in ("/uploads/khong_co.jpg", "/uploads/pharmacy/bi_mat.txt", "/uploads/pharmacy/trang.html",
                  "/uploads/.cache/480w/pharmacy/hero/x.webp", "/uploads/../config.py", "/uploads/pharmacy/"):
            self.assertEqual(self.c.get(u).status_code, 404, u)

    def test_pdf_hien_trong_trinh_duyet_con_zip_thi_tai_ve(self):
        pdf = LT.luu_tep(Gia(b"%PDF-1.4 x"), "pharmacy/bai_viet_dinh_kem", "pdf")
        zp = LT.luu_tep(Gia(b"PK\x03\x04x"), "pharmacy/bai_viet_dinh_kem", "zip")
        rp, rz = self.c.get(pdf), self.c.get(zp)
        self.assertEqual(rp.mimetype, "application/pdf")
        self.assertNotIn("attachment", rp.headers.get("Content-Disposition", ""))
        self.assertIn("attachment", rz.headers["Content-Disposition"])

    def test_xoa_anh_don_ca_ban_thu_nho(self):
        self.c.get(self.url + "?w=480")
        self.c.get(self.url + "?w=112&c=1")
        self.assertTrue(UP.xoa_anh_cloudinary(self.url))
        self.assertEqual(list((LT.thu_muc_goc() / ".cache").rglob("*.webp")), [])
        self.assertEqual(self.c.get(self.url).status_code, 404)
        self.assertFalse(UP.xoa_anh_cloudinary(self.url))                       # xoá lần 2 không lỗi


class DoiUrl(Co):
    def test_url_thu_nho_cho_anh_local_va_cloudinary_van_nhu_cu(self):
        self.assertEqual(UP.anh_thu_nho("/uploads/pharmacy/thuoc/a.jpg"), "/uploads/pharmacy/thuoc/a.jpg?w=112&c=1")
        self.assertEqual(UP.anh_theo_chieu_rong("/uploads/pharmacy/hero/a.jpg", 960), "/uploads/pharmacy/hero/a.jpg?w=960")
        self.assertEqual(UP.anh_theo_chieu_rong("/uploads/a.jpg?w=480", 960), "/uploads/a.jpg?w=480")      # đã có tham số
        cl = "https://res.cloudinary.com/demo/image/upload/v1/pharmacy/hero/a.jpg"
        self.assertIn("/upload/f_auto,q_auto,c_limit,w_960/", UP.anh_theo_chieu_rong(cl, 960))
        self.assertIn("c_fill,w_112,h_112", UP.anh_thu_nho(cl))
        self.assertEqual(UP.anh_thu_nho(""), "")
        self.assertEqual(UP.anh_thu_nho("https://lh3.googleusercontent.com/x"), "https://lh3.googleusercontent.com/x")

    def test_regex_url_an_toan_cua_hero_nhan_uploads(self):
        ma = open(os.path.join(ROOT, "app/utils/hero.py"), encoding="utf-8").read()
        mau = re.search(r"_RE_URL_AN_TOAN = re\.compile\((r\".*?\")\)", ma).group(1)
        rx = re.compile(eval(mau))
        for tot in ("https://res.cloudinary.com/a/b.jpg", "/uploads/pharmacy/hero/hero_ab12.jpg?w=1920"):
            self.assertTrue(rx.match(tot), tot)
        for xau in ("http://a/b.jpg", "//a/b.jpg", "/static/a.jpg", "/uploads/a\"onerror=x", "/uploads/a b.jpg", "javascript:alert(1)", ""):
            self.assertFalse(rx.match(xau), xau)


if __name__ == "__main__":
    unittest.main()
