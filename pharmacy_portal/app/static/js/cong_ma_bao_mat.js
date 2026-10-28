// Ô nhập mã 6 số: chỉ nhận chữ số, tự gửi đúng 1 lần khi đủ 6 số.
(function () {
  var o = document.getElementById("gateMa");
  var f = document.getElementById("gateForm");
  if (!o || !f) return;
  var da_gui = false;
  o.addEventListener("input", function () {
    var chiSo = o.value.replace(/\D/g, "").slice(0, 6);
    if (chiSo !== o.value) o.value = chiSo;
    if (chiSo.length === 6 && !da_gui) { da_gui = true; f.submit(); }
  });
  f.addEventListener("submit", function (e) {
    if (da_gui) { e.preventDefault(); return; }
    da_gui = true;
  });
})();
