/* Giao diện "taste": menu (panel khi chỉ vào + màn hình menu trên điện thoại) và khoảnh khắc word-highlight.
   Không có script thì mọi thứ vẫn đọc được: panel mở bằng :hover/:focus-within, chữ nhấn mạnh hiện đủ màu. */
(function () {
  "use strict";
  var raf = window.requestAnimationFrame || function (f) { return setTimeout(f, 16); };

  /* ---- menu ---- */
  var menu = document.getElementById("tkMenu"), sheet = document.getElementById("tkSheet");
  function datSheet(mo) {
    if (!menu || !sheet) return;
    sheet.hidden = !mo;
    menu.setAttribute("aria-expanded", mo ? "true" : "false");
    menu.textContent = mo ? "Đóng" : "Menu";
    document.documentElement.style.overflow = mo ? "hidden" : "";
  }
  if (menu && sheet) {
    menu.addEventListener("click", function () { datSheet(sheet.hidden); });
    sheet.addEventListener("click", function (e) { if (e.target.closest("a")) datSheet(false); });
    window.addEventListener("resize", function () { if (window.innerWidth > 900) datSheet(false); });
  }
  var cacMuc = document.querySelectorAll(".tk-nav__item[data-panel]");
  function dongPanel(tru) {
    cacMuc.forEach(function (m) {
      if (m === tru) return;
      m.dataset.open = "false";
      var b = m.querySelector("button"); if (b) b.setAttribute("aria-expanded", "false");
    });
  }
  cacMuc.forEach(function (m) {
    var b = m.querySelector("button");
    if (!b) return;
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      var mo = m.dataset.open !== "true";
      dongPanel(m); m.dataset.open = mo ? "true" : "false"; b.setAttribute("aria-expanded", mo ? "true" : "false");
    });
  });
  document.addEventListener("click", function (e) { if (!e.target.closest(".tk-nav__item")) dongPanel(null); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    dongPanel(null); datSheet(false);
  });

  /* ---- word-highlight: câu chữ sáng dần theo từng từ khi mục đi qua giữa màn hình (chạy ngược khi cuộn lên) ---- */
  var cacCau = document.querySelectorAll('[data-moment="word-highlight"]');
  if (!cacCau.length || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches)) return;

  function tachTu(nut) {
    var kq = [];
    Array.prototype.slice.call(nut.childNodes).forEach(function (n) {
      if (n.nodeType === 3) {
        var frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach(function (t) {
          if (!t) return;
          if (/^\s+$/.test(t)) { frag.appendChild(document.createTextNode(t)); return; }
          var s = document.createElement("span"); s.className = "w"; s.textContent = t; frag.appendChild(s); kq.push(s);
        });
        nut.replaceChild(frag, n);
      } else if (n.nodeType === 1) {
        kq = kq.concat(tachTu(n));
      }
    });
    return kq;
  }
  cacCau.forEach(function (cau) {
    var tu = tachTu(cau), cho = false;
    if (!tu.length) return;
    cau.classList.add("is-live");
    function capNhat() {
      cho = false;
      var r = cau.getBoundingClientRect(), vh = window.innerHeight || 800;
      // 0 khi câu vừa lọt vào 85% chiều cao màn hình, 1 khi đã lên quá giữa màn hình
      var p = Math.max(0, Math.min(1, (vh * 0.85 - r.top) / (vh * 0.85 - vh * 0.35 + r.height * 0.4)));
      var n = Math.round(p * tu.length);
      for (var i = 0; i < tu.length; i++) tu[i].classList.toggle("on", i < n);
    }
    function yeuCau() { if (!cho) { cho = true; raf(capNhat); } }
    window.addEventListener("scroll", yeuCau, { passive: true });
    window.addEventListener("resize", yeuCau);
    capNhat();
  });
})();
