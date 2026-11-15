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

function filterBacklogToTriDevice() {
  const verSelect = document.getElementById('backlogVersionFilter');
  if (verSelect) {
    let has218 = Array.from(verSelect.options).some(o => o.value === 'v2.18.0');
    if (!has218) {
      const opt = document.createElement('option');
      opt.value = 'v2.18.0';
      opt.textContent = 'v2.18.0 (Tri-Device)';
      verSelect.appendChild(opt);
    }
    verSelect.value = 'v2.18.0';
  }
  selectedBacklogStatuses.clear();
  selectedBacklogPriorities.clear();
  activeBacklogStatusFilter = 'ALL';
  activeBacklogPriorityFilter = 'ALL';
  syncBacklogStatusFilterButtons();
  syncBacklogPriorityFilterButtons();
  fetchBacklog();
}

async function syncTriDeviceGitHubProjectFromUI() {
  try {
    const res = await fetch('/api/github/projects/tri-device/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      const m = (data.project_status && data.project_status.metrics) || {};
      alert(`Tri-Device GitHub Project synced!\nProgress: ${m.completed || 6}/${m.total_deliverables || 12} deliverables (${m.progress_pct || 50}%).`);
    }
  } catch (e) {
    console.error('Error syncing Tri-Device GitHub project:', e);
  }
}

let _triDeviceLivePollTimer = null;

async function refreshTriDeviceHealthHub() {
  try {
    const [healthRes, gwRes] = await Promise.all([
      fetch('/api/mobile/health/status'),
      fetch('/api/mobile/gateway/status')
    ]);
    if (healthRes.ok) {
      const hData = await healthRes.json();
      const isReal = Boolean(hData.is_real_device_sync);
      const readiness = hData.readiness || {};
      const metrics = hData.metrics || {};
      const badgeEl = document.getElementById('triDeviceReadinessBadge');
      const recEl = document.getElementById('triDeviceRecommendationText');
      const hrvEl = document.getElementById('triDeviceHrvRhrVal');
      const sleepEl = document.getElementById('triDeviceSleepSpo2Val');
      const planEl = document.getElementById('triDeviceWorkoutPlanVal');

      if (planEl && hData.today_schedule) {
        planEl.textContent = hData.today_schedule;
      }

      if (isReal && readiness.readiness_score) {
        if (badgeEl) {
          badgeEl.style.background = 'rgba(16, 185, 129, 0.2)';
          badgeEl.style.color = '#34d399';
          badgeEl.style.borderColor = 'rgba(16, 185, 129, 0.45)';
          badgeEl.textContent = `✅ Connected • Readiness: ${readiness.readiness_score}/100 (${readiness.readiness_tier || 'PEAK_STRENGTH'})`;
        }
        if (recEl && readiness.recommendation) {
          recEl.textContent = `${readiness.recommendation} (Synced from ${hData.device_source || 'Apple Watch'})`;
        }
        if (hrvEl) {
          hrvEl.textContent = `${metrics.hrv_sdnn_ms != null ? metrics.hrv_sdnn_ms + ' ms' : '-- ms'} • ${metrics.resting_hr_bpm != null ? metrics.resting_hr_bpm + ' bpm' : '-- bpm'}`;
        }
        if (sleepEl) {
          sleepEl.textContent = `${metrics.sleep_hours != null ? metrics.sleep_hours + ' hrs' : '-- hrs'} • ${metrics.spo2_pct != null ? metrics.spo2_pct + '% SpO2' : '--% SpO2'}`;
        }
      } else {
        if (badgeEl) {
          badgeEl.style.background = 'rgba(245, 158, 11, 0.2)';
          badgeEl.style.color = '#fbbf24';
          badgeEl.style.borderColor = 'rgba(245, 158, 11, 0.45)';
          badgeEl.textContent = '⏳ Awaiting Real Watch / iPhone Sync';
        }
        if (hrvEl) hrvEl.textContent = '-- ms • -- bpm (Not Synced)';
        if (sleepEl) sleepEl.textContent = '-- hrs • --% SpO2 (Not Synced)';
      }
    }
    if (gwRes.ok) {
      const gData = await gwRes.json();
      const gwEl = document.getElementById('triDeviceGatewayUrlVal');
      const lanIp = (gData.network && gData.network.lan_ips && gData.network.lan_ips[0]) || '127.0.0.1';
      if (gwEl) {
        gwEl.textContent = `http://${lanIp}:7890/mobile-pair`;
      }
    }
    loadTriDeviceHardwareInventoryAndConstraints(false);
  } catch (e) {
    // non-fatal
  }
}

