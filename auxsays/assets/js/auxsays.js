document.addEventListener("DOMContentLoaded", () => {

  const search = document.getElementById("pf-search");
  const cards = Array.from(document.querySelectorAll(".pf-card"));

  const filterBtns = document.querySelectorAll("[data-filter]");
  const sortBtns = document.querySelectorAll("[data-sort]");

  let currentFilter = "all";
  let currentSort = "latest";

  function apply() {
    let visible = cards.filter(card => {
      const text = card.dataset.title + card.dataset.product + card.dataset.company;
      const matchSearch = !search.value || text.includes(search.value.toLowerCase());
      const matchFilter = currentFilter === "all" || card.dataset.category.includes(currentFilter);
      return matchSearch && matchFilter;
    });

    if (currentSort === "latest") {
      visible.sort((a,b)=> b.dataset.date - a.dataset.date);
    }

    if (currentSort === "alpha") {
      visible.sort((a,b)=> a.dataset.product.localeCompare(b.dataset.product));
    }

    if (currentSort === "risk") {
      visible.sort((a,b)=> (b.dataset.risk || 0) - (a.dataset.risk || 0));
    }

    const container = document.getElementById("pf-feed");
    container.innerHTML = "";
    visible.forEach(v => container.appendChild(v));
  }

  search?.addEventListener("input", apply);

  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b=>b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentFilter = btn.dataset.filter;
      apply();
    });
  });

  sortBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      sortBtns.forEach(b=>b.classList.remove("is-active"));
      btn.classList.add("is-active");
      currentSort = btn.dataset.sort;
      apply();
    });
  });

});
