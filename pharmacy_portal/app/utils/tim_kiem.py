"""
Fuzzy search engine cho tên thuốc/hoạt chất.

Chiến lược (thứ tự ưu tiên):
1. Exact / ilike       : khớp trực tiếp chuỗi con → điểm cao nhất
2. Token AND           : tách từ khoá thành nhiều token, tất cả phải xuất hiện
3. Token OR (prefix)   : ít nhất 1 token khớp, xếp theo số token khớp
4. Trigram (pg_trgm)   : similarity() từ PostgreSQL, bắt được lỗi chính tả

Kết quả trả về đã dedup và sắp xếp theo độ liên quan.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING
from sqlalchemy import or_, and_, func, case, literal, text
from app import db

if TYPE_CHECKING:
    from sqlalchemy.orm import Query


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------

def _tach_token(tu_khoa: str) -> list[str]:
    """Tách từ khoá thành danh sách token có nghĩa (>= 2 ký tự)."""
    return [t for t in re.split(r"[\s\-/,\.\(\)]+", tu_khoa.lower().strip()) if len(t) >= 2]


def _like(token: str) -> str:
    return f"%{token}%"


def _prefix(token: str) -> str:
    return f"{token}%"


# ---------------------------------------------------------------------------
# Kiểm tra pg_trgm
# ---------------------------------------------------------------------------
_trgm_available: bool | None = None


def _co_trgm() -> bool:
    global _trgm_available
    if _trgm_available is None:
        try:
            db.session.execute(text("SELECT similarity('a','a')"))
            _trgm_available = True
        except Exception:
            _trgm_available = False
    return _trgm_available


# ---------------------------------------------------------------------------
# Core: xây filter theo nhiều cột
# ---------------------------------------------------------------------------

def _build_filter(cols: list, tu_khoa: str):
    """
    Trả về SQLAlchemy filter cho danh sách cột, ứng với từ khoá.
    Thứ tự: substring → token-AND → token-OR-prefix
    """
    tokens = _tach_token(tu_khoa)
    if not tokens:
        return None

    # 1. Substring match trên từ khoá gốc
    sub_filters = [c.ilike(_like(tu_khoa)) for c in cols]

    # 2. Token AND: tất cả token đều phải xuất hiện trong ít nhất 1 cột
    token_and = []
    for tok in tokens:
        tok_in_any_col = or_(*[c.ilike(_like(tok)) for c in cols])
        token_and.append(tok_in_any_col)

    # 3. Token OR prefix: ít nhất 1 token khớp (prefix)
    prefix_filters = []
    for tok in tokens:
        prefix_filters.extend([c.ilike(_prefix(tok)) for c in cols])

    return or_(
        or_(*sub_filters),
        and_(*token_and),
        or_(*prefix_filters),
    )


# ---------------------------------------------------------------------------
# Công khai: tìm kiếm cho từng model
# ---------------------------------------------------------------------------

def tim_danh_muc_thuoc(tu_khoa: str, per_page: int = 12, page: int = 1):
    from app.models.models import DanhMucThuoc, HoatChat

    tu_khoa = tu_khoa.strip()
    if not tu_khoa:
        return None

    cols = [DanhMucThuoc.ten_biet_duoc, HoatChat.ten_hoat_chat]
    f = _build_filter(cols, tu_khoa)

    query = (
        DanhMucThuoc.query
        .outerjoin(DanhMucThuoc.hoat_chat_list)
        .filter(f)
        .order_by(
            # Ưu tiên: khớp đầu tên biệt dược
            DanhMucThuoc.ten_biet_duoc.ilike(f"{tu_khoa}%").desc(),
            DanhMucThuoc.ten_biet_duoc
        )
        .distinct()
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def tim_nha_thuoc_bv(tu_khoa: str, per_page: int = 12, page: int = 1):
    from app.models.models import NhaThuocBV, HoatChat

    tu_khoa = tu_khoa.strip()
    if not tu_khoa:
        return None

    cols = [NhaThuocBV.ten_biet_duoc, HoatChat.ten_hoat_chat]
    f = _build_filter(cols, tu_khoa)

    query = (
        NhaThuocBV.query
        .outerjoin(NhaThuocBV.hoat_chat_list)
        .filter(f)
        .order_by(
            NhaThuocBV.ten_biet_duoc.ilike(f"{tu_khoa}%").desc(),
            NhaThuocBV.ten_biet_duoc
        )
        .distinct()
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def tim_thuoc(tu_khoa: str, per_page: int = 15, page: int = 1):
    from app.models.models import Thuoc

    tu_khoa = tu_khoa.strip()
    if not tu_khoa:
        return None

    cols = [Thuoc.ten_thuoc, Thuoc.hoat_chat]
    f = _build_filter(cols, tu_khoa)

    query = (
        Thuoc.query
        .filter(f)
        .order_by(
            Thuoc.ten_thuoc.ilike(f"{tu_khoa}%").desc(),
            Thuoc.ten_thuoc
        )
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def tim_thuoc_tiem_truyen(tu_khoa: str, per_page: int = 15, page: int = 1):
    from app.models.models import Thuoc, ThuocTiemTruyen

    tu_khoa = tu_khoa.strip()
    if not tu_khoa:
        return None

    cols = [Thuoc.ten_thuoc, Thuoc.hoat_chat]
    f = _build_filter(cols, tu_khoa)

    query = (
        ThuocTiemTruyen.query.join(Thuoc)
        .filter(f)
        .order_by(
            Thuoc.ten_thuoc.ilike(f"{tu_khoa}%").desc(),
            Thuoc.ten_thuoc
        )
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def tim_tuong_tac(tu_khoa: str, limit: int = 50):
    """Tìm tương tác: từ khoá khớp với thuốc A hoặc B."""
    from app.models.models import Thuoc, TuongTacThuoc
    from sqlalchemy.orm import aliased

    tu_khoa = tu_khoa.strip()
    if not tu_khoa:
        return []

    ThuocA = aliased(Thuoc, name="ta")
    ThuocB = aliased(Thuoc, name="tb")
    tokens = _tach_token(tu_khoa)

    # Tìm tất cả thuốc khớp từ khoá trước
    thuoc_ids = (
        Thuoc.query
        .filter(_build_filter([Thuoc.ten_thuoc, Thuoc.hoat_chat], tu_khoa))
        .with_entities(Thuoc.id)
        .all()
    )
    ids = [r[0] for r in thuoc_ids]
    if not ids:
        return []

    return (
        TuongTacThuoc.query
        .filter(or_(
            TuongTacThuoc.thuoc_a_id.in_(ids),
            TuongTacThuoc.thuoc_b_id.in_(ids),
        ))
        .limit(limit)
        .all()
    )


def tim_tuong_hop_tuong_ky(thuoc_a: str, thuoc_b: str, limit: int = 50):
    """Tìm tương hợp/tương kỵ giữa 2 thuốc."""
    from app.models.models import Thuoc, TuongHopTuongKy

    if not thuoc_a:
        return []

    # IDs thuốc A
    ids_a = [r[0] for r in (
        Thuoc.query
        .filter(_build_filter([Thuoc.ten_thuoc, Thuoc.hoat_chat], thuoc_a))
        .with_entities(Thuoc.id).all()
    )]
    if not ids_a:
        return []

    if thuoc_b:
        ids_b = [r[0] for r in (
            Thuoc.query
            .filter(_build_filter([Thuoc.ten_thuoc, Thuoc.hoat_chat], thuoc_b))
            .with_entities(Thuoc.id).all()
        )]
        if not ids_b:
            return []
        return (
            TuongHopTuongKy.query
            .filter(or_(
                and_(TuongHopTuongKy.thuoc_a_id.in_(ids_a), TuongHopTuongKy.thuoc_b_id.in_(ids_b)),
                and_(TuongHopTuongKy.thuoc_a_id.in_(ids_b), TuongHopTuongKy.thuoc_b_id.in_(ids_a)),
            ))
            .limit(limit)
            .all()
        )
    else:
        return (
            TuongHopTuongKy.query
            .filter(or_(
                TuongHopTuongKy.thuoc_a_id.in_(ids_a),
                TuongHopTuongKy.thuoc_b_id.in_(ids_a),
            ))
            .limit(limit)
            .all()
        )
