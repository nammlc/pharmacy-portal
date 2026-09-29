// Gợi ý tìm kiếm dạng dropdown (kiểu Google) cho các ô <input data-goi-y="...">.
// data-goi-y nhận giá trị: "all" (trang chủ, gộp cả 2 danh mục), "dmt" (Danh mục
// thuốc) hoặc "ntbv" (Nhà thuốc BV). Gọi API /api/goi-y-tim-kiem, click 1 gợi ý
// sẽ đi thẳng tới trang chi tiết thuốc đó; Enter khi chưa chọn gợi ý nào thì để
// form submit như tìm kiếm bình thường.
(function () {
  function thoat_html(s) {
    return (s || "").replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // In đậm phần khớp với từ khoá đang gõ (so khớp chuỗi con, không phân biệt hoa thường)
  function lam_dam(ten, tu_khoa) {
    var idx = ten.toLowerCase().indexOf(tu_khoa.toLowerCase());
    if (idx === -1) return thoat_html(ten);
    return (
      thoat_html(ten.slice(0, idx)) +
      "<strong>" + thoat_html(ten.slice(idx, idx + tu_khoa.length)) + "</strong>" +
      thoat_html(ten.slice(idx + tu_khoa.length))
    );
  }

  function debounce(fn, cho) {
    var t;
    return function () {
      var self = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, cho);
    };
  }

  function gan(input) {
    if (input.dataset.goiYGan) return;
    input.dataset.goiYGan = "1";
    input.setAttribute("autocomplete", "off");

    var pham_vi = input.dataset.goiY;

    var wrap = document.createElement("div");
    wrap.className = "goi-y-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var hop = document.createElement("div");
    hop.className = "goi-y-dropdown";
    hop.hidden = true;
    wrap.appendChild(hop);

    var danh_sach = [];
    var dang_chon = -1;
    var bo_dem = 0;

    function dong() {
      hop.hidden = true;
      hop.innerHTML = "";
      danh_sach = [];
      dang_chon = -1;
    }

    function ve() {
      if (!danh_sach.length) { dong(); return; }
      var tu_khoa = input.value.trim();
      hop.innerHTML = danh_sach.map(function (it, i) {
        return (
          '<div class="goi-y-item" data-idx="' + i + '">' +
            '<div class="goi-y-ten-dong">' +
              '<span class="goi-y-ten">' + lam_dam(it.ten, tu_khoa) + "</span>" +
              (it.loai ? '<span class="goi-y-badge">' + thoat_html(it.loai) + "</span>" : "") +
            "</div>" +
            (it.phu ? '<div class="goi-y-phu">' + thoat_html(it.phu) + "</div>" : "") +
          "</div>"
        );
      }).join("");
      hop.hidden = false;
    }

    function to_dam_dang_chon() {
      var muc = hop.querySelectorAll(".goi-y-item");
      muc.forEach(function (el, i) { el.classList.toggle("active", i === dang_chon); });
      if (dang_chon >= 0 && muc[dang_chon]) muc[dang_chon].scrollIntoView({ block: "nearest" });
    }

    function chon(i) {
      var it = danh_sach[i];
      if (it) window.location.href = it.url;
    }

    hop.addEventListener("mousedown", function (e) {
      // mousedown (không phải click) để chạy trước khi input mất focus và đóng dropdown
      var el = e.target.closest(".goi-y-item");
      if (el) chon(parseInt(el.dataset.idx, 10));
    });

    var tim = debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { dong(); return; }
      var luot = ++bo_dem;
      fetch("/api/goi-y-tim-kiem?scope=" + encodeURIComponent(pham_vi) + "&q=" + encodeURIComponent(q))
        .then(function (r) { return r.ok ? r.json() : []; })
        .then(function (ds) {
          if (luot !== bo_dem) return; // bỏ kết quả cũ trả về muộn
          danh_sach = ds; dang_chon = -1; ve();
        })
        .catch(function () {});
    }, 200);

    input.addEventListener("input", tim);
    input.addEventListener("focus", function () {
      if (danh_sach.length) ve();
    });
    input.addEventListener("keydown", function (e) {
      if (hop.hidden) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        dang_chon = Math.min(dang_chon + 1, danh_sach.length - 1);
        to_dam_dang_chon();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        dang_chon = Math.max(dang_chon - 1, -1);
        to_dam_dang_chon();
      } else if (e.key === "Enter") {
        if (dang_chon >= 0) { e.preventDefault(); chon(dang_chon); }
        // ngược lại: để form submit tìm kiếm bình thường
      } else if (e.key === "Escape") {
        dong();
      }
    });

    document.addEventListener("click", function (e) {
      if (!wrap.contains(e.target)) dong();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input[data-goi-y]").forEach(gan);
  });
})();
