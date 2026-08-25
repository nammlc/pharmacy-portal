document.addEventListener("DOMContentLoaded", function () {
  var dropdown = document.getElementById("navDropdown");
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("mainNav");

  if (!dropdown || !toggle || !nav) return;

  function openMenu() {
    nav.classList.add("open");
    dropdown.setAttribute("data-open", "true");
    toggle.setAttribute("aria-expanded", "true");
  }

  function closeMenu() {
    nav.classList.remove("open");
    dropdown.setAttribute("data-open", "false");
    toggle.setAttribute("aria-expanded", "false");
  }

  toggle.addEventListener("click", function (e) {
    e.stopPropagation();
    if (nav.classList.contains("open")) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  // Đóng menu khi bấm ra ngoài
  document.addEventListener("click", function (e) {
    if (!dropdown.contains(e.target)) {
      closeMenu();
    }
  });

  // Đóng menu khi chọn 1 mục
  nav.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", closeMenu);
  });

  // Đóng menu khi nhấn Esc
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMenu();
  });
});

/* ============================================================
   ADMIN PANEL — sidebar mobile (drawer) + dropdown tài khoản
   ============================================================ */
document.addEventListener("DOMContentLoaded", function () {
  var sidebar = document.getElementById("adminSidebar");
  var overlay = document.getElementById("adminOverlay");
  var menuBtn = document.getElementById("adminMenuBtn");

  if (sidebar && overlay && menuBtn) {
    function openSidebar() {
      sidebar.classList.add("is-open");
      overlay.classList.add("is-open");
      menuBtn.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    }
    function closeSidebar() {
      sidebar.classList.remove("is-open");
      overlay.classList.remove("is-open");
      menuBtn.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }
    menuBtn.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) closeSidebar();
      else openSidebar();
    });
    overlay.addEventListener("click", closeSidebar);
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", closeSidebar);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeSidebar();
    });
    // Đóng drawer khi resize lên desktop (tránh kẹt trạng thái mở)
    window.addEventListener("resize", function () {
      if (window.innerWidth > 800) closeSidebar();
    });
  }

  var userBtn = document.getElementById("adminUserBtn");
  var userDropdown = document.getElementById("adminUserDropdown");

  if (userBtn && userDropdown) {
    function openUserMenu() {
      userDropdown.classList.add("is-open");
      userBtn.setAttribute("aria-expanded", "true");
    }
    function closeUserMenu() {
      userDropdown.classList.remove("is-open");
      userBtn.setAttribute("aria-expanded", "false");
    }
    userBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (userDropdown.classList.contains("is-open")) closeUserMenu();
      else openUserMenu();
    });
    document.addEventListener("click", function (e) {
      if (!userDropdown.contains(e.target) && e.target !== userBtn) closeUserMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeUserMenu();
    });
  }
});
