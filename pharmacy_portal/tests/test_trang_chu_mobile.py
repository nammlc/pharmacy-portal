"""Trang chủ điện thoại: các ô chức năng dạng thẻ sản phẩm 2 cột kiểu Shopee (chỉ ≤ 700px, máy tính không đổi)."""
import os
import re
import unittest

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from tests.test_phan_hoi import Co                                      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _khoi_mobile():
    css = open(os.path.join(ROOT, "app/static/css/style.css"), encoding="utf-8").read()
    a = css.index("TRANG CHỦ ĐIỆN THOẠI")
    return css[a:]


class TrangChuMobile(Co):
    def test_eight_function_cards_each_with_image_tile_title_desc_action_and_tag(self):
        h = self.client().get("/trang-chu").get_data(as_text=True)
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

    def test_each_card_has_its_own_colours(self):
        trong = _khoi_mobile()
        for k in ("dmt", "ntbv", "tt", "thtk", "ttt", "ttth", "ttbn", "bv"):
            self.assertRegex(trong, r"\.category-card\.cat-%s\s*\{ --cat-bg1:" % k)


if __name__ == "__main__":
    unittest.main()
