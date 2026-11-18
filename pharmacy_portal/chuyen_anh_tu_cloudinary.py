#!/usr/bin/env python3
"""Chuyển TOÀN BỘ ảnh / tệp đính kèm từ Cloudinary về máy chủ, an toàn và kiểm chứng được.

Quét MỌI cột chữ của MỌI bảng (cột ảnh, ảnh hero, ảnh trong nội dung bài viết HTML, tệp đính kèm...), nên không sót ảnh
chèn trong nội dung. Mỗi ảnh được tải bản GỐC (không nén lại), kiểm tra đúng là ảnh / đúng loại tệp rồi mới ghi nhận.
Database chỉ bị sửa khi 100% ảnh đã tải xong (trừ khi chủ động dùng --bo-qua-loi), và luôn có file sao lưu để hoàn tác.

Các bước (chạy trong thư mục dự án, cùng môi trường Python với web):
    python chuyen_anh_tu_cloudinary.py kiem-ke            # chỉ ĐẾM, không đổi gì
    python chuyen_anh_tu_cloudinary.py tai-ve             # tải về UPLOAD_DIR (chạy lại bao nhiêu lần cũng được)
    python chuyen_anh_tu_cloudinary.py ap-dung            # tải nốt ảnh mới phát sinh + ghi đường dẫn mới vào database
    python chuyen_anh_tu_cloudinary.py kiem-tra [--goi-thu https://ten-mien-cua-ban]
    python chuyen_anh_tu_cloudinary.py hoan-tac chuyen_anh/sao_luu_db_XXXX.json     # nếu cần quay lại

Xem HUONG_DAN_CHUYEN_ANH.md để biết thứ tự đầy đủ (đặc biệt: sao lưu database TRƯỚC khi ap-dung).
"""
import argparse
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import unquote

AQUI = os.path.dirname(os.path.abspath(__file__))
BAN_DO = "anh_ban_do.json"
BANG_BO_QUA_MAC_DINH = ("nhat_ky",)          # nhật ký truy cập: không phải nội dung, quét tốn thời gian
MAX_BYTES = 80 * 1024 * 1024
DUOI_ANH = {"png", "jpg", "jpeg", "webp", "gif"}
DUOI_TEP = {"pdf", "doc", "docx", "xls", "xlsx", "zip"}

# --------------------------------------------------------------------------- nhận diện URL Cloudinary
RE_URL = re.compile(
    r"(?:https?:)?//res(?:-\d+)?\.cloudinary\.com/([A-Za-z0-9_-]+)/(image|raw|video)/(upload|private|authenticated)/"
    r"([^\s\"'<>()\\]+)")
RE_THUC_THE = re.compile(r"&(?:quot|amp|apos|lt|gt|#\d+|#x[0-9a-fA-F]+);")
_KHOA_BIEN_DOI = r"(?:ar|bo|co|dpr|fl|ac|dn|pg|vc|if|so|eo|du|sp|vs|[a-z])"
RE_BIEN_DOI = re.compile(rf"{_KHOA_BIEN_DOI}_[^/]+(?:,{_KHOA_BIEN_DOI}_[^/]+)*")
RE_PHIEN_BAN = re.compile(r"v\d+")
RE_URL_LOCAL = re.compile(r"(?<![\w.\-:/])/uploads/[A-Za-z0-9._\-/]+")


def _cat_duoi(khop: re.Match):
    """Tách chuỗi khớp thành (phần URL thật, phần đuôi giữ nguyên). Bỏ query ?_a=... , giữ lại thực thể HTML như &quot;."""
    s = khop.group(0)
    m = re.search(r"[?#&]", s)
    if not m:
        loi = len(s) - len(s.rstrip(".,;:!"))
        return (s[:len(s) - loi], s[len(s) - loi:]) if loi else (s, "")
    loi_chinh, duoi = s[:m.start()], s[m.start():]
    if duoi[0] in "?#":                      # query/hash của Cloudinary: bỏ, nhưng giữ thực thể HTML kế tiếp (&quot;)
        te = RE_THUC_THE.search(duoi)
        duoi = duoi[te.start():] if te else ""
    return loi_chinh, duoi


