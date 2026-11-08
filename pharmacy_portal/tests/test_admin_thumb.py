"""Ảnh trong bảng danh sách thuốc (admin) phải đủ lớn và không bị co nhỏ."""
import os
import re
import tempfile
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from flask import url_for                                         # noqa: E402

from app import create_app, db                                    # noqa: E402
from app.models.models import DanhMucThuoc, NguoiDung, NhaThuocBV  # noqa: E402
from config import Config                                         # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "app")
LISTS = ("thuoc", "danh_muc_thuoc", "nha_thuoc_bv", "nhom_thuoc")


def doc(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


class CssAnhThuNho(unittest.TestCase):
    def test_single_definition_with_large_portrait_size(self):
        css = doc("static", "css", "style.css")
        self.assertEqual(len(re.findall(r"^\.adm-thumb \{", css, re.M)), 1, "chỉ một nơi quyết định kích thước ảnh")
        w = int(re.search(r"--adm-thumb-w:\s*(\d+)px", css).group(1)); h = int(re.search(r"--adm-thumb-h:\s*(\d+)px", css).group(1))
        self.assertGreaterEqual(w, 56); self.assertGreater(h, w)                    # đủ lớn, dạng đứng
        blk = css[css.index(".adm-thumb {"):].split("}")[0]
        for s in ("max-width: none", "min-width: var(--adm-thumb-w)", "object-fit: cover"):
            self.assertIn(s, blk)                                                    # không bị img{max-width:100%} ép nhỏ

    def test_thumb_column_is_wide_enough_for_the_image(self):
        css = doc("static", "css", "style.css")
        self.assertIn(".adm-table th.adm-col-thumb { width: calc(var(--adm-thumb-w) + 32px); }", css)

    def test_list_templates_no_longer_force_a_42px_image_column(self):
        for f in LISTS:
            t = doc("templates", "admin", f, "danh_sach.html")
            self.assertNotIn('style="width:42px;"', t, f)
            self.assertIn("adm-col-thumb", t, f)


class TrangDanhSach(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.tmp}/t.db", "SQLALCHEMY_ENGINE_OPTIONS": {}})
        self.app = create_app(cfg)
        with self.app.app_context():
            db.create_all()
            u = NguoiDung(ten_dang_nhap="admin1", vai_tro="quan_tri"); u.set_password("mat-khau-123456")
            db.session.add_all([u, DanhMucThuoc(ten_biet_duoc="LIDOCAIN", hinh_anh="https://example.com/a.jpg"),
                                NhaThuocBV(ten_biet_duoc="SPRAY", hinh_anh="https://example.com/b.jpg")])
            db.session.commit()
        self.c = self.app.test_client()
        self.c.post("/admin/dang-nhap", data={"ten_dang_nhap": "admin1", "mat_khau": "mat-khau-123456"})

    def trang(self, endpoint):
        with self.app.test_request_context():
            url = url_for(endpoint)
        return self.c.get(url).get_data(as_text=True)

    def test_drug_lists_render_big_thumbnails(self):
        for ep in ("admin_dmt.danh_sach", "admin_ntbv.danh_sach"):
            h = self.trang(ep)
            self.assertIn('class="adm-thumb"', h, ep); self.assertIn('class="adm-col-thumb"', h, ep)
            self.assertNotIn("width:42px", h, ep)


if __name__ == "__main__":
    unittest.main()
