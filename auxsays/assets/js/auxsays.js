document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.coverage-card[data-lottie]');
  if (window.lottie) {
    cards.forEach((card) => {
      const target = card.querySelector('.coverage-lottie');
      const src = card.dataset.lottie;
      if (!target || !src) return;
      const anim = window.lottie.loadAnimation({
        container: target,
        renderer: 'svg',
        loop: true,
        autoplay: false,
        path: src
      });
      card.addEventListener('mouseenter', () => anim.play());
      card.addEventListener('mouseleave', () => anim.stop());
    });
  }

  const search = document.getElementById('article-search');
  const chips = document.querySelectorAll('.chip');
  const articleCards = document.querySelectorAll('.article-card');
  let activeFilter = 'all';

  function applyFilters() {
    const query = (search?.value || '').toLowerCase().trim();
    articleCards.forEach((card) => {
      const haystack = [card.dataset.title, card.dataset.description, card.dataset.tags].join(' ');
      const categoryMatch = activeFilter === 'all' || (card.dataset.categories || '').includes(activeFilter);
      const queryMatch = !query || haystack.includes(query);
      card.style.display = categoryMatch && queryMatch ? '' : 'none';
    });
  }

  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      chips.forEach((c) => c.classList.remove('is-active'));
      chip.classList.add('is-active');
      activeFilter = chip.dataset.filter;
      applyFilters();
    });
  });
  search?.addEventListener('input', applyFilters);
});
