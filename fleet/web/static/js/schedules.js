// --- Automated Agent Schedules & Background Tasks Engine ---
async function fetchSchedules() {
  try {
    const res = await fetch('/api/schedules');
    const data = await res.json();
    if (!data || !data.schedules) return;

    const schedules = data.schedules;
    const list = document.getElementById('scheduleList');
    const countBadge = document.getElementById('activeSchedulesCount');

    if (!list) return;

    const activeCount = schedules.filter(s => s.enabled).length;
    if (countBadge) {
      countBadge.textContent = `${activeCount} Active / ${schedules.length} Total`;
    }

    if (schedules.length === 0) {
      list.innerHTML = '<div style="color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px;">No automated schedules configured.</div>';
      return;
    }

    list.innerHTML = schedules.map(s => {
      // Determine human-readable timing string
      let timingStr = '';
      if (s.time) {
        timingStr = `Daily at ${s.time}`;
      } else if (s.times && s.times.length) {
        timingStr = `Daily at ${s.times.join(', ')}`;
      } else if (s.cron) {
        timingStr = `Cron: ${s.cron}`;
      } else if (s.every) {
        timingStr = `Every ${s.every}`;
      } else if (s.interval_hours) {
        timingStr = `Every ${s.interval_hours}h`;
      } else if (s.interval_minutes) {
        timingStr = `Every ${s.interval_minutes}m`;
      } else if (s.interval_seconds) {
        timingStr = `Every ${s.interval_seconds}s`;
      } else {
        timingStr = 'Periodic';
      }

      const isEnabled = s.enabled !== false;
      const lastRunStr = s.last_run ? new Date(s.last_run * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Pending';

      return `
        <div class="schedule-item" style="display: flex; align-items: center; justify-content: space-between; background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 8px; padding: 10px 14px; gap: 10px;">
          <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 13px; font-weight: 600; color: ${isEnabled ? 'var(--text)' : 'var(--text-muted)'};">${escapeHtml(s.agent)}.<strong style="color: var(--accent-cyan);">${escapeHtml(s.task)}</strong></span>
              <span class="badge" style="font-size: 10.5px; padding: 2px 7px; background: ${isEnabled ? 'rgba(16, 185, 129, 0.12)' : 'rgba(100, 116, 139, 0.2)'}; color: ${isEnabled ? 'var(--accent-green)' : 'var(--text-muted)'}; border: 1px solid ${isEnabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(100, 116, 139, 0.3)'};">${timingStr}</span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
              ${escapeHtml(s.description || 'Automated agent task')} &bull; Last run: <span style="color: var(--text);">${lastRunStr}</span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; flex-shrink: 0;">
            <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 10px;" onclick="runScheduleNow('${escapeHtml(s.id)}')">⚡ Run</button>
            <label class="switch" style="position: relative; display: inline-block; width: 34px; height: 18px; margin: 0;">
              <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleSchedule('${escapeHtml(s.id)}', this.checked)" style="opacity: 0; width: 0; height: 0;">
              <span style="position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: ${isEnabled ? 'var(--accent-green)' : '#475569'}; transition: .3s; border-radius: 18px;"></span>
            </label>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Error fetching schedules:', e);
  }
}

async function toggleSchedule(id, enabled) {
  try {
    await fetch('/api/schedules/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, enabled })
    });
    fetchSchedules();
  } catch (e) {
    console.error('Failed to toggle schedule:', e);
  }
}

async function runScheduleNow(id) {
  try {
    const res = await fetch('/api/schedules/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id })
    });
    const result = await res.json();
    if (result.status === 'success') {
      if (typeof showToast === 'function') {
        showToast(`✅ Executed task: ${id}`);
      }
      fetchSchedules();
      if (typeof fetchLogs === 'function') fetchLogs();
    } else {
      alert(`Execution failed: ${result.message || 'Unknown error'}`);
    }
  } catch (e) {
    console.error('Failed to run schedule:', e);
  }
}

async function reloadSchedules() {
  try {
    const res = await fetch('/api/schedules/reload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const result = await res.json();
    if (result.status === 'success') {
      fetchSchedules();
    }
  } catch (e) {
    console.error('Failed to reload schedules:', e);
  }
}

window.fetchSchedules = fetchSchedules;
window.toggleSchedule = toggleSchedule;
window.runScheduleNow = runScheduleNow;
window.reloadSchedules = reloadSchedules;

