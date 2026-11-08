// --- Daily, Monthly & Yearly Unified Cross-Agent Tasks Engine (100% Local-Only Storage) ---
    window._cachedTasksList = [];
    window._activeTaskFilter = 'ALL';
    window._activeTaskAgentFilter = 'ALL';
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

    function filterTasksByAgent(agentId) {
      window._activeTaskAgentFilter = agentId || 'ALL';
      renderTasksList();
    }

    function _getTaskCadence(t) {
      if (t.cadence) return String(t.cadence);
      const s = String(t.source || '').toLowerCase();
      if (s === 'monthly') return 'Monthly';
      if (s === 'yearly') return 'Yearly';
      return 'Daily';
    }

    const _MONTH_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const _MONTH_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

    function _formatIsoDateParts(isoStr) {
      if (!isoStr) return null;
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return null;
      const day = String(d.getDate()).padStart(2, '0');
      const mShort = _MONTH_SHORT[d.getMonth()];
      const mFull = _MONTH_FULL[d.getMonth()];
      const year = d.getFullYear();
      return {
        day,
        monthShort: mShort,
        monthFull: mFull,
        year,
        formattedDate: `${day} ${mShort} ${year}`,
        formattedMonthYear: `${mFull} ${year}`,
        shortMonthYear: `${mShort} ${year}`
      };
    }

    function _getCurrentCycleParts() {
      const now = new Date();
      const year = now.getFullYear();
      const monthIdx = now.getMonth();
      const lastDay = new Date(year, monthIdx + 1, 0).getDate();
      const mShort = _MONTH_SHORT[monthIdx];
      const mFull = _MONTH_FULL[monthIdx];
      return {
        year,
        nextYearShort: String((year + 1) % 100).padStart(2, '0'),
        nextYearFull: year + 1,
        monthShort: mShort,
        monthFull: mFull,
        shortMonthYear: `${mShort} ${year}`,
        fullMonthYear: `${mFull} ${year}`,
        endOfMonthDate: `${lastDay} ${mShort} ${year}`
      };
    }

    function resolveTaskTemporalMeta(t) {
      const cyc = _getCurrentCycleParts();
      const srcLower = String(t.source || t.assigned_agent || 'Manual').toLowerCase();
      const titleLower = String(t.title || '').toLowerCase();
      const descLower = String(t.description || '').toLowerCase();
      const rawDue = String(t.due_date || '').trim();
      const createdParts = _formatIsoDateParts(t.created_at) || {
        day: String(new Date().getDate()).padStart(2, '0'),
        monthShort: cyc.monthShort,
        monthFull: cyc.monthFull,
        year: cyc.year,
        formattedDate: `${String(new Date().getDate()).padStart(2, '0')} ${cyc.monthShort} ${cyc.year}`,
        formattedMonthYear: cyc.fullMonthYear,
        shortMonthYear: cyc.shortMonthYear
      };
      const updatedParts = _formatIsoDateParts(t.updated_at || t.created_at) || createdParts;
      const isDone = t.status === 'completed';

      if (srcLower === 'monthly') {
        let dueText = rawDue;
        if (!dueText) {
          if (titleLower.includes('axis') || descLower.includes('4th of every month')) {
            dueText = `04 ${cyc.monthShort} ${cyc.year} (4th of every month)`;
          } else if (titleLower.includes('icici') || descLower.includes('27th of every month')) {
            dueText = `27 ${cyc.monthShort} ${cyc.year} (27th of every month)`;
          } else if (titleLower.includes('websites') || descLower.includes('ojas.world')) {
            dueText = `By ${cyc.endOfMonthDate} • GoDaddy (Ojas.world): Jan ${cyc.nextYearFull}`;
          } else {
            dueText = `By ${cyc.endOfMonthDate} (1st–${cyc.endOfMonthDate})`;
          }
        }
        return {
          periodLabel: `🗓️ Month: ${cyc.fullMonthYear}`,
          dueLabel: `📌 Due Date: ${dueText}`,
          statusLabel: isDone
            ? `✓ Completed for ${cyc.shortMonthYear} (${updatedParts.formattedDate})`
            : `⏳ Pending for ${cyc.shortMonthYear}`
        };
      }

      if (srcLower === 'yearly') {
        let dueText = rawDue;
        if (!dueText || dueText.toLowerCase() === 'jan 25th') {
          if (titleLower.includes('income tax') || descLower.includes('jan 25')) {
            dueText = `25 Jan ${cyc.nextYearFull} (Month: January • Year: ${cyc.nextYearFull})`;
          } else {
            dueText = `Annual ${cyc.year} Cycle (Jan–Dec ${cyc.year})`;
          }
        }
        return {
          periodLabel: `🗓️ Year: ${cyc.year} (FY ${cyc.year}–${cyc.nextYearShort})`,
          dueLabel: `📌 Due Date: ${dueText}`,
          statusLabel: isDone
            ? `✓ Completed for ${cyc.year} (${updatedParts.formattedDate})`
            : `⏳ Pending for Year ${cyc.year}–${cyc.nextYearShort}`
        };
      }

      // Daily / One-Off / Manual / Antigravity / Dashboard tasks
      const dueText = rawDue
        ? `${rawDue} (Added ${createdParts.formattedDate})`
        : `${createdParts.formattedDate} (Month: ${createdParts.monthShort} • Year: ${createdParts.year})`;
      return {
        periodLabel: `🗓️ Date: ${createdParts.formattedDate} (${createdParts.shortMonthYear})`,
        dueLabel: `📌 Target Date: ${dueText}`,
        statusLabel: isDone
          ? `✓ Completed (${updatedParts.formattedDate})`
          : `⏳ Pending (${createdParts.formattedDate})`
      };
    }

    function updateTaskFilterBarCounts(tasks) {
      const bar = document.getElementById('taskFilterBar');
      if (!bar) return;
      const cyc = _getCurrentCycleParts();
      const agentFilter = window._activeTaskAgentFilter || 'ALL';
      const scopedTasks = agentFilter === 'ALL'
        ? tasks
        : tasks.filter(t => String(t.agent_id || 'overview') === agentFilter);

      const allCount = scopedTasks.length;
      const dailyTasks = scopedTasks.filter(t => _getTaskCadence(t).toLowerCase() === 'daily');
      const dailyPending = dailyTasks.filter(t => t.status !== 'completed').length;
      const monthlyTasks = scopedTasks.filter(t => _getTaskCadence(t).toLowerCase() === 'monthly');
      const monthlyPending = monthlyTasks.filter(t => t.status !== 'completed').length;
      const yearlyTasks = scopedTasks.filter(t => _getTaskCadence(t).toLowerCase() === 'yearly');
      const yearlyPending = yearlyTasks.filter(t => t.status !== 'completed').length;
      const pendingCount = scopedTasks.filter(t => t.status !== 'completed').length;
      const completedCount = scopedTasks.filter(t => t.status === 'completed').length;

      const labels = {
        'ALL': `All (${allCount} • ${pendingCount} Pending)`,
        'Daily': `☀️ Daily (${dailyPending} Pending / ${dailyTasks.length})`,
        'Monthly': `📅 Monthly: ${cyc.shortMonthYear} (${monthlyPending} Pending / ${monthlyTasks.length})`,
        'Yearly': `🗓️ Yearly: ${cyc.year}–${cyc.nextYearShort} (${yearlyPending} Pending / ${yearlyTasks.length})`,
        'PENDING': `⏳ Pending (${pendingCount})`,
        'COMPLETED': `✓ Completed (${completedCount})`
      };
      bar.querySelectorAll('.filter-btn').forEach(btn => {
        const key = btn.getAttribute('data-task-filter');
        if (key && labels[key]) {
          btn.textContent = labels[key];
        }
      });

      const sel = document.getElementById('taskAgentFilterSelect');
      if (sel) {
        const agentCounts = {};
        const agentMeta = {};
        tasks.forEach(t => {
          const aid = String(t.agent_id || 'overview');
          agentCounts[aid] = (agentCounts[aid] || 0) + 1;
          if (!agentMeta[aid]) {
            agentMeta[aid] = {
              name: t.agent_name || 'Overview & Tasks',
              icon: t.agent_icon || '⚡'
            };
          }
        });
        const curVal = sel.value || 'ALL';
        let optsHtml = `<option value="ALL">🤖 All Agents (${tasks.length} Tasks)</option>`;
        Object.keys(agentCounts).forEach(aid => {
          const m = agentMeta[aid];
          optsHtml += `<option value="${escapeHtml(aid)}">${escapeHtml(m.icon)} ${escapeHtml(m.name)} (${agentCounts[aid]})</option>`;
        });
        sel.innerHTML = optsHtml;
        sel.value = agentCounts[curVal] || curVal === 'ALL' ? curVal : 'ALL';
      }
    }

    function renderTasksList() {
      const list = document.getElementById('taskList');
      if (!list) return;
      updateTaskMaskButtonUI();
      const allTasks = Array.isArray(window._cachedTasksList) ? window._cachedTasksList : [];
      updateTaskFilterBarCounts(allTasks);

      const filter = window._activeTaskFilter || 'ALL';
      const agentFilter = window._activeTaskAgentFilter || 'ALL';
      const tasks = allTasks.filter(t => {
        if (agentFilter !== 'ALL' && String(t.agent_id || 'overview') !== agentFilter) return false;
        if (filter === 'ALL') return true;
        if (filter === 'PENDING') return t.status !== 'completed';
        if (filter === 'COMPLETED') return t.status === 'completed';
        return _getTaskCadence(t).toLowerCase() === String(filter).toLowerCase();
      });

      const counterEl = document.getElementById('taskCounter');
      if (counterEl) {
        const pendingShown = tasks.filter(t => t.status !== 'completed').length;
        counterEl.innerText = (filter === 'ALL' && agentFilter === 'ALL')
          ? `${allTasks.length} Total (${pendingShown} Pending)`
          : `${tasks.length} / ${allTasks.length} Shown (${pendingShown} Pending)`;
      }

      if (tasks.length === 0) {
        list.innerHTML = `<div style="text-align: center; padding: 24px; color: var(--text-muted); font-size: 13px;">No tasks in this view. Type above to add one!</div>`;
        return;
      }

      list.innerHTML = tasks.map(t => {
        const isDone = t.status === 'completed';
        const badgeClass = t.priority === 'P1' ? 'badge-p1' : (t.priority === 'P2' ? 'badge-p2' : 'badge-p3');
        const cadenceText = _getTaskCadence(t);
        const srcLower = cadenceText.toLowerCase();
        const sourceIcon = srcLower === 'monthly' ? '📅' : (srcLower === 'yearly' ? '🗓️' : '☀️');
        const sourceBadgeStyle = srcLower === 'monthly'
          ? 'background: rgba(56, 189, 248, 0.14); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35);'
          : (srcLower === 'yearly'
            ? 'background: rgba(168, 85, 247, 0.14); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35);'
            : 'background: rgba(245, 158, 11, 0.14); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35);');
        const agentName = t.agent_name || 'Overview & Tasks';
        const agentIcon = t.agent_icon || '⚡';
        const agentId = t.agent_id || 'overview';
        const actionType = t.action_type || 'core_task';
        const rawId = t.raw_id !== undefined ? t.raw_id : t.id;
        const maskedTitle = maskSensitiveTaskText(t.title || '');
        const temporal = resolveTaskTemporalMeta({ ...t, source: cadenceText });
        const statusPillStyle = isDone
          ? 'background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);'
          : 'background: rgba(245, 158, 11, 0.16); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4);';

        const canToggleCheckbox = ['core_task', 'medication', 'routine', 'custom_agent_entry'].includes(actionType);
        const canEditTask = ['core_task', 'medication', 'routine', 'custom_agent_entry'].includes(actionType);
        const taskDomKey = String(t.id !== undefined ? t.id : rawId);
        const isEditingThis = String(window._editingTaskId || '') === taskDomKey;
        const editBtnHtml = canEditTask
          ? `<button class="btn-delete" title="Edit Task" style="color: #38bdf8; font-size: 13px; padding: 2px 6px;" onclick="openEditTaskInline('${escapeHtml(taskDomKey)}')">✏️</button>`
          : '';

        let inlineActionsHtml = '';
        if (actionType === 'hydration') {
          inlineActionsHtml = `<button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(56, 189, 248, 0.16); border-color: rgba(56, 189, 248, 0.4); color: #38bdf8;" onclick="executeUnifiedTaskAction('hydration', 'hyd_today', 'health', 'log_water')">💧 +1 Glass (+250ml)</button>`;
        } else if (actionType === 'email_proposal') {
          inlineActionsHtml = `
            <button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(16, 185, 129, 0.18); border-color: rgba(16, 185, 129, 0.45); color: #34d399;" onclick="executeUnifiedTaskAction('email_proposal', '${escapeHtml(String(rawId))}', 'gmail', 'approve')">✅ Approve</button>
            <button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.4); color: #f87171;" onclick="executeUnifiedTaskAction('email_proposal', '${escapeHtml(String(rawId))}', 'gmail', 'reject')">✕ Reject</button>
          `;
        } else if (actionType === 'urgent_email') {
          inlineActionsHtml = `<button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(56, 189, 248, 0.15); border-color: rgba(56, 189, 248, 0.4); color: #38bdf8;" onclick="if(typeof openEmailModal==='function') openEmailModal('${escapeHtml(String(rawId))}')">📧 Read Email</button>`;
        } else if (actionType === 'optimizer') {
          inlineActionsHtml = `<button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(168, 85, 247, 0.18); border-color: rgba(168, 85, 247, 0.45); color: #c084fc;" onclick="executeUnifiedTaskAction('optimizer', 'opt_workstation_health', 'optimizer', 'optimize')">⚡ 1-Click Optimize PC</button>`;
        } else if (actionType === 'optimizer_upgrade') {
          inlineActionsHtml = `<button class="btn" style="font-size: 11px; padding: 3px 9px; background: rgba(56, 189, 248, 0.18); border-color: rgba(56, 189, 248, 0.45); color: #38bdf8;" onclick="executeUnifiedTaskAction('optimizer_upgrade', 'opt_os_software_upgrades', 'optimizer', 'upgrade')">⬆️ Auto-Upgrade</button>`;
        } else if (actionType === 'core_task') {
          inlineActionsHtml = `${editBtnHtml}<button class="btn-delete" title="Delete Task" onclick="deleteTask(${Number(rawId)})">✕</button>`;
        } else {
          inlineActionsHtml = editBtnHtml;
        }

        const checkboxHtml = canToggleCheckbox
          ? `<input type="checkbox" class="task-checkbox" style="margin-top: 3px;" ${isDone ? 'checked' : ''} onchange="executeUnifiedTaskAction('${escapeHtml(actionType)}', '${escapeHtml(String(rawId))}', '${escapeHtml(agentId)}', 'toggle')">`
          : `<span style="font-size: 15px; margin-top: 1px;">${escapeHtml(agentIcon)}</span>`;

        const curPrio = (t.priority || 'P2').toUpperCase();
        const curSrc = t.source || cadenceText || 'Monthly';
        const editFormHtml = isEditingThis ? `
          <div style="margin-top: 8px; padding: 10px 12px; background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 8px; display: flex; flex-direction: column; gap: 8px;">
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              <input type="text" id="editTaskTitle_${escapeHtml(taskDomKey)}" value="${escapeHtml(t.title || '')}" placeholder="Task title" style="flex: 2; min-width: 200px; font-size: 12.5px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--card-border); background: rgba(255,255,255,0.05); color: var(--text);">
              <input type="text" id="editTaskDue_${escapeHtml(taskDomKey)}" value="${escapeHtml(t.due_date || '')}" placeholder="Due date (e.g. 04 Nov 2026)" style="flex: 1; min-width: 160px; font-size: 12px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--card-border); background: rgba(255,255,255,0.05); color: var(--text);">
              <select id="editTaskPrio_${escapeHtml(taskDomKey)}" style="font-size: 12px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--card-border); background: rgba(15,23,42,0.95); color: var(--text);">
                <option value="P1" ${curPrio === 'P1' ? 'selected' : ''}>🔴 P1 High</option>
                <option value="P2" ${curPrio === 'P2' ? 'selected' : ''}>🟡 P2 Medium</option>
                <option value="P3" ${curPrio === 'P3' ? 'selected' : ''}>🔵 P3 Low</option>
              </select>
              <select id="editTaskSource_${escapeHtml(taskDomKey)}" style="font-size: 12px; padding: 6px 8px; border-radius: 6px; border: 1px solid var(--card-border); background: rgba(15,23,42,0.95); color: var(--text);">
                <option value="Daily" ${curSrc.toLowerCase() === 'daily' ? 'selected' : ''}>☀️ Daily</option>
                <option value="Monthly" ${curSrc.toLowerCase() === 'monthly' ? 'selected' : ''}>📅 Monthly</option>
                <option value="Yearly" ${curSrc.toLowerCase() === 'yearly' ? 'selected' : ''}>🗓️ Yearly</option>
                <option value="Dashboard" ${!['daily','monthly','yearly'].includes(curSrc.toLowerCase()) ? 'selected' : ''}>💻 Dashboard</option>
              </select>
            </div>
            <textarea id="editTaskDesc_${escapeHtml(taskDomKey)}" rows="2" placeholder="Task description / details" style="width: 100%; font-size: 12px; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--card-border); background: rgba(255,255,255,0.05); color: var(--text); resize: vertical;">${escapeHtml(t.description || '')}</textarea>
            <div style="display: flex; justify-content: flex-end; gap: 8px;">
              <button class="btn" style="font-size: 11.5px; padding: 4px 12px;" onclick="cancelEditTaskInline()">Cancel</button>
              <button class="btn btn-primary" style="font-size: 11.5px; padding: 4px 14px;" onclick="saveEditedTask('${escapeHtml(taskDomKey)}', '${escapeHtml(actionType)}', '${escapeHtml(String(rawId))}', '${escapeHtml(agentId)}')">💾 Save Changes</button>
            </div>
          </div>
        ` : '';

        return `
          <div class="task-item ${isDone ? 'completed' : ''}">
            <div class="task-left" style="align-items: flex-start; width: 100%;">
              ${checkboxHtml}
              <span class="badge ${badgeClass}" style="margin-top: 1px;">${escapeHtml(t.priority || 'P2')}</span>
              <span class="badge-source" style="font-size: 10px; padding: 2px 7px; border-radius: 4px; ${sourceBadgeStyle} font-weight: 600; white-space: nowrap; margin-top: 1px;">${sourceIcon} ${escapeHtml(cadenceText)}</span>
              <div style="display: flex; flex-direction: column; gap: 5px; flex: 1; min-width: 0;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; flex-wrap: wrap;">
                  <span class="task-title" style="font-size: 13.5px; font-weight: 600;">${escapeHtml(maskedTitle)}</span>
                  <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                    <span style="font-size: 10.5px; padding: 2px 8px; border-radius: 999px; font-weight: 600; white-space: nowrap; background: rgba(99, 102, 241, 0.14); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.32); cursor: pointer;" title="Source Agent: ${escapeHtml(agentName)} (Click to view agent)" onclick="if(window.FleetNavigator) FleetNavigator.switchAgent('${escapeHtml(agentId)}')">${escapeHtml(agentIcon)} ${escapeHtml(agentName)}</span>
                    <span style="font-size: 10.5px; padding: 2px 8px; border-radius: 999px; font-weight: 600; white-space: nowrap; ${statusPillStyle}">${escapeHtml(temporal.statusLabel)}</span>
                  </div>
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 6px; align-items: center;">
                  <span style="font-size: 11px; padding: 1px 7px; border-radius: 4px; background: rgba(148, 163, 184, 0.12); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.25); font-weight: 500;">${escapeHtml(temporal.periodLabel)}</span>
                  <span style="font-size: 11px; padding: 1px 7px; border-radius: 4px; background: rgba(56, 189, 248, 0.08); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.22); font-weight: 500;">${escapeHtml(temporal.dueLabel)}</span>
                </div>
                <span class="task-desc" style="font-size: 12px; color: var(--text-muted); line-height: 1.45;">${formatTaskDescriptionHtml(t.description)}</span>
                ${editFormHtml}
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 6px; margin-left: 8px; flex-shrink: 0;">
              ${inlineActionsHtml}
            </div>
          </div>
        `;
      }).join('');
    }

    function openEditTaskInline(taskDomKey) {
      window._editingTaskId = String(taskDomKey || '');
      renderTasksList();
    }

    function cancelEditTaskInline() {
      window._editingTaskId = '';
      renderTasksList();
    }

    async function saveEditedTask(taskDomKey, actionType, rawId, agentId) {
      const titleEl = document.getElementById(`editTaskTitle_${taskDomKey}`);
      const descEl = document.getElementById(`editTaskDesc_${taskDomKey}`);
      const dueEl = document.getElementById(`editTaskDue_${taskDomKey}`);
      const prioEl = document.getElementById(`editTaskPrio_${taskDomKey}`);
      const srcEl = document.getElementById(`editTaskSource_${taskDomKey}`);
      const title = titleEl ? titleEl.value.trim() : '';
      const description = descEl ? descEl.value.trim() : '';
      const due_date = dueEl ? dueEl.value.trim() : '';
      const priority = prioEl ? prioEl.value : 'P2';
      const source = srcEl ? srcEl.value : 'Monthly';
      if (!title || !description) {
        alert('Both a task title and description are required.');
        return;
      }
      try {
        await fetch('/api/tasks/unified_action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action_type: actionType || 'core_task',
            raw_id: rawId,
            agent_id: agentId || 'overview',
            sub_action: 'edit',
            title,
            description,
            due_date,
            priority,
            source
          })
        });
        window._editingTaskId = '';
        await fetchTasks();
        if (typeof fetchBriefing === 'function') fetchBriefing();
        if (typeof fetchLogs === 'function') fetchLogs();
      } catch (e) {
        console.error('Failed to save edited task:', e);
      }
    }

    async function executeUnifiedTaskAction(actionType, rawId, agentId, subAction) {
      try {
        await fetch('/api/tasks/unified_action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            action_type: actionType,
            raw_id: rawId,
            agent_id: agentId,
            sub_action: subAction || 'toggle',
            glasses_delta: 1
          })
        });
        fetchTasks();
        if (typeof fetchBriefing === 'function') fetchBriefing();
        if (typeof fetchRoutines === 'function') fetchRoutines();
        if (typeof fetchLogs === 'function') fetchLogs();
      } catch (e) {
        console.error(e);
      }
    }

    async function fetchTasks() {
      try {
        const res = await fetch('/api/tasks?unified=true');
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
      const dueInput = document.getElementById('taskDueDate');
      const sourceSelect = document.getElementById('taskSource');
      const title = input.value.trim();
      const description = descInput ? descInput.value.trim() : '';
      const due_date = dueInput ? dueInput.value.trim() : '';
      const priority = document.getElementById('taskPriority').value;
      const source = sourceSelect ? sourceSelect.value : 'Dashboard';
      if (!title || !description) {
        alert('Both a task title and description are required.');
        return;
      }

      const resp = await fetch('/api/tasks', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ title, description, priority, source, due_date })
      });
      if (resp.ok) {
        input.value = '';
        if (descInput) descInput.value = '';
        if (dueInput) dueInput.value = '';
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
window.openEditTaskInline = openEditTaskInline;
window.cancelEditTaskInline = cancelEditTaskInline;
window.saveEditedTask = saveEditedTask;
window.filterTasksBySource = filterTasksBySource;
window.filterTasksByAgent = filterTasksByAgent;
window.executeUnifiedTaskAction = executeUnifiedTaskAction;
window.toggleTaskSensitiveMask = toggleTaskSensitiveMask;
