"""Hỏi đáp công khai (duyệt trước) + chat riêng (vào bằng SĐT, không mã bí mật) + thông báo cho admin."""
import os
import re
import tempfile
import time
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app import create_app, db                                          # noqa: E402
from app.models.models import (BaiViet, ChatLanThu, DanhMucThuoc, KhachHang, NguoiDung, NhaThuocBV,   # noqa: E402
                               ThongBao, ThongTinBenhNhan, Thuoc, TinNhanRieng, YKien)
from app.utils import phan_hoi as PH                                    # noqa: E402
from config import Config                                               # noqa: E402

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
UA2 = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
PW = "mat-khau-123456"


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


class Co(unittest.TestCase):
    csrf = False

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # TEST_DATABASE_URL (PostgreSQL riêng cho test, bảng bị XOÁ SẠCH mỗi test) → chạy đúng loại DB của môi trường thật
        uri = os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{self.tmp}/t.db"
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": uri, "SQLALCHEMY_ENGINE_OPTIONS": {}, "WTF_CSRF_ENABLED": self.csrf})
        self.app = create_app(cfg)
        with self.app.app_context():
            if os.environ.get("TEST_DATABASE_URL"):
                db.drop_all()
            db.create_all()
            for t in ("admin1", "admin2"):
                u = NguoiDung(ten_dang_nhap=t, ho_ten=t.upper(), vai_tro="quan_tri"); u.set_password(PW); db.session.add(u)
            off = NguoiDung(ten_dang_nhap="nghi", vai_tro="duoc_si", dang_hoat_dong=False); off.set_password(PW); db.session.add(off)
            self.ids = {}
            for ten, obj in (("dmt", DanhMucThuoc(ten_biet_duoc="LIDOCAIN")), ("ntbv", NhaThuocBV(ten_biet_duoc="SPRAY")),
                             ("tt", Thuoc(ten_thuoc="Paracetamol")),
                             ("bv", BaiViet(tieu_de="Bài đã đăng", slug="bai-da-dang", trang_thai="da_xuat_ban")),
                             ("bv_nhap", BaiViet(tieu_de="Bài nháp", slug="bai-nhap", trang_thai="nhap")),
                             ("ttbn", ThongTinBenhNhan(tieu_de="Dùng thuốc tại nhà", noi_dung="x"))):
                db.session.add(obj); db.session.flush(); self.ids[ten] = obj.id
            db.session.commit()

    def client(self, ua=UA, ip="27.64.1.1"):
        c = self.app.test_client()
        c.environ_base["HTTP_USER_AGENT"] = ua
        c.environ_base["REMOTE_ADDR"] = ip
        return c

    def admin(self, ten="admin1", ua=UA):
        c = self.client(ua)
        r = c.post("/admin/dang-nhap", data={"ten_dang_nhap": ten, "mat_khau": PW})
        self.assertIn(r.status_code, (302, 303), r.data[:200])
        return c

    def q(self, fn):
        with self.app.app_context():
            return fn()


