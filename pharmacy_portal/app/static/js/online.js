// Đếm người đang online — cập nhật gần thời gian thực, không cần tải lại trang.
//  1) Gửi tín hiệu "còn ở đây" ~20 giây/lần — chỉ khi tab đang hiện VÀ có thao tác gần đây
//     (khách: 5 phút; admin: 14 phút, ngắn hơn thời hạn tự đăng xuất 15 phút). Tab bỏ quên không được tính.
//  2) Khi đóng tab / rời trang: báo "tôi rời" bằng sendBeacon → số liệu giảm gần như ngay.
//  3) Trang quản trị: ô thống kê (#onlineBox) hỏi lại server mỗi 5 giây khi tab đang hiện.
(function () {
  var tag = document.currentScript;
  if (!tag) return;
  var khu = tag.dataset.khu || "cong_khai";
  var pingUrl = tag.dataset.pingUrl;
  var roiUrl = tag.dataset.roiUrl;
  var statUrl = tag.dataset.statUrl;
  var loginUrl = tag.dataset.loginUrl;
  if (!pingUrl) return;

  var PING_MS = 20000, STAT_MS = 5000;
  var IDLE_MS = (khu === "admin" ? 14 : 5) * 60 * 1000;
  var lastAct = Date.now(), lastPing = 0, stopped = false, daRoi = false;
  var query = "?khu=" + encodeURIComponent(khu);

  function hienTai() { return !document.hidden; }

  function ping() {
    if (stopped || !hienTai() || Date.now() - lastAct > IDLE_MS) return;
    lastPing = Date.now(); daRoi = false;
    fetch(pingUrl + query, { method: "POST", credentials: "same-origin", keepalive: true })
      .then(function (r) {
        if (r.status === 401) {            // trang quản trị nhưng phiên đã hết hạn: dừng, không tính thành khách
          stopped = true; if (box) box.classList.add("is-off");
        }
      })
      .catch(function () {});
  }

  function roi() {                          // đóng tab / chuyển trang
    if (stopped || daRoi || !roiUrl || !navigator.sendBeacon) return;
    daRoi = true;
    navigator.sendBeacon(roiUrl + query);
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

  function datSo(el, v) {                      // đổi số + nháy xanh nếu khác giá trị trước
    var moi = String(v);
    if (el.textContent === moi) return;
    var daCoSo = el.textContent !== "–";
    el.textContent = moi;
    if (daCoSo) {
      el.classList.add("is-changed");
      setTimeout(function () { el.classList.remove("is-changed"); }, 700);
    }
  }

  var dangHoi = false;
  function layThongKe() {
    if (!statUrl || !box || stopped || !hienTai() || dangHoi) return;
    dangHoi = true;
    fetch(statUrl, { credentials: "same-origin", cache: "no-store", headers: { "Accept": "application/json" } })
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
        datSo(elAdmin, d.admin);
        datSo(elKhach, d.khach);
        veTen(d.ten_admin);
      })
      .catch(function () { box.classList.add("is-off"); })
      .then(function () { dangHoi = false; });
  }

  ping();
  setInterval(ping, PING_MS);
  if (box) {
    setTimeout(layThongKe, 500);               // chờ tín hiệu của chính mình được ghi rồi mới đếm
    setInterval(layThongKe, STAT_MS);
  }
  document.addEventListener("visibilitychange", function () {
    if (hienTai()) { ping(); layThongKe(); }
  });
  window.addEventListener("pagehide", roi);
  window.addEventListener("pageshow", function (e) { if (e.persisted) { daRoi = false; ping(); layThongKe(); } });
})();
