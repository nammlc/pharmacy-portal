document.addEventListener("DOMContentLoaded", function () {
  var dropdown = document.getElementById("navDropdown");
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");

  if (!dropdown || !toggle || !nav) return;

  function openMenu() {
    nav.classList.add("open");
    dropdown.setAttribute("data-open", "true");
    toggle.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    nav.classList.remove("open");
    dropdown.setAttribute("data-open", "false");
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    if (nav.classList.contains("open")) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  // Đóng menu khi bấm ra ngoài
  document.addEventListener("click", function (e) {
    if (!dropdown.contains(e.target)) {
      closeMenu();
    }
  });

  // Đóng menu khi chọn 1 mục
  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", closeMenu);
  });

  // Đóng menu khi nhấn Esc
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMenu();
  });
});

/* ============================================================
   ADMIN PANEL — sidebar mobile (drawer) + dropdown tài khoản
   ============================================================ */
document.addEventListener("DOMContentLoaded", function () {
  var sidebar = document.getElementById("adminSidebar");
  var overlay = document.getElementById("adminOverlay");
  var menuBtn = document.getElementById("adminMenuBtn");

  if (sidebar && overlay && menuBtn) {
    function openSidebar() {
      sidebar.classList.add("is-open");
      overlay.classList.add("is-open");
      menuBtn.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    }
    function closeSidebar() {
      sidebar.classList.remove("is-open");
      overlay.classList.remove("is-open");
      menuBtn.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }
    menuBtn.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) closeSidebar();
      else openSidebar();
    });
    overlay.addEventListener("click", closeSidebar);
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeSidebar);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });
    // Đóng drawer khi resize lên desktop (tránh kẹt trạng thái mở)
    window.addEventListener("resize", function () {
      if (window.innerWidth > 800) closeSidebar();
    });
  }

  var userBtn = document.getElementById("adminUserBtn");
  var userDropdown = document.getElementById("adminUserDropdown");

  if (userBtn && userDropdown) {
    function openUserMenu() {
      userDropdown.classList.add("is-open");
      userBtn.setAttribute("aria-expanded", "true");
    }
    function closeUserMenu() {
      userDropdown.classList.remove("is-open");
      userBtn.setAttribute("aria-expanded", "false");
    }
    userBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (userDropdown.classList.contains("is-open")) closeUserMenu();
      else openUserMenu();
    });
    document.addEventListener("click", function (e) {
      if (!userDropdown.contains(e.target) && e.target !== userBtn) closeUserMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeUserMenu();
    });
  }
});

/* ============================================================
   ADMIN PANEL — trình soạn thảo văn bản kiểu Word (Quill)
   Tự động gắn vào mọi TextAreaField được đánh dấu [data-rich-editor]
   (xem app/templates/admin/_macros.html)
   ============================================================ */
document.addEventListener("DOMContentLoaded", function () {
  if (typeof Quill === "undefined") return;

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : "";

  // Chèn ảnh mô tả vào đúng vị trí con trỏ trong editor. Cho phép chèn
  // NHIỀU ảnh xen giữa các đoạn văn (khác ảnh đại diện — chỉ có 1 ảnh
  // cho cả bài viết, upload riêng ở field "file_anh" bên dưới).
  function chenAnhVaoNoiDung(quill) {
    var input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp,image/gif";
    input.onchange = function () {
      var file = input.files && input.files[0];
      if (!file) return;

      var range = quill.getSelection(true);
      // Hiện chỗ giữ trong lúc tải ảnh lên, để người dùng biết đang xử lý
      var chuGiuCho = "Đang tải ảnh lên...";
      quill.insertText(range.index, chuGiuCho, { italic: true });
      quill.setSelection(range.index + chuGiuCho.length);

      var duLieu = new FormData();
      duLieu.append("anh", file);

      fetch("/admin/upload-anh-noi-dung", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: duLieu,
      })
        .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
        .then(function (ket_qua) {
          quill.deleteText(range.index, chuGiuCho.length);
          if (!ket_qua.ok || !ket_qua.data.url) {
            alert(ket_qua.data.loi || "Upload ảnh thất bại, thử lại sau.");
            return;
          }
          quill.insertEmbed(range.index, "image", ket_qua.data.url);
          quill.setSelection(range.index + 1);
        })
        .catch(function () {
          quill.deleteText(range.index, chuGiuCho.length);
          alert("Không kết nối được máy chủ, thử lại sau.");
        });
    };
    input.click();
  }

  document.querySelectorAll("[data-rich-editor]").forEach(function (wrap) {
    var targetId = wrap.getAttribute("data-target");
    var textarea = targetId ? document.getElementById(targetId) : null;
    var editorEl = wrap.querySelector(".quill-editor");
    if (!textarea || !editorEl) return;

    var quill = new Quill(editorEl, {
      theme: "snow",
      placeholder: textarea.getAttribute("placeholder") || "",
      modules: {
        toolbar: {
          container: [
            [{ header: [1, 2, 3, false] }],
            ["bold", "italic", "underline", "strike"],
            ["blockquote"],
            [{ list: "ordered" }, { list: "bullet" }],
            ["link", "image"],
            ["clean"],
          ],
          handlers: {
            image: function () { chenAnhVaoNoiDung(quill); },
          },
        },
      },
    });

    // Nạp nội dung có sẵn khi sửa (textarea đang giữ HTML đã lưu)
    if (textarea.value) {
      quill.clipboard.dangerouslyPasteHTML(textarea.value);
    }

    // Đồng bộ nội dung Quill -> textarea ẩn mỗi khi gõ, để khi submit
    // form (POST bình thường) textarea gửi đúng HTML mới nhất
    quill.on("text-change", function () {
      var html = quill.root.innerHTML;
      textarea.value = html === "<p><br></p>" ? "" : html;
    });
  });
});
