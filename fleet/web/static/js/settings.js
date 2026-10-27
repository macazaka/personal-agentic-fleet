/**
 * Fleet Settings & Agent Customization Controller
 * Enables runtime configuration of fleet agents, system preferences,
 * timezone, notifications, hyperscaler models, and instant dynamic tab updates.
 */

let fleetSettingsState = {
  settings: {},
  agents: [],
  catalog: [],
  activeTab: 'agents',
  searchQuery: '',
  agentCategory: 'all',
  catalogQuery: '',
  catalogCategory: 'all',
  versionInfo: null,
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
  ['agents', 'catalog', 'updates', 'general', 'ai', 'backups', 'autoheal', 'mind'].forEach(t => {
    const btn = document.getElementById(`settingsNavBtn_${t}`);
    const view = document.getElementById(`settingsView_${t}`);
    if (btn) btn.classList.toggle('active', t === tab);
    if (view) view.style.display = (t === tab) ? 'block' : 'none';
  });

  if (tab === 'agents') {
    renderSettingsAgents();
  } else if (tab === 'catalog') {
    loadAgentCatalog();
  } else if (tab === 'updates') {
    loadVersionStatus();
  } else if (tab === 'general') {
    populateGeneralSettingsForm();
  } else if (tab === 'ai') {
    populateAISettingsForm();
  } else if (tab === 'autoheal') {
    loadAutoHealStatus();
  } else if (tab === 'mind') {
    loadFleetMindStatus();
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

function filterSettingsAgentCategory(cat) {
  fleetSettingsState.agentCategory = cat || 'all';
  renderSettingsAgents();
}

function renderSettingsAgents() {
  const container = document.getElementById('settingsAgentsList');
  if (!container) return;

  const query = fleetSettingsState.searchQuery;
  const cat = fleetSettingsState.agentCategory || 'all';
  const agents = fleetSettingsState.agents.filter(a => {
    if (cat !== 'all') {
      const aCat = a.category || 'Productivity';
      if (aCat.toLowerCase() !== cat.toLowerCase()) return false;
    }
    if (!query) return true;
    return (a.name || '').toLowerCase().includes(query) ||
           (a.id || '').toLowerCase().includes(query) ||
           (a.category || '').toLowerCase().includes(query) ||
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
                ${isEnabled ? '<span class="agent-pill pill-active" style="background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3); font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600;">🟢 Active</span>' : '<span class="agent-pill pill-disabled" style="background: rgba(255,255,255,0.06); color: var(--text-muted); border: 1px solid rgba(255,255,255,0.1); font-size: 11px; padding: 2px 8px; border-radius: 12px; font-weight: 600;">⚪ Disabled</span>'}
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

          <!-- Dynamic Agent-Specific Settings Section -->
          ${(agent.agent_settings_schema && agent.agent_settings_schema.length > 0) ? `
            <div style="margin-top: 14px; padding-top: 14px; border-top: 1px dashed rgba(255,255,255,0.1);">
              <div style="font-weight: 600; font-size: 12.5px; color: var(--accent-cyan); margin-bottom: 10px; display: flex; align-items: center; gap: 6px;">
                <span>🛠️</span>
                <span>Agent-Specific Settings (${escapeHtml(agent.name || agent.id)})</span>
              </div>
              <div class="agent-form-grid">
                ${agent.agent_settings_schema.map(s => {
                  const sVal = (s.value !== undefined) ? s.value : s.default;
                  const fieldId = `cfg_spec_${agent.id}_${s.id}`;
                  if (s.type === 'boolean') {
                    return `
                      <div class="form-group" style="grid-column: span 2; display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: rgba(255,255,255,0.02); border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">
                        <div>
                          <label style="margin: 0; font-size: 12px; font-weight: 600; color: var(--text);">${escapeHtml(s.label)}</label>
                          <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(s.description || '')}</div>
                        </div>
                        <label class="toggle-switch">
                          <input type="checkbox" id="${fieldId}" data-setting-id="${s.id}" data-type="boolean" ${Boolean(sVal) ? 'checked' : ''}>
                          <span class="toggle-slider"></span>
                        </label>
                      </div>
                    `;
                  } else if (s.type === 'select') {
                    return `
                      <div class="form-group">
                        <label style="font-size: 12px;">${escapeHtml(s.label)}</label>
                        <select id="${fieldId}" data-setting-id="${s.id}" data-type="select" class="form-control" style="font-size: 12px;">
                          ${(s.options || []).map(opt => `
                            <option value="${escapeHtml(opt)}" ${String(sVal) === String(opt) ? 'selected' : ''}>${escapeHtml(opt)}</option>
                          `).join('')}
                        </select>
                        <small style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(s.description || '')}</small>
                      </div>
                    `;
                  } else if (s.type === 'number') {
                    return `
                      <div class="form-group">
                        <label style="font-size: 12px;">${escapeHtml(s.label)}</label>
                        <input type="number" id="${fieldId}" data-setting-id="${s.id}" data-type="number" class="form-control" value="${sVal !== undefined ? sVal : ''}" style="font-size: 12px;">
                        <small style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(s.description || '')}</small>
                      </div>
                    `;
                  } else {
                    return `
                      <div class="form-group" style="grid-column: span 2;">
                        <label style="font-size: 12px;">${escapeHtml(s.label)}</label>
                        <input type="text" id="${fieldId}" data-setting-id="${s.id}" data-type="text" class="form-control" value="${escapeHtml(String(sVal || ''))}" style="font-size: 12px;">
                        <small style="font-size: 10.5px; color: var(--text-muted);">${escapeHtml(s.description || '')}</small>
                      </div>
                    `;
                  }
                }).join('')}
              </div>
            </div>
          ` : ''}

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

  // Harvest agent-specific custom settings
  const agent = fleetSettingsState.agents.find(a => a.id === agentId);
  const specificSettings = {};
  if (agent && agent.agent_settings_schema) {
    agent.agent_settings_schema.forEach(s => {
      const field = document.getElementById(`cfg_spec_${agentId}_${s.id}`);
      if (field) {
        if (s.type === 'boolean') {
          specificSettings[s.id] = Boolean(field.checked);
        } else if (s.type === 'number') {
          specificSettings[s.id] = parseFloat(field.value) || 0;
        } else {
          specificSettings[s.id] = field.value;
        }
      }
    });
  }

  const payload = {
    id: agentId,
    name: name,
    icon: icon,
    order: orderVal,
    provider: provider,
    model: model,
    system_prompt: prompt,
    is_default: isDefault,
    settings: specificSettings,
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
  const layout = document.getElementById('genSettingLayout');

  if (tz) tz.value = s.timezone || 'Asia/Kolkata (IST, UTC+05:30)';
  if (notify) notify.checked = s.notifications_enabled !== 'false';
  if (quiet) quiet.checked = s.quiet_hours_enabled === 'true';
  if (qStart) qStart.value = s.quiet_hours_start || '22:00';
  if (qEnd) qEnd.value = s.quiet_hours_end || '07:00';
  if (cost) cost.value = s.cost_policy || 'PREFER_ZERO_TOKEN_CODE';
  if (theme) theme.value = s.theme || 'dark';
  if (layout) layout.value = s.layout || 'sidebar_dock';

  // Highlight active layout option card
  ['sidebar_dock', 'command_deck', 'launchpad_grid'].forEach(l => {
    const card = document.getElementById(`layoutCard_${l}`);
    if (card) card.classList.toggle('active', l === (s.layout || 'sidebar_dock'));
  });
}

function onSelectLayoutInSettings(layoutId) {
  const layoutSelect = document.getElementById('genSettingLayout');
  if (layoutSelect) layoutSelect.value = layoutId;

  ['sidebar_dock', 'command_deck', 'launchpad_grid'].forEach(l => {
    const card = document.getElementById(`layoutCard_${l}`);
    if (card) card.classList.toggle('active', l === layoutId);
  });

  if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.setWorkspaceLayout === 'function') {
    FleetNavigator.setWorkspaceLayout(layoutId, true);
  }
}

function onSelectThemeInSettings(themeId) {
  if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.setWorkspaceTheme === 'function') {
    FleetNavigator.setWorkspaceTheme(themeId, true);
  }
}

