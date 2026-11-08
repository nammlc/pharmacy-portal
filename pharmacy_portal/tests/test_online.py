"""Đếm người đang online: ghi tín hiệu, đếm admin / khách, không gia hạn phiên, giao diện ô thống kê."""
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app import create_app, db                     # noqa: E402
from app.models.models import DangOnline, NguoiDung  # noqa: E402
from config import Config                          # noqa: E402

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
UA_PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
UA_BOT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SERVER_NAME = None


class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.tmp}/t.db",
                                    "SQLALCHEMY_ENGINE_OPTIONS": {}})
        self.app = create_app(cfg)
        with self.app.app_context():
            db.create_all()
            u = NguoiDung(ten_dang_nhap="admin1", ho_ten="Lê Công Nam", vai_tro="quan_tri")
            u.set_password("mat-khau-123456")
            u2 = NguoiDung(ten_dang_nhap="duocsi2", vai_tro="duoc_si")
            u2.set_password("mat-khau-123456")
            db.session.add_all([u, u2]); db.session.commit()
        from app.utils import online
        online._GHI_LAN_CUOI.clear()
        self.online = online

    def client(self, ua=UA_PC, **kw):
        c = self.app.test_client()
        c.environ_base["HTTP_USER_AGENT"] = ua
        c.environ_base["REMOTE_ADDR"] = kw.get("ip", "27.64.1.1")
        return c

    def login(self, c, user="admin1"):
        r = c.post("/admin/dang-nhap", data={"ten_dang_nhap": user, "mat_khau": "mat-khau-123456"})
        self.assertIn(r.status_code, (302, 303), r.data[:300])

    def rows(self):
        with self.app.app_context():
            return [(r.khoa, r.loai, r.ten) for r in DangOnline.query.order_by(DangOnline.khoa).all()]

    def dem(self):
        with self.app.app_context():
            return self.online.dem()

    # ---- khách ----
    def test_visitor_ping_is_counted_as_user(self):
        r = self.client().post("/api/online/ping?khu=cong_khai")
        self.assertEqual(r.status_code, 204)
        d = self.dem()
        self.assertEqual((d["admin"], d["khach"]), (0, 1))

    def test_visitors_are_counted_per_device_not_per_request(self):
        a, b = self.client(UA_PC, ip="27.64.1.1"), self.client(UA_PHONE, ip="27.64.1.1")
        for _ in range(3):
            a.post("/api/online/ping"); self.online._GHI_LAN_CUOI.clear()
        b.post("/api/online/ping")
        self.assertEqual(self.dem()["khach"], 2)

    def test_visitor_raw_ip_is_never_stored(self):
        self.client(ip="203.0.113.77").post("/api/online/ping")
        for khoa, _, ten in self.rows():
            self.assertNotIn("203.0.113.77", khoa)
            self.assertTrue(khoa.startswith("k:"))

    def test_bots_are_not_counted(self):
        self.assertEqual(self.client(UA_BOT).post("/api/online/ping").status_code, 204)
        self.assertEqual(self.rows(), [])

    def test_consent_cookie_id_is_used_as_key(self):
        c = self.client()
        c.set_cookie("pp_dongy", "1"); c.set_cookie("pp_vid", "a" * 32)
        c.post("/api/online/ping")
        self.assertEqual([k for k, *_ in self.rows()], ["v:" + "a" * 32])

    def test_old_signals_drop_out_of_the_window(self):
        self.client().post("/api/online/ping")
        with self.app.app_context():
            DangOnline.query.update({"lan_cuoi": datetime.utcnow() - timedelta(seconds=300)}); db.session.commit()
        self.assertEqual(self.dem()["khach"], 0)

    # ---- gần thời gian thực: báo rời trang ----
    def lan_cuoi(self, khoa):
        with self.app.app_context():
            return DangOnline.query.get(khoa).lan_cuoi

    def test_leaving_the_page_drops_the_count_quickly(self):
        c = self.client(); c.post("/api/online/ping")
        khoa = self.rows()[0][0]
        self.assertEqual(self.dem()["khach"], 1)
        cua_so = self.app.config["ONLINE_CUA_SO_GIAY"]
        self.assertEqual(c.post("/api/online/roi").status_code, 204)
        con_lai = cua_so - (datetime.utcnow() - self.lan_cuoi(khoa)).total_seconds()      # còn được tính bao lâu nữa
        self.assertTrue(3 <= con_lai <= self.online.ROI_GIU_GIAY + 2, con_lai)             # ~6 giây thay vì cả phút
        self.assertEqual(self.dem()["khach"], 1)                                           # chưa tụt ngay (chống nháy khi đổi trang)
        with self.app.app_context():                                                       # hết 6 giây mà không có tín hiệu mới
            DangOnline.query.update({"lan_cuoi": datetime.utcnow() - timedelta(seconds=cua_so + 1)}); db.session.commit()
        self.assertEqual(self.dem()["khach"], 0)

    def test_next_page_signal_right_after_leaving_restores_the_count(self):
        c = self.client(); c.post("/api/online/ping")
        c.post("/api/online/roi")
        c.post("/api/online/ping")                                                         # trang kế tiếp báo lại ngay
        khoa = self.rows()[0][0]
        self.assertLess((datetime.utcnow() - self.lan_cuoi(khoa)).total_seconds(), 3)

    def test_leaving_unknown_visitor_and_bot_is_harmless(self):
        self.assertEqual(self.client().post("/api/online/roi").status_code, 204)
        self.assertEqual(self.client(UA_BOT).post("/api/online/roi").status_code, 204)
        self.assertEqual(self.rows(), [])

    def test_admin_leaving_and_expired_admin_tab(self):
        c = self.client(); self.login(c); c.post("/api/online/ping?khu=admin")
        c.post("/api/online/roi?khu=admin")
        self.assertEqual(self.dem()["admin"], 1)
        with c.session_transaction() as s:
            s["_last_active"] = time.time() - 16 * 60
        self.assertEqual(c.post("/api/online/roi?khu=admin").status_code, 204)           # hết phiên: không tính thành khách

    def test_default_window_is_short_for_near_realtime(self):
        self.assertEqual(self.app.config["ONLINE_CUA_SO_GIAY"], 60)

    # ---- admin ----
    def test_stats_requires_login(self):
        self.assertEqual(self.client().get("/api/online/thong-ke").status_code, 401)

    def test_admin_is_counted_once_per_account_with_name(self):
        c = self.client(); self.login(c)
        c.post("/api/online/ping?khu=admin"); self.online._GHI_LAN_CUOI.clear()
        c2 = self.client(UA_PHONE); self.login(c2)                          # cùng tài khoản, thiết bị khác
        c2.post("/api/online/ping?khu=admin")
        c3 = self.client(); self.login(c3, "duocsi2"); c3.post("/api/online/ping?khu=admin")
        self.client(UA_PHONE, ip="27.64.9.9").post("/api/online/ping")
        d = c.get("/api/online/thong-ke").get_json()
        self.assertEqual((d["admin"], d["khach"]), (2, 1))
        self.assertEqual(sorted(d["ten_admin"], key=str.lower), ["duocsi2", "Lê Công Nam"])

    def test_logged_in_admin_browsing_the_public_site_counts_as_a_user(self):
        """Đúng ca thực tế: admin mở website công khai bằng trình duyệt đã đăng nhập để xem thử → số "Người dùng" phải nhảy."""
        c = self.client(); self.login(c)
        c.post("/api/online/ping?khu=cong_khai")
        d = self.dem()
        self.assertEqual((d["admin"], d["khach"]), (0, 1))

    def test_admin_with_admin_tab_and_public_tab_is_one_admin_and_one_user(self):
        c = self.client(); self.login(c)
        c.post("/api/online/ping?khu=admin")                               # tab trang quản trị
        c.post("/api/online/ping?khu=cong_khai")                           # tab website công khai (cùng trình duyệt)
        d = c.get("/api/online/thong-ke").get_json()
        self.assertEqual((d["admin"], d["khach"]), (1, 1))

    def test_expired_admin_tab_is_not_counted_as_visitor(self):
        c = self.client(); self.login(c)
        with c.session_transaction() as s:
            s["_last_active"] = time.time() - 16 * 60                       # quá 15 phút không hoạt động
        r = c.post("/api/online/ping?khu=admin")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.rows(), [])

    def test_background_signals_do_not_extend_the_idle_session(self):
        c = self.client(); self.login(c)
        cu = time.time() - 10 * 60
        with c.session_transaction() as s:
            s["_last_active"] = cu
        c.post("/api/online/ping?khu=admin"); c.get("/api/online/thong-ke")
        with c.session_transaction() as s:
            self.assertAlmostEqual(s["_last_active"], cu, delta=1)          # không bị làm mới
        c.get("/admin/")                                                    # thao tác thật thì làm mới
        with c.session_transaction() as s:
            self.assertGreater(s["_last_active"], time.time() - 30)

    # ---- giao diện ----
    def test_admin_pages_have_the_widget_and_script(self):
        c = self.client(); self.login(c)
        h = c.get("/admin/").get_data(as_text=True)
        for chuoi in ('id="onlineBox"', 'id="onlineAdmin"', 'id="onlineKhach"', "Admin online", "Người dùng online",
                      'data-khu="admin"', "/api/online/ping", "/api/online/roi", "/api/online/thong-ke", "js/online.js"):
            self.assertIn(chuoi, h, chuoi)
        self.assertLess(h.index("admin-body"), h.index('id="onlineBox"'))   # ô nằm SAU nội dung → cuối trang trên mobile

    def test_public_pages_only_send_the_signal(self):
        h = self.client().get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn('data-khu="cong_khai"', h); self.assertIn("/api/online/roi", h); self.assertNotIn("onlineBox", h)

    def test_script_polls_fast_and_reports_leaving(self):
        js = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "js", "online.js"), encoding="utf-8").read()
        self.assertIn("STAT_MS = 5000", js); self.assertIn("PING_MS = 20000", js)
        self.assertIn("sendBeacon", js); self.assertIn('"pagehide"', js)

    def test_css_pins_box_on_desktop_and_puts_it_at_the_end_on_mobile(self):
        css = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css"), encoding="utf-8").read()
        box = css[css.index(".online-box {"):]
        self.assertIn("position: fixed; right: 12px; bottom: 12px", box.split("}")[0])
        mobile = css[css.index("@media (max-width: 800px) {\n  .online-box"):]
        self.assertIn("position: static", mobile.split("}")[0])

    def test_dashboard_grid_cannot_overflow_on_mobile(self):
        c = self.client(); self.login(c)
        h = c.get("/admin/").get_data(as_text=True)
        self.assertIn("repeat(2, minmax(0, 1fr))", h); self.assertIn("minmax(0, 1fr)", h.split("max-width: 800px")[1])
        self.assertIn(".dash-recent-block { min-width: 0; }", h)


