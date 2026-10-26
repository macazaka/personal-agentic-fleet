/**
 * Fleet Settings & Agent Customization Controller
 * Enables runtime configuration of fleet agents, system preferences,
 * timezone, notifications, hyperscaler models, and instant dynamic tab updates.
 */

let fleetSettingsState = {
  settings: {},
  agents: [],
  activeTab: 'agents',
  searchQuery: '',
};

// --- Modal Lifecycle ---

async function openSettingsModal() {
  const modal = document.getElementById('fleetSettingsModal');
  if (!modal) return;
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';
  await refreshSettingsData();
  switchSettingsModalTab(fleetSettingsState.activeTab || 'agents');
}

function closeSettingsModal() {
  const modal = document.getElementById('fleetSettingsModal');
  if (modal) {
    modal.style.display = 'none';
    document.body.style.overflow = '';
  }
}

function switchSettingsModalTab(tab) {
  fleetSettingsState.activeTab = tab;
  ['agents', 'general', 'ai', 'backups'].forEach(t => {
    const btn = document.getElementById(`settingsNavBtn_${t}`);
    const view = document.getElementById(`settingsView_${t}`);
    if (btn) btn.classList.toggle('active', t === tab);
    if (view) view.style.display = (t === tab) ? 'block' : 'none';
  });

  if (tab === 'agents') {
    renderSettingsAgents();
  } else if (tab === 'general') {
    populateGeneralSettingsForm();
  } else if (tab === 'ai') {
    populateAISettingsForm();
  }
}

// --- Data Fetching ---

async function refreshSettingsData() {
  try {
    const res = await fetch('/api/settings');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status === 'ok') {
      fleetSettingsState.settings = data.settings || {};
      fleetSettingsState.agents = data.agents || [];
      updateSettingsBadgeCounts(data.active_agents_count, data.total_agents_count);
    }
  } catch (err) {
    console.error('Failed to load fleet settings:', err);
    showSettingsToast('Failed to load fleet settings: ' + err.message, 'error');
  }
}

function updateSettingsBadgeCounts(activeCount, totalCount) {
  const badge = document.getElementById('settingsAgentsCountBadge');
  if (badge) {
    badge.innerText = `${activeCount} / ${totalCount} Active`;
  }
}

// --- Agent Management Tab ---

function filterSettingsAgents(query) {
  fleetSettingsState.searchQuery = (query || '').toLowerCase().trim();
  renderSettingsAgents();
}

