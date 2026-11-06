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

    def test_logged_in_admin_on_public_pages_counts_as_admin_not_visitor(self):
        c = self.client(); self.login(c)
        c.post("/api/online/ping?khu=cong_khai")
        d = self.dem()
        self.assertEqual((d["admin"], d["khach"]), (1, 0))

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
                      'data-khu="admin"', "/api/online/ping", "/api/online/thong-ke", "js/online.js"):
            self.assertIn(chuoi, h, chuoi)
        self.assertLess(h.index("admin-body"), h.index('id="onlineBox"'))   # ô nằm SAU nội dung → cuối trang trên mobile

    def test_public_pages_only_send_the_signal(self):
        h = self.client().get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn('data-khu="cong_khai"', h); self.assertNotIn("onlineBox", h)

    def test_css_pins_box_on_desktop_and_puts_it_at_the_end_on_mobile(self):
        css = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "css", "style.css"), encoding="utf-8").read()
        box = css[css.index(".online-box {"):]
        self.assertIn("position: fixed; right: 18px; bottom: 18px", box.split("}")[0])
        mobile = css[css.index("@media (max-width: 800px) {\n  .online-box"):]
        self.assertIn("position: static", mobile.split("}")[0])

    def test_dashboard_grid_cannot_overflow_on_mobile(self):
        c = self.client(); self.login(c)
        h = c.get("/admin/").get_data(as_text=True)
        self.assertIn("repeat(2, minmax(0, 1fr))", h); self.assertIn("minmax(0, 1fr)", h.split("max-width: 800px")[1])
        self.assertIn(".dash-recent-block { min-width: 0; }", h)


if __name__ == "__main__":
    unittest.main()
