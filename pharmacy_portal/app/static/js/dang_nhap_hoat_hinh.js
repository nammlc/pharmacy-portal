// Nút đăng nhập hoạt hình (ngược lại với đăng xuất):
// người trồi lên -> rung -> cửa mở -> đi ra ngoài -> vào trang quản trị.
// Chỉ chạy hiệu ứng khi đăng nhập THÀNH CÔNG; sai mật khẩu thì hiện lỗi như bình thường.
(function () {
  var btn = document.getElementById("liBtn");
  if (!btn) return;
  var form = btn.form;
  var person = document.getElementById("liPerson");
  var leaf = document.getElementById("liLeaf");
  var label = document.getElementById("liLabel");
  var chuoiGoc = label.textContent;

  // Phải khớp với --T và --cycles trong style.css
  var CYCLE = 900, CYCLES = 2;
  var WALK = CYCLE * CYCLES;
  var busy = false;

  function phatHieuUng(url) {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { window.location.href = url; return; }

    label.textContent = "Đang đăng nhập";

    // 1) trồi lên từ dưới (ngược với cú rơi của đăng xuất)
    person.style.transition = "none";
    person.style.opacity = "0";
    person.style.transform = "translate(11px,34px) rotate(80deg)";
    void person.offsetWidth;
    person.style.transition = "transform 850ms cubic-bezier(0,.55,.45,1),opacity 400ms ease";
    person.style.transform = "translate(9px,0px) rotate(0deg)";
    person.style.opacity = "1";

    setTimeout(function () { btn.classList.add("shake"); }, 900);            // 2) rung
    setTimeout(function () { leaf.classList.remove("closed"); }, 1340);      // 3) cửa mở
    setTimeout(function () {                                                 // 4) đi ra
      person.classList.add("walking");
      person.style.transition = "transform " + WALK + "ms linear";
      person.style.transform = "translate(0px,0px) rotate(0deg)";
    }, 1600);
    setTimeout(function () { window.location.href = url; }, 1600 + WALK + 100);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (busy) return;
    busy = true;
    btn.disabled = true;
    label.textContent = "Đang kiểm tra...";

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      redirect: "follow"
    }).then(function (res) {
      var vaoDuoc = res.redirected && res.url.indexOf("/dang-nhap") === -1;
      if (vaoDuoc) {
        phatHieuUng(res.url);
      } else {
        // Sai mật khẩu / tài khoản khoá: hiện lại trang với thông báo lỗi từ server
        res.text().then(function (html) {
          document.open(); document.write(html); document.close();
        });
      }
    }).catch(function () {
      // Lỗi mạng: gửi form theo cách thường
      busy = false; btn.disabled = false; label.textContent = chuoiGoc;
      form.submit();
    });
  });
})();