function renderSettingsAgents() {
  const container = document.getElementById('settingsAgentsList');
  if (!container) return;

  const query = fleetSettingsState.searchQuery;
  const agents = fleetSettingsState.agents.filter(a => {
    if (!query) return true;
    return (a.name || '').toLowerCase().includes(query) ||
           (a.id || '').toLowerCase().includes(query) ||
           (a.provider || '').toLowerCase().includes(query) ||
           (a.model || '').toLowerCase().includes(query);
  });

  if (agents.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; color: var(--text-muted);">
        <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
        <div>No agents found matching "${escapeHtml(query)}"</div>
      </div>
    `;
    return;
  }

  container.innerHTML = agents.map(agent => {
    const isEnabled = Boolean(agent.enabled);
    const isDefault = Boolean(agent.is_default);
    const isCustomized = Boolean(agent.is_customized);

    return `
      <div class="agent-setting-card ${isEnabled ? 'is-enabled' : 'is-disabled'}" id="agentCard_${agent.id}">
        <div class="agent-card-header">
          <div class="agent-card-identity">
            <span class="agent-card-icon">${escapeHtml(agent.icon || '🤖')}</span>
            <div>
              <div class="agent-card-title-row">
                <strong class="agent-card-title">${escapeHtml(agent.name || agent.id)}</strong>
                <code class="agent-card-id">${escapeHtml(agent.id)}</code>
                ${isDefault ? '<span class="agent-pill pill-default">Default Tab</span>' : ''}
                ${isCustomized ? '<span class="agent-pill pill-customized">Customized</span>' : ''}
              </div>
              <div class="agent-card-subtitle">
                Order: ${agent.order || 100} • Model: <code>${escapeHtml(agent.model || 'Auto')}</code> • Provider: <code>${escapeHtml(agent.provider || 'Auto')}</code>
              </div>
            </div>
          </div>
          <div class="agent-card-actions">
            <button class="btn btn-sm btn-outline" onclick="toggleAgentDrawer('${agent.id}')" title="Configure Agent Properties">
              ⚙️ Customize
            </button>
            <label class="toggle-switch" title="${isEnabled ? 'Deactivate Agent' : 'Activate Agent'}">
              <input type="checkbox" id="toggle_${agent.id}" ${isEnabled ? 'checked' : ''} onchange="onToggleAgentSwitch('${agent.id}', this.checked)">
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>

        <!-- Collapsible Configuration Drawer -->
        <div class="agent-card-drawer" id="drawer_${agent.id}" style="display: none;">
          <div class="agent-form-grid">
            <div class="form-group">
              <label>Display Name</label>
              <input type="text" id="cfg_name_${agent.id}" class="form-control" value="${escapeHtml(agent.name || '')}" placeholder="Agent Name">
            </div>
            <div class="form-group">
              <label>Icon (Emoji or SVG)</label>
              <input type="text" id="cfg_icon_${agent.id}" class="form-control" value="${escapeHtml(agent.icon || '🤖')}" style="max-width: 120px;">
            </div>
            <div class="form-group">
              <label>Tab Order (0 = First)</label>
              <input type="number" id="cfg_order_${agent.id}" class="form-control" value="${agent.order || 100}" style="max-width: 120px;">
            </div>
            <div class="form-group">
              <label>LLM Hyperscaler Provider</label>
              <select id="cfg_provider_${agent.id}" class="form-control">
                <option value="auto" ${agent.provider === 'auto' ? 'selected' : ''}>Auto Gateway</option>
                <option value="google" ${agent.provider === 'google' ? 'selected' : ''}>Google Gemini</option>
                <option value="anthropic" ${agent.provider === 'anthropic' ? 'selected' : ''}>Anthropic Claude</option>
                <option value="microsoft" ${agent.provider === 'microsoft' ? 'selected' : ''}>Microsoft Azure / OpenAI</option>
                <option value="aws" ${agent.provider === 'aws' ? 'selected' : ''}>AWS Bedrock</option>
                <option value="ollama" ${agent.provider === 'ollama' ? 'selected' : ''}>Local Ollama ($0.00)</option>
              </select>
            </div>
            <div class="form-group" style="grid-column: span 2;">
              <label>LLM Model Tier / ID</label>
              <input type="text" id="cfg_model_${agent.id}" class="form-control" value="${escapeHtml(agent.model || '')}" placeholder="e.g. gemini-2.5-flash, claude-3-7-sonnet, llama3.2">
            </div>
            <div class="form-group" style="grid-column: span 2;">
              <label>Custom System Instruction / Prompt</label>
              <textarea id="cfg_prompt_${agent.id}" class="form-control" rows="3" placeholder="Define customized persona or instructions...">${escapeHtml(agent.system_prompt || '')}</textarea>
            </div>
          </div>

          <div class="agent-drawer-footer">
            <label style="display: inline-flex; align-items: center; gap: 6px; font-size: 12px; cursor: pointer;">
              <input type="checkbox" id="cfg_default_${agent.id}" ${isDefault ? 'checked' : ''}>
              Set as Default Active Tab on Dashboard Load
            </label>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-sm btn-ghost" onclick="resetAgentToDefaults('${agent.id}')" title="Reset all overrides to factory defaults">
                ↺ Reset Defaults
              </button>
              <button class="btn btn-sm btn-primary" onclick="saveAgentCustomization('${agent.id}')">
                💾 Save Customization
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

function toggleAgentDrawer(agentId) {
  const drawer = document.getElementById(`drawer_${agentId}`);
  if (!drawer) return;
  const isHidden = drawer.style.display === 'none';
  drawer.style.display = isHidden ? 'block' : 'none';
}

async function onToggleAgentSwitch(agentId, enabled) {
  try {
    const res = await fetch('/api/settings/agents/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: agentId, enabled: enabled })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Toggle failed');
    }

    // Update in local state
    const agent = fleetSettingsState.agents.find(a => a.id === agentId);
    if (agent) {
      agent.enabled = enabled;
    }
    updateSettingsBadgeCounts(data.active_agents_count, data.total_agents_count);

    // Update Card UI
    const card = document.getElementById(`agentCard_${agentId}`);
    if (card) {
      card.classList.toggle('is-enabled', enabled);
      card.classList.toggle('is-disabled', !enabled);
    }

    // Refresh dynamic navigation tabs in real time
    if (typeof initDynamicAgentTabs === 'function') {
      await initDynamicAgentTabs();
    }

    showSettingsToast(`Agent '${agent ? agent.name : agentId}' ${enabled ? 'activated' : 'deactivated'}.`);
  } catch (err) {
    console.error('Error toggling agent:', err);
    showSettingsToast('Failed to toggle agent: ' + err.message, 'error');
    // Revert switch
    const sw = document.getElementById(`toggle_${agentId}`);
    if (sw) sw.checked = !enabled;
  }
}

async function saveAgentCustomization(agentId) {
  const name = (document.getElementById(`cfg_name_${agentId}`)?.value || '').trim();
  const icon = (document.getElementById(`cfg_icon_${agentId}`)?.value || '').trim();
  const orderVal = parseInt(document.getElementById(`cfg_order_${agentId}`)?.value || '100', 10);
  const provider = document.getElementById(`cfg_provider_${agentId}`)?.value || 'auto';
  const model = (document.getElementById(`cfg_model_${agentId}`)?.value || '').trim();
  const prompt = (document.getElementById(`cfg_prompt_${agentId}`)?.value || '').trim();
  const isDefault = Boolean(document.getElementById(`cfg_default_${agentId}`)?.checked);

  const payload = {
    id: agentId,
    name: name,
    icon: icon,
    order: orderVal,
    provider: provider,
    model: model,
    system_prompt: prompt,
    is_default: isDefault,
  };

  try {
    const res = await fetch('/api/settings/agents/customize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Customization failed');
    }

    showSettingsToast(`Agent '${name || agentId}' customized successfully.`);
    await refreshSettingsData();
    renderSettingsAgents();

    // Re-render header navigation tabs
    if (typeof initDynamicAgentTabs === 'function') {
      await initDynamicAgentTabs();
    }
  } catch (err) {
    console.error('Failed to customize agent:', err);
    showSettingsToast('Failed to save customization: ' + err.message, 'error');
  }
}

