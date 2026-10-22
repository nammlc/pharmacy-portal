// Banner hỏi cookie ẩn danh (pp_vid). Lưu lựa chọn trong cookie "pp_dongy" (1 năm):
//   "1" = đồng ý -> server đặt cookie pp_vid ở lần tải trang kế tiếp
//   "0" = từ chối -> server xoá pp_vid (nếu có); IP + từ khoá tra cứu vẫn được ghi
(function () {
  var banner = document.getElementById("ppCookie");
  if (!banner) return;
  var HAN = 60 * 60 * 24 * 365;

  function luu(giaTri) {
    document.cookie = "pp_dongy=" + giaTri + "; max-age=" + HAN + "; path=/; SameSite=Lax" +
      (location.protocol === "https:" ? "; Secure" : "");
    banner.hidden = true;
  }

  document.getElementById("ppCookieYes").addEventListener("click", function () { luu("1"); });
  document.getElementById("ppCookieNo").addEventListener("click", function () { luu("0"); });

  // "Xem chi tiết" cuộn xuống footer; thu banner xuống để không che nội dung
  var chiTiet = banner.querySelector(".pp-cookie-link");
  if (chiTiet) chiTiet.addEventListener("click", function () {
    var dich = document.getElementById("ppThongBaoDuLieu");
    if (dich) { dich.scrollIntoView({ behavior: "smooth", block: "center" }); }
  });

  // Link ở footer: mở lại banner để đổi lựa chọn
  var mo = document.getElementById("ppCookieMo");
  if (mo) mo.addEventListener("click", function (e) { e.preventDefault(); banner.hidden = false; });
})();