async function saveGeneralSettings() {
  const selectedLayout = document.getElementById('genSettingLayout')?.value || 'sidebar_dock';
  const selectedTheme = document.getElementById('genSettingTheme')?.value || 'dark';
  const payload = {
    timezone: document.getElementById('genSettingTimezone')?.value,
    notifications_enabled: Boolean(document.getElementById('genSettingNotifications')?.checked),
    quiet_hours_enabled: Boolean(document.getElementById('genSettingQuietHours')?.checked),
    quiet_hours_start: document.getElementById('genSettingQuietStart')?.value || '22:00',
    quiet_hours_end: document.getElementById('genSettingQuietEnd')?.value || '07:00',
    cost_policy: document.getElementById('genSettingCostPolicy')?.value || 'PREFER_ZERO_TOKEN_CODE',
    theme: selectedTheme,
    layout: selectedLayout,
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
    if (typeof FleetNavigator !== 'undefined') {
      FleetNavigator.setWorkspaceLayout(selectedLayout, false);
      FleetNavigator.setWorkspaceTheme(selectedTheme, false);
    }
    showSettingsToast('General fleet settings, layout & theme saved successfully.');
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


// --- Discover & Download Agents Catalog ---

async function loadAgentCatalog() {
  const notice = document.getElementById('settingsCatalogNotice');
  if (notice) notice.innerHTML = '<span style="color: var(--accent-cyan);">Fetching available agents from catalog...</span>';

  try {
    const res = await fetch('/api/settings/agents/catalog');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.status === 'ok') {
      fleetSettingsState.catalog = data.catalog || [];
      if (notice) notice.innerHTML = '';
      renderAgentCatalog();
    }
  } catch (err) {
    console.error('Failed to load agent catalog:', err);
    if (notice) {
      notice.innerHTML = `<span style="color: #ef4444;">Failed to load catalog: ${escapeHtml(err.message)}</span>`;
    }
  }
}

async function refreshCatalogData() {
  showSettingsToast('Checking GitHub for new agent packages...');
  await loadAgentCatalog();
}

function filterCatalogAgents(query) {
  fleetSettingsState.catalogQuery = (query || '').toLowerCase().trim();
  renderAgentCatalog();
}

function setCatalogCategory(cat) {
  fleetSettingsState.catalogCategory = cat;
  renderAgentCatalog();
}

function renderAgentCatalog() {
  const container = document.getElementById('settingsCatalogList');
  const pillsContainer = document.getElementById('catalogCategoryPills');
  if (!container) return;

  const catalog = fleetSettingsState.catalog || [];
  const query = fleetSettingsState.catalogQuery || '';
  const currentCategory = fleetSettingsState.catalogCategory || 'all';

  // Render category filter pills
  if (pillsContainer) {
    const categories = ['all', ...new Set(catalog.map(c => c.category).filter(Boolean))];
    pillsContainer.innerHTML = categories.map(cat => {
      const isSel = (cat === currentCategory);
      return `
        <button class="btn btn-sm ${isSel ? 'btn-primary' : 'btn-ghost'}" style="font-size: 11px; padding: 3px 8px;" onclick="setCatalogCategory('${cat}')">
          ${cat === 'all' ? 'All Categories' : escapeHtml(cat)}
        </button>
      `;
    }).join('');
  }

  const filtered = catalog.filter(item => {
    const matchesCat = (currentCategory === 'all') || (item.category === currentCategory);
    if (!matchesCat) return false;
    if (!query) return true;
    return (item.name || '').toLowerCase().includes(query) ||
           (item.id || '').toLowerCase().includes(query) ||
           (item.description || '').toLowerCase().includes(query) ||
           (item.category || '').toLowerCase().includes(query);
  });

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 40px 20px; color: var(--text-muted);">
        <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
        <div>No downloadable agents found matching "${escapeHtml(query)}"</div>
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(item => {
    const isInstalled = Boolean(item.is_installed);
    const perms = item.permissions || [];

    return `
      <div class="card" style="padding: 16px; display: flex; flex-direction: column; justify-content: space-between; border: 1px solid var(--card-border); background: rgba(255,255,255,0.02); border-radius: 8px;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 26px;">${escapeHtml(item.icon || '📦')}</span>
              <div>
                <strong style="font-size: 14px; color: var(--text);">${escapeHtml(item.name)}</strong>
                <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(item.category || 'General')} • v${escapeHtml(item.version || '1.0.0')}</div>
              </div>
            </div>
            ${isInstalled ?
              '<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; font-size: 11px;">✓ Installed</span>' :
              '<span class="badge" style="background: rgba(0, 242, 254, 0.15); color: var(--accent-cyan); font-size: 11px;">Available</span>'
            }
          </div>
          <p style="font-size: 12px; color: var(--text-muted); margin: 6px 0 12px 0; line-height: 1.4;">
            ${escapeHtml(item.description)}
          </p>
          <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 14px;">
            ${perms.map(p => `<code style="font-size: 10px; background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px;">${escapeHtml(p)}</code>`).join('')}
          </div>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 12px;">
          ${isInstalled ? `
            <button class="btn btn-sm btn-ghost" onclick="switchSettingsModalTab('agents'); filterSettingsAgents('${item.id}');">
              ⚙️ Configure in Agents
            </button>
          ` : `
            <button class="btn btn-sm btn-primary" onclick="installCatalogAgent('${item.id}')">
              📥 Download & Install
            </button>
          `}
        </div>
      </div>
    `;
  }).join('');
}

async function installCatalogAgent(agentId) {
  try {
    showSettingsToast(`Downloading agent '${agentId}' from catalog...`);
    const res = await fetch('/api/settings/agents/catalog/install', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: agentId })
    });
    const data = await res.json();
    if (!res.ok || data.status !== 'success') {
      throw new Error(data.message || 'Installation failed');
    }

    showSettingsToast(`Agent '${data.name || agentId}' downloaded and activated!`);
    await refreshSettingsData();
    await loadAgentCatalog();

    if (typeof initDynamicAgentTabs === 'function') {
      await initDynamicAgentTabs();
    }
  } catch (err) {
    console.error('Failed to install catalog agent:', err);
    showSettingsToast('Failed to install agent: ' + err.message, 'error');
  }
}