function toggleAddHardwareDeviceForm() {
  const form = document.getElementById('triDeviceAddHardwareForm');
  if (!form) return;
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
}

async function loadTriDeviceHardwareInventoryAndConstraints(forceRefresh) {
  const hwGrid = document.getElementById('triDeviceHardwareInventoryGrid');
  const ecGrid = document.getElementById('triDeviceConstraintsMatrixGrid');
  const countBadge = document.getElementById('triDeviceHwCountBadge');
  if (!hwGrid && !ecGrid) return;
  try {
    const res = await fetch('/api/mobile/hardware/inventory');
    if (!res.ok) return;
    const data = await res.json();
    const inv = data.inventory || {};
    const devices = inv.devices || [];
    const constraints = data.environmental_constraints || [];

    if (countBadge) {
      countBadge.textContent = `${devices.length} Local Devices`;
    }

    if (hwGrid) {
      if (!devices.length) {
        hwGrid.innerHTML = `<div style="padding: 12px; color: var(--text-muted); font-size: 12px;">No local hardware devices registered yet.</div>`;
      } else {
        hwGrid.innerHTML = devices.map(dev => {
          const st = String(dev.status || 'Configured');
          const isOnline = /online|active|ready|paired/i.test(st);
          const badgeCol = isOnline ? '#34d399' : '#38bdf8';
          const badgeBg = isOnline ? 'rgba(16, 185, 129, 0.16)' : 'rgba(56, 189, 248, 0.16)';
          return `
            <div style="background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 12px 14px;">
              <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 6px; margin-bottom: 5px;">
                <strong style="font-size: 12.5px; color: #fff;">${escapeHtml(dev.name || dev.id || 'Device')}</strong>
                <span class="badge" style="background: ${badgeBg}; color: ${badgeCol}; font-size: 9.5px; white-space: nowrap;">${escapeHtml(st)}</span>
              </div>
              <div style="font-size: 11px; color: var(--accent-cyan); margin-bottom: 4px;">
                ${escapeHtml(dev.category || 'Hardware')} • ${escapeHtml(dev.os_or_firmware || 'Standard')}
              </div>
              <div style="font-size: 11px; color: #cbd5e1; margin-bottom: 4px;">
                <strong>Transport:</strong> ${escapeHtml(dev.transport || 'Local')}
              </div>
              <div style="font-size: 11px; color: var(--text-muted); line-height: 1.4;">
                ${escapeHtml(dev.role || dev.notes || '')}
              </div>
            </div>
          `;
        }).join('');
      }
    }

    if (ecGrid && constraints.length) {
      ecGrid.innerHTML = constraints.map(ec => `
        <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.24); border-left: 3px solid #38bdf8; border-radius: 8px; padding: 11px 13px;">
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px; margin-bottom: 4px;">
            <strong style="font-size: 12px; color: #38bdf8;">[${escapeHtml(ec.id)}] ${escapeHtml(ec.title)}</strong>
            <span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; font-size: 9.5px;">${escapeHtml(ec.layer || 'Tri-Device')}</span>
          </div>
          <div style="font-size: 11px; color: #fbbf24; margin-bottom: 5px; line-height: 1.4;">
            <strong>Constraint:</strong> ${escapeHtml(ec.constraint)}
          </div>
          <div style="font-size: 11px; color: #cbd5e1; line-height: 1.4;">
            <strong style="color: #34d399;">Practical Architecture:</strong> ${escapeHtml(ec.practical_solution)}
          </div>
        </div>
      `).join('');
    }
  } catch (e) {
    // non-fatal
  }
}

