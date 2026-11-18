"""Điện thoại (≤ 700px, máy tính không đổi): trang chủ dạng thẻ sản phẩm 2 cột kiểu Shopee; Danh mục thuốc / Nhóm thuốc cũng là lưới 2 cột;
tất cả cùng MỘT bảng màu xanh thương hiệu (không còn màu riêng / màu xoay vòng cho từng thẻ)."""
import os
import re
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from tests.test_phan_hoi import Co                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _css():
    with open(os.path.join(ROOT, "app/static/css/style.css"), encoding="utf-8") as f:
        return f.read()


def _khoi_mobile():
    css = _css()
    a = css.index("TRANG CHỦ ĐIỆN THOẠI")
    return css[a:]


def _khoi_luoi_nhom_thuoc():
    """Khối CSS điện thoại của Danh mục thuốc / Nhóm thuốc (nằm cuối file, sau khối trang chủ)."""
    css = _css()
    a = css.index("ĐIỆN THOẠI (≤ 700px): DANH MỤC THUỐC / NHÓM THUỐC")
    k = css[a:]
    return k[k.index("@media (max-width: 700px)"):]


class TrangChuMobile(Co):
    def test_eight_function_cards_each_with_image_tile_title_desc_action_and_tag(self):
        h = self.client().get("/").get_data(as_text=True)
        cards = re.findall(r'<a class="category-card cat-\w+".*?</a>', h, re.S)
        self.assertEqual(len(cards), 8)
        for c in cards:
            for cls in ("cat-icon-wrap", "cat-tag", "<h3>", "<p>", "cat-arrow"):
                self.assertIn(cls, c)
            self.assertRegex(c, r'<div class="cat-icon-wrap">.*?<span class="cat-tag">[^<]+</span></div>')   # nhãn nằm trong ô "ảnh"

    def test_two_column_card_grid_only_on_phones(self):
        k = _khoi_mobile()
        self.assertIn("@media (max-width: 700px)", k)                      # cùng mốc với hero
        trong = k[k.index("@media (max-width: 700px)"):]
        self.assertRegex(trong, r"\.category-grid \{[^}]*grid-template-columns: 1fr 1fr")
        self.assertIn("aspect-ratio: 1 / 1", trong)                       # ô "ảnh sản phẩm" vuông
        self.assertIn("-webkit-line-clamp: 2", trong)                     # tên tối đa 2 dòng
        ngoai = k[:k.index("@media (max-width: 700px)")]
        self.assertIn(".cat-tag { display: none; }", ngoai)               # máy tính không hiện nhãn

    def test_cards_do_not_create_stacking_contexts_over_search_suggestions(self):
        trong = _khoi_mobile()
        for m in re.finditer(r"\.category-card[^{]*\{([^}]*)\}", trong):
            body = m.group(1)
            for v in re.findall(r"transform:\s*([^;}]+)", body):
                self.assertEqual(v.strip(), "none", m.group(0))             # chỉ được phép vô hiệu hoá transform, không được tạo mới
            self.assertNotIn("filter:", body); self.assertNotIn("z-index", body); self.assertNotIn("opacity:", body)

    def test_grid_sits_below_hero_without_overlapping_background_image(self):
        trong = _khoi_mobile()
        self.assertNotRegex(trong, r"\.category-grid \{[^}]*margin: -")                                 # không còn margin âm kéo lưới lên đè hero
        self.assertRegex(trong, r"\.category-grid-outer \{[^}]*padding: 18px 14px 32px")                # chừa khoảng trống giữa đáy hero và thẻ đầu
        css = _css()
        self.assertNotRegex(css, r"\.hero--anh \{ min-height: 0; padding-top: 56px; padding-bottom: 92px")  # hết chừa đáy 92px cho phần đè

    def test_all_cards_share_one_harmonised_palette(self):
        trong = _khoi_mobile()
        # không còn màu riêng cho từng thẻ (trước đây 8 thẻ = 8 màu: xanh / lục / chàm / tím / cam / ngọc / hồng / vàng)
        self.assertNotRegex(trong, r"\.category-card\.cat-\w+\s*\{ --cat-bg1:")
        # cả 8 thẻ dùng chung một bộ màu: nền ô "ảnh" xanh nhạt + chữ/nhãn xanh navy thương hiệu
        self.assertRegex(trong, r"\.category-card \{[^}]*--cat-bg1: var\(--m-tile-1\);\s*--cat-bg2: var\(--m-tile-2\);\s*--cat-ink: var\(--navy-600\)")
        # nền khu vực thẻ cùng màu nền các trang khác (không phải xám trung tính #f3f4f6)
        self.assertRegex(trong, r"\.category-grid-outer \{ background: var\(--paper-0\)")