// --- GitHub Version & Updates Engine ---

async function loadVersionStatus() {
  const pill = document.getElementById('versionStatusPill');
  const installedText = document.getElementById('installedVersionText');
  const latestText = document.getElementById('latestVersionText');
  const applyBtn = document.getElementById('btnApplyUpdate');
  const notesBox = document.getElementById('updateReleaseNotesBox');
  const releaseTitle = document.getElementById('updateReleaseTitle');
  const notesContent = document.getElementById('updateReleaseNotesContent');

  if (pill) pill.innerText = 'Checking GitHub...';

  try {
    const res = await fetch('/api/settings/version');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    fleetSettingsState.versionInfo = data;

    if (installedText) installedText.innerText = `v${data.current_version}`;
    if (latestText) latestText.innerText = `v${data.latest_version}`;

    if (data.update_available) {
      if (pill) {
        pill.innerText = '🚀 Update Available';
        pill.style.background = 'rgba(0, 242, 254, 0.2)';
        pill.style.color = 'var(--accent-cyan)';
      }
      if (applyBtn) applyBtn.style.display = 'inline-block';
      if (notesBox) notesBox.style.display = 'block';
      if (releaseTitle) releaseTitle.innerText = data.release_name || `Personal Agentic Fleet v${data.latest_version}`;
      if (notesContent) notesContent.innerText = data.release_notes || 'New release ready to download on GitHub.';

      // Light up header update badge
      updateHeaderBadge(true, data.latest_version);
    } else {
      if (pill) {
        pill.innerText = '✓ Up to Date';
        pill.style.background = 'rgba(16, 185, 129, 0.15)';
        pill.style.color = '#10b981';
      }
      if (applyBtn) applyBtn.style.display = 'none';
      if (notesBox) notesBox.style.display = 'none';
      updateHeaderBadge(false);
    }
  } catch (err) {
    console.error('Failed to load version status:', err);
    if (pill) {
      pill.innerText = 'Offline';
      pill.style.background = 'rgba(255, 255, 255, 0.1)';
      pill.style.color = 'var(--text-muted)';
    }
  }
}

