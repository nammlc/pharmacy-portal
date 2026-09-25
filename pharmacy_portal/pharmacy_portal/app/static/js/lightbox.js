/* ============================================================
   Xem ảnh phóng to (lightbox): áp dụng cho ảnh đại diện bài viết,
   ảnh trong nội dung bài viết (rich-content), và ảnh thuốc ở trang
   chi tiết công khai. Bấm vào ảnh -> hiện to kèm lớp overlay tối;
   bấm ra ngoài / nút X / phím Esc để đóng.
   ============================================================ */
(function () {
  "use strict";

  var CAC_SELECTOR_ANH = [
    ".bv-detail-anh",       // ảnh đại diện bài viết (trang chi tiết)
    ".rich-content img",    // ảnh chèn trong nội dung bài viết
    ".drug-detail-media img", // ảnh thuốc (trang chi tiết công khai)
  ];

  var overlay, anhLon, nutDong;

  function taoOverlay() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.className = "lightbox-overlay";
    overlay.innerHTML =
      '<button type="button" class="lightbox-close" aria-label="Đóng">&times;</button>' +
      '<img class="lightbox-anh" alt="">';
    document.body.appendChild(overlay);

    anhLon = overlay.querySelector(".lightbox-anh");
    nutDong = overlay.querySelector(".lightbox-close");

    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) dong();
    });
    nutDong.addEventListener("click", dong);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") dong();
    });
  }

  function mo(src, alt) {
    taoOverlay();
    anhLon.src = src;
    anhLon.alt = alt || "";
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
  }

  function dong() {
    if (!overlay) return;
    overlay.classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function ganSuKien() {
    var danhSachAnh = document.querySelectorAll(CAC_SELECTOR_ANH.join(","));
    danhSachAnh.forEach(function (img) {
      if (img.dataset.lightboxDaGan === "1") return;
      img.dataset.lightboxDaGan = "1";
      img.classList.add("lightbox-trigger");
      img.addEventListener("click", function () {
        mo(img.currentSrc || img.src, img.alt);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", ganSuKien);
})();