async function submitNewLocalHardwareDevice() {
  const nameEl = document.getElementById('hwFormName');
  const catEl = document.getElementById('hwFormCategory');
  const osEl = document.getElementById('hwFormOsVersion');
  const trEl = document.getElementById('hwFormTransport');
  const notesEl = document.getElementById('hwFormNotes');
  const name = (nameEl && nameEl.value || '').trim();
  if (!name) {
    alert('Please enter a device name or model.');
    return;
  }
  try {
    const res = await fetch('/api/mobile/hardware/inventory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        category: catEl ? catEl.value : 'Peripheral',
        os_or_firmware: osEl ? osEl.value.trim() : '',
        transport: trEl ? trEl.value.trim() : 'Local Bridge',
        role: notesEl ? notesEl.value.trim() : '',
        notes: notesEl ? notesEl.value.trim() : '',
        status: 'Configured (Local Vault)'
      })
    });
    if (res.ok) {
      if (nameEl) nameEl.value = '';
      if (osEl) osEl.value = '';
      if (trEl) trEl.value = '';
      if (notesEl) notesEl.value = '';
      toggleAddHardwareDeviceForm();
      await loadTriDeviceHardwareInventoryAndConstraints(true);
    }
  } catch (e) {
    alert('Error saving device to local hardware vault: ' + e.message);
  }
}

function closeTriDeviceSyncConsole() {
  const panel = document.getElementById('triDeviceSyncStepsPanel');
  if (panel) panel.style.display = 'none';
  if (_triDeviceLivePollTimer) {
    clearInterval(_triDeviceLivePollTimer);
    _triDeviceLivePollTimer = null;
  }
}

function _renderStepRow(stepObj) {
  const icons = {
    'running': '🔄',
    'pass': '✅',
    'warn': '⚠️',
    'info': 'ℹ️',
    'waiting': '⏳',
    'action_required': '📲'
  };
  const colors = {
    'running': '#38bdf8',
    'pass': '#34d399',
    'warn': '#fbbf24',
    'info': '#94a3b8',
    'waiting': '#fb7185',
    'action_required': '#00f2fe'
  };
  const ic = icons[stepObj.status] || '•';
  const col = colors[stepObj.status] || '#cbd5e1';
  return `
    <div style="background: rgba(15, 23, 42, 0.85); border-left: 3px solid ${col}; border-radius: 6px; padding: 8px 12px;">
      <div style="font-weight: 700; color: ${col};">${ic} Step ${stepObj.step}/5 — ${escapeHtml(stepObj.title)}</div>
      <div style="color: #cbd5e1; margin-top: 3px; line-height: 1.45;">${escapeHtml(stepObj.detail)}</div>
    </div>
  `;
}