def phan_tich(url: str):
    """Trả dict {cloud, loai, public, phien_ban, goc} cho URL Cloudinary, hoặc None.
    'goc' là URL gốc chuẩn (bỏ biến đổi như c_fill,w_112 và query), dùng làm khoá."""
    m = RE_URL.search(url)
    if not m:
        return None
    cloud, loai, kieu, con_lai = m.groups()
    con_lai = re.split(r"[?#]", con_lai, 1)[0]
    seg = con_lai.split("/")
    phien_ban, i = None, None
    for k, s in enumerate(seg):
        if RE_PHIEN_BAN.fullmatch(s):
            phien_ban, i = s, k + 1
            break
    if i is None:
        i = 0
        while i < len(seg) - 1 and RE_BIEN_DOI.fullmatch(seg[i]):
            i += 1
    public = "/".join(seg[i:])
    if not public:
        return None
    goc = f"https://res.cloudinary.com/{cloud}/{loai}/{kieu}/" + (f"{phien_ban}/" if phien_ban else "") + public
    return {"cloud": cloud, "loai": loai, "public": public, "phien_ban": phien_ban, "goc": goc}


def tim_url(van_ban: str, cloud_cua_toi: str = ""):
    """Danh sách thông tin URL Cloudinary trong 1 đoạn chữ/HTML. Mỗi phần tử có thêm 'khop' (đoạn chữ gốc)."""
    ra = []
    if not isinstance(van_ban, str) or "cloudinary" not in van_ban:
        return ra
    for m in RE_URL.finditer(van_ban):
        loi_chinh, _ = _cat_duoi(m)
        tt = phan_tich(loi_chinh)
        if tt:
            tt["khop"] = loi_chinh
            tt["cua_toi"] = (not cloud_cua_toi) or tt["cloud"] == cloud_cua_toi
            ra.append(tt)
    return ra


def thay_url(van_ban: str, ban_do: dict, cloud_cua_toi: str = ""):
    """Thay mọi URL Cloudinary đã có trong ban_do bằng đường dẫn mới. Trả (chuỗi mới, số lần thay)."""
    dem = [0]

    def f(m):
        loi_chinh, duoi = _cat_duoi(m)
        tt = phan_tich(loi_chinh)
        if tt and ((not cloud_cua_toi) or tt["cloud"] == cloud_cua_toi):
            muc = ban_do.get(tt["goc"])
            if muc and muc.get("ok") and muc.get("local"):
                dem[0] += 1
                return muc["local"] + duoi
        return m.group(0)
    return RE_URL.sub(f, van_ban), dem[0]


# --------------------------------------------------------------------------- tên file & kiểm tra nội dung
def _nap_luu_tru():
    """Nạp app/utils/luu_tru_anh.py theo đường dẫn (không khởi động cả web app)."""
    duong = os.path.join(AQUI, "app", "utils", "luu_tru_anh.py")
    spec = importlib.util.spec_from_file_location("luu_tru_anh_doc_lap", duong)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dinh_dang_that(b: bytes):
    if b.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return None


def kiem_tra_noi_dung(du_lieu: bytes, duoi: str):
    """Trả (đuôi đúng, '') nếu hợp lệ, hoặc (None, lý do lỗi)."""
    if not du_lieu:
        return None, "file rỗng"
    if duoi in DUOI_ANH:
        that = dinh_dang_that(du_lieu)
        if not that:
            return None, "nội dung không phải ảnh png/jpg/gif/webp"
        try:                                           # có Pillow thì kiểm tra sâu hơn (file ảnh bị cắt cụt)
            from PIL import Image
            import io
            Image.open(io.BytesIO(du_lieu)).verify()
        except ImportError:
            pass
        except Exception:
            return None, "ảnh bị hỏng"
        return that, ""
    if duoi == "pdf" and not du_lieu.startswith(b"%PDF"):
        return None, "không phải PDF"
    if duoi in ("zip", "docx", "xlsx") and not du_lieu.startswith(b"PK"):
        return None, f"không phải {duoi}"
    return duoi, ""


