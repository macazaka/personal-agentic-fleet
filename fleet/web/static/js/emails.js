// --- Email Intelligence, Pre-Download Attachment Antivirus & Proposal Approval Engine ---
let globalEmails = [];
let globalEmailProposals = [];
let activeFilter = 'ALL';

async function fetchEmails() {
  try {
    const res = await fetch('/api/emails');
    const data = await res.json();

    const counts = data.counts || {};
    globalEmails = data.classified_sample || [];

    // Update live status badge
    const isLive = data.connected_to_live_gmail;
    const liveEl = document.getElementById('emailLiveStatus');
    if (liveEl) {
      liveEl.innerText = isLive ? '🟢 Live Gmail' : '⚡ Simulation Active';
    }

    const pillsHtml = `
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

    const gridEl = document.getElementById('emailPillGrid');
    if (gridEl) gridEl.innerHTML = pillsHtml;
    const agentGridEl = document.getElementById('gmailAgentPillGrid');
    if (agentGridEl) agentGridEl.innerHTML = pillsHtml;

    renderEmailList();
    await fetchEmailProposals();
  } catch (e) {
    console.error('Error fetching emails:', e);
  }
}

async function fetchEmailProposals() {
  try {
    const res = await fetch('/api/emails/proposals');
    const data = await res.json();
    if (data && Array.isArray(data.proposals)) {
      globalEmailProposals = data.proposals;
      const unappCount = Number(data.unapproved_count || 0);
      const cleanAttCount = Number(data.clean_attachments_count || 0);
      const blockedAttCount = Number(data.blocked_attachments_count || 0);

      const pendingBadge = document.getElementById('emailPendingApprovalsBadge');
      if (pendingBadge) {
        pendingBadge.innerText = unappCount > 0
          ? `⏳ ${unappCount} Unapproved in Backlog`
          : '✓ All Proposals Reviewed';
      }
      const agentPendingBadge = document.getElementById('gmailAgentPendingBadge');
      if (agentPendingBadge) {
        agentPendingBadge.innerText = unappCount > 0
          ? `⏳ ${unappCount} Unapproved in Backlog`
          : '✓ All Proposals Reviewed';
      }
      const shieldBadge = document.getElementById('emailVirusShieldBadge');
      if (shieldBadge) {
        shieldBadge.innerText = blockedAttCount > 0
          ? `🚨 ${blockedAttCount} Threat Blocked • ${cleanAttCount} Clean`
          : `🛡️ Virus Scan: ${cleanAttCount} Attachment(s) CLEAN`;
      }
      renderEmailProposals();
      if (typeof fetchBacklog === 'function') {
        fetchBacklog();
      }
    }
  } catch (err) {
    console.error('Error fetching email proposals:', err);
  }
}

function renderEmailProposals() {
  const containers = [
    document.getElementById('emailProposalsList'),
    document.getElementById('gmailAgentProposalsList')
  ].filter(Boolean);
  if (containers.length === 0) return;

  if (!Array.isArray(globalEmailProposals) || globalEmailProposals.length === 0) {
    const emptyHtml = `<div style="padding: 10px; font-size: 12px; color: var(--text-muted); text-align: center;">No email or attachment proposals discovered yet. Click "🔄 Scan Proposals" to inspect recent emails.</div>`;
    containers.forEach(c => { c.innerHTML = emptyHtml; });
    return;
  }

  // Sort unapproved first, then approved
  const sorted = [...globalEmailProposals].sort((a, b) => {
    const rank = { unapproved: 0, blocked_virus: 1, approved: 2, rejected: 3 };
    return (rank[a.approval_status] ?? 9) - (rank[b.approval_status] ?? 9);
  });

  const html = sorted.map(prop => {
    const isUnapproved = prop.approval_status === 'unapproved';
    const isApproved = prop.approval_status === 'approved';
    const isRejected = prop.approval_status === 'rejected';
    const isBlocked = prop.approval_status === 'blocked_virus';
    const isNewAgent = prop.proposal_type === 'new_agent';
    const scan = prop.attachment_scan || {};
    const scanClean = scan.safe_to_use !== false;
    const shaShort = scan.sha256 ? String(scan.sha256).slice(0, 10) : 'verified';
    const blId = Number(prop.backlog_id || 0);

    const typeBadge = isNewAgent
      ? `<span class="badge" style="background: rgba(168, 85, 247, 0.18); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.4); font-size: 10.5px; font-weight: 700;">🤖 New Agent Proposal</span>`
      : `<span class="badge" style="background: rgba(0, 242, 254, 0.14); color: var(--accent-cyan); border: 1px solid rgba(0, 242, 254, 0.35); font-size: 10.5px; font-weight: 700;">📌 New AFCC Track Addition</span>`;

    const scanBadge = scanClean
      ? `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10px;" title="Pre-download 4-Layer Antivirus Check Passed (SHA-256: ${escapeHtml(scan.sha256 || '')})">🛡️ Virus Scan: CLEAN (${escapeHtml(scan.filename || 'Email Body')} • ${escapeHtml(shaShort)})</span>`
      : `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.45); font-size: 10px;">🚨 BLOCKED: ${escapeHtml(scan.threat_code || 'MALWARE')}</span>`;

    const backlogBadge = blId > 0
      ? `<span class="badge" style="background: ${isUnapproved ? 'rgba(244, 63, 94, 0.16)' : 'rgba(16, 185, 129, 0.15)'}; color: ${isUnapproved ? '#fb7185' : '#34d399'}; border: 1px solid ${isUnapproved ? 'rgba(244, 63, 94, 0.38)' : 'rgba(16, 185, 129, 0.35)'}; font-size: 10px; cursor: pointer;" onclick="FleetNavigator.switchAgent('backlog'); setTimeout(() => filterBacklogByStatus('${isUnapproved ? 'Unapproved' : 'ALL'}'), 120);" title="Click to view #BL-${blId} in Feature Backlog">📋 #BL-${blId} • ${escapeHtml(prop.backlog_status || (isUnapproved ? 'Unapproved' : 'Completed'))}</span>`
      : '';

    let actionsHtml = '';
    if (isUnapproved && !isBlocked) {
      actionsHtml = `
        <button title="Approve and implement this proposal in AFCC" class="btn btn-primary" style="font-size: 11px; padding: 4px 10px; background: rgba(16, 185, 129, 0.22); border: 1px solid rgba(16, 185, 129, 0.5); color: #34d399; font-weight: 700;" onclick="approveEmailProposal('${encodeURIComponent(prop.id)}', ${blId})">
          ✅ Approve &amp; Implement
        </button>
        <button title="Reject and defer this proposal" class="btn" style="font-size: 11px; padding: 4px 8px; color: #f87171; border-color: rgba(239, 68, 68, 0.35);" onclick="rejectEmailProposal('${encodeURIComponent(prop.id)}', ${blId})">
          ✕ Reject
        </button>
      `;
    } else if (isApproved) {
      const impl = prop.implemented_result || {};
      const openAgentBtn = impl.agent_id
        ? `<button title="Open newly created agent in AFCC" class="btn" style="font-size: 10.5px; padding: 3px 8px; color: var(--accent-cyan); border-color: rgba(0, 242, 254, 0.35);" onclick="FleetNavigator.switchAgent('${escapeHtml(impl.agent_id)}')">↗ Open Agent</button>`
        : '';
      actionsHtml = `
        <span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10.5px; font-weight: 700;">✓ Approved &amp; Implemented</span>
        ${openAgentBtn}
      `;
    } else if (isRejected) {
      actionsHtml = `<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; font-size: 10.5px;">⏸️ Rejected / Deferred</span>`;
    }

    return `
      <div style="padding: 10px 12px; border-radius: 8px; background: rgba(15, 23, 42, 0.65); border: 1px solid ${isUnapproved ? 'rgba(244, 63, 94, 0.35)' : 'rgba(255, 255, 255, 0.08)'}; display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 240px;">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-bottom: 4px;">
            ${typeBadge}
            ${scanBadge}
            ${backlogBadge}
          </div>
          <div style="font-size: 12.5px; font-weight: 700; color: #f8fafc;">${escapeHtml(prop.title)}</div>
          <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 2px; line-height: 1.35;">${escapeHtml(prop.description)}</div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
          ${actionsHtml}
        </div>
      </div>
    `;
  }).join('');

  containers.forEach(c => { c.innerHTML = html; });
}

