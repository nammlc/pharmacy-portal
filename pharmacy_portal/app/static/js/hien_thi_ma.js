// Nút hiện/ẩn (icon con mắt) cho mọi ô mã bảo mật có thuộc tính data-hien-ma.
(function () {
  var MAT_MO = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-7.5 11-7.5S23 12 23 12s-4 7.5-11 7.5S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var MAT_GACH = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19.5C5 19.5 1 12 1 12a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A10.9 10.9 0 0 1 12 4.5c7 0 11 7.5 11 7.5a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  document.querySelectorAll("input[data-hien-ma]").forEach(function (o) {
    if (o.parentNode.classList && o.parentNode.classList.contains("hien-ma-wrap")) return;
    var wrap = document.createElement("div");
    wrap.className = "hien-ma-wrap";
    o.parentNode.insertBefore(wrap, o);
    wrap.appendChild(o);
    var nut = document.createElement("button");
    nut.type = "button";
    nut.className = "hien-ma-nut";
    nut.innerHTML = MAT_MO;
    nut.setAttribute("aria-label", "Hiện mã");
    nut.setAttribute("title", "Hiện mã");
    nut.addEventListener("click", function () {
      var dang_an = o.type === "password";
      o.type = dang_an ? "text" : "password";
      nut.innerHTML = dang_an ? MAT_GACH : MAT_MO;
      nut.setAttribute("aria-label", dang_an ? "Ẩn mã" : "Hiện mã");
      nut.setAttribute("title", dang_an ? "Ẩn mã" : "Hiện mã");
    });
    wrap.appendChild(nut);
  });
})();
