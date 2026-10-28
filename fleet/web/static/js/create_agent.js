/**
 * Fleet Create Agent Workflow Wizard & Client Engine
 * Powered by the create-agent Skill & UX-01 Zero-Code Agent Studio.
 */

let currentWizardStep = 1;
let currentPreviewCodeTab = 'py';
let newlyCreatedAgentId = null;

function openCreateAgentModal() {
  const modal = document.getElementById('createAgentModal');
  if (!modal) return;

  // Reset state
  currentWizardStep = 1;
  newlyCreatedAgentId = null;
  const successBox = document.getElementById('wizardSuccessBox');
  if (successBox) successBox.style.display = 'none';

  const notice = document.getElementById('wizardStatusNotice');
  if (notice) notice.style.display = 'none';

  const footer = document.getElementById('wizardFooterBar');
  if (footer) footer.style.display = 'flex';

  goToWizardStep(1);
  modal.style.display = 'flex';

  setTimeout(() => {
    const nlInput = document.getElementById('wizardNaturalLanguageInput');
    const nameInput = document.getElementById('newAgentName');
    if (nlInput) nlInput.focus();
    else if (nameInput) nameInput.focus();
  }, 100);
}

function closeCreateAgentModal() {
  const modal = document.getElementById('createAgentModal');
  if (modal) modal.style.display = 'none';
}

function closeCreateAgentModalOnBackdrop(e) {
  if (e && e.target && e.target.id === 'createAgentModal') {
    closeCreateAgentModal();
  }
}

function onNewAgentNameInput(name) {
  const idInput = document.getElementById('newAgentId');
  if (idInput) {
    const slug = name
      .toLowerCase()
      .replace(/[^a-z0-9_]/g, '_')
      .replace(/_+/g, '_')
      .replace(/^_+|_+$/g, '');
    idInput.value = slug;
  }
  updateLiveWizardPreview();
}

function selectWizardIcon(icon) {
  const iconInput = document.getElementById('newAgentIcon');
  if (iconInput) iconInput.value = icon;
  updateLiveWizardPreview();
}

function applyWizardPreset(preset) {
  const perms = {
    observer: ['ui:render', 'network:http', 'db:read'],
    notifier: ['ui:render', 'notifications:send'],
    analyst: ['ui:render', 'db:read'],
    autonomous: ['ui:render', 'db:read', 'db:write', 'notifications:send', 'network:http', 'system:exec'],
  };

  const selected = perms[preset] || ['ui:render', 'db:read'];
  const allIds = [
    'perm_ui_render', 'perm_db_read', 'perm_db_write',
    'perm_notifications_send', 'perm_network_http', 'perm_system_exec'
  ];

  allIds.forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const permKey = id.replace('perm_', '').replace('_', ':');
    el.checked = selected.includes(permKey);
  });

  document.querySelectorAll('.wizard-preset-card').forEach(card => card.classList.remove('active-preset'));
  if (window.event && window.event.currentTarget) {
    window.event.currentTarget.classList.add('active-preset');
  }

  updateLiveWizardPreview();
}

function getSelectedPermissions() {
  const checked = [];
  const map = {
    'perm_ui_render': 'ui:render',
    'perm_db_read': 'db:read',
    'perm_db_write': 'db:write',
    'perm_notifications_send': 'notifications:send',
    'perm_network_http': 'network:http',
    'perm_system_exec': 'system:exec',
  };
  for (const [id, perm] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el && el.checked) checked.push(perm);
  }
  return checked.length > 0 ? checked : ['ui:render', 'db:read'];
}

function getSelectedUiBlocks() {
  const blockIds = ['alert_banner', 'kpi_row', 'quick_capture_bar', 'history_table', 'habit_checklist', 'status_timeline'];
  const selected = [];
  blockIds.forEach(b => {
    const el = document.getElementById(`uiBlock_${b}`);
    if (el && el.checked) selected.push(b);
  });
  return selected.length > 0 ? selected : ['kpi_row', 'quick_capture_bar', 'history_table'];
}

