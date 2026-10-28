"""robots.txt và sitemap.xml để công cụ tìm kiếm (Google, Bing...) lập chỉ mục đúng các trang công khai."""
from flask import Response, current_app, request

from app.models.models import BaiViet, DanhMucThuoc, NhaThuocBV


def _goc_trang():
    """Địa chỉ gốc ưu tiên tên miền chính (CANONICAL_HOST) để tránh trùng lặp với onrender.com."""
    host = current_app.config.get("CANONICAL_HOST")
    if host:
        return f"https://{host}"
    return request.host_url.rstrip("/")


def dang_ky_seo(app):
    @app.route("/robots.txt")
    def robots_txt():
        goc = _goc_trang()
        noi_dung = "\n".join([
            "User-agent: *",
            "Disallow: /admin/",
            "Disallow: /tim-kiem",
            "Disallow: /api/",
            "",
            f"Sitemap: {goc}/sitemap.xml",
            "",
        ])
        return Response(noi_dung, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap_xml():
        goc = _goc_trang()
        # "/" chuyển hướng 302 sang /bai-viet/ nên KHÔNG đưa vào sitemap (sitemap chỉ nên chứa URL trả 200);
        # trang chủ thật nằm ở /trang-chu.
        duong_dan = [
            "/trang-chu",
            "/ve-chung-toi",
            "/bai-viet/",
            "/danh-muc-thuoc/",
            "/nha-thuoc-bv/",
            "/tra-cuu-thuoc-tiem-truyen/",
            "/tra-cuu-tuong-hop-tuong-ky/",
            "/tra-cuu-tuong-tac-thuoc/",
            "/tra-cuu-thong-tin-thuoc/",
            "/thong-tin-cho-benh-nhan/",
        ]
        # Từng biệt dược trong danh mục và nhà thuốc BV
        for (ma,) in DanhMucThuoc.query.with_entities(DanhMucThuoc.id).all():
            duong_dan.append(f"/danh-muc-thuoc/thuoc/{ma}")
        for (ma,) in NhaThuocBV.query.with_entities(NhaThuocBV.id).all():
            duong_dan.append(f"/nha-thuoc-bv/thuoc/{ma}")
        # Bài viết đã xuất bản
        for (slug,) in BaiViet.query.with_entities(BaiViet.slug).filter(
            BaiViet.trang_thai == "da_xuat_ban", BaiViet.slug.isnot(None)
        ).all():
            duong_dan.append(f"/bai-viet/{slug}")

        from xml.sax.saxutils import escape
        dong = ['<?xml version="1.0" encoding="UTF-8"?>',
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in duong_dan:
            dong.append(f"  <url><loc>{escape(goc + p)}</loc></url>")
        dong.append("</urlset>")
        return Response("\n".join(dong), mimetype="application/xml")
