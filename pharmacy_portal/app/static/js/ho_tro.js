// Chat riêng của khách: đăng nhập bằng SĐT + mã bí mật 6 số (lần đầu = tạo tài khoản), gửi / nhận tin, tự cập nhật.
(function () {
  var app = document.getElementById("htApp");
  if (!app) return;
  var D = app.dataset, csrf = D.csrf;
  var fDangNhap = document.getElementById("htDangNhap"), boxChat = document.getElementById("htChat");
  var msgs = document.getElementById("htMsgs"), fGui = document.getElementById("htGui");
  var tName = document.getElementById("htTen");
  var t0 = Date.now(), cuoiId = 0, dangNhap = D.daDangNhap === "1", timer = null;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function bao(node, text, loi) { node.textContent = text; node.className = "hd-msg " + (loi ? "hd-msg-loi" : "hd-msg-ok"); }
  function post(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin",
                        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "Accept": "application/json" },
                        body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().then(function (d) { d._ma = r.status; return d; }).catch(function () { return { ok: false, loi: "Có lỗi xảy ra, vui lòng tải lại trang.", _ma: r.status }; }); });
  }

  function veTin(t) {
    var b = el("div", "ht-msg ht-" + t.tu); b.dataset.id = t.id;
    if (t.ngu_canh) {
      var c = el("div", "ht-msg-ctx"); c.appendChild(document.createTextNode("📎 "));
      if (t.ngu_canh_url && t.ngu_canh_url.charAt(0) === "/") { var a = el("a", "", t.ngu_canh); a.href = t.ngu_canh_url; c.appendChild(a); }
      else c.appendChild(document.createTextNode(t.ngu_canh));
      b.appendChild(c);
    }
    b.appendChild(el("div", "ht-bubble", t.noi_dung));
    b.appendChild(el("div", "ht-meta", (t.tu === "admin" ? (t.ten || "Khoa Dược") + " · " : "") + t.gio));
    return b;
  }
  function themTin(ds) {
    var gan = msgs.scrollTop + msgs.clientHeight >= msgs.scrollHeight - 80;
    var trong = document.getElementById("htTrong"); if (trong && ds.length) trong.remove();
    ds.forEach(function (t) { if (t.id > cuoiId) { msgs.appendChild(veTin(t)); cuoiId = t.id; } });
    if (ds.length && gan) msgs.scrollTop = msgs.scrollHeight;
  }
  Array.prototype.forEach.call(msgs.querySelectorAll(".ht-msg"), function (m) { cuoiId = Math.max(cuoiId, +m.dataset.id || 0); });
  msgs.scrollTop = msgs.scrollHeight;

  function hoiTinMoi() {
    if (!dangNhap || document.hidden) return;
    fetch(D.tinUrl + "?sau=" + cuoiId, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (r.status === 401) { vaoManHinhDangNhap(); return null; } return r.json(); })
      .then(function (d) { if (d && d.ok) themTin(d.tin); })
      .catch(function () {});
  }
  function batDau() { dangNhap = true; fDangNhap.hidden = true; boxChat.hidden = false; if (!timer) timer = setInterval(hoiTinMoi, 8000); }
  function vaoManHinhDangNhap() { dangNhap = false; if (timer) { clearInterval(timer); timer = null; } boxChat.hidden = true; fDangNhap.hidden = false; }
  if (dangNhap) batDau();
  document.addEventListener("visibilitychange", function () { if (!document.hidden) hoiTinMoi(); });

  // ── Form đầu tiên: đăng nhập / tạo tài khoản rồi gửi tin ──
  var msgDN = document.getElementById("htMsgDangNhap"), nutMoi = document.getElementById("htGuiMoi");
  fDangNhap.addEventListener("submit", function (e) {
    e.preventDefault();
    var f = new FormData(fDangNhap);
    var sdt = String(f.get("sdt") || "").trim(), ma = String(f.get("ma") || "").trim(), nd = String(f.get("noi_dung") || "").trim();
    if (!sdt || !/^\d{6}$/.test(ma) || !nd) { bao(msgDN, "Vui lòng nhập số điện thoại, mã bí mật gồm 6 chữ số và nội dung tin nhắn.", true); return; }
    if (Date.now() - t0 < 3000) { bao(msgDN, "Bạn gửi quá nhanh, vui lòng kiểm tra lại rồi gửi.", true); return; }
    nutMoi.disabled = true; bao(msgDN, "Đang gửi…", false);
    post(D.dangNhapUrl, { sdt: sdt, ten: f.get("ten"), ma: ma, website: f.get("website") }).then(function (d) {
      if (!d.ok) { bao(msgDN, d.loi || "Không đăng nhập được.", true); nutMoi.disabled = false; return null; }
      tName.textContent = d.ten || "";
      return post(D.guiUrl, { noi_dung: nd, loai: f.get("loai"), ngu_canh: D.nguCanh, ngu_canh_url: D.nguCanhUrl, website: f.get("website") }).then(function (g) {
        if (!g.ok) { bao(msgDN, g.loi || "Không gửi được tin nhắn.", true); nutMoi.disabled = false; return; }
        fDangNhap.reset(); batDau(); themTin(g.tin);
        // tải toàn bộ cuộc trò chuyện cũ (nếu là khách quay lại)
        fetch(D.tinUrl + "?sau=0", { credentials: "same-origin" }).then(function (r) { return r.json(); }).then(function (h) {
          if (h && h.ok) { msgs.innerHTML = ""; cuoiId = 0; themTin(h.tin); msgs.scrollTop = msgs.scrollHeight; }
        });
        nutMoi.disabled = false;
      });
    }).catch(function () { bao(msgDN, "Không kết nối được, vui lòng thử lại.", true); nutMoi.disabled = false; });
  });

  // ── Gửi tin tiếp ──
  var msgChat = document.getElementById("htMsgChat"), nutGui = document.getElementById("htGuiTiep");
  function guiTiep() {
    var f = new FormData(fGui), nd = String(f.get("noi_dung") || "").trim();
    if (!nd) return;
    nutGui.disabled = true;
    post(D.guiUrl, { noi_dung: nd, loai: D.loai, ngu_canh: D.nguCanh, ngu_canh_url: D.nguCanhUrl, website: f.get("website") }).then(function (d) {
      if (d.ok) { fGui.elements.noi_dung.value = ""; msgChat.textContent = ""; themTin(d.tin); msgs.scrollTop = msgs.scrollHeight; var c = fGui.querySelector(".ht-context"); if (c) { c.remove(); D.nguCanh = ""; D.nguCanhUrl = ""; } }
      else if (d._ma === 401) { vaoManHinhDangNhap(); bao(document.getElementById("htMsgDangNhap"), d.loi, true); }
      else bao(msgChat, d.loi || "Không gửi được.", true);
    }).catch(function () { bao(msgChat, "Không kết nối được, vui lòng thử lại.", true); }).then(function () { nutGui.disabled = false; });
  }
  fGui.addEventListener("submit", function (e) { e.preventDefault(); guiTiep(); });
  fGui.elements.noi_dung.addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); guiTiep(); } });

  document.getElementById("htThoat").addEventListener("click", function () {
    post(D.thoatUrl).then(function () { location.href = location.pathname; });
  });
})();
