from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from sqlalchemy.orm import joinedload

from app import db
from app.models.models import TuongTacHoatChat
from app.utils.tim_kiem import MUC_DO_TUONG_TAC, goi_y_hoat_chat, tim_tuong_tac

bp = Blueprint("ttt", __name__, url_prefix="/tra-cuu-tuong-tac-thuoc")

SO_TUONG_TAC_MOI_TRANG = 10


def _doc_bo_loc(nguon):
    """Đọc ?q= (hoạt chất 1), ?q2= (hoạt chất 2), ?muc_do= từ URL, đã làm sạch.
    Chỉ nhập ô 2 thì coi ô 2 là hoạt chất cần tìm."""
    q = nguon.get("q", "").strip()[:120]
    q2 = nguon.get("q2", "").strip()[:120]
    muc_do = nguon.get("muc_do", "").strip()
    if not q and q2:
        q, q2 = q2, ""
    if muc_do not in MUC_DO_TUONG_TAC:
        muc_do = ""
    return q, q2, muc_do


@bp.route("/")
def index():
    tu_khoa, tu_khoa2, muc_do = _doc_bo_loc(request.args)
    trang = request.args.get("page", 1, type=int) or 1

    # Form GET luôn gửi cả ô trống (?q=...&q2=): chuyển về URL gọn, không đuôi rỗng
    if any(k in request.args and not request.args[k].strip() for k in ("q", "q2", "muc_do")):
        gon = {k: v for k, v in (("q", tu_khoa), ("q2", tu_khoa2), ("muc_do", muc_do)) if v}
        return redirect(url_for("ttt.index", **gon))

    kq = (tim_tuong_tac(tu_khoa, tu_khoa2, muc_do, page=trang, per_page=SO_TUONG_TAC_MOI_TRANG)
          if tu_khoa else None)

    # Tham số URL cần giữ khi chuyển trang / mở chi tiết / bấm chip (bỏ giá trị rỗng cho URL gọn)
    tham_so_goc = {k: v for k, v in (("q", tu_khoa), ("q2", tu_khoa2)) if v}
    tham_so = dict(tham_so_goc, **({"muc_do": muc_do} if muc_do else {}))
    return render_template(
        "tra_cuu_tuong_tac_thuoc.html",
        kq=kq, tu_khoa=tu_khoa, tu_khoa2=tu_khoa2, muc_do=muc_do,
        tham_so_goc=tham_so_goc, tham_so=tham_so,
        tham_so_trang=dict(tham_so, _anchor="ket-qua"),
    )


@bp.route("/<int:tt_id>")
def chi_tiet(tt_id):
    """Chi tiết tương tác giữa 2 hoạt chất: cơ chế, hậu quả lâm sàng, xử trí, nguồn."""
    tt = db.get_or_404(TuongTacHoatChat, tt_id, options=[joinedload(TuongTacHoatChat.hoat_chat_a),
                                                         joinedload(TuongTacHoatChat.hoat_chat_b)])
    q, q2, muc_do = _doc_bo_loc(request.args)
    tham_so_quay_lai = {k: v for k, v in (("q", q), ("q2", q2), ("muc_do", muc_do),
                                          ("page", request.args.get("page", type=int))) if v}
    return render_template("chi_tiet_tuong_tac_thuoc.html", tt=tt, tham_so_quay_lai=tham_so_quay_lai)


@bp.route("/goi-y")
def goi_y():
    """Gợi ý dropdown khi gõ hoạt chất (dùng cho cả hai ô tìm kiếm)."""
    return jsonify(goi_y_hoat_chat(request.args.get("q", "")))
