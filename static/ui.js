/* Onyx shared UI behaviors.
 *
 * Progressive enhancement only — every behavior is a no-op if the page does
 * not opt in. The `html` element gets a `.js` class early (set inline on each
 * page) so CSS can gate reveal animations behind `html.js`.
 */

(function () {
  'use strict';

  // Progressive enhancement marker: CSS gates reveal animations behind
  // `html.js` so no-JS users always see content.
  document.documentElement.classList.add('js');

  /* ── Scroll reveal ── */
  // Elements with class "reveal" fade up as they enter the viewport.
  // Gate: only animate when JS is on (html.js) and motion is not reduced.
  const prefersReduced = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  if (!prefersReduced && document.documentElement.classList.contains('js')) {
    const targets = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window && targets.length) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('revealed');
            io.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });
      targets.forEach((el) => io.observe(el));
    } else {
      targets.forEach((el) => el.classList.add('revealed'));
    }
  }

  /* ── Sticky nav shadow + active section highlight ── */
  const navbar = document.querySelector('.navbar');
  if (navbar) {
    const onScroll = () => {
      navbar.classList.toggle('scrolled', window.scrollY > 8);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  const sections = document.querySelectorAll('section[id]');
  const navLinks = Array.prototype.slice.call(
    document.querySelectorAll('.nav-link[href^="#"]')
  );
  if (sections.length && navLinks.length && 'IntersectionObserver' in window) {
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          navLinks.forEach((link) => {
            const href = link.getAttribute('href');
            link.classList.toggle('active', href === '#' + id);
          });
        }
      });
    }, { rootMargin: '-40% 0px -55% 0px' });
    sections.forEach((el) => spy.observe(el));
  }

  /* ── Accessibility: skip-to-content ── */
  const skipLink = document.getElementById('skip-to-content');
  if (skipLink) {
    skipLink.addEventListener('click', (e) => {
      e.preventDefault();
      const main = document.querySelector('main');
      if (main) {
        main.setAttribute('tabindex', '-1');
        main.focus({ preventScroll: false });
        main.scrollIntoView();
      }
    });
  }

  /* ── Accessibility: font-size toggle ── */
  // Cycles a proportional zoom (100% / 112% / 125%) on the root element.
  // Uses CSS `zoom` so it scales px-based styles too (equivalent to browser
  // zoom), unlike a rem-only change.
  const btnFont = document.getElementById('font-size-toggle');
  if (btnFont) {
    const sizes = [1, 1.125, 1.25];
    const readScale = () => {
      const raw = document.documentElement.dataset.fontScale;
      const n = parseInt(raw || '0', 10);
      return (isNaN(n) || n < 0 || n >= sizes.length) ? 0 : n;
    };
    let idx = readScale();

    const apply = () => {
      document.documentElement.style.zoom = String(sizes[idx]);
      document.documentElement.dataset.fontScale = String(idx);
      btnFont.setAttribute('aria-pressed', idx > 0 ? 'true' : 'false');
      btnFont.textContent = 'A' + (idx > 0 ? '+' + (idx * 12.5) + '%' : '');
    };

    btnFont.addEventListener('click', () => {
      idx = (idx + 1) % sizes.length;
      apply();
    });
    apply();
  }

  /* ── Button press feedback (safe: transform only) ── */
  document.addEventListener('mousedown', (e) => {
    const btn = e.target.closest('button, .btn-hero-primary, .btn-hero-secondary, .btn-nav-launch');
    if (btn && !btn.disabled) btn.classList.add('pressed');
  });
  document.addEventListener('mouseup', (e) => {
    const btn = e.target.closest('button, .btn-hero-primary, .btn-hero-secondary, .btn-nav-launch');
    if (btn) btn.classList.remove('pressed');
  });
})();