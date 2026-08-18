"""
Parse các file raw trong scrape/raw/*.txt thành list dict thuốc.
Mỗi file tương ứng 1 nhóm thuốc, tên file dạng NN_slug_nhom.txt
Mỗi thuốc trong file phân cách bằng dòng ===DRUG_END===
"""
import re
import os
import json

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
OUT_FILE = os.path.join(os.path.dirname(__file__), "parsed_drugs.json")


def parse_file(filepath, nhom_slug):
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # Dòng tiêu đề nhóm (dòng đầu bắt đầu bằng #)
    header_match = re.match(r"#\s*(.+)", content.strip())
    ten_nhom = header_match.group(1).strip() if header_match else nhom_slug

    blocks = content.split("===DRUG_END===")
    drugs = []
    for block in blocks:
        block = block.strip()
        if not block or "Tên biệt dược" not in block:
            continue

        def grab(pattern, text, flags=re.DOTALL):
            m = re.search(pattern, text, flags)
            return m.group(1).strip() if m else ""

        ten_thuoc = grab(r"Tên biệt dược\s*:\s*(.+)", block, re.MULTILINE)
        hoat_chat = grab(r"Tên hoạt chất:\s*(.+)", block, re.MULTILINE)
        thanh_phan = grab(r"Thành phần:\s*(.+?)(?=\n4-Dạng bào chế)", block)
        dang_bao_che = grab(r"Dạng bào chế:\s*(.+?)(?=\n5- Chỉ định)", block)
        chi_dinh = grab(r"Chỉ định:\s*(.+?)(?=\n6-Cách dùng)", block)
        lieu_dung = grab(r"Cách dùng, liều dùng:\s*(.+?)(?=\n7-Chống chỉ định)", block)
        chong_chi_dinh = grab(r"Chống chỉ định:\s*(.+?)(?=\nLink tham khảo)", block)
        link_tk = grab(r"Link tham khảo chi tiết thuốc:\s*(.*)", block, re.MULTILINE)
        img = grab(r"IMG:\s*(.+)", block, re.MULTILINE)

        if not ten_thuoc:
            continue

        drugs.append({
            "ten_thuoc": ten_thuoc,
            "hoat_chat": hoat_chat,
            "thanh_phan": thanh_phan.replace("\n", " ").strip(),
            "dang_bao_che": dang_bao_che.replace("\n", " ").strip(),
            "chi_dinh": chi_dinh.replace("\n", " ").strip(),
            "lieu_dung": lieu_dung.replace("\n", " ").strip(),
            "chong_chi_dinh": chong_chi_dinh.replace("\n", " ").strip(),
            "link_tham_khao": link_tk.strip(),
            "img_url": img.strip(),
            "nhom_slug": nhom_slug,
            "ten_nhom": ten_nhom,
        })

    return drugs


def main():
    all_drugs = []
    files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".txt"))
    for fname in files:
        nhom_slug = fname.replace(".txt", "")
        filepath = os.path.join(RAW_DIR, fname)
        drugs = parse_file(filepath, nhom_slug)
        all_drugs.extend(drugs)
        print(f"{fname}: {len(drugs)} thuốc")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_drugs, f, ensure_ascii=False, indent=2)

    print(f"\nTổng cộng: {len(all_drugs)} thuốc -> {OUT_FILE}")


if __name__ == "__main__":
    main()
