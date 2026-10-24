// --- Daily Habits & Routines Engine ---
    async function fetchRoutines() {
      try {
        const res = await fetch('/api/routines');
        const routines = await res.json();
        const list = document.getElementById('routineList');
        list.innerHTML = routines.map(r => `
          <div class="routine-item">
            <div style="display: flex; align-items: center; gap: 10px;">
              <input type="checkbox" class="task-checkbox" ${r.completed_today ? 'checked' : ''} onchange="toggleRoutine(${r.id})">
              <span style="font-size: 13px; font-weight: 500; ${r.completed_today ? 'text-decoration: line-through; color: var(--text-muted);' : ''}">${escapeHtml(r.title)}</span>
            </div>
            <span class="routine-time">${r.time_target}</span>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function toggleRoutine(id) {
      await fetch('/api/routines/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id })
      });
      fetchRoutines();
      fetchBriefing();
      fetchLogs();
    }


window.fetchRoutines = fetchRoutines;
window.toggleRoutine = toggleRoutine;
