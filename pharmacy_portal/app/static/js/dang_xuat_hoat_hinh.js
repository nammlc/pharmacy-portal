// Nút đăng xuất hoạt hình: nhân vật đi vào cửa, cửa đóng, rung, rơi -> rồi mới chuyển trang.
(function () {
  var btn = document.getElementById("loBtn");
  if (!btn) return;
  var person = document.getElementById("loPerson");
  var leaf = document.getElementById("loLeaf");
  var label = document.getElementById("loLabel");
  var url = btn.getAttribute("href");

  // Phải khớp với --T và --cycles trong style.css
  var CYCLE = 900, CYCLES = 2;
  var WALK = CYCLE * CYCLES;
  var playing = false;

  btn.addEventListener("click", function (e) {
    e.preventDefault();
    if (playing) return;
    playing = true;

    // Người dùng tắt animation -> đăng xuất ngay
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.location.href = url;
      return;
    }

    label.textContent = "Đang đăng xuất";
    person.classList.add("walking");
    person.style.transition = "transform " + WALK + "ms linear";
    person.style.transform = "translate(9px,0px) rotate(0deg)";

    setTimeout(function () {                  // tới cửa -> đóng cửa
      person.classList.remove("walking");
      leaf.classList.add("closed");
    }, WALK);
    setTimeout(function () {                  // rung
      btn.classList.add("shake");
    }, WALK + 560);
    setTimeout(function () {                  // rơi xuống
      person.style.transition = "transform 850ms cubic-bezier(.55,0,1,.45),opacity 500ms ease 450ms";
      person.style.transform = "translate(11px,34px) rotate(80deg)";
      person.style.opacity = "0";
    }, WALK + 940);
    setTimeout(function () {                  // xong -> gọi route đăng xuất thật
      window.location.href = url;
    }, WALK + 1800);
  });
})();
