// Đếm người đang online.
//  1) Gửi tín hiệu "còn ở đây" ~45 giây/lần — chỉ khi tab đang hiện VÀ có thao tác trong 5 phút gần nhất
//     (tab bỏ quên không tính, cũng không giữ database thức).
//  2) Trang quản trị: cập nhật ô thống kê (#onlineBox) mỗi 20 giây khi tab đang hiện.
(function () {
  var tag = document.currentScript;
  if (!tag) return;
  var khu = tag.dataset.khu || "cong_khai";
  var pingUrl = tag.dataset.pingUrl;
  var statUrl = tag.dataset.statUrl;
  var loginUrl = tag.dataset.loginUrl;
  if (!pingUrl) return;

  var PING_MS = 45000, STAT_MS = 20000, IDLE_MS = 5 * 60 * 1000;
  var lastAct = Date.now(), lastPing = 0, stopped = false;

  function hienTai() { return !document.hidden; }

  function ping() {
    if (stopped || !hienTai() || Date.now() - lastAct > IDLE_MS) return;
    lastPing = Date.now();
    fetch(pingUrl + "?khu=" + encodeURIComponent(khu), { method: "POST", credentials: "same-origin", keepalive: true })
      .then(function (r) {
        if (r.status === 401) {            // trang quản trị nhưng phiên đã hết hạn: dừng, không tính thành khách
          stopped = true; box && box.classList.add("is-off");
        }
      })
      .catch(function () {});
  }

  function coThaoTac() {
    var truocDo = Date.now() - lastAct;
    lastAct = Date.now();
    if (truocDo > IDLE_MS && Date.now() - lastPing > 5000) ping();     // vừa quay lại sau khi im lâu → báo ngay
  }
  ["mousemove", "keydown", "scroll", "touchstart", "click", "wheel"].forEach(function (ev) {
    window.addEventListener(ev, coThaoTac, { passive: true, capture: true });
  });

  // ----- Ô thống kê (chỉ có ở trang quản trị) -----
  var box = document.getElementById("onlineBox");
  var elAdmin = document.getElementById("onlineAdmin");
  var elKhach = document.getElementById("onlineKhach");
  var elNames = document.getElementById("onlineNames");
  var elNote = document.getElementById("onlineNote");
  var btn = document.getElementById("onlineToggle");
  var detail = document.getElementById("onlineDetail");

  if (btn && detail) {
    btn.addEventListener("click", function () {
      var mo = detail.hidden;
      detail.hidden = !mo;
      btn.setAttribute("aria-expanded", mo ? "true" : "false");
      box.classList.toggle("is-open", mo);
    });
  }

  function veTen(ds) {
    if (!elNames) return;
    elNames.innerHTML = "";
    (ds && ds.length ? ds : ["—"]).forEach(function (t) {
      var li = document.createElement("li");
      li.textContent = t;                      // textContent: tên admin không bao giờ được hiểu là HTML
      elNames.appendChild(li);
    });
  }

  function layThongKe() {
    if (!statUrl || !box || stopped || !hienTai()) return;
    fetch(statUrl, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r.status === 401) {                // hết phiên: về trang đăng nhập (server mới là bên quyết định)
          stopped = true; box.classList.add("is-off");
          if (loginUrl) window.location.href = loginUrl;
          return null;
        }
        return r.ok ? r.json() : null;
      })
      .then(function (d) {
        if (!d) { box.classList.add("is-off"); return; }
        box.classList.remove("is-off");
        elAdmin.textContent = d.admin;
        elKhach.textContent = d.khach;
        veTen(d.ten_admin);
        if (elNote && d.cua_so) elNote.textContent = "Tính trong " + Math.round(d.cua_so / 60) + " phút gần nhất. Số người dùng là ước lượng.";
      })
      .catch(function () { box.classList.add("is-off"); });
  }

  ping();
  setInterval(ping, PING_MS);
  if (box) {
    setTimeout(layThongKe, 600);               // chờ tín hiệu của chính mình được ghi rồi mới đếm
    setInterval(layThongKe, STAT_MS);
  }
  document.addEventListener("visibilitychange", function () {
    if (hienTai()) { ping(); layThongKe(); }
  });
})();
