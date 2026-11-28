"""
Fuzzy search engine cho tên thuốc/hoạt chất.

Chiến lược kết hợp:
1. Substring ilike      — khớp chuỗi con chính xác
2. Token AND            — tách từ khoá, tất cả token phải xuất hiện
3. Token prefix OR      — ít nhất 1 token khớp đầu
4. pg_trgm similarity   — bắt lỗi chính tả (sunphat→sulphat, buncat→bucarvin)

Kết quả sắp xếp: exact/prefix lên đầu, fuzzy xuống dưới.
"""

from __future__ import annotations
import re
import logging
from sqlalchemy import or_, and_, text
from app import db

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------

def _tach_token(tu_khoa: str) -> list[str]:
    return [t for t in re.split(r"[\s\-/,\.\(\)]+", tu_khoa.lower().strip()) if len(t) >= 2]


# Ngưỡng similarity — 0.25 là khá rộng, bắt được sai 1-2 ký tự
# Tăng lên 0.35 nếu muốn chặt hơn
TRGM_THRESHOLD = 0.25


# ---------------------------------------------------------------------------
# Lấy IDs dùng pg_trgm (fallback nếu các bước trên không đủ kết quả)
# ---------------------------------------------------------------------------

def _trgm_ids_thuoc(tu_khoa: str, bang: str, col: str, id_col: str = "id",
                    limit: int = 40) -> list[int]:
    """
    Dùng pg_trgm similarity để tìm kiếm mờ trực tiếp qua SQL raw.
    Trả về list id.
    """
    try:
        rows = db.session.execute(
            text(f"""
                SELECT {id_col}
                FROM {bang}
                WHERE similarity({col}, :q) >= :thresh
                   OR {col} ILIKE :like
                ORDER BY similarity({col}, :q) DESC
                LIMIT :lim
            """),
            {"q": tu_khoa, "thresh": TRGM_THRESHOLD,
             "like": f"%{tu_khoa}%", "lim": limit}
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        # KHÔNG để lỗi này biến mất âm thầm - fuzzy search phụ thuộc
        # extension pg_trgm trên Postgres (bật qua file them_trgm.sql).
        # Nếu chưa bật, hoặc chạy nhầm trên SQLite (không hỗ trợ
        # similarity()/ILIKE), lỗi sẽ hiện trong log Render thay vì
        # khiến tính năng "im lặng" không hoạt động mà không rõ vì sao.
        logger.warning(
            "Fuzzy search (pg_trgm) lỗi trên bảng '%s' cột '%s' - "
            "có thể chưa chạy them_trgm.sql trên Neon, hoặc DB không phải Postgres.",
            bang, col, exc_info=True,
        )
        return []


def _trgm_ids_hoat_chat(tu_khoa: str, limit: int = 40) -> list[int]:
    try:
        rows = db.session.execute(
            text("""
                SELECT id FROM hoat_chat
                WHERE similarity(ten_hoat_chat, :q) >= :thresh
                   OR ten_hoat_chat ILIKE :like
                ORDER BY similarity(ten_hoat_chat, :q) DESC
                LIMIT :lim
            """),
            {"q": tu_khoa, "thresh": TRGM_THRESHOLD,
             "like": f"%{tu_khoa}%", "lim": limit}
        ).fetchall()
        return [r[0] for r in rows]
    except Exception:
        logger.warning(
            "Fuzzy search (pg_trgm) lỗi trên bảng 'hoat_chat' - "
            "có thể chưa chạy them_trgm.sql trên Neon, hoặc DB không phải Postgres.",
            exc_info=True,
        )
        return []


# ---------------------------------------------------------------------------
# Tìm kiếm chính
# ---------------------------------------------------------------------------

def _tim_chung(model, ten_col, hoat_chat_rel, hoat_chat_bang,
               tu_khoa: str, per_page: int, page: int):
    """
    Hàm tìm kiếm dùng chung cho DanhMucThuoc và NhaThuocBV.
    """
    from app.models.models import HoatChat

    q = tu_khoa.strip()
    if not q:
        return None

    tokens = _tach_token(q)

    # --- Bước 1+2+3: ilike / token ---
    sub = ten_col.ilike(f"%{q}%")
    prefix = ten_col.ilike(f"{q}%")

    if tokens:
        token_and = and_(*[
            or_(ten_col.ilike(f"%{t}%"), HoatChat.ten_hoat_chat.ilike(f"%{t}%"))
            for t in tokens
        ])
        token_prefix = or_(*[ten_col.ilike(f"{t}%") for t in tokens])
        fast_filter = or_(sub, token_and, token_prefix,
                          HoatChat.ten_hoat_chat.ilike(f"%{q}%"))
    else:
        fast_filter = or_(sub, HoatChat.ten_hoat_chat.ilike(f"%{q}%"))

    fast_ids = (
        model.query
        .outerjoin(hoat_chat_rel)
        .filter(fast_filter)
        .distinct()
        .with_entities(model.id)
        .all()
    )
    fast_id_set = {r[0] for r in fast_ids}

    # --- Bước 4: pg_trgm cho tên biệt dược ---
    trgm_biet_duoc = _trgm_ids_thuoc(q, model.__tablename__, "ten_biet_duoc")

    # --- Bước 4b: pg_trgm cho hoạt chất ---
    hc_ids = _trgm_ids_hoat_chat(q)
    trgm_via_hc: list[int] = []
    if hc_ids:
        rows = (
            model.query
            .outerjoin(hoat_chat_rel)
            .filter(HoatChat.id.in_(hc_ids))
            .distinct()
            .with_entities(model.id)
            .all()
        )
        trgm_via_hc = [r[0] for r in rows]

    # --- Gộp tất cả IDs, giữ thứ tự ưu tiên ---
    all_ids: list[int] = []
    seen: set[int] = set()
    for id_ in list(fast_id_set) + trgm_biet_duoc + trgm_via_hc:
        if id_ not in seen:
            all_ids.append(id_)
            seen.add(id_)

    if not all_ids:
        # Trả về trang rỗng cùng kiểu paginate
        return model.query.filter(model.id == -1).paginate(
            page=page, per_page=per_page, error_out=False
        )

    # --- Query cuối: lấy đúng thứ tự ưu tiên ---
    # Ưu tiên: prefix match lên đầu, fuzzy xuống sau
    priority_ids = [i for i in all_ids if i in fast_id_set]
    fuzzy_ids = [i for i in all_ids if i not in fast_id_set]
    ordered_ids = priority_ids + fuzzy_ids

    # Paginate thủ công trên danh sách IDs
    total = len(ordered_ids)
    start = (page - 1) * per_page
    page_ids = ordered_ids[start: start + per_page]

    items = model.query.filter(model.id.in_(page_ids)).all()
    # Sắp xếp lại theo ordered_ids
    id_order = {id_: i for i, id_ in enumerate(page_ids)}
    items.sort(key=lambda x: id_order.get(x.id, 9999))

    # Tạo đối tượng giả pagination để template dùng được
    return _FakePagination(items, total, page, per_page)


class _FakePagination:
    """Giả lập SQLAlchemy Pagination để template không cần thay đổi."""
    def __init__(self, items, total, page, per_page):
        self.items = items
        self.total = total
        self.page = page
        self.per_page = per_page
        self.pages = max(1, -(-total // per_page))  # ceil division
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1
        self.next_num = page + 1

    def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
        last = self.pages
        for num in range(1, last + 1):
            if (num <= left_edge
                    or (self.page - left_current <= num <= self.page + right_current)
                    or num > last - right_edge):
                yield num
            else:
                yield None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tim_danh_muc_thuoc(tu_khoa: str, per_page: int = 12, page: int = 1):
    from app.models.models import DanhMucThuoc, HoatChat
    return _tim_chung(
        DanhMucThuoc, DanhMucThuoc.ten_biet_duoc,
        DanhMucThuoc.hoat_chat_list, "dmt_hoat_chat",
        tu_khoa, per_page, page
    )


def tim_nha_thuoc_bv(tu_khoa: str, per_page: int = 12, page: int = 1):
    from app.models.models import NhaThuocBV, HoatChat
    return _tim_chung(
        NhaThuocBV, NhaThuocBV.ten_biet_duoc,
        NhaThuocBV.hoat_chat_list, "ntbv_hoat_chat",
        tu_khoa, per_page, page
    )


def tim_thuoc(tu_khoa: str, per_page: int = 15, page: int = 1):
    from app.models.models import Thuoc

    q = tu_khoa.strip()
    if not q:
        return None

    tokens = _tach_token(q)
    fast_filter = or_(
        Thuoc.ten_thuoc.ilike(f"%{q}%"),
        Thuoc.hoat_chat.ilike(f"%{q}%"),
        *(and_(Thuoc.ten_thuoc.ilike(f"%{t}%")) for t in tokens),
    )
    fast_ids = {r[0] for r in Thuoc.query.filter(fast_filter).with_entities(Thuoc.id).all()}
    trgm_ids = _trgm_ids_thuoc(q, "thuoc", "ten_thuoc")
    trgm_hc = _trgm_ids_thuoc(q, "thuoc", "hoat_chat")

    all_ids, seen = [], set()
    for id_ in list(fast_ids) + trgm_ids + trgm_hc:
        if id_ not in seen:
            all_ids.append(id_)
            seen.add(id_)

    if not all_ids:
        return Thuoc.query.filter(Thuoc.id == -1).paginate(page=page, per_page=per_page, error_out=False)

    total = len(all_ids)
    page_ids = all_ids[(page - 1) * per_page: page * per_page]
    items = Thuoc.query.filter(Thuoc.id.in_(page_ids)).all()
    id_order = {id_: i for i, id_ in enumerate(page_ids)}
    items.sort(key=lambda x: id_order.get(x.id, 9999))
    return _FakePagination(items, total, page, per_page)


def tim_thuoc_tiem_truyen(tu_khoa: str, per_page: int = 15, page: int = 1):
    from app.models.models import Thuoc, ThuocTiemTruyen

    q = tu_khoa.strip()
    if not q:
        return None

    thuoc_ids_fast = {r[0] for r in (
        Thuoc.query
        .filter(or_(Thuoc.ten_thuoc.ilike(f"%{q}%"), Thuoc.hoat_chat.ilike(f"%{q}%")))
        .with_entities(Thuoc.id).all()
    )}
    thuoc_ids_trgm = set(_trgm_ids_thuoc(q, "thuoc", "ten_thuoc")
                         + _trgm_ids_thuoc(q, "thuoc", "hoat_chat"))
    all_thuoc_ids = list(thuoc_ids_fast) + [i for i in thuoc_ids_trgm if i not in thuoc_ids_fast]

    if not all_thuoc_ids:
        return ThuocTiemTruyen.query.filter(ThuocTiemTruyen.id == -1).paginate(
            page=page, per_page=per_page, error_out=False)

    all_ids, seen = [], set()
    for r in ThuocTiemTruyen.query.filter(ThuocTiemTruyen.thuoc_id.in_(all_thuoc_ids)).with_entities(ThuocTiemTruyen.id).all():
        if r[0] not in seen:
            all_ids.append(r[0])
            seen.add(r[0])

    total = len(all_ids)
    page_ids = all_ids[(page - 1) * per_page: page * per_page]
    items = ThuocTiemTruyen.query.filter(ThuocTiemTruyen.id.in_(page_ids)).all()
    return _FakePagination(items, total, page, per_page)


MUC_DO_TUONG_TAC = ("chong_chi_dinh", "nang", "trung_binh", "nhe")   # nặng nhất → nhẹ nhất


def _giai_hoat_chat(tu_khoa: str):
    """Từ khoá → ({id: HoatChat}, [(tên biệt dược, [tên các hoạt chất])]).

    Gõ tên hoạt chất, HOẶC tên biệt dược (lấy các hoạt chất của biệt dược đó);
    không khớp trực tiếp thì thử gần đúng (pg_trgm) để bắt lỗi chính tả."""
    from app.models.models import HoatChat, DanhMucThuoc, NhaThuocBV

    q = (tu_khoa or "").strip()
    if not q:
        return {}, []

    hc = {h.id: h for h in HoatChat.query.filter(HoatChat.ten_hoat_chat.ilike(f"%{q}%")).limit(200).all()}

    thuoc_khop, da_co = [], set()
    for Model in (DanhMucThuoc, NhaThuocBV):
        for t in Model.query.filter(Model.ten_biet_duoc.ilike(f"%{q}%")).limit(6).all():
            ds = list(t.hoat_chat_list)
            if not ds or t.ten_biet_duoc.lower() in da_co:
                continue
            da_co.add(t.ten_biet_duoc.lower())
            thuoc_khop.append((t.ten_biet_duoc, [h.ten_hoat_chat for h in ds]))
            for h in ds:
                hc.setdefault(h.id, h)

    if not hc:
        ids = _trgm_ids_hoat_chat(q)
        if ids:
            hc = {h.id: h for h in HoatChat.query.filter(HoatChat.id.in_(ids)).all()}
    return hc, thuoc_khop


def tim_tuong_tac(tu_khoa: str, tu_khoa2: str = "", muc_do: str = "", page: int = 1, per_page: int = 15):
    """Tra cứu tương tác theo HOẠT CHẤT, có lọc và phân trang.

    tu_khoa  : hoạt chất / biệt dược thứ nhất (bắt buộc)
    tu_khoa2 : hoạt chất / biệt dược thứ hai (tuỳ chọn) — chỉ giữ các cặp giữa hai nhóm này
    muc_do   : lọc theo mức độ ('' = tất cả; hoặc một giá trị của MUC_DO_TUONG_TAC)

    Trả về SimpleNamespace:
      phan_trang      : Pagination các cặp (nặng nhất lên đầu); None khi không có hoạt chất nào khớp
      tong            : tổng số cặp khớp (CHƯA áp bộ lọc mức độ)
      dem_muc_do      : {mức độ: số cặp} (CHƯA áp bộ lọc mức độ, để chip hiển thị đúng số)
      hoat_chat_khop / hoat_chat_khop2 : các hoạt chất tìm thấy theo ô 1 / ô 2
      thuoc_khop / thuoc_khop2         : [(tên biệt dược, [hoạt chất])] khi người dùng gõ tên biệt dược
    """
    from types import SimpleNamespace
    from sqlalchemy import case, func
    from sqlalchemy.orm import joinedload
    from app.models.models import TuongTacHoatChat as TT

    ket = SimpleNamespace(phan_trang=None, tong=0, dem_muc_do={m: 0 for m in MUC_DO_TUONG_TAC},
                          hoat_chat_khop=[], hoat_chat_khop2=[], thuoc_khop=[], thuoc_khop2=[])
    q1, q2 = (tu_khoa or "").strip(), (tu_khoa2 or "").strip()
    if not q1:
        return ket

    hc1, ket.thuoc_khop = _giai_hoat_chat(q1)
    ket.hoat_chat_khop = sorted(hc1.values(), key=lambda h: h.ten_hoat_chat.lower())
    if not hc1:
        return ket
    ids1 = list(hc1)[:300]

    if q2:
        hc2, ket.thuoc_khop2 = _giai_hoat_chat(q2)
        ket.hoat_chat_khop2 = sorted(hc2.values(), key=lambda h: h.ten_hoat_chat.lower())
        if not hc2:
            return ket
        ids2 = list(hc2)[:300]
        dk = or_(and_(TT.hoat_chat_a_id.in_(ids1), TT.hoat_chat_b_id.in_(ids2)),
                 and_(TT.hoat_chat_a_id.in_(ids2), TT.hoat_chat_b_id.in_(ids1)))
    else:
        dk = or_(TT.hoat_chat_a_id.in_(ids1), TT.hoat_chat_b_id.in_(ids1))

    dem = dict(db.session.query(TT.muc_do, func.count(TT.id)).filter(dk).group_by(TT.muc_do).all())
    ket.dem_muc_do = {m: dem.get(m, 0) for m in MUC_DO_TUONG_TAC}
    ket.tong = sum(ket.dem_muc_do.values())

    truy_van = TT.query.filter(dk)
    if muc_do in MUC_DO_TUONG_TAC:
        truy_van = truy_van.filter(TT.muc_do == muc_do)
    nang_nhat = case((TT.muc_do == "chong_chi_dinh", 0), (TT.muc_do == "nang", 1),
                     (TT.muc_do == "trung_binh", 2), else_=3)
    truy_van = (truy_van.options(joinedload(TT.hoat_chat_a), joinedload(TT.hoat_chat_b))
                .order_by(nang_nhat, TT.id))
    pt = truy_van.paginate(page=max(page, 1), per_page=per_page, error_out=False)
    if pt.total and not pt.items and pt.pages:           # ?page= vượt quá trang cuối → về trang cuối
        pt = truy_van.paginate(page=pt.pages, per_page=per_page, error_out=False)
    ket.phan_trang = pt
    return ket


def goi_y_hoat_chat(tu_khoa: str, gioi_han: int = 8):
    """Gợi ý dropdown khi gõ ô hoạt chất ở trang Tương tác thuốc.

    Trả về list[dict] cùng dạng với /api/goi-y-tim-kiem: hoạt chất (kèm số tương tác đã ghi nhận)
    đứng trước, sau đó tối đa 4 biệt dược (kèm hoạt chất chứa trong đó)."""
    from sqlalchemy import case, func
    from app.models.models import HoatChat, TuongTacHoatChat as TT, DanhMucThuoc, NhaThuocBV

    q = (tu_khoa or "").strip()
    if len(q) < 2:
        return []

    nhom = (HoatChat.query.filter(HoatChat.ten_hoat_chat.ilike(f"%{q}%"))
            .order_by(case((HoatChat.ten_hoat_chat.ilike(f"{q}%"), 0), else_=1), func.lower(HoatChat.ten_hoat_chat))
            .limit(gioi_han).all())
    if not nhom:                                          # gõ sai chính tả → gần đúng
        ids = _trgm_ids_hoat_chat(q, limit=6)
        if ids:
            nhom = HoatChat.query.filter(HoatChat.id.in_(ids)).order_by(func.lower(HoatChat.ten_hoat_chat)).all()

    dem = {}
    if nhom:
        ids = [h.id for h in nhom]
        for cot in (TT.hoat_chat_a_id, TT.hoat_chat_b_id):   # a < b nên mỗi cặp chỉ tính một lần cho mỗi hoạt chất
            for hid, n in db.session.query(cot, func.count(TT.id)).filter(cot.in_(ids)).group_by(cot).all():
                dem[hid] = dem.get(hid, 0) + n

    ket = [{"ten": h.ten_hoat_chat,
            "phu": f"{dem[h.id]} tương tác đã ghi nhận" if dem.get(h.id) else "Chưa có tương tác ghi nhận",
            "anh": "", "url": "", "loai": "Hoạt chất"} for h in nhom]

    da_co = set()
    for Model in (DanhMucThuoc, NhaThuocBV):
        for t in Model.query.filter(Model.ten_biet_duoc.ilike(f"%{q}%")).limit(4).all():
            ds = [h.ten_hoat_chat for h in t.hoat_chat_list]
            khoa = t.ten_biet_duoc.lower()
            if not ds or khoa in da_co or len(da_co) >= 4:
                continue
            da_co.add(khoa)
            ket.append({"ten": t.ten_biet_duoc, "phu": "Chứa: " + ", ".join(ds),
                        "anh": "", "url": "", "loai": "Biệt dược"})
    return ket[:12]


def tim_tuong_hop_tuong_ky(thuoc_a: str, thuoc_b: str = "", limit: int = 50):
    from app.models.models import Thuoc, TuongHopTuongKy
    from sqlalchemy import or_, and_

    def _get_ids(q):
        fast = {r[0] for r in Thuoc.query.filter(
            or_(Thuoc.ten_thuoc.ilike(f"%{q}%"), Thuoc.hoat_chat.ilike(f"%{q}%"))
        ).with_entities(Thuoc.id).all()}
        trgm = set(_trgm_ids_thuoc(q, "thuoc", "ten_thuoc"))
        return list(fast | trgm)

    ids_a = _get_ids(thuoc_a) if thuoc_a else []
    if not ids_a:
        return []

    if thuoc_b:
        ids_b = _get_ids(thuoc_b)
        if not ids_b:
            return []
        return (
            TuongHopTuongKy.query
            .filter(or_(
                and_(TuongHopTuongKy.thuoc_a_id.in_(ids_a), TuongHopTuongKy.thuoc_b_id.in_(ids_b)),
                and_(TuongHopTuongKy.thuoc_a_id.in_(ids_b), TuongHopTuongKy.thuoc_b_id.in_(ids_a)),
            ))
            .limit(limit).all()
        )
    return (
        TuongHopTuongKy.query
        .filter(or_(
            TuongHopTuongKy.thuoc_a_id.in_(ids_a),
            TuongHopTuongKy.thuoc_b_id.in_(ids_a),
        ))
        .limit(limit).all()
    )


# Alias cho _build_filter (các route nhom dùng)
def _build_filter(cols, tu_khoa):
    tokens = _tach_token(tu_khoa)
    if not tokens:
        return cols[0].ilike(f"%{tu_khoa}%")
    sub = [c.ilike(f"%{tu_khoa}%") for c in cols]
    token_and = [or_(*[c.ilike(f"%{t}%") for c in cols]) for t in tokens]
    prefix = [c.ilike(f"{t}%") for c in cols for t in tokens]
    from sqlalchemy import or_, and_
    return or_(*sub, and_(*token_and), *prefix)


def tim_bai_viet(tu_khoa: str, per_page: int = 9, page: int = 1):
    """Tìm gần đúng bài viết (theo tiêu đề + mô tả ngắn), chỉ trong các bài đã xuất bản."""
    from app.models.models import BaiViet

    q = tu_khoa.strip()
    if not q:
        return None

    da_xuat_ban = BaiViet.trang_thai == "da_xuat_ban"
    tokens = _tach_token(q)

    sub = BaiViet.tieu_de.ilike(f"%{q}%")
    mo_ta = BaiViet.mo_ta_ngan.ilike(f"%{q}%")

    if tokens:
        token_and = and_(*[
            or_(BaiViet.tieu_de.ilike(f"%{t}%"), BaiViet.mo_ta_ngan.ilike(f"%{t}%"))
            for t in tokens
        ])
        token_prefix = or_(*[BaiViet.tieu_de.ilike(f"{t}%") for t in tokens])
        fast_filter = or_(sub, mo_ta, token_and, token_prefix)
    else:
        fast_filter = or_(sub, mo_ta)

    fast_ids = {
        r[0] for r in
        BaiViet.query.filter(da_xuat_ban, fast_filter).with_entities(BaiViet.id).all()
    }

    # pg_trgm bắt lỗi chính tả trên tiêu đề (chỉ có tác dụng nếu DB là Postgres + đã bật extension)
    trgm_raw_ids = _trgm_ids_thuoc(q, "bai_viet", "tieu_de")
    trgm_ids = []
    if trgm_raw_ids:
        trgm_ids = [
            r[0] for r in
            BaiViet.query.filter(BaiViet.id.in_(trgm_raw_ids), da_xuat_ban)
            .with_entities(BaiViet.id).all()
        ]

    all_ids, seen = [], set()
    for id_ in list(fast_ids) + trgm_ids:
        if id_ not in seen:
            all_ids.append(id_)
            seen.add(id_)

    if not all_ids:
        return BaiViet.query.filter(BaiViet.id == -1).paginate(
            page=page, per_page=per_page, error_out=False
        )

    priority_ids = [i for i in all_ids if i in fast_ids]
    fuzzy_ids = [i for i in all_ids if i not in fast_ids]
    ordered_ids = priority_ids + fuzzy_ids

    total = len(ordered_ids)
    start = (page - 1) * per_page
    page_ids = ordered_ids[start: start + per_page]

    items = BaiViet.query.filter(BaiViet.id.in_(page_ids)).all()
    id_order = {id_: i for i, id_ in enumerate(page_ids)}
    items.sort(key=lambda x: id_order.get(x.id, 9999))

    return _FakePagination(items, total, page, per_page)