class HoiDapCongKhai(Co):
    def gui(self, c, **kw):
        d = dict(loai="dmt", id=self.ids["dmt"], ten="Nguyễn Văn A", sdt="0912345678", noi_dung="Thuốc này dùng thế nào cho trẻ nhỏ?",
                 website="", thoi_gian_dien=10)
        d.update(kw)
        return c.post("/api/hoi-dap/", json=d)

    def danh_sach(self, c, loai="dmt", key="dmt"):
        return c.get(f"/api/hoi-dap/?loai={loai}&id={self.ids[key]}").get_json()

    # ── giao diện ──
    def test_five_detail_pages_have_the_qa_block(self):
        c = self.client()
        paths = {"dmt": f"/danh-muc-thuoc/thuoc/{self.ids['dmt']}", "ntbv": f"/nha-thuoc-bv/thuoc/{self.ids['ntbv']}",
                 "tt": f"/tra-cuu-thong-tin-thuoc/{self.ids['tt']}", "bv": "/bai-viet/bai-da-dang",
                 "ttbn": f"/thong-tin-cho-benh-nhan/{self.ids['ttbn']}"}
        for loai, p in paths.items():
            r = c.get(p)
            self.assertEqual(r.status_code, 200, p)
            h = r.get_data(as_text=True)
            self.assertIn('id="hoi-dap"', h, p); self.assertIn(f'data-loai="{loai}"', h, p)
            self.assertIn("/ho-tro", h, p); self.assertIn("js/hoi_dap.js", h, p)

    def test_report_error_bar_on_the_three_lookup_pages(self):
        c = self.client()
        for p in ("/tra-cuu-tuong-tac-thuoc/", "/tra-cuu-thuoc-tiem-truyen/", "/tra-cuu-tuong-hop-tuong-ky/"):
            r = c.get(p)
            if r.status_code == 308 or r.status_code == 301:
                r = c.get(r.headers["Location"])
            h = r.get_data(as_text=True)
            self.assertEqual(r.status_code, 200, p)
            self.assertIn("Báo lỗi thông tin", h, p); self.assertIn("loai=bao_loi", h, p)

    # ── gửi + duyệt ──
    def test_new_comment_is_pending_and_hidden_until_approved(self):
        c = self.client()
        r = self.gui(c)
        self.assertEqual(r.status_code, 200); self.assertTrue(r.get_json()["ok"])
        self.assertEqual(self.danh_sach(c)["tong"], 0)                                    # chưa duyệt → không hiện
        with self.app.app_context():
            yk = YKien.query.one()
            self.assertEqual((yk.trang_thai, yk.so_dien_thoai, yk.doi_tuong_ten), ("cho_duyet", "0912345678", "LIDOCAIN"))
            yid = yk.id
        a = self.admin()
        self.assertEqual(a.post(f"/admin/y-kien/{yid}/duyet").status_code, 302)
        d = self.danh_sach(c)
        self.assertEqual(d["tong"], 1); self.assertEqual(d["muc"][0]["ten"], "Nguyễn Văn A")
        self.assertNotIn("0912345678", str(d)); self.assertNotIn("sdt", str(d))             # SĐT không bao giờ ra công khai

    def test_admin_public_reply_approves_and_shows_under_the_comment(self):
        c = self.client(); self.gui(c)
        yid = self.q(lambda: YKien.query.one().id)
        a = self.admin()
        a.post(f"/admin/y-kien/{yid}/tra-loi", data={"tra_loi": "Trẻ dưới 2 tuổi hỏi bác sĩ trước khi dùng."})
        m = self.danh_sach(c)["muc"][0]
        self.assertEqual(m["tra_loi"], "Trẻ dưới 2 tuổi hỏi bác sĩ trước khi dùng.")

    def test_reject_spam_and_delete_hide_or_remove(self):
        c = self.client(); a = self.admin()
        for hd, ung in (("tu_choi", "tu_choi"), ("spam", "spam")):
            self.q(lambda: [db.session.delete(y) for y in YKien.query.all()] and db.session.commit())
            self.client(ip="9.9.9.9")
            self.gui(self.client(ip=f"9.9.9.{len(hd)}"), noi_dung=f"Nội dung cần kiểm duyệt {hd}")
            yid = self.q(lambda: YKien.query.one().id)
            a.post(f"/admin/y-kien/{yid}/{hd}")
            self.assertEqual(self.q(lambda: db.session.get(YKien, yid).trang_thai), ung)
            self.assertEqual(self.danh_sach(c)["tong"], 0)
        a.post(f"/admin/y-kien/{yid}/xoa")
        self.assertEqual(self.q(lambda: YKien.query.count()), 0)

    def test_bulk_action(self):
        for i in range(3):
            self.gui(self.client(ip=f"8.8.8.{i}"), noi_dung=f"Câu hỏi số {i} về cách dùng thuốc")
        ids = self.q(lambda: [y.id for y in YKien.query.all()])
        self.admin().post("/admin/y-kien/hang-loat", data={"hanh_dong": "duyet", "ids": ids})
        self.assertEqual(self.danh_sach(self.client())["tong"], 3)

    # ── kiểm tra dữ liệu & chống spam ──
    def test_validation_errors(self):
        c = self.client()
        for kw, mong in ((dict(ten="A"), "Họ tên"), (dict(sdt="123"), "Số điện thoại"), (dict(noi_dung="hi"), "quá ngắn"),
                         (dict(noi_dung="Mua thuốc tại www.thuoc-gia.com nhé"), "đường dẫn"),
                         (dict(noi_dung="x" * 1001), "quá dài"), (dict(thoi_gian_dien=1), "quá nhanh")):
            r = self.gui(c, **kw)
            self.assertEqual(r.status_code, 400, kw); self.assertIn(mong, r.get_json()["loi"], kw)
        self.assertEqual(self.q(lambda: YKien.query.count()), 0)

    def test_unknown_or_draft_target_rejected(self):
        c = self.client()
        self.assertEqual(self.gui(c, loai="xxx").status_code, 404)
        self.assertEqual(self.gui(c, id=99999).status_code, 404)
        self.assertEqual(c.post("/api/hoi-dap/", json=dict(loai="bv", id=self.ids["bv_nhap"], ten="An Bình", sdt="0912345678",
                                                           noi_dung="Bài này còn là bản nháp", website="", thoi_gian_dien=9)).status_code, 404)

    def test_honeypot_pretends_ok_but_saves_nothing(self):
        r = self.gui(self.client(), website="http://spam.example")
        self.assertTrue(r.get_json()["ok"]); self.assertEqual(self.q(lambda: YKien.query.count()), 0)

    def test_bots_are_rejected(self):
        c = self.client("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
        self.assertEqual(self.gui(c).status_code, 400)

    def test_rate_limit_and_duplicates(self):
        c = self.client()
        for i in range(3):
            self.assertEqual(self.gui(c, noi_dung=f"Câu hỏi khác nhau số {i} nè").status_code, 200)
        self.assertEqual(self.gui(c, noi_dung="Câu hỏi thứ tư bị chặn").status_code, 429)
        c2 = self.client(UA2, ip="5.5.5.5")
        self.assertEqual(self.gui(c2, noi_dung="Câu hỏi giống hệt nhau").status_code, 200)
        self.assertEqual(self.gui(c2, noi_dung="Câu hỏi giống hệt nhau").status_code, 409)

    def test_phone_limit_per_day_across_devices(self):
        for i in range(PH.GIOI_HAN_SDT_NGAY):
            self.assertEqual(self.gui(self.client(ip=f"7.7.7.{i}", ua=UA + str(i)), noi_dung=f"Hỏi lần thứ {i} về thuốc").status_code, 200)
        self.assertEqual(self.gui(self.client(ip="7.7.9.9", ua=UA + "z"), noi_dung="Lần vượt giới hạn").status_code, 429)

    def test_control_and_bidi_characters_are_stripped(self):
        c = self.client()
        self.gui(c, noi_dung="Thuốc\u202e này\x00 dùng\u200b sao?")
        self.assertEqual(self.q(lambda: YKien.query.one().noi_dung), "Thuốc này dùng sao?")

    def test_html_is_kept_as_plain_text_and_never_rendered_by_the_script(self):
        self.gui(self.client(), noi_dung="<script>alert(1)</script> hỏi về liều dùng")
        js = open(os.path.join(os.path.dirname(__file__), "..", "app", "static", "js", "hoi_dap.js"), encoding="utf-8").read()
        self.assertNotIn("innerHTML = m.", js); self.assertIn("textContent = text", js)

    def test_phone_normalisation(self):
        for tho, chuan in (("0912 345 678", "0912345678"), ("+84912345678", "0912345678"), ("84912345678", "0912345678"),
                           ("091-234-5678", "0912345678"), ("02373838939", "02373838939")):
            self.assertEqual(PH.chuan_hoa_sdt(tho), chuan, tho)
        for xau in ("", "12345", "0912abc678", "1912345678"):
            self.assertIsNone(PH.chuan_hoa_sdt(xau), xau)

    def test_internal_urls_only(self):
        for ok in ("/danh-muc-thuoc/thuoc/5", "/tra-cuu-tuong-tac-thuoc/?q=a&b=2"):
            self.assertEqual(PH.duong_dan_noi_bo(ok), ok)
        for xau in ("https://evil.example/x", "//evil.example", "javascript:alert(1)", "relative/path", "/a b"):
            self.assertIsNone(PH.duong_dan_noi_bo(xau), xau)


class HoiDapCoCsrf(Co):
    csrf = True

    def test_csrf_enforced_on_public_post(self):
        c = self.client()
        body = dict(loai="dmt", id=self.ids["dmt"], ten="Nguyễn Văn A", sdt="0912345678", noi_dung="Câu hỏi hợp lệ về thuốc", website="", thoi_gian_dien=9)
        self.assertEqual(c.post("/api/hoi-dap/", json=body).status_code, 400)                      # không có token → bị chặn
        h = c.get(f"/danh-muc-thuoc/thuoc/{self.ids['dmt']}").get_data(as_text=True)
        token = re.search(r'id="hoi-dap"[^>]*data-csrf="([^"]+)"', h).group(1)
        r = c.post("/api/hoi-dap/", json=body, headers={"X-CSRFToken": token})
        self.assertEqual(r.status_code, 200, r.data)


class ChatVaAdminCoCsrf(Co):
    """Cấu hình thật có bật CSRF: biểu mẫu / fetch của khách và của admin đều phải lấy được token và gửi thành công."""
    csrf = True

    def test_customer_chat_flow_with_csrf(self):
        c = self.client()
        h = c.get("/ho-tro").get_data(as_text=True)
        token = re.search(r'id="htApp" data-csrf="([^"]+)"', h).group(1)
        H = {"X-CSRFToken": token}
        self.assertEqual(c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="Trần Thị B", ma="123456")).status_code, 400)   # thiếu token
        self.assertEqual(c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="Trần Thị B", ma="123456"), headers=H).status_code, 200)
        self.assertEqual(c.post("/api/ho-tro/gui", json=dict(noi_dung="Tin nhắn có token", website=""), headers=H).status_code, 200)
        self.assertEqual(c.get("/api/ho-tro/tin-nhan").status_code, 200)

    def test_admin_actions_with_csrf(self):
        a = self.client()
        tok = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', a.get("/admin/dang-nhap").get_data(as_text=True)).group(1)
        self.assertIn(a.post("/admin/dang-nhap", data={"ten_dang_nhap": "admin1", "mat_khau": PW, "csrf_token": tok}).status_code, (302, 303))
        page = a.get("/admin/y-kien/").get_data(as_text=True)
        tok = re.search(r'<meta name="csrf-token" content="([^"]+)"', page).group(1)
        self.client().post("/api/hoi-dap/", json={}, headers={"X-CSRFToken": "x"})                 # (không dùng, chỉ để chắc app chạy)
        with self.app.app_context():
            db.session.add(YKien(doi_tuong_loai="dmt", doi_tuong_id=self.ids["dmt"], doi_tuong_ten="LIDOCAIN", ten="Lê C", so_dien_thoai="0988000111",
                                 noi_dung="Ý kiến chờ duyệt có token", trang_thai="cho_duyet")); db.session.commit()
        yid = self.q(lambda: YKien.query.one().id)
        self.assertEqual(a.post(f"/admin/y-kien/{yid}/duyet", data={}).status_code, 400)           # thiếu token → bị chặn
        self.assertEqual(a.post(f"/admin/y-kien/{yid}/duyet", data={"csrf_token": tok}).status_code, 302)
        self.assertEqual(a.post("/api/thong-bao/doc-tat-ca").status_code, 400)
        self.assertEqual(a.post("/api/thong-bao/doc-tat-ca", headers={"X-CSRFToken": tok}).status_code, 200)