def duong_dan_moi(tt: dict, da_dung: dict, lt, duoi_that: str = "") -> str:
    """Đường dẫn tương đối trong UPLOAD_DIR, giữ cấu trúc thư mục như trên Cloudinary (pharmacy/thuoc/xxx.jpg).
    duoi_that: với ẢNH, đuôi theo nội dung thật (jpeg->jpg, thiếu đuôi -> thêm). Với tệp 'raw' để trống.
    da_dung: {đường dẫn: URL gốc đã chiếm}. Trùng tên nhưng khác ảnh -> thêm mã băm ngắn để không đè nhau."""
    phan = [lt.ten_an_toan(unquote(s)) for s in tt["public"].split("/")]
    if duoi_that:
        ten = phan[-1]
        phan[-1] = (ten.rsplit(".", 1)[0] if "." in ten else ten) + "." + duoi_that
    rel = "/".join(phan)
    chu = da_dung.get(rel)
    if chu is not None and chu != tt["goc"]:
        ten, _, duoi = phan[-1].rpartition(".") if "." in phan[-1] else (phan[-1], "", "")
        h = hashlib.sha1(tt["goc"].encode()).hexdigest()[:8]
        phan[-1] = f"{ten}_{h}" + (f".{duoi}" if duoi else "")
        rel = "/".join(phan)
    return rel


