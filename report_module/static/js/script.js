document.addEventListener('DOMContentLoaded', () => {
  const searchInput = document.getElementById('search-input');
  const filterBtns = document.querySelectorAll('.filter-btn');
  const frameCards = document.querySelectorAll('.frame-card');
  const modal = document.getElementById('lightbox-modal');
  const modalImg = document.getElementById('modal-img');
  const modalTitle = document.getElementById('modal-title');
  const modalDesc = document.getElementById('modal-desc');
  const modalClose = document.getElementById('modal-close');

  let activeFilter = 'all';

  // Search & Filter Logic
  function filterFrames() {
    const query = (searchInput?.value || '').toLowerCase().trim();

    frameCards.forEach(card => {
      const title = card.getAttribute('data-title')?.toLowerCase() || '';
      const summary = card.getAttribute('data-summary')?.toLowerCase() || '';
      const tags = card.getAttribute('data-tags')?.toLowerCase() || '';
      const ocr = card.getAttribute('data-ocr')?.toLowerCase() || '';

      const matchesSearch = !query || 
        title.includes(query) || 
        summary.includes(query) || 
        tags.includes(query) || 
        ocr.includes(query);

      const matchesTag = (activeFilter === 'all') || tags.includes(activeFilter.toLowerCase());

      if (matchesSearch && matchesTag) {
        card.style.display = 'flex';
      } else {
        card.style.display = 'none';
      }
    });
  }

  if (searchInput) {
    searchInput.addEventListener('input', filterFrames);
  }

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.getAttribute('data-filter') || 'all';
      filterFrames();
    });
  });

  // Lightbox Modal
  document.querySelectorAll('.frame-media').forEach(media => {
    media.addEventListener('click', () => {
      const card = media.closest('.frame-card');
      const img = media.querySelector('img');
      if (!card || !img || !modal) return;

      modalImg.src = img.src;
      modalTitle.textContent = card.querySelector('.frame-title')?.textContent || '';
      modalDesc.textContent = card.querySelector('.frame-desc')?.textContent || '';
      modal.classList.add('open');
    });
  });

  function closeModal() {
    if (modal) modal.classList.remove('open');
  }

  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });
});