class NhomThuocMobile(unittest.TestCase):
    """Danh mục thuốc (danh sách nhóm) và Nhóm thuốc (danh sách thuốc) trên điện thoại: lưới 2 cột, một bảng màu."""

    def test_group_and_drug_grids_are_two_columns_on_phones_only(self):
        trong = _khoi_luoi_nhom_thuoc()
        self.assertRegex(trong, r"\.nhom-grid, \.drug-grid \{[^}]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)")  # minmax(0,…) để tên dài không làm tràn cột
        # máy tính giữ nguyên lưới tự co giãn
        css = _css()
        self.assertRegex(css, r"\.nhom-grid \{\s*display: grid;\s*grid-template-columns: repeat\(auto-fill, minmax\(250px, 1fr\)\)")
        self.assertRegex(css, r"\.drug-grid \{\s*display: grid;\s*grid-template-columns: repeat\(auto-fill, minmax\(240px, 1fr\)\)")

    def test_group_cards_use_one_accent_not_rotating_colours(self):
        trong = _khoi_luoi_nhom_thuoc()
        # .nhom-grid .nhom-card (2 class) thắng .nhom-card-accent-0..3 (1 class: xanh / vàng / cam…) → mọi nhóm cùng một màu
        self.assertRegex(trong, r"\.nhom-grid \.nhom-card \{ --accent-color: var\(--navy-600\); --accent-bg: var\(--sage-100\);")

    def test_drug_cards_are_product_tiles_with_ratio_image_on_top(self):
        trong = _khoi_luoi_nhom_thuoc()
        self.assertRegex(trong, r"\.drug-grid \.drug-card \{ flex-direction: column;")
        self.assertIn("aspect-ratio: 4 / 5", trong)                          # cùng tỉ lệ 4:5 của ảnh thuốc đang dùng (80×100)
        self.assertIn("-webkit-line-clamp: 2", trong)                        # tên thuốc / hoạt chất tối đa 2 dòng
        # ô chữ cái khi chưa có ảnh: ghi đè màu inline (xanh dương / xanh lá) ở trang tìm kiếm tổng hợp
        self.assertRegex(trong, r"\.drug-card-thumb-fallback \{[^}]*color: var\(--navy-600\) !important;[^}]*background: radial-gradient\([^}]*!important")

    def test_no_sticky_hover_motion_on_touch(self):
        trong = _khoi_luoi_nhom_thuoc()
        for sel in (".nhom-card:hover", ".drug-card:hover"):
            self.assertRegex(trong, re.escape(sel) + r" \{ transform: none;")

    def test_footer_strip_follows_the_blue_palette_on_phones(self):
        trong = _khoi_luoi_nhom_thuoc()
        self.assertRegex(trong, r"\.site-footer::before \{ background: linear-gradient\(90deg, var\(--navy-600\), var\(--sky-400\)\)")


class AnhThuocChiTietMobile(unittest.TestCase):
    """Trang chi tiết thuốc trên điện thoại: ảnh thuốc là khung vuông rộng hết khung tiêu đề (trước đây chỉ 96px)."""

    def _khoi(self):
        css = _css()
        a = css.index("ẢNH THUỐC Ở TRANG CHI TIẾT to hơn")
        k = css[a:]
        return k[k.index("@media (max-width: 640px)"):]

    def test_image_box_fills_hero_width_on_phones(self):
        k = self._khoi()
        self.assertRegex(k, r"\.drug-hero-media \{[^}]*width: 100%;[^}]*max-width: 420px;[^}]*aspect-ratio: 1 / 1")
        self.assertNotRegex(k, r"\.drug-hero-media \{[^}]*width: (96|110|150)px")      # không còn khung nhỏ cố định

    def test_image_is_scaled_up_but_never_cropped(self):
        k = self._khoi()
        self.assertRegex(k, r"\.drug-hero-media img \{[^}]*width: 100%; height: 100%;[^}]*object-fit: contain")
        self.assertNotIn("object-fit: cover", k)                                        # ảnh hộp thuốc không được bị cắt chữ

    def test_desktop_size_is_unchanged(self):
        css = _css()
        self.assertRegex(css, r"\.drug-hero-media \{\s*flex-shrink: 0;\s*width: 150px;\s*height: 150px;")


class ChiTietThuocRender(Co):
    def test_detail_page_still_has_clickable_hero_image(self):
        c = self.client()
        h = c.get("/danh-muc-thuoc/thuoc/%d" % self.ids["dmt"]).get_data(as_text=True)
        self.assertIn('class="drug-hero-media"', h)                                     # khung ảnh vẫn nằm trong khối tiêu đề


if __name__ == "__main__":
    unittest.main()
