// Thêm nút "mắt" để hiện/ẩn mật khẩu cho mọi ô <input type="password">.
(function () {
  var MAT_MO = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var MAT_GACH = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 19c-7 0-11-7-11-7a19.8 19.8 0 0 1 5.06-5.94"/><path d="M9.9 4.24A10.9 10.9 0 0 1 12 4c7 0 11 7 11 7a19.8 19.8 0 0 1-3.17 4.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

  function gan(input) {
    if (input.dataset.pwToggle) return;
    input.dataset.pwToggle = "1";

    var wrap = document.createElement("span");
    wrap.className = "pw-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);

    var nut = document.createElement("button");
    nut.type = "button";
    nut.className = "pw-toggle";
    nut.setAttribute("aria-label", "Hiện mật khẩu");
    nut.innerHTML = MAT_MO;
    nut.addEventListener("click", function () {
      var dangAn = input.type === "password";
      input.type = dangAn ? "text" : "password";
      nut.innerHTML = dangAn ? MAT_GACH : MAT_MO;
      nut.setAttribute("aria-label", dangAn ? "Ẩn mật khẩu" : "Hiện mật khẩu");
    });
    wrap.appendChild(nut);
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll('input[type="password"]').forEach(gan);
  });
})();
