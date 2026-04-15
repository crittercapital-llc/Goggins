/* ── History page ────────────────────────────────────────────────────── */
const History = (() => {
  let offset = 0;
  const LIMIT = 20;

  async function onActivate() {
    offset = 0;
    document.getElementById('history-list').innerHTML =
      '<div style="padding:40px;text-align:center"><div class="spinner" style="margin:0 auto"></div></div>';
    document.getElementById('history-empty').style.display = 'none';
    await loadHistory();
  }

  async function loadHistory() {
    try {
      const logs = await API.get(`/logs/history?limit=${LIMIT}&offset=${offset}`);
      const listEl = document.getElementById('history-list');

      if (offset === 0) listEl.innerHTML = '';

      if (logs.length === 0 && offset === 0) {
        document.getElementById('history-empty').style.display = 'block';
        return;
      }

      logs.forEach(log => listEl.appendChild(buildHistoryCard(log)));
      offset += logs.length;

    } catch (err) {
      API.showToast('Failed to load history: ' + err.message, true);
    }
  }

  function buildHistoryCard(log) {
    const card = document.createElement('div');
    card.className = 'history-card';

    const date = formatDate(log.workout_date);
    const focus = log.focus || 'Workout';
    const dayLabel = log.day_label || '';
    const exercises = Array.isArray(log.exercises_completed) ? log.exercises_completed : [];
    const doneCount = exercises.filter(e => !e.skipped).length;
    const rpe = log.overall_rpe;

    card.innerHTML = `
      <div class="history-card-header">
        <div class="history-card-left">
          <div class="history-date">${date}${dayLabel ? ' · ' + dayLabel : ''}</div>
          <div class="history-focus">${focus}</div>
          <div class="history-meta">${doneCount} exercise${doneCount !== 1 ? 's' : ''}${log.energy_level ? ' · ' + log.energy_level + ' energy' : ''}</div>
        </div>
        ${rpe ? `<div class="history-rpe">RPE ${rpe}</div>` : ''}
      </div>
      <div class="history-body" id="history-body-${log.id}">
        ${buildExerciseRows(exercises)}
        ${buildFeedbackBlock(log)}
      </div>
    `;

    card.querySelector('.history-card-header').addEventListener('click', () => {
      const body = document.getElementById(`history-body-${log.id}`);
      body.classList.toggle('open');

      // Lazy-load feedback if not yet loaded
      if (body.classList.contains('open') && !log._feedbackLoaded) {
        loadFeedbackForLog(log, body);
        log._feedbackLoaded = true;
      }
    });

    return card;
  }

  function buildExerciseRows(exercises) {
    if (!exercises.length) return '';
    let html = '<div class="history-exercises">';
    exercises.slice(0, 8).forEach(ex => {
      const sets = (ex.sets || []).filter(s => s.reps !== null || s.weight_lbs !== null);
      const summary = sets.map(s => {
        if (s.weight_lbs) return `${s.reps}×${s.weight_lbs}lb`;
        return s.reps ? `${s.reps} reps` : '';
      }).filter(Boolean).join(', ');

      html += `
        <div class="history-ex-row">
          <span class="history-ex-name">${ex.skipped ? '✕ ' : ''}${ex.exercise || ''}</span>
          <span class="history-ex-sets">${ex.skipped ? 'skipped' : (summary || `${(ex.sets || []).length} sets`)}</span>
        </div>`;
    });
    if (exercises.length > 8) {
      html += `<div style="font-size:12px;color:var(--text-3);padding:4px 0">+${exercises.length - 8} more</div>`;
    }
    html += '</div>';
    return html;
  }

  function buildFeedbackBlock(log) {
    if (log.feedback_text) {
      return `
        <div class="history-feedback-label">Goggins Feedback</div>
        <div class="history-feedback">${escapeHtml(log.feedback_text)}</div>`;
    }
    return `<div id="feedback-slot-${log.id}"></div>`;
  }

  async function loadFeedbackForLog(log, bodyEl) {
    const slot = bodyEl.querySelector(`#feedback-slot-${log.id}`);
    if (!slot || log.feedback_text) return;

    slot.innerHTML = `
      <div class="history-feedback-label">Goggins Feedback</div>
      <div class="history-feedback" id="feedback-text-${log.id}"><em style="color:var(--text-3)">Loading feedback...</em></div>`;

    try {
      // Try fetching from the api_feedback table via log history (already loaded)
      // If not present in log data, stream it now
      const fbEl = document.getElementById(`feedback-text-${log.id}`);
      fbEl.innerHTML = '';

      API.stream(
        `/feedback/workout/${log.id}`,
        null,
        (chunk) => { fbEl.textContent += chunk; },
        () => {},
        (err) => {
          fbEl.textContent = 'Feedback unavailable.';
        }
      );
    } catch (_) {}
  }

  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr + 'T12:00:00');
      return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    } catch (_) { return dateStr; }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  return { onActivate };
})();
