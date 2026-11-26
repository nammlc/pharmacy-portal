"""
THÙNG RÁC cho khu vực quản trị.

Cách hoạt động (không phải sửa từng trang xoá):
- Một hook của SQLAlchemy (before_flush) bắt MỌI lần xoá bản ghi thuộc các loại khai báo trong REGISTRY
  (xoá 1 mục, xoá đã chọn, xoá tất cả...). Trước khi dòng thật bị xoá khỏi bảng gốc, hook chụp lại toàn bộ
  dữ liệu thành 1 dòng trong bảng `thung_rac` (cùng transaction → hoặc cả hai cùng thành công, hoặc cùng huỷ).
- Bản ghi gốc vẫn bị xoá khỏi bảng gốc như cũ → trang công khai, tìm kiếm, thống kê không bị ảnh hưởng.
- Ảnh / tệp đính kèm KHÔNG bị xoá lúc này; chỉ xoá khi mục bị xoá vĩnh viễn hoặc hết hạn.
- Giữ tối đa THUNG_RAC_GIU_NGAY ngày (mặc định và tối đa 30). Quá hạn: ẩn ngay và tự dọn (xem don_het_han).
- Khôi phục = tạo lại dòng với id cũ (nếu id còn trống), nối lại hoạt chất / bài viết con còn tồn tại.

Không đưa vào thùng rác: tài khoản chat của khách và tin nhắn riêng (dữ liệu cá nhân).
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta

from flask import current_app, has_request_context
from sqlalchemy import DateTime, event
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import db
from app.models.models import (
    BaiViet, DanhMucBaiViet, DanhMucThuoc, HoatChat, NguoiDung, NhaThuocBV, NhomThuoc, ThongTinBenhNhan,
    ThongTinThuoc, Thuoc, ThuocTiemTruyen, ThungRac, TuongHopTuongKy, TuongTacThuoc, YKien,
)
from app.utils.slug import tao_slug_duy_nhat

log = logging.getLogger(__name__)

TOI_DA_MOI_LAN_DON = 50          # mỗi lần tự dọn chỉ xử lý tối đa N mục (xoá ảnh trên Cloudinary có thể chậm)
_LAN_DON_CUOI = {"t": 0.0}


def _cat(s, n):
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


class Loai:
    """Khai báo 1 loại dữ liệu được đưa vào thùng rác."""

    def __init__(self, khoa, model, nhan, ten, anh=None, tep=None, m2m=None, bat_buoc=(), tuy_chon=(),
                 duy_nhat=(), slug=None, nguoc=()):
        self.khoa, self.model, self.nhan, self.ten = khoa, model, nhan, ten
        self.anh = anh          # tên cột chứa ảnh (xoá bằng xoa_anh_cloudinary)
        self.tep = tep          # tên cột chứa tệp đính kèm (xoá bằng xoa_tep_dinh_kem_cloudinary)
        self.m2m = m2m          # (tên thuộc tính quan hệ, Model liên kết)
        self.bat_buoc = bat_buoc    # [(cột FK, Model cha, nhãn)]: thiếu cha thì KHÔNG khôi phục được
        self.tuy_chon = tuy_chon    # [(cột FK, Model cha)]: thiếu cha thì để trống rồi khôi phục
        self.duy_nhat = duy_nhat    # [(cột, nhãn)]: trùng giá trị với bản đang có thì không khôi phục
        self.slug = slug            # (cột slug, cột nguồn) — trùng slug thì tự sinh slug mới
        self.nguoc = nguoc          # [(tên quan hệ, Model con, cột FK ở con)]: nối lại con sau khi khôi phục


def _cap(item):
    return f"{item.thuoc_a.ten_thuoc if item.thuoc_a else '?'} + {item.thuoc_b.ten_thuoc if item.thuoc_b else '?'}"


REGISTRY = {l.khoa: l for l in (
    Loai("thuoc", Thuoc, "Thuốc tra cứu", lambda o: o.ten_thuoc, anh="hinh_anh",
         tuy_chon=[("nhom_thuoc_id", NhomThuoc)]),
    Loai("danh_muc_thuoc", DanhMucThuoc, "Danh mục thuốc", lambda o: o.ten_biet_duoc, anh="hinh_anh",
         m2m=("hoat_chat_list", HoatChat), tuy_chon=[("nhom_thuoc_id", NhomThuoc)]),
    Loai("nha_thuoc_bv", NhaThuocBV, "Nhà thuốc BV", lambda o: o.ten_biet_duoc, anh="hinh_anh",
         m2m=("hoat_chat_list", HoatChat), tuy_chon=[("nhom_thuoc_id", NhomThuoc)]),
    Loai("nhom_thuoc", NhomThuoc, "Nhóm thuốc", lambda o: o.ten_nhom, anh="hinh_anh",
         tuy_chon=[("parent_id", NhomThuoc)], nguoc=[("con", NhomThuoc, "parent_id")]),
    Loai("hoat_chat", HoatChat, "Hoạt chất", lambda o: o.ten_hoat_chat,
         duy_nhat=[("ten_hoat_chat", "hoạt chất")]),
    Loai("tiem_truyen", ThuocTiemTruyen, "Thuốc tiêm truyền",
         lambda o: o.thuoc.ten_thuoc if o.thuoc else "Bản ghi tiêm truyền",
         bat_buoc=[("thuoc_id", Thuoc, "thuốc")]),
    Loai("tuong_hop", TuongHopTuongKy, "Tương hợp - Tương kỵ", _cap,
         bat_buoc=[("thuoc_a_id", Thuoc, "thuốc"), ("thuoc_b_id", Thuoc, "thuốc")]),
    Loai("tuong_tac", TuongTacThuoc, "Tương tác thuốc", _cap,
         bat_buoc=[("thuoc_a_id", Thuoc, "thuốc"), ("thuoc_b_id", Thuoc, "thuốc")]),
    Loai("thong_tin_thuoc", ThongTinThuoc, "Thông tin thuốc",
         lambda o: o.thuoc.ten_thuoc if o.thuoc else "Thông tin thuốc",
         bat_buoc=[("thuoc_id", Thuoc, "thuốc")], duy_nhat=[("thuoc_id", "thông tin của thuốc này")]),
    Loai("benh_nhan", ThongTinBenhNhan, "Bài viết bệnh nhân", lambda o: o.tieu_de),
    Loai("bai_viet", BaiViet, "Bài viết - Thông báo", lambda o: o.tieu_de, anh="anh_dai_dien", tep="file_dinh_kem",
         tuy_chon=[("danh_muc_id", DanhMucBaiViet), ("nguoi_dung_id", NguoiDung)], slug=("slug", "tieu_de")),
    Loai("danh_muc_bai_viet", DanhMucBaiViet, "Danh mục bài viết", lambda o: o.ten, slug=("slug", "ten"),
         nguoc=[("bai_viet_list", BaiViet, "danh_muc_id")]),
    Loai("y_kien", YKien, "Hỏi đáp & bình luận",
         lambda o: f"{o.ten}: {(o.noi_dung or '').strip()}",
         tuy_chon=[("nguoi_tra_loi_id", NguoiDung), ("nguoi_duyet_id", NguoiDung)]),
)}
_THEO_LOP = {l.model: l for l in REGISTRY.values()}
_THEO_BANG = {l.model.__table__.name: l for l in REGISTRY.values()}


def so_ngay_giu() -> int:
    return min(30, max(1, int(current_app.config.get("THUNG_RAC_GIU_NGAY", 30))))


# ------------------------------------------------------------------ chụp lại khi xoá
def _gia_tri_json(v):
    if isinstance(v, datetime):
        return v.isoformat()
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "value") and not isinstance(v, (str, int, float, bool)):
        return v.value
    return v


def _chup(loai: Loai, obj) -> ThungRac:
    cot = {a.key: _gia_tri_json(getattr(obj, a.key)) for a in obj.__mapper__.column_attrs}
    du_lieu = {"cot": cot}
    if loai.m2m:
        du_lieu["m2m"] = [x.id for x in getattr(obj, loai.m2m[0])]
    if loai.nguoc:
        du_lieu["nguoc"] = {ten: [c.id for c in getattr(obj, ten)] for ten, _m, _f in loai.nguoc}
    nguoi_id = ten_nguoi = None
    if has_request_context():
        try:
            from flask_login import current_user
            if current_user.is_authenticated:
                nguoi_id, ten_nguoi = current_user.id, _cat(current_user.ten_dang_nhap, 100)
        except Exception:                                                # noqa: BLE001
            pass
    bay_gio = datetime.utcnow()
    return ThungRac(
        loai=loai.khoa, doi_tuong_id=obj.id, ten=_cat(loai.ten(obj), 300),
        anh=_cat(getattr(obj, loai.anh), 500) if loai.anh and getattr(obj, loai.anh) else None,
        du_lieu=json.dumps(du_lieu, ensure_ascii=False), nguoi_xoa_id=nguoi_id, ten_nguoi_xoa=ten_nguoi,
        ngay_xoa=bay_gio, het_han=bay_gio + timedelta(days=so_ngay_giu()),
    )


def _truoc_flush(session, _ctx, _instances):
    for obj in list(session.deleted):
        loai = _THEO_LOP.get(type(obj))
        if loai is None:
            continue
        try:
            session.add(_chup(loai, obj))
        except Exception:
            # Không chụp được thì KHÔNG cho xoá: tránh mất dữ liệu mà người dùng tưởng đã có trong thùng rác.
            log.exception("Không đưa được %s #%s vào thùng rác", loai.khoa, getattr(obj, "id", "?"))
            raise


_da_gan = {"ok": False}


def dang_ky(app):
    """Gắn hook chụp khi xoá, lệnh `flask don-thung-rac`, và tự dọn mục hết hạn khi admin thao tác."""
    if not _da_gan["ok"]:
        event.listen(Session, "before_flush", _truoc_flush)
        _da_gan["ok"] = True

    @app.cli.command("don-thung-rac")
    def _lenh_don():
        """Xoá vĩnh viễn các mục trong thùng rác đã quá hạn."""
        n = don_het_han(toi_da=100000)
        print(f"Đã dọn {n} mục hết hạn khỏi thùng rác.")

    @app.before_request
    def _tu_don():
        from flask import request
        if not (request.blueprint or "").startswith("admin_") or request.method != "POST":
            return
        if time.monotonic() - _LAN_DON_CUOI["t"] < 1800:
            return
        _LAN_DON_CUOI["t"] = time.monotonic()
        try:
            don_het_han()
        except Exception:                                                # noqa: BLE001
            db.session.rollback()
            log.exception("Tự dọn thùng rác lỗi")


# ------------------------------------------------------------------ đọc
def con_han():
    return ThungRac.query.filter(ThungRac.het_han > datetime.utcnow())


def so_ngay_con_lai(ban_ghi) -> int:
    giay = (ban_ghi.het_han - datetime.utcnow()).total_seconds()
    return max(0, int(-(-giay // 86400)))


def _doc(ban_ghi) -> dict:
    return json.loads(ban_ghi.du_lieu or "{}")


# ------------------------------------------------------------------ xoá vĩnh viễn
def _xoa_tep(loai: Loai, du_lieu: dict):
    from app.utils.upload_anh import xoa_anh_cloudinary, xoa_tep_dinh_kem_cloudinary
    cot = du_lieu.get("cot", {})
    try:
        if loai.anh and cot.get(loai.anh):
            xoa_anh_cloudinary(cot[loai.anh])
        if loai.tep and cot.get(loai.tep):
            xoa_tep_dinh_kem_cloudinary(cot[loai.tep])
    except Exception:                                                    # noqa: BLE001
        log.exception("Không xoá được ảnh/tệp của mục thùng rác")


def xoa_vinh_vien(ban_ghi) -> None:
    """Xoá ảnh/tệp rồi xoá dòng thùng rác (không commit)."""
    loai = REGISTRY.get(ban_ghi.loai)
    if loai:
        _xoa_tep(loai, _doc(ban_ghi))
    db.session.delete(ban_ghi)


def don_het_han(toi_da: int = TOI_DA_MOI_LAN_DON) -> int:
    het = (ThungRac.query.filter(ThungRac.het_han <= datetime.utcnow())
           .order_by(ThungRac.het_han).limit(toi_da).all())
    for b in het:
        xoa_vinh_vien(b)
    if het:
        db.session.commit()
    return len(het)


# ------------------------------------------------------------------ khôi phục
def _phuc_gia_tri(Model, cot: dict) -> dict:
    kq = {}
    bang = Model.__table__.columns
    for ten, v in cot.items():
        if ten not in bang:
            continue
        if v is not None and isinstance(bang[ten].type, DateTime):
            try:
                v = datetime.fromisoformat(v)
            except (TypeError, ValueError):
                v = None
        kq[ten] = v
    return kq


def _ten_cha_trong_rac(Model, id_cha):
    khoa = _THEO_LOP[Model].khoa
    b = con_han().filter(ThungRac.loai == khoa, ThungRac.doi_tuong_id == id_cha).first()
    return b.ten if b else None


def khoi_phuc(ban_ghi):
    """Khôi phục 1 mục. Trả về (thanh_cong, thong_diep, muc_do). Tự commit / rollback."""
    loai = REGISTRY.get(ban_ghi.loai)
    ten = ban_ghi.ten
    if loai is None:
        return False, f'"{ten}": loại dữ liệu này không còn được hỗ trợ khôi phục.', "danger"
    if ban_ghi.het_han <= datetime.utcnow():
        return False, f'"{ten}" đã hết hạn lưu trong thùng rác.', "danger"

    Model = loai.model
    du_lieu = _doc(ban_ghi)
    gia_tri = _phuc_gia_tri(Model, du_lieu.get("cot", {}))
    ghi_chu = []

    for cot, nhan in loai.duy_nhat:
        v = gia_tri.get(cot)
        if v is not None and Model.query.filter(getattr(Model, cot) == v).first():
            return False, (f'Không khôi phục được "{ten}": đã có {nhan} trùng. '
                           f'Hãy đổi tên hoặc xoá bản đang có rồi khôi phục lại.'), "danger"

    for cot, Cha, nhan in loai.bat_buoc:
        id_cha = gia_tri.get(cot)
        if id_cha is None or db.session.get(Cha, id_cha) is None:
            trong_rac = _ten_cha_trong_rac(Cha, id_cha) if id_cha is not None else None
            if trong_rac:
                return False, (f'Không khôi phục được "{ten}": {nhan} "{trong_rac}" đang nằm trong thùng rác. '
                               f'Hãy khôi phục {nhan} đó trước.'), "danger"
            return False, f'Không khôi phục được "{ten}": {nhan} liên quan không còn tồn tại.', "danger"

    for cot, Cha in loai.tuy_chon:
        id_cha = gia_tri.get(cot)
        if id_cha is not None and db.session.get(Cha, id_cha) is None:
            gia_tri[cot] = None
            ghi_chu.append("một liên kết cũ (nhóm, danh mục hoặc người dùng) không còn nên để trống")

    if loai.slug:
        cot_slug, cot_nguon = loai.slug
        slug = gia_tri.get(cot_slug)
        if not slug or Model.query.filter(getattr(Model, cot_slug) == slug).first():
            gia_tri[cot_slug] = tao_slug_duy_nhat(Model, gia_tri.get(cot_nguon) or ten, cot=cot_slug)
            ghi_chu.append("đường dẫn (slug) đã được tạo lại vì bị trùng")

    if gia_tri.get("id") is not None and db.session.get(Model, gia_tri["id"]) is not None:
        gia_tri.pop("id")          # id cũ đã có mục khác dùng → để CSDL cấp id mới

    try:
        moi = Model(**gia_tri)
        db.session.add(moi)
        db.session.flush()
        if loai.m2m and du_lieu.get("m2m"):
            ten_qh, Lien = loai.m2m
            con = Lien.query.filter(Lien.id.in_(du_lieu["m2m"])).all()
            setattr(moi, ten_qh, con)
            thieu = len(du_lieu["m2m"]) - len(con)
            if thieu > 0:
                ghi_chu.append(f"{thieu} hoạt chất đã bị xoá nên không được nối lại")
        for ten_qh, Con, cot_fk in loai.nguoc:
            ids = du_lieu.get("nguoc", {}).get(ten_qh) or []
            if ids:
                Con.query.filter(Con.id.in_(ids), getattr(Con, cot_fk).is_(None)).update(
                    {cot_fk: moi.id}, synchronize_session=False)
        db.session.delete(ban_ghi)
        db.session.commit()
    except (IntegrityError, SQLAlchemyError):
        db.session.rollback()
        log.exception("Khôi phục thùng rác lỗi (%s #%s)", ban_ghi.loai, ban_ghi.id)
        return False, f'Không khôi phục được "{ten}" vì dữ liệu hiện tại xung đột với bản đã xoá.', "danger"

    thong_diep = f'Đã khôi phục "{ten}" ({loai.nhan}).'
    if ghi_chu:
        thong_diep += " Lưu ý: " + "; ".join(sorted(set(ghi_chu))) + "."
    return True, thong_diep, "warning" if ghi_chu else "success"