async function checkGitHubUpdateManual() {
  showSettingsToast('Checking GitHub for new releases...');
  const pill = document.getElementById('versionStatusPill');
  if (pill) pill.innerText = 'Checking GitHub...';

  try {
    const res = await fetch('/api/settings/version/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    fleetSettingsState.versionInfo = data;
    await loadVersionStatus();

    if (data.update_available) {
      showSettingsToast(`New release v${data.latest_version} available from GitHub!`);
    } else {
      showSettingsToast(`Personal Agentic Fleet is up to date (v${data.current_version}).`);
    }
  } catch (err) {
    showSettingsToast('Could not reach GitHub: ' + err.message, 'error');
  }
}

async function applyGitHubUpdate() {
  if (!confirm('Download and apply the latest update from GitHub now?')) return;

  showSettingsToast('Applying update from GitHub...');
  try {
    const res = await fetch('/api/settings/version/upgrade', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    if (data.status === 'success') {
      alert(`Update Successful!

${data.message}

Please restart Fleet to apply all changes.`);
      showSettingsToast('Update complete. Please restart server.');
      await loadVersionStatus();
    } else {
      alert(`Update Notice: ${data.message}`);
      showSettingsToast(data.message, 'error');
    }
  } catch (err) {
    showSettingsToast('Failed to apply update: ' + err.message, 'error');
  }
}

function updateHeaderBadge(available, version) {
  const badge = document.getElementById('headerUpdateBadge');
  const badgeText = document.getElementById('headerUpdateBadgeText');
  if (badge) {
    badge.style.display = available ? 'inline-flex' : 'none';
    if (badgeText && version) {
      badgeText.innerText = `Update v${version}`;
    }
  }
}

function openSettingsModalToUpdates() {
  openSettingsModal();
  switchSettingsModalTab('updates');
}

// Background version checker on page load
setTimeout(() => {
  fetch('/api/settings/version')
    .then(r => r.json())
    .then(d => {
      if (d.update_available) {
        updateHeaderBadge(true, d.latest_version);
      }
    })
    .catch(() => {});
}, 2000);

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
window.onSelectLayoutInSettings = onSelectLayoutInSettings;
window.onSelectThemeInSettings = onSelectThemeInSettings;
window.saveAISettings = saveAISettings;
window.testOllamaConnection = testOllamaConnection;
window.triggerBackupSnapshotNow = triggerBackupSnapshotNow;
window.showSettingsToast = showSettingsToast;


window.loadAgentCatalog = loadAgentCatalog;
window.refreshCatalogData = refreshCatalogData;
window.filterCatalogAgents = filterCatalogAgents;
window.setCatalogCategory = setCatalogCategory;
window.renderAgentCatalog = renderAgentCatalog;
window.installCatalogAgent = installCatalogAgent;
window.loadVersionStatus = loadVersionStatus;
window.checkGitHubUpdateManual = checkGitHubUpdateManual;
window.applyGitHubUpdate = applyGitHubUpdate;
window.openSettingsModalToUpdates = openSettingsModalToUpdates;

// --- Proactive Log Scanner & Autonomous Auto-Healer ---

async function loadAutoHealStatus() {
  const notice = document.getElementById('autoHealNotice');
  try {
    const res = await fetch('/api/diagnostics/log-analysis');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const report = data.report || {};

    const scoreEl = document.getElementById('autoHealHealthScore');
    const timeEl = document.getElementById('autoHealLastScanTime');
    const totalEl = document.getElementById('autoHealTotalImprovements');

    if (scoreEl) {
      const score = report.system_health_index !== undefined ? report.system_health_index : 100.0;
      scoreEl.textContent = `${score}/100`;
      scoreEl.style.color = score >= 90 ? 'var(--accent-green)' : (score >= 60 ? '#f59e0b' : '#ef4444');
    }
    if (timeEl && report.timestamp) {
      const dt = new Date(report.timestamp);
      timeEl.textContent = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    await loadAutoImprovementsHistory();
  } catch (err) {
    if (notice) notice.innerHTML = `<span style="color: #ef4444;">Failed to load log analysis status: ${escapeHtml(err.message)}</span>`;
  }
}

async function triggerProactiveLogScanNow() {
  const btn = document.getElementById('btnRunAutoHealNow');
  const notice = document.getElementById('autoHealNotice');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Scanning & Auto-Healing...';
  }
  if (notice) notice.innerHTML = '<span style="color: var(--accent-cyan);">Proactively scanning logs and evaluating autonomous improvements...</span>';

  try {
    const res = await fetch('/api/diagnostics/log-analysis/run', { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const report = data.report || {};
    const impCount = report.improvements_applied_count || 0;
    const issuesCount = report.issues_detected_count || 0;

    if (notice) {
      notice.innerHTML = `<span style="color: var(--accent-green);">✓ Proactive scan complete: ${issuesCount} issues analyzed, ${impCount} improvement(s) executed. Health score: ${report.system_health_index}/100.</span>`;
    }
    await loadAutoHealStatus();
    showSettingsToast(`Proactive Log Scan Complete: ${impCount} improvement(s) applied.`, 'success');
  } catch (err) {
    if (notice) notice.innerHTML = `<span style="color: #ef4444;">Error during proactive scan: ${escapeHtml(err.message)}</span>`;
    showSettingsToast(`Scan failed: ${err.message}`, 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔍 Run Proactive Scan & Auto-Heal';
    }
  }
}

async function loadAutoImprovementsHistory() {
  const container = document.getElementById('autoImprovementsList');
  const totalEl = document.getElementById('autoHealTotalImprovements');
  if (!container) return;

  try {
    const res = await fetch('/api/diagnostics/auto-improvements?limit=30');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const improvements = data.improvements || [];
    const stats = data.stats || {};

    if (totalEl) {
      totalEl.textContent = stats.total_improvements !== undefined ? stats.total_improvements : improvements.length;
    }

    if (!improvements.length) {
      container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">No autonomous improvements required yet. All logs clean.</div>';
      return;
    }

    container.innerHTML = improvements.map(imp => {
      const dt = imp.created_at ? new Date(imp.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Recent';
      const statusBadge = imp.status === 'VERIFIED'
        ? '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 10px;">VERIFIED</span>'
        : (imp.status === 'APPLIED'
          ? '<span class="badge" style="background: rgba(0, 242, 254, 0.2); color: #00f2fe; border: 1px solid rgba(0, 242, 254, 0.4); font-size: 10px;">APPLIED</span>'
          : `<span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.4); font-size: 10px;">${escapeHtml(imp.status)}</span>`);

      return `
        <div style="padding: 10px 12px; margin-bottom: 8px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--card-border); border-radius: 6px; display: flex; flex-direction: column; gap: 4px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
              ${statusBadge}
              <strong style="color: var(--text); font-size: 12px;">${escapeHtml(imp.issue_type || 'SYSTEM')}</strong>
              <span style="font-size: 11px; color: var(--text-muted);">${escapeHtml(imp.severity || 'INFO')}</span>
            </div>
            <span style="font-size: 11px; color: var(--text-muted);">${dt}</span>
          </div>
          <div style="font-size: 11.5px; color: var(--text); margin-top: 2px;">${escapeHtml(imp.action_taken || imp.description || '')}</div>
        </div>
      `;
    }).join('');
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 12px;">Failed to load history: ${escapeHtml(err.message)}</div>`;
  }
}

window.loadAutoHealStatus = loadAutoHealStatus;
window.triggerProactiveLogScanNow = triggerProactiveLogScanNow;
window.loadAutoImprovementsHistory = loadAutoImprovementsHistory;


// --- Cognitive Fleet Mind Controller ---

async function loadFleetMindStatus() {
  try {
    const res = await fetch('/api/mind/status');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const harmony = data.cognitive_harmony_index || 100;
    const overallState = data.overall_state || 'COHERENT';
    const badgeEl = document.getElementById('mindHarmonyBadge');
    if (badgeEl) {
      badgeEl.textContent = `Harmony: ${harmony}/100 [${overallState}]`;
      badgeEl.style.color = harmony >= 90 ? '#c084fc' : (harmony >= 75 ? '#38bdf8' : '#ef4444');
    }

    const layers = data.layers || {};
    const brain = layers.brain || {};
    const cons = layers.consciousness || {};
    const subc = layers.subconsciousness || {};
    const soul = layers.soul || {};

    // Brain layer
    const brainHealthBadge = document.getElementById('brainHealthBadge');
    if (brainHealthBadge) brainHealthBadge.textContent = `${brain.health_score || 100}% Health`;
    const brainSynapses = document.getElementById('brainSynapsesCount');
    if (brainSynapses) brainSynapses.textContent = (brain.synapses_fired || 0).toLocaleString();
    const brainRam = document.getElementById('brainRamUsage');
    if (brainRam) brainRam.textContent = `${brain.working_memory?.rss_mb || 0} MB`;
    const brainThreads = document.getElementById('brainThreadsCount');
    if (brainThreads) brainThreads.textContent = brain.working_memory?.threads || 0;
    const brainEpistemic = document.getElementById('brainEpistemicSize');
    if (brainEpistemic) brainEpistemic.textContent = `${Math.round((brain.epistemic_memory?.database_size_bytes || 0) / 1024)} KB`;
    const brainLogs = document.getElementById('brainLogsCount');
    if (brainLogs) brainLogs.textContent = brain.epistemic_memory?.activities_count || 0;

    // Consciousness layer
    const consBadge = document.getElementById('consciousnessStateBadge');
    if (consBadge) consBadge.textContent = cons.executive_attention?.state || 'AWARE';
    const consAgent = document.getElementById('consActiveAgent');
    if (consAgent) consAgent.textContent = cons.executive_attention?.active_agent || 'Fleet Executive';
    const consGoal = document.getElementById('consActiveGoal');
    if (consGoal) consGoal.textContent = cons.executive_attention?.current_goal || 'Observing Sensory Synapses';
    const consTotalCritiques = document.getElementById('consTotalCritiques');
    if (consTotalCritiques) consTotalCritiques.textContent = cons.meta_critique_vitals?.total_critiques_logged || 0;
    const consAvgQuality = document.getElementById('consAvgQuality');
    if (consAvgQuality) consAvgQuality.textContent = `${cons.meta_critique_vitals?.average_quality_score || 100.0}/100`;

    // Subconsciousness layer
    const subcBadge = document.getElementById('subcStateBadge');
    if (subcBadge) subcBadge.textContent = subc.status || 'INTUITING';
    const subcInsights = document.getElementById('subcInsightsCount');
    if (subcInsights) subcInsights.textContent = subc.recent_insights_count || 0;
    const subcLastDream = document.getElementById('subcLastDream');
    if (subcLastDream) {
      const dt = subc.last_dream_cycle;
      subcLastDream.textContent = dt && dt !== 'Awaiting initial dream cycle' ? new Date(dt).toLocaleTimeString() : 'Awaiting Dream';
    }

    // Soul layer
    const soulBadge = document.getElementById('soulScoreBadge');
    const soulScore = soul.latest_audit?.alignment_score !== undefined ? soul.latest_audit.alignment_score : 100.0;
    if (soulBadge) soulBadge.textContent = `${soulScore}% ${soul.latest_audit?.status || 'PURE'}`;
    const soulGen = document.getElementById('soulGeneration');
    if (soulGen) soulGen.textContent = `Gen ${soul.evolution_metrics?.current_generation || 1}`;

    loadMindInsights();
    loadMindCritiques();
  } catch (err) {
    console.error('Failed to load fleet mind status:', err);
  }
}

async function loadMindInsights(manual = false) {
  const container = document.getElementById('mindDreamInsightsList');
  if (!container) return;

  try {
    const res = await fetch('/api/mind/insights?limit=15');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const insights = data.insights || [];

    if (!insights.length) {
      container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">No dream insights yet. Click "🌙 Dream Cycle" above to consolidate memory.</div>';
      return;
    }

    container.innerHTML = insights.map(ins => {
      const dt = ins.created_at ? new Date(ins.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
      const typeColor = ins.insight_type === 'FRICTION' ? '#ef4444' : (ins.insight_type === 'HABIT' ? '#38bdf8' : '#c084fc');
      return `
        <div style="padding: 8px 10px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--card-border); border-radius: 6px; display: flex; flex-direction: column; gap: 3px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="badge" style="background: rgba(255,255,255,0.06); color: ${typeColor}; border: 1px solid ${typeColor}40; font-size: 9.5px; padding: 1px 5px;">${escapeHtml(ins.insight_type || 'WISDOM')}</span>
              <strong style="color: var(--text); font-size: 11.5px;">${escapeHtml(ins.title || '')}</strong>
            </div>
            <span style="font-size: 10px; color: var(--text-muted);">${dt}</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(ins.description || '')}</div>
          ${ins.actionable_recommendation ? `<div style="font-size: 10.5px; color: var(--accent-cyan); margin-top: 2px;">💡 ${escapeHtml(ins.actionable_recommendation)}</div>` : ''}
        </div>
      `;
    }).join('');
    if (manual) showSettingsToast('Dream insights refreshed', 'success');
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 10px;">Failed to load insights: ${escapeHtml(err.message)}</div>`;
  }
}

async function loadMindCritiques(manual = false) {
  const container = document.getElementById('mindCritiquesList');
  if (!container) return;

  try {
    const res = await fetch('/api/mind/critiques?limit=15');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const critiques = data.critiques || [];

    if (!critiques.length) {
      container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 20px;">No meta-critiques recorded yet. Executive critiques fire automatically as agents execute actions.</div>';
      return;
    }

    container.innerHTML = critiques.map(c => {
      const dt = c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
      const passBadge = c.passed
        ? `<span class="badge" style="background: rgba(34, 197, 94, 0.15); color: var(--accent-green); font-size: 9.5px; padding: 1px 5px;">${c.score}/100 PASS</span>`
        : `<span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; font-size: 9.5px; padding: 1px 5px;">${c.score}/100 FAIL</span>`;
      return `
        <div style="padding: 8px 10px; background: rgba(255, 255, 255, 0.03); border: 1px solid var(--card-border); border-radius: 6px; display: flex; flex-direction: column; gap: 3px;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 6px;">
              ${passBadge}
              <strong style="color: var(--text); font-size: 11.5px;">${escapeHtml(c.agent || '')} → ${escapeHtml(c.action || '')}</strong>
            </div>
            <span style="font-size: 10px; color: var(--text-muted);">${dt}</span>
          </div>
          <div style="font-size: 11px; color: var(--text-muted);">${escapeHtml(c.notes || '')}</div>
          ${c.corrective_action ? `<div style="font-size: 10.5px; color: #f59e0b; margin-top: 2px;">🔧 Remedy: ${escapeHtml(c.corrective_action)}</div>` : ''}
        </div>
      `;
    }).join('');
    if (manual) showSettingsToast('Meta-critiques refreshed', 'success');
  } catch (err) {
    container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 10px;">Failed to load critiques: ${escapeHtml(err.message)}</div>`;
  }
}

async function triggerSubconsciousDreamNow() {
  const btn = document.getElementById('btnMindDream');
  const notice = document.getElementById('mindActionNotice');
  if (btn) { btn.disabled = true; btn.textContent = '🌙 Dreaming...'; }
  if (notice) { notice.style.display = 'block'; notice.style.color = 'var(--accent-cyan)'; notice.textContent = 'Consolidating episodic logs & synthesizing subconscious wisdom...'; }

  try {
    const res = await fetch('/api/mind/dream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ max_activities: 200 }) });
    const data = await res.json();
    if (notice) {
      notice.style.color = 'var(--accent-green)';
      const insCount = data.insight?.insights_synthesized_count || (data.insight?.insights || []).length || 0;
      notice.textContent = `🌙 Dream cycle complete! Consolidated ${data.insight?.events_consolidated || 0} events and synthesized ${insCount} insights.`;
    }
    await loadFleetMindStatus();
    showSettingsToast('Subconscious memory consolidation complete', 'success');
  } catch (err) {
    if (notice) { notice.style.color = '#ef4444'; notice.textContent = 'Failed dream cycle: ' + err.message; }
    showSettingsToast('Dream cycle failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🌙 Dream Cycle'; }
  }
}

async function triggerSoulAuditNow() {
  const btn = document.getElementById('btnMindSoul');
  const notice = document.getElementById('mindActionNotice');
  if (btn) { btn.disabled = true; btn.textContent = '🧭 Auditing...'; }
  if (notice) { notice.style.display = 'block'; notice.style.color = '#c084fc'; notice.textContent = 'Auditing moral alignment against sovereign privacy, frugality & wellbeing tenets...'; }

  try {
    const res = await fetch('/api/mind/soul/audit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    const audit = data.audit || {};
    if (notice) {
      notice.style.color = audit.alignment_score >= 80 ? 'var(--accent-green)' : '#f59e0b';
      notice.textContent = `🧭 Soul Audit Complete: Score ${audit.alignment_score}/100 [${audit.status || 'PURE'}]. Violations: ${(audit.violations || []).length}.`;
    }
    await loadFleetMindStatus();
    showSettingsToast(`Soul alignment audited: ${audit.alignment_score}/100 [${audit.status}]`, 'success');
  } catch (err) {
    if (notice) { notice.style.color = '#ef4444'; notice.textContent = 'Failed soul audit: ' + err.message; }
    showSettingsToast('Soul audit failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🧭 Audit Soul'; }
  }
}

async function triggerSelfImproveNow() {
  const btn = document.getElementById('btnMindImprove');
  const notice = document.getElementById('mindActionNotice');
  if (btn) { btn.disabled = true; btn.textContent = '🌱 Evolving...'; }
  if (notice) { notice.style.display = 'block'; notice.style.color = 'var(--accent-green)'; notice.textContent = 'Executing evolutionary self-improvement cycle...'; }

  try {
    const res = await fetch('/api/mind/self_improve', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    if (notice) {
      notice.style.color = 'var(--accent-green)';
      notice.textContent = `🌱 Evolution cycle complete! Ascended to Gen ${data.generation || 1}. Applied ${(data.enhancements || []).length} systemic enhancements.`;
    }
    await loadFleetMindStatus();
    showSettingsToast(`Evolution generation complete (Gen ${data.generation || 1})`, 'success');
  } catch (err) {
    if (notice) { notice.style.color = '#ef4444'; notice.textContent = 'Evolution failed: ' + err.message; }
    showSettingsToast('Self-improvement failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🌱 Evolve Generation'; }
  }
}

async function triggerAutonomicHealNow() {
  const btn = document.getElementById('btnMindHeal');
  const notice = document.getElementById('mindActionNotice');
  if (btn) { btn.disabled = true; btn.textContent = '🩺 Healing...'; }
  if (notice) { notice.style.display = 'block'; notice.style.color = 'var(--accent-cyan)'; notice.textContent = 'Triggering autonomic self-healing reflex arc...'; }

  try {
    const res = await fetch('/api/mind/heal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
    const data = await res.json();
    if (notice) {
      notice.style.color = 'var(--accent-green)';
      notice.textContent = `🩺 Autonomic reflex complete: Health Score ${data.health_score || 100}%. Repairs applied: ${(data.auto_repairs_applied || []).length}.`;
    }
    await loadFleetMindStatus();
    showSettingsToast('Autonomic reflex completed successfully', 'success');
  } catch (err) {
    if (notice) { notice.style.color = '#ef4444'; notice.textContent = 'Autonomic heal failed: ' + err.message; }
    showSettingsToast('Autonomic heal failed: ' + err.message, 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🩺 Autonomic Heal'; }
  }
}

window.loadFleetMindStatus = loadFleetMindStatus;
window.loadMindInsights = loadMindInsights;
window.loadMindCritiques = loadMindCritiques;
window.triggerSubconsciousDreamNow = triggerSubconsciousDreamNow;
window.triggerSoulAuditNow = triggerSoulAuditNow;
window.triggerSelfImproveNow = triggerSelfImproveNow;
window.triggerAutonomicHealNow = triggerAutonomicHealNow;

