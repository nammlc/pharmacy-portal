// Tự đăng xuất admin khi KHÔNG thao tác trong N phút (N lấy từ server, mặc định 15).
// Server mới là bên quyết định hết phiên; file này chỉ:
//  (1) báo "tôi còn đang làm việc" định kỳ để phiên không hết hạn oan khi đang gõ bài dài;
//  (2) tự chuyển về trang đăng nhập khi hết giờ, khỏi để màn hình dữ liệu nằm đó.
(function () {
  var tag = document.currentScript;
  if (!tag) return;
  var IDLE_MS = (parseFloat(tag.dataset.idleMinutes) || 15) * 60 * 1000;
  var PING_MS = Math.min(5 * 60 * 1000, IDLE_MS / 3);     // báo "còn hoạt động" mỗi ≤5 phút
  var keepAliveUrl = tag.dataset.keepAliveUrl;
  var logoutUrl = tag.dataset.logoutUrl;
  var loginUrl = tag.dataset.loginUrl;
  var KEY = "pp_admin_last_active";                          // chia sẻ giữa các tab

  var lastActive = Date.now();
  var lastPing = Date.now();
  var lastWrite = 0;
  var dangChuyenTrang = false;

  function ghiNho(t) {
    try { localStorage.setItem(KEY, String(t)); } catch (e) {}
  }
  function docChung() {
    try { return parseInt(localStorage.getItem(KEY), 10) || 0; } catch (e) { return 0; }
  }
  ghiNho(lastActive);

  function coThaoTac() {
    var now = Date.now();
    lastActive = now;
    if (now - lastWrite > 5000) { lastWrite = now; ghiNho(now); }   // giảm tải: 5 giây/lần
  }
  ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"].forEach(function (ev) {
    window.addEventListener(ev, coThaoTac, { passive: true, capture: true });
  });

  function hetHan() {
    if (dangChuyenTrang) return;
    dangChuyenTrang = true;
    window.location.href = logoutUrl;
  }
  function phienDaHetTrenServer() {
    if (dangChuyenTrang) return;
    dangChuyenTrang = true;
    window.location.href = loginUrl;
  }

  setInterval(function () {
    if (dangChuyenTrang) return;
    var now = Date.now();
    // Lấy mốc mới nhất giữa tab này và các tab admin khác đang mở
    var moc = Math.max(lastActive, docChung());

    if (now - moc >= IDLE_MS) { hetHan(); return; }

    // Có thao tác kể từ lần báo trước -> báo server để làm mới phiên
    if (moc > lastPing && now - lastPing >= PING_MS) {
      lastPing = now;
      fetch(keepAliveUrl, { credentials: "same-origin", cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : { active: false }; })
        .then(function (d) { if (d && d.active === false) phienDaHetTrenServer(); })
        .catch(function () { /* mất mạng tạm thời: bỏ qua, lần sau thử lại */ });
    }
  }, 15000);
})();
