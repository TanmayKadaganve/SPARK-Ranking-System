(() => {
  "use strict";

  const filterForm = document.querySelector(".filter-bar");
  if (!filterForm) return;

  const search = filterForm.querySelector('input[name="q"]');
  const selects = filterForm.querySelectorAll("select");
  let searchTimer;

  // Search and filters are submitted to Django; the browser only provides a
  // quick interaction. The server remains the source of ranking/filter data.
  if (search) {
    search.addEventListener("input", () => {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(() => {
        const page = filterForm.querySelector('input[name="page"]');
        if (page) page.remove();
        filterForm.requestSubmit();
      }, 350);
    });
  }

  selects.forEach((select) => {
    select.addEventListener("change", () => {
      const page = filterForm.querySelector('input[name="page"]');
      if (page) page.remove();
      filterForm.requestSubmit();
    });
  });

  const tableScroll = document.querySelector(".table-scroll");
  if (tableScroll) {
    tableScroll.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight") tableScroll.scrollBy({ left: 160, behavior: "smooth" });
      if (event.key === "ArrowLeft") tableScroll.scrollBy({ left: -160, behavior: "smooth" });
    });
  }
})();