class ChatRieng(Co):
    def vao(self, c, sdt="0912345678", ten="Trần Thị B", nd="Tôi cần hỏi về đơn thuốc", **kw):
        r = c.post("/api/ho-tro/dang-nhap", json=dict(sdt=sdt, ten=ten, website=""))
        if r.status_code != 200:
            return r, None
        g = c.post("/api/ho-tro/gui", json=dict(noi_dung=nd, loai=kw.get("loai", "ho_tro"), ngu_canh=kw.get("ngu_canh", ""),
                                                ngu_canh_url=kw.get("url", ""), website=""))
        return r, g

    def test_new_phone_registers_and_old_phone_returns_to_old_chat(self):
        c = self.client()
        r, g = self.vao(c)                                                      # SĐT mới → tự đăng ký
        self.assertTrue(r.get_json()["moi"]); self.assertTrue(g.get_json()["ok"])
        with self.app.app_context():
            k = KhachHang.query.one()
            self.assertEqual((k.so_dien_thoai, k.ten), ("0912345678", "Trần Thị B"))
        c2 = self.client(UA2, "6.6.6.6")                                        # cùng SĐT, thiết bị khác, KHÔNG nhập họ tên → vào lại cuộc trò chuyện cũ
        r2 = c2.post("/api/ho-tro/dang-nhap", json=dict(sdt="+84912345678"))
        self.assertTrue(r2.get_json()["ok"]); self.assertFalse(r2.get_json()["moi"]); self.assertEqual(r2.get_json()["ten"], "Trần Thị B")
        self.assertEqual(self.q(lambda: KhachHang.query.count()), 1)
        tin = c2.get("/api/ho-tro/tin-nhan?sau=0").get_json()["tin"]
        self.assertEqual([t["noi_dung"] for t in tin], ["Tôi cần hỏi về đơn thuốc"])

    def test_returning_customer_can_log_in_without_sending_a_message(self):
        self.vao(self.client())
        c = self.client(UA2, "6.6.6.6")
        self.assertTrue(c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678")).get_json()["ok"])
        self.assertEqual(len(c.get("/api/ho-tro/tin-nhan?sau=0").get_json()["tin"]), 1)      # chỉ có tin cũ, không tạo thêm tin

    def test_no_session_means_no_access(self):
        self.vao(self.client())
        c = self.client(UA2, "6.6.6.6")
        self.assertEqual(c.get("/api/ho-tro/tin-nhan").status_code, 401)
        self.assertEqual(c.post("/api/ho-tro/gui", json=dict(noi_dung="Thử gửi khi chưa nhập SĐT", website="")).status_code, 401)

    def test_no_secret_code_in_page_or_api(self):
        h = self.client().get("/ho-tro").get_data(as_text=True)
        self.assertNotIn("Mã bí mật", h); self.assertNotIn('name="ma"', h)
        r = self.client().post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="An Bình", ma="000000"))   # tham số cũ bị bỏ qua
        self.assertTrue(r.get_json()["ok"])

    def test_per_device_limits_against_phone_enumeration(self):
        c = self.client(UA2, "6.6.6.6")
        for i in range(5):                                                     # tối đa 5 SĐT MỚI / thiết bị / 24 giờ
            self.assertEqual(c.post("/api/ho-tro/dang-nhap", json=dict(sdt=f"09123456{i:02d}", ten="An Bình")).status_code, 200)
        r = c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345699", ten="An Bình"))
        self.assertEqual(r.status_code, 429); self.assertIn("quá nhiều", r.get_json()["loi"])
        c2 = self.client(UA, "7.7.7.7")                                         # dò số có sẵn: tối đa 30 lần / 15 phút / thiết bị
        for i in range(30):
            c2.post("/api/ho-tro/dang-nhap", json=dict(sdt=f"09123456{i % 5:02d}"))
        r = c2.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345600"))
        self.assertEqual(r.status_code, 429); self.assertIn("quá nhiều", r.get_json()["loi"])

    def test_phone_and_name_validation(self):
        c = self.client()
        r = c.post("/api/ho-tro/dang-nhap", json=dict(sdt="999", ten="An Bình"))
        self.assertEqual(r.status_code, 400); self.assertIn("Số điện thoại", r.get_json()["loi"])
        r = c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten=""))             # số mới mà thiếu họ tên
        self.assertEqual(r.status_code, 400); self.assertIn("chưa đăng ký", r.get_json()["loi"]); self.assertIn("Họ tên", r.get_json()["loi"])
        self.assertEqual(self.q(lambda: KhachHang.query.count()), 0)

    def test_customers_only_see_their_own_conversation(self):
        a, b = self.client(), self.client(UA2, "6.6.6.6")
        self.vao(a, sdt="0911111111", ten="Khách A", nd="Bí mật của A")
        self.vao(b, sdt="0922222222", ten="Khách B", nd="Chuyện của B")
        self.assertEqual([t["noi_dung"] for t in a.get("/api/ho-tro/tin-nhan").get_json()["tin"]], ["Bí mật của A"])
        self.assertEqual([t["noi_dung"] for t in b.get("/api/ho-tro/tin-nhan").get_json()["tin"]], ["Chuyện của B"])
        self.assertNotIn("Bí mật của A", b.get("/ho-tro").get_data(as_text=True))

    def test_tampered_or_foreign_cookie_is_not_a_login(self):
        c = self.client(); self.vao(c, sdt="0911111111")
        d = self.client(UA2, "6.6.6.6")
        d.set_cookie("pp_chat", "dung-gia-mao.abc.def")
        self.assertEqual(d.get("/api/ho-tro/tin-nhan").status_code, 401)

    def test_page_is_private(self):
        r = self.client().get("/ho-tro")
        self.assertEqual(r.status_code, 200)
        self.assertIn("noindex", r.headers["X-Robots-Tag"]); self.assertIn("no-store", r.headers["Cache-Control"])
        self.assertIn('content="noindex, nofollow"', r.get_data(as_text=True))
        robots = self.client().get("/robots.txt").get_data(as_text=True)
        self.assertIn("Disallow: /ho-tro", robots); self.assertIn("Disallow: /api/", robots)

    def test_error_report_context_is_kept_and_only_internal_links(self):
        c = self.client()
        self.vao(c, loai="bao_loi", ngu_canh="Báo lỗi: Tương tác thuốc", url="/tra-cuu-tuong-tac-thuoc/?q=a")
        self.vao(self.client(UA2, "6.6.6.6"), sdt="0933333333", loai="bao_loi", ngu_canh="x", url="https://evil.example/phish")
        with self.app.app_context():
            t1, t2 = TinNhanRieng.query.order_by(TinNhanRieng.id).all()
            self.assertEqual((t1.loai, t1.ngu_canh, t1.ngu_canh_url), ("bao_loi", "Báo lỗi: Tương tác thuốc", "/tra-cuu-tuong-tac-thuoc/?q=a"))
            self.assertIsNone(t2.ngu_canh_url)
        h = c.get("/ho-tro?loai=bao_loi&ngu_canh=Báo%20lỗi:%20ABC&url=/x/y").get_data(as_text=True)
        self.assertIn("Báo lỗi: ABC", h)

    def test_message_rate_limit(self):
        c = self.client(); self.vao(c)
        for i in range(7):
            self.assertEqual(c.post("/api/ho-tro/gui", json=dict(noi_dung=f"Tin nhắn số {i} nhé", website="")).status_code, 200)
        r = c.post("/api/ho-tro/gui", json=dict(noi_dung="Tin vượt giới hạn", website=""))
        self.assertEqual(r.status_code, 429)

    def test_logout_clears_the_device(self):
        c = self.client(); self.vao(c)
        c.post("/api/ho-tro/thoat")
        self.assertEqual(c.get("/api/ho-tro/tin-nhan").status_code, 401)


