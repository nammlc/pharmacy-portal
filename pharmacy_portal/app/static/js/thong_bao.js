// Chuông thông báo trang quản trị: số chưa đọc + danh sách, tự cập nhật ~15 giây/lần (không cần tải lại trang).
// Hỏi định kỳ KHÔNG làm mới giờ hoạt động của phiên (server loại endpoint này khỏi việc gia hạn), nên vẫn tự đăng xuất sau 15 phút không thao tác.
(function () {
  var tag = document.currentScript;
  var btn = document.getElementById("tbBellBtn"), panel = document.getElementById("tbPanel"), badge = document.getElementById("tbBellBadge");
  var list = document.getElementById("tbList"), readAll = document.getElementById("tbReadAll");
  if (!tag || !btn || !panel) return;
  var D = tag.dataset, tieuDeGoc = document.title, truoc = -1, dangHoi = false, het = false;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function csrf() { var m = document.querySelector('meta[name="csrf-token"]'); return m ? m.content : ""; }
  function moUrl(id) { return D.moUrl.replace(/0$/, String(id)); }

  function capNhatSo(n) {
    badge.hidden = !n; badge.textContent = n > 99 ? "99+" : String(n || "");
    document.title = n ? "(" + n + ") " + tieuDeGoc.replace(/^\(\d+\)\s*/, "") : tieuDeGoc.replace(/^\(\d+\)\s*/, "");
    var nav = document.querySelector("[data-tb-nav]"); if (nav) { nav.textContent = n; nav.hidden = !n; }
  }

  function ve(muc) {
    list.innerHTML = "";
    if (!muc.length) { list.appendChild(el("li", "tb-empty", "Chưa có thông báo nào.")); return; }
    muc.forEach(function (t) {
      var li = el("li", t.da_doc ? "" : "tb-unread");
      var a = el("a"); a.href = moUrl(t.id);
      a.appendChild(el("span", "tb-ico", t.loai === "y_kien_moi" ? "💬" : "✉️"));
      var txt = el("span", "tb-txt");
      var tt = el("strong", "", t.tieu_de);
      if (t.so_luong > 1) tt.appendChild(el("span", "tb-count", " ×" + t.so_luong));
      txt.appendChild(tt); txt.appendChild(el("small", "", t.noi_dung));
      a.appendChild(txt); a.appendChild(el("span", "tb-time", t.gio));
      li.appendChild(a); list.appendChild(li);
    });
  }

  function hoi() {
    if (dangHoi || het || document.hidden) return;
    dangHoi = true;
    fetch(D.url, { credentials: "same-origin", cache: "no-store", headers: { "Accept": "application/json" } })
      .then(function (r) { if (r.status === 401) { het = true; if (D.loginUrl) location.href = D.loginUrl; return null; } return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.ok) return;
        capNhatSo(d.chua_doc);
        if (!panel.hidden || d.chua_doc !== truoc) ve(d.muc);          // đang mở panel hoặc có thay đổi → vẽ lại
        if (truoc !== -1 && d.chua_doc > truoc) { btn.classList.add("tb-ring"); setTimeout(function () { btn.classList.remove("tb-ring"); }, 1500); }
        truoc = d.chua_doc;
      })
      .catch(function () {})
      .then(function () { dangHoi = false; });
  }

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    var mo = panel.hidden; panel.hidden = !mo; btn.setAttribute("aria-expanded", mo ? "true" : "false");
    if (mo) { truoc = -2; hoi(); }
  });
  document.addEventListener("click", function (e) { if (!panel.hidden && !panel.contains(e.target)) { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); } });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { panel.hidden = true; btn.setAttribute("aria-expanded", "false"); } });
  readAll.addEventListener("click", function () {
    fetch(D.docTatCa, { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf(), "Accept": "application/json" } })
      .then(function (r) { return r.json(); }).then(function () { capNhatSo(0); truoc = -2; hoi(); }).catch(function () {});
  });

  hoi();
  setInterval(hoi, 15000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) hoi(); });
})();
