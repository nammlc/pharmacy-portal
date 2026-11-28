"""
Nhập hàng loạt TƯƠNG TÁC THUỐC (cặp HOẠT CHẤT) từ file Excel / CSV.

File này chỉ chứa logic THUẦN (không đụng CSDL, không import Flask/SQLAlchemy) nên kiểm thử
được độc lập. Phần ghi CSDL nằm ở app/utils/tuong_tac_hc.py.

Luồng:  doc_file_tuong_tac()  ->  phan_tich_file()  ->  lap_ke_hoach()  ->  (ghi CSDL)

CHỐNG TRÙNG - các trường hợp được xử lý ở lap_ke_hoach():
  1. Cặp (A,B) và (B,A) là MỘT cặp (so khớp theo thứ tự đã sắp xếp).
  2. Cùng một cặp xuất hiện nhiều lần TRONG FILE:
       - nội dung y hệt nhau  -> tự gộp, chỉ giữ dòng đầu;
       - nội dung khác nhau   -> "xung đột": người nhập chọn dòng dùng (mặc định dòng đầu).
  3. Cặp đã CÓ trong CSDL -> bỏ qua (mặc định) hoặc ghi đè (người nhập chọn).
  4. Tên khác nhau nhưng thực chất là một hoạt chất (khác hoa/thường, dấu, khoảng trắng, hoặc được
     người nhập "ghép") -> so trùng theo hoạt chất ĐÃ GHÉP, không theo chữ gốc.
  5. Hai hoạt chất trở thành một sau khi ghép -> báo lỗi, không tạo cặp tự tương tác.
"""
from __future__ import annotations

import csv
import difflib
import html
import io
import re
import unicodedata
from dataclasses import dataclass, field
from itertools import chain, islice

TOI_DA_DONG = 5000

# Giá trị lưu trong CSDL (enum muc_do_enum) -> nhãn hiển thị
NHAN_MUC_DO = {
    "nhe": "Nhẹ",
    "trung_binh": "Trung bình",
    "nang": "Nghiêm trọng",
    "chong_chi_dinh": "Chống chỉ định",
}
# Chữ trong file (đã bỏ dấu, chữ thường) -> giá trị lưu
_MUC_DO_TU_FILE = {
    "chong chi dinh": "chong_chi_dinh",
    "nghiem trong": "nang",
    "nang": "nang",
    "vua phai": "trung_binh",
    "trung binh": "trung_binh",
    "nhe": "nhe",
}

# Tên cột (đã chuẩn hoá) -> trường. Chấp nhận vài cách gọi để file của người dùng nhập được nguyên trạng.
_TIEU_DE = {
    "hoat_chat_1": "ten_a", "hoat_chat_a": "ten_a", "hoat_chat_thu_nhat": "ten_a", "hoat_chat": "ten_a",
    "hoat_chat_2": "ten_b", "hoat_chat_b": "ten_b", "hoat_chat_thu_hai": "ten_b",
    "muc_do": "muc_do", "muc_do_tuong_tac": "muc_do",
    "co_che": "co_che",
    "hau_qua": "hau_qua", "hau_qua_lam_sang": "hau_qua",
    "xu_tri": "xu_tri", "huong_xu_tri": "xu_tri", "xu_ly": "xu_tri",
    "nguon": "nguon", "nguon_tham_khao": "nguon",
}
_BAT_BUOC = ("ten_a", "ten_b", "muc_do")
_TEN_TIEU_DE_DEP = {"ten_a": "Hoạt chất 1", "ten_b": "Hoạt chất 2", "muc_do": "Mức độ"}

# Trạng thái hiển thị của từng dòng
OK = "ok"                      # sẽ được xử lý (tạo mới / cập nhật / bỏ vì đã có - xem DongKetQua.hanh_dong)
TRUNG_GIONG = "trung_giong"    # trùng y hệt dòng khác trong file -> gộp
LOAI_XUNG_DOT = "loai_xung_dot"  # cùng cặp nhưng khác nội dung, không được chọn
THIEU_MUC_DO = "thieu_muc_do"  # chưa có mức độ hợp lệ -> cần chọn (mặc định bỏ qua)
LOI = "loi"
BO_QUA_TEN = "bo_qua_ten"      # người nhập chọn "bỏ" một trong hai hoạt chất

