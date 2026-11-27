/* Trang Bài viết: (1) slide 3 bài ưu tiên  (2) mục lục + sao chép liên kết + in ở trang chi tiết.
   Không phụ thuộc thư viện. Slide có nút Tạm dừng (WCAG 2.2.2), dừng khi rê chuột / đang focus / tab ẩn,
   tắt hẳn tự chuyển khi người dùng bật "giảm chuyển động". Không có hiệu ứng hiện ra khi cuộn. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------------- Slide ---------------- */
  document.querySelectorAll('[data-bvx-slider]').forEach(function (root) {
    var slides = [].slice.call(root.querySelectorAll('.bvx-slide'));
    var dots = [].slice.call(root.querySelectorAll('.bvx-dot'));
    var stage = root.querySelector('.bvx-hero__stage');
    var toggle = root.querySelector('[data-act="toggle"]');
    if (slides.length < 2) return;

    var ms = parseInt(root.getAttribute('data-ms'), 10) || 7000;
    var cur = 0, timer = null, userPaused = false, hover = false, focusIn = false, touchX = null;
    root.style.setProperty('--bvx-ms', ms + 'ms');
    if (reduce) root.setAttribute('data-static', '');

    function running() { return !reduce && !userPaused && !hover && !focusIn && !document.hidden; }

    function restartBar() {                       // chạy lại thanh tiến độ của chấm đang chọn
      var d = dots[cur];
      if (!d) return;
      d.classList.remove('is-active'); void d.offsetWidth; d.classList.add('is-active');
    }
    function schedule() {
      clearTimeout(timer);
      if (running()) {
        root.removeAttribute('data-paused');
        timer = setTimeout(function () { show(cur + 1); }, ms);
      } else if (!reduce) {
        root.setAttribute('data-paused', '');
      }
    }
    function show(i, byUser) {
      cur = (i + slides.length) % slides.length;
      slides.forEach(function (s, k) {
        var on = k === cur;
        s.classList.toggle('is-active', on);
        if (on) { s.removeAttribute('inert'); s.removeAttribute('aria-hidden'); }
        else { s.setAttribute('inert', ''); s.setAttribute('aria-hidden', 'true'); }
      });
      dots.forEach(function (d, k) {
        var on = k === cur;
        d.classList.remove('is-active');
        if (on) { void d.offsetWidth; d.classList.add('is-active'); d.setAttribute('aria-current', 'true'); }
        else d.removeAttribute('aria-current');
      });
      if (stage) stage.setAttribute('aria-live', byUser || !running() ? 'polite' : 'off');
      schedule();
    }

    dots.forEach(function (d) { d.addEventListener('click', function () { show(parseInt(d.getAttribute('data-i'), 10), true); }); });
    var prev = root.querySelector('[data-act="prev"]'), next = root.querySelector('[data-act="next"]');
    if (prev) prev.addEventListener('click', function () { show(cur - 1, true); });
    if (next) next.addEventListener('click', function () { show(cur + 1, true); });
    if (toggle) toggle.addEventListener('click', function () {
      userPaused = !userPaused;
      toggle.setAttribute('aria-label', toggle.getAttribute(userPaused ? 'data-play' : 'data-pause'));
      restartBar(); schedule();
    });

    root.addEventListener('mouseenter', function () { hover = true; schedule(); });
    root.addEventListener('mouseleave', function () { hover = false; restartBar(); schedule(); });
    root.addEventListener('focusin', function () { focusIn = true; schedule(); });
    root.addEventListener('focusout', function (e) { if (!root.contains(e.relatedTarget)) { focusIn = false; restartBar(); schedule(); } });
    document.addEventListener('visibilitychange', function () { restartBar(); schedule(); });
    root.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') { show(cur - 1, true); e.preventDefault(); }
      else if (e.key === 'ArrowRight') { show(cur + 1, true); e.preventDefault(); }
    });
    // Vuốt ngang trên điện thoại
    stage.addEventListener('pointerdown', function (e) { if (e.pointerType === 'touch') touchX = e.clientX; });
    stage.addEventListener('pointerup', function (e) {
      if (touchX === null) return;
      var dx = e.clientX - touchX; touchX = null;
      if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1), true);
    });
    show(0);
  });

  /* ---------------- Trang chi tiết: mục lục, sao chép liên kết, in ---------------- */
  var body = document.getElementById('bvx-body'), toc = document.getElementById('bvx-toc');
  function slug(s) {
    return (s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'muc';
  }
  if (body && toc) {
    var hs = [].slice.call(body.querySelectorAll('h2, h3')).filter(function (h) { return h.textContent.trim(); });
    if (hs.length >= 3) {
      var list = toc.querySelector('.bvx-toc__list'), used = {}, links = [];
      hs.forEach(function (h) {
        var id = h.id || slug(h.textContent), base = id, n = 2;
        while (used[id] || (document.getElementById(id) && document.getElementById(id) !== h)) id = base + '-' + (n++);
        used[id] = true; h.id = id;
        var li = document.createElement('li'), a = document.createElement('a');
        if (h.tagName === 'H3') li.className = 'is-sub';
        a.href = '#' + id; a.textContent = h.textContent.trim();
        li.appendChild(a); list.appendChild(li); links.push({ h: h, a: a });
      });
      toc.hidden = false;
      if ('IntersectionObserver' in window) {                 // đánh dấu mục đang đọc (không có chuyển động)
        var obs = new IntersectionObserver(function (entries) {
          entries.forEach(function (en) {
            if (!en.isIntersecting) return;
            links.forEach(function (l) { if (l.h === en.target) l.a.setAttribute('aria-current', 'true'); else l.a.removeAttribute('aria-current'); });
          });
        }, { rootMargin: '-90px 0px -65% 0px' });
        links.forEach(function (l) { obs.observe(l.h); });
      }
    }
  }

  document.querySelectorAll('.bvx-tool').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var act = btn.getAttribute('data-act');
      if (act === 'print') { window.print(); return; }
      if (act !== 'copy') return;
      var url = location.href.split('#')[0], label = btn.querySelector('span'), old = label.textContent;
      function xong() {
        btn.classList.add('is-done'); label.textContent = btn.getAttribute('data-ok') || 'Đã sao chép'; btn.setAttribute('aria-live', 'polite');
        setTimeout(function () { btn.classList.remove('is-done'); label.textContent = old; }, 2200);
      }
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(xong, function () { window.prompt('Sao chép liên kết:', url); });
      else { var t = document.createElement('textarea'); t.value = url; t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); t.select();
        try { document.execCommand('copy'); xong(); } catch (e) { window.prompt('Sao chép liên kết:', url); } document.body.removeChild(t); }
    });
  });
})();