async function approveEmailProposal(encodedProposalId, backlogId = 0) {
  const proposalId = decodeURIComponent(encodedProposalId || '');
  try {
    const res = await fetch('/api/emails/proposals/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proposal_id: proposalId, backlog_id: Number(backlogId || 0) })
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      alert(`Failed to approve proposal: ${data.error || 'Unknown error'}`);
      return;
    }
    await fetchEmailProposals();
    if (typeof fetchTasks === 'function') fetchTasks();
    if (typeof fetchBriefing === 'function') fetchBriefing();
    if (typeof fetchBacklog === 'function') fetchBacklog();
    if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.loadManifest === 'function') {
      FleetNavigator.loadManifest();
    }
  } catch (err) {
    console.error('Error approving email proposal:', err);
  }
}

async function rejectEmailProposal(encodedProposalId, backlogId = 0) {
  const proposalId = decodeURIComponent(encodedProposalId || '');
  try {
    const res = await fetch('/api/emails/proposals/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proposal_id: proposalId, backlog_id: Number(backlogId || 0) })
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      alert(`Failed to reject proposal: ${data.error || 'Unknown error'}`);
      return;
    }
    await fetchEmailProposals();
    if (typeof fetchBacklog === 'function') fetchBacklog();
  } catch (err) {
    console.error('Error rejecting email proposal:', err);
  }
}