CHE_DO_BO_QUA = "bo_qua"
CHE_DO_GHI_DE = "ghi_de"


# ---------------------------------------------------------------------------
# Chuẩn hoá chữ
# ---------------------------------------------------------------------------
def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.replace("đ", "d")


def chuan_hoa_ten_cot(ten) -> str:
    return re.sub(r"[^a-z0-9]+", "_", bo_dau(str(ten or "").strip())).strip("_")


def lam_sach_ten(ten) -> str:
    """Giữ nguyên chữ hoa/thường, chỉ dọn khoảng trắng thừa (kể cả khoảng trắng đặc biệt)."""
    s = unicodedata.normalize("NFC", str(ten or "")).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()


def khoa_ten(ten: str) -> str:
    """Khoá so khớp tên hoạt chất: không phân biệt hoa/thường, dấu, khoảng trắng thừa và khoảng trắng
    quanh + / , ; (vd 'Saquinavir/ ritonavir' == 'saquinavir/ritonavir')."""
    s = bo_dau(lam_sach_ten(ten))
    return re.sub(r"\s*([/+,;])\s*", r"\1", s)


def ly_do_ten_la(ten: str) -> list[str]:
    """Các dấu hiệu cho thấy tên có thể không phải 'một hoạt chất sạch' -> nên người nhập xem lại."""
    ly = []
    if re.search(r"[+/]", ten):
        ly.append("thuốc phối hợp / nhiều hoạt chất")
    if re.search(r"[()]", ten):
        ly.append("có ghi chú trong ngoặc")
    if re.search(r"[,;]", ten):
        ly.append("có dấu phẩy / chấm phẩy")
    return ly