class QuanTriChat(Co):
    def khach(self, sdt="0912345678", ten="Trần Thị B", nd="Tôi cần hỏi về đơn thuốc"):
        c = self.client(UA2, "6.6.6.6")
        c.post("/api/ho-tro/dang-nhap", json=dict(sdt=sdt, ten=ten, ma="123456"))
        c.post("/api/ho-tro/gui", json=dict(noi_dung=nd, website=""))
        return c

    def kid(self):
        return self.q(lambda: KhachHang.query.one().id)

    def test_admin_sees_conversations_and_unread_counts(self):
        self.khach()
        a = self.admin()
        h = a.get("/admin/tin-nhan/").get_data(as_text=True)
        self.assertIn("Trần Thị B", h); self.assertIn("0912345678", h); self.assertIn("1 mới", h); self.assertIn("Chờ trả lời", h)

    def test_opening_marks_read_and_reply_reaches_the_customer(self):
        kc = self.khach(); a = self.admin()
        kid = self.kid()
        h = a.get(f"/admin/tin-nhan/{kid}").get_data(as_text=True)
        self.assertIn("Tôi cần hỏi về đơn thuốc", h)
        self.assertEqual(self.q(lambda: TinNhanRieng.query.filter_by(da_doc_admin=False).count()), 0)
        r = a.post(f"/admin/tin-nhan/{kid}/gui", json={"noi_dung": "Chào bạn, Khoa Dược xin trả lời…"})
        self.assertTrue(r.get_json()["ok"])
        tin = kc.get("/api/ho-tro/tin-nhan?sau=0").get_json()["tin"]
        self.assertEqual([t["tu"] for t in tin], ["khach", "admin"])
        self.assertEqual(tin[1]["ten"], "Khoa Dược")                                              # khách thấy "Khoa Dược", không lộ tên nhân viên
        self.assertEqual(a.get(f"/admin/tin-nhan/{kid}/tin-nhan?sau=0").get_json()["tin"][1]["ten"], "ADMIN1")   # admin thấy ai đã trả lời
        self.assertEqual(self.q(lambda: TinNhanRieng.query.filter_by(tu="admin", da_doc_khach=False).count()), 0)   # khách đã đọc

    def test_polling_returns_only_new_messages_from_the_customer(self):
        kc = self.khach(); a = self.admin(); kid = self.kid()
        ds = a.get(f"/admin/tin-nhan/{kid}/tin-nhan?sau=0").get_json()["tin"]
        self.assertEqual(len(ds), 1)
        kc.post("/api/ho-tro/gui", json=dict(noi_dung="Tôi nhắn thêm một tin nữa", website=""))
        ds2 = a.get(f"/admin/tin-nhan/{kid}/tin-nhan?sau={ds[-1]['id']}").get_json()["tin"]
        self.assertEqual([t["noi_dung"] for t in ds2], ["Tôi nhắn thêm một tin nữa"])

    def test_block_and_delete(self):
        kc = self.khach(); a = self.admin(); kid = self.kid()
        a.post(f"/admin/tin-nhan/{kid}/chan")
        self.assertEqual(kc.get("/api/ho-tro/tin-nhan").status_code, 401)                      # bị chặn: cookie cũ vô hiệu
        kn = self.client(UA, "3.3.3.3")                                                        # đổi thiết bị vẫn không vào được bằng SĐT đã bị chặn
        self.assertEqual(kn.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678")).status_code, 400)
        a.post(f"/admin/tin-nhan/{kid}/chan", data={"bo_chan": "1"})
        self.assertTrue(kn.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678")).get_json()["ok"])
        self.assertEqual(a.post(f"/admin/tin-nhan/{kid}/dat-lai-ma", data={"ma_moi": "654321"}).status_code, 404)   # đã bỏ chức năng đặt lại mã
        a.post(f"/admin/tin-nhan/{kid}/xoa")
        self.assertEqual(self.q(lambda: TinNhanRieng.query.count()), 0)
        self.assertEqual(self.q(lambda: KhachHang.query.count()), 0)

    def test_anonymous_cannot_reach_admin_chat_or_moderation(self):
        self.khach()
        c = self.client()
        for p in ("/admin/tin-nhan/", f"/admin/tin-nhan/{self.kid()}", "/admin/y-kien/", "/admin/thong-bao/"):
            r = c.get(p)
            self.assertIn(r.status_code, (301, 302, 401, 403), p)
            self.assertNotIn("Trần Thị B", r.get_data(as_text=True))
        self.assertIn(c.post(f"/admin/tin-nhan/{self.kid()}/gui", json={"noi_dung": "xin chào"}).status_code, (302, 401, 403))


class ThongBaoAdmin(Co):
    def comment(self, **kw):
        d = dict(loai="dmt", id=self.ids["dmt"], ten="Nguyễn Văn A", sdt="0912345678", noi_dung="Thuốc này có dùng cho phụ nữ mang thai?", website="", thoi_gian_dien=9)
        d.update(kw)
        return self.client().post("/api/hoi-dap/", json=d)

    def test_each_comment_notifies_every_active_admin_only(self):
        self.comment()
        with self.app.app_context():
            ten = {a.ten_dang_nhap: ThongBao.query.filter_by(nguoi_nhan_id=a.id).count() for a in NguoiDung.query.all()}
        self.assertEqual(ten, {"admin1": 1, "admin2": 1, "nghi": 0})                         # tài khoản đã tắt không nhận

    def test_bell_summary_requires_login_and_lists_items(self):
        self.comment()
        self.assertEqual(self.client().get("/api/thong-bao/tom-tat").status_code, 401)
        a = self.admin()
        d = a.get("/api/thong-bao/tom-tat").get_json()
        self.assertEqual(d["chua_doc"], 1)
        self.assertIn("Ý kiến mới: LIDOCAIN", d["muc"][0]["tieu_de"]); self.assertEqual(d["muc"][0]["loai"], "y_kien_moi")
        self.assertTrue(d["muc"][0]["url"].startswith("/admin/y-kien/"))

    def test_chat_messages_collapse_into_one_notification(self):
        c = self.client()
        c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="Trần Thị B", ma="123456"))
        for i in range(3):
            c.post("/api/ho-tro/gui", json=dict(noi_dung=f"Tin nhắn số {i} gửi Khoa Dược", website=""))
        a = self.admin()
        d = a.get("/api/thong-bao/tom-tat").get_json()
        self.assertEqual((d["chua_doc"], len(d["muc"]), d["muc"][0]["so_luong"]), (1, 1, 3))   # 1 dòng "×3", không phải 3 dòng
        self.assertIn("Trần Thị B", d["muc"][0]["tieu_de"])

    def test_read_state_is_per_admin(self):
        self.comment()
        a1, a2 = self.admin("admin1"), self.admin("admin2")
        tid = a1.get("/api/thong-bao/tom-tat").get_json()["muc"][0]["id"]
        self.assertEqual(a1.post(f"/api/thong-bao/doc/{tid}").get_json()["chua_doc"], 0)
        self.assertEqual(a2.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 1)            # admin kia vẫn chưa đọc
        self.assertEqual(a1.get(f"/admin/thong-bao/mo/{tid}").status_code, 302)
        tid2 = a2.get("/api/thong-bao/tom-tat").get_json()["muc"][0]["id"]
        self.assertEqual(a1.get(f"/admin/thong-bao/mo/{tid2}").status_code, 404)                # không đọc được thông báo của người khác

    def test_open_notification_marks_read_and_redirects_internally(self):
        self.comment()
        a = self.admin(); tid = a.get("/api/thong-bao/tom-tat").get_json()["muc"][0]["id"]
        r = a.get(f"/admin/thong-bao/mo/{tid}")
        self.assertEqual(r.status_code, 302); self.assertIn("/admin/y-kien/", r.headers["Location"])
        self.assertEqual(a.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 0)
        with self.app.app_context():                                                             # url độc hại không bao giờ được chuyển tới
            a1 = NguoiDung.query.filter_by(ten_dang_nhap="admin1").one()
            tb = ThongBao.query.filter_by(nguoi_nhan_id=a1.id).first()
            tb.url = "https://evil.example/x"; tb.da_doc = False; db.session.commit(); tid = tb.id
        r = a.get(f"/admin/thong-bao/mo/{tid}")
        self.assertNotIn("evil.example", r.headers["Location"])

    def test_mark_all_read(self):
        for i in range(3):
            self.comment(noi_dung=f"Câu hỏi số {i} cần Khoa Dược xem")
        a = self.admin()
        self.assertEqual(a.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 3)
        a.post("/api/thong-bao/doc-tat-ca")
        self.assertEqual(a.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 0)

    def test_handling_the_item_marks_notifications_read_for_everyone(self):
        self.comment()
        a1, a2 = self.admin("admin1"), self.admin("admin2")
        yid = self.q(lambda: YKien.query.one().id)
        a1.post(f"/admin/y-kien/{yid}/duyet")
        self.assertEqual(a2.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 0)           # đã có người duyệt → admin kia không cần xử lý nữa

    def test_replying_to_a_customer_clears_the_chat_notification_for_everyone(self):
        c = self.client()
        c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="Trần Thị B", ma="123456"))
        c.post("/api/ho-tro/gui", json=dict(noi_dung="Cần hỗ trợ gấp về thuốc", website=""))
        a1, a2 = self.admin("admin1"), self.admin("admin2")
        self.assertEqual(a2.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 1)
        kid = self.q(lambda: KhachHang.query.one().id)
        a1.post(f"/admin/tin-nhan/{kid}/gui", json={"noi_dung": "Khoa Dược đã nhận được, xin trả lời bạn…"})
        self.assertEqual(a2.get("/api/thong-bao/tom-tat").get_json()["chua_doc"], 0)

    def test_notifications_page_and_sidebar_badges_and_dashboard(self):
        self.comment()
        c = self.client(); c.post("/api/ho-tro/dang-nhap", json=dict(sdt="0912345678", ten="Trần Thị B", ma="123456"))
        c.post("/api/ho-tro/gui", json=dict(noi_dung="Cần hỗ trợ về thuốc", website=""))
        a = self.admin()
        h = a.get("/admin/").get_data(as_text=True)
        for s in ("Ý kiến chờ duyệt", "Tin nhắn chưa đọc", 'id="tbBell"', "Hỏi đáp &amp; bình luận", "Tin nhắn riêng", "js/thong_bao.js", 'nav-badge'):
            self.assertIn(s, h, s)
        p = a.get("/admin/thong-bao/").get_data(as_text=True)
        self.assertIn("Ý kiến mới: LIDOCAIN", p); self.assertIn("Trần Thị B", p)
        self.assertEqual(a.get("/admin/thong-bao/?chua_doc=1").status_code, 200)

    def test_bell_polling_does_not_extend_the_idle_session(self):
        a = self.admin()
        cu = time.time() - 10 * 60
        with a.session_transaction() as s:
            s["_last_active"] = cu
        a.get("/api/thong-bao/tom-tat")
        with a.session_transaction() as s:
            self.assertAlmostEqual(s["_last_active"], cu, delta=1)                              # hỏi chuông không gia hạn phiên
        a.get("/admin/y-kien/")                                                                  # thao tác thật thì làm mới
        with a.session_transaction() as s:
            self.assertGreater(s["_last_active"], time.time() - 30)

    def test_expired_session_gets_json_401_for_the_bell(self):
        a = self.admin()
        with a.session_transaction() as s:
            s["_last_active"] = time.time() - 16 * 60
        r = a.get("/api/thong-bao/tom-tat")
        self.assertEqual(r.status_code, 401)


