// Ô nhập mã 6 số: chỉ nhận chữ số, tự gửi khi đủ 6 số.
(function () {
  var o = document.getElementById("gateMa");
  var f = document.getElementById("gateForm");
  if (!o || !f) return;
  o.addEventListener("input", function () {
    var chiSo = o.value.replace(/\D/g, "").slice(0, 6);
    if (chiSo !== o.value) o.value = chiSo;
    if (chiSo.length === 6) f.submit();
  });
})();
