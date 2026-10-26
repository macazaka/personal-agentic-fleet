// --- Daily Tasks & Goals Engine ---
    async function fetchTasks() {
      try {
        const res = await fetch('/api/tasks');
        const rawTasks = await res.json();
        const tasks = (Array.isArray(rawTasks) ? rawTasks : []).filter(t => {
          const s = (t.source || '').toLowerCase();
          const title = (t.title || '').toLowerCase();
          return !s.includes('test') && !s.includes('e2e') && !title.includes('test task') && !title.includes('e2e deep');
        });
        const list = document.getElementById('taskList');
        document.getElementById('taskCounter').innerText = `${tasks.length} Total`;
        
        if (tasks.length === 0) {
          list.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">No tasks yet. Type above to add one!</div>`;
          return;
        }

        list.innerHTML = tasks.map(t => {
          const isDone = t.status === 'completed';
          const badgeClass = t.priority === 'P1' ? 'badge-p1' : (t.priority === 'P2' ? 'badge-p2' : 'badge-p3');
          const sourceText = t.source || t.assigned_agent || 'Manual';
          return `
            <div class="task-item ${isDone ? 'completed' : ''}">
              <div class="task-left">
                <input type="checkbox" class="task-checkbox" ${isDone ? 'checked' : ''} onchange="toggleTask(${t.id})">
                <span class="badge ${badgeClass}">${t.priority}</span>
                <span class="badge-source" style="font-size: 10px; padding: 2px 7px; border-radius: 4px; background: rgba(0, 242, 254, 0.1); color: var(--accent-cyan); border: 1px solid rgba(0, 242, 254, 0.25); font-weight: 600; white-space: nowrap;">📍 ${escapeHtml(sourceText)}</span>
                <div style="display: flex; flex-direction: column; gap: 3px;">
                  <span class="task-title" style="font-size: 13.5px; font-weight: 600;">${escapeHtml(t.title)}</span>
                  <span class="task-desc" style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">${escapeHtml(t.description || 'No description provided')}</span>
                </div>
              </div>
              <button class="btn-delete" title="Delete Task" onclick="deleteTask(${t.id})">✕</button>
            </div>
          `;
        }).join('');
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