# --------------------------------------------------------------------------- tải về
def tai_bytes(url: str, thu_lai: int = 3, timeout: int = 40):
    """Tải 1 URL. Trả (bytes, content_type). Ném OSError với nội dung rõ ràng nếu thất bại."""
    loi_cuoi = None
    for lan in range(thu_lai):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (chuyen-anh-cloudinary)"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                du_lieu = r.read(MAX_BYTES + 1)
                if len(du_lieu) > MAX_BYTES:
                    raise OSError("file quá lớn (> 80MB)")
                return du_lieu, (r.headers.get("Content-Type") or "").lower()
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410):          # không đáng thử lại
                raise OSError(f"HTTP {e.code}") from e
            loi_cuoi = OSError(f"HTTP {e.code}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            loi_cuoi = OSError(str(getattr(e, "reason", e)))
        time.sleep((1, 3, 7)[min(lan, 2)])
    raise loi_cuoi or OSError("không tải được")


def _luu_json(duong: str, du_lieu) -> None:
    os.makedirs(os.path.dirname(duong), exist_ok=True)
    tam = duong + ".tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(du_lieu, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tam, duong)


def _doc_ban_do(thu_muc: str) -> dict:
    d = os.path.join(thu_muc, BAN_DO)
    if os.path.isfile(d):
        with open(d, encoding="utf-8") as f:
            return json.load(f)
    return {"muc": {}}


def tai_tat_ca(danh_sach: list, thu_muc: str, lt, luong: int = 6, in_ra=print) -> dict:
    """Tải mọi URL trong danh_sach (mỗi phần tử là dict từ phan_tich) chưa có/chưa hợp lệ. Cập nhật & lưu bản đồ.
    Chạy lại được: mục đã tải xong và file còn nguyên kích thước thì bỏ qua."""
    bd = _doc_ban_do(thu_muc)
    muc = bd.setdefault("muc", {})
    goc_luu = lt.thu_muc_goc()
    da_dung = {m["local"][len(lt.TIEN_TO_URL):]: k for k, m in muc.items() if m.get("local")}

    can_tai = []
    for tt in danh_sach:
        m = muc.get(tt["goc"])
        if m and m.get("ok"):
            p = lt.duong_dan_tu_url(m["local"])
            if p is not None and p.is_file() and p.stat().st_size == m.get("bytes"):
                continue
        can_tai.append(tt)
    in_ra(f"Cần tải {len(can_tai)} / {len(danh_sach)} ảnh (còn lại đã có sẵn và còn nguyên vẹn).")

    def lam(tt):
        goc = tt["goc"]
        try:
            du_lieu, ctype = tai_bytes(goc)
            if "text/html" in ctype:
                raise OSError("máy chủ trả về trang web chứ không phải file")
            duoi_url = tt["public"].rsplit(".", 1)[1].lower() if "." in tt["public"].rsplit("/", 1)[-1] else ""
            if tt["loai"] == "raw":
                duoi = duoi_url
                if duoi not in DUOI_TEP:
                    raise OSError(f"loại tệp .{duoi or '?'} không được hỗ trợ")
            else:
                duoi = duoi_url if duoi_url in DUOI_ANH else ""
                if not duoi and duoi_url:
                    raise OSError(f"định dạng .{duoi_url} không được hỗ trợ (chỉ png/jpg/gif/webp)")
            that, ly_do = kiem_tra_noi_dung(du_lieu, duoi or "jpg")
            if not that:
                raise OSError(ly_do)
            return tt, du_lieu, (that if tt["loai"] != "raw" else duoi), ""
        except Exception as e:                                       # noqa: BLE001
            return tt, None, None, str(e)

    def ket_qua_theo_me():
        with cf.ThreadPoolExecutor(max_workers=max(1, luong)) as pool:
            for dau in range(0, len(can_tai), 40):                      # mẻ 40 file: không dồn hàng nghìn ảnh vào RAM
                yield from pool.map(lam, can_tai[dau:dau + 40])

    xong = loi = 0
    if True:
        for i, (tt, du_lieu, duoi, ly_do) in enumerate(ket_qua_theo_me(), 1):
            goc = tt["goc"]
            if du_lieu is None:
                muc[goc] = {"ok": False, "loi": ly_do, "local": "", "bytes": 0}
                loi += 1
                in_ra(f"  [LỖI] {goc}  ->  {ly_do}")
            else:
                rel = duong_dan_moi(tt, da_dung, lt, duoi if tt["loai"] != "raw" else "")
                da_dung[rel] = goc
                lt._ghi_nguyen_tu(goc_luu / rel, du_lieu)
                muc[goc] = {"ok": True, "loi": "", "local": lt.TIEN_TO_URL + rel, "bytes": len(du_lieu),
                            "sha256": hashlib.sha256(du_lieu).hexdigest()}
                xong += 1
            if i % 25 == 0:
                _luu_json(os.path.join(thu_muc, BAN_DO), bd)
                in_ra(f"  ... {i}/{len(can_tai)}")
    _luu_json(os.path.join(thu_muc, BAN_DO), bd)
    in_ra(f"Tải xong: {xong} thành công, {loi} lỗi.")
    return bd


# --------------------------------------------------------------------------- database
class KhoSQLAlchemy:
    """Truy cập database qua SQLAlchemy (dùng đúng DATABASE_URL / DB_* của web)."""

    def __init__(self, url: str, bo_qua_bang=()):
        from sqlalchemy import MetaData, create_engine
        self.engine = create_engine(url)
        self.meta = MetaData()
        self.meta.reflect(bind=self.engine)
        self.bo_qua = set(bo_qua_bang)
        self.bang_khong_khoa = []

    def quet(self, mau: str):
        """Sinh (bảng, {khoá chính}, cột, giá trị) cho mọi ô chữ có chứa `mau`."""
        from sqlalchemy import Enum, String, or_, select
        for t in self.meta.sorted_tables:
            if t.name in self.bo_qua:
                continue
            pk = list(t.primary_key.columns)
            cot = [c for c in t.columns if isinstance(c.type, String) and not isinstance(c.type, Enum)   # String gồm Text/LongText
                   and c not in pk]                                                                       # không bao giờ sửa khoá chính
            if not cot:
                continue
            if not pk:
                self.bang_khong_khoa.append(t.name)
                continue
            truy_van = select(*pk, *cot).where(or_(*[c.like(f"%{mau}%") for c in cot]))
            with self.engine.connect() as kn:
                for dong in kn.execute(truy_van).mappings():
                    khoa = {c.name: dong[c.name] for c in pk}
                    for c in cot:
                        v = dong[c.name]
                        if isinstance(v, str) and mau in v:
                            yield t.name, khoa, c.name, v

    def cap_nhat_nhieu(self, thay_doi: list):
        """Ghi tất cả trong MỘT giao dịch: lỗi ở đâu thì huỷ hết. Chỉ sửa ô còn đúng giá trị cũ (tránh đè người khác)."""
        from sqlalchemy import and_, update
        with self.engine.begin() as kn:
            for tc in thay_doi:
                t = self.meta.tables[tc["bang"]]
                dk = and_(*[t.c[k] == v for k, v in tc["khoa"].items()], t.c[tc["cot"]] == tc["cu"])
                kq = kn.execute(update(t).where(dk).values({tc["cot"]: tc["moi"]}))
                if kq.rowcount != 1:
                    raise RuntimeError(f"Ô {tc['bang']}.{tc['cot']} {tc['khoa']} đã bị đổi trong lúc chạy (rowcount={kq.rowcount}); "
                                       "đã huỷ toàn bộ, database KHÔNG bị thay đổi.")


def tao_kho(args):
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(AQUI, ".env"))
    except ImportError:
        pass
    sys.path.insert(0, AQUI)
    from config import Config
    os.environ.setdefault("UPLOAD_DIR", Config.UPLOAD_DIR)
    url = Config.SQLALCHEMY_DATABASE_URI
    from sqlalchemy.engine import make_url
    print(f"Database : {make_url(url).render_as_string(hide_password=True)}")
    print(f"Thư mục ảnh (UPLOAD_DIR): {Config.UPLOAD_DIR}")
    if not args.thu_muc:
        args.thu_muc = os.path.join(os.path.dirname(os.path.abspath(Config.UPLOAD_DIR)), "chuyen_anh")
    print(f"Thư mục làm việc        : {args.thu_muc}   (bản đồ ảnh, file sao lưu để hoàn tác)")
    print(f"Tài khoản Cloudinary    : {Config.CLOUDINARY_CLOUD_NAME or '(CHƯA ĐẶT CLOUDINARY_CLOUD_NAME -> sẽ coi MỌI URL Cloudinary là của bạn)'}")
    if Config.DB_TYPE == "sqlite" and "sqlite" in url:
        print("LƯU Ý: đang dùng SQLite. Nếu web chạy với database KHÁC thì hãy đặt đủ biến môi trường như web (DB_TYPE, DB_*, DATABASE_URL).")
    return KhoSQLAlchemy(url, args.bo_qua_bang.split(",") if args.bo_qua_bang else BANG_BO_QUA_MAC_DINH), Config


