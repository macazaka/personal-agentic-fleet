// --- Morning Briefing Engine ---
    async function fetchBriefing() {
      try {
        const res = await fetch('/api/briefing');
        const data = await res.json();
        document.getElementById('greetingText').innerText = `${data.greeting} • ${data.date} (${data.time})`;
        document.getElementById('briefingHeadline').innerText = data.headline;
        
        const stats = data.summary_stats;
        document.getElementById('statsContainer').innerHTML = `
          <div class="stat-pill">
            <span class="label">High Priority</span>
            <span class="val" style="color: var(--accent-pink);">${stats.p1_count}</span>
          </div>
          <div class="stat-pill">
            <span class="label">Open Tasks</span>
            <span class="val">${stats.pending_count}</span>
          </div>
          <div class="stat-pill">
            <span class="label">Completed</span>
            <span class="val" style="color: var(--accent-green);">${stats.completed_count}</span>
          </div>
          <div class="stat-pill">
            <span class="label">Habits Done</span>
            <span class="val" style="color: var(--accent-cyan);">${stats.routines_done}/${stats.routines_total}</span>
          </div>
        `;

        const meetingsContainer = document.getElementById('briefingMeetingsContainer');
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
                  ${m.prep_notes.map(note => `<div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px;">💡 <span style="color: var(--text);">${escapeHtml(note)}</span></div>`).join('')}
                </div>
              </div>
            `).join('')}
          `;
        } else {
          meetingsContainer.style.display = 'none';
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
