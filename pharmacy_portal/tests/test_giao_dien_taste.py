"""Giao diện công khai kiểu 'taste' (trang chủ, danh mục thuốc, danh sách thuốc, chi tiết thuốc, về chúng tôi, khung chung).
Kiểm tra cấu trúc HTML (giữ nội dung SEO, điều hướng, mục có id) và vài luật thiết kế quan trọng trong CSS."""
import os
import re
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from tests.test_phan_hoi import Co                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _doc(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class TrangCongKhai(Co):
    def trang(self, url):
        r = self.client().get(url)
        self.assertEqual(r.status_code, 200, url)
        return r.get_data(as_text=True)

    def test_home_has_hero_lookup_rows_statement_and_keeps_seo_text(self):
        h = self.trang("/")
        self.assertIn('class="tk-hero" data-enter', h)
        for dong in ("Tra cứu dược", "BVĐK Tâm Đức", "Cầu Quan"):
            self.assertIn(">" + dong + "<", h)                          # tiêu đề ngắt dòng cố định, mỗi dòng một khối
        self.assertIn("Cổng tra cứu thuốc Khoa Dược Bệnh viện Đa khoa Tâm Đức Cầu Quan", h)   # chữ SEO vẫn nằm trong HTML
        for ep in ("/danh-muc-thuoc/", "/nha-thuoc-bv/", "/tra-cuu-thuoc-tiem-truyen/", "/tra-cuu-tuong-hop-tuong-ky/", "/tra-cuu-tuong-tac-thuoc/", "/tra-cuu-thong-tin-thuoc/", "/thong-tin-cho-benh-nhan/", "/bai-viet/"):
            self.assertIn('href="%s"' % ep, h)
        self.assertIn('data-moment="word-highlight"', h)                 # khoảnh khắc duy nhất của trang
        self.assertIn('data-goi-y="all"', h)                             # ô tìm kiếm vẫn có gợi ý

    def test_shell_nav_footer_and_assets(self):
        h = self.trang("/")
        self.assertIn('class="tk-nav"', h); self.assertIn('class="tk-foot"', h)
        self.assertIn("css/taste.css", h); self.assertIn("css/taste-fonts.css", h); self.assertIn("js/taste.js", h)
        self.assertNotIn("fonts.googleapis.com", h)                      # phông tự lưu, không gọi Google
        self.assertNotIn('class="tabbar"', h)                            # chỉ còn màn hình menu trên điện thoại
        self.assertIn('class="skip-link"', h)
        self.assertEqual(len(re.findall(r'<div class="tk-wrap tk-panel__grid">(.*?)</div>\s*</div>', h, re.S)), 1)
        self.assertGreaterEqual(h.count('<a href="/'), 7)

    def test_current_page_is_marked_in_nav(self):
        h = self.trang("/ve-chung-toi")
        self.assertRegex(h, r'<a class="tk-nav__word" href="/ve-chung-toi" aria-current="page">Giới thiệu</a>')
        d = self.trang("/danh-muc-thuoc/")
        self.assertIn("data-here", d)                                    # từ "Tra cứu" được gạch chân khi đang ở mục tra cứu

    def test_group_list_and_drug_list_and_detail(self):
        from app import db
        from app.models.models import NhomThuoc, DanhMucThuoc

        def tao():
            g = NhomThuoc(ten_nhom="Kháng sinh", loai="danh_muc_thuoc", thu_tu=1)
            db.session.add(g); db.session.flush()
            t = DanhMucThuoc(ten_biet_duoc="AUGMENTIN", nhom_thuoc_id=g.id, chi_dinh="<p>Nhiễm khuẩn</p>", chong_chi_dinh="<p>Quá mẫn</p>")
            db.session.add(t); db.session.commit()
            return g.id, t.id
        gid, tid = self.q(tao)
        idx = self.trang("/danh-muc-thuoc/")
        self.assertIn("Danh mục thuốc theo nhóm dược lý", idx); self.assertIn('class="tk-row"', idx); self.assertIn("Kháng sinh", idx)
        ds = self.trang("/danh-muc-thuoc/nhom/%d" % gid)
        self.assertIn('class="tk-grid"', ds); self.assertIn("AUGMENTIN", ds)
        ct = self.trang("/danh-muc-thuoc/thuoc/%d" % tid)
        for muc in ("thanh-phan", "chi-dinh", "lieu-dung", "chong-chi-dinh"):
            self.assertRegex(ct, r'<section class="tk-fact[^"]*" id="%s"' % muc)
        self.assertIn('id="chong-chi-dinh"', ct)
        self.assertRegex(ct, r'class="tk-fact tk-section--dark" id="chong-chi-dinh"')   # chống chỉ định: nền tối, nổi bật bằng độ tương phản
        self.assertIn('href="#chong-chi-dinh"', ct)                                     # nút nhảy nhanh
        self.assertIn("Quá mẫn", ct)

    def test_about_page_renders_contact_rows(self):
        def luu():
            from app import db
            from app.models.models import CaiDat
            CaiDat.dat("vct_gioi_thieu", "Khoa Dược cung ứng thuốc."); CaiDat.dat("vct_dien_thoai", "0961 256 092"); db.session.commit()
        self.q(luu)
        h = self.trang("/ve-chung-toi")
        self.assertIn('data-moment="word-highlight"', h); self.assertIn('href="tel:0961256092"', h)


class LuatThietKe(unittest.TestCase):
    def setUp(self):
        self.css = _doc("app/static/css/taste.css")

    def test_motion_respects_reduced_motion_and_cards_lift_only_on_fine_pointers(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        self.assertRegex(self.css, r"@media \(hover: hover\) and \(pointer: fine\) \{ \.tk-card:hover \{ transform: translateY\(-2px\)")

    def test_no_glass_no_uppercase_labels_no_hard_shadows(self):
        self.assertNotIn("backdrop-filter", self.css)
        self.assertNotIn("text-transform: uppercase", self.css)          # nhãn viết thường, không in hoa giãn chữ
        for m in re.finditer(r"box-shadow: 0 \d+px (\d+)px rgba\(29, 37, 48, \.(\d+)\)", self.css):
            self.assertLessEqual(int(m.group(2)), 10)                    # bóng chỉ nhẹ (≤ 10%)

    def test_buttons_are_44px_and_single_radius_scale(self):
        self.assertRegex(self.css, r"\.tk-btn \{[^}]*height: 44px")
        self.assertIn("--r-lg: 20px; --r-md: 12px; --r-sm: 8px", self.css)

    def test_fonts_are_self_hosted_with_vietnamese_subset(self):
        f = _doc("app/static/css/taste-fonts.css")
        self.assertIn("vietnamese", f)
        for ten in re.findall(r"url\(\.\./fonts/([^)]+)\)", f):
            self.assertTrue(os.path.exists(os.path.join(ROOT, "app/static/fonts", ten)), ten)

    def test_word_highlight_is_scroll_linked_only_inside_its_section_and_skips_reduced_motion(self):
        js = _doc("app/static/js/taste.js")
        self.assertIn("prefers-reduced-motion: reduce", js)
        self.assertIn('[data-moment="word-highlight"]', js)


if __name__ == "__main__":
    unittest.main()
