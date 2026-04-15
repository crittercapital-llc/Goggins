/* ── Plan View page ──────────────────────────────────────────────────── */
const PlanView = (() => {

  async function onActivate() {
    const accordion = document.getElementById('plan-weeks-accordion');
    const noPlan    = document.getElementById('plan-no-plan');
    const content   = document.getElementById('plan-content');
    const headerSub = document.getElementById('plan-header-sub');

    accordion.innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div></div>';
    noPlan.style.display = 'none';
    content.style.display = 'block';

    try {
      const data = await API.get('/plans/active');
      if (!data.plan) {
        content.style.display = 'none';
        noPlan.style.display = 'block';
        return;
      }

      headerSub.textContent =
        `${data.plan.name} · ${data.plan.total_weeks} weeks · Week ${data.plan.current_week} active`;

      accordion.innerHTML = '';
      data.weeks.forEach(week => {
        accordion.appendChild(buildWeekAccordion(week, data.plan.current_week));
      });

      // Auto-open current week
      const currentHeader = document.querySelector(
        `.week-accordion[data-week="${data.plan.current_week}"] .week-header`
      );
      if (currentHeader) currentHeader.click();

    } catch (err) {
      accordion.innerHTML = '';
      API.showToast('Failed to load plan: ' + err.message, true);
    }
  }

  function buildWeekAccordion(week, currentWeek) {
    const isCurrent = week.week_number === currentWeek;
    const trainingDays = week.workouts.filter(w => !w.is_rest_day).length;

    const wrap = document.createElement('div');
    wrap.className = 'week-accordion';
    wrap.dataset.week = week.week_number;

    const header = document.createElement('div');
    header.className = 'week-header';
    header.innerHTML = `
      <div class="week-header-left">
        <span class="week-num">Week ${week.week_number}</span>
        <span class="week-theme">${trainingDays} training day${trainingDays !== 1 ? 's' : ''}</span>
        ${isCurrent ? '<span class="week-current-badge">Current</span>' : ''}
      </div>
      <span class="week-chevron">›</span>
    `;

    const body = document.createElement('div');
    body.className = 'week-body';
    week.workouts.forEach(workout => {
      body.appendChild(buildDayCard(workout));
    });

    header.addEventListener('click', () => {
      const isOpen = body.classList.contains('open');
      body.classList.toggle('open', !isOpen);
      header.querySelector('.week-chevron').classList.toggle('open', !isOpen);
    });

    wrap.appendChild(header);
    wrap.appendChild(body);
    return wrap;
  }

  function buildDayCard(workout) {
    const card = document.createElement('div');
    card.className = 'day-card' + (workout.is_rest_day ? ' rest-day' : '');
    card.innerHTML = `
      <div>
        <div class="day-label">${workout.day_label || `Day ${workout.day_number}`}</div>
        <div class="day-focus">${workout.focus || (workout.is_rest_day ? 'Rest Day' : 'Training')}</div>
      </div>
      ${workout.is_rest_day ? '' : '<span class="day-arrow">›</span>'}
    `;

    if (!workout.is_rest_day) {
      card.addEventListener('click', () => openWorkoutDetail(workout.id));
    }
    return card;
  }

  async function openWorkoutDetail(workoutId) {
    const modal = document.getElementById('workout-detail-modal');
    const title = document.getElementById('workout-detail-title');
    const body  = document.getElementById('workout-detail-body');

    modal.style.display = 'flex';
    title.textContent = 'Loading...';
    body.innerHTML = '<div style="padding:20px;text-align:center"><div class="spinner"></div></div>';

    document.getElementById('workout-detail-close').onclick = () => {
      modal.style.display = 'none';
    };
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };

    try {
      const workout = await API.get(`/workouts/${workoutId}`);
      title.textContent = `${workout.day_label} — ${workout.focus}`;
      body.innerHTML = buildWorkoutDetailHTML(workout.workout_structure);
    } catch (err) {
      body.innerHTML = `<p style="padding:20px;color:var(--text-2)">Failed to load: ${err.message}</p>`;
    }
  }

  function buildWorkoutDetailHTML(ws) {
    if (!ws) return '<p style="padding:20px;color:var(--text-2)">No workout data.</p>';
    let html = '';

    function renderSection(label, items, isTime) {
      if (!items || items.length === 0) return '';
      let s = `<div class="detail-section">
        <div class="detail-section-title">${label}</div>`;
      items.forEach(ex => {
        const meta = isTime
          ? `${ex.duration_seconds ? ex.duration_seconds + 's' : ''} ${ex.reps > 0 ? '× ' + ex.reps : ''}`
          : `${ex.sets ? ex.sets + ' sets' : ''} ${ex.reps ? '× ' + ex.reps : ''} ${ex.weight_guidance ? '— ' + ex.weight_guidance : ''} ${ex.rest_seconds ? '| Rest ' + ex.rest_seconds + 's' : ''}`;
        s += `
          <div class="detail-exercise">
            <div class="detail-ex-name">${ex.exercise || ''}</div>
            <div class="detail-ex-meta">${meta.trim()}</div>
            ${ex.notes ? `<div class="detail-ex-notes">${ex.notes}</div>` : ''}
          </div>`;
      });
      return s + '</div>';
    }

    html += renderSection('Warm-up', ws.warmup, true);
    html += renderSection('Main Lifts', ws.main, false);
    html += renderSection('Accessories', ws.accessory, false);
    html += renderSection('Cool-down', ws.cooldown, true);
    return html || '<p style="padding:20px;color:var(--text-2)">No exercises programmed.</p>';
  }

  return { onActivate };
})();