class ModerationList(Co):
    def test_filters_and_pagination_and_links(self):
        c = self.client()
        for i in range(25):
            c.post("/api/hoi-dap/", json=dict(loai="dmt" if i % 2 else "ntbv", id=self.ids["dmt" if i % 2 else "ntbv"],
                   ten="Nguyễn Văn A", sdt=f"09123456{i:02d}", noi_dung=f"Câu hỏi số {i} về thuốc", website="", thoi_gian_dien=9))
        with self.app.app_context():                                                             # nạp thẳng để vượt giới hạn tốc độ
            for i in range(25):
                db.session.add(YKien(doi_tuong_loai="dmt", doi_tuong_id=self.ids["dmt"], doi_tuong_ten="LIDOCAIN", ten="Lê Thị C",
                                     so_dien_thoai=f"0988000{i:03d}", noi_dung=f"Ý kiến nạp sẵn số {i}", trang_thai="cho_duyet"))
            db.session.commit()
        a = self.admin()
        h = a.get("/admin/y-kien/?trang_thai=cho_duyet").get_data(as_text=True)
        self.assertIn("Trang 1 /", h); self.assertIn("/danh-muc-thuoc/thuoc/", h)                # có phân trang + link tới trang công khai
        self.assertIn("tel:", h)
        self.assertEqual(a.get("/admin/y-kien/?trang_thai=cho_duyet&trang=2").status_code, 200)
        self.assertIn("Ý kiến nạp sẵn", a.get("/admin/y-kien/?q=n%E1%BA%A1p+s%E1%BA%B5n").get_data(as_text=True))
        self.assertNotIn("Ý kiến nạp sẵn", a.get("/admin/y-kien/?trang_thai=da_duyet").get_data(as_text=True))

    def test_admin_actions_are_logged_in_the_audit_log(self):
        self.client().post("/api/hoi-dap/", json=dict(loai="dmt", id=self.ids["dmt"], ten="Nguyễn Văn A", sdt="0912345678",
                                                      noi_dung="Câu hỏi cần duyệt trong nhật ký", website="", thoi_gian_dien=9))
        yid = self.q(lambda: YKien.query.one().id)
        self.admin().post(f"/admin/y-kien/{yid}/duyet")
        from app.models.models import NhatKy
        with self.app.app_context():
            self.assertTrue(NhatKy.query.filter(NhatKy.doi_tuong == "Ý kiến hỏi đáp", NhatKy.hanh_dong == "duyet").count() >= 1)


if __name__ == "__main__":
    unittest.main()