async function synthesizeWizardFromPrompt() {
  const input = document.getElementById('wizardNaturalLanguageInput');
  const prompt = (input?.value || '').trim();
  if (!prompt) {
    alert('Please enter a plain-English description of the agent you want to build.');
    input?.focus();
    return;
  }
  const btn = document.getElementById('btnSynthesizeAgentPrompt');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Synthesizing...';
  }
  try {
    const res = await fetch('/api/studio/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    const spec = await res.json();
    if (!res.ok || spec.status === 'error') {
      throw new Error(spec.message || 'Failed to synthesize agent spec.');
    }
    const nameEl = document.getElementById('newAgentName');
    const idEl = document.getElementById('newAgentId');
    const iconEl = document.getElementById('newAgentIcon');
    const descEl = document.getElementById('newAgentDesc');
    const taskEl = document.getElementById('newAgentTaskName');
    if (nameEl) nameEl.value = spec.name || '';
    if (idEl) idEl.value = spec.agent_id || '';
    if (iconEl) iconEl.value = spec.icon || '✨';
    if (descEl) descEl.value = spec.description || prompt;
    if (taskEl) taskEl.value = spec.routine_task || 'run_check';

    const perms = spec.permissions || ['db:read', 'ui:render'];
    const permCheckMap = {
      'perm_ui_render': perms.includes('ui:render'),
      'perm_db_read': perms.includes('db:read'),
      'perm_db_write': perms.includes('db:write'),
      'perm_notifications_send': perms.includes('event_bus:publish') || perms.includes('notifications:send'),
      'perm_network_http': perms.includes('network:outbound') || perms.includes('network:http'),
      'perm_system_exec': perms.includes('system:diagnostics') || perms.includes('system:exec'),
    };
    Object.entries(permCheckMap).forEach(([cid, isChecked]) => {
      const el = document.getElementById(cid);
      if (el) el.checked = isChecked;
    });

    const blocks = spec.ui_blocks || ['kpi_row', 'quick_capture_bar', 'history_table'];
    ['alert_banner', 'kpi_row', 'quick_capture_bar', 'history_table', 'habit_checklist', 'status_timeline'].forEach(b => {
      const el = document.getElementById(`uiBlock_${b}`);
      if (el) el.checked = blocks.includes(b);
    });

    updateLiveWizardPreview();
    if (typeof showFleetToast === 'function') {
      showFleetToast(`✨ Synthesized '${spec.name}' (${spec.schedule?.display || 'Scheduled'}) at $0.00!`, false);
    }
  } catch (err) {
    alert('Synthesis error: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '✨ Auto-Fill Wizard';
    }
  }
}

function goToWizardStep(step) {
  if (step < 1 || step > 4) return;

  if (currentWizardStep === 1 && step > 1) {
    const name = (document.getElementById('newAgentName')?.value || '').trim();
    const id = (document.getElementById('newAgentId')?.value || '').trim();
    if (!name) {
      alert('Please enter a display name for your new agent (or use ✨ Auto-Fill Wizard above).');
      document.getElementById('newAgentName')?.focus();
      return;
    }
    if (!id) {
      alert('Please enter a unique agent ID (slug).');
      document.getElementById('newAgentId')?.focus();
      return;
    }
  }

  currentWizardStep = step;

  for (let s = 1; s <= 4; s++) {
    const pane = document.getElementById(`wizardStep_${s}`);
    const pill = document.getElementById(`wizardPill_${s}`);
    if (pane) pane.style.display = (s === step) ? 'block' : 'none';
    if (pill) {
      pill.classList.remove('active', 'completed');
      if (s === step) {
        pill.classList.add('active');
      } else if (s < step) {
        pill.classList.add('completed');
      }
    }
  }

  const backBtn = document.getElementById('btnWizardBack');
  const nextBtn = document.getElementById('btnWizardNext');
  const submitBtn = document.getElementById('btnWizardSubmit');
  const countText = document.getElementById('wizardStepCountText');

  if (backBtn) backBtn.disabled = (step === 1);
  if (countText) countText.textContent = `Step ${step} of 4`;

  if (step === 4) {
    if (nextBtn) nextBtn.style.display = 'none';
    if (submitBtn) submitBtn.style.display = 'inline-flex';
  } else {
    if (nextBtn) nextBtn.style.display = 'inline-flex';
    if (submitBtn) submitBtn.style.display = 'none';
  }

  updateLiveWizardPreview();
}

function nextWizardStep() {
  goToWizardStep(currentWizardStep + 1);
}

function prevWizardStep() {
  goToWizardStep(currentWizardStep - 1);
}

