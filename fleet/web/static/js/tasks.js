// --- Daily, Monthly & Yearly Tasks Engine (100% Local-Only Storage) ---
    window._cachedTasksList = [];
    window._activeTaskFilter = 'ALL';
    window._maskSensitiveTaskData = localStorage.getItem('afcc_mask_sensitive_tasks') !== 'false';

    function maskSensitiveTaskText(text) {
      if (!text || !window._maskSensitiveTaskData) return text;
      let masked = String(text);
      // Mask alphanumeric account/loan/IFSC identifiers (e.g. ABCD0123456, LOAN00012345, 1234-5678-901)
      masked = masked.replace(/\b([A-Z]{4,6}[0-9]{5,12})\b/g, (m) => m.slice(0, 2) + '••••••' + m.slice(-3));
      masked = masked.replace(/\b(\d{4}-\d{4}-\d{3,4})\b/g, (m) => '••••-••••-' + m.slice(-3));
      // Mask long numeric account / consumer numbers (8 to 16 digits)
      masked = masked.replace(/\b(\d{8,16})\b/g, (m) => '••••••••' + m.slice(-4));
      // Mask 4-digit account suffixes after "ending in" or "A/c"
      masked = masked.replace(/(ending in\s+|A\/c\s+)(\d{4})\b/gi, '$1••' + '$2'.slice(-2));
      return masked;
    }

    function formatTaskDescriptionHtml(rawDesc) {
      const masked = maskSensitiveTaskText(rawDesc || 'No description provided');
      const escaped = escapeHtml(masked);
      // Safely convert https:// URLs into clickable links and newlines into <br>
      const withLinks = escaped.replace(
        /(https?:\/\/[^\s<]+)/g,
        '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: var(--accent-cyan); text-decoration: underline; word-break: break-all;">$1</a>'
      );
      return withLinks.replace(/\n/g, '<br>');
    }

    function updateTaskMaskButtonUI() {
      const btn = document.getElementById('btnToggleTaskMask');
      if (!btn) return;
      if (window._maskSensitiveTaskData) {
        btn.innerHTML = '🙈 Mask IDs: On';
        btn.style.background = 'rgba(16, 185, 129, 0.16)';
        btn.style.borderColor = 'rgba(16, 185, 129, 0.45)';
        btn.style.color = '#34d399';
      } else {
        btn.innerHTML = '👁️ Mask IDs: Off';
        btn.style.background = 'transparent';
        btn.style.borderColor = 'rgba(56, 189, 248, 0.35)';
        btn.style.color = 'var(--accent-cyan)';
      }
    }

    function toggleTaskSensitiveMask() {
      window._maskSensitiveTaskData = !window._maskSensitiveTaskData;
      localStorage.setItem('afcc_mask_sensitive_tasks', window._maskSensitiveTaskData ? 'true' : 'false');
      updateTaskMaskButtonUI();
      renderTasksList();
    }

    function filterTasksBySource(filterMode) {
      window._activeTaskFilter = filterMode || 'ALL';
      const bar = document.getElementById('taskFilterBar');
      if (bar) {
        bar.querySelectorAll('.filter-btn').forEach(btn => {
          btn.classList.toggle('active', btn.getAttribute('data-task-filter') === window._activeTaskFilter);
        });
      }
      renderTasksList();
    }

    function updateTaskFilterBarCounts(tasks) {
      const bar = document.getElementById('taskFilterBar');
      if (!bar) return;
      const allCount = tasks.length;
      const monthlyCount = tasks.filter(t => String(t.source || '').toLowerCase() === 'monthly').length;
      const yearlyCount = tasks.filter(t => String(t.source || '').toLowerCase() === 'yearly').length;
      const pendingCount = tasks.filter(t => t.status !== 'completed').length;
      const completedCount = tasks.filter(t => t.status === 'completed').length;

      const labels = {
        'ALL': `All (${allCount})`,
        'Monthly': `📅 Monthly (${monthlyCount})`,
        'Yearly': `🗓️ Yearly (${yearlyCount})`,
        'PENDING': `⏳ Pending (${pendingCount})`,
        'COMPLETED': `✓ Completed (${completedCount})`
      };
      bar.querySelectorAll('.filter-btn').forEach(btn => {
        const key = btn.getAttribute('data-task-filter');
        if (key && labels[key]) {
          btn.textContent = labels[key];
        }
      });
    }

    function renderTasksList() {
      const list = document.getElementById('taskList');
      if (!list) return;
      updateTaskMaskButtonUI();
      const allTasks = Array.isArray(window._cachedTasksList) ? window._cachedTasksList : [];
      updateTaskFilterBarCounts(allTasks);

      const filter = window._activeTaskFilter || 'ALL';
      const tasks = allTasks.filter(t => {
        if (filter === 'ALL') return true;
        if (filter === 'PENDING') return t.status !== 'completed';
        if (filter === 'COMPLETED') return t.status === 'completed';
        return String(t.source || '').toLowerCase() === String(filter).toLowerCase();
      });

      const counterEl = document.getElementById('taskCounter');
      if (counterEl) {
        counterEl.innerText = filter === 'ALL' ? `${allTasks.length} Total` : `${tasks.length} / ${allTasks.length} Shown`;
      }

      if (tasks.length === 0) {
        list.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">No tasks in this view. Type above to add one!</div>`;
        return;
      }

      list.innerHTML = tasks.map(t => {
        const isDone = t.status === 'completed';
        const badgeClass = t.priority === 'P1' ? 'badge-p1' : (t.priority === 'P2' ? 'badge-p2' : 'badge-p3');
        const sourceText = t.source || t.assigned_agent || 'Manual';
        const srcLower = String(sourceText).toLowerCase();
        const sourceIcon = srcLower === 'monthly' ? '📅' : (srcLower === 'yearly' ? '🗓️' : '📍');
        const sourceBadgeStyle = srcLower === 'monthly'
          ? 'background: rgba(56, 189, 248, 0.14); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35);'
          : (srcLower === 'yearly'
            ? 'background: rgba(168, 85, 247, 0.14); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);'
            : 'background: rgba(0, 242, 254, 0.1); color: var(--accent-cyan); border: 1px solid rgba(0, 242, 254, 0.25);');
        const maskedTitle = maskSensitiveTaskText(t.title || '');
        return `
          <div class="task-item ${isDone ? 'completed' : ''}">
            <div class="task-left" style="align-items: flex-start;">
              <input type="checkbox" class="task-checkbox" style="margin-top: 3px;" ${isDone ? 'checked' : ''} onchange="toggleTask(${t.id})">
              <span class="badge ${badgeClass}" style="margin-top: 1px;">${escapeHtml(t.priority || 'P2')}</span>
              <span class="badge-source" style="font-size: 10px; padding: 2px 7px; border-radius: 4px; ${sourceBadgeStyle} font-weight: 600; white-space: nowrap; margin-top: 1px;">${sourceIcon} ${escapeHtml(sourceText)}</span>
              <div style="display: flex; flex-direction: column; gap: 3px;">
                <span class="task-title" style="font-size: 13.5px; font-weight: 600;">${escapeHtml(maskedTitle)}</span>
                <span class="task-desc" style="font-size: 12px; color: var(--text-muted); line-height: 1.45;">${formatTaskDescriptionHtml(t.description)}</span>
              </div>
            </div>
            <button class="btn-delete" title="Delete Task" onclick="deleteTask(${t.id})">✕</button>
          </div>
        `;
      }).join('');
    }

    async function fetchTasks() {
      try {
        const res = await fetch('/api/tasks');
        const rawTasks = await res.json();
        window._cachedTasksList = (Array.isArray(rawTasks) ? rawTasks : []).filter(t => {
          const s = (t.source || '').toLowerCase();
          const title = (t.title || '').toLowerCase();
          return !s.includes('test') && !s.includes('e2e') && !title.includes('test task') && !title.includes('e2e deep');
        });
        renderTasksList();
      } catch (e) {
        console.error(e);
      }
    }

    async function addTask() {
      const input = document.getElementById('taskTitle');
      const descInput = document.getElementById('taskDesc');
      const sourceSelect = document.getElementById('taskSource');
      const title = input.value.trim();
      const description = descInput ? descInput.value.trim() : '';
      const priority = document.getElementById('taskPriority').value;
      const source = sourceSelect ? sourceSelect.value : 'Dashboard';
      if (!title || !description) {
        alert('Both a task title and description are required.');
        return;
      }

      const resp = await fetch('/api/tasks', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ title, description, priority, source })
      });
      if (resp.ok) {
        input.value = '';
        if (descInput) descInput.value = '';
        fetchTasks();
        fetchBriefing();
        fetchLogs();
      } else {
        const err = await resp.json();
        alert(err.error || 'Failed to add task');
      }
    }

    async function toggleTask(id) {
      await fetch('/api/tasks/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id })
      });
      fetchTasks();
      fetchBriefing();
      fetchLogs();
    }

    async function deleteTask(id) {
      await fetch('/api/tasks/delete', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ id })
      });
      fetchTasks();
      fetchBriefing();
      fetchLogs();
    }


window.fetchTasks = fetchTasks;
window.addTask = addTask;
window.toggleTask = toggleTask;
window.deleteTask = deleteTask;
window.filterTasksBySource = filterTasksBySource;
window.toggleTaskSensitiveMask = toggleTaskSensitiveMask;
