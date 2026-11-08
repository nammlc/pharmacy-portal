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

  // Tiếng rơi: "aaaa~" kéo dài (giọng tổng hợp bằng formant nguyên âm "a"),
  // hoảng lên rồi trầm xuống + nhỏ dần như đang rơi xa, kết thúc bằng tiếng "bịch" xa xa.
  var SCREAM = 1.5;          // giây
  function amThanhNga() {
    if (!audioCtx || VOLUME <= 0) return;
    try {
      var t = audioCtx.currentTime + 0.02;
      var master = audioCtx.createGain();
      master.gain.value = VOLUME;
      master.connect(audioCtx.destination);

      // nguồn giọng: sóng răng cưa + rung nhẹ (vibrato) cho tự nhiên
      var voice = audioCtx.createOscillator();
      voice.type = "sawtooth";
      voice.frequency.setValueAtTime(470, t);
      voice.frequency.linearRampToValueAtTime(640, t + 0.14);              // giật mình, vút lên
      voice.frequency.exponentialRampToValueAtTime(290, t + SCREAM);       // trầm dần khi rơi xa

      var lfo = audioCtx.createOscillator(), lfoGain = audioCtx.createGain();
      lfo.frequency.value = 6;
      lfoGain.gain.setValueAtTime(6, t);
      lfoGain.gain.linearRampToValueAtTime(20, t + SCREAM);                // càng về sau càng run
      lfo.connect(lfoGain); lfoGain.connect(voice.frequency);

      // độ to: vào nhanh, giữ, rồi nhỏ dần
      var env = audioCtx.createGain();
      env.gain.setValueAtTime(0.0001, t);
      env.gain.exponentialRampToValueAtTime(0.32, t + 0.05);
      env.gain.setValueAtTime(0.32, t + 0.35);
      env.gain.exponentialRampToValueAtTime(0.0001, t + SCREAM);
      env.connect(master);

      // 3 formant của nguyên âm "a" (F1~800, F2~1250, F3~2600 Hz)
      [[800, 6, 1.0], [1250, 8, 0.7], [2600, 10, 0.3]].forEach(function (f) {
        var bp = audioCtx.createBiquadFilter(), g = audioCtx.createGain();
        bp.type = "bandpass"; bp.frequency.value = f[0]; bp.Q.value = f[1];
        g.gain.value = f[2];
        voice.connect(bp); bp.connect(g); g.connect(env);
      });

      voice.start(t); lfo.start(t);
      voice.stop(t + SCREAM + 0.05); lfo.stop(t + SCREAM + 0.05);

      // "bịch" nhỏ, xa xa khi chạm đất
      var tb = t + SCREAM + 0.02;
      var o2 = audioCtx.createOscillator(), g2 = audioCtx.createGain();
      o2.type = "sine";
      o2.frequency.setValueAtTime(130, tb);
      o2.frequency.exponentialRampToValueAtTime(40, tb + 0.18);
      g2.gain.setValueAtTime(0.0001, tb);
      g2.gain.exponentialRampToValueAtTime(0.28, tb + 0.01);
      g2.gain.exponentialRampToValueAtTime(0.0001, tb + 0.22);
      o2.connect(g2); g2.connect(master);
      o2.start(tb); o2.stop(tb + 0.25);
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
      person.style.transition = "transform 1100ms cubic-bezier(.55,0,1,.45),opacity 500ms ease 600ms";
      person.style.transform = "translate(18px,34px) rotate(80deg)";
      amThanhNga();
      person.style.opacity = "0";
    }, WALK + 940);
    setTimeout(function () {                  // xong -> gọi route đăng xuất thật
      window.location.href = url;
    }, WALK + 940 + 1900);
  });
})();
