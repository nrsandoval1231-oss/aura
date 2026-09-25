/* ==========================================================================
   Renzo — Page-turn motion, suggestion fill, rise-on-load
   ========================================================================== */

// Apply rise animations to elements with .rise class
document.querySelectorAll('.rise').forEach((el, i) => {
  const d = el.dataset.rise || (i + 1);
  el.style.animationDelay = (d * 0.1) + 's';
});

// Suggestion auto-fill (on the first-visit page)
document.querySelectorAll('.e-suggestion[data-fill]').forEach(btn => {
  btn.addEventListener('click', () => {
    const fill = btn.dataset.fill;
    if (!fill) return;
    sessionStorage.setItem('renzo-fill', fill);
    window.location.href = 'home.html';
  });
});

// On the home page, check for the suggested fill
if (document.querySelector('.field-input') && sessionStorage.getItem('renzo-fill')) {
  const fill = sessionStorage.getItem('renzo-fill');
  const input = document.querySelector('.field-input');
  if (input) {
    input.value = fill;
    input.focus();
    input.setSelectionRange(fill.length, fill.length);
  }
  sessionStorage.removeItem('renzo-fill');
}

// Page-turn transitions on internal navigation
document.querySelectorAll('a[href]').forEach(link => {
  const href = link.getAttribute('href');
  if (!href || href.startsWith('http') || href.startsWith('#') || href.startsWith('mailto')) return;
  if (link.target === '_blank') return;
  link.addEventListener('click', (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    document.body.classList.add('page-turn-out');
    setTimeout(() => { window.location.href = href; }, 420);
  });
});

// Initial fade-in
document.body.classList.add('page-turn-in');

// Building screen → done screen transition
if (window.location.pathname.includes('building')) {
  setTimeout(() => {
    document.body.style.transition = 'opacity 0.8s ease';
    document.body.style.opacity = '0';
    setTimeout(() => { window.location.href = 'done.html'; }, 800);
  }, 5500);
}
