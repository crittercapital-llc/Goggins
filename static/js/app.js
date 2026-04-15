/* ── Goggins SPA router ──────────────────────────────────────────────── */
const App = (() => {
  const pages = {
    onboarding: document.getElementById('page-onboarding'),
    dashboard:  document.getElementById('page-dashboard'),
    plan:       document.getElementById('page-plan'),
    'workout-logger': document.getElementById('page-workout-logger'),
    history:    document.getElementById('page-history'),
  };
  const nav     = document.getElementById('nav');
  const navItems = document.querySelectorAll('.nav-item[data-page]');
  let currentPage = 'onboarding';

  function navigate(pageId, opts = {}) {
    if (!(pageId in pages)) return;
    Object.values(pages).forEach(p => p.classList.remove('active'));
    pages[pageId].classList.add('active');
    currentPage = pageId;

    const showNav = pageId !== 'onboarding';
    nav.classList.toggle('hidden', !showNav);

    navItems.forEach(item => {
      item.classList.toggle('active', item.dataset.page === pageId);
    });

    // Notify page modules of activation
    if (pageId === 'dashboard' && typeof Dashboard !== 'undefined') {
      Dashboard.onActivate(opts);
    } else if (pageId === 'plan' && typeof PlanView !== 'undefined') {
      PlanView.onActivate(opts);
    } else if (pageId === 'workout-logger' && typeof WorkoutLogger !== 'undefined') {
      WorkoutLogger.onActivate(opts);
    } else if (pageId === 'history' && typeof History !== 'undefined') {
      History.onActivate(opts);
    }
  }

  // Bottom nav clicks
  navItems.forEach(item => {
    item.addEventListener('click', () => navigate(item.dataset.page));
  });

  async function init() {
    try {
      const profile = await API.get('/profile');
      if (!profile || profile.exists === false) {
        navigate('onboarding');
        if (typeof Onboarding !== 'undefined') Onboarding.init();
      } else {
        navigate('dashboard');
      }
    } catch (err) {
      console.error('Init error', err);
      navigate('onboarding');
      if (typeof Onboarding !== 'undefined') Onboarding.init();
    }
  }

  document.addEventListener('DOMContentLoaded', init);

  return { navigate };
})();
