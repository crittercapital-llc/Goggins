/* ── Dashboard (Today) page ──────────────────────────────────────────── */
const Dashboard = (() => {
  let state = {};

  /* Zone helpers */
  function zone(score) {
    if (score <= 33) return { label: 'Red — Low Recovery',   cls: 'zone-red',    badge: 'badge-red',    text: 'Red' };
    if (score <= 66) return { label: 'Yellow — Take It Easy', cls: 'zone-yellow', badge: 'badge-yellow', text: 'Yellow' };
    if (score <= 84) return { label: 'Green — Ready',         cls: 'zone-green',  badge: 'badge-green',  text: 'Green' };
    return             { label: 'Blue — Peak Performance',    cls: 'zone-blue',   badge: 'badge-blue',   text: 'Peak' };
  }

  function intensityCls(i) {
    if (i === 'low')  return 'intensity-low';
    if (i === 'high') return 'intensity-high';
    return 'intensity-moderate';
  }

  async function onActivate() {
    renderDate();
    await loadToday();
  }

  function renderDate() {
    const el = document.getElementById('dash-date');
    if (!el) return;
    el.textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long', month: 'long', day: 'numeric'
    });
  }

  async function loadToday() {
    showWorkoutLoading(true);
    try {
      const data = await API.get('/workouts/today');
      state = data;
      renderRecovery(data);
      renderWorkout(data);
    } catch (err) {
      API.showToast('Failed to load today\'s workout.', true);
    } finally {
      showWorkoutLoading(false);
    }
  }

  /* ── Recovery card ────────────────────────────────────────────────── */
  function renderRecovery(data) {
    const form    = document.getElementById('dash-recovery-form');
    const display = document.getElementById('dash-recovery-display');
    const spinner = document.getElementById('dash-adapting');

    // If we have a plan name
    const planEl = document.getElementById('dash-plan-name');
    if (planEl && data.planned_workout) {
      // plan name comes from the workout data eventually; blank for now
    }

    if (data.recovery_score) {
      showRecoveryDisplay(data.recovery_score);
    } else {
      form.style.display = 'block';
      display.style.display = 'none';
      spinner.style.display = 'none';
      setupRecoveryForm();
    }
  }

  function showRecoveryDisplay(rec) {
    const form    = document.getElementById('dash-recovery-form');
    const display = document.getElementById('dash-recovery-display');
    const spinner = document.getElementById('dash-adapting');
    const badge   = document.getElementById('dash-recovery-badge');
    const scoreBig = document.getElementById('dash-score-big');
    const details = document.getElementById('dash-recovery-details');

    form.style.display    = 'none';
    spinner.style.display = 'none';
    display.style.display = 'block';

    const z = zone(rec.whoop_score);
    scoreBig.textContent = rec.whoop_score;
    scoreBig.className = 'recovery-score-big ' + z.cls;

    const parts = [];
    if (rec.hrv)         parts.push(`HRV ${rec.hrv}ms`);
    if (rec.rhr)         parts.push(`RHR ${rec.rhr}bpm`);
    if (rec.sleep_hours) parts.push(`Sleep ${rec.sleep_hours}h`);
    if (rec.subjective_feel) parts.push(rec.subjective_feel);
    details.textContent = parts.join(' · ') || z.label;

    badge.textContent = z.text;
    badge.className = 'recovery-badge ' + z.badge;
    badge.style.display = 'inline-block';

    document.getElementById('dash-edit-recovery').onclick = () => {
      display.style.display = 'none';
      document.getElementById('dash-recovery-form').style.display = 'block';
      setupRecoveryForm();
    };
  }

  function setupRecoveryForm() {
    const slider  = document.getElementById('dash-score-slider');
    const display = document.getElementById('dash-score-display');
    const zoneEl  = document.getElementById('dash-score-zone');
    const feelChips = document.querySelectorAll('#dash-feel-chips .chip-sm');

    function updateSlider() {
      const s = parseInt(slider.value, 10);
      const z = zone(s);
      display.textContent = s;
      display.className = 'score-display ' + z.cls;
      zoneEl.textContent = z.label;
      zoneEl.className = 'score-zone ' + z.cls;
    }
    slider.addEventListener('input', updateSlider);
    updateSlider();

    feelChips.forEach(chip => {
      chip.addEventListener('click', () => {
        feelChips.forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });

    document.getElementById('dash-submit-recovery').onclick = handleRecoverySubmit;
  }

  async function handleRecoverySubmit() {
    const score = parseInt(document.getElementById('dash-score-slider').value, 10);
    const hrv   = parseInt(document.getElementById('dash-hrv').value, 10) || null;
    const rhr   = parseInt(document.getElementById('dash-rhr').value, 10) || null;
    const sleep = parseFloat(document.getElementById('dash-sleep').value) || null;
    const feelActive = document.querySelector('#dash-feel-chips .chip-sm.active');
    const feel  = feelActive ? feelActive.dataset.value : null;
    const today = new Date().toISOString().slice(0, 10);

    const btn = document.getElementById('dash-submit-recovery');
    btn.disabled = true;

    try {
      const rec = await API.post('/recovery', {
        score_date: today,
        whoop_score: score,
        hrv, rhr,
        sleep_hours: sleep,
        subjective_feel: feel,
      });

      state.recovery_score = rec;
      showRecoveryDisplay(rec);

      // Trigger adaptation if there's a workout to adapt
      if (state.planned_workout && !state.planned_workout.is_rest_day) {
        await triggerAdaptation(state.planned_workout.id, rec.id);
      }
    } catch (err) {
      API.showToast('Failed to save recovery score: ' + err.message, true);
      btn.disabled = false;
    }
  }

  async function triggerAdaptation(plannedWorkoutId, recoveryScoreId) {
    const spinner = document.getElementById('dash-adapting');
    const stream  = document.getElementById('dash-adapt-stream');
    spinner.style.display = 'block';

    await new Promise((resolve, reject) => {
      API.stream(
        '/workouts/adapt',
        { planned_workout_id: plannedWorkoutId, recovery_score_id: recoveryScoreId },
        (chunk) => {
          stream.style.display = 'block';
          stream.textContent = (stream.textContent + chunk).slice(-200);
        },
        async (data) => {
          spinner.style.display = 'none';
          stream.style.display = 'none';
          // Reload today's data to get adapted workout
          const fresh = await API.get('/workouts/today');
          state = fresh;
          renderWorkout(fresh);
          resolve();
        },
        (err) => {
          spinner.style.display = 'none';
          API.showToast('Adaptation failed: ' + err.message, true);
          resolve(); // still render planned
        }
      );
    });
  }

  /* ── Workout card ─────────────────────────────────────────────────── */
  function renderWorkout(data) {
    showWorkoutLoading(false);

    const noplan   = document.getElementById('dash-no-plan');
    const restDay  = document.getElementById('dash-rest-day');
    const content  = document.getElementById('dash-workout-content');
    const title    = document.getElementById('dash-workout-title');
    const ibadge   = document.getElementById('dash-intensity-badge');
    const focus    = document.getElementById('dash-workout-focus');
    const adaptNotes = document.getElementById('dash-adaptation-notes');
    const adaptText  = document.getElementById('dash-adapt-text');
    const exList   = document.getElementById('dash-exercise-list');
    const startBtn = document.getElementById('dash-start-workout');
    const doneDiv  = document.getElementById('dash-workout-done');

    [noplan, restDay, content].forEach(el => el.style.display = 'none');

    if (!data.planned_workout) {
      noplan.style.display = 'block';
      return;
    }

    const pw = data.planned_workout;

    if (pw.is_rest_day) {
      restDay.style.display = 'block';
      document.getElementById('dash-mark-rest-done').onclick = markRestDone;
      return;
    }

    content.style.display = 'block';
    title.textContent = pw.day_label || 'Today\'s Workout';

    ibadge.textContent = pw.intended_intensity || 'moderate';
    ibadge.className = 'intensity-badge ' + intensityCls(pw.intended_intensity);

    // Use adapted workout if available
    const ws = data.adapted_workout
      ? data.adapted_workout.adapted_structure
      : pw.workout_structure;

    focus.textContent = pw.focus || '';

    if (data.adapted_workout && data.adapted_workout.adaptation_notes) {
      adaptNotes.style.display = 'flex';
      adaptText.textContent = data.adapted_workout.adaptation_notes;
    } else {
      adaptNotes.style.display = 'none';
    }

    renderExercisePreview(ws, exList);

    if (data.log_completed) {
      startBtn.style.display = 'none';
      doneDiv.style.display = 'block';
      document.getElementById('dash-view-feedback').onclick = showFeedbackModal;
    } else {
      doneDiv.style.display = 'none';
      startBtn.style.display = 'flex';
      startBtn.onclick = () => {
        App.navigate('workout-logger', {
          planned_workout: pw,
          adapted_workout: data.adapted_workout,
          log_id: data.log_id,
        });
      };
    }
  }

  function renderExercisePreview(ws, container) {
    container.innerHTML = '';
    if (!ws) return;
    const exercises = [...(ws.main || []), ...(ws.accessory || [])].slice(0, 6);
    exercises.forEach(ex => {
      const item = document.createElement('div');
      item.className = 'exercise-preview-item';
      item.innerHTML = `
        <span class="exercise-preview-name">${ex.exercise || ''}</span>
        <span class="exercise-preview-detail">${ex.sets || ''}×${ex.reps || ''}</span>
      `;
      container.appendChild(item);
    });
    if (exercises.length === 0) {
      container.innerHTML = '<p style="color:var(--text-3);font-size:13px;padding:4px 0">Active recovery session</p>';
    }
  }

  async function markRestDone() {
    const pw = state.planned_workout;
    if (!pw) return;
    try {
      await API.post('/logs/start', { planned_workout_id: pw.id, adapted_workout_id: null });
      const logId = (await API.get('/workouts/today')).log_id;
      if (logId) {
        await API.post(`/logs/${logId}/complete`, {
          exercises_completed: [],
          overall_rpe: null,
          energy_level: null,
          notes: 'Rest day completed.',
        });
      }
      API.showToast('Rest day marked complete.');
      await loadToday();
    } catch (err) {
      API.showToast('Error: ' + err.message, true);
    }
  }

  async function showFeedbackModal() {
    const today = await API.get('/workouts/today');
    if (!today.log_id) return;

    // Try to fetch existing feedback from history
    try {
      const logs = await API.get('/logs/history?limit=5');
      const todayLog = logs.find(l => l.id === today.log_id);
      if (todayLog && todayLog.feedback_text) {
        openFeedbackModal(todayLog.feedback_text);
        return;
      }
    } catch (_) {}

    // Otherwise generate feedback
    const modal = document.getElementById('feedback-modal');
    const text  = document.getElementById('feedback-modal-text');
    modal.style.display = 'flex';
    text.textContent = '';
    document.getElementById('feedback-modal-close').onclick = () => { modal.style.display = 'none'; };
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };

    API.stream(
      `/feedback/workout/${today.log_id}`,
      null,
      (chunk) => { text.textContent += chunk; },
      () => {},
      (err) => { text.textContent += '\n\nError: ' + err.message; }
    );
  }

  function openFeedbackModal(feedbackText) {
    const modal = document.getElementById('feedback-modal');
    const text  = document.getElementById('feedback-modal-text');
    modal.style.display = 'flex';
    text.textContent = feedbackText;
    document.getElementById('feedback-modal-close').onclick = () => { modal.style.display = 'none'; };
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
  }

  function showWorkoutLoading(show) {
    document.getElementById('dash-workout-loading').style.display = show ? 'block' : 'none';
    document.getElementById('dash-workout-content').style.display = show ? 'none' : '';
  }

  return { onActivate };
})();
