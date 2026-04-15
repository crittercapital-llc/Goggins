/* ── Workout Logger page ─────────────────────────────────────────────── */
const WorkoutLogger = (() => {
  let logId = null;
  let plannedWorkout = null;
  let adaptedWorkout = null;
  let exercises = [];   // runtime set data per exercise
  let timerInterval = null;
  let startTime = null;
  let saveDebounce = null;

  /* ── Activate ─────────────────────────────────────────────────────── */
  async function onActivate(opts = {}) {
    plannedWorkout = opts.planned_workout || null;
    adaptedWorkout = opts.adapted_workout || null;
    logId = opts.log_id || null;

    // Restore in-progress log from localStorage
    if (!logId) {
      const saved = localStorage.getItem('activeLogId');
      if (saved) logId = parseInt(saved, 10);
    }

    resetUI();

    if (!plannedWorkout) {
      // Try to load from today's endpoint
      try {
        const today = await API.get('/workouts/today');
        if (today.planned_workout && !today.planned_workout.is_rest_day) {
          plannedWorkout = today.planned_workout;
          adaptedWorkout = today.adapted_workout;
          logId = today.log_id;
        }
      } catch (_) {}
    }

    if (!plannedWorkout) {
      document.getElementById('logger-title').textContent = 'No Workout Today';
      return;
    }

    // Use adapted structure if available
    const ws = (adaptedWorkout && adaptedWorkout.adapted_structure)
      ? adaptedWorkout.adapted_structure
      : plannedWorkout.workout_structure;

    document.getElementById('logger-title').textContent =
      plannedWorkout.focus || plannedWorkout.day_label || 'Workout';

    // Start or resume log
    if (!logId) {
      try {
        const resp = await API.post('/logs/start', {
          planned_workout_id: plannedWorkout.id,
          adapted_workout_id: adaptedWorkout ? adaptedWorkout.id : null,
        });
        logId = resp.log_id;
        localStorage.setItem('activeLogId', logId);
      } catch (err) {
        API.showToast('Failed to start log: ' + err.message, true);
        return;
      }
    } else {
      localStorage.setItem('activeLogId', logId);
    }

    startTimer();
    renderExercises(ws);
    setupFinishSection();
  }

  function resetUI() {
    clearInterval(timerInterval);
    document.getElementById('logger-timer').textContent = '0:00';
    document.getElementById('logger-exercises').innerHTML = '';
    document.getElementById('logger-finish-section').style.display = 'block';
    document.getElementById('logger-feedback-section').style.display = 'none';
    document.getElementById('logger-feedback-text').textContent = '';
    document.querySelectorAll('#logger-rpe-row .rpe-btn').forEach(b => b.classList.remove('active'));
    const chips = document.querySelectorAll('#logger-energy-chips .chip-sm');
    chips.forEach(c => { c.classList.remove('active'); if (c.dataset.value === 'medium') c.classList.add('active'); });
    document.getElementById('logger-notes').value = '';
    exercises = [];
  }

  /* ── Timer ────────────────────────────────────────────────────────── */
  function startTimer() {
    startTime = Date.now();
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      const m = Math.floor(elapsed / 60);
      const s = elapsed % 60;
      document.getElementById('logger-timer').textContent =
        `${m}:${s.toString().padStart(2, '0')}`;
    }, 1000);
  }

  /* ── Build exercise list ──────────────────────────────────────────── */
  function renderExercises(ws) {
    if (!ws) return;
    const allExercises = [
      ...(ws.warmup   || []).map(e => ({ ...e, section: 'warmup' })),
      ...(ws.main     || []).map(e => ({ ...e, section: 'main' })),
      ...(ws.accessory|| []).map(e => ({ ...e, section: 'accessory' })),
      ...(ws.cooldown || []).map(e => ({ ...e, section: 'cooldown' })),
    ].filter(e => e.exercise);

    exercises = allExercises.map(ex => ({
      exercise: ex.exercise,
      section: ex.section,
      target_sets: ex.sets || 1,
      target_reps: ex.reps || '',
      weight_guidance: ex.weight_guidance || '',
      rest_seconds: ex.rest_seconds || 0,
      notes: ex.notes || '',
      duration_seconds: ex.duration_seconds || 0,
      skipped: false,
      skip_reason: '',
      sets: [],
    }));

    const container = document.getElementById('logger-exercises');
    container.innerHTML = '';
    exercises.forEach((ex, idx) => {
      container.appendChild(buildExerciseCard(ex, idx));
    });

    updateProgress();
  }

  function buildExerciseCard(ex, idx) {
    const isTimeBased = ex.duration_seconds > 0 && !ex.target_sets;
    const guidance = buildGuidanceText(ex);

    const card = document.createElement('div');
    card.className = 'exercise-card';
    card.dataset.idx = idx;
    card.innerHTML = `
      <div class="exercise-card-header">
        <div class="exercise-card-info">
          <div class="exercise-card-name">${ex.exercise}</div>
          <div class="exercise-card-guidance">${guidance}</div>
          ${ex.notes ? `<div class="exercise-card-notes">${ex.notes}</div>` : ''}
        </div>
        <button class="btn-skip-ex" data-idx="${idx}">Skip</button>
      </div>
      <div class="sets-header">
        <span>Set</span><span>Reps</span><span>Weight (lbs)</span><span>RPE</span>
      </div>
      <div class="set-rows" id="set-rows-${idx}"></div>
      <button class="btn-add-set" data-idx="${idx}">+ Add Set</button>
    `;

    card.querySelector('.btn-skip-ex').addEventListener('click', () => toggleSkip(idx));
    card.querySelector('.btn-add-set').addEventListener('click', () => addSet(idx));

    // Pre-populate with target sets
    const targetSets = ex.target_sets || 1;
    for (let i = 0; i < targetSets; i++) addSet(idx, false);

    return card;
  }

  function buildGuidanceText(ex) {
    const parts = [];
    if (ex.target_sets && ex.target_reps) parts.push(`${ex.target_sets} × ${ex.target_reps}`);
    if (ex.weight_guidance) parts.push(ex.weight_guidance);
    if (ex.rest_seconds > 0) parts.push(`Rest ${ex.rest_seconds}s`);
    if (ex.duration_seconds > 0) parts.push(`${ex.duration_seconds}s`);
    return parts.join(' · ');
  }

  function addSet(idx, autoSave = true) {
    const ex = exercises[idx];
    if (!ex || ex.skipped) return;
    const setNum = ex.sets.length + 1;
    ex.sets.push({ set_number: setNum, reps: null, weight_lbs: null, rpe: null });

    const rowsEl = document.getElementById(`set-rows-${idx}`);
    const row = document.createElement('div');
    row.className = 'set-row';
    row.dataset.setIdx = setNum - 1;
    row.innerHTML = `
      <span class="set-num">${setNum}</span>
      <input type="number" class="set-input set-reps"
        placeholder="${ex.target_reps || 'reps'}" min="0" max="999" inputmode="numeric">
      <input type="number" class="set-input set-weight"
        placeholder="lbs" min="0" max="2000" inputmode="decimal" step="2.5">
      <select class="set-rpe-select">
        <option value="">—</option>
        <option>6</option><option>7</option><option>8</option>
        <option>9</option><option>10</option>
      </select>
    `;

    row.querySelector('.set-reps').addEventListener('input', e => {
      ex.sets[setNum - 1].reps = parseInt(e.target.value, 10) || null;
      scheduleSave();
    });
    row.querySelector('.set-weight').addEventListener('input', e => {
      ex.sets[setNum - 1].weight_lbs = parseFloat(e.target.value) || null;
      scheduleSave();
    });
    row.querySelector('.set-rpe-select').addEventListener('change', e => {
      ex.sets[setNum - 1].rpe = parseInt(e.target.value, 10) || null;
      scheduleSave();
    });

    rowsEl.appendChild(row);
    if (autoSave) scheduleSave();
  }

  function toggleSkip(idx) {
    const ex = exercises[idx];
    if (!ex) return;
    ex.skipped = !ex.skipped;

    const card = document.querySelector(`.exercise-card[data-idx="${idx}"]`);
    if (!card) return;
    card.classList.toggle('skipped', ex.skipped);
    const skipBtn = card.querySelector('.btn-skip-ex');
    skipBtn.textContent = ex.skipped ? 'Undo' : 'Skip';

    // Disable/enable inputs
    card.querySelectorAll('.set-input, .set-rpe-select, .btn-add-set').forEach(el => {
      el.disabled = ex.skipped;
    });
    scheduleSave();
  }

  function updateProgress() {
    const total = exercises.length;
    const done  = exercises.filter(e => e.skipped || e.sets.some(s => s.reps !== null)).length;
    document.getElementById('logger-progress').textContent = `${done} of ${total} exercises`;
  }

  /* ── Auto-save ────────────────────────────────────────────────────── */
  function scheduleSave() {
    updateProgress();
    clearTimeout(saveDebounce);
    saveDebounce = setTimeout(autoSave, 3000);
  }

  async function autoSave() {
    if (!logId) return;
    try {
      await API.put(`/logs/${logId}/exercises`, {
        exercises_completed: buildExercisePayload(),
      });
    } catch (_) { /* silent */ }
  }

  function buildExercisePayload() {
    return exercises.map(ex => ({
      exercise: ex.exercise,
      section: ex.section,
      skipped: ex.skipped,
      skip_reason: ex.skip_reason || '',
      sets: ex.sets.filter(s => s.reps !== null || s.weight_lbs !== null),
    }));
  }

  /* ── Finish section ───────────────────────────────────────────────── */
  function setupFinishSection() {
    document.querySelectorAll('#logger-rpe-row .rpe-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#logger-rpe-row .rpe-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    document.querySelectorAll('#logger-energy-chips .chip-sm').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#logger-energy-chips .chip-sm').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });

    document.getElementById('logger-complete-btn').onclick = handleComplete;
    document.getElementById('logger-done-btn').onclick = () => {
      clearInterval(timerInterval);
      localStorage.removeItem('activeLogId');
      logId = null;
      App.navigate('dashboard');
    };
  }

  async function handleComplete() {
    const rpeBtn  = document.querySelector('#logger-rpe-row .rpe-btn.active');
    const energyBtn = document.querySelector('#logger-energy-chips .chip-sm.active');
    const notes   = document.getElementById('logger-notes').value.trim() || null;
    const rpe     = rpeBtn ? parseInt(rpeBtn.dataset.value, 10) : null;
    const energy  = energyBtn ? energyBtn.dataset.value : null;

    clearTimeout(saveDebounce);
    clearInterval(timerInterval);

    const btn = document.getElementById('logger-complete-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    try {
      await API.post(`/logs/${logId}/complete`, {
        exercises_completed: buildExercisePayload(),
        overall_rpe: rpe,
        energy_level: energy,
        notes,
        completed_at: new Date().toISOString(),
      });

      localStorage.removeItem('activeLogId');

      // Show feedback section
      document.getElementById('logger-finish-section').style.display = 'none';
      const fbSection = document.getElementById('logger-feedback-section');
      fbSection.style.display = 'block';
      fbSection.scrollIntoView({ behavior: 'smooth' });

      const fbText = document.getElementById('logger-feedback-text');
      const fbDot  = document.getElementById('logger-feedback-dot');
      fbText.textContent = '';
      fbDot.style.display = 'inline-block';

      API.stream(
        `/feedback/workout/${logId}`,
        null,
        (chunk) => {
          fbText.textContent += chunk;
          fbText.scrollIntoView({ behavior: 'smooth', block: 'end' });
        },
        () => { fbDot.style.display = 'none'; },
        (err) => {
          fbDot.style.display = 'none';
          fbText.textContent += '\n\nError generating feedback: ' + err.message;
        }
      );
    } catch (err) {
      btn.disabled = false;
      btn.textContent = 'Complete Workout';
      API.showToast('Failed to complete workout: ' + err.message, true);
    }
  }

  document.getElementById('logger-back').addEventListener('click', () => {
    clearTimeout(saveDebounce);
    autoSave();  // save before leaving
    App.navigate('dashboard');
  });

  return { onActivate };
})();
