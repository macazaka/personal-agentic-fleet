// --- Feature Backlog Management (Multi-Select Status & Priority Filtering) ---
let selectedBacklogStatuses = new Set();
let selectedBacklogPriorities = new Set();
let activeBacklogStatusFilter = 'ALL';
let activeBacklogPriorityFilter = 'ALL';
let globalBacklogItems = [];

const BACKLOG_STATUS_BTN_MAP = {
  'Unapproved': { id: 'backlogFilterStatusUnapproved', label: '⏳ Unapproved' },
  'Idea': { id: 'backlogFilterStatusIdea', label: '💡 Idea' },
  'Planned': { id: 'backlogFilterStatusPlanned', label: '📅 Planned' },
  'In Progress': { id: 'backlogFilterStatusProgress', label: '⚡ In Progress' },
  'Completed': { id: 'backlogFilterStatusCompleted', label: '✅ Completed' }
};

const BACKLOG_PRIORITY_BTN_MAP = {
  'P1': { id: 'backlogFilterPriorityP1', label: '🔴 P1' },
  'P2': { id: 'backlogFilterPriorityP2', label: '🟡 P2' },
  'P3': { id: 'backlogFilterPriorityP3', label: '🟢 P3' }
};

function toggleAddBacklogCard() {
  const card = document.getElementById('addBacklogCard');
  const btn = document.getElementById('btnToggleAddBacklog');
  if (!card) return;
  const isHidden = card.style.display === 'none' || card.style.display === '';
  card.style.display = isHidden ? 'block' : 'none';
  if (isHidden) {
    document.getElementById('newBacklogTitle').focus();
    if (btn) btn.innerText = '✕ Close Form';
  } else {
    if (btn) btn.innerText = '+ Add New Feature';
  }
}

function syncBacklogStatusFilterButtons() {
  const allBtn = document.getElementById('backlogFilterStatusAll');
  const isAll = selectedBacklogStatuses.size === 0;
  if (allBtn) {
    allBtn.classList.toggle('active', isAll);
    allBtn.setAttribute('aria-pressed', isAll ? 'true' : 'false');
  }
  Object.entries(BACKLOG_STATUS_BTN_MAP).forEach(([statusKey, meta]) => {
    const btn = document.getElementById(meta.id);
    if (!btn) return;
    const isSelected = selectedBacklogStatuses.has(statusKey);
    btn.classList.toggle('active', isSelected);
    btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    btn.innerText = isSelected ? `✓ ${meta.label}` : meta.label;
  });
}

function syncBacklogPriorityFilterButtons() {
  const allBtn = document.getElementById('backlogFilterPriorityAll');
  const isAll = selectedBacklogPriorities.size === 0;
  if (allBtn) {
    allBtn.classList.toggle('active', isAll);
    allBtn.setAttribute('aria-pressed', isAll ? 'true' : 'false');
  }
  Object.entries(BACKLOG_PRIORITY_BTN_MAP).forEach(([prioKey, meta]) => {
    const btn = document.getElementById(meta.id);
    if (!btn) return;
    const isSelected = selectedBacklogPriorities.has(prioKey);
    btn.classList.toggle('active', isSelected);
    btn.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
    btn.innerText = isSelected ? `✓ ${meta.label}` : meta.label;
  });
}

function filterBacklogByStatus(status) {
  if (!status || String(status).toUpperCase() === 'ALL') {
    selectedBacklogStatuses.clear();
  } else if (String(status).includes(',')) {
    selectedBacklogStatuses = new Set(
      String(status).split(',').map(s => s.trim()).filter(Boolean)
    );
  } else {
    const clean = String(status).trim();
    if (selectedBacklogStatuses.has(clean)) {
      selectedBacklogStatuses.delete(clean);
    } else {
      selectedBacklogStatuses.add(clean);
    }
  }
  activeBacklogStatusFilter = selectedBacklogStatuses.size > 0
    ? Array.from(selectedBacklogStatuses).join(',')
    : 'ALL';
  syncBacklogStatusFilterButtons();
  fetchBacklog();
}