async function triggerAppleWatchDemoSync() {
  const panel = document.getElementById('triDeviceSyncStepsPanel');
  const listEl = document.getElementById('triDeviceSyncStepsList');
  const footerEl = document.getElementById('triDeviceLiveBridgeFooter');
  const btn = document.getElementById('btnSyncAppleWatchNow');
  if (panel) panel.style.display = 'block';
  if (footerEl) footerEl.style.display = 'none';
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🔍 Checking Apple Watch Connection...';
  }

  const pendingSteps = [
    { step: 1, title: 'Checking iPhone Companion Relay Bridge (Apple Watch → iPhone → Windows Hub)...', status: 'running', detail: 'Apple Watch pairs exclusively with your iPhone (never directly to Windows). Checking Windows Bluetooth Registry for your paired iPhone Companion Bridge...' },
    { step: 2, title: 'Verifying Laptop Wi-Fi LAN & Tailscale Listener (Port 7890)...', status: 'running', detail: 'Checking 0.0.0.0:7890 binding and active 192.168.1.x Wi-Fi neighbors...' },
    { step: 3, title: 'Scanning Local Apple Health Inbox (fleet/data/user/apple_health_inbox/)...', status: 'running', detail: 'Looking for Apple Health export.xml / .json files...' },
    { step: 4, title: 'Verifying Real Incoming Apple Watch / iPhone Telemetry...', status: 'running', detail: 'Checking apple_health_sync_vault.json for authenticated real-device packets...' },
    { step: 5, title: 'Computing Final Connection Verdict...', status: 'running', detail: 'Waiting for hardware & network probe results...' }
  ];
  if (listEl) {
    listEl.innerHTML = _renderStepRow(pendingSteps[0]);
  }

  try {
    const res = await fetch('/api/mobile/watch/verify_and_sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    const steps = data.steps || [];

    // Reveal each step sequentially so the user sees the exact hardware & network checks
    const revealed = [];
    for (let i = 0; i < steps.length; i++) {
      revealed.push(steps[i]);
      if (listEl) {
        listEl.innerHTML = revealed.map(_renderStepRow).join('');
      }
      await new Promise(r => setTimeout(r, 280));
    }

    await refreshTriDeviceHealthHub();
    if (typeof fetchHealthDashboard === 'function') fetchHealthDashboard();

    if (footerEl) {
      footerEl.style.display = 'block';
      const pairUrl = data.mobile_pair_http_url || 'http://192.168.1.35:7890/mobile-pair';
      const fwBlocked = Boolean(data.firewall && data.firewall.blocked_on_public_wifi);
      const fwBannerHtml = fwBlocked ? `
        <div style="margin-bottom: 10px; padding: 10px 12px; border-radius: 8px; background: rgba(244, 63, 94, 0.14); border: 1px solid rgba(244, 63, 94, 0.45);">
          <div style="font-weight: 700; color: #fb7185; margin-bottom: 4px;">
            🛡️ Why your iPhone got <code>ERR_CONNECTION_TIMED_OUT</code>: Windows Defender Firewall Public Profile Block Detected!
          </div>
          <div style="font-size: 11.5px; color: #e2e8f0; line-height: 1.45; margin-bottom: 8px;">
            Your laptop's Wi-Fi is currently set to <strong>Public Network Profile</strong>, and Windows Defender Firewall has an explicit <code>Action=Block</code> rule on <code>C:\\Python314\\python.exe</code> for Public Wi-Fi (while allowing Private Wi-Fi). Fix it in 3 seconds using either button below:
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button type="button" class="btn btn-primary" onclick="fixWindowsFirewallForIphoneBridge()" style="font-size: 11.5px; padding: 6px 12px;">
              🛡️ Option 1: 1-Click Unblock iPhone in Windows Firewall (Click 'Yes' on Windows Prompt)
            </button>
            <button type="button" class="btn" onclick="openWindowsWifiSettings('wifi')" style="font-size: 11.5px; padding: 6px 12px; border-color: rgba(56, 189, 248, 0.45); color: #38bdf8;">
              📶 Option 2: Open Windows Wi-Fi Settings (Switch Network Profile: Public → Private)
            </button>
          </div>
        </div>
      ` : '';
      if (data.real_sync_verified) {
        footerEl.innerHTML = fwBannerHtml + `<span style="color: #34d399; font-weight: 700;">✅ Real Apple Watch / iPhone sync verified and encrypted at rest!</span>`;
        if (_triDeviceLivePollTimer) {
          clearInterval(_triDeviceLivePollTimer);
          _triDeviceLivePollTimer = null;
        }
      } else {
        footerEl.innerHTML = fwBannerHtml + `
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
            <div>
              <strong style="color: #fbbf24;">📡 Live Listener Active (Polling every 2s for your iPhone):</strong><br>
              <span>1. Open <a href="${pairUrl}" target="_blank" style="color: #00f2fe; font-weight: 700;">${pairUrl}</a> in Safari on your iPhone (same Wi-Fi) and tap <strong>Push Live to Laptop AFCC Hub</strong>.</span><br>
              <span>2. Or click <strong>📂 Upload Health Export</strong> above to import an Apple Health <code>export.xml</code> / <code>.json</code> file.</span>
            </div>
          </div>
        `;
        if (_triDeviceLivePollTimer) clearInterval(_triDeviceLivePollTimer);
        _triDeviceLivePollTimer = setInterval(async () => {
          try {
            const stRes = await fetch('/api/mobile/health/status');
            if (stRes.ok) {
              const stData = await stRes.json();
              if (stData.is_real_device_sync) {
                clearInterval(_triDeviceLivePollTimer);
                _triDeviceLivePollTimer = null;
                await triggerAppleWatchDemoSync();
              }
            }
          } catch (e) {}
        }, 2000);
      }
    }
  } catch (e) {
    if (listEl) {
      listEl.innerHTML = `<div style="color: #fb7185;">❌ Error verifying Apple Watch connection: ${escapeHtml(e.message || String(e))}</div>`;
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '⌚ Sync Apple Watch Now';
    }
  }
}

