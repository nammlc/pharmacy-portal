/* Trang chủ: hiệu ứng khi cuộn — thanh tiến độ, xuất hiện so le, đếm số, hình khối trôi theo cuộn, ánh sáng theo con trỏ.
   Chỉ chạy khi không bật "giảm chuyển động". Nội dung luôn có sẵn trong HTML (progressive enhancement). */
(function () {
  "use strict";
  var giam = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (giam) return;
  document.documentElement.classList.add("sd-run");
  var raf = window.requestAnimationFrame || function (f) { return setTimeout(f, 16); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  /* ---- xuất hiện so le: phần tử cùng nhóm lệch nhau 1 nhịp ---- */
  $$("[data-sd-group]").forEach(function (nhom) {
    $$("[data-sd]", nhom).forEach(function (el, i) { el.style.setProperty("--d", i % 6); });
  });
  var cacAn = $$("[data-sd]");
  if ("IntersectionObserver" in window) {
    var quanSat = new IntersectionObserver(function (ds) {
      ds.forEach(function (d) {
        if (!d.isIntersecting) return;
        d.target.classList.add("is-in"); quanSat.unobserve(d.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    cacAn.forEach(function (el) { quanSat.observe(el); });
  } else { cacAn.forEach(function (el) { el.classList.add("is-in"); }); }

  /* ---- đếm số lên khi vào màn hình ---- */
  function dinhDang(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, "."); }
  var cacSo = $$("[data-count]");
  function dem(el) {
    var dich = parseInt(el.getAttribute("data-count"), 10);
    if (!dich || dich < 0) return;
    var t0 = null, tg = 1300;
    function buoc(t) {
      if (t0 === null) t0 = t;
      var p = Math.min(1, (t - t0) / tg), e = 1 - Math.pow(1 - p, 3);
      el.textContent = dinhDang(dich * e);
      if (p < 1) raf(buoc); else el.textContent = dinhDang(dich);
    }
    el.textContent = "0"; raf(buoc);
  }
  if ("IntersectionObserver" in window && cacSo.length) {
    var qs = new IntersectionObserver(function (ds) {
      ds.forEach(function (d) { if (d.isIntersecting) { dem(d.target); qs.unobserve(d.target); } });
    }, { threshold: 0.6 });
    cacSo.forEach(function (el) { qs.observe(el); });
  }

  /* ---- thanh tiến độ + hình khối trôi theo cuộn ---- */
  var bar = document.querySelector(".sd-progress");
  var cacTroi = $$("[data-sd-par]"), cho = false;
  function capNhat() {
    cho = false;
    var vh = window.innerHeight || 800, cao = document.documentElement.scrollHeight - vh;
    if (bar) bar.style.setProperty("--sp", cao > 0 ? Math.min(1, window.pageYOffset / cao).toFixed(4) : 0);
    cacTroi.forEach(function (el) {
      var r = el.parentNode.getBoundingClientRect();
      if (r.bottom < -200 || r.top > vh + 200) return;
      var he = parseFloat(el.getAttribute("data-sd-par")) || 0;
      el.style.transform = "translate3d(0," + ((r.top + r.height / 2 - vh / 2) * he).toFixed(1) + "px,0)";
    });
  }
  function yeuCau() { if (!cho) { cho = true; raf(capNhat); } }
  window.addEventListener("scroll", yeuCau, { passive: true });
  window.addEventListener("resize", yeuCau);
  capNhat();

  /* ---- ánh sáng màu đi theo con trỏ trên thẻ ---- */
  if (window.matchMedia && window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
    $$(".sd-card").forEach(function (the) {
      the.addEventListener("pointermove", function (e) {
        var r = the.getBoundingClientRect();
        the.style.setProperty("--mx", (e.clientX - r.left) + "px");
        the.style.setProperty("--my", (e.clientY - r.top) + "px");
      });
    });
  }
})();