function switchCodePreviewTab(tabKey) {
  currentPreviewCodeTab = tabKey;
  ['py', 'json', 'html'].forEach(t => {
    const btn = document.getElementById(`codeTabBtn_${t}`);
    if (btn) {
      if (t === tabKey) {
        btn.style.background = 'rgba(56, 189, 248, 0.2)';
        btn.style.color = 'var(--accent-cyan)';
      } else {
        btn.style.background = 'transparent';
        btn.style.color = 'var(--text-muted)';
      }
    }
  });
  updateLiveWizardPreview();
}

function toPascalCase(str) {
  return str
    .split('_')
    .map(p => p.charAt(0).toUpperCase() + p.slice(1))
    .join('');
}

function updateLiveWizardPreview() {
  const name = (document.getElementById('newAgentName')?.value || 'My Custom Agent').trim();
  const id = (document.getElementById('newAgentId')?.value || 'my_custom_agent').trim();
  const icon = (document.getElementById('newAgentIcon')?.value || '⚡').trim();
  const desc = (document.getElementById('newAgentDesc')?.value || 'Custom user agent package.').trim();
  const perms = getSelectedPermissions();
  const uiBlocks = getSelectedUiBlocks();
  const syncInterval = parseInt(document.getElementById('settingSyncInterval')?.value || '60', 10);
  const enableAlerts = document.getElementById('settingEnableAlerts')?.value === 'true';
  const taskName = (document.getElementById('newAgentTaskName')?.value || 'check_routine').trim();

  const sumIcon = document.getElementById('previewSummaryIcon');
  const sumName = document.getElementById('previewSummaryName');
  const sumId = document.getElementById('previewSummaryId');
  const sumPerms = document.getElementById('previewSummaryPerms');

  if (sumIcon) sumIcon.textContent = icon;
  if (sumName) sumName.textContent = name;
  if (sumId) sumId.textContent = `id: ${id} | blocks: ${uiBlocks.length}`;
  if (sumPerms) {
    sumPerms.innerHTML = perms.map(p => `<span class="badge" style="background: rgba(56,189,248,0.12); color: var(--accent-cyan); font-size: 11px; padding: 2px 7px;">${p}</span>`).join('');
  }

  const pre = document.getElementById('wizardCodePreview');
  if (!pre) return;

  const pascalName = toPascalCase(id) + 'Agent';

  if (currentPreviewCodeTab === 'py') {
    pre.textContent = `"""
${name} Package for Personal Agentic Fleet.
Generated via create-agent Skill & Zero-Code Studio (UX-01).
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent


class ${pascalName}(FleetAgent):
    @property
    def id(self) -> str:
        return "${id}"

    @property
    def name(self) -> str:
        return "${name}"

    @property
    def icon(self) -> str:
        return "${icon}"

    @property
    def order(self) -> int:
        return 75

    def get_agent_settings_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "refresh_interval_sec",
                "label": "Poll Interval (Seconds)",
                "type": "number",
                "default": ${syncInterval},
                "description": "Frequency for automated updates."
            },
            {
                "id": "enable_alerts",
                "label": "Enable Desktop Notifications",
                "type": "boolean",
                "default": ${enableAlerts ? 'True' : 'False'},
                "description": "Send alerts when tasks run."
            }
        ]

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Runs scheduled or ad-hoc tasks (${taskName})."""
        interval = self.get_setting("refresh_interval_sec", ${syncInterval})
        return {
            "status": "success",
            "title": f"${icon} ${name}: {task}",
            "message": f"Successfully executed '{task}' (interval: {interval}s).",
            "agent": self.id,
            "task": task
        }`;
  } else if (currentPreviewCodeTab === 'json') {
    const manifestObj = {
      id: id,
      name: name,
      version: "1.0.0",
      description: desc,
      icon: icon,
      order: 75,
      permissions: perms,
      ui_blocks: uiBlocks,
      routine_task: taskName,
      entrypoint: "agent.py",
      author: "Fleet Operator"
    };
    pre.textContent = JSON.stringify(manifestObj, null, 2);
  } else if (currentPreviewCodeTab === 'html') {
    pre.textContent = `<div class="panel-section" id="studio_panel_${id}">
  <!-- Declarative UI Blocks: ${uiBlocks.join(', ')} -->
  <div class="card" style="padding: 20px;">
    <strong>${icon} ${name}</strong>
    <p>${desc}</p>
    <button class="btn btn-primary" onclick="triggerScheduledTaskNow('${id}', '${taskName}')">▶ Run ${taskName}</button>
  </div>
</div>`;
  }
}