async function uploadAppleHealthExportFile(inputEl) {
  if (!inputEl || !inputEl.files || !inputEl.files[0]) return;
  const file = inputEl.files[0];
  try {
    const text = await file.text();
    const res = await fetch('/api/mobile/health/import_export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        filename: file.name,
        content: text.slice(0, 2000000)
      })
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      await triggerAppleWatchDemoSync();
    } else {
      alert(data.message || 'Could not parse Apple Health export file.');
    }
  } catch (e) {
    alert('Error reading Apple Health file: ' + e.message);
  } finally {
    inputEl.value = '';
  }
}

async function copyTriDeviceShortcutRecipe() {
  try {
    const [tplRes, tokRes, gwRes] = await Promise.all([
      fetch('/api/mobile/shortcuts/template'),
      fetch('/api/mobile/gateway/token', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
      fetch('/api/mobile/gateway/status')
    ]);
    const tpl = await tplRes.json();
    const tok = await tokRes.json();
    const gw = await gwRes.json();
    const bundle = {
      gateway_base_url: (gw.network && gw.network.recommended_mobile_base_url) || 'https://127.0.0.1:7890',
      auth_header: { 'X-AFCC-Mobile-Token': tok.bearer_token || '' },
      recipes: tpl.recipes || []
    };
    const jsonText = JSON.stringify(bundle, null, 2);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(jsonText);
    }
    alert('Copied iOS Shortcuts & Apple Watch Action Button JSON recipe (with your Mobile Bearer Token) to clipboard!');
  } catch (e) {
    console.error('Error copying iOS shortcut recipe:', e);
  }
}

async function fixWindowsFirewallForIphoneBridge() {
  const btn = document.getElementById('btnFixWindowsFirewall');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🛡️ Requesting Windows Firewall Permission...';
  }
  try {
    const res = await fetch('/api/mobile/gateway/fix_firewall', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}'
    });
    const data = await res.json();
    alert(data.message || "Click 'Yes' on the Windows Administrator (UAC) prompt on your laptop taskbar to unblock Port 7890 for your iPhone over Wi-Fi!");
    setTimeout(triggerAppleWatchDemoSync, 2500);
  } catch (e) {
    alert('Error requesting Windows Firewall update: ' + e.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🛡️ Unblock iPhone Wi-Fi (Firewall)';
    }
  }
}

async function openWindowsWifiSettings(target) {
  try {
    await fetch('/api/mobile/gateway/open_wifi_settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target: target || 'wifi' })
    });
  } catch (e) {}
}

window.filterBacklogToTriDevice = filterBacklogToTriDevice;
window.syncTriDeviceGitHubProjectFromUI = syncTriDeviceGitHubProjectFromUI;
window.refreshTriDeviceHealthHub = refreshTriDeviceHealthHub;
window.triggerAppleWatchDemoSync = triggerAppleWatchDemoSync;
window.closeTriDeviceSyncConsole = closeTriDeviceSyncConsole;
window.uploadAppleHealthExportFile = uploadAppleHealthExportFile;
window.copyTriDeviceShortcutRecipe = copyTriDeviceShortcutRecipe;
window.toggleAddHardwareDeviceForm = toggleAddHardwareDeviceForm;
window.loadTriDeviceHardwareInventoryAndConstraints = loadTriDeviceHardwareInventoryAndConstraints;
window.submitNewLocalHardwareDevice = submitNewLocalHardwareDevice;
window.fixWindowsFirewallForIphoneBridge = fixWindowsFirewallForIphoneBridge;
window.openWindowsWifiSettings = openWindowsWifiSettings;
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(refreshTriDeviceHealthHub, 600);
});