function filterBacklogByPriority(priority) {
  if (!priority || String(priority).toUpperCase() === 'ALL') {
    selectedBacklogPriorities.clear();
  } else if (String(priority).includes(',')) {
    selectedBacklogPriorities = new Set(
      String(priority).split(',').map(p => p.trim().toUpperCase()).filter(Boolean)
    );
  } else {
    const clean = String(priority).trim().toUpperCase();
    if (selectedBacklogPriorities.has(clean)) {
      selectedBacklogPriorities.delete(clean);
    } else {
      selectedBacklogPriorities.add(clean);
    }
  }
  activeBacklogPriorityFilter = selectedBacklogPriorities.size > 0
    ? Array.from(selectedBacklogPriorities).join(',')
    : 'ALL';
  syncBacklogPriorityFilterButtons();
  fetchBacklog();
}

function parseBacklogSemver(verStr) {
  const s = String(verStr || '').trim().replace(/^v/i, '');
  if (!s || s.toLowerCase() === 'backlog') return [999, 999, 999];
  const parts = s.split('.').map(n => parseInt(n, 10));
  return [
    Number.isFinite(parts[0]) ? parts[0] : 999,
    Number.isFinite(parts[1]) ? parts[1] : 0,
    Number.isFinite(parts[2]) ? parts[2] : 0
  ];
}

function compareBacklogSemver(a, b) {
  const va = parseBacklogSemver(a);
  const vb = parseBacklogSemver(b);
  for (let i = 0; i < 3; i++) {
    if (va[i] !== vb[i]) return va[i] - vb[i];
  }
  return 0;
}

function syncBacklogVersionDropdown(items) {
  const verSelect = document.getElementById('backlogVersionFilter');
  if (!verSelect || !Array.isArray(items)) return;
  const existing = new Set(Array.from(verSelect.options).map(o => o.value));
  items.forEach(item => {
    const v = String(item.target_version || '').trim();
    if (v && !existing.has(v)) {
      const opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      verSelect.appendChild(opt);
      existing.add(v);
    }
  });
}

function renderBacklogFromState() {
  const searchEl = document.getElementById('backlogSearchInput');
  const sortEl = document.getElementById('backlogSortFilter');
  const q = searchEl ? searchEl.value.trim().toLowerCase() : '';
  const sortMode = sortEl ? sortEl.value : 'chronological_asc';

  let filtered = Array.isArray(globalBacklogItems) ? [...globalBacklogItems] : [];
  if (selectedBacklogStatuses.size > 0) {
    filtered = filtered.filter(item => selectedBacklogStatuses.has(String(item.status || '')));
  }
  if (selectedBacklogPriorities.size > 0) {
    filtered = filtered.filter(item => selectedBacklogPriorities.has(String(item.priority || '').toUpperCase()));
  }
  if (q) {
    filtered = filtered.filter(item => {
      const t = String(item.title || '').toLowerCase();
      const d = String(item.description || '').toLowerCase();
      const c = String(item.category || '').toLowerCase();
      const v = String(item.target_version || '').toLowerCase();
      const p = String(item.priority || '').toLowerCase();
      return t.includes(q) || d.includes(q) || c.includes(q) || v.includes(q) || p.includes(q);
    });
  }

  const prioRank = { 'P1': 1, 'P2': 2, 'P3': 3 };
  filtered.sort((a, b) => {
    const pa = prioRank[a.priority] || 4;
    const pb = prioRank[b.priority] || 4;
    if (sortMode === 'chronological_asc') {
      const vc = compareBacklogSemver(a.target_version, b.target_version);
      if (vc !== 0) return vc;
      if (pa !== pb) return pa - pb;
      return (a.id || 0) - (b.id || 0);
    } else if (sortMode === 'version_desc') {
      const vc = compareBacklogSemver(b.target_version, a.target_version);
      if (vc !== 0) return vc;
      if (pa !== pb) return pa - pb;
      return (b.id || 0) - (a.id || 0);
    } else {
      if (pa !== pb) return pa - pb;
      const vc = compareBacklogSemver(a.target_version, b.target_version);
      if (vc !== 0) return vc;
      return (a.id || 0) - (b.id || 0);
    }
  });

  renderBacklogList(filtered);
}