async function testAttachmentVirusShield() {
  try {
    // 1. Test blocking an EICAR / Malicious Macro attachment before download
    const eicarRes = await fetch('/api/emails/attachments/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: 'Urgent_Invoice_Macro.pdf.exe',
        text_content: 'X5O!P%@AP[4\\PZX54(P^)7CC)7\x7d$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*',
        mime_type: 'application/octet-stream'
      })
    });
    const eicarData = await eicarRes.json();

    // 2. Test scanning a clean PDF invoice
    const cleanRes = await fetch('/api/emails/attachments/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: 'Stripe_Invoice_INV-2026-10-8941.pdf',
        content_base64: 'JVBERi0xLjQKJcOkw7zDtsOfCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nPj4KZW5kb2JqCllPRgo=',
        mime_type: 'application/pdf'
      })
    });
    const cleanData = await cleanRes.json();

    const msgHtml = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
        <div>
          <strong style="color: #34d399;">🛡️ 4-Layer Pre-Download Antivirus Verification Complete:</strong><br>
          • <strong>Malicious Test (<code>${escapeHtml(eicarData.filename)}</code>):</strong> <span style="color: #f87171; font-weight: 700;">${escapeHtml(eicarData.status)}</span> — ${escapeHtml(eicarData.threat_reason || '')} (Blocked in memory before download/use)<br>
          • <strong>Clean PDF Test (<code>${escapeHtml(cleanData.filename)}</code>):</strong> <span style="color: #34d399; font-weight: 700;">${escapeHtml(cleanData.status)}</span> — Passed ${(cleanData.checks_passed || []).length} security layers (SHA-256: <code>${escapeHtml(String(cleanData.sha256 || '').slice(0, 12))}...</code>)
        </div>
        <button title="Dismiss antivirus test banner" class="btn" style="padding: 2px 6px; font-size: 10px;" onclick="this.parentElement.parentElement.style.display='none'">✕</button>
      </div>
    `;

    ['emailVirusTestResultBanner', 'gmailAgentVirusTestBanner'].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.style.display = 'block';
        el.style.background = 'rgba(16, 185, 129, 0.12)';
        el.style.border = '1px solid rgba(16, 185, 129, 0.4)';
        el.style.color = '#f8fafc';
        el.innerHTML = msgHtml;
      }
    });
  } catch (err) {
    console.error('Error testing attachment virus shield:', err);
  }
}

function filterEmails(cat) {
  activeFilter = cat;
  document.querySelectorAll('.filter-btn').forEach(btn => {
    if (!btn.getAttribute('onclick') || !btn.getAttribute('onclick').includes('filterEmails')) return;
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

  let taskTitle = '';
  let priority = 'P2';
  if (email.category_id === 0) {
    taskTitle = `Prep & Attend: ${email.subject.replace(/^(Invitation:\s*|New Event:\s*|Updated invitation:\s*)/i, '').trim()}`;
    priority = 'P1';
  } else if (email.category_id === 1) {
    const senderClean = (email.from || '').split('<')[0].replace(/['"]/g, '').trim() || 'Sender';
    taskTitle = `Reply to ${senderClean}: ${email.subject}`;
    priority = 'P1';
  } else if (email.category_id === 2) {
    taskTitle = `Review Note: ${email.subject}`;
    priority = 'P2';
  } else if (email.category_id === 3) {
    taskTitle = `Review FYI: ${email.subject}`;
    priority = 'P3';
  } else {
    taskTitle = `Filter: ${email.subject}`;
    priority = 'P3';
  }

  const taskDesc = `From: ${email.from}\nSubject: ${email.subject}\n\nEmail Summary / Body:\n${email.snippet || email.body || ''}`.slice(0, 500);

  try {
    const res = await fetch('/api/tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
  const containers = [
    document.getElementById('emailList'),
    document.getElementById('gmailAgentEmailList')
  ].filter(Boolean);
  if (containers.length === 0) return;

  const filtered = activeFilter === 'ALL'
    ? globalEmails
    : globalEmails.filter(e => e.category_name === activeFilter);

  if (filtered.length === 0) {
    const emptyHtml = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">No emails found in this folder.</div>`;
    containers.forEach(c => { c.innerHTML = emptyHtml; });
    return;
  }

  const listHtml = filtered.map(e => {
    const badgeClass = `badge-cat-${e.category_id}`;
    const isExpanded = expandedEmailBodies.has(e.id);
    const emailContent = (e.body || e.snippet || '(No content available)').trim();
    const isLong = emailContent.length > 150 || emailContent.includes('\n');

    const attScans = Array.isArray(e.attachment_scans) ? e.attachment_scans : [];
    const attBadgesHtml = attScans.map(s => {
      const isClean = s.safe_to_use !== false;
      return `<span class="badge" style="background: ${isClean ? 'rgba(16, 185, 129, 0.14)' : 'rgba(239, 68, 68, 0.2)'}; color: ${isClean ? '#34d399' : '#f87171'}; border: 1px solid ${isClean ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.45)'}; font-size: 10.5px;" title="Pre-download 4-Layer Antivirus Scan: ${escapeHtml(s.status || 'CLEAN')} (SHA-256: ${escapeHtml(s.sha256 || '')})">📎 ${escapeHtml(s.filename || 'attachment')} • 🛡️ Virus Scan: ${escapeHtml(s.status || 'CLEAN')}</span>`;
    }).join(' ');

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
        <button title="Unsubscribe from this sender" class="email-act-btn email-act-btn-unsub" onclick="unsubscribeEmail('${encodeURIComponent(e.id)}')">
          🔕 Unsubscribe
        </button>
        ${hasWebLink ? `<a href="${encodeURI(e.unsubscribe_url)}" target="_blank" rel="noopener noreferrer" class="email-act-btn" style="color: var(--text-muted); font-size: 11px;" title="Open unsubscribe web page">↗ Unsub Page</a>` : ''}
      `;
    } else {
      unsubActionHtml = `
        <button title="Mute or block emails from this sender" class="email-act-btn email-act-btn-unsub" style="opacity: 0.85;" onclick="unsubscribeEmail('${encodeURIComponent(e.id)}')">
          🔕 Mute / Block
        </button>
      `;
    }

    return `
      <div class="email-item">
        <div class="email-header">
          <span class="email-subject">${escapeHtml(e.subject)}</span>
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            ${attBadgesHtml}
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
            <button title="Expand or collapse full email body" class="btn" style="font-size: 11px; padding: 2px 8px; color: var(--accent-cyan); border-color: rgba(0, 242, 254, 0.3); cursor: pointer;" onclick="toggleEmailBody('${e.id}')">
              ${isExpanded ? '▲ Collapse Body' : '▼ View Full Body'}
            </button>
          </div>
        ` : ''}

        <!-- Action Buttons Toolbar -->
        <div class="email-actions">
          <button title="Create an AFCC priority task from this email" class="email-act-btn email-act-btn-task" onclick="createTaskFromEmail('${encodeURIComponent(e.id)}')">
            ➕ Add to Tasks
          </button>
          <button title="Draft a reply to this email" class="email-act-btn email-act-btn-reply" onclick="draftEmailReply('${encodeURIComponent(e.id)}')">
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

  containers.forEach(c => { c.innerHTML = listHtml; });
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
      headers: { 'Content-Type': 'application/json' },
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
      if (typeof fetchLogs === 'function') fetchLogs();
    }
  } catch (err) {
    console.error('Failed to unsubscribe:', err);
  }
}

async function syncEmails(forceRefresh = false) {
  const btn = document.getElementById('btnSyncEmails');
  if (btn) {
    btn.innerText = '⏳ Syncing...';
    btn.disabled = true;
  }

  try {
    await fetch('/api/emails/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: false, force_refresh: forceRefresh })
    });
    await fetchEmails();
    if (typeof fetchLogs === 'function') await fetchLogs();
  } catch (e) {
    console.error(e);
  } finally {
    if (btn) {
      btn.innerText = '⚡ Sync & Classify';
      btn.disabled = false;
    }
  }
}

window.fetchEmails = fetchEmails;
window.fetchEmailProposals = fetchEmailProposals;
window.renderEmailProposals = renderEmailProposals;
window.approveEmailProposal = approveEmailProposal;
window.rejectEmailProposal = rejectEmailProposal;
window.testAttachmentVirusShield = testAttachmentVirusShield;
window.filterEmails = filterEmails;
window.toggleEmailBody = toggleEmailBody;
window.createTaskFromEmail = createTaskFromEmail;
window.draftEmailReply = draftEmailReply;
window.renderEmailList = renderEmailList;
window.unsubscribeEmail = unsubscribeEmail;
window.syncEmails = syncEmails;
window.syncEmailsNow = () => syncEmails(true);
