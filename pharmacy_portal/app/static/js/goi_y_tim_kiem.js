// Gợi ý tìm kiếm dạng dropdown (kiểu Google) cho các ô <input data-goi-y="...">.
// data-goi-y nhận giá trị: "all" (trang chủ, gộp cả 2 danh mục), "dmt" (Danh mục
// thuốc) hoặc "ntbv" (Nhà thuốc BV). Gọi API /api/goi-y-tim-kiem, click 1 gợi ý
// sẽ đi thẳng tới trang chi tiết thuốc đó; Enter khi chưa chọn gợi ý nào thì để
// form submit như tìm kiếm bình thường.
// Thuộc tính tuỳ chọn (trang Tương tác thuốc, có 2 ô tìm trong cùng 1 form):
//   data-goi-y-url   : API gợi ý riêng (thay cho /api/goi-y-tim-kiem); API nhận ?q=
//   data-goi-y-dien  : chọn gợi ý thì ĐIỀN tên vào ô (không chuyển trang)
//   data-goi-y-khung : đặt trên phần tử bọc riêng của ô này — dropdown rộng bằng khung đó thay vì cả form
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
    // Gợi ý native của Chrome cho ô tìm kiếm (danh sách những từ đã gõ trước
    // đó) vẫn hiện ra dù đã có autocomplete="off" — Chrome cố tình lờ thuộc
    // tính này với các field dạng tìm kiếm có lịch sử nhập. Cách duy nhất
    // Chrome chịu ẩn hẳn: field người dùng NHÌN THẤY và GÕ VÀO không được
    // mang "name" nào cả -> Chrome không có gì để nhớ/gợi ý. Value thật vẫn
    // được gửi lên server qua 1 input ẩn cùng tên, đồng bộ mỗi khi gõ/khi
    // submit form.
    var form = input.closest("form");
    var ten_that = input.getAttribute("name");
    var an_input = null;
    if (form && ten_that) {
      input.removeAttribute("name");
      var an = document.createElement("input");
      an.type = "hidden";
      an.name = ten_that;
      an.value = input.value;
      form.appendChild(an);
      an_input = an;
      input.addEventListener("input", function () { an.value = input.value; });
      form.addEventListener("submit", function () { an.value = input.value; });
    }

    var pham_vi = input.dataset.goiY;

    // Dropdown rộng đúng bằng cả thanh tìm kiếm (form, gồm cả nút "Tra cứu"), không chỉ bằng ô nhập:
    // đánh dấu form để CSS lấy form làm khung định vị cho dropdown.
    var khung = input.closest("[data-goi-y-khung]") || form;
    if (khung) khung.classList.add("goi-y-form");
    var che_do_dien = input.hasAttribute("data-goi-y-dien");

    var wrap = document.createElement("div");
    wrap.className = "goi-y-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var hop = document.createElement("div");
    hop.className = "goi-y-dropdown";
    hop.hidden = true;
    var uid = "gy-" + Math.random().toString(36).slice(2, 8);
    hop.id = uid + "-ds";
    hop.setAttribute("role", "listbox");
    hop.setAttribute("aria-label", "Gợi ý tìm kiếm");
    wrap.appendChild(hop);
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", hop.id);

    // Vùng đọc (ẩn) báo số gợi ý cho trình đọc màn hình
    var trang_thai = document.createElement("div");
    trang_thai.className = "sr-only";
    trang_thai.setAttribute("role", "status");
    trang_thai.setAttribute("aria-live", "polite");
    wrap.appendChild(trang_thai);

    var danh_sach = [];
    var dang_chon = -1;
    var bo_dem = 0;

    function dong() {
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      hop.hidden = true;
      hop.innerHTML = "";
      danh_sach = [];
      dang_chon = -1;
    }

    function ve() {
      if (!danh_sach.length) { dong(); return; }
      var tu_khoa = input.value.trim();
      hop.innerHTML = danh_sach.map(function (it, i) {
        // Ảnh thuốc; chưa có ảnh (hoặc ảnh lỗi) thì hiện chữ cái đầu như ở danh sách kết quả
        var chu = (it.ten || "?").trim().charAt(0).toUpperCase();
        var anh = it.anh
          ? '<img class="goi-y-anh" src="' + thoat_html(it.anh) + '" alt="" loading="lazy" decoding="async">'
          : '<span class="goi-y-anh goi-y-anh-trong">' + thoat_html(chu) + "</span>";
        return (
          '<div class="goi-y-item" role="option" id="' + uid + '-' + i + '" aria-selected="false" data-idx="' + i + '">' +
            anh +
            '<div class="goi-y-noidung">' +
              '<div class="goi-y-ten-dong">' +
                '<span class="goi-y-ten">' + lam_dam(it.ten, tu_khoa) + "</span>" +
                (it.loai ? '<span class="goi-y-badge">' + thoat_html(it.loai) + "</span>" : "") +
              "</div>" +
              (it.phu ? '<div class="goi-y-phu">' + thoat_html(it.phu) + "</div>" : "") +
            "</div>" +
          "</div>"
        );
      }).join("");
      hop.querySelectorAll("img.goi-y-anh").forEach(function (img) {
        img.addEventListener("error", function () {           // ảnh hỏng / bị chặn → chữ cái đầu
          var cho = document.createElement("span");
          cho.className = "goi-y-anh goi-y-anh-trong";
          cho.textContent = (img.closest(".goi-y-item").querySelector(".goi-y-ten").textContent || "?").trim().charAt(0).toUpperCase();
          img.replaceWith(cho);
        });
      });
      hop.hidden = false;
      input.setAttribute("aria-expanded", "true");
      trang_thai.textContent = danh_sach.length + " gợi ý, dùng phím mũi tên lên xuống để chọn";
    }

    function to_dam_dang_chon() {
      var muc = hop.querySelectorAll(".goi-y-item");
      muc.forEach(function (el, i) {
        el.classList.toggle("active", i === dang_chon);
        el.setAttribute("aria-selected", i === dang_chon ? "true" : "false");
      });
      if (dang_chon >= 0 && muc[dang_chon]) input.setAttribute("aria-activedescendant", muc[dang_chon].id);
      else input.removeAttribute("aria-activedescendant");
      if (dang_chon >= 0 && muc[dang_chon]) muc[dang_chon].scrollIntoView({ block: "nearest" });
    }

    function chon(i) {
      var it = danh_sach[i];
      if (!it) return;
      if (che_do_dien) {                       // điền vào ô, người dùng bấm "Tra cứu" sau
        input.value = it.ten;
        if (an_input) an_input.value = it.ten;
        dong();
        input.focus();
        return;
      }
      window.location.href = it.url;
    }

    hop.addEventListener("mousedown", function (e) {
      // mousedown (không phải click) để chạy trước khi input mất focus và đóng dropdown
      var el = e.target.closest(".goi-y-item");
      if (!el) return;
      if (che_do_dien) e.preventDefault();     // không để ô nhập mất focus
      chon(parseInt(el.dataset.idx, 10));
    });

    var tim = debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { dong(); return; }
      var luot = ++bo_dem;
      var api = input.dataset.goiYUrl || ("/api/goi-y-tim-kiem?scope=" + encodeURIComponent(pham_vi));
      fetch(api + (api.indexOf("?") === -1 ? "?" : "&") + "q=" + encodeURIComponent(q))
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
