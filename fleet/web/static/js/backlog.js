// --- Feature Backlog Management ---
let activeBacklogStatusFilter = 'ALL';
let globalBacklogItems = [];

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

    function filterBacklogByStatus(status) {
      activeBacklogStatusFilter = status;
      ['All', 'Idea', 'Planned', 'Progress', 'Completed'].forEach(s => {
        const b = document.getElementById(`backlogFilterStatus${s}`);
        if (b) b.classList.remove('active');
      });
      const activeMap = {
        'ALL': 'backlogFilterStatusAll',
        'Idea': 'backlogFilterStatusIdea',
        'Planned': 'backlogFilterStatusPlanned',
        'In Progress': 'backlogFilterStatusProgress',
        'Completed': 'backlogFilterStatusCompleted'
      };
      const targetBtn = document.getElementById(activeMap[status]);
      if (targetBtn) targetBtn.classList.add('active');
      fetchBacklog();
    }

    async function fetchBacklog() {
      const catSelect = document.getElementById('backlogCategoryFilter');
      const verSelect = document.getElementById('backlogVersionFilter');
      const cat = catSelect ? catSelect.value : 'ALL';
      const ver = verSelect ? verSelect.value : 'ALL';

      let url = `/api/backlog?status=${encodeURIComponent(activeBacklogStatusFilter)}&category=${encodeURIComponent(cat)}&target_version=${encodeURIComponent(ver)}`;
      try {
        const res = await fetch(url);
        const data = await res.json();
        const items = data.items || [];
        const stats = data.stats || {};
        globalBacklogItems = items;

        const totalEl = document.getElementById('backlogStatTotal');
        if (totalEl) totalEl.innerText = stats.total || 0;
        const inProgEl = document.getElementById('backlogStatInProgress');
        if (inProgEl) inProgEl.innerText = stats.in_progress || 0;
        const planEl = document.getElementById('backlogStatPlanned');
        if (planEl) planEl.innerText = stats.planned || 0;
        const ideaEl = document.getElementById('backlogStatIdea');
        if (ideaEl) ideaEl.innerText = stats.idea || 0;
        const compEl = document.getElementById('backlogStatCompleted');
        if (compEl) compEl.innerText = stats.completed || 0;

        renderBacklogList(items);
      } catch (e) {
        console.error('Error fetching backlog:', e);
      }
    }

    function renderBacklogList(items) {
      const container = document.getElementById('backlogListContainer');
      if (!container) return;
      if (items.length === 0) {
        container.innerHTML = `<div style="text-align: center; padding: 40px; color: var(--text-muted); font-size: 13px; background: rgba(0,0,0,0.2); border-radius: 8px;">No backlog features found matching current filter. Click "+ Add New Feature" above to create one.</div>`;
        return;
      }

      const statusColors = {
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

        return `
          <div class="card" style="margin-bottom: 0; padding: 16px 20px; border: 1px solid var(--card-border); background: var(--card-bg); transition: all 0.2s ease;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap;">
              <div style="flex: 1; min-width: 280px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap;">
                  <span class="badge ${priorityBadge}">${escapeHtml(item.priority)}</span>
                  <span class="badge" style="background: rgba(255,255,255,0.06); color: var(--text-muted); font-size: 11px;">${escapeHtml(item.category)}</span>
                  <span class="badge" style="background: rgba(79, 172, 254, 0.12); color: var(--accent-blue); font-size: 11px; border: 1px solid rgba(79, 172, 254, 0.25);">${escapeHtml(item.target_version)}</span>
                  <span class="badge" style="background: ${sc.bg}; color: ${sc.text}; border: 1px solid ${sc.border}; font-size: 11px; font-weight: 700;">${escapeHtml(item.status)}</span>
                </div>
                <div style="font-size: 14.5px; font-weight: 600; color: ${isCompleted ? 'var(--text-muted)' : '#fff'}; ${isCompleted ? 'text-decoration: line-through;' : ''}">${escapeHtml(item.title)}</div>
                ${item.description ? `<div style="font-size: 12.5px; color: var(--text-muted); margin-top: 4px; line-height: 1.4;">${escapeHtml(item.description)}</div>` : ''}
              </div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <select onchange="updateBacklogStatus(${item.id}, this.value)" style="background: rgba(0,0,0,0.5); border: 1px solid var(--card-border); border-radius: 6px; color: var(--text); padding: 5px 8px; font-size: 12px;">
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

    // --- PC Performance Optimizer ---

window.toggleAddBacklogCard = toggleAddBacklogCard;
window.filterBacklogByStatus = filterBacklogByStatus;
window.fetchBacklog = fetchBacklog;
window.renderBacklogList = renderBacklogList;
window.submitNewBacklogItem = submitNewBacklogItem;
window.updateBacklogStatus = updateBacklogStatus;
window.deleteBacklogItem = deleteBacklogItem;
