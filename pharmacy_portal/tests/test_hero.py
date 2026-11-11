"""Ảnh nền (hero) trang chủ: 2 ảnh riêng (máy tính / điện thoại), kéo giãn vừa khung, không cắt."""
import io
import os
import re
import unittest
from unittest import mock

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app.models.models import CaiDat                                    # noqa: E402
from app.utils import hero as H                                         # noqa: E402
from tests.test_phan_hoi import Co                                      # noqa: E402

PC = "https://res.cloudinary.com/demo/image/upload/v111/pharmacy/hero/pc.jpg"
MB = "https://res.cloudinary.com/demo/image/upload/v222/pharmacy/hero_mobile/mb.jpg"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Hero(Co):
    def dat(self, **kw):
        with self.app.app_context():
            for k, v in kw.items():
                CaiDat.dat(k, v)
            from app import db
            db.session.commit()

    def trang_chu(self):
        r = self.client().get("/trang-chu")
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def test_no_image_keeps_default_blue_hero(self):
        h = self.trang_chu()
        self.assertNotIn("hero--anh", h); self.assertNotIn("<picture>", h)

    def test_only_pc_image_is_used_for_all_screens(self):
        self.dat(**{H.K_ANH: PC})
        h = self.trang_chu()
        self.assertIn("hero--anh", h); self.assertIn("v111/pharmacy/hero/pc.jpg", h)
        self.assertNotIn("<source", h)

    def test_only_mobile_image_is_used_for_all_screens(self):
        self.dat(**{H.K_ANH_MOBILE: MB})
        h = self.trang_chu()
        self.assertIn("hero--anh", h); self.assertIn("v222/pharmacy/hero_mobile/mb.jpg", h)
        self.assertNotIn("<source", h)

    def test_both_images_phone_gets_its_own_source(self):
        self.dat(**{H.K_ANH: PC, H.K_ANH_MOBILE: MB})
        h = self.trang_chu()
        src = re.search(r'<source media="\(max-width: (\d+)px\)" srcset="([^"]+)"', h)
        self.assertIsNotNone(src)
        self.assertEqual(int(src.group(1)), H.MOBILE_MAX_WIDTH)             # khớp @media của CSS
        self.assertIn("v222/pharmacy/hero_mobile/mb.jpg", src.group(2))
        img = re.search(r'<img class="hero-bg" src="([^"]+)"', h).group(1)
        self.assertIn("v111/pharmacy/hero/pc.jpg", img)                     # máy tính dùng ảnh PC
        self.assertNotIn("object-position", h)                              # không còn cắt / định vị ảnh

    def test_css_stretches_image_and_never_crops(self):
        css = open(os.path.join(ROOT, "app/static/css/style.css"), encoding="utf-8").read()
        rule = re.search(r"\.hero--anh \.hero-bg \{([^}]*)\}", css).group(1)
        self.assertIn("object-fit: fill", rule); self.assertNotIn("cover", rule)
        self.assertIn("position: absolute", rule)                           # ảnh không tham gia bố cục => không đổi kích thước trang
        self.assertIn("@media (max-width: %dpx)" % H.MOBILE_MAX_WIDTH, css)

    def test_admin_form_has_two_uploads_and_no_crop_option(self):
        a = self.admin()
        r = a.get("/admin/anh-trang-chu/")
        self.assertEqual(r.status_code, 200)
        h = r.get_data(as_text=True)
        self.assertIn('name="file_anh"', h); self.assertIn('name="file_anh_mobile"', h)
        self.assertNotIn('name="vi_tri"', h)
        self.assertIn("object-fit:fill", h)

    def test_admin_upload_replace_and_delete_each_image(self):
        a = self.admin()
        with mock.patch("app.routes.admin_hero.upload_anh_hero", return_value=PC), \
             mock.patch("app.routes.admin_hero.upload_anh_hero_mobile", return_value=MB), \
             mock.patch("app.routes.admin_hero.xoa_anh_cloudinary") as xoa:
            r = a.post("/admin/anh-trang-chu/", data={"file_anh": (io.BytesIO(b"x"), "pc.jpg"), "file_anh_mobile": (io.BytesIO(b"y"), "mb.jpg"),
                                                      "do_phu": "70", "alt": "Toàn cảnh"}, content_type="multipart/form-data")
            self.assertIn(r.status_code, (302, 303))
            self.assertEqual(self.q(lambda: (CaiDat.lay(H.K_ANH), CaiDat.lay(H.K_ANH_MOBILE), CaiDat.lay(H.K_DO_PHU))), (PC, MB, "70"))
            # xoá riêng ảnh điện thoại, ảnh máy tính giữ nguyên
            a.post("/admin/anh-trang-chu/", data={"xoa_anh_mobile": "1", "do_phu": "70"})
            self.assertEqual(self.q(lambda: (CaiDat.lay(H.K_ANH), CaiDat.lay(H.K_ANH_MOBILE))), (PC, ""))
            xoa.assert_called_with(MB)

    def test_admin_upload_error_keeps_old_image_and_does_not_claim_success(self):
        self.dat(**{H.K_ANH: PC})
        a = self.admin()
        with mock.patch("app.routes.admin_hero.upload_anh_hero_mobile", side_effect=ValueError("File quá lớn")):
            r = a.post("/admin/anh-trang-chu/", data={"file_anh_mobile": (io.BytesIO(b"y"), "mb.jpg"), "do_phu": "80"},
                       content_type="multipart/form-data", follow_redirects=True)
        h = r.get_data(as_text=True)
        self.assertIn("File quá lớn", h); self.assertNotIn("Đã lưu ảnh nền trang chủ", h)
        self.assertEqual(self.q(lambda: (CaiDat.lay(H.K_ANH), CaiDat.lay(H.K_ANH_MOBILE) or "")), (PC, ""))

    def test_anonymous_cannot_open_hero_admin(self):
        r = self.client().get("/admin/anh-trang-chu/")
        self.assertIn(r.status_code, (301, 302, 303, 401, 403))


if __name__ == "__main__":
    unittest.main()
