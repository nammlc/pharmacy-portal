"""Thùng rác admin: xoá → vào thùng rác → khôi phục / xoá vĩnh viễn / hết hạn."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("ADMIN_2FA_BAT_BUOC", "0")

from app import create_app, db                                              # noqa: E402
from app.models.models import (BaiViet, DanhMucBaiViet, DanhMucThuoc, HoatChat, NguoiDung, NhomThuoc,   # noqa: E402
                               Thuoc, ThuocTiemTruyen, ThungRac)
from app.utils import thung_rac as TR                                       # noqa: E402
from config import Config                                                   # noqa: E402


class _Cfg(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False


class ThungRacTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        cfg = type("Cfg", (_Cfg,), {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.tmp}/t.db", "SQLALCHEMY_ENGINE_OPTIONS": {}})
        self.app = create_app(cfg)
        with self.app.app_context():
            db.create_all()
            u = NguoiDung(ten_dang_nhap="admin1", vai_tro="quan_tri"); u.set_password("mat-khau-123456")
            nhom = NhomThuoc(ten_nhom="Giảm đau")
            hc1, hc2 = HoatChat(ten_hoat_chat="Paracetamol"), HoatChat(ten_hoat_chat="Cafein")
            db.session.add_all([u, nhom, hc1, hc2]); db.session.flush()
            dm = DanhMucThuoc(ten_biet_duoc="Panadol Extra", nhom_thuoc_id=nhom.id, hinh_anh="https://example.com/p.jpg")
            dm.hoat_chat_list = [hc1, hc2]
            db.session.add(dm); db.session.commit()
            self.dm_id, self.nhom_id = dm.id, nhom.id
        self.c = self.app.test_client()
        self.c.post("/admin/dang-nhap", data={"ten_dang_nhap": "admin1", "mat_khau": "mat-khau-123456"})

    def xoa_dm(self):
        r = self.c.post(f"/admin/danh-muc-thuoc/{self.dm_id}/xoa")
        self.assertEqual(r.status_code, 302)

    def test_delete_goes_to_trash_and_restores_with_links(self):
        self.xoa_dm()
        with self.app.app_context():
            self.assertIsNone(db.session.get(DanhMucThuoc, self.dm_id))
            rac = ThungRac.query.one()
            self.assertEqual((rac.loai, rac.ten, rac.ten_nguoi_xoa), ("danh_muc_thuoc", "Panadol Extra", "admin1"))
            self.assertAlmostEqual((rac.het_han - rac.ngay_xoa).days, 30, delta=1)
            rid = rac.id
        r = self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc")
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            dm = db.session.get(DanhMucThuoc, self.dm_id)
            self.assertEqual(dm.ten_hoat_chat_hien_thi, "Cafein + Paracetamol")
            self.assertEqual((dm.nhom_thuoc_id, dm.hinh_anh), (self.nhom_id, "https://example.com/p.jpg"))
            self.assertEqual(ThungRac.query.count(), 0)

    def test_page_lists_item_and_escapes_names(self):
        with self.app.app_context():
            db.session.add(DanhMucBaiViet(ten='<script>x</script> "q"')); db.session.commit()
            dmbv = DanhMucBaiViet.query.one().id
        self.c.post(f"/admin/danh-muc-bai-viet/{dmbv}/xoa")
        html = self.c.get("/admin/thung-rac/").get_data(as_text=True)
        self.assertIn("Còn 30 ngày", html)
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("Dọn sạch thùng rác", html)

    def test_expired_items_hidden_unrestorable_and_purged(self):
        self.xoa_dm()
        with self.app.app_context():
            rac = ThungRac.query.one(); rac.het_han = datetime.utcnow() - timedelta(minutes=1); rid = rac.id
            db.session.commit()
        self.assertNotIn("Panadol Extra", self.c.get("/admin/thung-rac/").get_data(as_text=True))
        self.assertEqual(self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc").status_code, 404)
        with self.app.app_context():
            self.assertEqual(ThungRac.query.count(), 0)          # trang thùng rác đã tự dọn mục quá hạn

    def test_child_needs_parent_restored_first(self):
        with self.app.app_context():
            t = Thuoc(ten_thuoc="Cefazolin"); db.session.add(t); db.session.flush()
            tt = ThuocTiemTruyen(thuoc_id=t.id, dung_moi_pha_loang="NaCl"); db.session.add(tt); db.session.commit()
            tid, ttid = t.id, tt.id
            db.session.delete(db.session.get(ThuocTiemTruyen, ttid)); db.session.commit()
            db.session.delete(db.session.get(Thuoc, tid)); db.session.commit()
            ids = {r.loai: r.id for r in ThungRac.query.all()}
        self.c.post(f"/admin/thung-rac/{ids['tiem_truyen']}/khoi-phuc")
        with self.app.app_context():
            self.assertIsNone(db.session.get(ThuocTiemTruyen, ttid))     # chưa khôi phục được: thuốc cha đang trong rác
        self.c.post("/admin/thung-rac/khoi-phuc-nhieu", data={"ids": [ids["thuoc"]]})
        self.c.post(f"/admin/thung-rac/{ids['tiem_truyen']}/khoi-phuc")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(ThuocTiemTruyen, ttid))

    def test_unique_name_conflict_blocks_restore(self):
        with self.app.app_context():
            hc = HoatChat.query.filter_by(ten_hoat_chat="Cafein").one(); db.session.delete(hc); db.session.commit()
            db.session.add(HoatChat(ten_hoat_chat="Cafein")); db.session.commit()
            rid = ThungRac.query.one().id
        self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc")
        with self.app.app_context():
            self.assertEqual(ThungRac.query.count(), 1)
            self.assertEqual(HoatChat.query.filter_by(ten_hoat_chat="Cafein").count(), 1)

    def test_article_category_restore_relinks_articles_and_slug_conflict(self):
        with self.app.app_context():
            dm = DanhMucBaiViet(ten="Tin tức", slug="tin-tuc"); db.session.add(dm); db.session.flush()
            bv = BaiViet(tieu_de="A", slug="a", danh_muc_id=dm.id); db.session.add(bv); db.session.commit()
            dmid, bvid = dm.id, bv.id
        self.c.post(f"/admin/danh-muc-bai-viet/{dmid}/xoa")
        with self.app.app_context():
            self.assertIsNone(db.session.get(BaiViet, bvid).danh_muc_id)
            db.session.add(DanhMucBaiViet(ten="Mới", slug="tin-tuc")); db.session.commit()   # chiếm slug cũ
            rid = ThungRac.query.one().id
        self.c.post(f"/admin/thung-rac/{rid}/khoi-phuc")
        with self.app.app_context():
            dm = DanhMucBaiViet.query.filter_by(ten="Tin tức").one()
            self.assertEqual(dm.slug, "tin-tuc-2")
            self.assertEqual(db.session.get(BaiViet, bvid).danh_muc_id, dm.id)

    def test_permanent_delete_removes_files_and_empty_trash(self):
        self.xoa_dm()
        calls = []
        import app.utils.upload_anh as UA
        goc = UA.xoa_anh_cloudinary
        UA.xoa_anh_cloudinary = lambda u: calls.append(u) or True
        try:
            with self.app.app_context():
                rid = ThungRac.query.one().id
            self.c.post(f"/admin/thung-rac/{rid}/huy-vinh-vien")
        finally:
            UA.xoa_anh_cloudinary = goc
        self.assertEqual(calls, ["https://example.com/p.jpg"])
        with self.app.app_context():
            self.assertEqual(ThungRac.query.count(), 0)
            self.assertIsNone(db.session.get(DanhMucThuoc, self.dm_id))
        self.assertEqual(self.c.post("/admin/thung-rac/don-sach").status_code, 302)

    def test_delete_does_not_remove_image_and_bulk_delete_all_are_trashed(self):
        import app.utils.upload_anh as UA
        goc = UA.xoa_anh_cloudinary
        calls = []
        UA.xoa_anh_cloudinary = lambda u: calls.append(u) or True
        try:
            self.c.post("/admin/danh-muc-thuoc/xoa-tat-ca")
        finally:
            UA.xoa_anh_cloudinary = goc
        self.assertEqual(calls, [])
        with self.app.app_context():
            self.assertEqual(ThungRac.query.filter_by(loai="danh_muc_thuoc").count(), 1)

    def test_retention_never_exceeds_30_days(self):
        with self.app.app_context():
            self.app.config["THUNG_RAC_GIU_NGAY"] = 90
            self.assertEqual(TR.so_ngay_giu(), 30)


if __name__ == "__main__":
    unittest.main()