async function resetAgentToDefaults(agentId) {
  if (!confirm(`Reset agent '${agentId}' back to built-in factory defaults?`)) return;

  try {
    const res = await fetch('/api/settings/agents/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: agentId })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Reset failed');
    }

    showSettingsToast(`Agent '${agentId}' reset to factory defaults.`);
    await refreshSettingsData();
    renderSettingsAgents();

    if (typeof initDynamicAgentTabs === 'function') {
      await initDynamicAgentTabs();
    }
  } catch (err) {
    console.error('Failed to reset agent:', err);
    showSettingsToast('Failed to reset agent: ' + err.message, 'error');
  }
}

// --- Quick Add Custom Agent ---

function toggleCreateAgentForm() {
  const form = document.getElementById('createAgentInlineForm');
  if (form) {
    form.style.display = form.style.display === 'none' ? 'block' : 'none';
  }
}

async function submitCreateCustomAgent() {
  const idInput = document.getElementById('newAgentId');
  const nameInput = document.getElementById('newAgentName');
  const iconInput = document.getElementById('newAgentIcon');
  const descInput = document.getElementById('newAgentDesc');

  const cleanId = (idInput?.value || '').trim().toLowerCase().replace(/[^a-z0-9_]/g, '');
  const name = (nameInput?.value || '').trim();
  const icon = (iconInput?.value || '✨').trim();
  const desc = (descInput?.value || '').trim();

  if (!cleanId || !name) {
    alert('Please specify both an Agent Identifier (alphanumeric/underscore) and Display Name.');
    return;
  }

  try {
    const res = await fetch('/api/fleet/agents/custom/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: cleanId,
        name: name,
        icon: icon,
        description: desc,
        order: 85,
      })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Creation failed');
    }

    showSettingsToast(`Custom Agent '${name}' created and activated!`);
    toggleCreateAgentForm();
    if (idInput) idInput.value = '';
    if (nameInput) nameInput.value = '';

    await refreshSettingsData();
    renderSettingsAgents();

    if (typeof initDynamicAgentTabs === 'function') {
      await initDynamicAgentTabs();
    }
  } catch (err) {
    console.error('Failed to create agent:', err);
    showSettingsToast('Agent creation failed: ' + err.message, 'error');
  }
}

