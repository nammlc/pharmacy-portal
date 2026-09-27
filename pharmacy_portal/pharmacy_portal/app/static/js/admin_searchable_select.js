/* ============================================================
   Ô chọn gõ-để-tìm (searchable dropdown) dùng chung cho:
   1) <select data-searchable="1"> đơn (vd: Nhóm thuốc)
   2) Từng dòng trong khối "Hoạt chất" nhiều dòng ([data-hc-multi])
   Không phụ thuộc thư viện ngoài — thuần vanilla JS.
   ============================================================ */
(function () {
  "use strict";

  function chuanHoa(str) {
    // Bỏ dấu tiếng Việt để tìm kiếm không phân biệt dấu.
    return (str || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d");
  }

  /**
   * Biến 1 <select> thành ô gõ-để-tìm. Select gốc vẫn nằm trong DOM
   * (ẩn về mặt hình ảnh) nên vẫn submit form bình thường — không cần
   * đổi gì ở backend/WTForms.
   */
  function enhanceSearchableSelect(select, options) {
    if (!select || select.dataset.ssEnhanced === "1") {
      return select ? select._ssApi : null;
    }
    select.dataset.ssEnhanced = "1";
    options = options || {};

    var wrap = document.createElement("div");
    wrap.className = "ss-wrap";
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);
    select.classList.add("ss-native-select");
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");

    var input = document.createElement("input");
    input.type = "text";
    input.className = "ss-input";
    input.autocomplete = "off";
    input.spellcheck = false;
    input.placeholder =
      options.placeholder || select.getAttribute("data-placeholder") || "Gõ để tìm...";
    wrap.appendChild(input);

    var dropdown = document.createElement("div");
    dropdown.className = "ss-dropdown";
    dropdown.hidden = true;
    wrap.appendChild(dropdown);

    var visibleItems = [];
    var activeIndex = -1;

    function syncInputFromSelect() {
      var opt = select.options[select.selectedIndex];
      input.value = opt && opt.value !== "" ? opt.textContent : "";
    }
    syncInputFromSelect();

    function closeDropdown() {
      dropdown.hidden = true;
      activeIndex = -1;
    }

    function setActive(idx) {
      activeIndex = idx;
      visibleItems.forEach(function (it, i) {
        it.classList.toggle("is-active", i === activeIndex);
      });
      if (activeIndex >= 0 && visibleItems[activeIndex]) {
        visibleItems[activeIndex].scrollIntoView({ block: "nearest" });
      }
    }

    function choose(value, label) {
      if (select.value !== value) {
        select.value = value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      input.value = value === "" ? "" : label;
      closeDropdown();
    }

    function renderDropdown(filterText) {
      var q = chuanHoa(filterText);
      dropdown.innerHTML = "";
      visibleItems = [];

      Array.prototype.forEach.call(select.options, function (opt) {
        var text = opt.textContent;
        if (opt.value === "" && q) return; // ẩn "-- không chọn --" khi đang gõ tìm
        if (q && chuanHoa(text).indexOf(q) === -1) return;

        var item = document.createElement("div");
        item.className = "ss-option";
        if (opt.value === select.value && opt.value !== "") item.classList.add("is-selected");
        item.textContent = text;
        item.addEventListener("mousedown", function (e) {
          e.preventDefault(); // tránh input bị blur trước khi bắt sự kiện click
          choose(opt.value, text);
        });
        dropdown.appendChild(item);
        visibleItems.push(item);
      });

      if (!visibleItems.length) {
        var empty = document.createElement("div");
        empty.className = "ss-empty";
        empty.textContent = "Không tìm thấy kết quả";
        dropdown.appendChild(empty);
      }
      activeIndex = -1;
      dropdown.hidden = false;
    }

    input.addEventListener("focus", function () {
      renderDropdown(select.value ? "" : input.value);
      input.select(); // bôi đen chữ có sẵn để gõ là thay thế luôn, khỏi phải xoá tay
    });
    input.addEventListener("click", function () {
      if (dropdown.hidden) renderDropdown(select.value ? "" : input.value);
    });
    input.addEventListener("input", function () {
      renderDropdown(input.value);
    });
    input.addEventListener("keydown", function (e) {
      if (dropdown.hidden && (e.key === "ArrowDown" || e.key === "Enter")) {
        renderDropdown(input.value);
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActive(Math.min(activeIndex + 1, visibleItems.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActive(Math.max(activeIndex - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (activeIndex >= 0 && visibleItems[activeIndex]) {
          visibleItems[activeIndex].dispatchEvent(new MouseEvent("mousedown"));
        }
      } else if (e.key === "Escape") {
        closeDropdown();
        syncInputFromSelect();
      }
    });
    input.addEventListener("blur", function () {
      // Trễ 1 nhịp để sự kiện mousedown trên item kịp chạy trước khi đóng dropdown.
      window.setTimeout(function () {
        closeDropdown();
        syncInputFromSelect();
      }, 120);
    });

    var api = {
      refresh: function () {
        syncInputFromSelect();
      },
      select: select,
      input: input,
      wrap: wrap,
    };
    select._ssApi = api;
    return api;
  }

  /* ============================================================
     Khối "Hoạt chất" nhiều dòng: mỗi dòng 1 ô gõ-để-tìm, chọn xong
     dòng cuối thì hiện nút "+ Thêm hoạt chất" để thêm dòng mới.
     ============================================================ */
  function initHoatChatMulti(container) {
    var sourceSelect = container.querySelector(".hc-source-options");
    var rowsWrap = container.querySelector(".hc-rows");
    var addBtn = container.querySelector(".hc-add-btn");
    if (!sourceSelect || !rowsWrap || !addBtn) return;

    var fieldName = container.getAttribute("data-field-name") || "hoat_chat_ids";
    var placeholder = container.getAttribute("data-placeholder") || "Gõ để tìm...";

    var allOptions = Array.prototype.map.call(sourceSelect.options, function (opt) {
      return { value: opt.value, label: opt.textContent, checked: opt.dataset.checked === "1" };
    });

    function selectedValuesExcept(exceptSelect) {
      var vals = [];
      rowsWrap.querySelectorAll("select.hc-row-select").forEach(function (sel) {
        if (sel !== exceptSelect && sel.value !== "") vals.push(sel.value);
      });
      return vals;
    }

    function refreshRowOptions(rowSelect) {
      var used = selectedValuesExcept(rowSelect);
      var currentValue = rowSelect.value;
      rowSelect.innerHTML = "";

      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "-- Chọn hoạt chất --";
      rowSelect.appendChild(blank);

      allOptions.forEach(function (opt) {
        if (used.indexOf(opt.value) !== -1) return; // đã chọn ở dòng khác
        var o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        rowSelect.appendChild(o);
      });

      rowSelect.value = currentValue && used.indexOf(currentValue) === -1 ? currentValue : "";
      toggleName(rowSelect);
    }

    function refreshAllRows() {
      rowsWrap.querySelectorAll("select.hc-row-select").forEach(refreshRowOptions);
    }

    function toggleName(rowSelect) {
      // Dòng chưa chọn gì thì bỏ "name" để không submit giá trị rỗng lên server.
      if (rowSelect.value) {
        rowSelect.name = fieldName;
      } else {
        rowSelect.removeAttribute("name");
      }
    }

    function updateAddBtn() {
      var rows = rowsWrap.querySelectorAll(".hc-row");
      var lastRow = rows[rows.length - 1];
      var lastSelect = lastRow ? lastRow.querySelector("select.hc-row-select") : null;
      var totalChosen = selectedValuesExcept(null).length;
      var conCoTheChon = totalChosen < allOptions.length;
      addBtn.hidden = !(lastSelect && lastSelect.value !== "" && conCoTheChon);
    }

    function updateRemoveButtons() {
      var rows = rowsWrap.querySelectorAll(".hc-row");
      rows.forEach(function (row) {
        var btn = row.querySelector(".hc-remove-btn");
        if (btn) btn.hidden = rows.length <= 1;
      });
    }

    function createRow(initialValue) {
      var row = document.createElement("div");
      row.className = "hc-row";

      var select = document.createElement("select");
      select.className = "hc-row-select";
      row.appendChild(select);

      var removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "hc-remove-btn";
      removeBtn.title = "Xoá hoạt chất này";
      removeBtn.innerHTML = "&times;";
      row.appendChild(removeBtn);

      rowsWrap.appendChild(row);

      select.value = "";
      refreshRowOptions(select);
      if (initialValue) select.value = initialValue;
      toggleName(select);

      enhanceSearchableSelect(select, { placeholder: placeholder });

      select.addEventListener("change", function () {
        refreshAllRows();
        updateAddBtn();
      });

      removeBtn.addEventListener("click", function () {
        row.remove();
        if (!rowsWrap.querySelector(".hc-row")) {
          createRow(""); // luôn giữ ít nhất 1 dòng để chọn
        }
        refreshAllRows();
        updateAddBtn();
        updateRemoveButtons();
      });

      updateRemoveButtons();
      return row;
    }

    addBtn.addEventListener("click", function () {
      var row = createRow("");
      updateAddBtn();
      updateRemoveButtons();
      var input = row.querySelector(".ss-input");
      if (input) input.focus();
    });

    var checkedOptions = allOptions.filter(function (o) {
      return o.checked;
    });
    if (checkedOptions.length) {
      checkedOptions.forEach(function (o) {
        createRow(o.value);
      });
    } else {
      createRow("");
    }
    refreshAllRows();
    updateAddBtn();
    updateRemoveButtons();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("select[data-searchable]").forEach(function (sel) {
      enhanceSearchableSelect(sel);
    });
    document.querySelectorAll("[data-hc-multi]").forEach(function (el) {
      initHoatChatMulti(el);
    });
  });
})();
