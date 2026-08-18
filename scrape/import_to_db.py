"""
Nạp dữ liệu đã parse (parsed_drugs.json) vào database của pharmacy_portal.
Chạy từ trong thư mục pharmacy_portal: python ../scrape/import_to_db.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pharmacy_portal"))

from app import create_app, db
from app.models.models import NhomThuoc, Thuoc, ThongTinThuoc

PARSED_FILE = os.path.join(os.path.dirname(__file__), "parsed_drugs.json")


def slugify(text):
    return text.strip().lower().replace(" ", "-")


def main():
    with open(PARSED_FILE, encoding="utf-8") as f:
        drugs = json.load(f)

    app = create_app()
    with app.app_context():
        db.create_all()
        nhom_cache = {}
        so_thuoc_moi = 0
        so_thuoc_trung = 0

        for d in drugs:
            slug = d["nhom_slug"]
            if slug not in nhom_cache:
                nhom = NhomThuoc.query.filter_by(slug=slug, loai="danh_muc_thuoc").first()
                if not nhom:
                    nhom = NhomThuoc(ten_nhom=d["ten_nhom"], slug=slug, loai="danh_muc_thuoc")
                    db.session.add(nhom)
                    db.session.flush()
                nhom_cache[slug] = nhom
            nhom = nhom_cache[slug]

            # Tránh trùng nếu chạy import nhiều lần
            existing = Thuoc.query.filter_by(ten_thuoc=d["ten_thuoc"], nhom_thuoc_id=nhom.id).first()
            if existing:
                so_thuoc_trung += 1
                continue

            thuoc = Thuoc(
                ten_thuoc=d["ten_thuoc"],
                hoat_chat=d["hoat_chat"],
                thanh_phan=d["thanh_phan"],
                dang_bao_che=d["dang_bao_che"],
                nhom_thuoc_id=nhom.id,
                link_tham_khao=d["link_tham_khao"],
                hinh_anh=d["img_url"],
            )
            db.session.add(thuoc)
            db.session.flush()

            ttt = ThongTinThuoc(
                thuoc_id=thuoc.id,
                chi_dinh=d["chi_dinh"],
                chong_chi_dinh=d["chong_chi_dinh"],
                lieu_dung_nguoi_lon=d["lieu_dung"],
                nguon_tham_khao=d["link_tham_khao"],
            )
            db.session.add(ttt)
            so_thuoc_moi += 1

        db.session.commit()
        print(f"Đã thêm {so_thuoc_moi} thuốc mới, bỏ qua {so_thuoc_trung} thuốc trùng.")
        print(f"Tổng số nhóm thuốc: {NhomThuoc.query.count()}")
        print(f"Tổng số thuốc trong database: {Thuoc.query.count()}")


if __name__ == "__main__":
    main()
