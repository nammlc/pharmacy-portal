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


def tim_tuong_tac(tu_khoa: str, limit: int = 50):
    from app.models.models import Thuoc, TuongTacThuoc
    from sqlalchemy import or_

    q = tu_khoa.strip()
    if not q:
        return []

    ids_fast = {r[0] for r in (
        Thuoc.query
        .filter(or_(Thuoc.ten_thuoc.ilike(f"%{q}%"), Thuoc.hoat_chat.ilike(f"%{q}%")))
        .with_entities(Thuoc.id).all()
    )}
    ids_trgm = set(_trgm_ids_thuoc(q, "thuoc", "ten_thuoc"))
    all_ids = list(ids_fast | ids_trgm)
    if not all_ids:
        return []

    return (
        TuongTacThuoc.query
        .filter(or_(
            TuongTacThuoc.thuoc_a_id.in_(all_ids),
            TuongTacThuoc.thuoc_b_id.in_(all_ids),
        ))
        .limit(limit).all()
    )


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
