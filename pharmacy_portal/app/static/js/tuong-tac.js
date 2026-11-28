// Trang Tương tác thuốc: ô "Hoạt chất thứ hai" chỉ hiện ra sau khi đã nhập hoạt chất thứ nhất.
// Không có JS thì trang vẫn dùng được: tra hoạt chất thứ nhất xong, ô thứ hai được server hiển thị sẵn.
(function () {
  "use strict";
  var q1 = document.getElementById("ttt-q");
  var q2 = document.getElementById("ttt-q2");
  var khung2 = q2 && q2.closest(".ttt-field");
  if (!q1 || !khung2) return;

  function cap_nhat() {
    var co_q1 = q1.value.trim() !== "";
    if (co_q1 && khung2.hidden) {
      khung2.hidden = false;
      khung2.classList.add("is-reveal");
    } else if (!co_q1 && q2.value.trim() === "" && !khung2.hidden) {
      khung2.hidden = true;                      // xoá hết ô 1 và ô 2 trống → ẩn lại
      khung2.classList.remove("is-reveal");
    }
  }

  ["input", "change", "goi-y-chon"].forEach(function (ev) { q1.addEventListener(ev, cap_nhat); });
  cap_nhat();
})();
