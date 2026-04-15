/* ── Onboarding page ─────────────────────────────────────────────────── */
const Onboarding = (() => {

  function init() {
    setupSegControl('ob-experience');
    setupGoalGrid();
    setupChips('ob-equipment');
    setupRangeDisplay('ob-days', 'ob-days-val');
    setupRangeDisplay('ob-duration', 'ob-duration-val');
    setupRangeDisplay('ob-weeks', 'ob-weeks-val');
    document.getElementById('ob-score-slider-live');  // not present, ignore

    document.getElementById('onboarding-form')
      .addEventListener('submit', handleSubmit);
  }

  /* ── Segment control (single select) ─────────────────────────────── */
  function setupSegControl(id) {
    const wrap = document.getElementById(id);
    if (!wrap) return;
    wrap.querySelectorAll('.seg-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        wrap.querySelectorAll('.seg-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });
  }

  /* ── Goal grid (single select) ────────────────────────────────────── */
  function setupGoalGrid() {
    const grid = document.getElementById('ob-goal');
    if (!grid) return;
    grid.querySelectorAll('.goal-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        grid.querySelectorAll('.goal-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });
  }

  /* ── Multi-select chips ───────────────────────────────────────────── */
  function setupChips(id) {
    const wrap = document.getElementById(id);
    if (!wrap) return;
    wrap.querySelectorAll('.chip').forEach(chip => {
      chip.addEventListener('click', () => chip.classList.toggle('active'));
    });
  }

  /* ── Range → label ───────────────────────────────────────────────── */
  function setupRangeDisplay(sliderId, labelId) {
    const slider = document.getElementById(sliderId);
    const label  = document.getElementById(labelId);
    if (!slider || !label) return;
    slider.addEventListener('input', () => { label.textContent = slider.value; });
  }

  /* ── Collect form values ──────────────────────────────────────────── */
  function getValues() {
    const expBtn = document.querySelector('#ob-experience .seg-btn.active');
    const goalBtn = document.querySelector('#ob-goal .goal-btn.active');
    const equipChips = document.querySelectorAll('#ob-equipment .chip.active');

    return {
      name: document.getElementById('ob-name').value.trim() || 'Athlete',
      experience_level: expBtn ? expBtn.dataset.value : 'intermediate',
      primary_goal: goalBtn ? goalBtn.dataset.value : 'general_fitness',
      equipment: Array.from(equipChips).map(c => c.dataset.value),
      days_per_week: parseInt(document.getElementById('ob-days').value, 10),
      session_duration_minutes: parseInt(document.getElementById('ob-duration').value, 10),
      age: parseInt(document.getElementById('ob-age').value, 10) || null,
      injuries_limitations: document.getElementById('ob-injuries').value.trim() || null,
    };
  }

  /* ── Submit ───────────────────────────────────────────────────────── */
  async function handleSubmit(e) {
    e.preventDefault();
    const profile = getValues();
    const weeks = parseInt(document.getElementById('ob-weeks').value, 10);

    if (profile.equipment.length === 0) {
      API.showToast('Select at least one equipment option.', true);
      return;
    }

    // Show generating screen
    document.getElementById('onboarding-form').style.display = 'none';
    const gen = document.getElementById('ob-generating');
    gen.style.display = 'block';
    const statusEl = document.getElementById('ob-gen-status');
    const progress = document.getElementById('ob-progress-bar');

    const statuses = [
      'Analyzing your goals...',
      'Building your mesocycles...',
      'Programming progressive overload...',
      'Scheduling deload weeks...',
      'Finalizing exercises...',
    ];
    let si = 0;
    const statusInterval = setInterval(() => {
      si = (si + 1) % statuses.length;
      statusEl.textContent = statuses[si];
      progress.style.width = Math.min(90, (si + 1) * 18) + '%';
    }, 4000);

    try {
      // 1. Save profile
      await API.post('/profile', profile);

      // 2. Generate plan (streaming)
      await new Promise((resolve, reject) => {
        API.stream(
          '/plans/generate',
          { weeks, notes: null },
          (_chunk) => { /* raw JSON chunks – don't display */ },
          (data) => {
            clearInterval(statusInterval);
            progress.style.width = '100%';
            statusEl.textContent = `"${data.plan_name || 'Your plan'}" is ready.`;
            setTimeout(resolve, 800);
          },
          (err) => {
            clearInterval(statusInterval);
            reject(err);
          }
        );
      });

      App.navigate('dashboard');

    } catch (err) {
      clearInterval(statusInterval);
      gen.style.display = 'none';
      document.getElementById('onboarding-form').style.display = 'block';
      API.showToast('Error: ' + err.message, true);
    }
  }

  return { init };
})();
