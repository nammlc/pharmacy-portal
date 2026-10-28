// Nút hiện/ẩn cho mọi ô mã bảo mật có thuộc tính data-hien-ma.
(function () {
  document.querySelectorAll("input[data-hien-ma]").forEach(function (o) {
    var wrap = document.createElement("div");
    wrap.className = "hien-ma-wrap";
    o.parentNode.insertBefore(wrap, o);
    wrap.appendChild(o);
    var nut = document.createElement("button");
    nut.type = "button";
    nut.className = "hien-ma-nut";
    nut.setAttribute("aria-label", "Hiện hoặc ẩn mã");
    nut.textContent = "Hiện";
    nut.addEventListener("click", function () {
      var dang_an = o.type === "password";
      o.type = dang_an ? "text" : "password";
      nut.textContent = dang_an ? "Ẩn" : "Hiện";
    });
    wrap.appendChild(nut);
  });
})();
