/* ============================================================
   Nén ảnh phía trình duyệt trước khi upload.
   Áp dụng tự động cho MỌI <input type="file"> có accept chứa "image"
   (kể cả các input ảnh sinh ra sau này trong màn hình "Nhập hàng loạt",
   vì dùng event delegation ở document thay vì gắn từng input).

   Vì sao cần: ảnh chụp từ điện thoại hiện nay thường 5-15 MB, trong khi
   server chỉ nhận tối đa MAX_CONTENT_LENGTH (xem config.py). Nén trước ở
   trình duyệt giúp: (1) không bị lỗi "413 Request Entity Too Large",
   (2) upload nhanh hơn, (3) tiết kiệm dung lượng lưu trữ trên Cloudinary.

   Cách làm: vẽ ảnh lên <canvas>, giới hạn cạnh dài nhất KICH_THUOC_TOI_DA,
   xuất lại thành JPEG với chất lượng CHAT_LUONG, rồi thay thế file gốc
   trong input bằng file đã nén (dùng DataTransfer).
   ============================================================ */
(function () {
  "use strict";

  var KICH_THUOC_TOI_DA = 1600;   // px - cạnh dài nhất sau khi nén
  var CHAT_LUONG = 0.82;          // chất lượng JPEG (0-1)
  var BO_QUA_NEU_NHO_HON = 300 * 1024; // < 300KB thì không cần nén nữa

  function dinhDangDungLuong(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function laHopThoaiAnh(input) {
    if (!input || input.type !== "file") return false;
    var accept = (input.getAttribute("accept") || "").toLowerCase();
    return accept.indexOf("image") !== -1;
  }

  function timHoacTaoTrangThai(input) {
    var el = input._nenAnhTrangThai;
    if (el) return el;
    el = document.createElement("small");
    el.className = "nen-anh-trang-thai";
    el.style.cssText = "display:block;margin-top:4px;font-size:12px;color:var(--text-muted, #777);";
    if (input.parentNode) {
      input.parentNode.insertBefore(el, input.nextSibling);
    }
    input._nenAnhTrangThai = el;
    return el;
  }

  function nenMotAnh(file) {
    return new Promise(function (resolve, reject) {
      // GIF (có thể là ảnh động) và ảnh đã đủ nhỏ thì giữ nguyên, khỏi nén.
      if (file.type === "image/gif" || file.size <= BO_QUA_NEU_NHO_HON) {
        resolve(file);
        return;
      }

      var urlTam = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        var rong = img.naturalWidth, cao = img.naturalHeight;
        var canhDaiNhat = Math.max(rong, cao);
        if (canhDaiNhat > KICH_THUOC_TOI_DA) {
          var ti_le = KICH_THUOC_TOI_DA / canhDaiNhat;
          rong = Math.round(rong * ti_le);
          cao = Math.round(cao * ti_le);
        }

        var canvas = document.createElement("canvas");
        canvas.width = rong;
        canvas.height = cao;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, rong, cao);
        URL.revokeObjectURL(urlTam);

        canvas.toBlob(
          function (blob) {
            if (!blob || blob.size >= file.size) {
              // Nén không hiệu quả (hiếm gặp) -> giữ file gốc cho an toàn.
              resolve(file);
              return;
            }
            var tenMoi = file.name.replace(/\.[^.]+$/, "") + ".jpg";
            var fileMoi = new File([blob], tenMoi, { type: "image/jpeg", lastModified: Date.now() });
            resolve(fileMoi);
          },
          "image/jpeg",
          CHAT_LUONG
        );
      };
      img.onerror = function () {
        URL.revokeObjectURL(urlTam);
        resolve(file); // đọc ảnh lỗi thì thôi, giữ file gốc, để server tự validate
      };
      img.src = urlTam;
    });
  }

  function xuLyInput(input) {
    var file = input.files && input.files[0];
    if (!file || !file.type || file.type.indexOf("image/") !== 0) return;

    var trangThai = timHoacTaoTrangThai(input);
    var dungLuongGoc = file.size;
    input.dataset.dangNen = "1";
    trangThai.textContent = "Đang nén ảnh...";

    nenMotAnh(file).then(function (fileMoi) {
      var dt = new DataTransfer();
      dt.items.add(fileMoi);
      input.files = dt.files;
      input.dataset.dangNen = "0";

      if (fileMoi.size < dungLuongGoc) {
        trangThai.textContent =
          "Đã nén ảnh: " + dinhDangDungLuong(dungLuongGoc) + " → " + dinhDangDungLuong(fileMoi.size);
      } else {
        trangThai.textContent = "";
      }
    });
  }

  document.addEventListener("change", function (e) {
    if (laHopThoaiAnh(e.target)) {
      xuLyInput(e.target);
    }
  });

  // An toàn: nếu người dùng bấm Lưu ngay trong lúc ảnh đang nén (hiếm khi xảy ra
  // vì nén rất nhanh), chặn submit lại và tự submit khi nén xong, tránh gửi
  // nhầm file gốc (chưa nén) lên server.
  document.addEventListener(
    "submit",
    function (e) {
      var form = e.target;
      if (!form || !form.querySelectorAll) return;
      var dangNen = form.querySelector('input[type="file"][data-dang-nen="1"]');
      if (!dangNen) return;

      e.preventDefault();
      var cho = setInterval(function () {
        if (dangNen.dataset.dangNen !== "1") {
          clearInterval(cho);
          form.submit();
        }
      }, 150);
    },
    true
  );
})();