class GiaoDienGon(unittest.TestCase):
    """Ô đếm gọn, không còn dòng chú thích; khoá cuộn trang không làm menu trái (sticky) trôi đi."""
    ROOT = os.path.join(os.path.dirname(__file__), "..", "app")

    def doc(self, *p):
        return open(os.path.join(self.ROOT, *p), encoding="utf-8").read()

    def test_widget_has_no_footnote_and_is_compact(self):
        html = self.doc("templates", "admin", "_online_widget.html")
        self.assertNotIn("online-note", html); self.assertNotIn("ước lượng", html); self.assertNotIn("xem thử", html)
        self.assertNotIn("online-note", self.doc("static", "css", "style.css"))
        self.assertNotIn("onlineNote", self.doc("static", "js", "online.js"))
        css = self.doc("static", "css", "style.css")
        box = css[css.index(".online-box {"):].split("}")[0]
        self.assertIn("border-radius: 999px", box); self.assertIn("max-width: min(260px", box)   # viên thuốc nhỏ, không phải thẻ to

    def test_scroll_lock_never_goes_on_body(self):
        """html có overflow-x: clip nên overflow:hidden đặt trên <body> sẽ làm sidebar sticky mất ghim (menu trái trôi)."""
        css = self.doc("static", "css", "style.css")
        self.assertIn("html { overflow-x: clip; }", css)
        self.assertIn("html.rich-modal-open { overflow: hidden; scrollbar-gutter: stable; }", css)
        self.assertNotIn("body.rich-modal-open", css)
        for f in (("static", "js", "main.js"), ("static", "js", "lightbox.js"), ("templates", "admin", "base.html")):
            t = self.doc(*f)
            self.assertNotIn("body.style.overflow", t, f)
            self.assertNotIn('body.classList.add("rich-modal-open")', t, f)
        self.assertIn('document.documentElement.classList.add("rich-modal-open")', self.doc("static", "js", "main.js"))


if __name__ == "__main__":
    unittest.main()
