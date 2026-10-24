// --- Email Intelligence Engine ---
let globalEmails = [];
let activeFilter = 'ALL';

    async function fetchEmails() {
      try {
        const res = await fetch('/api/emails');
        const data = await res.json();
        
        const counts = data.counts || {};
        globalEmails = data.classified_sample || [];

        // Update live status badge
        const isLive = data.connected_to_live_gmail;
        document.getElementById('emailLiveStatus').innerText = isLive ? "🟢 Live Gmail" : "⚡ Simulation Active";
        
        // Render 5 pills
        document.getElementById('emailPillGrid').innerHTML = `
          <div class="email-pill" onclick="filterEmails('Meetings')">
            <span class="label" style="color: var(--accent-purple);">0) Meetings</span>
            <span class="val" style="color: var(--accent-purple);">${counts.Meetings || 0}</span>
          </div>
          <div class="email-pill" onclick="filterEmails('Respond')">
            <span class="label" style="color: var(--accent-pink);">1) Respond</span>
            <span class="val" style="color: var(--accent-pink);">${counts.Respond || 0}</span>
          </div>
          <div class="email-pill" onclick="filterEmails('Note')">
            <span class="label" style="color: var(--accent-amber);">2) Note</span>
            <span class="val" style="color: var(--accent-amber);">${counts.Note || 0}</span>
          </div>
          <div class="email-pill" onclick="filterEmails('FYI')">
            <span class="label" style="color: var(--accent-green);">3) FYI</span>
            <span class="val" style="color: var(--accent-green);">${counts.FYI || 0}</span>
          </div>
          <div class="email-pill" onclick="filterEmails('Ignore')">
            <span class="label" style="color: var(--text-muted);">4) Ignore</span>
            <span class="val" style="color: var(--text-muted);">${counts.Ignore || 0}</span>
          </div>
        `;

        renderEmailList();
      } catch (e) {
        console.error("Error fetching emails:", e);
      }
    }

    function filterEmails(cat) {
      activeFilter = cat;
      // update filter buttons
      document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.innerText.includes(cat) || (cat === 'ALL' && btn.innerText === 'All')) {
          btn.classList.add('active');
        }
      });
      renderEmailList();
    }

    const expandedEmailBodies = new Set();

    function toggleEmailBody(id) {
      if (expandedEmailBodies.has(id)) {
        expandedEmailBodies.delete(id);
      } else {
        expandedEmailBodies.add(id);
      }
      renderEmailList();
    }

    async function createTaskFromEmail(encodedId) {
      const id = decodeURIComponent(encodedId);
      const email = globalEmails.find(x => x.id === id);
      if (!email) return;

      let taskTitle = "";
      let priority = "P2";
      if (email.category_id === 0) { // Meetings
        taskTitle = `Prep & Attend: ${email.subject.replace(/^(Invitation:\\s*|New Event:\\s*|Updated invitation:\\s*)/i, '').trim()}`;
        priority = "P1";
      } else if (email.category_id === 1) { // Respond
        const senderClean = (email.from || '').split('<')[0].replace(/['"]/g, '').trim() || 'Sender';
        taskTitle = `Reply to ${senderClean}: ${email.subject}`;
        priority = "P1";
      } else if (email.category_id === 2) { // Note
        taskTitle = `Review Note: ${email.subject}`;
        priority = "P2";
      } else if (email.category_id === 3) { // FYI
        taskTitle = `Review FYI: ${email.subject}`;
        priority = "P3";
      } else {
        taskTitle = `Filter: ${email.subject}`;
        priority = "P3";
      }

      const taskDesc = `From: ${email.from}\nSubject: ${email.subject}\n\nEmail Summary / Body:\n${email.snippet || email.body || ''}`.slice(0, 500);

      try {
        const res = await fetch('/api/tasks', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            title: taskTitle,
            description: taskDesc,
            priority: priority,
            source: 'Email'
          })
        });
        const data = await res.json();
        if (data.status === 'success' || data.id) {
          alert(`✓ Added task to 🎯 Daily Tasks & Goals:\n"${taskTitle}" (${priority})`);
          if (typeof fetchTasks === 'function') fetchTasks();
          if (typeof fetchBriefing === 'function') fetchBriefing();
        } else {
          alert(`Failed to add task: ${data.error || 'Unknown error'}`);
        }
      } catch (err) {
        console.error('Failed to create task from email:', err);
        alert('Failed to add task from email.');
      }
    }

    function draftEmailReply(encodedId) {
      const id = decodeURIComponent(encodedId);
      const email = globalEmails.find(x => x.id === id);
      if (!email) return;

      const promptText = `Draft a concise, professional reply to ${email.from} regarding: "${email.subject}". Context: ${email.snippet || email.body}`;

      switchTab('antigravity');
      const inputEl = document.getElementById('agPromptInput');
      if (inputEl) {
        inputEl.value = promptText;
        inputEl.focus();
      }
    }

    function renderEmailList() {
      const container = document.getElementById('emailList');
      const filtered = activeFilter === 'ALL' 
        ? globalEmails 
        : globalEmails.filter(e => e.category_name === activeFilter);

      if (filtered.length === 0) {
        container.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">No emails found in this folder.</div>`;
        return;
      }

      container.innerHTML = filtered.map(e => {
        const badgeClass = `badge-cat-${e.category_id}`;
        const isExpanded = expandedEmailBodies.has(e.id);
        const emailContent = (e.body || e.snippet || '(No content available)').trim();
        const isLong = emailContent.length > 150 || emailContent.includes('\n');

        let unsubActionHtml = '';
        if (e.unsubscribed) {
          unsubActionHtml = `
            <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3); font-size: 11px;">
              ✓ Unsubscribed
            </span>
          `;
        } else if (e.can_unsubscribe || e.category_id === 4 || e.unsubscribe_url) {
          const hasWebLink = e.unsubscribe_url && e.unsubscribe_url.startsWith('http');
          unsubActionHtml = `
            <button class="email-act-btn email-act-btn-unsub" onclick="unsubscribeEmail('${encodeURIComponent(e.id)}')">
              🔕 Unsubscribe
            </button>
            ${hasWebLink ? `<a href="${encodeURI(e.unsubscribe_url)}" target="_blank" rel="noopener noreferrer" class="email-act-btn" style="color: var(--text-muted); font-size: 11px;" title="Open unsubscribe web page">↗ Unsub Page</a>` : ''}
          `;
        } else {
          unsubActionHtml = `
            <button class="email-act-btn email-act-btn-unsub" style="opacity: 0.85;" onclick="unsubscribeEmail('${encodeURIComponent(e.id)}')">
              🔕 Mute / Block
            </button>
          `;
        }

        return `
          <div class="email-item">
            <div class="email-header">
              <span class="email-subject">${escapeHtml(e.subject)}</span>
              <div style="display: flex; align-items: center; gap: 6px;">
                <span class="badge ${badgeClass}">${e.category_name}</span>
              </div>
            </div>
            <div class="email-from">From: ${escapeHtml(e.from)}</div>
            <div class="email-reason">Matched via: ${escapeHtml(e.reason)}</div>

            <!-- Email Body View -->
            <div class="email-body-box ${isExpanded || !isLong ? '' : 'email-body-collapsed'}" id="emailBodyBox_${e.id}">
              ${escapeHtml(emailContent)}
            </div>
            ${isLong ? `
              <div style="margin-top: 4px;">
                <button class="btn" style="font-size: 11px; padding: 2px 8px; color: var(--accent-cyan); border-color: rgba(0, 242, 254, 0.3); cursor: pointer;" onclick="toggleEmailBody('${e.id}')">
                  ${isExpanded ? '▲ Collapse Body' : '▼ View Full Body'}
                </button>
              </div>
            ` : ''}

            <!-- Action Buttons Toolbar -->
            <div class="email-actions">
              <button class="email-act-btn email-act-btn-task" onclick="createTaskFromEmail('${encodeURIComponent(e.id)}')">
                ➕ Add to Tasks
              </button>
              <button class="email-act-btn email-act-btn-reply" onclick="draftEmailReply('${encodeURIComponent(e.id)}')">
                ✉️ Draft Reply
              </button>
              ${unsubActionHtml}
              <a href="https://mail.google.com/mail/u/0/#search/${encodeURIComponent(e.subject || e.id)}" target="_blank" rel="noopener noreferrer" class="email-act-btn" title="Open search in Gmail">
                🌐 Gmail
              </a>
            </div>
          </div>
        `;
      }).join('');
    }

    async function unsubscribeEmail(encodedId) {
      const id = decodeURIComponent(encodedId);
      const email = globalEmails.find(x => x.id === id);
      if (!email) return;
      const fromName = email.from || 'this sender';
      if (!confirm(`Unsubscribe from emails sent by "${fromName}"?`)) return;

      try {
        const res = await fetch('/api/emails/unsubscribe', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            id: email.id,
            url: email.unsubscribe_url || '',
            type: email.unsubscribe_type || 'http',
            sender: email.from || '',
            subject: email.subject || ''
          })
        });
        const data = await res.json();
        if (data.status === 'success') {
          email.unsubscribed = true;
          renderEmailList();
          fetchLogs();
        }
      } catch (err) {
        console.error('Failed to unsubscribe:', err);
      }
    }

    async function syncEmails(forceRefresh = false) {
      const btn = document.getElementById('btnSyncEmails');
      btn.innerText = "⏳ Syncing...";
      btn.disabled = true;

      try {
        await fetch('/api/emails/sync', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ dry_run: false, force_refresh: forceRefresh })
        });
        await fetchEmails();
        await fetchLogs();
      } catch (e) {
        console.error(e);
      } finally {
        btn.innerText = "⚡ Sync & Classify";
        btn.disabled = false;
      }
    }


window.fetchEmails = fetchEmails;
window.filterEmails = filterEmails;
window.toggleEmailBody = toggleEmailBody;
window.createTaskFromEmail = createTaskFromEmail;
window.draftEmailReply = draftEmailReply;
window.renderEmailList = renderEmailList;
window.unsubscribeEmail = unsubscribeEmail;
window.syncEmails = syncEmails;
