/**
 * Dán ảnh từ clipboard (Ctrl+V) vào các ô upload ảnh trong trang admin.
 *
 * Cách dùng: đặt 1 phần tử ".anh-paste-zone" ngay dưới input[type=file],
 * kèm data-target-input trỏ tới name của input đó. Ví dụ:
 *
 *   <input type="file" name="file_anh" ...>
 *   <div class="anh-paste-zone" tabindex="0" data-target-input="file_anh">
 *     📋 Bấm vào đây rồi Ctrl+V để dán ảnh
 *   </div>
 *
 * Khi người dùng copy ảnh (chụp màn hình, copy từ web, từ Excel...) rồi
 * Ctrl+V, script sẽ gán ảnh đó vào input[type=file] tương ứng (dùng
 * DataTransfer) và bắn sự kiện "change" để preview có sẵn của form tự
 * chạy — không cần sửa gì ở backend.
 */
(function () {
  document.addEventListener("DOMContentLoaded", function () {
    var vungDan = Array.prototype.slice.call(document.querySelectorAll(".anh-paste-zone"));
    if (!vungDan.length) return;

    var vungDangChon = vungDan[0];
    danhDauVungDangChon(vungDangChon);

    vungDan.forEach(function (vung) {
      vung.addEventListener("click", function () { chonVung(vung); });
      vung.addEventListener("focus", function () { chonVung(vung); });
    });

    function chonVung(vung) {
      vungDangChon = vung;
      danhDauVungDangChon(vung);
    }

    function danhDauVungDangChon(vungChon) {
      vungDan.forEach(function (v) {
        v.classList.toggle("is-active-zone", vungDan.length > 1 && v === vungChon);
      });
    }

    document.addEventListener("paste", function (event) {
      // Không can thiệp khi đang dán vào ô soạn thảo Quill hoặc vùng contenteditable khác
      var phanTuDangFocus = document.activeElement;
      if (phanTuDangFocus && phanTuDangFocus.closest(".ql-editor, [contenteditable='true']")) {
        return;
      }

      var duLieu = event.clipboardData || window.clipboardData;
      if (!duLieu) return;

      var fileAnh = timAnhTrongClipboard(duLieu);
      if (!fileAnh) return; // không có ảnh trong clipboard -> để trình duyệt xử lý dán bình thường (vd dán text)

      event.preventDefault();

      var vungDich = vungDangChon || vungDan[0];
      var tenInput = vungDich.getAttribute("data-target-input");
      var input = document.querySelector('input[type="file"][name="' + tenInput + '"]');
      if (!input) return;

      var duoiFile = (fileAnh.type.split("/")[1] || "png").replace("jpeg", "jpg");
      var fileDatTen = new File([fileAnh], "dan-clipboard-" + Date.now() + "." + duoiFile, {
        type: fileAnh.type,
      });

      var danhSachFile = new DataTransfer();
      danhSachFile.items.add(fileDatTen);
      input.files = danhSachFile.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));

      baoDaDan(vungDich);
    });

    function timAnhTrongClipboard(duLieu) {
      if (duLieu.items) {
        for (var i = 0; i < duLieu.items.length; i++) {
          var muc = duLieu.items[i];
          if (muc.kind === "file" && muc.type.indexOf("image/") === 0) {
            return muc.getAsFile();
          }
        }
      }
      if (duLieu.files && duLieu.files.length) {
        for (var j = 0; j < duLieu.files.length; j++) {
          if (duLieu.files[j].type.indexOf("image/") === 0) return duLieu.files[j];
        }
      }
      return null;
    }

    function baoDaDan(vung) {
      var chuGoc = vung.getAttribute("data-text-goc") || vung.innerHTML;
      vung.setAttribute("data-text-goc", chuGoc);
      vung.classList.add("is-flash");
      vung.innerHTML = '<span class="anh-paste-zone-icon">&#10003;</span> Đã dán ảnh từ clipboard!';
      setTimeout(function () {
        vung.classList.remove("is-flash");
        vung.innerHTML = chuGoc;
      }, 1800);
    }
  });
})();
