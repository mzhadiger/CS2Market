(function () {
  'use strict';

  // use the saved theme, otherwise follow the system setting
  const THEME_KEY = 'cs2mp-theme';
  const stored = localStorage.getItem(THEME_KEY);
  const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
  const initial = stored || (prefersLight ? 'light' : 'dark');
  document.documentElement.setAttribute('data-theme', initial);

  window.toggleTheme = function () {
    const curr = document.documentElement.getAttribute('data-theme');
    const next = curr === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem(THEME_KEY, next);
  };

  // opens and closes the filters on small screens
  window.toggleFilters = function (btn) {
    const panel = document.querySelector('.filters-collapsible');
    if (!panel) return;
    panel.classList.toggle('open');
    const icon = btn.querySelector('.bi');
    if (icon) icon.classList.toggle('bi-chevron-down');
  };

  // elements with .observe-fade fade in when you scroll to them
  document.addEventListener('DOMContentLoaded', function () {
    const items = document.querySelectorAll('.observe-fade');
    if (!('IntersectionObserver' in window) || items.length === 0) {
      items.forEach(el => el.classList.add('fade-in'));
      return;
    }
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('fade-in');
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -40px 0px' });
    items.forEach(el => io.observe(el));
  });

  // numbers with data-count-to count up from 0 when the page loads
  document.addEventListener('DOMContentLoaded', function () {
    const nums = document.querySelectorAll('[data-count-to]');
    nums.forEach(el => {
      const target = parseFloat(el.dataset.countTo);
      const prefix = el.dataset.prefix || '';
      const duration = 900;
      const start = performance.now();
      function step(now) {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);  // slows down near the end
        const val = target * eased;
        const rounded = Math.abs(target) >= 1000
            ? val.toLocaleString('en-US', { maximumFractionDigits: 0 })
            : val.toFixed(0);
        el.textContent = prefix + rounded;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
  });

  // highlight the nav link for the page we are on
  document.addEventListener('DOMContentLoaded', function () {
    const path = window.location.pathname;
    document.querySelectorAll('.cs2-nav .nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (!href || href === '/') {
        if (path === '/') link.classList.add('active');
      } else if (path.startsWith(href)) {
        link.classList.add('active');
      }
    });
  });

  // show or hide the password
  window.togglePassword = function (btn) {
    const input = btn.closest('.password-wrap').querySelector('input');
    const icon = btn.querySelector('.bi');
    if (input.type === 'password') {
      input.type = 'text';
      icon.classList.replace('bi-eye', 'bi-eye-slash');
    } else {
      input.type = 'password';
      icon.classList.replace('bi-eye-slash', 'bi-eye');
    }
  };

  // forms with data-confirm ask the user before submitting
  document.addEventListener('submit', function (e) {
    const msg = e.target.dataset.confirm;
    if (msg && !confirm(msg)) e.preventDefault();
  });
})();
