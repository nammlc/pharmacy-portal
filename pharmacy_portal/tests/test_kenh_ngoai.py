"""Báo ra ngoài (Telegram + email) khi có ý kiến / tin nhắn mới: đúng nội dung, riêng tư, giới hạn tần suất, không làm hỏng yêu cầu."""
import os
import unittest
from unittest import mock

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app import db                                                  # noqa: E402
from app.models.models import KhachHang, NguoiDung, YKien           # noqa: E402
from app.utils import kenh_ngoai as KN                              # noqa: E402
from tests import test_phan_hoi as TP                               # noqa: E402

COMMENT = dict(ten="Nguyễn Văn A", sdt="0912345678", noi_dung="Thuốc này dùng thế nào cho trẻ nhỏ?", website="", thoi_gian_dien=10)


class Co(TP.Co):
    def setUp(self):
        super().setUp()
        KN._TG_LAN_CUOI.clear(); KN._EMAIL_DA_GUI.clear(); KN._EMAIL_BI_GOM.clear()
        self.app.config.update(APP_BASE_URL="https://tracuuduoc.example", TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
        with self.app.app_context():
            for ten, email, on in (("admin1", "a1@bv.vn", True), ("admin2", "A2@bv.vn", True), ("nghi", "off@bv.vn", False)):
                u = NguoiDung.query.filter_by(ten_dang_nhap=ten).one(); u.email = email; u.dang_hoat_dong = on
            db.session.commit()

    def cau_hinh_telegram(self, ids="-1001"):
        self.app.config.update(TELEGRAM_BOT_TOKEN="123:ABC", TELEGRAM_CHAT_ID=ids)

    def hoi(self, ip="27.64.1.1", **kw):
        d = dict(loai="dmt", id=self.ids["dmt"], **COMMENT); d.update(kw)
        return self.client(ip=ip).post("/api/hoi-dap/", json=d)

    def khach_nhan(self, noi_dung="Tôi bị dị ứng thuốc kháng sinh, cần hỏi gấp", sdt="0912345678", ten="Trần Thị B", ip="6.6.6.6"):
        c = self.client(TP.UA2, ip)
        c.post("/api/ho-tro/dang-nhap", json=dict(sdt=sdt, ten=ten, ma="123456"))
        return c, c.post("/api/ho-tro/gui", json=dict(noi_dung=noi_dung, website=""))


class ChuaCauHinh(Co):
    def test_nothing_is_sent_and_nothing_breaks(self):
        self.app.config.update(THONG_BAO_EMAIL=False)
        with mock.patch.object(KN, "_post_telegram") as tg, mock.patch("app.utils.gui_email.gui_email") as em:
            r = self.hoi()
        self.assertEqual(r.status_code, 200); self.assertTrue(r.get_json()["ok"])
        tg.assert_not_called(); em.assert_not_called()


class Telegram(Co):
    def setUp(self):
        super().setUp()
        self.app.config.update(THONG_BAO_EMAIL=False)
        self.cau_hinh_telegram()

    def test_public_comment_is_reported_with_preview_but_without_phone(self):
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg:
            self.assertEqual(self.hoi().status_code, 200)
        self.assertEqual(tg.call_count, 1)
        token, chat, text = tg.call_args.args
        self.assertEqual((token, chat), ("123:ABC", "-1001"))
        for s in ("Ý kiến mới chờ duyệt", "LIDOCAIN", "Nguyễn Văn A", "Thuốc này dùng thế nào", "https://tracuuduoc.example/admin/y-kien/"):
            self.assertIn(s, text, s)
        self.assertNotIn("0912345678", text); self.assertNotIn("912345678", text)

    def test_private_chat_is_reported_without_its_content(self):
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg:
            _, r = self.khach_nhan(noi_dung="Tôi bị dị ứng thuốc kháng sinh, cần hỏi gấp")
        self.assertEqual(r.status_code, 200)
        text = tg.call_args.args[2]
        self.assertIn("Trần Thị B", text); self.assertIn("/admin/tin-nhan/", text)
        for riêng_tu in ("dị ứng", "kháng sinh", "0912345678"):
            self.assertNotIn(riêng_tu, text, riêng_tu)

    def test_one_conversation_does_not_flood_telegram(self):
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg:
            c, _ = self.khach_nhan()
            for i in range(3):
                c.post("/api/ho-tro/gui", json=dict(noi_dung=f"Tin nhắn thêm số {i} nè", website=""))
            self.khach_nhan(sdt="0933333333", ten="Lê Văn C", ip="5.5.5.5")                 # cuộc trò chuyện KHÁC vẫn được báo
        self.assertEqual(tg.call_count, 2)

    def test_several_chat_ids_each_get_the_message(self):
        self.cau_hinh_telegram(" -1001 , 555 ,, ")
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg:
            self.hoi()
        self.assertEqual([c.args[1] for c in tg.call_args_list], ["-1001", "555"])

    def test_sender_failure_never_breaks_the_visitor_request(self):
        with mock.patch.object(KN, "_post_telegram", side_effect=RuntimeError("mạng lỗi")):
            r = self.hoi()
        self.assertEqual(r.status_code, 200); self.assertTrue(r.get_json()["ok"])
        self.assertEqual(self.q(lambda: YKien.query.count()), 1)                              # ý kiến vẫn được lưu

    def test_telegram_http_failure_returns_readable_error(self):
        import urllib.error, io
        err = urllib.error.HTTPError("u", 400, "Bad", {}, io.BytesIO(b'{"ok":false,"description":"chat not found"}'))
        with mock.patch("urllib.request.urlopen", side_effect=err):
            ok, loi = KN._post_telegram("t", "c", "x")
        self.assertFalse(ok); self.assertIn("chat not found", loi)

    def test_text_is_plain_and_truncated(self):
        long = "x" * 5000
        with mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value.read.return_value = b'{"ok":true}'
            KN._post_telegram("t", "c", "<b>" + long)
            body = op.call_args.args[0].data.decode()
        self.assertNotIn("parse_mode", body); self.assertLess(len(body), 4200)


class Email(Co):
    def setUp(self):
        super().setUp()
        self.app.config.update(THONG_BAO_EMAIL=True, THONG_BAO_EMAIL_TOI_DA_GIO=20)

    def test_active_admins_with_email_get_one_mail_each(self):
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.hoi()
        den = sorted(c.args[0].lower() for c in em.call_args_list)
        self.assertEqual(den, ["a1@bv.vn", "a2@bv.vn"])                                      # tài khoản đã tắt không nhận
        tieu_de, html_, text = em.call_args_list[0].args[1:4]
        self.assertIn("Ý kiến mới chờ duyệt: LIDOCAIN", tieu_de); self.assertIn("https://tracuuduoc.example/admin/y-kien/", html_ + text)
        self.assertNotIn("0912345678", html_ + text)

    def test_every_new_item_emails_every_registered_admin(self):
        """Mỗi ý kiến mới = 1 thư tới TỪNG admin đã đăng ký email (không còn gộp theo 30 phút)."""
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            for i in range(3):
                self.hoi(ip=f"8.8.8.{i}", noi_dung=f"Câu hỏi số {i} về thuốc")
        self.assertEqual(em.call_count, 6)                                                    # 3 ý kiến × 2 admin
        self.assertEqual(sorted({c.args[0].lower() for c in em.call_args_list}), ["a1@bv.vn", "a2@bv.vn"])
        self.assertIn("chưa ai trả lời", em.call_args_list[0].args[2] + em.call_args_list[0].args[3])

    def test_admin_without_registered_email_is_skipped_but_others_still_notified(self):
        with self.app.app_context():
            u = NguoiDung(ten_dang_nhap="admin3", ho_ten="ADMIN3", vai_tro="quan_tri"); u.set_password(TP.PW)
            db.session.add(u); db.session.commit()
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.hoi()
        self.assertEqual(sorted(c.args[0].lower() for c in em.call_args_list), ["a1@bv.vn", "a2@bv.vn"])

    def test_hourly_safety_cap_merges_the_excess_into_the_next_mail(self):
        self.app.config.update(THONG_BAO_EMAIL_TOI_DA_GIO=2)
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            for i in range(4):
                self.hoi(ip=f"8.8.7.{i}", noi_dung=f"Câu hỏi số {i} cần xem")
        self.assertEqual(em.call_count, 4)                                                    # mỗi admin chỉ nhận 2 thư, 2 lần sau bị gom
        for k in KN._EMAIL_DA_GUI:
            KN._EMAIL_DA_GUI[k].clear(); KN._EMAIL_DA_GUI[k].append(-99999)                   # giả lập đã qua 1 giờ
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em2:
            self.hoi(ip="8.8.7.9", sdt="0933000111", noi_dung="Câu hỏi sau một giờ")
        self.assertEqual(em2.call_count, 2)
        self.assertIn("Và 2 thông báo khác", em2.call_args_list[0].args[2] + em2.call_args_list[0].args[3])

    def test_private_chat_mail_has_no_message_content(self):
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.khach_nhan(noi_dung="Tôi bị dị ứng thuốc kháng sinh, cần hỏi gấp")
        self.assertEqual(em.call_count, 2)
        noi = " ".join(str(a) for a in em.call_args_list[0].args)
        self.assertIn("Trần Thị B", noi)
        for riêng_tu in ("dị ứng", "kháng sinh"):
            self.assertNotIn(riêng_tu, noi)

    def test_user_content_is_html_escaped_in_the_mail(self):
        with mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.hoi(ten="An Bình", noi_dung="<script>alert(1)</script> hỏi về liều dùng")
        h = em.call_args_list[0].args[2]
        self.assertNotIn("<script>", h); self.assertIn("&lt;script&gt;", h)

    def test_can_be_switched_off_and_failures_are_harmless(self):
        self.app.config.update(THONG_BAO_EMAIL=False)
        with mock.patch("app.utils.gui_email.gui_email") as em:
            self.hoi()
        em.assert_not_called()
        self.app.config.update(THONG_BAO_EMAIL=True); KN._EMAIL_DA_GUI.clear()
        with mock.patch("app.utils.gui_email.gui_email", side_effect=RuntimeError("smtp lỗi")):
            self.assertEqual(self.hoi(noi_dung="Câu hỏi khi email đang lỗi").status_code, 200)


class TrangCaiDat(Co):
    def test_page_shows_channel_status_and_requires_login(self):
        self.assertIn(self.client().get("/admin/thong-bao/").status_code, (301, 302, 401, 403))
        a = self.admin()
        h = a.get("/admin/thong-bao/").get_data(as_text=True)
        self.assertIn("Báo ra ngoài", h); self.assertIn("TELEGRAM_BOT_TOKEN", h); self.assertIn("tất cả 2/2 admin đã đăng ký email", h); self.assertIn("Gửi thử cho tôi", h)
        self.assertIn("a1***@bv.vn", h); self.assertNotIn("a1@bv.vn", h)                    # chỉ hiện email đã che bớt
        self.cau_hinh_telegram("-1001,-1002")
        self.assertIn("2 nơi nhận", a.get("/admin/thong-bao/").get_data(as_text=True))

    def test_test_button_sends_through_each_channel_and_reports(self):
        self.cau_hinh_telegram()
        a = self.admin()
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg, \
             mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            r = a.post("/admin/thong-bao/gui-thu", follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        tg.assert_called_once(); em.assert_called_once()
        self.assertEqual(em.call_args.args[0], "a1@bv.vn")
        h = r.get_data(as_text=True)
        self.assertIn("Telegram (-1001): đã gửi", h); self.assertIn("Email (a1@bv.vn): đã gửi", h)

    def test_test_button_reports_errors_clearly(self):
        self.cau_hinh_telegram()
        a = self.admin()
        with mock.patch.object(KN, "_post_telegram", return_value=(False, "chat not found")), \
             mock.patch("app.utils.gui_email.gui_email", return_value=False):
            h = a.post("/admin/thong-bao/gui-thu", follow_redirects=True).get_data(as_text=True)
        self.assertIn("chat not found", h); self.assertIn("gửi không được", h)

    def test_test_button_without_config(self):
        self.app.config.update(THONG_BAO_EMAIL=False)
        a = self.admin()
        h = a.post("/admin/thong-bao/gui-thu", follow_redirects=True).get_data(as_text=True)
        self.assertIn("Telegram: chưa cấu hình", h); self.assertIn("Email: đang tắt", h)


class DaTraLoi(Co):
    """Đánh dấu "đã trả lời" + báo cho các admin còn lại khi có người trả lời."""

    def setUp(self):
        super().setUp()
        self.app.config.update(THONG_BAO_EMAIL=True)
        self.cau_hinh_telegram()
        self.hoi()                                                                            # tạo sẵn 1 ý kiến chờ
        self.yid = self.q(lambda: YKien.query.one().id)
        self.a1, self.a2 = self.admin("admin1"), self.admin("admin2")

    def tra_loi(self, a, nd="Trẻ dưới 2 tuổi hỏi bác sĩ trước khi dùng nhé."):
        return a.post(f"/admin/y-kien/{self.yid}/tra-loi", data={"tra_loi": nd})

    def test_public_reply_notifies_the_other_admins_but_not_the_replier(self):
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg, \
             mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.tra_loi(self.a1)
        self.assertEqual([c.args[0].lower() for c in em.call_args_list], ["a2@bv.vn"])         # admin1 là người trả lời → không gửi cho họ
        tieu_de, h, t = em.call_args_list[0].args[1:4]
        self.assertIn("Đã trả lời", tieu_de); self.assertIn("ADMIN1 đã trả lời", h + t)
        text = tg.call_args.args[2]
        self.assertIn("ADMIN1 đã trả lời", text); self.assertNotIn("0912345678", text)
        self.assertNotIn("Trẻ dưới 2 tuổi", text + h + t)                                      # không gửi lại nội dung trả lời ra ngoài

    def test_editing_an_existing_reply_does_not_notify_again(self):
        self.tra_loi(self.a1)
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg, \
             mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.tra_loi(self.a2, "Đã chỉnh lại câu trả lời cho rõ hơn.")
        tg.assert_not_called(); em.assert_not_called()

    def test_comment_is_marked_answered_in_admin_list_with_who_and_filters(self):
        h = self.a1.get("/admin/y-kien/?trang_thai=tat_ca").get_data(as_text=True)
        self.assertIn("⏳ Chưa trả lời", h); self.assertNotIn("✔ Đã trả lời bởi", h)
        self.assertIn("Chưa trả lời <span>1</span>", h); self.assertIn("Đã trả lời <span>0</span>", h)
        self.tra_loi(self.a2)
        h = self.a1.get("/admin/y-kien/?trang_thai=tat_ca").get_data(as_text=True)
        self.assertIn("✔ Đã trả lời bởi ADMIN2", h); self.assertNotIn("⏳ Chưa trả lời</span>", h)
        self.assertIn("Chưa trả lời <span>0</span>", h); self.assertIn("Đã trả lời <span>1</span>", h)
        self.assertIn("Nguyễn Văn A", self.a1.get("/admin/y-kien/?trang_thai=tat_ca&tra_loi=da").get_data(as_text=True))
        self.assertNotIn("Nguyễn Văn A", self.a1.get("/admin/y-kien/?trang_thai=tat_ca&tra_loi=chua").get_data(as_text=True))

    def test_bell_and_notification_page_show_answered_state(self):
        d = self.a2.get("/api/thong-bao/tom-tat").get_json()
        self.assertEqual(d["muc"][0]["tra_loi"], {"da": False, "boi": "", "luc": ""})
        self.tra_loi(self.a1)
        tl = self.a2.get("/api/thong-bao/tom-tat").get_json()["muc"][0]["tra_loi"]
        self.assertTrue(tl["da"]); self.assertEqual(tl["boi"], "ADMIN1"); self.assertTrue(tl["luc"])
        self.assertIn("✔ Đã trả lời bởi ADMIN1", self.a2.get("/admin/thong-bao/").get_data(as_text=True))

    def test_chat_reply_marks_conversation_answered_and_notifies_without_content(self):
        c, _ = self.khach_nhan(noi_dung="Tôi bị dị ứng thuốc kháng sinh, cần hỏi gấp")
        kid = self.q(lambda: KhachHang.query.one().id)
        h = self.a1.get("/admin/tin-nhan/").get_data(as_text=True)
        self.assertIn("⏳ Chờ trả lời", h)
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg, \
             mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            self.assertTrue(self.a1.post(f"/admin/tin-nhan/{kid}/gui", json={"noi_dung": "Khoa Dược đã nhận, xin tư vấn thuốc thay thế…"}).get_json()["ok"])
        self.assertEqual([x.args[0].lower() for x in em.call_args_list], ["a2@bv.vn"])
        noi = tg.call_args.args[2] + " ".join(str(a) for a in em.call_args_list[0].args)
        self.assertIn("Trần Thị B", noi); self.assertIn("ADMIN1 đã trả lời", noi)
        for riêng_tu in ("dị ứng", "kháng sinh", "thuốc thay thế"):
            self.assertNotIn(riêng_tu, noi)
        h = self.a2.get("/admin/tin-nhan/").get_data(as_text=True)
        self.assertIn("✔ Đã trả lời bởi ADMIN1", h)
        self.assertIn("Trần Thị B", self.a2.get("/admin/tin-nhan/?tt=da").get_data(as_text=True))
        self.assertNotIn("Trần Thị B", self.a2.get("/admin/tin-nhan/?tt=cho").get_data(as_text=True))
        # trả lời thêm lần nữa khi khách chưa nhắn lại → không báo tiếp
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg2:
            self.a1.post(f"/admin/tin-nhan/{kid}/gui", json={"noi_dung": "Bổ sung thêm một ý nữa cho bạn."})
        tg2.assert_not_called()
        # khách nhắn lại → lại chờ trả lời; admin trả lời → báo lại
        c.post("/api/ho-tro/gui", json=dict(noi_dung="Cảm ơn, tôi hỏi thêm một câu", website=""))
        self.assertIn("⏳ Chờ trả lời", self.a2.get("/admin/tin-nhan/").get_data(as_text=True))
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg3:
            self.a2.post(f"/admin/tin-nhan/{kid}/gui", json={"noi_dung": "Mời bạn hỏi tiếp nhé."})
        tg3.assert_called_once()


class NhacChuaTraLoi(Co):
    """Lệnh flask nhac-chua-tra-loi: nhắc các ý kiến / tin nhắn chưa ai trả lời quá N giờ."""

    def chay(self, *args):
        return self.app.test_cli_runner().invoke(args=["nhac-chua-tra-loi", *args])

    def tao(self):
        from datetime import datetime, timedelta
        from app.models.models import TinNhanRieng
        self.hoi(); self.hoi(ip="9.9.9.9", sdt="0933000111", noi_dung="Câu hỏi đã có người trả lời rồi")
        c, _ = self.khach_nhan(noi_dung="Nội dung riêng tư cần giữ kín")
        with self.app.app_context():
            ys = YKien.query.order_by(YKien.id).all()
            ys[1].tra_loi = "Đã trả lời."; ys[1].trang_thai = "da_duyet"
            for y in ys:
                y.ngay_tao = datetime.utcnow() - timedelta(hours=6)
            for t in TinNhanRieng.query.all():
                t.ngay_tao = datetime.utcnow() - timedelta(hours=7)
            db.session.commit()

    def test_reminds_only_unanswered_items_past_the_threshold(self):
        self.tao()
        self.cau_hinh_telegram()
        self.app.config.update(THONG_BAO_EMAIL=True)
        with mock.patch.object(KN, "_post_telegram", return_value=(True, "")) as tg, \
             mock.patch("app.utils.gui_email.gui_email", return_value=True) as em:
            r = self.chay("--gio", "4")
        self.assertEqual(r.exit_code, 0, r.output); self.assertIn("Đã nhắc 2 mục", r.output)
        text = tg.call_args.args[2]
        self.assertIn("Còn 2 ý kiến / tin nhắn chưa ai trả lời", text)
        self.assertIn("Ý kiến: LIDOCAIN (Nguyễn Văn A)", text); self.assertIn("Tin nhắn riêng: Trần Thị B", text)
        self.assertIn("chờ 7 giờ", text); self.assertNotIn("Đã trả lời", text.replace("chưa ai trả lời", ""))
        self.assertNotIn("riêng tư", text); self.assertNotIn("0912345678", text)
        self.assertEqual(sorted(c.args[0].lower() for c in em.call_args_list), ["a1@bv.vn", "a2@bv.vn"])

    def test_nothing_to_remind_when_items_are_recent_or_answered(self):
        self.hoi()
        r = self.chay("--gio", "4")
        self.assertEqual(r.exit_code, 0); self.assertIn("Không có mục nào", r.output)

    def test_requires_site_url_to_build_links(self):
        self.app.config.update(APP_BASE_URL="")
        r = self.chay()
        self.assertNotEqual(r.exit_code, 0); self.assertIn("APP_BASE_URL", r.output)


if __name__ == "__main__":
    unittest.main()
