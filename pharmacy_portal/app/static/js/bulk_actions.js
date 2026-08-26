// Xử lý chọn nhiều dòng + xoá hàng loạt cho các trang danh sách admin.
// Quy ước ID dùng chung trên mọi trang danh_sach.html có bật tính năng này:
//   #checkAll        checkbox "chọn tất cả" ở tiêu đề bảng
//   .js-row-check     checkbox từng dòng (name="ids", form="bulkDeleteForm")
//   #bulkDeleteForm  form ẩn POST tới route xoa-hang-loat
//   #bulkToolbar     thanh công cụ hiện khi có mục được chọn
//   #bulkCount       vùng hiển thị số lượng đã chọn
//   #bulkDeleteBtn   nút submit form bulkDeleteForm
//   #bulkClearBtn    nút bỏ chọn tất cả
document.addEventListener("DOMContentLoaded", function () {
  var checkAll = document.getElementById("checkAll");
  var toolbar = document.getElementById("bulkToolbar");
  var countEl = document.getElementById("bulkCount");
  var bulkForm = document.getElementById("bulkDeleteForm");
  var clearBtn = document.getElementById("bulkClearBtn");
  var deleteBtn = document.getElementById("bulkDeleteBtn");

  // Trang này không có tính năng xoá hàng loạt -> bỏ qua.
  if (!checkAll || !toolbar || !bulkForm) return;

  function rowChecks() {
    return Array.prototype.slice.call(document.querySelectorAll(".js-row-check"));
  }

  function refresh() {
    var checks = rowChecks();
    var checked = checks.filter(function (c) { return c.checked; });

    if (checked.length > 0) {
      toolbar.hidden = false;
      if (countEl) countEl.textContent = "Đã chọn " + checked.length + " mục";
      if (deleteBtn) deleteBtn.disabled = false;
    } else {
      toolbar.hidden = true;
      if (deleteBtn) deleteBtn.disabled = true;
    }

    checkAll.checked = checks.length > 0 && checked.length === checks.length;
    checkAll.indeterminate = checked.length > 0 && checked.length < checks.length;
  }

  checkAll.addEventListener("change", function () {
    rowChecks().forEach(function (c) { c.checked = checkAll.checked; });
    refresh();
  });

  document.addEventListener("change", function (e) {
    if (e.target && e.target.classList && e.target.classList.contains("js-row-check")) {
      refresh();
    }
  });

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      rowChecks().forEach(function (c) { c.checked = false; });
      refresh();
    });
  }

  bulkForm.addEventListener("submit", function (e) {
    var checked = rowChecks().filter(function (c) { return c.checked; });
    if (checked.length === 0) {
      e.preventDefault();
      return;
    }
    var xacNhan = "Xoá " + checked.length + " mục đã chọn? Hành động này không thể hoàn tác.";
    if (!window.confirm(xacNhan)) {
      e.preventDefault();
    }
  });

  refresh();
});