async function fetchBacklog() {
  const catSelect = document.getElementById('backlogCategoryFilter');
  const verSelect = document.getElementById('backlogVersionFilter');
  const cat = catSelect ? catSelect.value : 'ALL';
  const ver = verSelect ? verSelect.value : 'ALL';

  const url = `/api/backlog?status=${encodeURIComponent(activeBacklogStatusFilter)}&priority=${encodeURIComponent(activeBacklogPriorityFilter)}&category=${encodeURIComponent(cat)}&target_version=${encodeURIComponent(ver)}`;
  try {
    const res = await fetch(url);
    const data = await res.json();
    const items = data.items || [];
    const stats = data.stats || {};
    globalBacklogItems = items;
    syncBacklogVersionDropdown(items);

    const totalEl = document.getElementById('backlogStatTotal');
    if (totalEl) totalEl.innerText = stats.total || 0;
    const unappEl = document.getElementById('backlogStatUnapproved');
    if (unappEl) unappEl.innerText = stats.unapproved || 0;
    const inProgEl = document.getElementById('backlogStatInProgress');
    if (inProgEl) inProgEl.innerText = stats.in_progress || 0;
    const planEl = document.getElementById('backlogStatPlanned');
    if (planEl) planEl.innerText = stats.planned || 0;
    const ideaEl = document.getElementById('backlogStatIdea');
    if (ideaEl) ideaEl.innerText = stats.idea || 0;
    const compEl = document.getElementById('backlogStatCompleted');
    if (compEl) compEl.innerText = stats.completed || 0;

    renderBacklogFromState();
  } catch (e) {
    console.error('Error fetching backlog:', e);
  }
}

