"""Gợi ý tìm kiếm: có ảnh thuốc, dropdown rộng bằng cả thanh tìm kiếm (máy tính + điện thoại)."""
import os
import tempfile
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app import create_app, db                       # noqa: E402
from app.models.models import DanhMucThuoc, HoatChat, NhaThuocBV  # noqa: E402
from app.utils.upload_anh import anh_thu_nho         # noqa: E402
from config import Config                            # noqa: E402

CLD = "https://res.cloudinary.com/demo/image/upload/v1700000000/thuoc/lidocain.jpg"
ROOT = os.path.join(os.path.dirname(__file__), "..", "app", "static")


def doc(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


class AnhThuNho(unittest.TestCase):
    def test_cloudinary_url_gets_square_thumbnail(self):
        self.assertEqual(anh_thu_nho(CLD), "https://res.cloudinary.com/demo/image/upload/c_fill,w_112,h_112,f_auto,q_auto/v1700000000/thuoc/lidocain.jpg")
        self.assertIn("w_64,h_64", anh_thu_nho(CLD, 64))

    def test_other_urls_and_empty_are_left_alone(self):
        self.assertEqual(anh_thu_nho(""), ""); self.assertEqual(anh_thu_nho(None), "")
        self.assertEqual(anh_thu_nho("https://example.com/a.jpg"), "https://example.com/a.jpg")
        cu = "https://res.cloudinary.com/demo/image/upload/w_300/v1/a.jpg"          # đã có biến đổi → không chèn thêm
        self.assertEqual(anh_thu_nho(cu), cu)


class GoiYApi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.tmp}/t.db", "SQLALCHEMY_ENGINE_OPTIONS": {}})
        self.app = create_app(cfg)
        with self.app.app_context():
            db.create_all()
            hc = HoatChat(ten_hoat_chat="Lidocain")
            db.session.add_all([
                DanhMucThuoc(ten_biet_duoc="LIDOCAIN 40MG", hinh_anh=CLD, hoat_chat_list=[hc]),
                DanhMucThuoc(ten_biet_duoc="LIDOCAIN KHÔNG ẢNH"),
                NhaThuocBV(ten_biet_duoc="LIDOCAIN SPRAY", hinh_anh="https://example.com/spray.png"),
            ])
            db.session.commit()
        self.c = self.app.test_client()

    def goi_y(self, scope="all", q="lidocain"):
        return self.c.get(f"/api/goi-y-tim-kiem?scope={scope}&q={q}").get_json()

    def test_each_suggestion_carries_an_image_field(self):
        ds = {x["ten"]: x for x in self.goi_y()}
        self.assertEqual(set(ds), {"LIDOCAIN 40MG", "LIDOCAIN KHÔNG ẢNH", "LIDOCAIN SPRAY"})
        self.assertIn("c_fill,w_112,h_112", ds["LIDOCAIN 40MG"]["anh"])           # ảnh Cloudinary được thu nhỏ
        self.assertEqual(ds["LIDOCAIN KHÔNG ẢNH"]["anh"], "")                      # chưa có ảnh → rỗng (JS hiện chữ cái đầu)
        self.assertEqual(ds["LIDOCAIN SPRAY"]["anh"], "https://example.com/spray.png")

    def test_image_also_in_single_scope(self):
        self.assertTrue(all("anh" in x for x in self.goi_y("dmt")))
        self.assertTrue(all("anh" in x for x in self.goi_y("ntbv")))

    def test_short_query_still_empty(self):
        self.assertEqual(self.goi_y(q="l"), [])


class GiaoDien(unittest.TestCase):
    def test_script_renders_image_and_fallback_and_marks_the_form(self):
        js = doc("js", "goi_y_tim_kiem.js")
        for s in ('form.classList.add("goi-y-form")', "goi-y-anh", "goi-y-anh-trong", "it.anh", 'addEventListener("error"',
                  "goi-y-noidung"):
            self.assertIn(s, js, s)

    def test_dropdown_spans_the_whole_search_bar(self):
        css = doc("css", "style.css")
        self.assertIn(".goi-y-form { position: relative; }", css)
        self.assertIn(".goi-y-form .goi-y-wrap { position: static; }", css)           # form (không phải ô nhập) là khung định vị
        dd = css[css.index(".goi-y-dropdown {"):].split("}")[0]
        self.assertIn("left: 0", dd); self.assertIn("right: 0", dd)

    def test_thumbnail_style_on_desktop_and_mobile(self):
        css = doc("css", "style.css")
        anh = css[css.index(".goi-y-anh {"):].split("}")[0]
        self.assertIn("width: 48px", anh); self.assertIn("object-fit: cover", anh)
        mobile = css[css.index("@media (max-width: 640px) {\n  .goi-y-dropdown"):].split("\n}")[0]
        self.assertIn("width: 52px", mobile); self.assertIn("max-height", mobile)

    def test_all_search_forms_use_the_script(self):
        import glob
        base = open(os.path.join(os.path.dirname(__file__), "..", "app", "templates", "base.html"), encoding="utf-8").read()
        self.assertIn("goi_y_tim_kiem.js", base)
        n = sum("data-goi-y" in open(f, encoding="utf-8").read()
                for f in glob.glob(os.path.join(os.path.dirname(__file__), "..", "app", "templates", "**", "*.html"), recursive=True))
        self.assertGreaterEqual(n, 5)


if __name__ == "__main__":
    unittest.main()
