// --- Morning Briefing Engine ---
async function fetchBriefing() {
  try {
    const res = await fetch('/api/briefing');
    const data = await res.json();
    document.getElementById('greetingText').innerText = `${data.greeting} • ${data.date} (${data.time})`;
    document.getElementById('briefingHeadline').innerText = data.headline;

    const stats = data.summary_stats || {};
    const customAlerts = Array.isArray(data.custom_agent_alerts) ? data.custom_agent_alerts : [];
    const customCount = Number(stats.custom_alerts_count || customAlerts.length || 0);
    const customPillHtml = customCount > 0 ? `
      <div class="stat-pill">
        <span class="label">Custom Alerts</span>
        <span class="val" style="color: #fbbf24;">${customCount}</span>
      </div>
    ` : '';

    document.getElementById('statsContainer').innerHTML = `
      <div class="stat-pill">
        <span class="label">High Priority</span>
        <span class="val" style="color: var(--accent-pink);">${stats.p1_count || 0}</span>
      </div>
      <div class="stat-pill">
        <span class="label">Open Tasks</span>
        <span class="val">${stats.pending_count || 0}</span>
      </div>
      <div class="stat-pill">
        <span class="label">Completed</span>
        <span class="val" style="color: var(--accent-green);">${stats.completed_count || 0}</span>
      </div>
      <div class="stat-pill">
        <span class="label">Habits Done</span>
        <span class="val" style="color: var(--accent-cyan);">${stats.routines_done || 0}/${stats.routines_total || 0}</span>
      </div>
      ${customPillHtml}
    `;

    const meetingsContainer = document.getElementById('briefingMeetingsContainer');
    if (meetingsContainer) {
      if (data.upcoming_meetings && data.upcoming_meetings.length > 0) {
        meetingsContainer.style.display = 'block';
        meetingsContainer.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 12.5px; color: var(--accent-purple); display: flex; align-items: center; gap: 6px;">
              📅 Calendar Agenda & Meeting Prep (${data.upcoming_meetings.length})
            </span>
            <span style="font-size: 11px; color: var(--text-muted);">Auto-Synthesized from Inbox</span>
          </div>
          ${data.upcoming_meetings.map(m => `
            <div style="margin-bottom: 8px; padding-bottom: 8px; border-bottom: 1px solid rgba(168, 85, 247, 0.15);">
              <div style="display: flex; align-items: center; gap: 6px; font-weight: 600; font-size: 12.5px; color: var(--text);">
                <span>${escapeHtml(m.title)}</span>
                <span style="font-size: 10px; padding: 1px 6px; border-radius: 4px; background: rgba(168, 85, 247, 0.2); color: var(--accent-purple); border: 1px solid rgba(168, 85, 247, 0.3);">${escapeHtml(m.platform)}</span>
                <span style="font-size: 11px; color: var(--text-muted); font-weight: 400;">(${escapeHtml(m.time)})</span>
              </div>
              <div style="margin-top: 4px; padding-left: 10px;">
                ${(m.prep_notes || []).map(note => `<div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">💡 <span style="color: var(--text);">${escapeHtml(note)}</span></div>`).join('')}
              </div>
            </div>
          `).join('')}
        `;
      } else {
        meetingsContainer.style.display = 'none';
      }
    }

    // Phase 4: Custom Studio Agent Alerts & Upcoming Renewals Rollup ($0.00 SQLite)
    let customContainer = document.getElementById('briefingCustomAgentsContainer');
    if (!customContainer) {
      const briefingBox = document.getElementById('briefingBox');
      if (briefingBox) {
        customContainer = document.createElement('div');
        customContainer.id = 'briefingCustomAgentsContainer';
        customContainer.style.cssText = 'display: none; margin-top: 12px; padding: 11px 14px; border-radius: 8px; background: rgba(245, 158, 11, 0.09); border: 1px solid rgba(245, 158, 11, 0.3);';
        briefingBox.appendChild(customContainer);
      }
    }
    if (customContainer) {
      if (customAlerts.length > 0) {
        customContainer.style.display = 'block';
        customContainer.innerHTML = `
          <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 12.5px; color: #fbbf24; display: flex; align-items: center; gap: 6px;">
              🛡️ Custom Agent Alerts & Upcoming Renewals (${customCount})
            </span>
            <span style="font-size: 11px; color: var(--text-muted);">Click any alert to open agent workspace</span>
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px;">
            ${customAlerts.map(al => {
              const isOverdue = al.urgency === 'overdue' || (typeof al.days_left === 'number' && al.days_left < 0);
              const badgeCol = isOverdue ? '#f87171' : '#fbbf24';
              let timing = '';
              if (al.kind === 'deadline') {
                const dl = Number(al.days_left || 0);
                timing = dl < 0 ? `${Math.abs(dl)}d OVERDUE` : (dl === 0 ? 'DUE TODAY' : `in ${dl}d`);
              } else {
                timing = 'WARNING';
              }
              const safeAgId = escapeHtml(al.agent_id || '');
              return `
                <button type="button" class="btn" title="Open ${escapeHtml(al.agent_name || al.agent_id)}"
                  onclick="if(window.FleetNavigator){FleetNavigator.switchAgent('${safeAgId}');}"
                  style="padding: 6px 11px; font-size: 11.5px; border-radius: 8px; background: rgba(15, 23, 42, 0.78); border: 1px solid ${badgeCol}55; color: var(--text); display: inline-flex; align-items: center; gap: 7px;">
                  <span>${escapeHtml(al.agent_icon || '✨')}</span>
                  <strong style="color: #f8fafc;">${escapeHtml(al.title || '')}</strong>
                  <span style="color: var(--text-muted); font-size: 10.5px;">(${escapeHtml(al.agent_name || al.agent_id)})</span>
                  <span style="padding: 1px 6px; border-radius: 999px; font-size: 10px; font-weight: 700; background: ${badgeCol}22; color: ${badgeCol};">${escapeHtml(timing)}</span>
                </button>
              `;
            }).join('')}
          </div>
        `;
      } else {
        customContainer.style.display = 'none';
      }
    }
  } catch (e) {
    console.error(e);
  }
}

function speakBriefing() {
  if (!('speechSynthesis' in window)) {
    alert('Text-to-speech is not supported in this browser.');
    return;
  }
  window.speechSynthesis.cancel();
  const headline = document.getElementById('briefingHeadline')?.innerText || '';
  const greeting = document.getElementById('greetingText')?.innerText || '';
  const utterText = `${greeting}. ${headline}`;
  const utterance = new SpeechSynthesisUtterance(utterText);
  utterance.rate = 1.0;
  window.speechSynthesis.speak(utterance);
}

window.fetchBriefing = fetchBriefing;
window.speakBriefing = speakBriefing;