function renderBacklogList(items) {
  const container = document.getElementById('backlogListContainer');
  if (!container) return;
  if (items.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; background: rgba(0,0,0,0.2); border-radius: 8px;">No backlog features found matching current filter. Click "All" to reset filters or "+ Add New Feature" above to create one.</div>`;
    return;
  }

  const statusColors = {
    'Unapproved': { bg: 'rgba(244, 63, 94, 0.16)', text: '#fb7185', border: 'rgba(244, 63, 94, 0.4)' },
    'Idea': { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' },
    'Planned': { bg: 'rgba(168, 85, 247, 0.15)', text: '#c084fc', border: 'rgba(168, 85, 247, 0.3)' },
    'In Progress': { bg: 'rgba(0, 242, 254, 0.15)', text: 'var(--accent-cyan)', border: 'rgba(0, 242, 254, 0.3)' },
    'Completed': { bg: 'rgba(16, 185, 129, 0.15)', text: 'var(--accent-green)', border: 'rgba(16, 185, 129, 0.3)' },
    'Deferred': { bg: 'rgba(148, 163, 184, 0.15)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)' }
  };

  container.innerHTML = items.map(item => {
    const sc = statusColors[item.status] || statusColors['Idea'];
    const priorityBadge = item.priority === 'P1' ? 'badge-p1' : (item.priority === 'P2' ? 'badge-p2' : 'badge-p3');
    const isCompleted = item.status === 'Completed';
    const isUnapproved = item.status === 'Unapproved';
    const createdDate = item.created_at ? String(item.created_at).slice(0, 10) : '';

    return `
      <div class="card" style="margin-bottom: 0; padding: 16px 20px; border: 1px solid ${isUnapproved ? 'rgba(244, 63, 94, 0.4)' : 'var(--card-border)'}; background: var(--card-bg); transition: all 0.2s ease;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 280px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;">
              <span class="badge ${priorityBadge}">${escapeHtml(item.priority)}</span>
              <span class="badge" style="background: rgba(255,255,255,0.06); color: var(--text-muted); font-size: 11px;">${escapeHtml(item.category)}</span>
              <span class="badge" style="background: rgba(79, 172, 254, 0.12); color: var(--accent-blue); font-size: 11px; border: 1px solid rgba(79, 172, 254, 0.25); font-weight: 700;">📦 ${escapeHtml(item.target_version)}</span>
              <span class="badge" style="background: ${sc.bg}; color: ${sc.text}; border: 1px solid ${sc.border}; font-size: 11px; font-weight: 700;">${isCompleted ? '✓ ' : (isUnapproved ? '⏳ ' : '')}${escapeHtml(item.status)}</span>
              ${createdDate ? `<span style="font-size: 11px; color: var(--text-muted);">📅 ${escapeHtml(createdDate)}</span>` : ''}
            </div>
            <div style="font-size: 14.5px; font-weight: 600; color: #f8fafc;">${escapeHtml(item.title)}</div>
            ${item.description ? `<div style="font-size: 12.5px; color: var(--text-muted); margin-top: 4px; line-height: 1.4;">${escapeHtml(item.description)}</div>` : ''}
          </div>
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            ${isUnapproved ? `
              <button title="Approve and implement this Unapproved email/attachment proposal" class="btn btn-primary" style="font-size: 11.5px; padding: 5px 11px; background: rgba(16, 185, 129, 0.22); border: 1px solid rgba(16, 185, 129, 0.5); color: #34d399; font-weight: 700;" onclick="approveUnapprovedBacklogItem(${item.id})">
                ✅ Approve &amp; Implement
              </button>
            ` : ''}
            <select onchange="updateBacklogStatus(${item.id}, this.value)" style="background: rgba(0,0,0,0.5); border: 1px solid var(--card-border); border-radius: 6px; color: var(--text); padding: 5px 8px; font-size: 12px;">
              <option value="Unapproved" ${item.status === 'Unapproved' ? 'selected' : ''}>⏳ Unapproved</option>
              <option value="Idea" ${item.status === 'Idea' ? 'selected' : ''}>💡 Idea</option>
              <option value="Planned" ${item.status === 'Planned' ? 'selected' : ''}>📅 Planned</option>
              <option value="In Progress" ${item.status === 'In Progress' ? 'selected' : ''}>⚡ In Progress</option>
              <option value="Completed" ${item.status === 'Completed' ? 'selected' : ''}>✅ Completed</option>
              <option value="Deferred" ${item.status === 'Deferred' ? 'selected' : ''}>⏸️ Deferred</option>
            </select>
            <button class="btn-delete" title="Delete Feature" onclick="deleteBacklogItem(${item.id})">✕</button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

async function approveUnapprovedBacklogItem(backlogId) {
  try {
    const res = await fetch('/api/emails/proposals/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backlog_id: backlogId })
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      fetchBacklog();
      if (typeof fetchEmailProposals === 'function') fetchEmailProposals();
      if (typeof fetchTasks === 'function') fetchTasks();
      if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.loadManifest === 'function') {
        FleetNavigator.loadManifest();
      }
    } else {
      alert(data.error || 'Could not approve backlog item.');
    }
  } catch (e) {
    console.error('Error approving unapproved backlog item:', e);
  }
}

async function submitNewBacklogItem() {
  const titleEl = document.getElementById('newBacklogTitle');
  const title = titleEl.value.trim();
  if (!title) {
    titleEl.focus();
    return;
  }
  const cat = document.getElementById('newBacklogCategory').value;
  const prio = document.getElementById('newBacklogPriority').value;
  const ver = document.getElementById('newBacklogVersion').value;
  const desc = document.getElementById('newBacklogDesc').value.trim();

  try {
    await fetch('/api/backlog', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        title: title,
        description: desc,
        category: cat,
        priority: prio,
        status: 'Planned',
        target_version: ver
      })
    });
    titleEl.value = '';
    document.getElementById('newBacklogDesc').value = '';
    toggleAddBacklogCard();
    fetchBacklog();
  } catch (e) {
    console.error('Error adding backlog item:', e);
  }
}

async function updateBacklogStatus(id, newStatus) {
  try {
    await fetch('/api/backlog/update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ id, status: newStatus })
    });
    fetchBacklog();
  } catch (e) {
    console.error('Error updating backlog status:', e);
  }
}

async function deleteBacklogItem(id) {
  if (!confirm('Are you sure you want to delete this feature from the backlog?')) return;
  try {
    await fetch('/api/backlog/delete', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ id })
    });
    fetchBacklog();
  } catch (e) {
    console.error('Error deleting backlog item:', e);
  }
}

window.toggleAddBacklogCard = toggleAddBacklogCard;
window.filterBacklogByStatus = filterBacklogByStatus;
window.filterBacklogByPriority = filterBacklogByPriority;
window.fetchBacklog = fetchBacklog;
window.renderBacklogFromState = renderBacklogFromState;
window.renderBacklogList = renderBacklogList;
window.submitNewBacklogItem = submitNewBacklogItem;
window.updateBacklogStatus = updateBacklogStatus;
window.deleteBacklogItem = deleteBacklogItem;
window.approveUnapprovedBacklogItem = approveUnapprovedBacklogItem;