# --------------------------------------------------------------------------- các lệnh
def quet_cloudinary(kho, cloud: str):
    """Trả (các ô có URL Cloudinary, mọi URL của mình {goc: thông tin}, các URL của tài khoản khác {goc: thông tin})."""
    o, cua_toi, ngoai = [], {}, {}
    for bang, khoa, cot, gia_tri in kho.quet("cloudinary"):
        ds = tim_url(gia_tri, cloud)
        if not ds:
            continue
        o.append({"bang": bang, "khoa": khoa, "cot": cot, "gia_tri": gia_tri, "url": [t["goc"] for t in ds if t["cua_toi"]]})
        for t in ds:
            (cua_toi if t["cua_toi"] else ngoai).setdefault(t["goc"], t)
    return o, cua_toi, ngoai


def lenh_kiem_ke(args, kho, cfg):
    o, cua_toi, ngoai = quet_cloudinary(kho, cfg.CLOUDINARY_CLOUD_NAME)
    theo_cot, dem_loai = {}, {}
    for x in o:
        k = f"{x['bang']}.{x['cot']}"
        a = theo_cot.setdefault(k, {"o": 0, "url": 0})
        a["o"] += 1
        a["url"] += len(x["url"])
    for t in cua_toi.values():
        dem_loai[t["loai"]] = dem_loai.get(t["loai"], 0) + 1
    print("\n=== KIỂM KÊ (chưa thay đổi gì) ===")
    if not theo_cot:
        print("Không thấy URL Cloudinary nào trong database.")
    for k, a in sorted(theo_cot.items()):
        print(f"  {k:<45} {a['o']:>5} ô   {a['url']:>5} đường dẫn")
    print(f"\nTổng cộng {len(cua_toi)} ảnh/tệp KHÁC NHAU thuộc tài khoản của bạn  ({', '.join(f'{v} {k}' for k, v in dem_loai.items()) or '0'})")
    if ngoai:
        print(f"CẢNH BÁO: {len(ngoai)} URL thuộc tài khoản Cloudinary KHÁC (không phải '{cfg.CLOUDINARY_CLOUD_NAME}') -> sẽ KHÔNG được chuyển.")
    if getattr(kho, "bang_khong_khoa", None):
        print(f"CẢNH BÁO: bảng không có khoá chính, bị bỏ qua: {', '.join(kho.bang_khong_khoa)}")
    _luu_json(os.path.join(args.thu_muc, "kiem_ke.json"), {
        "thoi_diem": datetime.now().isoformat(timespec="seconds"),
        "o": [{k: v for k, v in x.items() if k != "gia_tri"} for x in o], "url": sorted(cua_toi), "ngoai": sorted(ngoai)})
    print(f"Chi tiết: {os.path.join(args.thu_muc, 'kiem_ke.json')}")
    return 0