function copyWizardSkillPrompt() {
  const name = (document.getElementById('newAgentName')?.value || 'My Custom Agent').trim();
  const id = (document.getElementById('newAgentId')?.value || 'my_custom_agent').trim();
  const icon = (document.getElementById('newAgentIcon')?.value || '⚡').trim();
  const desc = (document.getElementById('newAgentDesc')?.value || 'Custom automation agent.').trim();
  const perms = getSelectedPermissions().join(', ');

  const promptText = `Please use the 'create-agent' skill to implement the full operational logic for a new Personal Agentic Fleet agent:
- Name: "${name}"
- ID: "${id}"
- Icon: "${icon}"
- Permissions: [${perms}]
- Purpose: ${desc}
Please generate the complete agent.py with realistic execute_task() logic and rich HTML panel controls.`;

  navigator.clipboard.writeText(promptText).then(() => {
    showFleetToast('📋 Skill prompt copied to clipboard! Paste it into Antigravity chat.', false);
  }).catch(() => {
    alert('Prompt copied:\n\n' + promptText);
  });
}

async function submitCreateAgentWizard() {
  const name = (document.getElementById('newAgentName')?.value || '').trim();
  const id = (document.getElementById('newAgentId')?.value || '').trim();
  const icon = (document.getElementById('newAgentIcon')?.value || '⚡').trim();
  const desc = (document.getElementById('newAgentDesc')?.value || '').trim();
  const category = document.getElementById('newAgentCategory')?.value || 'Productivity';
  const perms = getSelectedPermissions();
  const uiBlocks = getSelectedUiBlocks();
  const routineTask = (document.getElementById('newAgentTaskName')?.value || 'run_check').trim();
  const syncInterval = parseInt(document.getElementById('settingSyncInterval')?.value || '60', 10);
  const enableAlerts = document.getElementById('settingEnableAlerts')?.value === 'true';
  const systemPrompt = (document.getElementById('newAgentSystemPrompt')?.value || '').trim();

  const notice = document.getElementById('wizardStatusNotice');
  const submitBtn = document.getElementById('btnWizardSubmit');

  if (!name || !id) {
    if (notice) {
      notice.style.display = 'block';
      notice.style.background = 'rgba(239, 68, 68, 0.15)';
      notice.style.color = '#fca5a5';
      notice.style.border = '1px solid rgba(239, 68, 68, 0.3)';
      notice.textContent = 'Agent Name and ID are required.';
    }
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Scaffolding Agent...';
  }
  if (notice) notice.style.display = 'none';

  try {
    const res = await fetch('/api/settings/agents/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        id: id,
        icon: icon,
        description: desc,
        category: category,
        permissions: perms,
        ui_blocks: uiBlocks,
        routine_task: routineTask,
        settings: {
          refresh_interval_sec: syncInterval,
          enable_alerts: enableAlerts
        },
        system_prompt: systemPrompt || undefined,
      })
    });

    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Server error creating agent.');
    }

    newlyCreatedAgentId = data.agent_id || id;

    const footer = document.getElementById('wizardFooterBar');
    if (footer) footer.style.display = 'none';

    const successBox = document.getElementById('wizardSuccessBox');
    const successMsg = document.getElementById('wizardSuccessMsg');
    if (successMsg) {
      successMsg.innerHTML = `Agent <strong>${icon} ${name}</strong> (<code>${newlyCreatedAgentId}</code>) was scaffolded with ${uiBlocks.length} UI blocks and loaded into your fleet!`;
    }
    if (successBox) successBox.style.display = 'block';

    showFleetToast(`🎉 Agent '${name}' created and activated!`, false);

    if (typeof fetchAgents === 'function') {
      fetchAgents();
    }
    if (typeof loadSettingsData === 'function') {
      loadSettingsData();
    }

  } catch (err) {
    if (notice) {
      notice.style.display = 'block';
      notice.style.background = 'rgba(239, 68, 68, 0.15)';
      notice.style.color = '#fca5a5';
      notice.style.border = '1px solid rgba(239, 68, 68, 0.3)';
      notice.textContent = 'Error creating agent: ' + err.message;
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = '🚀 Scaffold & Activate Agent';
    }
  }
}

function openNewlyCreatedAgent() {
  closeCreateAgentModal();
  if (newlyCreatedAgentId) {
    if (typeof switchView === 'function') {
      switchView(newlyCreatedAgentId);
    } else {
      window.location.reload();
    }
  }
}
