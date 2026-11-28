/* Ô chọn hoạt chất có tìm kiếm NGAY TRONG khung sổ xuống (thay <select> thường).
   - Bấm vào ô -> khung sổ ra, con trỏ nằm sẵn ở ô tìm; gõ là lọc (không phân biệt dấu / hoa thường).
   - ↑ ↓ chọn, Enter xác nhận, Esc đóng.
   - Gõ tên chưa có -> dòng "＋ Thêm hoạt chất «…» vào hệ thống": thêm vào CSDL rồi chọn luôn.
   - <select> gốc vẫn nằm trong form (ẩn) nên form/WTForms hoạt động như cũ; không có JS thì vẫn dùng được select.
   Dùng:  HcChon.init([selectA, selectB], { themUrl: '...', csrf: '...' }) */
(function () {
  'use strict';
  var MAX = 100, dem = 0;

  function bd(s) { return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/\s+/g, ' ').trim(); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function init(selects, cfg) {
    // Kho dùng chung cho mọi ô: thêm hoạt chất ở ô này thì ô kia cũng thấy ngay
    var store = [], seen = {};
    selects.forEach(function (sel) {
      [].forEach.call(sel.options, function (o) { if (o.value !== '0' && o.value !== '' && !seen[o.value]) { seen[o.value] = 1; store.push({ v: o.value, t: o.text, n: bd(o.text) }); } });
    });
    var boxes = selects.map(function (sel) { return build(sel, store, cfg, selects); });
    boxes.forEach(function (b) { b.others = boxes; });
    return boxes;
  }

  function build(sel, store, cfg, allSelects) {
    var id = 'hcc' + (++dem), label = document.querySelector('label[for="' + sel.id + '"]');
    var root = el('div', 'hcc'), btn = el('button', 'hcc-btn'), val = el('span', 'hcc-val');
    btn.type = 'button'; btn.id = id + '-btn'; btn.setAttribute('role', 'combobox'); btn.setAttribute('aria-haspopup', 'listbox');
    btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', id + '-list');
    btn.appendChild(val);
    btn.insertAdjacentHTML('beforeend', '<svg class="hcc-chev" width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="m4 6 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>');
    var pop = el('div', 'hcc-pop'); pop.hidden = true;
    var sw = el('div', 'hcc-search'), q = el('input', 'hcc-q');
    sw.insertAdjacentHTML('beforeend', '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>');
    q.type = 'text'; q.placeholder = 'Gõ tên hoạt chất để tìm…'; q.autocomplete = 'off'; q.setAttribute('aria-label', 'Tìm hoạt chất');
    q.setAttribute('aria-controls', id + '-list'); q.setAttribute('aria-autocomplete', 'list');
    sw.appendChild(q);
    var list = el('ul', 'hcc-list'); list.id = id + '-list'; list.setAttribute('role', 'listbox');
    var foot = el('div', 'hcc-foot'); foot.setAttribute('aria-live', 'polite');
    pop.appendChild(sw); pop.appendChild(list); pop.appendChild(foot);
    root.appendChild(btn); root.appendChild(pop);
    sel.parentNode.insertBefore(root, sel.nextSibling);
    sel.hidden = true; sel.setAttribute('aria-hidden', 'true'); sel.tabIndex = -1;
    if (label) label.htmlFor = btn.id;

    var shown = [], active = -1, busy = false, self = { sel: sel };

    function textOf(v) { for (var i = 0; i < store.length; i++) if (store[i].v === v) return store[i].t; return ''; }
    function paintValue() {
      var t = sel.value && sel.value !== '0' ? textOf(sel.value) : '';
      val.textContent = t || '— Chọn hoạt chất —'; val.classList.toggle('is-empty', !t);
    }
    function otherValue() { var o = allSelects.filter(function (s) { return s !== sel; })[0]; return o ? o.value : ''; }

    function render() {
      var k = bd(q.value), words = k ? k.split(' ') : [], res = [];
      store.forEach(function (o) {
        if (!words.every(function (w) { return o.n.indexOf(w) !== -1; })) return;
        res.push({ o: o, r: o.n.indexOf(k) === 0 ? 0 : 1 });
      });
      res.sort(function (a, b) { return a.r - b.r || (a.o.n < b.o.n ? -1 : a.o.n > b.o.n ? 1 : 0); });
      var total = res.length; res = res.slice(0, MAX);
      list.innerHTML = ''; shown = [];
      var sv = otherValue();
      res.forEach(function (x) {
        var li = el('li', 'hcc-opt' + (x.o.v === sel.value ? ' is-selected' : ''), x.o.t);
        li.setAttribute('role', 'option'); li.id = id + '-o' + x.o.v; li.dataset.v = x.o.v;
        if (x.o.v === sel.value) li.setAttribute('aria-selected', 'true');
        if (sv && x.o.v === sv) { li.classList.add('is-other'); li.title = 'Đã chọn ở ô còn lại'; }
        list.appendChild(li); shown.push({ type: 'opt', v: x.o.v, li: li });
      });
      var exact = store.some(function (o) { return o.n === k; }), raw = q.value.replace(/\s+/g, ' ').trim();
      if (raw && !exact && cfg.themUrl) {
        var add = el('li', 'hcc-opt hcc-add', '＋ Thêm hoạt chất «' + raw + '» vào hệ thống');
        add.setAttribute('role', 'option'); add.id = id + '-add'; list.appendChild(add); shown.push({ type: 'add', li: add, ten: raw });
      }
      if (!res.length && !(raw && !exact && cfg.themUrl)) list.appendChild(el('li', 'hcc-none', 'Không có hoạt chất nào khớp.'));
      if (!foot.dataset.keep) foot.textContent = !total ? 'Hoạt chất này chưa có trong hệ thống.' : total > MAX ? 'Hiển thị ' + MAX + ' / ' + total + ' kết quả — gõ thêm để thu hẹp.' : (total + ' hoạt chất');
      setActive(res.length ? Math.max(0, shown.findIndex(function (s) { return s.type === 'opt' && s.v === sel.value; })) : (shown.length ? 0 : -1), true);
    }
    function setActive(i, noScroll) {
      active = i;
      shown.forEach(function (s, k) { s.li.classList.toggle('is-active', k === i); });
      if (i >= 0 && shown[i]) {
        q.setAttribute('aria-activedescendant', shown[i].li.id);
        if (!noScroll || shown[i].li.classList.contains('is-selected')) shown[i].li.scrollIntoView({ block: 'nearest' });
      } else q.removeAttribute('aria-activedescendant');
    }
    function open() {
      if (!pop.hidden) return;
      boxes_close_others(); pop.hidden = false; btn.setAttribute('aria-expanded', 'true'); delete foot.dataset.keep;
      q.value = ''; render(); q.focus();
    }
    function close(back) { if (pop.hidden) return; pop.hidden = true; btn.setAttribute('aria-expanded', 'false'); if (back) btn.focus(); }
    function boxes_close_others() { (self.others || []).forEach(function (b) { if (b !== self) b.close(); }); }
    function choose(v) {
      sel.value = v; paintValue(); close(true);
      sel.dispatchEvent(new Event('change', { bubbles: true }));
    }
    function themMoi(ten) {
      if (busy) return; busy = true; foot.dataset.keep = '1'; foot.textContent = 'Đang thêm…';
      var fd = new FormData(); fd.append('ten', ten);
      fetch(cfg.themUrl, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': cfg.csrf || '', 'Accept': 'application/json' } })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (x) {
          busy = false;
          if (!x.ok) { foot.textContent = (x.d && x.d.loi) || 'Không thêm được hoạt chất. Vui lòng thử lại.'; return; }
          var d = x.d, v = String(d.id);
          if (!store.some(function (o) { return o.v === v; })) {              // đưa vào kho + mọi <select>
            store.push({ v: v, t: d.ten, n: bd(d.ten) });
            allSelects.forEach(function (s) { var op = document.createElement('option'); op.value = v; op.text = d.ten; s.appendChild(op); });
          }
          foot.textContent = d.da_co ? 'Hoạt chất «' + d.ten + '» đã có sẵn — đã chọn.' : 'Đã thêm hoạt chất «' + d.ten + '» vào hệ thống và chọn.';
          choose(v);
        })
        .catch(function () { busy = false; foot.textContent = 'Lỗi kết nối. Hoạt chất chưa được thêm.'; });
    }
    function activate(i) {
      var s = shown[i]; if (!s) return;
      if (s.type === 'add') themMoi(s.ten); else choose(s.v);
    }

    btn.addEventListener('click', function () { pop.hidden ? open() : close(true); });
    btn.addEventListener('keydown', function (e) { if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); open(); } });
    q.addEventListener('input', function () { delete foot.dataset.keep; render(); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); if (shown.length) setActive((active + 1) % shown.length); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); if (shown.length) setActive((active - 1 + shown.length) % shown.length); }
      else if (e.key === 'Enter') { e.preventDefault(); if (active >= 0) activate(active); }
      else if (e.key === 'Escape') { e.preventDefault(); close(true); }
      else if (e.key === 'Tab') close(false);
    });
    list.addEventListener('mousedown', function (e) { e.preventDefault(); });          // giữ focus ở ô tìm
    list.addEventListener('click', function (e) { var li = e.target.closest('.hcc-opt'); if (li) activate([].indexOf.call(list.children, li)); });
    list.addEventListener('mousemove', function (e) { var li = e.target.closest('.hcc-opt'); if (li) { var i = [].indexOf.call(list.children, li); if (i !== active) setActive(i, true); } });
    document.addEventListener('mousedown', function (e) { if (!root.contains(e.target)) close(false); });
    sel.addEventListener('change', paintValue);       // ai đó đổi select bằng code -> cập nhật chữ hiển thị
    paintValue();
    self.close = close; self.open = open;
    return self;
  }
  window.HcChon = { init: init, bd: bd };
})();
