// Khối hỏi đáp công khai: tải ý kiến đã duyệt (phân trang) + gửi ý kiến mới (chờ Khoa Dược duyệt).
(function () {
  var root = document.getElementById("hoi-dap");
  if (!root) return;
  var loai = root.dataset.loai, id = root.dataset.id, api = root.dataset.api, csrf = root.dataset.csrf;
  var list = document.getElementById("hdList"), more = document.getElementById("hdMore"), count = document.getElementById("hdCount");
  var form = document.getElementById("hdForm"), msg = document.getElementById("hdMsg"), send = document.getElementById("hdSend");
  var trang = 0, daVe = 0, tong = 0, moFormLuc = Date.now();

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;                 // textContent: nội dung người dùng không bao giờ được hiểu là HTML
    return e;
  }

  function veMuc(m) {
    var box = el("article", "hd-item");
    var head = el("div", "hd-item-head");
    head.appendChild(el("span", "hd-avatar", (m.ten || "?").trim().charAt(0).toUpperCase()));
    var who = el("div");
    who.appendChild(el("strong", "", m.ten));
    who.appendChild(el("small", "", " · " + m.ngay));
    head.appendChild(who);
    box.appendChild(head);
    box.appendChild(el("p", "hd-item-body", m.noi_dung));
    if (m.tra_loi) {
      var r = el("div", "hd-reply");
      var rh = el("div", "hd-reply-head");
      rh.appendChild(el("strong", "", "Khoa Dược"));
      rh.appendChild(el("span", "hd-badge", "Đã trả lời"));
      if (m.ngay_tra_loi) rh.appendChild(el("small", "", " · " + m.ngay_tra_loi));
      r.appendChild(rh);
      r.appendChild(el("p", "hd-item-body", m.tra_loi));
      box.appendChild(r);
    }
    return box;
  }

  function tai(lanDau) {
    trang += 1;
    fetch(api + "?loai=" + encodeURIComponent(loai) + "&id=" + encodeURIComponent(id) + "&trang=" + trang, { headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) { list.innerHTML = ""; list.appendChild(el("p", "hd-empty", "Không tải được ý kiến.")); return; }
        if (lanDau) list.innerHTML = "";
        tong = d.tong; daVe += d.muc.length;
        d.muc.forEach(function (m) { list.appendChild(veMuc(m)); });
        if (!daVe) list.appendChild(el("p", "hd-empty", "Chưa có ý kiến nào. Hãy là người đầu tiên đặt câu hỏi."));
        count.textContent = tong ? "(" + tong + ")" : "";
        more.hidden = !d.co_them;
      })
      .catch(function () { if (lanDau) { list.innerHTML = ""; list.appendChild(el("p", "hd-empty", "Không tải được ý kiến.")); } });
  }
  more.addEventListener("click", function () { tai(false); });
  tai(true);                                              // tải sớm để nút "Lịch sử hỏi đáp" hiện được số ý kiến

  // 2 ngăn độc lập (có thể mở cùng lúc): bấm nút nào thì xổ / thu gọn ngăn đó
  [["hdTabList", "hdPanelList"], ["hdTabAsk", "hdPanelAsk"]].forEach(function (c) {
    var nut = document.getElementById(c[0]), ngan = document.getElementById(c[1]);
    nut.addEventListener("click", function () {
      var mo = ngan.hidden;
      ngan.hidden = !mo;
      nut.setAttribute("aria-expanded", mo ? "true" : "false");
      if (mo && c[1] === "hdPanelAsk") { moFormLuc = Date.now(); form.elements.ten.focus({ preventScroll: true }); }
    });
  });

  function bao(text, loi) { msg.textContent = text; msg.className = "hd-msg " + (loi ? "hd-msg-loi" : "hd-msg-ok"); }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var f = new FormData(form);
    var body = {
      loai: loai, id: id, ten: f.get("ten"), sdt: f.get("sdt"), noi_dung: f.get("noi_dung"), website: f.get("website"),
      thoi_gian_dien: (Date.now() - moFormLuc) / 1000
    };
    if (!String(body.ten || "").trim() || !String(body.sdt || "").trim() || !String(body.noi_dung || "").trim()) {
      bao("Vui lòng điền đủ họ tên, số điện thoại và nội dung.", true); return;
    }
    send.disabled = true; bao("Đang gửi…", false);
    fetch(api, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, "Accept": "application/json" },
                 credentials: "same-origin", body: JSON.stringify(body) })
      .then(function (r) { return r.json().catch(function () { return { ok: false, loi: "Có lỗi xảy ra, vui lòng tải lại trang." }; }); })
      .then(function (d) {
        if (d.ok) { form.elements.noi_dung.value = ""; moFormLuc = Date.now(); bao(d.thong_bao, false); }
        else bao(d.loi || "Không gửi được, vui lòng thử lại.", true);
      })
      .catch(function () { bao("Không kết nối được, vui lòng thử lại.", true); })
      .then(function () { send.disabled = false; });
  });
})();
