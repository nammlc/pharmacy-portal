// Nút đăng xuất hoạt hình: nhân vật đi vào cửa, cửa đóng, rung, rơi -> rồi mới chuyển trang.
(function () {
  var btn = document.getElementById("loBtn");
  if (!btn) return;
  var person = document.getElementById("loPerson");
  var leaf = document.getElementById("loLeaf");
  var label = document.getElementById("loLabel");
  var url = btn.getAttribute("href");

  // Phải khớp với --T và --cycles trong style.css
  var CYCLE = 900, CYCLES = 3;
  var WALK = CYCLE * CYCLES;
  var playing = false;

  // ===== Âm thanh (tổng hợp bằng Web Audio, không cần file mp3) =====
  var VOLUME = 0.6;          // 0 = tắt tiếng, 1 = to nhất
  var audioCtx = null;

  function moKhoaAm() {      // gọi ngay lúc bấm để trình duyệt cho phép phát tiếng
    try {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      audioCtx = audioCtx || new AC();
      if (audioCtx.state === "suspended") audioCtx.resume();
    } catch (e) {}
  }

  // Tiếng rơi: "wiiiu" trượt xuống rồi "bịch" nhẹ khi chạm đất
  function amThanhNga() {
    if (!audioCtx || VOLUME <= 0) return;
    try {
      var t = audioCtx.currentTime + 0.02;
      var master = audioCtx.createGain();
      master.gain.value = VOLUME;
      master.connect(audioCtx.destination);

      // 1) tiếng vút rơi (slide whistle đi xuống), dài ~0.75s
      var o1 = audioCtx.createOscillator(), g1 = audioCtx.createGain();
      o1.type = "triangle";
      o1.frequency.setValueAtTime(900, t);
      o1.frequency.exponentialRampToValueAtTime(170, t + 0.75);
      g1.gain.setValueAtTime(0.0001, t);
      g1.gain.exponentialRampToValueAtTime(0.16, t + 0.05);
      g1.gain.exponentialRampToValueAtTime(0.0001, t + 0.78);
      o1.connect(g1); g1.connect(master);
      o1.start(t); o1.stop(t + 0.8);

      // 2) tiếng "bịch" khi chạm đất
      var tb = t + 0.8;
      var o2 = audioCtx.createOscillator(), g2 = audioCtx.createGain();
      o2.type = "sine";
      o2.frequency.setValueAtTime(150, tb);
      o2.frequency.exponentialRampToValueAtTime(45, tb + 0.16);
      g2.gain.setValueAtTime(0.0001, tb);
      g2.gain.exponentialRampToValueAtTime(0.5, tb + 0.01);
      g2.gain.exponentialRampToValueAtTime(0.0001, tb + 0.2);
      o2.connect(g2); g2.connect(master);
      o2.start(tb); o2.stop(tb + 0.22);
    } catch (e) {}
  }

  btn.addEventListener("click", function (e) {
    e.preventDefault();
    if (playing) return;
    playing = true;
    moKhoaAm();

    // Người dùng tắt animation -> đăng xuất ngay
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.location.href = url;
      return;
    }

    label.textContent = "Đang đăng xuất";
    person.classList.add("walking");
    person.style.transition = "transform " + WALK + "ms linear";
    person.style.transform = "translate(16px,0px) rotate(0deg)";

    setTimeout(function () {                  // tới cửa -> đóng cửa
      person.classList.remove("walking");
      leaf.classList.add("closed");
    }, WALK);
    setTimeout(function () {                  // rung
      btn.classList.add("shake");
    }, WALK + 560);
    setTimeout(function () {                  // rơi xuống
      person.style.transition = "transform 850ms cubic-bezier(.55,0,1,.45),opacity 500ms ease 450ms";
      person.style.transform = "translate(18px,34px) rotate(80deg)";
      amThanhNga();
      person.style.opacity = "0";
    }, WALK + 940);
    setTimeout(function () {                  // xong -> gọi route đăng xuất thật
      window.location.href = url;
    }, WALK + 1800);
  });
})();