// --- General Settings Form ---

function populateGeneralSettingsForm() {
  const s = fleetSettingsState.settings || {};
  const tz = document.getElementById('genSettingTimezone');
  const notify = document.getElementById('genSettingNotifications');
  const quiet = document.getElementById('genSettingQuietHours');
  const qStart = document.getElementById('genSettingQuietStart');
  const qEnd = document.getElementById('genSettingQuietEnd');
  const cost = document.getElementById('genSettingCostPolicy');
  const theme = document.getElementById('genSettingTheme');

  if (tz) tz.value = s.timezone || 'Asia/Kolkata (IST, UTC+05:30)';
  if (notify) notify.checked = s.notifications_enabled !== 'false';
  if (quiet) quiet.checked = s.quiet_hours_enabled === 'true';
  if (qStart) qStart.value = s.quiet_hours_start || '22:00';
  if (qEnd) qEnd.value = s.quiet_hours_end || '07:00';
  if (cost) cost.value = s.cost_policy || 'PREFER_ZERO_TOKEN_CODE';
  if (theme) theme.value = s.theme || 'dark';
}

async function saveGeneralSettings() {
  const payload = {
    timezone: document.getElementById('genSettingTimezone')?.value,
    notifications_enabled: Boolean(document.getElementById('genSettingNotifications')?.checked),
    quiet_hours_enabled: Boolean(document.getElementById('genSettingQuietHours')?.checked),
    quiet_hours_start: document.getElementById('genSettingQuietStart')?.value || '22:00',
    quiet_hours_end: document.getElementById('genSettingQuietEnd')?.value || '07:00',
    cost_policy: document.getElementById('genSettingCostPolicy')?.value || 'PREFER_ZERO_TOKEN_CODE',
    theme: document.getElementById('genSettingTheme')?.value || 'dark',
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Save failed');
    }
    fleetSettingsState.settings = data.settings || {};
    showSettingsToast('General fleet settings saved successfully.');
  } catch (err) {
    console.error('Failed to save general settings:', err);
    showSettingsToast('Failed to save settings: ' + err.message, 'error');
  }
}

// --- AI & Hyperscaler Settings Form ---

function populateAISettingsForm() {
  const s = fleetSettingsState.settings || {};
  const prov = document.getElementById('aiSettingProvider');
  const model = document.getElementById('aiSettingModel');
  const ollama = document.getElementById('aiSettingOllamaUrl');

  if (prov) prov.value = s.default_provider || 'auto';
  if (model) model.value = s.default_model || 'gemini-2.5-flash';
  if (ollama) ollama.value = s.ollama_url || 'http://localhost:11434';
}

