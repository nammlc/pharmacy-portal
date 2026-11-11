// Chat với khách (trang quản trị): gửi trả lời không tải lại trang + tự nhận tin mới của khách (~8 giây/lần).
(function () {
  var root = document.getElementById("admChat");
  if (!root) return;
  var D = root.dataset, msgs = document.getElementById("admMsgs"), form = document.getElementById("admGui");
  var nut = document.getElementById("admGuiNut"), baoEl = document.getElementById("admMsg"), cuoiId = 0, dangHoi = false;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function bao(t, loi) { baoEl.textContent = t; baoEl.className = "hd-msg " + (loi ? "hd-msg-loi" : "hd-msg-ok"); }
  Array.prototype.forEach.call(msgs.querySelectorAll(".ht-msg"), function (m) { cuoiId = Math.max(cuoiId, +m.dataset.id || 0); });
  msgs.scrollTop = msgs.scrollHeight;

  function veTin(t) {
    var b = el("div", "ht-msg ht-" + t.tu + " " + (t.tu === "khach" ? "ht-adm-khach" : "ht-adm-admin")); b.dataset.id = t.id;
    if (t.ngu_canh) {
      var c = el("div", "ht-msg-ctx"); c.appendChild(document.createTextNode("📎 "));
      if (t.ngu_canh_url && t.ngu_canh_url.charAt(0) === "/") { var a = el("a", "", t.ngu_canh + " ↗"); a.href = t.ngu_canh_url; a.target = "_blank"; a.rel = "noopener"; c.appendChild(a); }
      else c.appendChild(document.createTextNode(t.ngu_canh));
      b.appendChild(c);
    }
    b.appendChild(el("div", "ht-bubble", t.noi_dung));
    b.appendChild(el("div", "ht-meta", (t.tu === "admin" ? (t.ten || "Khoa Dược") : "Khách") + " · " + t.gio));
    return b;
  }
  function them(ds) {
    var gan = msgs.scrollTop + msgs.clientHeight >= msgs.scrollHeight - 80;
    var trong = document.getElementById("admTrong"); if (trong && ds.length) trong.remove();
    ds.forEach(function (t) { if (t.id > cuoiId) { msgs.appendChild(veTin(t)); cuoiId = t.id; } });
    if (ds.length && gan) msgs.scrollTop = msgs.scrollHeight;
  }

  function hoi() {
    if (dangHoi || document.hidden) return;
    dangHoi = true;
    fetch(D.tinUrl + "?sau=" + cuoiId, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (r.redirected || !r.ok) { return null; } return r.json(); })    // hết phiên → bị chuyển về trang đăng nhập
      .then(function (d) { if (d && d.ok) them(d.tin); })
      .catch(function () {}).then(function () { dangHoi = false; });
  }
  setInterval(hoi, 8000);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) hoi(); });

  function gui() {
    var nd = String(form.elements.noi_dung.value || "").trim();
    if (!nd) return;
    nut.disabled = true;
    fetch(D.guiUrl, { method: "POST", credentials: "same-origin",
                      headers: { "Content-Type": "application/json", "X-CSRFToken": D.csrf, "Accept": "application/json" },
                      body: JSON.stringify({ noi_dung: nd }) })
      .then(function (r) { return r.json().catch(function () { return { ok: false, loi: "Phiên đã hết hạn, hãy tải lại trang." }; }); })
      .then(function (d) { if (d.ok) { form.elements.noi_dung.value = ""; bao("", false); them(d.tin); msgs.scrollTop = msgs.scrollHeight; } else bao(d.loi || "Không gửi được.", true); })
      .catch(function () { bao("Không kết nối được.", true); }).then(function () { nut.disabled = false; });
  }
  form.addEventListener("submit", function (e) { e.preventDefault(); gui(); });
  form.elements.noi_dung.addEventListener("keydown", function (e) { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); gui(); } });
})();
