// Nút đăng nhập hoạt hình:
// người que ngó trái -> ngó phải -> cửa mở -> bước vào cửa -> cửa đóng -> vào trang quản trị.
// Nhân vật bắt đầu ngó ngay khi bấm (trong lúc server kiểm tra). Chỉ đi tiếp khi đăng nhập
// THÀNH CÔNG; sai mật khẩu thì hiện lỗi như bình thường.
(function () {
  var btn = document.getElementById("liBtn");
  if (!btn) return;
  var form = btn.form;
  var person = document.getElementById("liPerson");
  var leaf = document.getElementById("liLeaf");
  var label = document.getElementById("liLabel");
  var chuoiGoc = label.textContent;

  // Phải khớp với --T, --cycles, --LOOK trong style.css
  var CYCLE = 900, CYCLES = 3, LOOK = 1600;
  var WALK = CYCLE * CYCLES;
  var busy = false;
  var tBam = 0;

  function batDauNgo() {
    label.textContent = "Đang đăng nhập";
    person.classList.add("looking");
  }

  function diVaoCua(url) {
    var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { window.location.href = url; return; }

    // đợi ngó xong (nếu server trả lời nhanh hơn thì chờ cho đủ chuyển động)
    var doi = Math.max(0, LOOK - (Date.now() - tBam));

    setTimeout(function () { leaf.classList.remove("closed"); }, doi);            // cửa mở (550ms)
    setTimeout(function () {                                                      // bước vào
      person.classList.add("walking");
      person.style.transition = "transform " + WALK + "ms linear";
      person.style.transform = "translate(16px,0px) rotate(0deg)";
    }, doi + 400);
    setTimeout(function () {                                                      // vào tới cửa -> đóng cửa
      person.classList.remove("walking");
      leaf.classList.add("closed");
    }, doi + 400 + WALK);
    setTimeout(function () { window.location.href = url; }, doi + 400 + WALK + 700);
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (busy) return;
    busy = true;
    btn.disabled = true;
    tBam = Date.now();
    batDauNgo();

    fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "same-origin",
      redirect: "follow"
    }).then(function (res) {
      var vaoDuoc = res.redirected && res.url.indexOf("/dang-nhap") === -1;
      if (vaoDuoc) {
        diVaoCua(res.url);
      } else {
        // Sai mật khẩu / tài khoản khoá: hiện lại trang với thông báo lỗi từ server
        res.text().then(function (html) {
          document.open(); document.write(html); document.close();
        });
      }
    }).catch(function () {
      // Lỗi mạng: gửi form theo cách thường
      busy = false; btn.disabled = false;
      person.classList.remove("looking"); label.textContent = chuoiGoc;
      form.submit();
    });
  });
})();