def lenh_tai_ve(args, kho, cfg):
    lt = _nap_luu_tru()
    _, cua_toi, _ = quet_cloudinary(kho, cfg.CLOUDINARY_CLOUD_NAME)
    bd = tai_tat_ca(list(cua_toi.values()), args.thu_muc, lt, args.luong)
    loi = [(k, m["loi"]) for k, m in bd["muc"].items() if k in cua_toi and not m.get("ok")]
    if loi:
        print(f"\n{len(loi)} ảnh CHƯA tải được (xem ở trên). Chạy lại lệnh này để thử lại; ảnh đã tải sẽ không tải lại.")
        return 2
    print("\nTất cả ảnh đã nằm trong thư mục UPLOAD_DIR. Database CHƯA bị thay đổi.")
    return 0


def lenh_ap_dung(args, kho, cfg):
    lt = _nap_luu_tru()
    o, cua_toi, _ = quet_cloudinary(kho, cfg.CLOUDINARY_CLOUD_NAME)
    if not o:
        print("Không còn URL Cloudinary nào để chuyển.")
        return 0
    bd = tai_tat_ca(list(cua_toi.values()), args.thu_muc, lt, args.luong)
    muc = bd["muc"]
    loi = [k for k in cua_toi if not muc.get(k, {}).get("ok")]
    if loi and not args.bo_qua_loi:
        print(f"\nDỪNG: còn {len(loi)} ảnh chưa tải được nên KHÔNG sửa database. Xử lý lỗi rồi chạy lại "
              "(hoặc dùng --bo-qua-loi để chỉ chuyển ảnh đã tải được, ảnh lỗi giữ nguyên trên Cloudinary).")
        return 2
    for k, m in muc.items():
        if m.get("ok"):
            p = lt.duong_dan_tu_url(m["local"])
            if p is None or not p.is_file() or p.stat().st_size != m["bytes"]:
                print(f"DỪNG: file {m['local']} không còn nguyên vẹn trong UPLOAD_DIR.")
                return 2
    thay_doi, tong = [], 0
    for x in o:
        moi, n = thay_url(x["gia_tri"], muc, cfg.CLOUDINARY_CLOUD_NAME)
        if n and moi != x["gia_tri"]:
            thay_doi.append({"bang": x["bang"], "khoa": x["khoa"], "cot": x["cot"], "cu": x["gia_tri"], "moi": moi})
            tong += n
    print(f"\nSẽ sửa {len(thay_doi)} ô dữ liệu, thay {tong} đường dẫn Cloudinary bằng /uploads/...")
    if loi:
        print(f"(Còn {len(loi)} ảnh lỗi giữ nguyên trên Cloudinary.)")
    if not thay_doi:
        return 0
    if not args.yes:
        if input("Đã sao lưu database chưa? Gõ  DONG Y  để tiếp tục: ").strip() != "DONG Y":
            print("Đã huỷ, không có gì thay đổi.")
            return 1
    sao_luu = os.path.join(args.thu_muc, f"sao_luu_db_{datetime.now():%Y%m%d_%H%M%S}.json")
    _luu_json(sao_luu, {"thoi_diem": datetime.now().isoformat(timespec="seconds"), "thay_doi": thay_doi})
    print(f"Đã ghi file sao lưu giá trị cũ: {sao_luu}")
    kho.cap_nhat_nhieu(thay_doi)
    print("XONG: đã cập nhật database trong 1 giao dịch.")
    print(f"Hoàn tác (nếu cần):  python chuyen_anh_tu_cloudinary.py hoan-tac {sao_luu}")
    print("Bước tiếp: chạy  kiem-tra  rồi xem thử website.")
    return 0