async function saveAISettings() {
  const payload = {
    default_provider: document.getElementById('aiSettingProvider')?.value || 'auto',
    default_model: document.getElementById('aiSettingModel')?.value || 'gemini-2.5-flash',
    ollama_url: document.getElementById('aiSettingOllamaUrl')?.value || 'http://localhost:11434',
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Save failed');
    }
    fleetSettingsState.settings = data.settings || {};
    showSettingsToast('AI Hyperscaler configuration saved.');
  } catch (err) {
    console.error('Failed to save AI settings:', err);
    showSettingsToast('Failed to save AI configuration: ' + err.message, 'error');
  }
}

async function testOllamaConnection() {
  const url = document.getElementById('aiSettingOllamaUrl')?.value || 'http://localhost:11434';
  const statusEl = document.getElementById('ollamaStatusNotice');
  if (statusEl) {
    statusEl.innerHTML = '<span style="color: var(--accent-cyan);">Testing connection...</span>';
  }

  try {
    const res = await fetch(url + '/api/tags', { method: 'GET', mode: 'cors' });
    if (res.ok) {
      if (statusEl) statusEl.innerHTML = '<span style="color: #10b981;">✓ Ollama service is reachable online</span>';
    } else {
      if (statusEl) statusEl.innerHTML = `<span style="color: #f59e0b;">⚠ Responded HTTP ${res.status}</span>`;
    }
  } catch (err) {
    if (statusEl) {
      statusEl.innerHTML = '<span style="color: var(--text-muted);">Local Ollama offline or CORS restricted (Normal if not started)</span>';
    }
  }
}

// --- Maintenance & Backups ---

async function triggerBackupSnapshotNow() {
  const notice = document.getElementById('backupSnapshotNotice');
  if (notice) notice.innerHTML = '<span style="color: var(--accent-cyan);">Generating database snapshot...</span>';

  try {
    const res = await fetch('/api/settings/backup/snapshot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Snapshot failed');
    }

    if (notice) {
      notice.innerHTML = `
        <span style="color: #10b981;">
          ✓ Snapshot created: <strong>${escapeHtml(data.snapshot_file)}</strong> (${(data.size_bytes / 1024).toFixed(1)} KB)
        </span>
      `;
    }
    showSettingsToast('Backup snapshot completed successfully!');
  } catch (err) {
    console.error('Failed to create snapshot:', err);
    if (notice) {
      notice.innerHTML = `<span style="color: #ef4444;">Failed to create snapshot: ${escapeHtml(err.message)}</span>`;
    }
    showSettingsToast('Snapshot creation failed: ' + err.message, 'error');
  }
}

// --- Settings Toast ---

function showSettingsToast(msg, type = 'success') {
  let toast = document.getElementById('fleetToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'fleetToast';
    toast.className = 'fleet-toast';
    document.body.appendChild(toast);
  }

  toast.className = `fleet-toast toast-${type} toast-show`;
  toast.innerText = msg;

  if (window._fleetToastTimer) clearTimeout(window._fleetToastTimer);
  window._fleetToastTimer = setTimeout(() => {
    toast.classList.remove('toast-show');
  }, 3500);
}

// Export functions to window
window.openSettingsModal = openSettingsModal;
window.closeSettingsModal = closeSettingsModal;
window.switchSettingsModalTab = switchSettingsModalTab;
window.filterSettingsAgents = filterSettingsAgents;
window.toggleAgentDrawer = toggleAgentDrawer;
window.onToggleAgentSwitch = onToggleAgentSwitch;
window.saveAgentCustomization = saveAgentCustomization;
window.resetAgentToDefaults = resetAgentToDefaults;
window.toggleCreateAgentForm = toggleCreateAgentForm;
window.submitCreateCustomAgent = submitCreateCustomAgent;
window.saveGeneralSettings = saveGeneralSettings;
window.saveAISettings = saveAISettings;
window.testOllamaConnection = testOllamaConnection;
window.triggerBackupSnapshotNow = triggerBackupSnapshotNow;
window.showSettingsToast = showSettingsToast;

