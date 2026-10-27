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

  // ------------------------------------------------------------------
  // Ô soạn thảo: trong form chỉ hiện BẢN XEM TRƯỚC (cao tối đa ~200px, mờ dần ở đáy).
  // Bấm vào -> mở MODAL có thanh công cụ đứng yên như Word: thanh công cụ nằm NGOÀI
  // vùng cuộn nên soạn dài đến đâu cũng không phải kéo lên để tìm. 1 Quill dùng chung
  // cho mọi ô (tạo lười ở lần mở đầu tiên).
  // ------------------------------------------------------------------
  var CHO_PHEP = { P:1, BR:1, STRONG:1, B:1, EM:1, I:1, U:1, S:1, STRIKE:1, H1:1, H2:1, H3:1,
                   BLOCKQUOTE:1, UL:1, OL:1, LI:1, A:1, IMG:1 };

  // Lọc HTML để hiển thị bản xem trước: chỉ giữ thẻ định dạng cơ bản, bỏ mọi thuộc tính
  // nguy hiểm (onerror, style...). Phân tích bằng DOMParser nên script/ảnh KHÔNG chạy.
  function locHtml(html) {
    var doc = new DOMParser().parseFromString("<body>" + (html || "") + "</body>", "text/html");
    (function duyet(node) {
      Array.prototype.slice.call(node.childNodes).forEach(function (con) {
        if (con.nodeType === 8) { node.removeChild(con); return; }          // comment
        if (con.nodeType !== 1) return;                                      // text giữ nguyên
        var ten = con.tagName;
        if (ten === "SCRIPT" || ten === "STYLE" || ten === "IFRAME" || ten === "OBJECT") {
          node.removeChild(con); return;
        }
        duyet(con);
        if (!CHO_PHEP[ten]) {                                                // thẻ lạ: bỏ thẻ, giữ nội dung
          while (con.firstChild) node.insertBefore(con.firstChild, con);
          node.removeChild(con);
          return;
        }
        Array.prototype.slice.call(con.attributes).forEach(function (at) {
          var ok = (ten === "A" && at.name === "href") || (ten === "IMG" && (at.name === "src" || at.name === "alt"));
          if (ok && /^\s*(javascript|data|vbscript):/i.test(at.value) && !(ten === "IMG" && /^\s*data:image\//i.test(at.value))) ok = false;
          if (!ok) con.removeAttribute(at.name);
        });
        if (ten === "A") { con.setAttribute("target", "_blank"); con.setAttribute("rel", "noopener noreferrer"); }
      });
    })(doc.body);
    return doc.body.innerHTML;
  }
  function laTrong(html) {
    var t = (html || "").replace(/<p><br><\/p>/g, "").replace(/\s+/g, "");
    return t === "" && !/<img/i.test(html || "");
  }

  var modal = null;          // { overlay, quill, tieuDe, dongBtn, ... } — dựng ở lần mở đầu
  var dangMo = null;         // { wrap, textarea, preview, htmlGoc }
  var triggerTruoc = null;   // phần tử đang focus trước khi mở, để trả focus khi đóng

  function dungModal() {
    var overlay = document.createElement("div");
    overlay.className = "rich-modal-overlay";
    overlay.hidden = true;
    overlay.innerHTML =
      '<div class="rich-modal" role="dialog" aria-modal="true" aria-labelledby="richModalTitle">' +
        '<div class="rich-modal-head">' +
          '<h3 id="richModalTitle" class="rich-modal-title"></h3>' +
          '<button type="button" class="rich-modal-x" data-act="huy" aria-label="Đóng">&times;</button>' +
        '</div>' +
        '<div class="rich-modal-body"><div class="rich-modal-editor"></div></div>' +
        '<div class="rich-modal-foot">' +
          '<span class="rich-modal-hint">Thanh công cụ luôn ở trên cùng. <kbd>Ctrl</kbd>+<kbd>Enter</kbd> = Xong · <kbd>Esc</kbd> = Huỷ</span>' +
          '<button type="button" class="btn btn-outline" data-act="huy">Huỷ</button>' +
          '<button type="button" class="btn btn-primary" data-act="xong">Xong</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    var editorEl = overlay.querySelector(".rich-modal-editor");
    var quill = new Quill(editorEl, {
      theme: "snow",
      placeholder: "Nhập nội dung...",
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
          handlers: { image: function () { chenAnhVaoNoiDung(quill); } },
        },
      },
    });

    overlay.addEventListener("click", function (e) {
      var act = e.target.getAttribute && e.target.getAttribute("data-act");
      if (act === "xong") dong(true);
      else if (act === "huy") dong(false);
      // Bấm ra vùng tối KHÔNG đóng: tránh mất bài đang soạn dài vì lỡ tay
    });
    // Bấm vào vùng tối không được cướp focus khỏi editor (nếu không Esc / Ctrl+Enter sẽ mất tác dụng)
    overlay.addEventListener("mousedown", function (e) {
      if (e.target === overlay) e.preventDefault();
    });
    // Bắt phím ở cấp document (chỉ khi modal đang mở) để vẫn chạy dù focus lỡ rời modal
    document.addEventListener("keydown", function (e) {
      if (!dangMo) return;
      if (e.key === "Escape") {
        // Esc đóng ô nhập link của Quill trước nếu đang mở
        var tip = overlay.querySelector(".ql-tooltip:not(.ql-hidden)");
        if (tip) return;
        e.preventDefault(); dong(false);
      } else if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault(); dong(true);
      } else if (e.key === "Tab") {
        // Giữ focus trong modal
        var ds = overlay.querySelectorAll('button, [contenteditable="true"], select, input, a[href]');
        var kha = Array.prototype.filter.call(ds, function (el) { return !el.disabled && el.offsetParent !== null; });
        if (!kha.length) return;
        var dau = kha[0], cuoi = kha[kha.length - 1];
        var trong = overlay.contains(document.activeElement);
        if (!trong) { e.preventDefault(); dau.focus(); }
        else if (e.shiftKey && document.activeElement === dau) { e.preventDefault(); cuoi.focus(); }
        else if (!e.shiftKey && document.activeElement === cuoi) { e.preventDefault(); dau.focus(); }
      }
    });

    modal = { overlay: overlay, quill: quill, tieuDe: overlay.querySelector(".rich-modal-title") };
  }

  function htmlHienTai() {
    var h = modal.quill.root.innerHTML;
    return h === "<p><br></p>" ? "" : h;
  }

  function mo(wrap, textarea, preview) {
    if (!modal) dungModal();
    triggerTruoc = document.activeElement;
    dangMo = { wrap: wrap, textarea: textarea, preview: preview, htmlGoc: textarea.value || "" };
    modal.tieuDe.textContent = "Chỉnh sửa: " + (wrap.getAttribute("data-label") || "Nội dung");
    modal.quill.setContents([]);
    if (dangMo.htmlGoc) modal.quill.clipboard.dangerouslyPasteHTML(locHtml(dangMo.htmlGoc));
    dangMo.htmlChuan = htmlHienTai();           // so sánh "đã sửa chưa" theo dạng Quill chuẩn hoá
    modal.overlay.hidden = false;
    document.body.classList.add("rich-modal-open");
    modal.quill.focus();
    modal.quill.setSelection(modal.quill.getLength(), 0);
  }

  function dong(luu) {
    if (!dangMo) return;
    var html = htmlHienTai();
    var daSua = html !== dangMo.htmlChuan;
    if (!luu && daSua && !window.confirm("Bỏ các thay đổi vừa nhập trong ô này?")) return;
    if (luu && daSua) {
      dangMo.textarea.value = html;
      capNhatXemTruoc(dangMo.preview, html);
      dangMo.textarea.dispatchEvent(new Event("input", { bubbles: true }));
      dangMo.textarea.dispatchEvent(new Event("change", { bubbles: true }));
    }
    modal.overlay.hidden = true;
    document.body.classList.remove("rich-modal-open");
    var tra = triggerTruoc; dangMo = null; triggerTruoc = null;
    if (tra && tra.focus) tra.focus();
  }

  function capNhatXemTruoc(preview, html) {
    var noiDung = preview.querySelector(".rich-preview-noidung");
    if (laTrong(html)) {
      noiDung.innerHTML = "";
      preview.classList.add("is-empty");
    } else {
      noiDung.innerHTML = locHtml(html);
      preview.classList.remove("is-empty");
    }
    // Ô quá dài thì hiện dải mờ ở đáy cho biết còn nội dung bên dưới
    preview.classList.toggle("is-tran", noiDung.scrollHeight > preview.clientHeight + 4);
  }

  document.querySelectorAll("[data-rich-editor]").forEach(function (wrap) {
    var targetId = wrap.getAttribute("data-target");
    var textarea = targetId ? document.getElementById(targetId) : null;
    if (!textarea) return;
    var nhan = wrap.getAttribute("data-label") || "nội dung";

    var preview = document.createElement("div");
    preview.className = "rich-preview is-empty";
    preview.tabIndex = 0;
    preview.setAttribute("role", "button");
    preview.setAttribute("aria-label", "Chỉnh sửa " + nhan);
    preview.innerHTML =
      '<span class="rich-preview-badge">✎ Bấm để chỉnh sửa</span>' +
      '<div class="rich-preview-noidung rich-content"></div>' +
      '<span class="rich-preview-placeholder"></span>';
    preview.querySelector(".rich-preview-placeholder").textContent =
      textarea.getAttribute("placeholder") || ("Bấm để nhập " + nhan.toLowerCase() + "...");
    wrap.appendChild(preview);
    capNhatXemTruoc(preview, textarea.value);

    function moO() { mo(wrap, textarea, preview); }
    preview.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("a")) e.preventDefault();   // bấm link trong xem trước = mở modal, không nhảy trang
      moO();
    });
    preview.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); moO(); }
    });
  });

});