def van_ban_sang_html(text: str) -> str:
    """Nội dung ô Excel là dữ liệu KHÔNG tin cậy: escape HTML, mỗi dòng thành một đoạn <p>."""
    dong = [d.strip() for d in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "".join(f"<p>{html.escape(d, quote=False)}</p>" for d in dong if d)


def _chuoi_o(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = unicodedata.normalize("NFC", str(v)).replace("\u00a0", " ")
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def anh_xa_muc_do(chu: str):
    """-> (giá trị enum | None, hợp_lệ). Ô trống: (None, True) vì chỉ là 'thiếu'; chữ lạ: (None, False)."""
    if not chu.strip():
        return None, True
    return _MUC_DO_TU_FILE.get(bo_dau(chu).strip()), bo_dau(chu).strip() in _MUC_DO_TU_FILE


# ---------------------------------------------------------------------------
# Đọc file
# ---------------------------------------------------------------------------
@dataclass
class DongNhap:
    so_dong: int                 # số dòng trong file (dòng tiêu đề là 1) - dùng để báo lỗi cho người nhập
    ten_a: str = ""
    ten_b: str = ""
    muc_do_goc: str = ""         # nguyên văn trong file
    muc_do: str | None = None    # đã đổi sang giá trị lưu (chong_chi_dinh/nang/trung_binh/nhe)
    muc_do_la: bool = False      # có chữ nhưng không nhận ra
    co_che: str = ""
    hau_qua: str = ""
    xu_tri: str = ""
    nguon: str = ""

    def chu_ky_noi_dung(self, muc_do_cuoi) -> tuple:
        """Dùng để biết 2 dòng trùng cặp có 'y hệt nhau' không (bỏ qua khác biệt hoa/thường, khoảng trắng)."""
        def g(s):
            return re.sub(r"\s+", " ", s or "").strip().casefold()
        return (muc_do_cuoi, g(self.co_che), g(self.hau_qua), g(self.xu_tri), g(self.nguon))


def _anh_xa_tieu_de(cells) -> dict:
    ket = {}
    for i, c in enumerate(cells):
        truong = _TIEU_DE.get(chuan_hoa_ten_cot(c))
        if truong and truong not in ket.values():
            ket[i] = truong
    return ket


def _doc_bang_tho(file_storage):
    """Trả về iterator các hàng (list ô) của file .xlsx hoặc .csv."""
    ten = (file_storage.filename or "").lower()
    if ten.endswith(".xlsx"):
        from openpyxl import load_workbook
        wb = load_workbook(file_storage.stream, data_only=True, read_only=True)
        return wb.active.iter_rows(values_only=True)
    raw = file_storage.stream.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1258", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")
    mau = text[:2048]
    cach = ";" if mau.count(";") > mau.count(",") else ","
    return iter(csv.reader(io.StringIO(text), delimiter=cach))


def doc_file_tuong_tac(file_storage) -> list[DongNhap]:
    """Đọc file thành danh sách DongNhap. Ném ValueError (thông báo tiếng Việt) nếu file sai mẫu."""
    it = _doc_bang_tho(file_storage)
    dau = list(islice(it, 10))          # tìm dòng tiêu đề trong 10 dòng đầu (phòng khi có dòng tiêu đề lớn)
    chi_so_tieu_de, cot = None, {}
    for i, hang in enumerate(dau):
        thu = _anh_xa_tieu_de(hang)
        if all(b in thu.values() for b in _BAT_BUOC):
            chi_so_tieu_de, cot = i, thu
            break
    if chi_so_tieu_de is None:
        thay = _anh_xa_tieu_de(dau[0]) if dau else {}
        thieu = [_TEN_TIEU_DE_DEP[b] for b in _BAT_BUOC if b not in thay.values()]
        raise ValueError("Không tìm thấy dòng tiêu đề đúng mẫu. File cần có các cột: "
                         + ", ".join(_TEN_TIEU_DE_DEP.values())
                         + " (kèm Cơ chế, Hậu quả, Xử trí). Đang thiếu: " + (", ".join(thieu) or "—") + ".")

    ket = []
    for so_dong, hang in enumerate(chain(dau[chi_so_tieu_de + 1:], it), start=chi_so_tieu_de + 2):
        if hang is None:
            continue
        gia = {truong: _chuoi_o(hang[i]) if i < len(hang) else "" for i, truong in cot.items()}
        if not any(gia.values()):
            continue                     # dòng trống (Excel hay còn hàng nghìn dòng trống đã định dạng)
        d = DongNhap(so_dong=so_dong,
                     ten_a=lam_sach_ten(gia.get("ten_a")), ten_b=lam_sach_ten(gia.get("ten_b")),
                     muc_do_goc=gia.get("muc_do", ""),
                     co_che=gia.get("co_che", ""), hau_qua=gia.get("hau_qua", ""),
                     xu_tri=gia.get("xu_tri", ""), nguon=gia.get("nguon", "")[:255])
        d.muc_do, hop_le = anh_xa_muc_do(d.muc_do_goc)
        d.muc_do_la = bool(d.muc_do_goc.strip()) and not hop_le
        ket.append(d)
    if len(ket) > TOI_DA_DONG:
        raise ValueError(f"File có {len(ket)} dòng dữ liệu, vượt giới hạn {TOI_DA_DONG} dòng mỗi lần nhập. "
                         "Hãy chia nhỏ file.")
    return ket


# ---------------------------------------------------------------------------
# Tên hoạt chất trong file
# ---------------------------------------------------------------------------
@dataclass
class TenFile:
    khoa: str
    ten: str                                   # tên hiển thị: dạng xuất hiện nhiều nhất trong file
    so_dong: int = 0
    cac_dang: dict = field(default_factory=dict)  # chữ gốc -> số lần
    la: list = field(default_factory=list)        # lý do cần xem lại (ly_do_ten_la)


def gom_ten(dongs: list[DongNhap]) -> dict[str, TenFile]:
    """Gom mọi tên hoạt chất trong file theo khoá so khớp (khác hoa/thường/khoảng trắng -> một tên)."""
    ket: dict[str, TenFile] = {}
    for d in dongs:
        for ten in (d.ten_a, d.ten_b):
            if not ten:
                continue
            k = khoa_ten(ten)
            tf = ket.setdefault(k, TenFile(khoa=k, ten=ten))
            tf.so_dong += 1
            tf.cac_dang[ten] = tf.cac_dang.get(ten, 0) + 1
    for tf in ket.values():
        tf.ten = max(tf.cac_dang.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
        tf.la = ly_do_ten_la(tf.ten)
    return ket


def goi_y_ghep_diem(khoa: str, ung_vien: dict[str, str], toi_da: int = 5, nguong: float = 0.86) -> list[tuple[str, int, str]]:
    """Gợi ý hoạt chất đang có để người nhập cân nhắc ghép (không tự ghép), KÈM ĐỘ GIỐNG.
    Trả về [(tên, độ giống %, loại)] với loại = '' (gần giống) | 'hamluong' | 'phoihop' | 'ngoac' | 'khac' (4 loại sau = tên trong
    CSDL BẮT ĐẦU bằng tên trong file), sắp theo: 'bắt đầu bằng' trước, rồi độ giống giảm dần.
      - 'bắt đầu bằng': tên trong CSDL bắt đầu bằng tên trong file (CSDL thường ghi kèm hàm lượng:
        'allopurinol' -> 'Allopurinol 100mg');
      - gần giống: độ giống chữ >= nguong (bắt lỗi chính tả / lỗi ngắt dòng); chỉ so các tên cùng 3 ký tự đầu
        và độ dài gần nhau để chạy nhanh.
    Độ giống % = tỉ lệ giống nhau của hai chuỗi (đã bỏ dấu, hoa/thường) - chỉ để tham khảo."""
    tien_to, gan = [], []
    for k, ten in ung_vien.items():
        if k == khoa:
            continue
        if k.startswith(khoa + " ") or k.startswith(khoa + "/") or k.startswith(khoa + "("):
            phan_con = k[len(khoa):]
            loai = ("phoihop" if phan_con.startswith("/") else "ngoac" if phan_con.startswith("(")
                    else "hamluong" if phan_con.strip()[:1].isdigit() else "khac")
            tien_to.append((ten, round(difflib.SequenceMatcher(None, khoa, k).ratio() * 100), loai))
            continue
        if k[:3] != khoa[:3] or abs(len(k) - len(khoa)) > 6:
            continue
        r = difflib.SequenceMatcher(None, khoa, k).ratio()
        if r >= nguong:
            gan.append((ten, round(r * 100), ""))
    tien_to.sort(key=lambda x: (-x[1], x[0].lower()))
    gan.sort(key=lambda x: (-x[1], x[0].lower()))
    return (tien_to + gan)[:toi_da]


def goi_y_ghep(khoa: str, ung_vien: dict[str, str], toi_da: int = 5, nguong: float = 0.86) -> list[str]:
    """Như goi_y_ghep_diem nhưng chỉ trả về tên."""
    return [t for t, _, _ in goi_y_ghep_diem(khoa, ung_vien, toi_da, nguong)]


# ---------------------------------------------------------------------------
# Lập kế hoạch nhập (toàn bộ chống trùng nằm ở đây)
# ---------------------------------------------------------------------------
@dataclass
class DongKetQua:
    dong: DongNhap
    trang_thai: str
    ly_do: str = ""
    thuc_the_a: tuple | None = None   # ('id', 12) | ('moi', khoa)
    thuc_the_b: tuple | None = None
    muc_do_cuoi: str | None = None
    da_co: bool = False               # cặp này đã có trong CSDL
    xung_dot: bool = False            # thuộc nhóm xung đột (đây là dòng đang được dùng)
    hanh_dong: str = "bo"             # 'tao' | 'cap_nhat' | 'bo'
    ma_nhom: str = ""


@dataclass
class KeHoach:
    ket_qua: list[DongKetQua]
    nhom_xung_dot: list[dict]         # [{ma, cap:(tenA,tenB), cac_dong:[so_dong...], dang_dung: so_dong}]
    so_lieu: dict
    ten_file: dict                    # khoá -> TenFile
    hoat_chat_moi: dict               # khoá -> tên hiển thị (những hoạt chất SẼ được tạo)


def _thu_tu(e):
    return (0, e[1], "") if e[0] == "id" else (1, 0, e[1])


def khoa_cap(e1, e2):
    a, b = sorted((e1, e2), key=_thu_tu)
    return (a, b)


def ma_nhom(kc) -> str:
    return "~".join(f"{t}:{v}" for t, v in kc)


def xac_dinh_thuc_the(khoa, ten_file, hc_hien_co, quyet_dinh, _sau=0):
    """Tên (khoá) -> thực thể:  ('id', id có sẵn) | ('moi', khoá cuối) | None (bỏ) | ('khong_thay', tên đích)."""
    if khoa in hc_hien_co:
        return ("id", hc_hien_co[khoa][0])
    qd = quyet_dinh.get(khoa) or {}
    hd = qd.get("hanh_dong", "tao")
    if hd == "bo":
        return None
    if hd == "ghep":
        dich_goc = lam_sach_ten(qd.get("dich", ""))
        dich = khoa_ten(dich_goc)
        if dich and dich != khoa and _sau < 6:
            if dich in hc_hien_co:
                return ("id", hc_hien_co[dich][0])
            if dich in ten_file:
                return xac_dinh_thuc_the(dich, ten_file, hc_hien_co, quyet_dinh, _sau + 1)
        return ("khong_thay", dich_goc or "(để trống)")
    return ("moi", khoa)


def lap_ke_hoach(dongs: list[DongNhap], hc_hien_co: dict, cap_hien_co: dict,
                 quyet_dinh: dict | None = None, muc_do_chon: dict | None = None,
                 chon_xung_dot: dict | None = None, che_do_trung: str = CHE_DO_BO_QUA) -> KeHoach:
    """
    hc_hien_co   : khoá_tên -> (id, tên)           hoạt chất ĐÃ có trong CSDL
    cap_hien_co  : (id_nhỏ, id_lớn) -> id bản ghi   các cặp ĐÃ có trong CSDL
    quyet_dinh   : khoá_tên -> {'hanh_dong': 'tao'|'ghep'|'bo', 'dich': tên}   cho tên chưa có trong CSDL
    muc_do_chon  : số_dòng -> giá trị enum | 'bo'    cho dòng thiếu/lạ mức độ
    chon_xung_dot: mã_nhóm -> số_dòng được dùng
    """
    quyet_dinh = quyet_dinh or {}
    muc_do_chon = muc_do_chon or {}
    chon_xung_dot = chon_xung_dot or {}
    ten_file = gom_ten(dongs)
    kq: list[DongKetQua] = []

    # --- 1) Từng dòng: kiểm tra, ghép tên, xác định mức độ
    ung_vien: list[DongKetQua] = []
    for d in dongs:
        if not d.ten_a or not d.ten_b:
            kq.append(DongKetQua(d, LOI, "Thiếu tên hoạt chất (cột Hoạt chất 1 hoặc 2 để trống)."))
            continue
        ea = xac_dinh_thuc_the(khoa_ten(d.ten_a), ten_file, hc_hien_co, quyet_dinh)
        eb = xac_dinh_thuc_the(khoa_ten(d.ten_b), ten_file, hc_hien_co, quyet_dinh)
        if ea is None or eb is None:
            kq.append(DongKetQua(d, BO_QUA_TEN, "Đã chọn bỏ một trong hai hoạt chất."))
            continue
        loi_dich = [e[1] for e in (ea, eb) if e[0] == "khong_thay"]
        if loi_dich:
            kq.append(DongKetQua(d, LOI, f"Không tìm thấy hoạt chất «{loi_dich[0]}» để ghép."))
            continue
        if ea == eb:
            kq.append(DongKetQua(d, LOI, "Hai hoạt chất là một (cùng tên, hoặc đã được ghép làm một)."))
            continue
        md = d.muc_do
        if md is None:
            chon = muc_do_chon.get(d.so_dong)
            if chon in NHAN_MUC_DO:
                md = chon
        if md is None:
            ly = (f"Mức độ «{d.muc_do_goc}» không nhận ra." if d.muc_do_la else "Chưa có mức độ.")
            kq.append(DongKetQua(d, THIEU_MUC_DO, ly + " Chọn mức độ để nhập, hoặc bỏ qua dòng này.",
                                 thuc_the_a=ea, thuc_the_b=eb))
            continue
        ung_vien.append(DongKetQua(d, OK, thuc_the_a=ea, thuc_the_b=eb, muc_do_cuoi=md))

    # --- 2) Gom theo CẶP (không phân biệt thứ tự A/B) để bắt trùng trong file
    nhom: dict[tuple, list[DongKetQua]] = {}
    for r in ung_vien:
        nhom.setdefault(khoa_cap(r.thuc_the_a, r.thuc_the_b), []).append(r)

    nhom_xung_dot = []
    giu: list[DongKetQua] = []
    for kc, ds in nhom.items():
        ma = ma_nhom(kc)
        if len(ds) == 1:
            ds[0].ma_nhom = ma
            giu.append(ds[0])
            continue
        chu_ky = {r.dong.chu_ky_noi_dung(r.muc_do_cuoi) for r in ds}
        if len(chu_ky) == 1:                                   # y hệt nhau -> tự gộp
            chinh = ds[0]
            chinh.ma_nhom = ma
            giu.append(chinh)
            for r in ds[1:]:
                r.trang_thai, r.ma_nhom = TRUNG_GIONG, ma
                r.ly_do = f"Trùng y hệt dòng {chinh.dong.so_dong} — đã gộp."
                kq.append(r)
            continue
        dang_dung = chon_xung_dot.get(ma)                      # khác nội dung -> xung đột, người nhập chọn
        chinh = next((r for r in ds if r.dong.so_dong == dang_dung), ds[0])
        chinh.xung_dot, chinh.ma_nhom = True, ma
        giu.append(chinh)
        for r in ds:
            if r is not chinh:
                r.trang_thai, r.ma_nhom = LOAI_XUNG_DOT, ma
                r.ly_do = f"Cùng cặp với dòng {chinh.dong.so_dong} nhưng nội dung khác — không dùng."
                kq.append(r)
        nhom_xung_dot.append({"ma": ma, "cac_dong": [r.dong.so_dong for r in ds],
                              "dang_dung": chinh.dong.so_dong,
                              "cap": (chinh.dong.ten_a, chinh.dong.ten_b)})

    # --- 3) So với CSDL: cặp đã có -> bỏ qua / ghi đè
    hoat_chat_moi: dict[str, str] = {}
    for r in giu:
        if r.thuc_the_a[0] == "id" and r.thuc_the_b[0] == "id":
            a, b = sorted((r.thuc_the_a[1], r.thuc_the_b[1]))
            if (a, b) in cap_hien_co:
                r.da_co = True
                r.hanh_dong = "cap_nhat" if che_do_trung == CHE_DO_GHI_DE else "bo"
                r.ly_do = ("Cặp đã có trong hệ thống — sẽ ghi đè bằng nội dung trong file."
                           if r.hanh_dong == "cap_nhat" else "Cặp đã có trong hệ thống — bỏ qua.")
                kq.append(r)
                continue
        r.hanh_dong = "tao"
        for e in (r.thuc_the_a, r.thuc_the_b):
            if e[0] == "moi":
                hoat_chat_moi[e[1]] = ten_file[e[1]].ten if e[1] in ten_file else e[1]
        kq.append(r)

    kq.sort(key=lambda r: r.dong.so_dong)
    dem = lambda tt: sum(1 for r in kq if r.trang_thai == tt)
    so_lieu = {
        "tong_dong": len(dongs),
        "tao": sum(1 for r in kq if r.trang_thai == OK and r.hanh_dong == "tao"),
        "cap_nhat": sum(1 for r in kq if r.trang_thai == OK and r.hanh_dong == "cap_nhat"),
        "da_co_bo_qua": sum(1 for r in kq if r.trang_thai == OK and r.da_co and r.hanh_dong == "bo"),
        "trung_giong": dem(TRUNG_GIONG),
        "nhom_xung_dot": len(nhom_xung_dot),
        "loai_xung_dot": dem(LOAI_XUNG_DOT),
        "thieu_muc_do": dem(THIEU_MUC_DO),
        "loi": dem(LOI),
        "bo_qua_ten": dem(BO_QUA_TEN),
        "hoat_chat_moi": len(hoat_chat_moi),
    }
    return KeHoach(ket_qua=kq, nhom_xung_dot=nhom_xung_dot, so_lieu=so_lieu,
                   ten_file=ten_file, hoat_chat_moi=hoat_chat_moi)
