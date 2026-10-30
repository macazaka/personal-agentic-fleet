// --- Core Navigation, Utilities & Modals ---
    async function fetchLogs() {
      try {
        const res = await fetch('/api/logs');
        const rawLogs = await res.json();
        const logs = (Array.isArray(rawLogs) ? rawLogs : []).filter(l => {
          const a = (l.agent || '').toLowerCase();
          const d = (l.details || '').toLowerCase();
          return !a.includes('test') && !d.includes('test task') && !d.includes('e2e deep') && !d.includes('ran test') && !d.includes('passed test');
        });
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

    window.isAgRightDocked = true;
    window.lastNonAgTab = 'health';

    function switchTab(tab) {
      if (tab !== 'antigravity') {
        window.lastNonAgTab = tab;
      } else if (window.isAgRightDocked) {
        // When docked to the right panel, ensure the right panel is open and focus its input without hiding the center stage
        if (typeof openAntigravityRightDock === 'function') {
          openAntigravityRightDock();
        }
        const agInput = document.getElementById('agCommandInput');
        if (agInput) agInput.focus();
        return;
      }
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
      const viewStage = document.getElementById('viewActiveAgentStage');

      // Reset tabs
      document.querySelectorAll('.nav-tab').forEach(b => { if (b) b.classList.remove('active'); });
      const dynTabBtn = document.getElementById('tabBtn_' + tab);
      if (dynTabBtn) dynTabBtn.classList.add('active');
      // Reset views (preserve viewAg if it is docked in the right panel)
      if (viewOverview) viewOverview.style.display = 'none';
      if (viewAg && !window.isAgRightDocked) viewAg.style.display = 'none';
      if (viewHealth) viewHealth.style.display = 'none';
      if (viewBacklog) viewBacklog.style.display = 'none';
      if (viewOptimizer) viewOptimizer.style.display = 'none';
      if (viewStage) viewStage.style.display = 'none';

      if (agInterval && tab !== 'antigravity' && !window.isAgRightDocked) {
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
      if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.syncActiveTabUI === 'function') {
        FleetNavigator.syncActiveTabUI(tab);
      }
    }

    function formatInlineMarkdown(escapedLine, codePlaceholders) {
      if (!escapedLine) return '';
      let s = escapedLine;
      const inlineCodes = [];
      s = s.replace(/`([^`\n]+)`/g, (_m, codeTxt) => {
        const idx = inlineCodes.length;
        inlineCodes.push(
          `<code style="background:rgba(15,23,42,0.85); border:1px solid rgba(56,189,248,0.22); padding:1px 6px; border-radius:4px; font-family:monospace; color:#7dd3fc; font-size:11.5px;">${codeTxt}</code>`
        );
        return `@@INLINECODE_${idx}@@`;
      });

      s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_m, label, url) => (
        `<a href="${url}" target="_blank" rel="noopener noreferrer" style="color:#38bdf8; text-decoration:underline;">${label}</a>`
      ));

      s = s.replace(/\*\*([^*\n]+?)\*\*/g, '<strong style="color:#f8fafc; font-weight:600;">$1</strong>');
      s = s.replace(/(^|[\s(])\*([^*\s][^*\n]*?)\*(?=[\s).,;:!?]|$)/g, '$1<em style="color:#cbd5e1;">$2</em>');
      s = s.replace(/(^|[\s(])_([^_\s][^_\n]*?)_(?=[\s).,;:!?]|$)/g, '$1<em style="color:#cbd5e1;">$2</em>');

      s = s.replace(/@@INLINECODE_(\d+)@@/g, (_m, i) => inlineCodes[Number(i)] || '');
      if (codePlaceholders) {
        s = s.replace(/@@CODEBLOCK_(\d+)@@/g, (_m, i) => codePlaceholders[Number(i)] || '');
      }
      return s;
    }

    function formatMarkdown(text) {
      if (!text) return '';
      const raw = String(text).replace(/\r\n/g, '\n');

      const codeBlocks = [];
      const withPlaceholders = raw.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (_m, lang, body) => {
        const idx = codeBlocks.length;
        const langBadge = lang
          ? `<div style="font-size:10px; color:#7dd3fc; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; opacity:0.85;">${escapeHtml(lang)}</div>`
          : '';
        codeBlocks.push(
          `<pre style="background:rgba(2,6,23,0.75); border:1px solid rgba(56,189,248,0.2); padding:10px 12px; border-radius:7px; overflow-x:auto; margin:7px 0; font-size:11.5px; line-height:1.48; font-family:monospace; color:#bae6fd; white-space:pre;">${langBadge}<code>${escapeHtml(body.replace(/\n$/, ''))}</code></pre>`
        );
        return `\n@@CODEBLOCK_${idx}@@\n`;
      });

      const lines = withPlaceholders.split('\n');
      const blocks = [];
      let i = 0;

      while (i < lines.length) {
        const rawLine = lines[i];
        const trimmed = rawLine.trim();

        if (!trimmed) {
          i += 1;
          continue;
        }

        const cbMatch = trimmed.match(/^@@CODEBLOCK_(\d+)@@$/);
        if (cbMatch) {
          blocks.push(codeBlocks[Number(cbMatch[1])] || '');
          i += 1;
          continue;
        }

        if (/^(?:---|\*\*\*|___)\s*$/.test(trimmed)) {
          blocks.push('<hr style="border:none; border-top:1px solid rgba(255,255,255,0.1); margin:8px 0;">');
          i += 1;
          continue;
        }

        const hMatch = trimmed.match(/^(#{1,4})\s+(.+)$/);
        if (hMatch) {
          const level = hMatch[1].length;
          const hText = formatInlineMarkdown(escapeHtml(hMatch[2].trim()), codeBlocks);
          const fontSize = level === 1 ? '14.5px' : (level === 2 ? '13.5px' : '12.5px');
          const color = level <= 2 ? '#f8fafc' : '#7dd3fc';
          blocks.push(
            `<div style="font-size:${fontSize}; font-weight:700; color:${color}; margin:${blocks.length > 0 ? '9px' : '2px'} 0 5px 0; letter-spacing:0.15px;">${hText}</div>`
          );
          i += 1;
          continue;
        }

        if (
          trimmed.startsWith('|') &&
          i + 1 < lines.length &&
          /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1].trim())
        ) {
          const parseRow = (rowStr) =>
            rowStr.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
          const headers = parseRow(trimmed);
          i += 2;
          const bodyRows = [];
          while (i < lines.length && lines[i].trim().startsWith('|')) {
            bodyRows.push(parseRow(lines[i]));
            i += 1;
          }
          const thHtml = headers
            .map(h => `<th style="padding:6px 9px; text-align:left; font-size:11px; color:#7dd3fc; border-bottom:1px solid rgba(56,189,248,0.25); background:rgba(15,23,42,0.85);">${formatInlineMarkdown(escapeHtml(h), codeBlocks)}</th>`)
            .join('');
          const trHtml = bodyRows
            .map(cols => `<tr style="border-bottom:1px solid rgba(255,255,255,0.06);">${cols.map(c => `<td style="padding:6px 9px; font-size:12px; color:#e2e8f0;">${formatInlineMarkdown(escapeHtml(c), codeBlocks)}</td>`).join('')}</tr>`)
            .join('');
          blocks.push(
            `<div style="overflow-x:auto; margin:7px 0;"><table style="width:100%; border-collapse:collapse; border:1px solid rgba(255,255,255,0.08); border-radius:6px; overflow:hidden;"><thead><tr>${thHtml}</tr></thead><tbody>${trHtml}</tbody></table></div>`
          );
          continue;
        }

        if (/^>\s?/.test(trimmed)) {
          const quoteLines = [];
          while (i < lines.length && /^>\s?/.test(lines[i].trim())) {
            quoteLines.push(formatInlineMarkdown(escapeHtml(lines[i].trim().replace(/^>\s?/, '')), codeBlocks));
            i += 1;
          }
          blocks.push(
            `<div style="margin:6px 0; padding:7px 11px; border-left:3px solid #38bdf8; background:rgba(56,189,248,0.09); border-radius:0 6px 6px 0; color:#e0f2fe; font-size:12px; line-height:1.5;">${quoteLines.join('<br>')}</div>`
          );
          continue;
        }

        if (/^(?:[-*•])\s+/.test(trimmed)) {
          const items = [];
          while (i < lines.length && /^(?:[-*•])\s+/.test(lines[i].trim())) {
            const itemTxt = lines[i].trim().replace(/^(?:[-*•])\s+/, '');
            items.push(
              `<li style="line-height:1.54; color:#e2e8f0; padding-left:2px;">${formatInlineMarkdown(escapeHtml(itemTxt), codeBlocks)}</li>`
            );
            i += 1;
          }
          blocks.push(
            `<ul style="margin:4px 0 8px 0; padding-left:18px; display:flex; flex-direction:column; gap:5px;">${items.join('')}</ul>`
          );
          continue;
        }

        if (/^\d+\.\s+/.test(trimmed)) {
          const items = [];
          while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
            const itemTxt = lines[i].trim().replace(/^\d+\.\s+/, '');
            items.push(
              `<li style="line-height:1.54; color:#e2e8f0; padding-left:2px;">${formatInlineMarkdown(escapeHtml(itemTxt), codeBlocks)}</li>`
            );
            i += 1;
          }
          blocks.push(
            `<ol style="margin:4px 0 8px 0; padding-left:20px; display:flex; flex-direction:column; gap:5px;">${items.join('')}</ol>`
          );
          continue;
        }

        const paraLines = [];
        while (
          i < lines.length &&
          lines[i].trim() !== '' &&
          !/^@@CODEBLOCK_\d+@@$/.test(lines[i].trim()) &&
          !/^(?:#{1,4}\s+|[-*•]\s+|\d+\.\s+|>\s?|(?:---|\*\*\*|___)\s*$)/.test(lines[i].trim()) &&
          !(lines[i].trim().startsWith('|') && i + 1 < lines.length && /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(lines[i + 1].trim()))
        ) {
          paraLines.push(formatInlineMarkdown(escapeHtml(lines[i].trim()), codeBlocks));
          i += 1;
        }
        blocks.push(`<div style="margin:4px 0; line-height:1.56;">${paraLines.join('<br>')}</div>`);
      }

      return blocks.join('');
    }

    if (typeof window !== 'undefined') {
      window.formatMarkdown = formatMarkdown;
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