def lenh_kiem_tra(args, kho, cfg):
    lt = _nap_luu_tru()
    con_cloud = sum(len(tim_url(v, cfg.CLOUDINARY_CLOUD_NAME)) for _, _, _, v in kho.quet("cloudinary"))
    thieu, da_co, tat_ca = [], 0, set()
    for bang, khoa, cot, v in kho.quet("/uploads/"):
        for m in RE_URL_LOCAL.finditer(v):
            tat_ca.add(m.group(0))
            p = lt.duong_dan_tu_url(m.group(0))
            if p is not None and p.is_file() and p.stat().st_size > 0:
                da_co += 1
            else:
                thieu.append(f"{bang}.{cot} {khoa}: {m.group(0)}")
    print("\n=== KIỂM TRA SAU KHI CHUYỂN ===")
    print(f"Đường dẫn Cloudinary còn lại trong database : {con_cloud}")
    print(f"Đường dẫn /uploads/ trong database          : {da_co + len(thieu)} ({len(tat_ca)} file khác nhau)")
    print(f"  - có file trong UPLOAD_DIR                 : {da_co}")
    print(f"  - THIẾU file                               : {len(thieu)}")
    for t in thieu[:50]:
        print("      ", t)
    loi_http = 0
    if args.goi_thu:
        goc = args.goi_thu.rstrip("/")

        def goi(u):
            try:
                du_lieu, ct = tai_bytes(goc + u, thu_lai=2, timeout=30)
                ok = len(du_lieu) > 0 and ("image/" in ct or "application/" in ct)
                return u, ok, ct
            except OSError as e:
                return u, False, str(e)
        with cf.ThreadPoolExecutor(max_workers=args.luong) as pool:
            for u, ok, ct in pool.map(goi, sorted(tat_ca)):
                if not ok:
                    loi_http += 1
                    print(f"  [HTTP LỖI] {goc}{u} -> {ct}")
        print(f"Gọi thử qua web ({goc}): {len(tat_ca) - loi_http}/{len(tat_ca)} đường dẫn trả về đúng ảnh/tệp.")
    ok = not thieu and not loi_http
    print("\nKẾT QUẢ:", "ĐẠT" if ok else "CHƯA ĐẠT - xem các dòng lỗi ở trên")
    if ok and con_cloud:
        print(f"(Còn {con_cloud} đường dẫn Cloudinary: ảnh lỗi hoặc thuộc tài khoản khác. Chạy kiem-ke để xem.)")
    return 0 if ok else 1


def lenh_hoan_tac(args, kho, cfg):
    with open(args.tep, encoding="utf-8") as f:
        sao_luu = json.load(f)["thay_doi"]
    thay_doi = [{"bang": x["bang"], "khoa": x["khoa"], "cot": x["cot"], "cu": x["moi"], "moi": x["cu"]} for x in sao_luu]
    print(f"Sẽ khôi phục {len(thay_doi)} ô dữ liệu về giá trị Cloudinary cũ (chỉ ô chưa bị sửa tay sau đó).")
    if not args.yes and input("Gõ  DONG Y  để tiếp tục: ").strip() != "DONG Y":
        print("Đã huỷ.")
        return 1
    kho.cap_nhat_nhieu(thay_doi)
    print("Đã hoàn tác. Lưu ý: ảnh mới upload SAU lúc chuyển (nếu có) vẫn ở /uploads/ và không bị ảnh hưởng.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Chuyển ảnh từ Cloudinary về máy chủ.")
    ap.add_argument("--thu-muc", default="", help="nơi lưu bản đồ/báo cáo/sao lưu (mặc định: thư mục 'chuyen_anh' NGAY CẠNH UPLOAD_DIR, "
                                                 "để cùng nằm trên ổ lưu trữ cố định và không mất khi deploy lại)")
    ap.add_argument("--bo-qua-bang", default="", help="danh sách bảng bỏ qua, cách nhau bởi dấu phẩy (mặc định: nhat_ky)")
    ap.add_argument("--luong", type=int, default=6, help="số luồng tải song song (mặc định 6)")
    sub = ap.add_subparsers(dest="lenh", required=True)
    sub.add_parser("kiem-ke", help="đếm ảnh, không đổi gì")
    sub.add_parser("tai-ve", help="tải ảnh về UPLOAD_DIR, không đổi database")
    p = sub.add_parser("ap-dung", help="tải nốt + sửa database")
    p.add_argument("--yes", action="store_true", help="không hỏi xác nhận")
    p.add_argument("--bo-qua-loi", action="store_true", help="vẫn sửa các ảnh đã tải được dù còn ảnh lỗi")
    p = sub.add_parser("kiem-tra", help="kiểm tra sau khi chuyển")
    p.add_argument("--goi-thu", default="", help="địa chỉ web (https://...) để gọi thử từng ảnh qua mạng")
    p = sub.add_parser("hoan-tac", help="khôi phục từ file sao lưu")
    p.add_argument("tep")
    p.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)
    kho, cfg = tao_kho(args)
    return {"kiem-ke": lenh_kiem_ke, "tai-ve": lenh_tai_ve, "ap-dung": lenh_ap_dung,
            "kiem-tra": lenh_kiem_tra, "hoan-tac": lenh_hoan_tac}[args.lenh](args, kho, cfg)


if __name__ == "__main__":
    sys.exit(main())
