// --- Core Navigation, Utilities & Modals ---
    async function fetchLogs() {
      try {
        const res = await fetch('/api/logs');
        const logs = await res.json();
        const stream = document.getElementById('logStream');
        stream.innerHTML = logs.map(l => `
          <div class="log-entry">
            <span style="color: var(--accent-cyan); font-weight: 600;">[${escapeHtml(l.agent)}]</span>
            <span>${escapeHtml(l.details)}</span>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function triggerNotification() {
      await fetch('/api/notify', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          title: "Personal Agentic Fleet",
          message: "Fleet active! All systems operational and ready on your laptop."
        })
      });
      fetchLogs();
    }

    function escapeHtml(text) {
      const div = document.createElement('div');
      div.innerText = text;
      return div.innerHTML;
    }

    // --- Antigravity Live Stream, Model Selector & Queue Engine ---
    let currentTab = 'health';
    let agInterval = null;
    let lastRenderedStep = -1;
    let attachedImages = [];
    let activeModelId = 'gemini-3.8-flash-high';
    let availableModels = [];

    function switchTab(tab) {
      currentTab = tab;
      const tabOverview = document.getElementById('tabBtnOverview');
      const tabAg = document.getElementById('tabBtnAntigravity');
      const tabHealth = document.getElementById('tabBtnHealth');
      const tabBacklog = document.getElementById('tabBtnBacklog');
      const tabOptimizer = document.getElementById('tabBtnOptimizer');
      const viewOverview = document.getElementById('viewOverview');
      const viewAg = document.getElementById('viewAntigravity');
      const viewHealth = document.getElementById('viewHealth');
      const viewBacklog = document.getElementById('viewBacklog');
      const viewOptimizer = document.getElementById('viewOptimizer');

      // Reset tabs
      [tabOverview, tabAg, tabHealth, tabBacklog, tabOptimizer].forEach(b => { if (b) b.classList.remove('active'); });
      // Reset views
      if (viewOverview) viewOverview.style.display = 'none';
      if (viewAg) viewAg.style.display = 'none';
      if (viewHealth) viewHealth.style.display = 'none';
      if (viewBacklog) viewBacklog.style.display = 'none';
      if (viewOptimizer) viewOptimizer.style.display = 'none';

      if (agInterval && tab !== 'antigravity') {
        clearInterval(agInterval);
        agInterval = null;
      }

      if (tab === 'overview') {
        if (tabOverview) tabOverview.classList.add('active');
        if (viewOverview) viewOverview.style.display = 'block';
      } else if (tab === 'antigravity') {
        if (tabAg) tabAg.classList.add('active');
        if (viewAg) viewAg.style.display = 'flex';
        fetchTranscript(true);
        fetchModels();
        fetchAgentQueue();
        if (!agInterval) {
          agInterval = setInterval(() => {
            fetchTranscript(false);
            fetchAgentQueue();
          }, 2500);
        }
      } else if (tab === 'health') {
        if (tabHealth) tabHealth.classList.add('active');
        if (viewHealth) viewHealth.style.display = 'flex';
        fetchHealthDashboard();
      } else if (tab === 'backlog') {
        if (tabBacklog) tabBacklog.classList.add('active');
        if (viewBacklog) viewBacklog.style.display = 'flex';
        fetchBacklog();
      } else if (tab === 'optimizer') {
        if (tabOptimizer) tabOptimizer.classList.add('active');
        if (viewOptimizer) viewOptimizer.style.display = 'flex';
        fetchOptimizerDiagnostics();
      }
    }

    function formatMarkdown(text) {
      if (!text) return '';
      let html = escapeHtml(text);
      // Code blocks ```code```
      html = html.replace(/```([\\s\\S]*?)```/g, '<pre style="background:rgba(0,0,0,0.5); padding:10px; border-radius:6px; overflow-x:auto; margin:8px 0; font-size:12px; font-family:monospace; color:#38bdf8;"><code>$1</code></pre>');
      // Inline code `code`
      html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 5px; border-radius:4px; font-family:monospace; color:#38bdf8; font-size:12px;">$1</code>');
      // Bold **bold**
      html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
      // Newlines to <br>
      html = html.replace(/\\n/g, '<br>');
      return html;
    }


    async function fetchVersion() {
      try {
        const res = await fetch('/api/version');
        const data = await res.json();
        if (data.version) {
          const hBadge = document.getElementById('fleetHeaderVerBadge');
          if (hBadge) hBadge.innerText = `v${data.version}`;
          const vLabel = document.getElementById('currentReleaseVerLabel');
          if (vLabel) vLabel.innerText = `Current Release: v${data.version}`;
        }
      } catch (e) {
        console.error('Error fetching version:', e);
      }
    }

    async function openReleaseNotesModal() {
      const modal = document.getElementById('releaseNotesModal');
      const body = document.getElementById('releaseNotesBody');
      if (!modal || !body) return;
      modal.style.display = 'flex';
      body.innerHTML = '<div style="color:var(--text-muted); padding:20px; text-align:center;">Loading release notes...</div>';
      try {
        const res = await fetch('/api/release_notes');
        const data = await res.json();
        const md = data.changelog_markdown || '';
        body.innerHTML = renderReleaseNotesMarkdown(md);
        if (data.version) {
          const vLabel = document.getElementById('currentReleaseVerLabel');
          if (vLabel) vLabel.innerText = `Current Release: v${data.version}`;
          const hBadge = document.getElementById('fleetHeaderVerBadge');
          if (hBadge) hBadge.innerText = `v${data.version}`;
        }
      } catch (e) {
        body.innerHTML = `<div style="color:#f87171;">Failed to load release notes: ${escapeHtml(e.message)}</div>`;
      }
    }

    function closeReleaseNotesModal() {
      const modal = document.getElementById('releaseNotesModal');
      if (modal) modal.style.display = 'none';
    }

    function renderReleaseNotesMarkdown(md) {
      if (!md) return '<p>No release notes available.</p>';
      const lines = md.split(/\r?\n/);
      const out = [];
      let inList = false;

      for (let rawLine of lines) {
        let line = rawLine.trim();
        if (!line) {
          if (inList) { out.push('</ul>'); inList = false; }
          continue;
        }

        if (line.startsWith('## ')) {
          if (inList) { out.push('</ul>'); inList = false; }
          let title = escapeHtml(line.substring(3));
          out.push(`<h2 style="font-size:16px; color:var(--accent-cyan); margin:18px 0 8px 0; border-bottom:1px solid rgba(255,255,255,0.08); padding-bottom:4px;">${title}</h2>`);
        } else if (line.startsWith('### ')) {
          if (inList) { out.push('</ul>'); inList = false; }
          let sub = escapeHtml(line.substring(4));
          out.push(`<h3 style="font-size:13.5px; color:#c084fc; margin:12px 0 6px 0;">${sub}</h3>`);
        } else if (line.startsWith('- ') || line.startsWith('* ')) {
          if (!inList) { out.push('<ul style="margin:4px 0 8px 20px; padding:0;">'); inList = true; }
          let item = escapeHtml(line.substring(2));
          item = item.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08); padding:2px 5px; border-radius:4px; font-family:monospace; color:#38bdf8;">$1</code>');
          item = item.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
          out.push(`<li style="margin-bottom:4px;">${item}</li>`);
        } else if (line.startsWith('# ')) {
          if (inList) { out.push('</ul>'); inList = false; }
          let mainTitle = escapeHtml(line.substring(2));
          out.push(`<h1 style="font-size:18px; color:#fff; margin-bottom:10px;">${mainTitle}</h1>`);
        } else {
          if (inList) { out.push('</ul>'); inList = false; }
          let p = escapeHtml(line);
          p = p.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:var(--accent-blue); text-decoration:none;">$1</a>');
          out.push(`<p style="margin-bottom:8px; color:var(--text-muted);">${p}</p>`);
        }
      }
      if (inList) out.push('</ul>');
      return out.join('');
    }

    // --- Token Health & Quota Monitor ---

window.switchTab = switchTab;
window.escapeHtml = escapeHtml;
window.formatMarkdown = formatMarkdown;
window.fetchLogs = fetchLogs;
window.triggerNotification = triggerNotification;
window.fetchVersion = fetchVersion;
window.openReleaseNotesModal = openReleaseNotesModal;
window.closeReleaseNotesModal = closeReleaseNotesModal;
window.renderReleaseNotesMarkdown = renderReleaseNotesMarkdown;
