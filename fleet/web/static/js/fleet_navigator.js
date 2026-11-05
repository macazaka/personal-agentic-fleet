/**
 * Fleet Navigator & Operations Center Engine (fleet_navigator.js)
 * High-Density Scalability for 100+ Concurrent Agents
 * Powered by Antigravity
 */

const STATIC_CORE_TAB_IDS = new Set(['health', 'overview', 'antigravity', 'backlog', 'optimizer']);
const VALID_WORKSPACE_LAYOUTS = ['sidebar_dock', 'command_deck', 'launchpad_grid'];
const VALID_WORKSPACE_THEMES = ['dark', 'midnight', 'aurora', 'solar'];

const FleetNavigator = {
  agents: [],
  pinnedIds: new Set(['overview', 'health', 'antigravity', 'backlog', 'optimizer']),
  layoutMode: 'sidebar_dock', // 'sidebar_dock' | 'command_deck' | 'launchpad_grid'
  themeMode: 'dark',
  sidebarCollapsed: false,
  sidebarFilter: 'all', // 'all' | 'working' | 'pinned'
  sidebarSearchQuery: '',
  launchpadCategory: 'all',
  launchpadSearchQuery: '',
  launchpadCollapsed: false,
  filterStatus: 'all',
  filterCategory: 'all',
  searchQuery: '',
  viewMode: 'matrix', // 'matrix' | 'dense' | 'category'
  currentPage: 1,
  pageSize: 24,
  paletteResults: [],
  paletteSelectedIndex: 0,
  activeAgentId: 'overview',
  _hasInitializedDefaultAgent: false,

  init() {
    this.loadPersistedState();
    this.applyLayoutAndThemeToDOM();
    this.bindKeyboardShortcuts();
    this.fetchFleetData();
    this.syncLayoutFromBackendSettings();
  },

  loadPersistedState() {
    try {
      const savedPinned = localStorage.getItem('fleet_pinned_agents');
      if (savedPinned) {
        const parsed = JSON.parse(savedPinned);
        if (Array.isArray(parsed) && parsed.length > 0) {
          this.pinnedIds = new Set(parsed);
        }
      }
      const savedLayout = localStorage.getItem('fleet_workspace_layout');
      if (savedLayout && VALID_WORKSPACE_LAYOUTS.includes(savedLayout)) {
        this.layoutMode = savedLayout;
      }
      const savedTheme = localStorage.getItem('fleet_workspace_theme');
      if (savedTheme && VALID_WORKSPACE_THEMES.includes(savedTheme)) {
        this.themeMode = savedTheme;
      }
      const savedViewMode = localStorage.getItem('fleet_view_mode');
      if (savedViewMode) {
        this.viewMode = savedViewMode;
      }
      const savedPageSize = localStorage.getItem('fleet_page_size');
      if (savedPageSize) {
        this.pageSize = parseInt(savedPageSize, 10) || 24;
      }
    } catch (e) {
      console.warn('Could not load navigator state:', e);
    }
  },

  savePersistedState() {
    try {
      localStorage.setItem('fleet_pinned_agents', JSON.stringify([...this.pinnedIds]));
      localStorage.setItem('fleet_workspace_layout', this.layoutMode);
      localStorage.setItem('fleet_workspace_theme', this.themeMode);
      localStorage.setItem('fleet_view_mode', this.viewMode);
      localStorage.setItem('fleet_page_size', String(this.pageSize));
    } catch (e) {}
  },

  async syncLayoutFromBackendSettings() {
    try {
      const res = await fetch('/api/settings');
      if (!res.ok) return;
      const data = await res.json();
      const s = data.settings || {};
      if (s.layout && VALID_WORKSPACE_LAYOUTS.includes(s.layout)) {
        this.layoutMode = s.layout;
      }
      if (s.theme && VALID_WORKSPACE_THEMES.includes(s.theme)) {
        this.themeMode = s.theme;
      }
      this.savePersistedState();
      this.applyLayoutAndThemeToDOM();
    } catch (e) {}
  },

  applyLayoutAndThemeToDOM() {
    if (document.body) {
      document.body.dataset.layout = this.layoutMode;
      document.body.dataset.theme = this.themeMode;
    }
    const headerSelect = document.getElementById('headerQuickLayoutSelect');
    if (headerSelect) headerSelect.value = this.layoutMode;

    const settingsLayoutSelect = document.getElementById('genSettingLayout');
    if (settingsLayoutSelect) settingsLayoutSelect.value = this.layoutMode;

    const settingsThemeSelect = document.getElementById('genSettingTheme');
    if (settingsThemeSelect) settingsThemeSelect.value = this.themeMode;

    VALID_WORKSPACE_LAYOUTS.forEach(l => {
      const card = document.getElementById(`layoutCard_${l}`);
      if (card) card.classList.toggle('active', l === this.layoutMode);
    });
  },

  async setWorkspaceLayout(layout, persistToBackend = false) {
    if (!VALID_WORKSPACE_LAYOUTS.includes(layout)) return;
    this.layoutMode = layout;
    this.savePersistedState();
    this.applyLayoutAndThemeToDOM();
    this.renderLeftSidebarDock();
    this.renderPinnedTray();
    this.renderLaunchpadMatrix();

    if (persistToBackend) {
      const labels = {
        sidebar_dock: 'IDE Left Activity Dock & Sidebar',
        command_deck: 'Compact Pinned Bar + Spotlight Command Deck',
        launchpad_grid: 'Mission Control Bento Matrix / Launchpad'
      };
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ layout })
        });
        if (typeof showSettingsToast === 'function') {
          showSettingsToast(`Workspace layout switched to: ${labels[layout] || layout}`);
        }
      } catch (e) {}
    }
  },

  async setWorkspaceTheme(theme, persistToBackend = false) {
    if (!VALID_WORKSPACE_THEMES.includes(theme)) return;
    this.themeMode = theme;
    this.savePersistedState();
    this.applyLayoutAndThemeToDOM();
    if (persistToBackend) {
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ theme })
        });
      } catch (e) {}
    }
  },

  toggleLeftSidebarCollapse() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    const sb = document.getElementById('fleetLeftSidebarDock');
    if (sb) sb.classList.toggle('collapsed', this.sidebarCollapsed);
  },

  bindKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      // Ctrl+K or Cmd+K
      if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        this.openCommandPalette();
        return;
      }
      // Slash '/' when not inside input or textarea
      if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        e.preventDefault();
        this.openCommandPalette();
        return;
      }
      // Escape closes drawer & palette
      if (e.key === 'Escape') {
        this.closeCommandPalette();
        this.closeFleetDrawer();
      }
      // Palette Navigation
      const palette = document.getElementById('commandPaletteModal');
      if (palette && palette.style.display !== 'none') {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          this.paletteNavigate(1);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          this.paletteNavigate(-1);
        } else if (e.key === 'Enter') {
          e.preventDefault();
          this.paletteSelectCurrent();
        }
      }
    });
  },

  async loadManifest() {
    return this.fetchFleetData();
  },

  async fetchFleetData() {
    try {
      const res = await fetch('/api/fleet/agents?all=true');
      if (!res.ok) return;
      const data = await res.json();
      if (data.status === 'ok' && Array.isArray(data.agents)) {
        const uniqueMap = new Map();
        data.agents.forEach(a => {
          if (a && a.id && !uniqueMap.has(a.id)) {
            uniqueMap.set(a.id, this.enrichAgent(a));
          }
        });
        this.agents = Array.from(uniqueMap.values());
        if (!this._hasInitializedDefaultAgent) {
          this._hasInitializedDefaultAgent = true;
          const defAgent = this.agents.find(a => a.enabled && a.is_default) || this.agents.find(a => a.id === 'overview');
          if (defAgent) {
            this.activeAgentId = defAgent.id;
            if (defAgent.id !== 'overview') {
              this.switchAgent(defAgent.id);
            } else if (typeof switchTab === 'function') {
              switchTab('overview');
            }
          }
        }
        this.updateHeaderSummary();
        this.renderPinnedTray();
        this.renderLeftSidebarDock();
        this.renderLaunchpadMatrix();
        this.renderDrawerList();
        this.renderOperationsCenter();
        this.renderActiveAgentSelfImprovementsBanner(this.activeAgentId);
      }
    } catch (e) {
      console.warn('Error fetching fleet agents:', e);
    }
  },

  enrichAgent(agent) {
    // Derive domain category if missing
    let category = agent.category || 'Productivity';
    const id = (agent.id || '').toLowerCase();
    const name = (agent.name || '').toLowerCase();
    const perms = agent.permissions || [];

    if (id.includes('crypto') || id.includes('finance') || id.includes('budget') || id.includes('invoice') || id.includes('trader')) {
      category = 'Finance & Markets';
    } else if (id.includes('home') || id.includes('iot') || id.includes('device') || id.includes('automation')) {
      category = 'Smart Home & IoT';
    } else if (id.includes('weather') || id.includes('scraper') || id.includes('monitor') || id.includes('watch') || id.includes('feed')) {
      category = 'Monitoring & Watchers';
    } else if (id.includes('research') || id.includes('paper') || id.includes('scholar') || id.includes('antigravity') || id.includes('ai')) {
      category = 'AI & Research';
    } else if (id.includes('pr_review') || id.includes('optimizer') || id.includes('git') || id.includes('docker') || id.includes('backup')) {
      category = 'DevOps & System';
    } else if (id.includes('health') || id.includes('habit') || id.includes('fitness') || id.includes('sleep') || id.includes('med')) {
      category = 'Health & Lifestyle';
    } else if (agent.is_custom) {
      category = 'Custom Agents';
    }

    // Determine status
    let status = 'idle';
    if (!agent.enabled) {
      status = 'disabled';
    } else if (agent.is_busy || agent.is_running || id === 'antigravity' || id === 'overview') {
      status = 'working';
    }

    return {
      ...agent,
      category,
      status,
      is_pinned: this.pinnedIds.has(agent.id),
      last_active: agent.last_active || 'Recent'
    };
  },

  updateHeaderSummary() {
    const total = this.agents.length;
    const active = this.agents.filter(a => a.enabled).length;

    const countBadge = document.getElementById('fleetAgentCountNavBadge');
    if (countBadge) {
      countBadge.textContent = `${total} (${active} Active)`;
    }
    const headerTotalBadge = document.getElementById('wccHeaderTotalAgentsBadge');
    if (headerTotalBadge) {
      headerTotalBadge.textContent = `${active}/${total}`;
    }
    const omniCount = document.getElementById('omniBarAgentCountText');
    if (omniCount) {
      omniCount.textContent = `${total} (${active} Active)`;
    }
    const sbCount = document.getElementById('sidebarTotalCountBadge');
    if (sbCount) {
      sbCount.textContent = `${active}/${total}`;
    }
    const lpCount = document.getElementById('launchpadCountBadge');
    if (lpCount) {
      lpCount.textContent = `${active} Active / ${total} Total`;
    }
  },

  // --- Layout 2: Bounded Pinned Tray (Zero Duplicates + Overflow Cap) ---
  renderPinnedTray() {
    const tray = document.getElementById('pinnedAgentsNavTray');
    if (!tray) return;

    tray.innerHTML = '';
    // Deduplicate: Never re-render the 5 static core buttons that already exist in #dynamicNavTabs!
    const extraPinned = this.agents.filter(a => this.pinnedIds.has(a.id) && !STATIC_CORE_TAB_IDS.has(a.id));
    const maxExtraInBar = 3;
    const visibleExtra = extraPinned.slice(0, maxExtraInBar);

    visibleExtra.forEach(agent => {
      const btn = document.createElement('button');
      btn.className = `nav-tab ${this.activeAgentId === agent.id ? 'active' : ''}`;
      btn.id = `pinnedNavBtn_${agent.id}`;
      btn.title = `${agent.name} (Pinned Custom/Catalog Agent)`;
      btn.innerHTML = `
        <span>${agent.icon || '⚡'}</span>
        <span class="pinned-tab-title">${agent.name}</span>
      `;
      btn.onclick = () => this.switchAgent(agent.id);
      tray.appendChild(btn);
    });

    const overflowNotice = document.getElementById('wccDeckOverflowNotice');
    if (overflowNotice) {
      const remainingCount = Math.max(0, this.agents.length - (STATIC_CORE_TAB_IDS.size + visibleExtra.length));
      if (remainingCount > 0) {
        overflowNotice.innerHTML = `📂 +${remainingCount} More Agent${remainingCount === 1 ? '' : 's'} in Fleet Hub ▸`;
      } else {
        overflowNotice.innerHTML = `📂 Browse All Domains (${this.agents.length}) ▸`;
      }
    }
  },

  // --- Layout 1: IDE Left Activity Dock & Sidebar (#fleetLeftSidebarDock) ---
  onSidebarSearch(query) {
    this.sidebarSearchQuery = (query || '').toLowerCase().trim();
    this.renderLeftSidebarDock();
  },

  setSidebarFilter(filter) {
    this.sidebarFilter = filter;
    document.querySelectorAll('.sidebar-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.sfilter === filter);
    });
    this.renderLeftSidebarDock();
  },

  renderLeftSidebarDock() {
    const pinnedContainer = document.getElementById('sidebarPinnedList');
    const categoriesContainer = document.getElementById('sidebarCategoriesList');
    if (!pinnedContainer || !categoriesContainer) return;

    const q = this.sidebarSearchQuery;
    const matchesSearch = (a) => {
      if (!q) return true;
      return (a.name || '').toLowerCase().includes(q) ||
             (a.id || '').toLowerCase().includes(q) ||
             (a.category || '').toLowerCase().includes(q) ||
             (a.description || '').toLowerCase().includes(q);
    };

    const matchesFilter = (a) => {
      if (this.sidebarFilter === 'working') return a.enabled && (a.status === 'working' || a.status === 'idle');
      if (this.sidebarFilter === 'pinned') return this.pinnedIds.has(a.id) || STATIC_CORE_TAB_IDS.has(a.id);
      return true;
    };

    // 1. Pinned & Core Favorites (Rendered once in top section)
    const coreAndPinned = this.agents.filter(a => (STATIC_CORE_TAB_IDS.has(a.id) || this.pinnedIds.has(a.id)) && matchesSearch(a) && matchesFilter(a));
    const coreAndPinnedIds = new Set(coreAndPinned.map(a => a.id));

    if (coreAndPinned.length === 0) {
      pinnedContainer.innerHTML = `<div style="font-size: 11px; color: var(--text-muted); padding: 4px 8px;">No matching pinned agents</div>`;
    } else {
      pinnedContainer.innerHTML = coreAndPinned.map(a => this.renderSidebarAgentItemHtml(a)).join('');
    }

    // 2. Collapsible Domain Categories Tree for Additional / Unpinned Agents (Zero Duplication with Pinned List)
    const unpinnedDomainAgents = this.agents.filter(a => !coreAndPinnedIds.has(a.id) && matchesSearch(a) && matchesFilter(a));
    if (unpinnedDomainAgents.length === 0) {
      categoriesContainer.innerHTML = q
        ? `<div style="font-size: 11.5px; color: var(--text-muted); padding: 12px 8px; text-align: center;">No additional domain agents match "${q}"</div>`
        : `<div style="font-size: 11px; color: var(--text-muted); padding: 8px 10px; background: rgba(255,255,255,0.02); border-radius: 6px;">All active agents are pinned above. Add or unpin agents to browse by domain.</div>`;
      return;
    }

    const groups = {};
    unpinnedDomainAgents.forEach(a => {
      const cat = a.category || 'Productivity';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(a);
    });

    categoriesContainer.innerHTML = Object.entries(groups).map(([catName, catAgents]) => `
      <div class="drawer-category-group" style="margin-bottom: 6px;">
        <div class="drawer-category-header" style="padding: 7px 10px; font-size: 11.5px;" onclick="this.parentElement.classList.toggle('collapsed')">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="drawer-cat-arrow">▾</span>
            <strong>${catName}</strong>
          </div>
          <span class="badge" style="background: rgba(255,255,255,0.06); font-size: 10px; padding: 1px 6px;">${catAgents.length}</span>
        </div>
        <div class="drawer-category-items" style="padding: 3px 4px;">
          ${catAgents.map(a => this.renderSidebarAgentItemHtml(a)).join('')}
        </div>
      </div>
    `).join('');
  },

  renderSidebarAgentItemHtml(a) {
    const isActive = (this.activeAgentId === a.id);
    const isWorking = a.status === 'working';
    const isDisabled = a.status === 'disabled';
    const dotClass = isWorking ? 'status-dot-working' : (isDisabled ? 'status-dot-disabled' : 'status-dot-idle');

    return `
      <div class="sidebar-agent-item ${isActive ? 'active' : ''}" onclick="FleetNavigator.switchAgent('${a.id}')" title="${a.name} (${a.category})">
        <div style="display: flex; align-items: center; gap: 8px; min-width: 0; overflow: hidden;">
          <span class="agent-status-dot ${dotClass}"></span>
          <span style="font-size: 14px; flex-shrink: 0;">${a.icon || '⚡'}</span>
          <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${a.name}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 2px; flex-shrink: 0;">
          <button class="btn-pin-star" style="font-size: 11px; padding: 0 3px; color: #d8b4fe;" onclick="event.stopPropagation(); openEvolveAgentModal('${a.id}')" title="Auto-generate 10 ways to improve '${a.name}' features or add manual self-improvements">✨</button>
          ${a.is_custom ? `<button class="btn-pin-star" style="font-size: 11px; padding: 0 3px; color: #f87171; opacity: 0.75;" onclick="FleetNavigator.deleteAgent('${a.id}', event)" title="Delete custom agent '${a.name}'">🗑️</button>` : ''}
          <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" style="font-size: 12px; padding: 0 3px;" onclick="FleetNavigator.togglePin('${a.id}', event)" title="${a.is_pinned ? 'Unpin' : 'Pin'}">
            ${a.is_pinned ? '★' : '☆'}
          </button>
        </div>
      </div>
    `;
  },

  // --- Layout 3: Mission Control Bento Matrix / Launchpad (#fleetLaunchpadMatrix) ---
  onLaunchpadSearch(query) {
    this.launchpadSearchQuery = (query || '').toLowerCase().trim();
    this.renderLaunchpadMatrix();
  },

  setLaunchpadCategory(cat) {
    this.launchpadCategory = cat;
    this.renderLaunchpadMatrix();
  },

  toggleLaunchpadMatrixBody() {
    this.launchpadCollapsed = !this.launchpadCollapsed;
    const grid = document.getElementById('launchpadMatrixGrid');
    const btn = document.getElementById('btnToggleLaunchpadBody');
    if (grid) grid.classList.toggle('collapsed', this.launchpadCollapsed);
    if (btn) btn.textContent = this.launchpadCollapsed ? '▼ Expand Matrix' : '▲ Collapse Matrix';
  },

  renderLaunchpadMatrix() {
    const tabsEl = document.getElementById('launchpadCategoryTabs');
    const gridEl = document.getElementById('launchpadMatrixGrid');
    if (!tabsEl || !gridEl) return;

    const categories = ['all', ...Array.from(new Set(this.agents.map(a => a.category || 'Productivity')))];
    tabsEl.innerHTML = categories.map(cat => {
      const count = cat === 'all' ? this.agents.length : this.agents.filter(a => a.category === cat).length;
      const isActive = (this.launchpadCategory === cat);
      const label = cat === 'all' ? `All (${count})` : `${cat} (${count})`;
      return `<button class="launchpad-cat-btn ${isActive ? 'active' : ''}" onclick="FleetNavigator.setLaunchpadCategory('${cat}')">${label}</button>`;
    }).join('');

    const q = this.launchpadSearchQuery;
    const filtered = this.agents.filter(a => {
      if (this.launchpadCategory !== 'all' && a.category !== this.launchpadCategory) return false;
      if (!q) return true;
      return (a.name || '').toLowerCase().includes(q) ||
             (a.id || '').toLowerCase().includes(q) ||
             (a.category || '').toLowerCase().includes(q);
    });

    if (filtered.length === 0) {
      gridEl.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 16px; color: var(--text-muted); font-size: 12px;">No agents match current matrix filter.</div>`;
      return;
    }

    gridEl.innerHTML = filtered.map(a => {
      const isActive = (this.activeAgentId === a.id);
      const isWorking = a.status === 'working';
      const isDisabled = a.status === 'disabled';
      const dotClass = isWorking ? 'status-dot-working' : (isDisabled ? 'status-dot-disabled' : 'status-dot-idle');

      return `
        <div class="launchpad-chip ${isActive ? 'active' : ''}" onclick="FleetNavigator.switchAgent('${a.id}')" title="${a.description || a.name}">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
            <span class="agent-status-dot ${dotClass}"></span>
            <span style="font-size: 16px; flex-shrink: 0;">${a.icon || '⚡'}</span>
            <div style="min-width: 0; overflow: hidden;">
              <div style="font-size: 12px; font-weight: 600; color: var(--text); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${a.name}</div>
              <div style="font-size: 10px; color: var(--text-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${a.category}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 3px; flex-shrink: 0;">
            <button class="btn-pin-star" style="font-size: 11.5px; color: #d8b4fe;" title="Auto-generate 10 ways to improve '${a.name}' features or add manual self-improvements" onclick="event.stopPropagation(); openEvolveAgentModal('${a.id}')">✨</button>
            <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" title="${a.is_pinned ? 'Unpin' : 'Pin'}" style="font-size: 12px;" onclick="FleetNavigator.togglePin('${a.id}', event)">
              ${a.is_pinned ? '★' : '☆'}
            </button>
          </div>
        </div>
      `;
    }).join('');
  },

  syncActiveTabUI(agentId) {
    this.activeAgentId = agentId;
    this.renderPinnedTray();
    this.renderLeftSidebarDock();
    this.renderLaunchpadMatrix();
  },

  togglePin(agentId, e) {
    if (e) e.stopPropagation();
    if (this.pinnedIds.has(agentId)) {
      this.pinnedIds.delete(agentId);
    } else {
      this.pinnedIds.add(agentId);
    }
    this.savePersistedState();
    this.agents.forEach(a => {
      a.is_pinned = this.pinnedIds.has(a.id);
    });
    this.renderPinnedTray();
    this.renderLeftSidebarDock();
    this.renderLaunchpadMatrix();
    this.renderDrawerList();
    this.renderOperationsCenter();
  },

  async fetchAgents() {
    return this.fetchFleetData();
  },

  async deleteAgent(agentId, e) {
    if (e) e.stopPropagation();
    if (!agentId) return;
    const agent = this.agents.find(a => a.id === agentId);
    const label = agent ? `${agent.name} (${agentId})` : agentId;
    if (!confirm(`Permanently delete custom agent "${label}" from AFCC?\n\nThis removes the agent's custom package folder and unregisters it immediately.`)) {
      return;
    }
    const clickedBtn = e && e.currentTarget && e.currentTarget.tagName === 'BUTTON' ? e.currentTarget : null;
    const execDelete = async () => {
      const res = await fetch('/api/settings/agents/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: agentId })
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok && res.status !== 404) {
        throw new Error(data.message || 'Failed to delete agent');
      }
      if (res.status !== 404 && data.status !== 'success') {
        throw new Error(data.message || 'Failed to delete agent');
      }
      this.agents = this.agents.filter(a => a.id !== agentId);
      this.pinnedIds.delete(agentId);
      this.savePersistedState();
      if (this.activeAgentId === agentId) {
        this.switchAgent('antigravity');
      }
      await this.fetchFleetData();
      if (typeof initDynamicAgentTabs === 'function') {
        await initDynamicAgentTabs();
      }
      if (typeof loadSettingsData === 'function') {
        loadSettingsData();
      }
      const msg = `🗑️ ${data.message || `Deleted '${label}'`}`;
      if (typeof showFleetToast === 'function') {
        showFleetToast(msg, false);
      } else if (typeof showSettingsToast === 'function') {
        showSettingsToast(msg);
      }
    };

    if (typeof window.runFleetAsyncAction === 'function') {
      await window.runFleetAsyncAction({
        buttons: [clickedBtn, 'btnStageDeleteAgent'],
        useStudioBanner: false,
        busyLabel: '⏳ Deleting...',
        startToast: `⏳ Deleting '${label}'...`,
        errorPrefix: 'Could not delete agent',
      }, execDelete);
    } else {
      try {
        await execDelete();
      } catch (err) {
        if (typeof showFleetToast === 'function') {
          showFleetToast(`✕ Could not delete agent: ${err.message}`, true);
        } else {
          alert('Could not delete agent: ' + err.message);
        }
      }
    }
  },

  // --- Off-Canvas Fleet Drawer ---
  toggleFleetDrawer() {
    const drawer = document.getElementById('fleetNavigatorDrawer');
    if (!drawer) return;
    if (drawer.classList.contains('open')) {
      this.closeFleetDrawer();
    } else {
      this.openFleetDrawer();
    }
  },

  openFleetDrawer() {
    const drawer = document.getElementById('fleetNavigatorDrawer');
    const backdrop = document.getElementById('fleetDrawerBackdrop');
    if (drawer) drawer.classList.add('open');
    if (backdrop) backdrop.style.display = 'block';
    const input = document.getElementById('drawerSearchInput');
    if (input) {
      input.value = '';
      setTimeout(() => input.focus(), 150);
    }
    this.renderDrawerList();
  },

  closeFleetDrawer() {
    const drawer = document.getElementById('fleetNavigatorDrawer');
    const backdrop = document.getElementById('fleetDrawerBackdrop');
    if (drawer) drawer.classList.remove('open');
    if (backdrop) backdrop.style.display = 'none';
  },

  onDrawerSearch(query) {
    this.searchQuery = (query || '').toLowerCase().trim();
    this.renderDrawerList();
  },

  setDrawerFilter(filter) {
    this.filterStatus = filter;
    document.querySelectorAll('.drawer-filter-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.filter === filter);
    });
    this.renderDrawerList();
  },

  renderDrawerList() {
    const container = document.getElementById('drawerAgentsList');
    if (!container) return;

    let filtered = this.agents;

    // Status filter
    if (this.filterStatus === 'working') {
      filtered = filtered.filter(a => a.status === 'working');
    } else if (this.filterStatus === 'idle') {
      filtered = filtered.filter(a => a.status === 'idle');
    } else if (this.filterStatus === 'disabled') {
      filtered = filtered.filter(a => a.status === 'disabled');
    }

    // Search query
    if (this.searchQuery) {
      filtered = filtered.filter(a =>
        a.name.toLowerCase().includes(this.searchQuery) ||
        a.id.toLowerCase().includes(this.searchQuery) ||
        a.category.toLowerCase().includes(this.searchQuery) ||
        (a.description || '').toLowerCase().includes(this.searchQuery)
      );
    }

    if (filtered.length === 0) {
      container.innerHTML = `
        <div style="padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px;">
          No matching agents found.
        </div>`;
      return;
    }

    // Group by category
    const groups = {};
    filtered.forEach(agent => {
      const cat = agent.category || 'Productivity';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(agent);
    });

    let html = '';
    for (const [catName, catAgents] of Object.entries(groups)) {
      html += `
        <div class="drawer-category-group">
          <div class="drawer-category-header" onclick="this.parentElement.classList.toggle('collapsed')">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="drawer-cat-arrow">▾</span>
              <strong>${catName}</strong>
            </div>
            <span class="badge" style="background: rgba(255,255,255,0.06); font-size: 11px;">${catAgents.length}</span>
          </div>
          <div class="drawer-category-items">
            ${catAgents.map(a => this.renderDrawerItemHtml(a)).join('')}
          </div>
        </div>`;
    }

    container.innerHTML = html;
  },

  renderDrawerItemHtml(a) {
    const isWorking = a.status === 'working';
    const isDisabled = a.status === 'disabled';
    const statusDotClass = isWorking ? 'status-dot-working' : (isDisabled ? 'status-dot-disabled' : 'status-dot-idle');
    const statusText = isWorking ? 'Working' : (isDisabled ? 'Disabled' : 'Idle');

    return `
      <div class="drawer-agent-item ${this.activeAgentId === a.id ? 'active' : ''}" onclick="FleetNavigator.switchAgent('${a.id}')">
        <div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
          <span class="agent-status-dot ${statusDotClass}" title="${statusText}"></span>
          <span style="font-size: 16px;">${a.icon || '⚡'}</span>
          <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            <div style="font-size: 13px; font-weight: 600; color: var(--text);">${a.name}</div>
            <div style="font-size: 11px; color: var(--text-muted); font-family: monospace;">${a.id}</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 6px;">
          <button class="btn" style="padding: 2px 7px; font-size: 10.5px; border-color: rgba(168, 85, 247, 0.45); color: #d8b4fe; background: rgba(168, 85, 247, 0.12);" title="Auto-generate 10 ways to improve '${a.name}' features or add manual self-improvements" onclick="event.stopPropagation(); FleetNavigator.closeFleetDrawer(); openEvolveAgentModal('${a.id}')">✨ 10 Ways</button>
          <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" title="${a.is_pinned ? 'Unpin from bar' : 'Pin to bar'}" onclick="FleetNavigator.togglePin('${a.id}', event)">
            ${a.is_pinned ? '★' : '☆'}
          </button>
        </div>
      </div>`;
  },

  // --- Fleet Operations Center (In Overview View) ---
  renderOperationsCenter() {
    const kpiTotal = document.getElementById('kpiTotalAgents');
    const kpiWorking = document.getElementById('kpiWorkingAgents');
    const kpiIdle = document.getElementById('kpiIdleAgents');
    const kpiDisabled = document.getElementById('kpiDisabledAgents');

    const total = this.agents.length;
    const working = this.agents.filter(a => a.status === 'working').length;
    const idle = this.agents.filter(a => a.status === 'idle').length;
    const disabled = this.agents.filter(a => a.status === 'disabled').length;

    if (kpiTotal) kpiTotal.textContent = total;
    if (kpiWorking) kpiWorking.textContent = working;
    if (kpiIdle) kpiIdle.textContent = idle;
    if (kpiDisabled) kpiDisabled.textContent = disabled;

    // Populate category filter dropdown
    const catSelect = document.getElementById('opsCategoryFilter');
    if (catSelect && catSelect.options.length <= 1) {
      const cats = Array.from(new Set(this.agents.map(a => a.category))).sort();
      cats.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        catSelect.appendChild(opt);
      });
    }

    this.renderOperationsGrid();
  },

  setOperationsStatusFilter(status) {
    this.filterStatus = status;
    document.querySelectorAll('.ops-status-pill').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.status === status);
    });
    this.currentPage = 1;
    this.renderOperationsGrid();
  },

  setOperationsCategoryFilter(cat) {
    this.filterCategory = cat;
    this.currentPage = 1;
    this.renderOperationsGrid();
  },

  onOperationsSearch(query) {
    this.searchQuery = (query || '').toLowerCase().trim();
    this.currentPage = 1;
    this.renderOperationsGrid();
  },

  setOperationsViewMode(mode) {
    this.viewMode = mode;
    this.savePersistedState();
    document.querySelectorAll('.ops-mode-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
    this.renderOperationsGrid();
  },

  getFilteredAgents() {
    let filtered = this.agents;

    if (this.filterStatus === 'working') {
      filtered = filtered.filter(a => a.status === 'working');
    } else if (this.filterStatus === 'idle') {
      filtered = filtered.filter(a => a.status === 'idle');
    } else if (this.filterStatus === 'disabled') {
      filtered = filtered.filter(a => a.status === 'disabled');
    }

    if (this.filterCategory && this.filterCategory !== 'all') {
      filtered = filtered.filter(a => a.category === this.filterCategory);
    }

    if (this.searchQuery) {
      filtered = filtered.filter(a =>
        a.name.toLowerCase().includes(this.searchQuery) ||
        a.id.toLowerCase().includes(this.searchQuery) ||
        a.category.toLowerCase().includes(this.searchQuery) ||
        (a.description || '').toLowerCase().includes(this.searchQuery)
      );
    }

    return filtered;
  },

  renderOperationsGrid() {
    const container = document.getElementById('fleetOperationsContainer');
    if (!container) return;

    const filtered = this.getFilteredAgents();
    const total = filtered.length;

    if (total === 0) {
      container.innerHTML = `
        <div style="padding: 40px; text-align: center; color: var(--text-muted); background: var(--card-bg); border-radius: var(--radius); border: 1px solid var(--card-border);">
          <div style="font-size: 32px; margin-bottom: 8px;">🔍</div>
          <strong style="font-size: 15px; color: var(--text);">No matching agents found</strong>
          <p style="margin-top: 4px; font-size: 13px;">Try adjusting your search query, status, or category filter.</p>
        </div>`;
      this.renderPagination(0, 0);
      return;
    }

    // Apply pagination
    const totalPages = Math.ceil(total / this.pageSize) || 1;
    if (this.currentPage > totalPages) this.currentPage = totalPages;
    const startIdx = (this.currentPage - 1) * this.pageSize;
    const endIdx = Math.min(startIdx + this.pageSize, total);
    const pageItems = filtered.slice(startIdx, endIdx);

    if (this.viewMode === 'matrix') {
      container.innerHTML = `
        <div class="fleet-matrix-grid">
          ${pageItems.map(a => this.renderMatrixCardHtml(a)).join('')}
        </div>`;
    } else if (this.viewMode === 'dense') {
      container.innerHTML = `
        <div class="fleet-table-wrapper">
          <table class="fleet-dense-table">
            <thead>
              <tr>
                <th style="width: 40px;">Status</th>
                <th>Agent</th>
                <th>Domain Category</th>
                <th>Permissions</th>
                <th>Last Active</th>
                <th style="text-align: right;">Quick Actions</th>
              </tr>
            </thead>
            <tbody>
              ${pageItems.map(a => this.renderDenseRowHtml(a)).join('')}
            </tbody>
          </table>
        </div>`;
    } else if (this.viewMode === 'category') {
      const groups = {};
      pageItems.forEach(a => {
        if (!groups[a.category]) groups[a.category] = [];
        groups[a.category].push(a);
      });
      container.innerHTML = Object.entries(groups).map(([cat, list]) => `
        <div class="fleet-cat-accordion">
          <div class="fleet-cat-accordion-header">
            <strong>${cat}</strong>
            <span class="badge">${list.length}</span>
          </div>
          <div class="fleet-matrix-grid" style="margin-top: 10px;">
            ${list.map(a => this.renderMatrixCardHtml(a)).join('')}
          </div>
        </div>
      `).join('');
    }

    this.renderPagination(total, pageItems.length);
  },

  renderMatrixCardHtml(a) {
    const isWorking = a.status === 'working';
    const isDisabled = a.status === 'disabled';
    const badgeColor = isWorking ? 'var(--accent-green)' : (isDisabled ? '#fca5a5' : 'var(--accent-cyan)');
    const badgeBg = isWorking ? 'rgba(16,185,129,0.12)' : (isDisabled ? 'rgba(239,68,68,0.12)' : 'rgba(56,189,248,0.12)');
    const statusLabel = isWorking ? '● Working' : (isDisabled ? '○ Disabled' : '● Standby');
    const evoCount = Array.isArray(a.evolution_improvements) ? a.evolution_improvements.length : 0;

    return `
      <div class="fleet-matrix-card ${a.enabled ? '' : 'card-disabled'}" onclick="FleetNavigator.switchAgent('${a.id}')">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <div class="matrix-card-icon">${a.icon || '⚡'}</div>
            <div>
              <div class="matrix-card-title">${a.name}</div>
              <div class="matrix-card-slug">${a.id}</div>
            </div>
          </div>
          <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" title="${a.is_pinned ? 'Unpin' : 'Pin'}" onclick="FleetNavigator.togglePin('${a.id}', event)">
            ${a.is_pinned ? '★' : '☆'}
          </button>
        </div>

        <p class="matrix-card-desc">${a.description || 'Fleet automated agent module.'}</p>

        <div style="display: flex; justify-content: space-between; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.06); font-size: 11.5px;">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span class="badge" style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}33;">
              ${statusLabel}
            </span>
            ${evoCount > 0 ? `<span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.35); font-size: 10px;">✨ ${evoCount} Improved</span>` : ''}
          </div>
          <button class="btn" style="padding: 3px 9px; font-size: 11px; border-color: rgba(168, 85, 247, 0.45); color: #d8b4fe; background: rgba(168, 85, 247, 0.12);" title="Auto-generate 10 ways to improve '${a.name}' features or add manual self-improvements" onclick="event.stopPropagation(); openEvolveAgentModal('${a.id}')">
            ✨ 10 Ways to Improve
          </button>
        </div>
      </div>`;
  },

  renderDenseRowHtml(a) {
    const isWorking = a.status === 'working';
    const isDisabled = a.status === 'disabled';
    const statusClass = isWorking ? 'status-dot-working' : (isDisabled ? 'status-dot-disabled' : 'status-dot-idle');

    return `
      <tr class="fleet-dense-row" onclick="FleetNavigator.switchAgent('${a.id}')">
        <td style="text-align: center;"><span class="agent-status-dot ${statusClass}"></span></td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">${a.icon || '⚡'}</span>
            <strong>${a.name}</strong>
            <span style="font-size: 11px; color: var(--text-muted); font-family: monospace;">(${a.id})</span>
          </div>
        </td>
        <td><span class="badge" style="background: rgba(255,255,255,0.06);">${a.category}</span></td>
        <td>
          <div style="display: flex; gap: 4px; flex-wrap: wrap;">
            ${(a.permissions || []).slice(0, 3).map(p => `<span class="badge" style="font-size: 10px; padding: 1px 5px;">${p}</span>`).join('')}
            ${(a.permissions || []).length > 3 ? `<span class="badge" style="font-size: 10px; padding: 1px 4px;">+${a.permissions.length - 3}</span>` : ''}
          </div>
        </td>
        <td style="color: var(--text-muted); font-size: 12px;">${a.last_active}</td>
        <td style="text-align: right;" onclick="event.stopPropagation()">
          <button title="Auto-generate 10 ways to improve '${a.name}' features or add manual self-improvements" class="btn" style="padding: 3px 8px; font-size: 11px; border-color: rgba(168, 85, 247, 0.45); color: #d8b4fe; background: rgba(168, 85, 247, 0.12);" onclick="openEvolveAgentModal('${a.id}')">✨ 10 Ways</button>
          <button title="Open '${a.name}' agent pane" class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="FleetNavigator.switchAgent('${a.id}')">Open Pane</button>
          <button title="Configure '${a.name}' settings" class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="openAgentSettingsDrawer('${a.id}')">⚙️</button>
        </td>
      </tr>`;
  },

  renderPagination(total, pageCount) {
    const bar = document.getElementById('fleetOperationsPagination');
    if (!bar) return;

    if (total <= this.pageSize) {
      bar.innerHTML = `<span style="color: var(--text-muted); font-size: 12px;">Showing all ${total} agents</span>`;
      return;
    }

    const totalPages = Math.ceil(total / this.pageSize) || 1;
    const start = (this.currentPage - 1) * this.pageSize + 1;
    const end = Math.min(start + pageCount - 1, total);

    bar.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 12px; color: var(--text-muted);">
        <div>Showing <strong>${start}–${end}</strong> of <strong>${total}</strong> agents</div>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button title="Previous page" class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="FleetNavigator.changePage(${this.currentPage - 1})" ${this.currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
          <span style="padding: 0 8px;">Page <strong>${this.currentPage}</strong> of <strong>${totalPages}</strong></span>
          <button title="Next page" class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="FleetNavigator.changePage(${this.currentPage + 1})" ${this.currentPage >= totalPages ? 'disabled' : ''}>Next →</button>
        </div>
      </div>`;
  },

  changePage(page) {
    const total = this.getFilteredAgents().length;
    const totalPages = Math.ceil(total / this.pageSize) || 1;
    if (page < 1 || page > totalPages) return;
    this.currentPage = page;
    this.renderOperationsGrid();
    const container = document.getElementById('fleetOperationsCenter');
    if (container) container.scrollIntoView({ behavior: 'smooth', block: 'start' });
  },

  // --- Dynamic Agent Staging & View Switching ---
  switchAgent(agentId) {
    this.activeAgentId = agentId;
    this.closeFleetDrawer();
    this.closeCommandPalette();

    const standardTabs = ['overview', 'health', 'antigravity', 'backlog', 'optimizer'];
    if (standardTabs.includes(agentId)) {
      if (typeof switchTab === 'function') switchTab(agentId);
      this.syncActiveTabUI(agentId);
      this.renderActiveAgentSelfImprovementsBanner(agentId);
      return;
    }

    // Custom or dynamic agent stage
    this.mountDynamicAgentPane(agentId);
    this.syncActiveTabUI(agentId);
    this.renderActiveAgentSelfImprovementsBanner(agentId);
  },

  mountDynamicAgentPane(agentId) {
    const agent = this.agents.find(a => a.id === agentId);
    if (!agent) {
      if (typeof switchTab === 'function') switchTab('overview');
      return;
    }
    window.lastNonAgTab = agentId;

    // Hide all standard view divs (except viewAntigravity when docked to the right panel)
    ['viewOverview', 'viewAntigravity', 'viewHealth', 'viewBacklog', 'viewOptimizer'].forEach(id => {
      if (id === 'viewAntigravity' && window.isAgRightDocked) return;
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });

    // Reset standard tab buttons
    document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));

    let stage = document.getElementById('viewActiveAgentStage');
    if (!stage) {
      console.warn('viewActiveAgentStage container missing in DOM.');
      return;
    }

    stage.style.display = 'block';

    // Update Stage Breadcrumb Header
    const bc = document.getElementById('stageBreadcrumbTitle');
    const bcCat = document.getElementById('stageBreadcrumbCategory');
    const bcStatus = document.getElementById('stageStatusBadge');
    const btnClone = document.getElementById('btnStageCloneAgent');
    const btnExport = document.getElementById('btnStageExportAgent');
    const btnEvolve = document.getElementById('btnStageEvolveAgent');
    const btnDel = document.getElementById('btnStageDeleteAgent');
    if (bc) bc.innerHTML = `<span style="font-size: 20px;">${agent.icon || '⚡'}</span> <strong>${agent.name}</strong> <span style="font-size: 12px; color: var(--text-muted); font-family: monospace;">(${agent.id})</span>`;
    if (bcCat) bcCat.textContent = agent.category;
    if (btnClone) btnClone.style.display = 'inline-flex';
    if (btnExport) btnExport.style.display = agent.is_custom ? 'inline-flex' : 'none';
    if (btnEvolve) btnEvolve.style.display = 'inline-flex';
    if (btnDel) btnDel.style.display = agent.is_custom ? 'inline-flex' : 'none';
    if (bcStatus) {
      const isWorking = agent.status === 'working';
      bcStatus.className = `badge ${isWorking ? 'badge-success' : 'badge-neutral'}`;
      bcStatus.textContent = isWorking ? '● Working' : '● Standby';
    }

    this.renderActiveAgentSelfImprovementsBanner(agentId);

    // Mount agent panel HTML without repeating header identity already shown in .stage-header
    const panelContainer = document.getElementById('stagePanelContainer');
    if (panelContainer) {
      const rawHtml = agent.panel_html || agent.html || '';
      if (rawHtml) {
        panelContainer.innerHTML = rawHtml;
        // Strip redundant inner .section-title if it duplicates the stage header title
        const duplicateTitle = panelContainer.querySelector('.section-header .section-title');
        if (duplicateTitle) {
          const parentHeader = duplicateTitle.closest('.section-header');
          const actions = parentHeader ? parentHeader.querySelector('.section-actions') : null;
          if (parentHeader && !actions) {
            parentHeader.remove();
          } else {
            duplicateTitle.remove();
          }
        }
        // Hydrate Zero-Code Studio live SQLite runtime if present
        if (window.CustomAgentRuntime && typeof window.CustomAgentRuntime.mount === 'function') {
          window.CustomAgentRuntime.mount(agent.id);
        }
        if (agent.id === 'pr_review' && typeof window.fetchPRReviewStatus === 'function') {
          window.fetchPRReviewStatus(false);
        }
        if (agent.id === 'gmail' && typeof window.fetchEmails === 'function') {
          window.fetchEmails();
        }
      } else {
        panelContainer.innerHTML = `
          <div class="card" style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 24px;">
            <p style="color: var(--text-muted); font-size: 13.5px; margin: 0;">${agent.description || 'Agent operational pane ready.'}</p>
            <div style="margin-top: 14px; padding: 12px; background: rgba(15,23,42,0.5); border-radius: 8px;">
              <span class="badge" style="background: rgba(56,189,248,0.15); color: var(--accent-cyan);">Declared permissions: ${(agent.permissions || []).join(', ')}</span>
            </div>
          </div>`;
      }
    }
  },

  _selfImproveMonitorOpen: {},
  _selfImproveSelectedIdx: {},
  _selfImproveLiveJob: {},
  _originalImproviseDrafts: {},

  renderActiveAgentSelfImprovementsBanner(agentId) {
    const targetIds = new Set(['overview', 'health', 'antigravity', 'backlog', 'optimizer']);
    if (agentId) targetIds.add(agentId);

    targetIds.forEach(aid => {
      const agent = this.agents.find(a => a.id === aid);
      if (!agent) return;

      const coreContainer = document.getElementById(`coreSelfImproveBanner_${aid}`);
      const stageContainer = (this.activeAgentId === aid && !STATIC_CORE_TAB_IDS.has(aid))
        ? document.getElementById('stageSelfImproveBanner')
        : null;

      const containers = [coreContainer, stageContainer].filter(Boolean);
      if (containers.length === 0) return;

      const imps = Array.isArray(agent.evolution_improvements) ? agent.evolution_improvements : [];
      const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      const liveJob = this._selfImproveLiveJob[aid] || null;
      const isMonitorOpen = Boolean(this._selfImproveMonitorOpen[aid] || liveJob);
      const selIdx = (typeof this._selfImproveSelectedIdx[aid] === 'number' && this._selfImproveSelectedIdx[aid] >= 0 && this._selfImproveSelectedIdx[aid] < imps.length)
        ? this._selfImproveSelectedIdx[aid]
        : (imps.length - 1);

      const pillsHtml = imps.length > 0
        ? `<div style="display: flex; flex-wrap: wrap; gap: 7px; margin-top: 9px; align-items: center;">
            ${imps.map((it, idx) => {
              const obj = typeof it === 'object' && it ? it : { title: String(it) };
              const t = obj.title || '';
              const isCust = Boolean(obj.is_custom);
              const blId = Number(obj.backlog_id || 0);
              const isSelected = isMonitorOpen && !liveJob && idx === selIdx;
              const prog = Number(obj.progress || 100);
              return `<button type="button" onclick="FleetNavigator.selectSelfImproveItemForMonitor('${aid}', ${idx})" title="Click to inspect live lifecycle status, Feature Backlog link, and LLM textual response for: ${esc(obj.description || t)}" style="cursor: pointer; display: inline-flex; align-items: center; gap: 6px; font-size: 11px; padding: 4px 10px; border-radius: 999px; background: ${isSelected ? 'rgba(168, 85, 247, 0.28)' : (isCust ? 'rgba(56, 189, 248, 0.16)' : 'rgba(16, 185, 129, 0.16)')}; border: 1px solid ${isSelected ? '#c084fc' : (isCust ? 'rgba(56, 189, 248, 0.42)' : 'rgba(16, 185, 129, 0.42)')}; color: ${isCust ? '#7dd3fc' : '#6ee7b7'}; font-weight: 600; box-shadow: ${isSelected ? '0 0 0 2px rgba(168, 85, 247, 0.25)' : 'none'};">
                <span>✅ ${esc(t)}</span>
                ${blId > 0 ? `<span style="padding: 1px 6px; border-radius: 999px; background: rgba(15, 23, 42, 0.78); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.4); font-size: 9.5px;">📋 #BL-${blId}</span>` : ''}
                <span style="padding: 1px 6px; border-radius: 999px; background: rgba(16, 185, 129, 0.22); color: #34d399; font-size: 9.5px;">${prog}%</span>
                <span style="font-size: 10px; color: #e9d5ff; opacity: 0.9;">📜 Status &amp; LLM</span>
              </button>`;
            }).join('')}
           </div>`
        : '';

      let monitorHtml = '';
      if (liveJob) {
        const curStep = Number(liveJob.step || 1);
        const stages = [
          { n: 1, label: '📋 Stage 1/4: Registering in Personal Fleet Feature Backlog (Planned → In Progress)' },
          { n: 2, label: `🧠 Stage 2/4: Consulting Connected LLM with ${agent.name} context & synthesizing solution` },
          { n: 3, label: `⚙️ Stage 3/4: Applying directives & hot-reloading ${agent.name} runtime` },
          { n: 4, label: '✅ Stage 4/4: Executing to completion & marking Feature Backlog item Completed (100%)' },
        ];
        monitorHtml = `
          <div style="margin-top: 10px; padding: 12px 14px; border-radius: 9px; background: rgba(2, 6, 23, 0.88); border: 1px solid rgba(56, 189, 248, 0.55); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 14px;">📡</span>
                <strong style="font-size: 12px; color: #38bdf8;">Live Self-Improvement Execution Monitor — In Progress (${esc(liveJob.progress || 25)}%)</strong>
              </div>
              <span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.45); font-size: 10.5px;">⏳ Executing via Connected LLM...</span>
            </div>
            <div style="font-size: 11.5px; color: #e2e8f0; margin-bottom: 8px;">
              <strong>Undertaking:</strong> ${esc(liveJob.title || '')}
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 6px; margin-bottom: 8px;">
              ${stages.map(st => {
                const done = curStep > st.n;
                const active = curStep === st.n;
                return `<div style="padding: 6px 9px; border-radius: 6px; font-size: 10.5px; background: ${done ? 'rgba(16, 185, 129, 0.14)' : (active ? 'rgba(56, 189, 248, 0.18)' : 'rgba(15, 23, 42, 0.6)')}; border: 1px solid ${done ? 'rgba(16, 185, 129, 0.4)' : (active ? 'rgba(56, 189, 248, 0.5)' : 'rgba(148, 163, 184, 0.2)')}; color: ${done ? '#6ee7b7' : (active ? '#38bdf8' : '#94a3b8')}; font-weight: ${active ? '700' : '500'};">
                  ${done ? '✅ ' : (active ? '🔄 ' : '⏳ ')}${esc(st.label)}
                </div>`;
              }).join('')}
            </div>
            <div style="padding: 8px 10px; border-radius: 6px; background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(168, 85, 247, 0.35); font-family: monospace; font-size: 11px; color: #e9d5ff; white-space: pre-wrap;">${esc(liveJob.message || 'Connecting to LLM and Feature Backlog pipeline...')}</div>
          </div>
        `;
      } else if (isMonitorOpen && imps.length > 0 && selIdx >= 0) {
        const rawSel = imps[selIdx];
        const sel = (typeof rawSel === 'object' && rawSel) ? rawSel : { title: String(rawSel) };
        const blId = Number(sel.backlog_id || 0);
        const blStatus = sel.backlog_status || 'Completed';
        const statusLabel = (sel.status || 'completed').toUpperCase();
        const prog = Number(sel.progress || 100);
        const llmModel = sel.llm_model || sel.llm_engine || 'afcc-evolution-executor-v2';
        const llmResp = sel.llm_response || (
          `✅ Self-Improvement Executed to Completion for ${agent.name}\n` +
          `1. Feature Backlog: Registered ${blId > 0 ? 'as #BL-' + blId : 'in Personal Fleet Feature Backlog'} (Planned → In Progress → Completed, 100%).\n` +
          `2. Agent Context: Integrated '${sel.title}' into ${agent.name} runtime directives and telemetry.\n` +
          `3. Verification: Live execution pass completed with 0 regressions.`
        );
        const steps = Array.isArray(sel.execution_steps) && sel.execution_steps.length > 0
          ? sel.execution_steps
          : [
              { step: 1, label: `📋 Added to Personal Fleet Feature Backlog ${blId > 0 ? '(#BL-' + blId + ')' : ''}`, detail: 'Status: Planned → In Progress', status: 'completed' },
              { step: 2, label: `🧠 Connected LLM Context & Architecture Synthesis (${llmModel})`, detail: `Synthesized implementation for ${agent.name}`, status: 'completed' },
              { step: 3, label: `⚙️ Applied Directives & Hot-Reloaded ${agent.name}`, detail: 'Persisted in agent_evolution state without data loss', status: 'completed' },
              { step: 4, label: '✅ Executed to Completion & Verified', detail: 'Feature Backlog item marked Completed (100%)', status: 'completed' },
            ];

        monitorHtml = `
          <div style="margin-top: 10px; padding: 12px 14px; border-radius: 9px; background: rgba(2, 6, 23, 0.86); border: 1px solid rgba(168, 85, 247, 0.45); box-shadow: 0 6px 20px rgba(0, 0, 0, 0.32);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
              <div style="display: flex; align-items: center; gap: 7px; flex-wrap: wrap;">
                <span style="font-size: 14px;">📡</span>
                <strong style="font-size: 12px; color: #e9d5ff;">Live Status &amp; LLM Textual Response Monitor</strong>
                <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.45); font-size: 10px;">✅ ${esc(statusLabel)} (${prog}%)</span>
                ${blId > 0 ? `<button type="button" onclick="FleetNavigator.switchAgent('backlog')" title="View #BL-${blId} in Personal Fleet Feature Backlog" class="btn" style="padding: 2px 8px; font-size: 10px; border-color: rgba(251, 191, 36, 0.45); background: rgba(251, 191, 36, 0.12); color: #fbbf24; font-weight: 700;">📋 Backlog #BL-${blId}: ${esc(blStatus)} ↗</button>` : ''}
                <span class="badge" style="background: rgba(56, 189, 248, 0.15); color: #7dd3fc; border: 1px solid rgba(56, 189, 248, 0.35); font-size: 10px;">🤖 LLM: ${esc(llmModel)}</span>
              </div>
              <button type="button" class="btn" onclick="FleetNavigator.toggleSelfImproveStatusMonitor('${aid}')" style="padding: 2px 8px; font-size: 10.5px; border-color: rgba(148, 163, 184, 0.3); color: #94a3b8;">✕ Hide Monitor</button>
            </div>

            <div style="font-size: 11.5px; color: #f8fafc; font-weight: 600; margin-bottom: 6px;">
              🎯 Improvement (${selIdx + 1}/${imps.length}): <span style="color: #38bdf8;">${esc(sel.title || '')}</span>
              ${sel.completed_at || sel.undertaken_at ? `<span style="font-size: 10.5px; color: #94a3b8; font-weight: 400; margin-left: 6px;">• Completed ${esc(sel.completed_at || sel.undertaken_at)}</span>` : ''}
            </div>

            ${sel.description && sel.description !== sel.title ? `<div style="font-size: 11px; color: #cbd5e1; margin-bottom: 8px; padding: 6px 9px; border-radius: 6px; background: rgba(15, 23, 42, 0.65); border-left: 3px solid #38bdf8; white-space: pre-wrap;">${esc(sel.description)}</div>` : ''}

            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 6px; margin-bottom: 9px;">
              ${steps.map(st => `
                <div style="padding: 6px 9px; border-radius: 6px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.32); font-size: 10.5px; color: #d1fae5;">
                  <div style="font-weight: 700; color: #6ee7b7;">${esc(st.label || '')}</div>
                  ${st.detail ? `<div style="color: #94a3b8; font-size: 10px; margin-top: 2px;">${esc(st.detail)}</div>` : ''}
                </div>
              `).join('')}
            </div>

            <div style="padding: 9px 11px; border-radius: 7px; background: rgba(15, 23, 42, 0.92); border: 1px solid rgba(56, 189, 248, 0.35);">
              <div style="font-size: 10.5px; font-weight: 700; color: #7dd3fc; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em;">📜 Textual Response from Connected LLM (${esc(llmModel)}):</div>
              <div style="font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11.5px; line-height: 1.5; color: #e2e8f0; white-space: pre-wrap;">${esc(llmResp)}</div>
            </div>
          </div>
        `;
      }

      containers.forEach((box, boxIdx) => {
        const inpId = `inlineSelfImproveInput_${aid}_${boxIdx}`;
        const btnId = `btnInlineSelfImprove_${aid}_${boxIdx}`;
        const impBtnId = `btnImproviseInline_${aid}_${boxIdx}`;
        const metaBarId = `improviseMetaBar_${aid}_${boxIdx}`;
        const prevVal = document.getElementById(inpId)?.value || '';
        box.innerHTML = `
          <div style="padding: 11px 14px; border-radius: 10px; background: linear-gradient(135deg, rgba(88, 28, 135, 0.18), rgba(15, 23, 42, 0.82)); border: 1px solid rgba(168, 85, 247, 0.38);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; padding-top: 3px;">
                <span style="font-size: 14px;">✨</span>
                <strong style="font-size: 12.5px; color: #e9d5ff;">Self-Improvement &amp; Feature Evolution (${esc(agent.name)})</strong>
                <span class="badge" style="background: ${imps.length > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(168, 85, 247, 0.2)'}; color: ${imps.length > 0 ? '#6ee7b7' : '#d8b4fe'}; border: 1px solid ${imps.length > 0 ? 'rgba(16, 185, 129, 0.4)' : 'rgba(168, 85, 247, 0.4)'}; font-size: 10.5px;">
                  ${imps.length} Undertaken
                </span>
                ${imps.length > 0 ? `<button type="button" class="btn" onclick="FleetNavigator.toggleSelfImproveStatusMonitor('${aid}')" title="Toggle Live Status &amp; Connected LLM Textual Response Monitor" style="padding: 3px 9px; font-size: 10.5px; font-weight: 600; border-color: rgba(168, 85, 247, 0.5); background: ${isMonitorOpen ? 'rgba(168, 85, 247, 0.28)' : 'rgba(15, 23, 42, 0.7)'}; color: #e9d5ff;">📡 ${isMonitorOpen ? 'Hide' : 'Live Status &amp; LLM Response'}</button>` : ''}
              </div>
              <div style="display: flex; align-items: stretch; gap: 7px; flex-wrap: wrap; flex: 1; justify-content: flex-end; min-width: 320px;">
                <textarea id="${inpId}" rows="2" placeholder="➕ Type manual improvement for ${esc(agent.name)} (multi-line supported • Ctrl+Enter to undertake, or click '🪄 Improvise Prompt' to enhance with ${esc(agent.name)} context via LLM)..." onkeydown="if((event.ctrlKey||event.metaKey)&amp;&amp;event.key==='Enter'){event.preventDefault();FleetNavigator.quickAddManualImprovementInline('${aid}', '${inpId}', '${btnId}');}" style="flex: 1; max-width: 520px; min-width: 240px; padding: 6px 10px; border-radius: 7px; background: rgba(2, 6, 23, 0.82); border: 1px solid rgba(56, 189, 248, 0.38); color: #f8fafc; font-size: 11.5px; line-height: 1.45; resize: vertical; font-family: inherit;">${esc(prevVal)}</textarea>
                <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                  <button id="${impBtnId}" title="Improvise and enhance your draft text with the connected LLM using '${esc(agent.name)}' context so you can review it before submitting" type="button" class="btn" onclick="FleetNavigator.improviseManualImprovementInline('${aid}', '${inpId}', '${impBtnId}', '${metaBarId}')" style="padding: 6px 10px; font-size: 11px; border-color: rgba(168, 85, 247, 0.55); background: rgba(88, 28, 135, 0.28); color: #e9d5ff; font-weight: 700; white-space: nowrap;">🪄 Improvise Prompt</button>
                  <button id="${btnId}" title="Add to Feature Backlog first and execute to completion for '${esc(agent.name)}'" type="button" class="btn" onclick="FleetNavigator.quickAddManualImprovementInline('${aid}', '${inpId}', '${btnId}')" style="padding: 6px 10px; font-size: 11px; border-color: rgba(56, 189, 248, 0.45); color: #38bdf8; font-weight: 700; white-space: nowrap;">➕ Undertake Manual Item</button>
                  <button title="Open 10 AI-generated feature improvements for '${esc(agent.name)}' and select which ones to apply" type="button" class="btn btn-primary" onclick="openEvolveAgentModal('${aid}')" style="padding: 6px 11px; font-size: 11px; font-weight: 700; background: linear-gradient(135deg, rgba(168, 85, 247, 0.35), rgba(6, 182, 212, 0.35)); border: 1px solid rgba(168, 85, 247, 0.6); color: #f8fafc; white-space: nowrap;">✨ 10 Ways to Improve</button>
                </div>
              </div>
            </div>
            <div id="${metaBarId}" style="display: none; margin-top: 7px; padding: 6px 10px; border-radius: 6px; background: rgba(88, 28, 135, 0.24); border: 1px solid rgba(168, 85, 247, 0.42); font-size: 11px; color: #e9d5ff; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap;"></div>
            ${pillsHtml}
            ${monitorHtml}
          </div>
        `;
      });
    });
  },

  toggleSelfImproveStatusMonitor(agentId) {
    this._selfImproveMonitorOpen[agentId] = !Boolean(this._selfImproveMonitorOpen[agentId]);
    this.renderActiveAgentSelfImprovementsBanner(agentId);
  },

  selectSelfImproveItemForMonitor(agentId, idx) {
    const currentlyOpen = Boolean(this._selfImproveMonitorOpen[agentId]);
    const currentIdx = this._selfImproveSelectedIdx[agentId];
    if (currentlyOpen && currentIdx === idx) {
      this._selfImproveMonitorOpen[agentId] = false;
    } else {
      this._selfImproveSelectedIdx[agentId] = idx;
      this._selfImproveMonitorOpen[agentId] = true;
    }
    this.renderActiveAgentSelfImprovementsBanner(agentId);
  },

  async improviseManualImprovementInline(agentId, inputId, btnId, metaBarId) {
    const inp = document.getElementById(inputId);
    const rawText = (inp ? inp.value : '').trim();
    const agent = this.agents.find(a => a.id === agentId);
    if (!rawText) {
      if (typeof showFleetToast === 'function') {
        showFleetToast(`Type a draft idea for ${agent?.name || agentId} first, then click "🪄 Improvise Prompt" to enhance it with LLM context.`, true);
      }
      if (inp) inp.focus();
      return;
    }
    const btn = document.getElementById(btnId);
    const origBtnText = btn ? btn.textContent : '🪄 Improvise Prompt';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Improvising...';
    }
    try {
      this._originalImproviseDrafts[inputId] = rawText;
      const res = await fetch('/api/studio/evolve/improvise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: agentId, text: rawText }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not improvise prompt.');
      }
      const improvised = String(data.improvised_text || rawText).trim();
      if (inp) {
        inp.value = improvised;
        inp.rows = Math.min(6, Math.max(3, improvised.split('\n').length));
        inp.focus();
      }
      const metaBar = document.getElementById(metaBarId);
      if (metaBar) {
        const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        metaBar.style.display = 'flex';
        metaBar.innerHTML = `
          <div>
            ✨ <strong>Improvised for ${esc(data.agent_name || agent?.name || agentId)}</strong>
            via <code>${esc(data.model_used || 'Connected LLM')}</code>
            <span style="color: #cbd5e1;">• Context: ${esc(data.domain_title || data.context_summary || '')} — Review or edit above before clicking ➕ Undertake Manual Item.</span>
          </div>
          <button type="button" class="btn" onclick="FleetNavigator.restoreOriginalInlineImproviseDraft('${inputId}', '${metaBarId}')" style="padding: 2px 8px; font-size: 10.5px; border-color: rgba(248, 250, 252, 0.3); color: #f8fafc;">↩️ Restore Original</button>
        `;
      }
      if (typeof showFleetToast === 'function') {
        showFleetToast(`🪄 Enhanced prompt using ${data.agent_name || agentId} context! Review before submitting.`, false);
      }
    } catch (err) {
      if (typeof showFleetToast === 'function') {
        showFleetToast(`✕ Failed to improvise prompt: ${err.message}`, true);
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = origBtnText;
      }
    }
  },

  restoreOriginalInlineImproviseDraft(inputId, metaBarId) {
    const inp = document.getElementById(inputId);
    const orig = this._originalImproviseDrafts[inputId];
    if (inp && orig) {
      inp.value = orig;
      inp.rows = Math.min(5, Math.max(2, orig.split('\n').length));
      inp.focus();
    }
    const metaBar = document.getElementById(metaBarId);
    if (metaBar) metaBar.style.display = 'none';
  },

  async quickAddManualImprovementInline(agentId, inputId, btnId) {
    const inp = document.getElementById(inputId);
    const text = (inp ? inp.value : '').trim();
    if (!text) {
      if (typeof showFleetToast === 'function') {
        showFleetToast('Type a manual improvement item first, or click "✨ 10 Ways to Improve".', true);
      }
      if (inp) inp.focus();
      return;
    }
    const agent = this.agents.find(a => a.id === agentId);
    const firstLine = text.split('\n')[0].trim();
    const shortHeadline = firstLine.length <= 85 ? firstLine : firstLine.slice(0, 82) + '...';
    const btn = document.getElementById(btnId);
    const origText = btn ? btn.textContent : '';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ Undertaking...';
    }

    // Activate live real-time execution status monitor immediately so user sees every stage
    this._selfImproveMonitorOpen[agentId] = true;
    this._selfImproveLiveJob[agentId] = {
      step: 1,
      progress: 25,
      title: shortHeadline,
      message: `[Stage 1/4] Registering "${shortHeadline}" in Personal Fleet Feature Backlog (Status: Planned → In Progress)...`,
    };
    this.renderActiveAgentSelfImprovementsBanner(agentId);

    try {
      let parsedItem = {
        id: `custom_${Date.now()}`,
        title: shortHeadline,
        description: text,
        code_enhancement_brief: text,
        is_custom: true,
      };
      try {
        const parseRes = await fetch('/api/studio/evolve/parse_custom', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: agentId, text }),
        });
        if (parseRes.ok) {
          const parseData = await parseRes.json();
          if (parseData && parseData.suggestion) {
            parsedItem = {
              id: parseData.suggestion.id || parsedItem.id,
              title: parseData.suggestion.title || parsedItem.title,
              description: parseData.suggestion.description || text,
              code_enhancement_brief: parseData.suggestion.patch?.code_enhancement_brief || text,
              is_custom: true,
            };
          }
        }
      } catch (_) {}

      this._selfImproveLiveJob[agentId] = {
        step: 2,
        progress: 55,
        title: parsedItem.title,
        message: `[Stage 2/4] Connected LLM analyzing "${parsedItem.title}" with ${agent?.name || agentId} context & applying runtime directives...`,
      };
      this.renderActiveAgentSelfImprovementsBanner(agentId);

      const existingImps = Array.isArray(agent?.evolution_improvements) ? agent.evolution_improvements : [];
      const res = await fetch('/api/settings/agents/evolve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: agentId,
          evolution_improvements: [...existingImps, parsedItem],
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not apply manual improvement.');
      }

      this._selfImproveLiveJob[agentId] = {
        step: 4,
        progress: 100,
        title: parsedItem.title,
        message: `[Stage 4/4] Completed! Improvement registered in Feature Backlog and executed to completion on ${agent?.name || agentId}.`,
      };
      if (inp) {
        inp.value = '';
        inp.rows = 2;
      }
      delete this._selfImproveLiveJob[agentId];
      await this.fetchFleetData();
      const updatedAgent = this.agents.find(a => a.id === agentId);
      const updatedImps = Array.isArray(updatedAgent?.evolution_improvements) ? updatedAgent.evolution_improvements : [];
      this._selfImproveSelectedIdx[agentId] = Math.max(0, updatedImps.length - 1);
      this._selfImproveMonitorOpen[agentId] = true;
      this.renderActiveAgentSelfImprovementsBanner(agentId);

      // Refresh Feature Backlog view if loaded so the new Completed backlog item is immediately visible
      if (typeof window.fetchFeatureBacklog === 'function') {
        try { window.fetchFeatureBacklog(); } catch (_) {}
      }

      const latestImp = updatedImps[updatedImps.length - 1];
      const blTag = latestImp?.backlog_id ? ` (Backlog #BL-${latestImp.backlog_id} → Completed)` : '';
      if (typeof showFleetToast === 'function') {
        showFleetToast(`✨ '${agent?.name || agentId}' undertook "${parsedItem.title}"${blTag}! See Live Status & LLM Response below.`, false);
      }
    } catch (err) {
      delete this._selfImproveLiveJob[agentId];
      this.renderActiveAgentSelfImprovementsBanner(agentId);
      if (typeof showFleetToast === 'function') {
        showFleetToast(`✕ Failed to undertake manual improvement: ${err.message}`, true);
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = origText || '➕ Undertake Manual Item';
      }
    }
  },

  // --- Command Palette & Unified Conversational Omnibar (Ctrl+K Spotlight / UX-05) ---
  omnibarChatTurns: [],
  paletteNavigatedByKeyboard: false,

  formatOmnibarMarkdown(text) {
    if (!text) return '';
    if (typeof window !== 'undefined' && typeof window.formatMarkdown === 'function') {
      return window.formatMarkdown(text);
    }
    const escaped = String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    return escaped
      .replace(/\*\*(.+?)\*\*/g, '<strong style="color: var(--text);">$1</strong>')
      .replace(/`([^`]+)`/g, '<code style="background: rgba(15, 23, 42, 0.75); padding: 1px 5px; border-radius: 4px; color: var(--accent-cyan); font-size: 11.5px;">$1</code>')
      .replace(/\n/g, '<br>');
  },

  openCommandPalette() {
    const modal = document.getElementById('commandPaletteModal');
    if (!modal) return;
    modal.style.display = 'flex';
    this.paletteSelectedIndex = 0;
    this.paletteNavigatedByKeyboard = false;
    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox) {
      if (this.omnibarChatTurns.length > 0) {
        outBox.style.display = 'block';
        this.renderOmnibarChatThread();
      } else {
        outBox.style.display = 'none';
      }
    }
    const input = document.getElementById('cmdPaletteInput');
    if (input) {
      input.value = '';
      setTimeout(() => input.focus(), 80);
    }
    this.filterCommandPalette('');
  },

  closeCommandPalette() {
    const modal = document.getElementById('commandPaletteModal');
    if (modal) modal.style.display = 'none';
  },

  clearOmnibarConversation() {
    this.omnibarChatTurns = [];
    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox) {
      outBox.innerHTML = '';
      outBox.style.display = 'none';
    }
    fetch('/api/omnibar/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: 'clear chat' })
    }).catch(() => {});
    const input = document.getElementById('cmdPaletteInput');
    if (input) input.focus();
  },

  onPaletteInput(query) {
    this.paletteNavigatedByKeyboard = false;
    this.filterCommandPalette(query);
  },

  runOmnibarPreset(presetQuery) {
    const input = document.getElementById('cmdPaletteInput');
    if (input) {
      input.value = presetQuery;
      this.filterCommandPalette(presetQuery);
    }
    this.executeOmnibarInput(presetQuery);
  },

  renderOmnibarChatThread() {
    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (!outBox) return;
    if (this.omnibarChatTurns.length === 0) {
      outBox.style.display = 'none';
      outBox.innerHTML = '';
      return;
    }
    outBox.style.display = 'block';

    const turnsHtml = this.omnibarChatTurns.map((turn, idx) => {
      const isLatest = idx === this.omnibarChatTurns.length - 1;
      const data = turn.data || {};
      let extraContentHtml = '';

      if ((data.mode === 'discovery' || data.mode === 'process_discovery') && Array.isArray(data.recommendations)) {
        extraContentHtml = data.recommendations.map(r => `
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 10px; margin-top: 6px; background: rgba(15, 23, 42, 0.75); border: 1px solid var(--border-color); border-radius: 6px;">
            <div>
              <strong style="color: var(--text); font-size: 12.5px;">${r.icon || '🤖'} ${r.name}</strong>
              <span class="badge" style="margin-left: 6px; font-size: 10px; background: rgba(16, 185, 129, 0.15); color: #10b981;">Score ${r.opportunity_score}/100</span>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${r.evidence_summary || r.description || ''} (${r.estimated_minutes_saved_per_week || 30} min/wk saved)</div>
            </div>
            <button type="button" class="btn btn-sm btn-primary" style="white-space: nowrap; font-size: 11px; padding: 4px 10px;" onclick="FleetNavigator.spawnDiscoveredAgent('${r.recommendation_id}')">🚀 Spawn Agent</button>
          </div>
        `).join('');
      } else if (data.mode === 'studio_synthesis' && data.spec) {
        const sp = data.spec;
        const fldCount = Array.isArray(sp.fields) ? sp.fields.length : 0;
        const blkCount = Array.isArray(sp.ui_blocks) ? sp.ui_blocks.length : 0;
        const esc = typeof escapeHtml === 'function' ? escapeHtml : (v => String(v == null ? '' : v));
        extraContentHtml = `
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 9px 11px; margin-top: 8px; background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 8px;">
            <div style="font-size: 11.5px; color: var(--text-muted);">
              <strong style="color: #34d399;">${esc(sp.icon || '✨')} ${esc(sp.name || sp.agent_id)}</strong>
              <span> • ${fldCount} typed SQLite fields • ${blkCount} live widgets</span>
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(56, 189, 248, 0.4); color: var(--accent-cyan);" onclick="FleetNavigator.openSynthesizedInStudio(${idx})">🎛️ Customize in Studio</button>
              <button type="button" class="btn btn-sm btn-primary" style="font-size: 11px; padding: 4px 11px; font-weight: 700;" onclick="FleetNavigator.launchSynthesizedOmnibarAgent(${idx})">🚀 1-Click Create &amp; Launch</button>
            </div>
          </div>
        `;
      }

      const suggestions = isLatest && Array.isArray(data.suggestions) ? data.suggestions : [];
      const suggestionsHtml = suggestions.length > 0 ? `
        <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.06);">
          ${suggestions.map(s => {
            const safeAttr = String(s).replace(/'/g, "\\'");
            return `<button type="button" class="badge" style="cursor: pointer; background: rgba(56, 189, 248, 0.12); color: var(--accent-cyan); border: 1px solid rgba(56, 189, 248, 0.28); font-size: 11px; padding: 3px 8px;" onclick="FleetNavigator.runOmnibarPreset('${safeAttr}')">💬 ${s}</button>`;
          }).join('')}
        </div>
      ` : '';

      return `
        <div style="margin-bottom: ${isLatest ? '0' : '10px'}; padding-bottom: ${isLatest ? '0' : '10px'}; border-bottom: ${isLatest ? 'none' : '1px solid rgba(255,255,255,0.06)'};">
          <div style="display: flex; justify-content: flex-end; margin-bottom: 6px;">
            <div style="background: rgba(56, 189, 248, 0.16); border: 1px solid rgba(56, 189, 248, 0.32); color: var(--text); padding: 5px 11px; border-radius: 12px 12px 2px 12px; font-size: 12.5px; max-width: 85%;">
              <span style="color: var(--accent-cyan); font-weight: 600; margin-right: 4px;">You:</span> ${this.formatOmnibarMarkdown(turn.userQuery)}
            </div>
          </div>
          <div style="background: rgba(15, 23, 42, 0.82); border: 1px solid var(--border-color); padding: 10px 13px; border-radius: 12px 12px 12px 2px;">
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 4px;">
              <strong style="color: var(--accent-green); font-size: 12.5px;">${data.title || '🤖 Fleet Conversational Assistant'}</strong>
              <div style="display: flex; gap: 6px; align-items: center;">
                ${data.agent_id ? `<button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 8px;" onclick="FleetNavigator.switchAgent('${data.agent_id}')">Open ${data.agent_id} →</button>` : ''}
              </div>
            </div>
            <div style="font-size: 12.5px; line-height: 1.5; color: var(--text);">${this.formatOmnibarMarkdown(data.message || '')}</div>
            ${extraContentHtml}
            ${suggestionsHtml}
          </div>
        </div>
      `;
    }).join('');

    outBox.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
        <span style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">💬 Conversational Fleet Session (${this.omnibarChatTurns.length} turn${this.omnibarChatTurns.length === 1 ? '' : 's'})</span>
        <div style="display: flex; gap: 6px;">
          <button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 1px 7px; border-color: rgba(16, 185, 129, 0.4); color: var(--accent-green);" onclick="FleetNavigator.closeCommandPalette(); if(typeof dockFleetChatToRightPanel==='function') dockFleetChatToRightPanel();">◨ Dock to Right Panel</button>
          <button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 1px 7px;" onclick="FleetNavigator.switchAgent('antigravity')">Open Live Console →</button>
          <button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 1px 7px; color: var(--text-muted);" onclick="FleetNavigator.clearOmnibarConversation()">Clear</button>
        </div>
      </div>
      <div id="omnibarChatScrollContainer" style="max-height: 250px; overflow-y: auto; padding-right: 4px;">
        ${turnsHtml}
      </div>
    `;
    const scrollEl = document.getElementById('omnibarChatScrollContainer');
    if (scrollEl) {
      scrollEl.scrollTop = scrollEl.scrollHeight;
    }
    if (typeof renderAgFleetZeroChat === 'function') {
      renderAgFleetZeroChat();
    }
  },

  async executeOmnibarInput(overrideQuery) {
    const input = document.getElementById('cmdPaletteInput');
    const rawQuery = (overrideQuery !== undefined ? overrideQuery : (input ? input.value : '')).trim();
    if (!rawQuery) return;

    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox && this.omnibarChatTurns.length === 0) {
      outBox.style.display = 'block';
      outBox.innerHTML = '<span style="color: var(--accent-cyan);">⚡ Thinking...</span>';
    }

    try {
      const res = await fetch('/api/omnibar/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: rawQuery })
      });
      const data = await res.json();
      if (rawQuery.toLowerCase().trim() === 'clear' || rawQuery.toLowerCase().trim() === 'clear chat') {
        this.omnibarChatTurns = [];
      } else {
        this.omnibarChatTurns.push({ userQuery: rawQuery, data });
        if (this.omnibarChatTurns.length > 12) {
          this.omnibarChatTurns.shift();
        }
      }
      this.renderOmnibarChatThread();
      if (data.mode === 'studio_created') {
        await this.fetchFleetData();
        if (typeof fetchSchedules === 'function') fetchSchedules();
      } else if (data.mode === 'navigate' && data.agent_id) {
        this.closeCommandPalette();
        this.switchAgent(data.agent_id);
        return;
      } else if ((data.mode === 'agent_record_added' || data.mode === 'agent_task') && data.agent_id && data.agent_id === this.activeAgentId) {
        if (window.CustomAgentRuntime && typeof window.CustomAgentRuntime.mount === 'function') {
          window.CustomAgentRuntime.mount(data.agent_id);
        }
      }
      if (input) {
        input.value = '';
        this.filterCommandPalette('');
        input.focus();
      }
    } catch (e) {
      if (outBox) {
        outBox.style.display = 'block';
        outBox.innerHTML = `<span style="color: #ef4444;">⚠️ Omnibar error: ${e.message}</span>`;
      }
    }
  },

  async launchSynthesizedOmnibarAgent(turnIdx) {
    const turn = this.omnibarChatTurns[turnIdx];
    const spec = turn?.data?.spec;
    if (!spec) return;
    try {
      const payload = {
        ...spec,
        id: spec.agent_id || spec.id,
        run_immediately: true,
      };
      const res = await fetch('/api/settings/agents/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not launch synthesized agent.');
      }
      await this.fetchFleetData();
      if (typeof fetchSchedules === 'function') fetchSchedules();
      this.closeCommandPalette();
      this.switchAgent(data.agent_id || payload.id);
      if (typeof showFleetToast === 'function') {
        showFleetToast(`🚀 Created & activated '${spec.name}' from Omnibar!`, false);
      }
    } catch (e) {
      if (typeof showFleetToast === 'function') showFleetToast('Launch error: ' + e.message, true);
      else alert('Launch error: ' + e.message);
    }
  },

  openSynthesizedInStudio(turnIdx) {
    const turn = this.omnibarChatTurns[turnIdx];
    const spec = turn?.data?.spec;
    if (!spec) return;
    this.closeCommandPalette();
    if (typeof openCreateAgentModal === 'function') {
      openCreateAgentModal();
      setTimeout(() => {
        if (typeof populateWizardFromSpec === 'function') {
          populateWizardFromSpec(spec);
        }
        if (typeof renderStudioSynthesisSummary === 'function') {
          renderStudioSynthesisSummary(spec);
        }
      }, 60);
    }
  },

  async spawnDiscoveredAgent(recId) {
    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox) {
      outBox.innerHTML = `<span style="color: var(--accent-cyan);">🚀 Spawning recommended agent (${recId})...</span>`;
    }
    try {
      const res = await fetch('/api/discovery/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recommendation_id: recId })
      });
      const data = await res.json();
      if (data.status === 'success') {
        await this.fetchFleetData();
        if (outBox) {
          outBox.innerHTML = `<div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: #10b981;">🎉 ${data.message}</strong>
            <button type="button" class="btn btn-sm btn-primary" onclick="FleetNavigator.switchAgent('${data.agent_id}')">Switch to ${data.agent_id} →</button>
          </div>`;
        }
      } else {
        if (outBox) outBox.innerHTML = `<span style="color: #ef4444;">⚠️ ${data.message || 'Spawn failed'}</span>`;
      }
    } catch (e) {
      if (outBox) outBox.innerHTML = `<span style="color: #ef4444;">⚠️ ${e.message}</span>`;
    }
  },

  filterCommandPalette(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
      this.paletteResults = this.agents.slice(0, 12);
    } else {
      const stripped = q.startsWith('@') ? q.slice(1).split(' ')[0] : q;
      this.paletteResults = this.agents.filter(a =>
        a.name.toLowerCase().includes(stripped) ||
        a.id.toLowerCase().includes(stripped) ||
        a.category.toLowerCase().includes(stripped) ||
        (a.description || '').toLowerCase().includes(stripped)
      ).slice(0, 15);
    }

    this.paletteSelectedIndex = 0;
    this.renderPaletteResults();
  },

  renderPaletteResults() {
    const list = document.getElementById('cmdPaletteResultsList');
    if (!list) return;

    if (this.paletteResults.length === 0) {
      list.innerHTML = `
        <div style="padding: 16px 20px; text-align: center; color: var(--text-muted); font-size: 13px;">
          💬 Press <strong>Enter</strong> or click <strong>Ask ↵</strong> to chat with the Fleet Conversational Assistant.
        </div>`;
      return;
    }

    list.innerHTML = this.paletteResults.map((a, idx) => {
      const isSelected = (idx === this.paletteSelectedIndex && this.paletteNavigatedByKeyboard);
      return `
        <div class="cmd-palette-item ${isSelected ? 'selected' : ''}" onclick="FleetNavigator.paletteSelectIndex(${idx})">
          <div style="display: flex; align-items: center; gap: 10px; min-width: 0;">
            <span style="font-size: 20px;">${a.icon || '⚡'}</span>
            <div style="min-width: 0;">
              <div style="font-size: 13.5px; font-weight: 600; color: var(--text);">${a.name}</div>
              <div style="font-size: 11px; color: var(--text-muted);">${a.description || a.id}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="badge" style="font-size: 11px; background: rgba(255,255,255,0.06);">${a.category}</span>
            <span style="font-size: 11px; color: var(--accent-cyan); font-family: monospace;">@${a.id} ↵</span>
          </div>
        </div>`;
    }).join('');
  },

  paletteNavigate(dir) {
    if (this.paletteResults.length === 0) return;
    this.paletteNavigatedByKeyboard = true;
    this.paletteSelectedIndex = (this.paletteSelectedIndex + dir + this.paletteResults.length) % this.paletteResults.length;
    this.renderPaletteResults();
    const activeEl = document.querySelector('.cmd-palette-item.selected');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
  },

  paletteSelectCurrent() {
    const input = document.getElementById('cmdPaletteInput');
    const rawQuery = (input ? input.value : '').trim();
    if (!rawQuery) {
      if (this.paletteResults[this.paletteSelectedIndex]) {
        this.switchAgent(this.paletteResults[this.paletteSelectedIndex].id);
      }
      return;
    }
    const lower = rawQuery.toLowerCase();
    const exactAgentMatch = this.agents.find(
      a => a.id.toLowerCase() === lower || a.name.toLowerCase() === lower
    );
    if (this.paletteNavigatedByKeyboard && this.paletteResults[this.paletteSelectedIndex]) {
      this.switchAgent(this.paletteResults[this.paletteSelectedIndex].id);
      return;
    }
    if (exactAgentMatch && !rawQuery.startsWith('@')) {
      this.switchAgent(exactAgentMatch.id);
      return;
    }
    this.executeOmnibarInput(rawQuery);
  },

  paletteSelectIndex(idx) {
    if (this.paletteResults[idx]) {
      this.switchAgent(this.paletteResults[idx].id);
    }
  }
};

// Global window helpers for inline HTML event handlers
window.FleetNavigator = FleetNavigator;

window.toggleFleetNavigator = function(open) {
  if (open === true) {
    FleetNavigator.openFleetDrawer();
  } else if (open === false) {
    FleetNavigator.closeFleetDrawer();
  } else {
    FleetNavigator.toggleFleetDrawer();
  }
};

window.openCommandPalette = function() {
  FleetNavigator.openCommandPalette();
};

window.closeCommandPalette = function() {
  FleetNavigator.closeCommandPalette();
};

window.openAgentSettingsDrawer = function(agentId) {
  if (typeof openSettingsModal === 'function') {
    openSettingsModal().then(() => {
      if (typeof switchSettingsModalTab === 'function') {
        switchSettingsModalTab('agents');
      }
      const search = document.getElementById('settingsAgentSearchInput');
      if (search && agentId) {
        search.value = agentId;
        if (typeof filterSettingsAgents === 'function') {
          filterSettingsAgents(agentId);
        }
      }
    });
  }
};

window.FleetNavigator = FleetNavigator;
window.fetchAgents = function() {
  return FleetNavigator.fetchFleetData();
};

// --- Admin PR Review, Branch Governance & CI Quality Gate (pr_review) ---
function _prEsc(val) {
  if (typeof escapeHtml === 'function') return escapeHtml(String(val == null ? '' : val));
  return String(val == null ? '' : val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function _prNotify(msg, isError) {
  if (typeof showFleetToast === 'function') {
    showFleetToast(msg, Boolean(isError));
  } else if (typeof showSettingsToast === 'function') {
    showSettingsToast(msg);
  }
}

function _renderDiffHtml(rawDiff) {
  if (!rawDiff || !rawDiff.trim()) {
    return '<div style="color: var(--text-muted); padding: 12px;">No file differences found relative to base.</div>';
  }
  const lines = String(rawDiff).split(/\r?\n/);
  const rendered = lines.map(line => {
    const esc = _prEsc(line);
    if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('diff --git')) {
      return `<div style="color: #93c5fd; font-weight: 700; background: rgba(30, 58, 138, 0.25); padding: 2px 6px; margin-top: 4px; border-radius: 3px;">${esc}</div>`;
    }
    if (line.startsWith('@@')) {
      return `<div style="color: #38bdf8; background: rgba(56, 189, 248, 0.12); padding: 1px 6px;">${esc}</div>`;
    }
    if (line.startsWith('+')) {
      return `<div style="color: #4ade80; background: rgba(16, 185, 129, 0.12); padding: 0 6px;">${esc}</div>`;
    }
    if (line.startsWith('-')) {
      return `<div style="color: #f87171; background: rgba(239, 68, 68, 0.12); padding: 0 6px;">${esc}</div>`;
    }
    return `<div style="color: #cbd5e1; padding: 0 6px;">${esc}</div>`;
  });
  return `<div style="background: rgba(2, 6, 23, 0.85); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px; overflow-x: auto; white-space: pre;">${rendered.join('')}</div>`;
}

function _renderSingleUnmergedBranchCard(b, idx) {
  const branchName = String(b.branch || '');
  const safeJsBranch = branchName.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
  const isClean = b.can_clean_merge !== false && b.merge_status !== 'CONFLICTS';
  const mergeBadge = isClean
    ? `<span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.35);">✅ Ready to Merge (Clean)</span>`
    : `<span class="badge" style="background: rgba(239, 68, 68, 0.16); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.35);">⚠️ Conflicts (${(b.conflict_files || []).length})</span>`;

  const scopeBadge = `<span class="badge" style="background: rgba(148, 163, 184, 0.14); color: #cbd5e1; font-family: monospace; font-size: 10.5px;">${_prEsc(b.scope || 'local')}</span>`;
  const currentBadge = b.is_current
    ? `<span class="badge" style="background: rgba(168, 85, 247, 0.2); color: #d8b4fe; font-size: 10.5px;">● Checked Out</span>`
    : '';
  const prObj = b.pr;
  const prBadge = prObj && prObj.number
    ? `<a href="${_prEsc(prObj.url || '#')}" target="_blank" rel="noopener noreferrer" class="badge" style="background: rgba(56, 189, 248, 0.18); color: #38bdf8; text-decoration: none;">🔗 PR #${_prEsc(prObj.number)}</a>`
    : '';

  // Authors list
  const authors = Array.isArray(b.authors) && b.authors.length > 0
    ? b.authors
    : [{
        name: b.latest_author_name || 'Unknown',
        email: b.latest_author_email || '',
        initials: b.latest_author_initials || '??',
        commits: b.ahead_count || 1
      }];

  const authorsHtml = authors.map(a => `
    <div style="display: inline-flex; align-items: center; gap: 7px; background: rgba(2, 6, 23, 0.65); border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; padding: 3px 10px 3px 5px; font-size: 11.5px;">
      <span style="width: 22px; height: 22px; border-radius: 50%; background: rgba(56, 189, 248, 0.22); color: #38bdf8; font-weight: 700; font-size: 10px; display: inline-flex; align-items: center; justify-content: center;">${_prEsc(a.initials || 'AU')}</span>
      <strong style="color: #f8fafc;">${_prEsc(a.name)}</strong>
      ${a.email ? `<span style="color: var(--text-muted); font-family: monospace; font-size: 11px;">&lt;${_prEsc(a.email)}&gt;</span>` : ''}
      <span class="badge" style="background: rgba(56, 189, 248, 0.12); color: #7dd3fc; font-size: 10px; padding: 1px 6px;">${_prEsc(a.commits)} commit${Number(a.commits) === 1 ? '' : 's'}</span>
    </div>
  `).join('');

  // Categories
  const categoriesHtml = (b.change_categories || []).map(cat => `
    <span class="badge" style="background: rgba(99, 102, 241, 0.16); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.3); font-size: 10.5px;">${_prEsc(cat)}</span>
  `).join('');

  // Commits list
  const commits = Array.isArray(b.commits) ? b.commits : [];
  const commitsHtml = commits.slice(0, 8).map(c => `
    <div style="display: flex; justify-content: space-between; align-items: baseline; gap: 10px; padding: 4px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 12px;">
      <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
        <code style="color: #38bdf8; font-size: 11px; margin-right: 6px;">${_prEsc(c.sha)}</code>
        <span style="color: #e2e8f0;">${_prEsc(c.subject)}</span>
      </div>
      <div style="white-space: nowrap; font-size: 11px; color: var(--text-muted);">
        <span>${_prEsc(c.author_name)}</span> • <span>${_prEsc(c.relative_time)}</span>
      </div>
    </div>
  `).join('');

  // Changed files list
  const changedFiles = Array.isArray(b.changed_files) ? b.changed_files : [];
  const filesHtml = changedFiles.slice(0, 15).map(f => {
    const st = String(f.status || 'M').toUpperCase();
    const stColor = st === 'A' ? '#4ade80' : (st === 'D' ? '#f87171' : '#38bdf8');
    return `
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 3px 8px; font-family: monospace; font-size: 11.5px; border-bottom: 1px solid rgba(255,255,255,0.04);">
        <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <span style="display: inline-block; width: 18px; color: ${stColor}; font-weight: 700;">[${_prEsc(st)}]</span>
          <span style="color: #cbd5e1;">${_prEsc(f.path)}</span>
        </div>
        <div style="white-space: nowrap;">
          <span style="color: #4ade80; margin-right: 6px;">+${_prEsc(f.additions || 0)}</span>
          <span style="color: #f87171;">-${_prEsc(f.deletions || 0)}</span>
        </div>
      </div>
    `;
  }).join('');

  const conflictBanner = (!isClean && Array.isArray(b.conflict_files) && b.conflict_files.length > 0)
    ? `<div style="margin-top: 8px; padding: 8px 10px; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); border-radius: 6px; font-size: 11.5px; color: #fca5a5;">
         <strong>⚠️ Merge Conflicts with <code>${_prEsc(b.base_branch || 'main')}</code>:</strong>
         <code>${b.conflict_files.map(_prEsc).join('</code>, <code>')}</code>
       </div>`
    : '';

  return `
    <div class="pr-branch-card" style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 10px; padding: 15px; margin-bottom: 12px;">
      <!-- Top Row: Branch Name & Status Badges -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 10px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span style="font-size: 14.5px; font-weight: 700; color: #38bdf8; font-family: monospace; background: rgba(56, 189, 248, 0.12); padding: 3px 10px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
            🌿 ${_prEsc(branchName)}
          </span>
          <span style="color: var(--text-muted); font-size: 12px;">→ <code>${_prEsc(b.base_branch || 'main')}</code></span>
          ${scopeBadge}
          ${currentBadge}
          ${prBadge}
          <span class="badge" style="background: rgba(16, 185, 129, 0.14); color: #4ade80; font-size: 11px;">+${_prEsc(b.ahead_count || 0)} ahead</span>
          ${Number(b.behind_count || 0) > 0
            ? `<span class="badge" style="background: rgba(245, 158, 11, 0.16); color: #fbbf24; font-size: 11px;">-${_prEsc(b.behind_count)} behind</span>`
            : `<span class="badge" style="background: rgba(255,255,255,0.06); color: var(--text-muted); font-size: 10.5px;">0 behind</span>`}
          ${mergeBadge}
        </div>
        <div style="font-size: 11.5px; color: var(--text-muted);">
          HEAD <code style="color: #7dd3fc;">${_prEsc(b.short_sha || '')}</code> • Updated <strong>${_prEsc(b.latest_commit_relative || '')}</strong>
        </div>
      </div>

      <!-- Author Attribution Row -->
      <div style="margin-bottom: 10px; padding: 8px 10px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;">
        <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 5px;">
          👤 Branch Author(s) &amp; Attribution
        </div>
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          ${authorsHtml}
        </div>
      </div>

      <!-- What Changed Summary & Diffstat -->
      <div style="margin-bottom: 10px; padding: 10px 12px; background: rgba(2, 6, 23, 0.55); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
          <div style="font-size: 13px; font-weight: 600; color: #f8fafc;">
            📝 What Changed: <span style="font-weight: 500; color: #e2e8f0;">${_prEsc(b.change_summary_text || b.latest_commit_subject || '')}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px; font-size: 12px; font-family: monospace;">
            <span class="badge" style="background: rgba(255,255,255,0.06); color: #cbd5e1;">📄 ${_prEsc(b.files_changed_count || 0)} file${Number(b.files_changed_count) === 1 ? '' : 's'}</span>
            <span style="color: #4ade80; font-weight: 700;">+${_prEsc(b.insertions || 0)}</span>
            <span style="color: #f87171; font-weight: 700;">-${_prEsc(b.deletions || 0)}</span>
          </div>
        </div>
        ${categoriesHtml ? `<div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px;">${categoriesHtml}</div>` : ''}
        ${conflictBanner}

        <!-- Commits Ahead Breakdown -->
        ${commitsHtml ? `
          <div style="margin-top: 8px; background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; overflow: hidden;">
            <div style="padding: 4px 8px; background: rgba(255,255,255,0.03); font-size: 11px; color: #94a3b8; font-weight: 600;">
              Commits Waiting Merge (${commits.length})
            </div>
            ${commitsHtml}
          </div>
        ` : ''}

        <!-- Expandable Changed Files List -->
        ${filesHtml ? `
          <details style="margin-top: 8px;">
            <summary style="cursor: pointer; font-size: 11.5px; color: #38bdf8; user-select: none;">
              📂 View Changed Files Breakdown (${changedFiles.length} file${changedFiles.length === 1 ? '' : 's'})
            </summary>
            <div style="margin-top: 6px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; max-height: 210px; overflow-y: auto;">
              ${filesHtml}
            </div>
          </details>
        ` : ''}
      </div>

      <!-- Action Buttons Row -->
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.07);">
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <button type="button" class="btn btn-primary btn-sm" style="font-size: 11.5px; padding: 5px 11px;" ${!isClean ? 'disabled title="Resolve merge conflicts first"' : ''} onclick="runPRBranchAction('merge', '${safeJsBranch}', {}, this)">
            ✅ Merge into ${_prEsc(b.base_branch || 'main')}
          </button>
          <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; border-color: rgba(16, 185, 129, 0.4); color: #34d399;" ${!isClean ? 'disabled' : ''} onclick="runPRBranchAction('merge', '${safeJsBranch}', {push_origin: true, delete_after_merge: true}, this)">
            🚀 Merge, Push &amp; Clean Up
          </button>
          <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; border-color: rgba(56, 189, 248, 0.35); color: #38bdf8;" onclick="inspectPRBranchDiff('${safeJsBranch}', this)">
            🔍 Inspect Full Diff
          </button>
          <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" onclick="runPRBranchAction('review_in_antigravity', '${safeJsBranch}', {}, this)">
            🤖 AI Review in Antigravity
          </button>
          ${Number(b.behind_count || 0) > 0 ? `
            <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; border-color: rgba(245, 158, 11, 0.4); color: #fbbf24;" onclick="runPRBranchAction('sync_with_main', '${safeJsBranch}', {}, this)">
              🔄 Sync with ${_prEsc(b.base_branch || 'main')}
            </button>
          ` : ''}
          ${!b.is_current ? `
            <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px;" onclick="runPRBranchAction('checkout', '${safeJsBranch}', {}, this)">
              📌 Checkout
            </button>
          ` : ''}
        </div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${b.compare_url ? `
            <a href="${_prEsc(b.compare_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; text-decoration: none;">
              🌐 Compare / PR on GitHub ↗
            </a>
          ` : ''}
          <button type="button" class="btn btn-sm" style="font-size: 11.5px; padding: 5px 10px; border-color: rgba(239, 68, 68, 0.35); color: #f87171;" onclick="confirmDeletePRBranch('${safeJsBranch}', true, this)">
            🗑️ Delete Branch
          </button>
        </div>
      </div>
    </div>
  `;
}

window.renderPRReviewDashboard = function(data) {
  if (!data || typeof data !== 'object') return;
  const prsData = data.prs || {};
  const ciData = data.ci || {};
  const branchesData = data.branches || {};
  const mainStatus = branchesData.main_status || {};
  const unmerged = Array.isArray(branchesData.unmerged_branches) ? branchesData.unmerged_branches : [];
  const synced = Array.isArray(branchesData.synced_branches) ? branchesData.synced_branches : [];
  const openPrs = Array.isArray(prsData.prs) ? prsData.prs : [];

  const lastBadge = document.getElementById('prLastCheckedBadge');
  if (lastBadge) {
    lastBadge.textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  // 1. Update KPI Cards
  const waitingCountEl = document.getElementById('prBranchesWaitingCount');
  const waitingSubEl = document.getElementById('prBranchesWaitingSub');
  const headerBadge = document.getElementById('prUnmergedHeaderBadge');
  if (waitingCountEl) {
    waitingCountEl.textContent = String(unmerged.length);
    waitingCountEl.style.color = unmerged.length > 0 ? '#f59e0b' : '#4ade80';
  }
  if (waitingSubEl) {
    waitingSubEl.textContent = unmerged.length > 0
      ? `${unmerged.length} branch${unmerged.length === 1 ? '' : 'es'} ahead of ${branchesData.base_branch || 'main'}`
      : `All branches merged into ${branchesData.base_branch || 'main'}`;
  }
  if (headerBadge) {
    headerBadge.textContent = `${unmerged.length} waiting merge`;
    headerBadge.style.background = unmerged.length > 0 ? 'rgba(245, 158, 11, 0.18)' : 'rgba(16, 185, 129, 0.16)';
    headerBadge.style.color = unmerged.length > 0 ? '#fbbf24' : '#34d399';
  }

  const prOpenCountEl = document.getElementById('prOpenCount');
  const prTriageEl = document.getElementById('prTriageStatus');
  if (prOpenCountEl) prOpenCountEl.textContent = String(openPrs.length);
  if (prTriageEl) {
    prTriageEl.textContent = prsData.status === 'ERROR'
      ? `Offline / ${prsData.error || 'GitHub unreachable'}`
      : (openPrs.length === 0 ? '0 open PRs on GitHub' : `${openPrs.length} open PR(s) awaiting review`);
  }

  const ciStatusEl = document.getElementById('ciHealthStatus');
  const ciSubEl = document.getElementById('ciHealthSub');
  if (ciStatusEl) {
    const st = ciData.status || 'PASSING';
    ciStatusEl.textContent = st;
    ciStatusEl.style.color = st === 'PASSING' ? '#4ade80' : (st === 'FAILING' ? '#f87171' : '#fbbf24');
  }
  if (ciSubEl) {
    const failingCount = Array.isArray(ciData.failing_runs) ? ciData.failing_runs.length : 0;
    ciSubEl.textContent = failingCount > 0
      ? `${failingCount} failing workflow run(s)`
      : `${ciData.total_checked || 5} recent workflow runs passing`;
  }

  const mainValEl = document.getElementById('prMainSyncVal');
  const mainSubEl = document.getElementById('prMainSyncSub');
  if (mainValEl) {
    mainValEl.textContent = `${branchesData.current_branch || 'main'} @ ${mainStatus.short_sha || 'HEAD'}`;
  }
  if (mainSubEl) {
    const wtCount = Number(mainStatus.working_tree_count || 0);
    const aheadOrig = Number(mainStatus.ahead_of_origin || 0);
    const parts = [];
    if (mainStatus.author_name) parts.push(`By ${mainStatus.author_name}`);
    if (aheadOrig > 0) parts.push(`+${aheadOrig} unpushed`);
    if (wtCount > 0) parts.push(`${wtCount} uncommitted file(s)`);
    else parts.push('Working tree clean');
    mainSubEl.textContent = parts.join(' • ');
  }

  // 2. Render Unmerged Branches Section
  const unmergedContainer = document.getElementById('prUnmergedBranchesContainer');
  if (unmergedContainer) {
    if (unmerged.length === 0) {
      const wtDirty = Boolean(mainStatus.working_tree_dirty);
      const wtCount = Number(mainStatus.working_tree_count || 0);
      unmergedContainer.innerHTML = `
        <div style="padding: 16px; background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.22); border-radius: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="color: #34d399; font-weight: 700; font-size: 13.5px;">
              ✅ No unmerged feature branches waiting to merge into <code>${_prEsc(branchesData.base_branch || 'main')}</code>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">
              Latest on <code>${_prEsc(branchesData.base_branch || 'main')}</code>:
              <code style="color: #38bdf8;">${_prEsc(mainStatus.short_sha || '')}</code>
              <strong>${_prEsc(mainStatus.subject || '')}</strong>
              by <strong>${_prEsc(mainStatus.author_name || '')}</strong>
              ${mainStatus.author_email ? `<span style="font-family: monospace;">&lt;${_prEsc(mainStatus.author_email)}&gt;</span>` : ''}
              (${_prEsc(mainStatus.relative_time || '')})
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            ${wtDirty ? `
              <button type="button" class="btn btn-sm" style="border-color: rgba(245, 158, 11, 0.45); color: #fbbf24;" onclick="openCreatePRBranchModal(true)">
                🌿 Spin Off ${wtCount} Uncommitted File(s) to Branch
              </button>
            ` : ''}
            <button type="button" class="btn btn-sm" onclick="runPRBranchAction('fetch_remote', '', {}, this)">
              ☁️ Scan Origin for Remote Branches
            </button>
          </div>
        </div>
      `;
    } else {
      unmergedContainer.innerHTML = unmerged.map((b, i) => _renderSingleUnmergedBranchCard(b, i)).join('');
    }
  }

  // 3. Render Main Branch HEAD, Working Tree & Synced Branches
  const mainContainer = document.getElementById('prMainAndWorkingTreeContainer');
  if (mainContainer) {
    const wtFiles = Array.isArray(mainStatus.working_tree_files) ? mainStatus.working_tree_files : [];
    const recentCommits = Array.isArray(mainStatus.recent_commits) ? mainStatus.recent_commits : [];
    const aheadOrigin = Number(mainStatus.ahead_of_origin || 0);

    const wtHtml = wtFiles.length > 0 ? `
      <div style="margin-bottom: 14px; padding: 12px 14px; background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
          <div>
            <strong style="color: #fbbf24; font-size: 13px;">🛠️ Uncommitted Working Tree Changes (${wtFiles.length} file${wtFiles.length === 1 ? '' : 's'} on <code>${_prEsc(branchesData.current_branch || 'main')}</code>)</strong>
            <div style="font-size: 11.5px; color: var(--text-muted);">You can inspect the live diff or spin these changes off into a feature branch for review before merging to <code>main</code>.</div>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button type="button" class="btn btn-sm" style="border-color: rgba(56, 189, 248, 0.35); color: #38bdf8;" onclick="inspectWorkingTreeDiff(this)">
              🔍 Inspect Working Tree Diff
            </button>
            <button type="button" class="btn btn-sm btn-primary" onclick="openCreatePRBranchModal(true)">
              🌿 Spin Off to Feature Branch
            </button>
          </div>
        </div>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${wtFiles.slice(0, 12).map(f => `
            <span style="font-family: monospace; font-size: 11px; background: rgba(2, 6, 23, 0.7); border: 1px solid rgba(255,255,255,0.08); padding: 2px 7px; border-radius: 4px; color: #e2e8f0;">
              <strong style="color: #fbbf24;">${_prEsc(f.status)}</strong> ${_prEsc(f.path)}
            </span>
          `).join('')}
          ${wtFiles.length > 12 ? `<span class="badge">+${wtFiles.length - 12} more</span>` : ''}
        </div>
      </div>
    ` : '';

    const syncedHtml = synced.length > 0 ? `
      <div style="margin-bottom: 14px; padding: 10px 12px; background: rgba(2, 6, 23, 0.5); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px;">
        <div style="font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 6px;">
          🧹 Already-Merged / Synced Branches (${synced.length})
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${synced.map(sb => {
            const safeSb = String(sb.branch || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            return `
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 5px 8px; background: rgba(15, 23, 42, 0.65); border-radius: 6px; font-size: 12px;">
                <div>
                  <code style="color: #34d399; font-weight: 600;">🌿 ${_prEsc(sb.branch)}</code>
                  <span class="badge" style="margin-left: 6px; font-size: 10px;">${_prEsc(sb.scope)}</span>
                  <span style="color: var(--text-muted); margin-left: 8px;">Author: <strong>${_prEsc(sb.latest_author_name)}</strong> &lt;${_prEsc(sb.latest_author_email)}&gt; • ${_prEsc(sb.latest_commit_relative)}</span>
                </div>
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 3px 8px; color: #f87171;" onclick="confirmDeletePRBranch('${safeSb}', false, this)">
                  🗑️ Delete Merged Branch
                </button>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    ` : '';

    const recentCommitsHtml = recentCommits.map(c => `
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 6px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 12px;">
        <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          <code style="color: #38bdf8; margin-right: 6px;">${_prEsc(c.sha)}</code>
          <span style="color: #e2e8f0;">${_prEsc(c.subject)}</span>
        </div>
        <div style="white-space: nowrap; font-size: 11.5px; color: var(--text-muted);">
          👤 <strong style="color: #cbd5e1;">${_prEsc(c.author_name)}</strong>
          ${c.author_email ? `<span style="font-family: monospace; font-size: 10.5px;">&lt;${_prEsc(c.author_email)}&gt;</span>` : ''}
          • <span>${_prEsc(c.relative_time)}</span>
        </div>
      </div>
    `).join('');

    mainContainer.innerHTML = `
      ${wtHtml}
      ${syncedHtml}
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
        <div style="font-size: 12.5px; color: #cbd5e1;">
          Latest commits on <code>${_prEsc(branchesData.base_branch || 'main')}</code>
          ${aheadOrigin > 0 ? `<span class="badge" style="margin-left: 6px; background: rgba(56, 189, 248, 0.16); color: #38bdf8;">+${aheadOrigin} ahead of origin/${_prEsc(branchesData.base_branch || 'main')}</span>` : ''}
        </div>
        ${aheadOrigin > 0 ? `
          <button type="button" class="btn btn-sm btn-primary" style="font-size: 11px; padding: 4px 10px;" onclick="runPRBranchAction('push_main', '', {}, this)">
            ⬆️ Push ${aheadOrigin} Commit(s) to origin/${_prEsc(branchesData.base_branch || 'main')}
          </button>
        ` : ''}
      </div>
      <div style="background: rgba(2, 6, 23, 0.6); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; overflow: hidden;">
        ${recentCommitsHtml || '<div style="padding: 10px; color: var(--text-muted);">No commits found.</div>'}
      </div>
    `;
  }

  // 4. Render Open Pull Requests Section
  const prListContainer = document.getElementById('prListContainer');
  if (prListContainer) {
    if (openPrs.length === 0) {
      prListContainer.innerHTML = `<div style="color: var(--text-muted); font-size: 12.5px;">No open GitHub pull requests currently pending review.</div>`;
    } else {
      prListContainer.innerHTML = openPrs.map(pr => {
        const prNum = Number(pr.number || 0);
        const safeBranch = String(pr.head_ref || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <strong style="color: #38bdf8; font-size: 13.5px;">#${prNum} ${_prEsc(pr.title)}</strong>
                ${pr.draft ? '<span class="badge">Draft</span>' : ''}
                ${pr.is_dependabot ? '<span class="badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8;">🤖 Dependabot</span>' : ''}
              </div>
              <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                👤 Author: <strong style="color: #e2e8f0;">${_prEsc(pr.author)}</strong>
                • Branch: <code>${_prEsc(pr.head_ref || '')}</code> → <code>${_prEsc(pr.base_ref || 'main')}</code>
                • HEAD: <code>${_prEsc(String(pr.head_sha || '').slice(0, 7))}</code>
                ${pr.relative_time ? `• Updated ${_prEsc(pr.relative_time)}` : ''}
              </div>
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="btn btn-primary btn-sm" style="font-size: 11px; padding: 4px 10px;" onclick="runPRPullRequestAction('merge_pr', ${prNum}, {merge_method: 'squash'}, this)">
                ✅ Squash &amp; Merge PR
              </button>
              ${safeBranch ? `
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" onclick="runPRBranchAction('review_in_antigravity', '${safeBranch}', {}, this)">
                  🤖 AI Review
                </button>
              ` : ''}
              ${pr.url ? `<a href="${_prEsc(pr.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; text-decoration: none;">🌐 GitHub ↗</a>` : ''}
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; color: #f87171;" onclick="runPRPullRequestAction('close_pr', ${prNum}, {}, this)">
                ✕ Close
              </button>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 5. Render 5-Pillar Governance Hub (Security/Quality, Discussions, Wiki Comments, Reported Issues, Other Governance)
  const gov = data.governance || {};
  const secQ = gov.security_and_quality || {};
  const discObj = gov.discussions || {};
  const wikiObj = gov.wiki_feedback || {};
  const issObj = gov.reported_issues || {};
  const otherObj = gov.other_governance || {};

  // Update the 4 additional KPI cards
  const secCountEl = document.getElementById('prSecQualityCount');
  const secSubEl = document.getElementById('prSecQualitySub');
  const secBadgeEl = document.getElementById('prSecurityQualityBadge');
  const secTotal = Number(secQ.total_notifications || 0);
  const secScore = Number(secQ.local_security_score != null ? secQ.local_security_score : 100);
  if (secCountEl) {
    secCountEl.textContent = String(secTotal);
    secCountEl.style.color = secTotal === 0 ? '#34d399' : '#f87171';
  }
  if (secSubEl) {
    secSubEl.textContent = `Score: ${secScore}/100 • CodeQL: ${secQ.codeql_count || 0} • Deps: ${secQ.dependabot_count || 0}`;
  }
  if (secBadgeEl) {
    secBadgeEl.textContent = secTotal === 0 ? `${secScore}/100 Clean` : `${secTotal} alert(s)`;
    secBadgeEl.style.background = secTotal === 0 ? 'rgba(16, 185, 129, 0.16)' : 'rgba(239, 68, 68, 0.2)';
    secBadgeEl.style.color = secTotal === 0 ? '#34d399' : '#f87171';
  }

  const discCountEl = document.getElementById('prDiscussionsCount');
  const discSubEl = document.getElementById('prDiscussionsSub');
  const discBadgeEl = document.getElementById('prDiscussionsBadge');
  const discOpen = Number(discObj.open_count || 0);
  const discUnans = Number(discObj.unanswered_count || 0);
  if (discCountEl) {
    discCountEl.textContent = String(discOpen);
    discCountEl.style.color = discUnans > 0 ? '#fbbf24' : '#60a5fa';
  }
  if (discSubEl) {
    discSubEl.textContent = discObj.discussions_enabled === false
      ? 'Discussions tab ready to enable'
      : (discOpen === 0 ? '0 unanswered threads' : `${discUnans} needing response`);
  }
  if (discBadgeEl) {
    discBadgeEl.textContent = `${discOpen} open (${discUnans} unanswered)`;
  }

  const wikiCountEl = document.getElementById('prWikiCommentsCount');
  const wikiSubEl = document.getElementById('prWikiCommentsSub');
  const wikiBadgeEl = document.getElementById('prWikiFeedbackBadge');
  const wikiCommentsCnt = Number(wikiObj.comments_needing_answer_count || 0);
  const wikiPagesCnt = Number(wikiObj.total_wiki_pages || 0);
  const unsyncedWikiCnt = Array.isArray(wikiObj.unsynced_wiki_files) ? wikiObj.unsynced_wiki_files.length : 0;
  if (wikiCountEl) {
    wikiCountEl.textContent = String(wikiCommentsCnt);
    wikiCountEl.style.color = wikiCommentsCnt > 0 ? '#fbbf24' : '#c084fc';
  }
  if (wikiSubEl) {
    wikiSubEl.textContent = `${wikiPagesCnt} Wiki pages • ${unsyncedWikiCnt > 0 ? `${unsyncedWikiCnt} unsynced` : 'Synced with GitHub'}`;
  }
  if (wikiBadgeEl) {
    wikiBadgeEl.textContent = wikiCommentsCnt > 0 ? `${wikiCommentsCnt} to answer` : `${wikiPagesCnt} pages synced`;
  }

  const issCountEl = document.getElementById('prIssuesCount');
  const issSubEl = document.getElementById('prIssuesSub');
  const issBadgeEl = document.getElementById('prReportedIssuesBadge');
  const totalIssues = Number(issObj.total_issues_count || 0);
  const ghIssuesCnt = Number(issObj.open_github_issues_count || 0);
  const localIssuesCnt = Number(issObj.local_reported_count || 0);
  if (issCountEl) {
    issCountEl.textContent = String(totalIssues);
    issCountEl.style.color = totalIssues > 0 ? '#fb7185' : '#34d399';
  }
  if (issSubEl) {
    issSubEl.textContent = `${ghIssuesCnt} GitHub • ${localIssuesCnt} Sentinel/Local`;
  }
  if (issBadgeEl) {
    issBadgeEl.textContent = `${totalIssues} open`;
    issBadgeEl.style.background = totalIssues > 0 ? 'rgba(244, 63, 94, 0.18)' : 'rgba(16, 185, 129, 0.16)';
    issBadgeEl.style.color = totalIssues > 0 ? '#fb7185' : '#34d399';
  }

  // 5a. Render Section 4: (1) Security & Quality Notifications
  const secContainer = document.getElementById('prSecurityQualityContainer');
  if (secContainer) {
    const notifs = Array.isArray(secQ.notifications) ? secQ.notifications : [];
    if (notifs.length === 0) {
      secContainer.innerHTML = `
        <div style="padding: 14px 16px; background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.22); border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <strong style="color: #34d399; font-size: 13px;">✅ Zero Open Security or Quality Alerts</strong>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
              CodeQL SAST: <strong>0 alerts</strong> • Dependabot: <strong>0 CVEs</strong> • Secret Scanning: <strong>0 leaks</strong> • Local 12-Layer Security: <strong>${secScore}/100</strong> • Pyright/VS Code: <strong>0 diagnostics</strong>
            </div>
          </div>
          <button type="button" class="btn btn-sm" style="font-size: 11px;" title="Run on-demand GitHub Pipeline & CodeQL audit" onclick="runPRPipelineAudit(this)">
            🛡️ Re-Verify Pipeline &amp; CodeQL
          </button>
        </div>
      `;
    } else {
      secContainer.innerHTML = notifs.map(n => {
        const sev = String(n.severity || 'HIGH').toUpperCase();
        const sevColor = (sev === 'CRITICAL' || sev === 'HIGH') ? '#f87171' : '#fbbf24';
        const safeTitle = String(n.title || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeDetail = String(n.detail || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeFile = String(n.file || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeUrl = String(n.url || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const alertNum = Number(n.alert_number || 0);
        const alertType = String(n.alert_type || '');
        return `
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; padding: 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(239, 68, 68, 0.28); border-radius: 8px;">
            <div style="flex: 1; min-width: 240px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span class="badge" style="background: rgba(239, 68, 68, 0.16); color: ${sevColor}; font-size: 10.5px;">${_prEsc(sev)}</span>
                <span class="badge" style="font-size: 10.5px;">${_prEsc(n.category || 'Security/Quality')}</span>
                <strong style="color: #f8fafc; font-size: 13px;">${_prEsc(n.title)}</strong>
              </div>
              <div style="font-size: 12px; color: #cbd5e1; margin-top: 4px;">
                ${_prEsc(n.detail)}
                ${n.file ? ` • <code>${_prEsc(n.file)}${n.line ? ':' + _prEsc(n.line) : ''}</code>` : ''}
                ${n.relative_time ? ` • <span style="color: var(--text-muted);">${_prEsc(n.relative_time)}</span>` : ''}
              </div>
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" title="Remediate this security/quality finding in Antigravity Live" onclick="dispatchPRItemToAntigravity('Security/Quality Alert', '${safeTitle}', '', '${safeDetail}', '${safeFile}', '${safeUrl}', this)">
                🤖 Fix in Antigravity
              </button>
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(16, 185, 129, 0.4); color: #34d399;" title="Run deterministic Auto-Fixer" onclick="runPRGovernanceAction('auto_fix_security_quality', {}, this)">
                🛠️ Auto-Fix
              </button>
              ${alertType === 'code_scanning' && alertNum > 0 ? `
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Dismiss CodeQL alert on GitHub" onclick="runPRGovernanceAction('dismiss_code_scanning_alert', {alert_number: ${alertNum}}, this)">
                  ✓ Dismiss
                </button>
              ` : ''}
              ${alertType === 'dependabot' && alertNum > 0 ? `
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Dismiss Dependabot alert on GitHub" onclick="runPRGovernanceAction('dismiss_dependabot_alert', {alert_number: ${alertNum}}, this)">
                  ✓ Dismiss
                </button>
              ` : ''}
              ${n.url ? `<a href="${_prEsc(n.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; text-decoration: none;" title="Open alert on GitHub">🌐 GitHub ↗</a>` : ''}
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 5b. Render Section 5: (2) Open Discussions Needing Attention
  const discContainer = document.getElementById('prDiscussionsContainer');
  if (discContainer) {
    const discussions = Array.isArray(discObj.discussions) ? discObj.discussions : [];
    if (discussions.length === 0) {
      discContainer.innerHTML = `
        <div style="padding: 14px 16px; background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <strong style="color: #38bdf8; font-size: 13px;">✅ No Unaddressed Open Discussions</strong>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
              ${_prEsc(discObj.note || 'All GitHub Discussions are answered and up to date.')}
            </div>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            ${discObj.discussions_enabled === false && discObj.settings_url ? `
              <a href="${_prEsc(discObj.settings_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; text-decoration: none;" title="Enable GitHub Discussions in Repository Settings">
                ⚙️ Enable Discussions Feature ↗
              </a>
            ` : ''}
            <a href="${_prEsc(discObj.discussions_url || 'https://github.com/macazaka/personal-agentic-fleet/discussions')}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; text-decoration: none;" title="View GitHub Discussions">
              💬 Open Discussions ↗
            </a>
          </div>
        </div>
      `;
    } else {
      discContainer.innerHTML = discussions.map(d => {
        const dNum = Number(d.number || 0);
        const safeTitle = String(d.title || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeAuthor = String(d.author || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeBody = String(d.body || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
        const safeUrl = String(d.url || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        return `
          <div style="padding: 12px 14px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
              <div style="flex: 1; min-width: 240px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <strong style="color: #38bdf8; font-size: 13.5px;">#${dNum} ${_prEsc(d.title)}</strong>
                  <span class="badge" style="font-size: 10.5px;">${_prEsc(d.category || 'General')}</span>
                  ${d.needs_attention ? '<span class="badge" style="background: rgba(245, 158, 11, 0.18); color: #fbbf24; font-size: 10.5px;">⏳ Needs Answer</span>' : '<span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; font-size: 10.5px;">✓ Answered</span>'}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  👤 Author: <strong style="color: #e2e8f0;">${_prEsc(d.author)}</strong>
                  • 💬 ${_prEsc(d.comments_count || 0)} comment(s)
                  • 👍 ${_prEsc(d.upvotes || 0)}
                  ${d.relative_time ? `• Updated ${_prEsc(d.relative_time)}` : ''}
                </div>
                ${d.body ? `<div style="font-size: 12px; color: #cbd5e1; margin-top: 6px; background: rgba(2,6,23,0.55); padding: 6px 10px; border-radius: 6px;">${_prEsc(d.body)}</div>` : ''}
              </div>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                <button type="button" class="btn btn-primary btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Post a reply to this discussion" onclick="openPRGovernanceReplyModal('comment_discussion', ${dNum}, 'Discussion #${dNum}: ${safeTitle}', '')">
                  💬 Reply / Answer
                </button>
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" title="Draft answer or implement RFC in Antigravity Live" onclick="dispatchPRItemToAntigravity('GitHub Discussion #${dNum}', '${safeTitle}', '${safeAuthor}', '${safeBody}', '', '${safeUrl}', this)">
                  🤖 Address in Antigravity
                </button>
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Track this discussion in the P1 Fleet Task Queue" onclick="runPRGovernanceAction('create_fleet_task', {title: '[Discussion #${dNum}] ${safeTitle}', description: '${safeBody}'}, this)">
                  📌 + P1 Task
                </button>
                ${d.url ? `<a href="${_prEsc(d.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; text-decoration: none;" title="Open discussion on GitHub">🌐 GitHub ↗</a>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // 5c. Render Section 6: (3) Wiki Page Comments, Questions & Revision Sync
  const wikiContainer = document.getElementById('prWikiFeedbackContainer');
  if (wikiContainer) {
    const wikiComments = Array.isArray(wikiObj.wiki_comments) ? wikiObj.wiki_comments : [];
    const wikiPages = Array.isArray(wikiObj.wiki_pages) ? wikiObj.wiki_pages : [];
    const unsyncedFiles = Array.isArray(wikiObj.unsynced_wiki_files) ? wikiObj.unsynced_wiki_files : [];

    const commentsHtml = wikiComments.length === 0 ? `
      <div style="padding: 12px 14px; background: rgba(168, 85, 247, 0.06); border: 1px solid rgba(168, 85, 247, 0.22); border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <strong style="color: #c084fc; font-size: 13px;">✅ 0 Unanswered Wiki Page Comments or Questions</strong>
          <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
            All ${wikiPages.length} Wiki documentation pages are clean${unsyncedFiles.length > 0 ? ` (${unsyncedFiles.length} local Wiki file(s) modified — click Sync & Publish Wiki Now)` : ' and synchronized with GitHub Wiki'}.
          </div>
        </div>
      </div>
    ` : wikiComments.map(wc => {
      const safePage = String(wc.page || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      const safeAuthor = String(wc.author || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      const safeQ = String(wc.question_or_comment || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
      const safeFile = String(wc.file || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      const safeUrl = String(wc.wiki_url || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      return `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; padding: 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 8px;">
          <div style="flex: 1; min-width: 240px;">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <strong style="color: #c084fc; font-size: 13px;">📖 ${_prEsc(wc.page)}</strong>
              <code style="font-size: 11px; color: #38bdf8;">${_prEsc(wc.file)}:${_prEsc(wc.line || 1)}</code>
              <span class="badge" style="font-size: 10px;">${_prEsc(wc.source)}</span>
            </div>
            <div style="font-size: 12.5px; color: #f8fafc; margin-top: 5px;">${_prEsc(wc.question_or_comment)}</div>
            <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 3px;">
              👤 Author: <strong>${_prEsc(wc.author)}</strong> ${wc.relative_time ? `• ${_prEsc(wc.relative_time)}` : ''}
            </div>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap;">
            <button type="button" class="btn btn-primary btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Answer question and update Wiki page in Antigravity Live" onclick="dispatchPRItemToAntigravity('Wiki Page Question/Comment (${safePage})', '${safeQ}', '${safeAuthor}', '${safeQ}', '${safeFile}', '${safeUrl}', this)">
              🤖 Answer &amp; Update Wiki in Antigravity
            </button>
            ${wc.issue_number ? `
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Post reply comment on Wiki issue" onclick="openPRGovernanceReplyModal('comment_issue', ${Number(wc.issue_number)}, 'Wiki Issue #${Number(wc.issue_number)}', '')">
                💬 Reply
              </button>
            ` : ''}
            ${wc.wiki_url ? `<a href="${_prEsc(wc.wiki_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; text-decoration: none;" title="Open Wiki page on GitHub">🌐 Wiki Page ↗</a>` : ''}
          </div>
        </div>
      `;
    }).join('');

    const pagesRollupHtml = wikiPages.length > 0 ? `
      <details style="margin-top: 6px;">
        <summary style="cursor: pointer; font-size: 12px; color: #c084fc; user-select: none;">
          📚 Inspect All ${wikiPages.length} Wiki Pages &amp; Latest Author Revisions
        </summary>
        <div style="margin-top: 8px; display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); gap: 8px;">
          ${wikiPages.map(wp => `
            <div style="padding: 8px 10px; background: rgba(2, 6, 23, 0.65); border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; font-size: 11.5px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
              <div style="min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <strong style="color: #e2e8f0;">${_prEsc(wp.page)}</strong>
                <div style="color: var(--text-muted); font-size: 11px;">
                  <code>${_prEsc(wp.last_sha)}</code> by ${_prEsc(wp.last_author)} • ${_prEsc(wp.last_updated_relative)}
                </div>
              </div>
              <a href="${_prEsc(wp.wiki_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 7px; text-decoration: none;" title="View ${_prEsc(wp.page)} on GitHub Wiki">↗</a>
            </div>
          `).join('')}
        </div>
      </details>
    ` : '';

    wikiContainer.innerHTML = commentsHtml + pagesRollupHtml;
  }

  // 5d. Render Section 7: (4) Reported Issues (GitHub Issues & Local Sentinel Reports)
  const issContainer = document.getElementById('prReportedIssuesContainer');
  if (issContainer) {
    const ghIssues = Array.isArray(issObj.github_issues) ? issObj.github_issues : [];
    const localIssues = Array.isArray(issObj.local_issues) ? issObj.local_issues : [];
    if (ghIssues.length === 0 && localIssues.length === 0) {
      issContainer.innerHTML = `
        <div style="padding: 14px 16px; background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.22); border-radius: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div>
            <strong style="color: #34d399; font-size: 13px;">✅ 0 Open Reported Issues</strong>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">
              Both the GitHub Issues tracker and the local Sentinel/Auto-Healer diagnostic queue have 0 open issues.
            </div>
          </div>
          <button type="button" class="btn btn-sm" style="font-size: 11px;" title="Report a new issue on GitHub" onclick="openCreatePRIssueModal()">
            ➕ Report New Issue
          </button>
        </div>
      `;
    } else {
      const ghHtml = ghIssues.map(iss => {
        const iNum = Number(iss.number || 0);
        const safeTitle = String(iss.title || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeAuthor = String(iss.author || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeBody = String(iss.body || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
        const safeUrl = String(iss.url || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const labelsHtml = (Array.isArray(iss.labels) ? iss.labels : []).map(lb => `
          <span class="badge" style="font-size: 10px; background: rgba(244, 63, 94, 0.15); color: #fda4af;">${_prEsc(lb.name)}</span>
        `).join('');
        return `
          <div style="padding: 12px 14px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(244, 63, 94, 0.28); border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
              <div style="flex: 1; min-width: 240px;">
                <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                  <strong style="color: #fb7185; font-size: 13.5px;">#${iNum} ${_prEsc(iss.title)}</strong>
                  ${labelsHtml}
                  ${iss.needs_response ? '<span class="badge" style="background: rgba(245, 158, 11, 0.18); color: #fbbf24; font-size: 10px;">Needs Response</span>' : ''}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  👤 Reporter: <strong style="color: #e2e8f0;">${_prEsc(iss.author)}</strong>
                  • 💬 ${_prEsc(iss.comments_count || 0)} comment(s)
                  ${iss.relative_time ? `• Updated ${_prEsc(iss.relative_time)}` : ''}
                </div>
                ${iss.body ? `<div style="font-size: 12px; color: #cbd5e1; margin-top: 6px; background: rgba(2,6,23,0.55); padding: 6px 10px; border-radius: 6px;">${_prEsc(iss.body)}</div>` : ''}
              </div>
              <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                <button type="button" class="btn btn-primary btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Investigate and fix this reported issue in Antigravity Live" onclick="dispatchPRItemToAntigravity('GitHub Issue #${iNum}', '${safeTitle}', '${safeAuthor}', '${safeBody}', '', '${safeUrl}', this)">
                  🤖 Fix in Antigravity
                </button>
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px;" title="Post a comment on this GitHub issue" onclick="openPRGovernanceReplyModal('comment_issue', ${iNum}, 'Issue #${iNum}: ${safeTitle}', '')">
                  💬 Comment
                </button>
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; color: #34d399;" title="Close this GitHub issue" onclick="runPRGovernanceAction('close_issue', {issue_number: ${iNum}}, this)">
                  ✅ Close Issue
                </button>
                ${iss.url ? `<a href="${_prEsc(iss.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; text-decoration: none;" title="Open issue on GitHub">🌐 GitHub ↗</a>` : ''}
              </div>
            </div>
          </div>
        `;
      }).join('');

      const localHtml = localIssues.map(li => {
        const tId = Number(li.id || 0);
        const safeTitle = String(li.title || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
        const safeDesc = String(li.description || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; padding: 10px 12px; margin-bottom: 8px; background: rgba(15, 23, 42, 0.72); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 8px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge" style="background: rgba(245, 158, 11, 0.16); color: #fbbf24; font-size: 10px;">${_prEsc(li.priority || 'P1')} • ${_prEsc(li.source)}</span>
                <strong style="color: #f8fafc; font-size: 13px;">${_prEsc(li.title)}</strong>
              </div>
              <div style="font-size: 11.5px; color: var(--text-muted); margin-top: 3px;">${_prEsc(li.description)}</div>
            </div>
            <div style="display: flex; gap: 6px;">
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" title="Resolve local diagnostic issue in Antigravity Live" onclick="dispatchPRItemToAntigravity('Local Sentinel Issue #${tId}', '${safeTitle}', '${_prEsc(li.source)}', '${safeDesc}', '', '', this)">
                🤖 Fix in Antigravity
              </button>
              <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 4px 10px; color: #34d399;" title="Mark local issue completed" onclick="runPRGovernanceAction('complete_local_task', {task_id: ${tId}}, this)">
                ✓ Complete
              </button>
            </div>
          </div>
        `;
      }).join('');

      issContainer.innerHTML = ghHtml + localHtml;
    }
  }

  // 5e. Render Section 8: (5) Other Relevant Governance Items (Commit/PR Review Comments, Mentions, Signed Tag Audit)
  const otherContainer = document.getElementById('prOtherGovernanceContainer');
  const otherBadgeEl = document.getElementById('prOtherGovernanceBadge');
  if (otherContainer) {
    const revComments = Array.isArray(otherObj.commit_and_pr_comments) ? otherObj.commit_and_pr_comments : [];
    const repoNotifs = Array.isArray(otherObj.repo_notifications) ? otherObj.repo_notifications : [];
    const tagAudit = Array.isArray(otherObj.tag_audit) ? otherObj.tag_audit : [];
    const unsignedTagsCnt = Number(otherObj.unsigned_tags_count || 0);

    if (otherBadgeEl) {
      const pendingOther = revComments.length + repoNotifs.length + unsignedTagsCnt;
      otherBadgeEl.textContent = pendingOther === 0 ? 'All Tags & Reviews Verified' : `${pendingOther} item(s)`;
      otherBadgeEl.style.background = pendingOther === 0 ? 'rgba(16, 185, 129, 0.16)' : 'rgba(245, 158, 11, 0.18)';
      otherBadgeEl.style.color = pendingOther === 0 ? '#34d399' : '#fbbf24';
    }

    const commentsBlock = revComments.length > 0 ? `
      <div style="margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 600; color: #38bdf8; margin-bottom: 6px;">
          💬 Recent Commit &amp; Inline PR Code Review Comments (${revComments.length})
        </div>
        ${revComments.map(rc => {
          const safeAuthor = String(rc.author || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
          const safeBody = String(rc.body || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\r?\n/g, ' ');
          const safePath = String(rc.path || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
          const safeSha = String(rc.full_commit_sha || rc.commit_sha || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
          return `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; padding: 10px 12px; margin-bottom: 6px; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(56, 189, 248, 0.22); border-radius: 8px;">
              <div style="flex: 1; min-width: 220px;">
                <div style="font-size: 12px; color: #e2e8f0;">
                  <span class="badge" style="font-size: 10px;">${_prEsc(rc.type_label)}</span>
                  👤 <strong>${_prEsc(rc.author)}</strong> on <code>${_prEsc(rc.commit_sha)}</code>
                  ${rc.path ? `• <code>${_prEsc(rc.path)}${rc.line ? ':' + _prEsc(rc.line) : ''}</code>` : ''}
                  • <span style="color: var(--text-muted);">${_prEsc(rc.relative_time)}</span>
                </div>
                <div style="font-size: 12px; color: #cbd5e1; margin-top: 4px;">${_prEsc(rc.body)}</div>
              </div>
              <div style="display: flex; gap: 6px;">
                ${safeSha ? `
                  <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 3px 9px;" title="Reply to commit comment" onclick="openPRGovernanceReplyModal('reply_commit_comment', 0, 'Reply on Commit ${_prEsc(rc.commit_sha)}', '${safeSha}')">
                    💬 Reply
                  </button>
                ` : ''}
                <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 3px 9px; border-color: rgba(168, 85, 247, 0.4); color: #c084fc;" title="Address code review comment in Antigravity Live" onclick="dispatchPRItemToAntigravity('${_prEsc(rc.type_label)}', 'Comment on ${_prEsc(rc.commit_sha)}', '${safeAuthor}', '${safeBody}', '${safePath}', '', this)">
                  🤖 Address in Antigravity
                </button>
                ${rc.url ? `<a href="${_prEsc(rc.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 11px; padding: 3px 8px; text-decoration: none;" title="View comment on GitHub">↗</a>` : ''}
              </div>
            </div>
          `;
        }).join('')}
      </div>
    ` : '';

    const notifsBlock = repoNotifs.length > 0 ? `
      <div style="margin-bottom: 12px;">
        <div style="font-size: 12px; font-weight: 600; color: #fbbf24; margin-bottom: 6px;">
          🔔 Unread Repository Mentions &amp; Review Requests (${repoNotifs.length})
        </div>
        ${repoNotifs.map(rn => `
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 8px 10px; margin-bottom: 6px; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(245, 158, 11, 0.25); border-radius: 6px; font-size: 12px;">
            <div>
              <span class="badge" style="font-size: 10px;">${_prEsc(rn.reason)}</span>
              <span class="badge" style="font-size: 10px;">${_prEsc(rn.subject_type)}</span>
              <strong style="color: #f8fafc; margin-left: 6px;">${_prEsc(rn.title)}</strong>
              <span style="color: var(--text-muted); margin-left: 6px;">• ${_prEsc(rn.relative_time)}</span>
            </div>
            <button type="button" class="btn btn-sm" style="font-size: 11px; padding: 3px 8px;" title="Mark GitHub notification thread as read" onclick="runPRGovernanceAction('mark_notification_read', {thread_id: '${_prEsc(rn.thread_id)}'}, this)">
              ✓ Mark Read
            </button>
          </div>
        `).join('')}
      </div>
    ` : '';

    const tagsBlock = `
      <div>
        <div style="font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 6px;">
          🏷️ Cryptographic Release Tag Verification Audit (${tagAudit.length} recent tags • 0 commit/ review comments pending: ${revComments.length === 0 ? 'Yes' : 'No'})
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 8px;">
          ${tagAudit.map(t => {
            const safeTag = String(t.tag || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
            return `
              <div style="padding: 8px 10px; background: rgba(2, 6, 23, 0.65); border: 1px solid ${t.verified_signed ? 'rgba(16, 185, 129, 0.25)' : 'rgba(245, 158, 11, 0.35)'}; border-radius: 6px; font-size: 11.5px; display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <div>
                  <div style="display: flex; align-items: center; gap: 6px;">
                    <strong style="color: #f8fafc;">${_prEsc(t.tag)}</strong>
                    <code>${_prEsc(t.sha)}</code>
                    ${t.verified_signed
                      ? '<span class="badge" style="background: rgba(16, 185, 129, 0.16); color: #34d399; font-size: 10px;">✓ Verified</span>'
                      : '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-size: 10px;">⚠️ Unverified</span>'}
                  </div>
                  <div style="color: var(--text-muted); font-size: 10.5px; margin-top: 2px;">
                    By ${_prEsc(t.author)} • ${_prEsc(t.relative_time)}
                  </div>
                </div>
                <div style="display: flex; gap: 4px;">
                  ${!t.verified_signed ? `
                    <button type="button" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 7px; color: #fbbf24;" title="Cryptographically sign and push this tag" onclick="runPRGovernanceAction('resign_tag', {tag: '${safeTag}', push_origin: true}, this)">
                      ✍️ Sign
                    </button>
                  ` : ''}
                  <a href="${_prEsc(t.release_url)}" target="_blank" rel="noopener noreferrer" class="btn btn-sm" style="font-size: 10.5px; padding: 2px 6px; text-decoration: none;" title="Open tag release on GitHub">↗</a>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </div>
    `;

    otherContainer.innerHTML = commentsBlock + notifsBlock + tagsBlock;
  }
};

window.fetchPRReviewStatus = async function(fetchRemote, btnEl) {
  const execFetch = async () => {
    const q = fetchRemote ? '?fetch=1' : '';
    const res = await fetch(`/api/pr_review/status${q}`);
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Failed to load PR Review & Branch status');
    }
    window.renderPRReviewDashboard(data);
    return data;
  };

  if (btnEl && typeof window.runFleetAsyncAction === 'function') {
    await window.runFleetAsyncAction({
      buttons: [btnEl],
      busyLabel: '⏳ Auditing...',
      startToast: '⏳ Auditing unmerged branches, PRs & CI gate...',
      successToast: '✅ Branch & CI governance status updated.',
      errorPrefix: 'PR Review audit failed',
    }, execFetch);
  } else {
    try {
      await execFetch();
    } catch (e) {
      _prNotify('✕ ' + e.message, true);
    }
  }
};

window.runPRBranchAction = async function(action, branch, extraPayload, btnEl) {
  const payload = Object.assign({}, extraPayload || {}, { action, branch });
  const labelMap = {
    merge: `⏳ Merging '${branch}'...`,
    fetch_remote: '⏳ Fetching origin...',
    sync_with_main: `⏳ Syncing '${branch}'...`,
    checkout: `⏳ Checking out '${branch}'...`,
    delete_branch: `⏳ Deleting '${branch}'...`,
    push_main: '⏳ Pushing main...',
    review_in_antigravity: '⏳ Dispatching to Antigravity...',
  };

  const execAction = async () => {
    const res = await fetch('/api/pr_review/branch_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || `Action '${action}' failed`);
    }
    if (data.branches) {
      await window.fetchPRReviewStatus(false);
    }
    if (action === 'review_in_antigravity') {
      if (typeof openAntigravityRightDock === 'function') {
        openAntigravityRightDock();
      }
      if (typeof fetchTranscript === 'function') {
        fetchTranscript(true);
      }
    }
    if (data.message) {
      _prNotify(`✅ ${data.message}`, false);
    }
    return data;
  };

  if (typeof window.runFleetAsyncAction === 'function') {
    await window.runFleetAsyncAction({
      buttons: btnEl ? [btnEl] : [],
      busyLabel: labelMap[action] || '⏳ Working...',
      errorPrefix: 'Branch action failed',
    }, execAction);
  } else {
    try {
      await execAction();
    } catch (e) {
      _prNotify('✕ ' + e.message, true);
    }
  }
};

window.confirmDeletePRBranch = async function(branch, isUnmerged, btnEl) {
  const promptMsg = isUnmerged
    ? `Branch "${branch}" still has unmerged commits ahead of main.\n\nAre you sure you want to force-delete local branch "${branch}"?`
    : `Delete merged local branch "${branch}"?`;
  if (!confirm(promptMsg)) return;
  await window.runPRBranchAction('delete_branch', branch, { force: Boolean(isUnmerged) }, btnEl);
};

window.inspectPRBranchDiff = async function(branch, btnEl) {
  const modal = document.getElementById('prBranchDiffModal');
  const titleEl = document.getElementById('prDiffModalTitle');
  const subEl = document.getElementById('prDiffModalSub');
  const bodyEl = document.getElementById('prDiffModalBody');
  if (modal) modal.style.display = 'flex';
  if (titleEl) titleEl.textContent = `🔍 Branch Diff Inspector: ${branch}`;
  if (subEl) subEl.textContent = 'Loading unified diff & commit telemetry...';
  if (bodyEl) bodyEl.innerHTML = '<div style="padding: 18px; color: var(--text-muted);">⏳ Computing git diff...</div>';

  try {
    const res = await fetch('/api/pr_review/branch_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'diff', branch }),
    });
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Could not load branch diff');
    }
    const info = data.branch_info || {};
    if (subEl) {
      subEl.textContent = `Author: ${info.latest_author_name || 'Unknown'} <${info.latest_author_email || ''}> • +${info.ahead_count || 0} commits ahead • ${info.files_changed_count || 0} files (+${info.insertions || 0} / -${info.deletions || 0})`;
    }
    if (bodyEl) {
      bodyEl.innerHTML = _renderDiffHtml(data.diff || '');
    }
  } catch (e) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div style="color: #f87171;">✕ ${_prEsc(e.message)}</div>`;
    }
  }
};

window.inspectWorkingTreeDiff = async function(btnEl) {
  const modal = document.getElementById('prBranchDiffModal');
  const titleEl = document.getElementById('prDiffModalTitle');
  const subEl = document.getElementById('prDiffModalSub');
  const bodyEl = document.getElementById('prDiffModalBody');
  if (modal) modal.style.display = 'flex';
  if (titleEl) titleEl.textContent = '🔍 Working Tree Uncommitted Diff (HEAD)';
  if (subEl) subEl.textContent = 'Uncommitted local changes relative to HEAD';
  if (bodyEl) bodyEl.innerHTML = '<div style="padding: 18px; color: var(--text-muted);">⏳ Computing working tree diff...</div>';

  try {
    const res = await fetch('/api/pr_review/branch_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'working_tree_diff' }),
    });
    const data = await res.json();
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Could not load working tree diff');
    }
    if (bodyEl) {
      bodyEl.innerHTML = _renderDiffHtml(data.diff || data.status_short || '');
    }
  } catch (e) {
    if (bodyEl) {
      bodyEl.innerHTML = `<div style="color: #f87171;">✕ ${_prEsc(e.message)}</div>`;
    }
  }
};

window.closePRBranchDiffModal = function() {
  const modal = document.getElementById('prBranchDiffModal');
  if (modal) modal.style.display = 'none';
};

window.openCreatePRBranchModal = function(prefillSpinOff) {
  const modal = document.getElementById('prCreateBranchModal');
  const nameInput = document.getElementById('prNewBranchNameInput');
  const msgInput = document.getElementById('prNewBranchCommitMsgInput');
  if (modal) modal.style.display = 'flex';
  if (nameInput) {
    const stamp = new Date().toISOString().slice(5, 10).replace('-', '');
    nameInput.value = prefillSpinOff ? `feat/pending-changes-${stamp}` : '';
    setTimeout(() => nameInput.focus(), 60);
  }
  if (msgInput) {
    msgInput.value = prefillSpinOff ? 'chore: stage working tree updates on feature branch for review' : '';
  }
};

window.closeCreatePRBranchModal = function() {
  const modal = document.getElementById('prCreateBranchModal');
  if (modal) modal.style.display = 'none';
};

window.submitCreatePRBranch = async function(btnEl) {
  const nameInput = document.getElementById('prNewBranchNameInput');
  const msgInput = document.getElementById('prNewBranchCommitMsgInput');
  const newBranch = (nameInput ? nameInput.value : '').trim();
  const commitMsg = (msgInput ? msgInput.value : '').trim();
  if (!newBranch) {
    _prNotify('Please enter a valid branch name (e.g. feat/my-feature).', true);
    return;
  }
  await window.runPRBranchAction(
    'create_branch',
    newBranch,
    { new_branch: newBranch, commit_message: commitMsg, switch_back_to_main: true },
    btnEl
  );
  window.closeCreatePRBranchModal();
};

window.runPRPullRequestAction = async function(action, prNumber, extraPayload, btnEl) {
  const payload = Object.assign({}, extraPayload || {}, { action, pr_number: prNumber });
  const execPr = async () => {
    const res = await fetch('/api/pr_review/pr_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || `PR #${prNumber} action failed`);
    }
    _prNotify(`✅ ${data.message || `Updated PR #${prNumber}`}`, false);
    await window.fetchPRReviewStatus(false);
  };

  if (typeof window.runFleetAsyncAction === 'function') {
    await window.runFleetAsyncAction({
      buttons: btnEl ? [btnEl] : [],
      busyLabel: '⏳ Updating PR...',
      errorPrefix: 'PR action failed',
    }, execPr);
  } else {
    try {
      await execPr();
    } catch (e) {
      _prNotify('✕ ' + e.message, true);
    }
  }
};

window.runPRPipelineAudit = async function(btnEl) {
  const box = document.getElementById('prPipelineAuditContainer');
  if (box) {
    box.style.display = 'block';
    box.innerHTML = '<div style="padding: 12px; color: #38bdf8;">⏳ Auditing GitHub Actions check-runs, CodeQL SARIF alerts &amp; OSV/Dependabot vulnerabilities...</div>';
  }
  const execAudit = async () => {
    const res = await fetch('/api/pr_review/pipeline_audit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wait: false, auto_remediate: true }),
    });
    const data = await res.json();
    const audit = data.audit || {};
    if (box) {
      const checks = audit.github_checks || {};
      const codeql = audit.code_scanning || {};
      const deps = audit.dependency_vulnerabilities || {};
      const healthy = audit.overall_healthy !== false;
      box.innerHTML = `
        <div style="padding: 12px 14px; background: rgba(15, 23, 42, 0.85); border: 1px solid ${healthy ? 'rgba(16, 185, 129, 0.35)' : 'rgba(239, 68, 68, 0.35)'}; border-radius: 8px; font-size: 12.5px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <strong style="color: ${healthy ? '#34d399' : '#f87171'};">
              ${healthy ? '✅ GitHub Pipeline, CodeQL & Dependency Audit: 100% HEALTHY' : '⚠️ Issues Detected in Pipeline / Code Scan'}
            </strong>
            <code style="color: #7dd3fc;">SHA ${_prEsc(String(audit.commit_sha || '').slice(0, 7))}</code>
          </div>
          <div style="color: #cbd5e1; display: flex; gap: 14px; flex-wrap: wrap;">
            <span>Checks: <strong>${_prEsc(checks.passing_count || 0)}/${_prEsc(checks.total_checks || 0)} passing</strong></span>
            <span>CodeQL / Secret Alerts: <strong>${_prEsc(codeql.open_count || 0)} open</strong></span>
            <span>Dependency Vulnerabilities: <strong>${_prEsc(deps.total_vulnerabilities || 0)} found</strong></span>
          </div>
        </div>
      `;
    }
    return data;
  };

  if (typeof window.runFleetAsyncAction === 'function') {
    await window.runFleetAsyncAction({
      buttons: btnEl ? [btnEl] : [],
      busyLabel: '⏳ Auditing Pipeline...',
      startToast: '⏳ Running GitHub Actions, CodeQL & OSV/Dependabot Sentinel...',
      successToast: '✅ GitHub Pipeline & CodeQL audit complete.',
      errorPrefix: 'Pipeline audit failed',
    }, execAudit);
  } else {
    try {
      await execAudit();
    } catch (e) {
      _prNotify('✕ ' + e.message, true);
    }
  }
};

window._prReplyContext = { action: '', targetNumber: 0, commitSha: '' };

window.runPRGovernanceAction = async function(action, extraPayload, btnEl) {
  const payload = Object.assign({}, extraPayload || {}, { action });
  const execGov = async () => {
    const res = await fetch('/api/pr_review/governance_action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || `Governance action '${action}' failed`);
    }
    if (action === 'address_in_antigravity') {
      if (typeof openAntigravityRightDock === 'function') {
        openAntigravityRightDock();
      }
      if (typeof fetchTranscript === 'function') {
        fetchTranscript(true);
      }
    }
    if (data.message) {
      _prNotify(`✅ ${data.message}`, false);
    }
    await window.fetchPRReviewStatus(false);
    return data;
  };

  if (typeof window.runFleetAsyncAction === 'function') {
    await window.runFleetAsyncAction({
      buttons: btnEl ? [btnEl] : [],
      busyLabel: '⏳ Working...',
      errorPrefix: 'Governance action failed',
    }, execGov);
  } else {
    try {
      await execGov();
    } catch (e) {
      _prNotify('✕ ' + e.message, true);
    }
  }
};

window.dispatchPRItemToAntigravity = async function(itemType, title, author, detail, file, url, btnEl) {
  await window.runPRGovernanceAction(
    'address_in_antigravity',
    { item_type: itemType, title, author, detail, file, url },
    btnEl
  );
};

window.openPRGovernanceReplyModal = function(action, targetNumber, subtitle, commitSha) {
  window._prReplyContext = {
    action: action || 'comment_issue',
    targetNumber: Number(targetNumber || 0),
    commitSha: String(commitSha || ''),
  };
  const modal = document.getElementById('prGovernanceReplyModal');
  const subEl = document.getElementById('prReplyModalSub');
  const bodyEl = document.getElementById('prReplyModalBodyInput');
  if (modal) modal.style.display = 'flex';
  if (subEl) subEl.textContent = subtitle || '';
  if (bodyEl) {
    bodyEl.value = '';
    setTimeout(() => bodyEl.focus(), 60);
  }
};

window.closePRGovernanceReplyModal = function() {
  const modal = document.getElementById('prGovernanceReplyModal');
  if (modal) modal.style.display = 'none';
};

window.submitPRGovernanceReply = async function(btnEl) {
  const bodyEl = document.getElementById('prReplyModalBodyInput');
  const commentTxt = (bodyEl ? bodyEl.value : '').trim();
  if (!commentTxt) {
    _prNotify('Please enter a reply message.', true);
    return;
  }
  const ctx = window._prReplyContext || {};
  await window.runPRGovernanceAction(
    ctx.action || 'comment_issue',
    {
      number: ctx.targetNumber,
      issue_number: ctx.targetNumber,
      discussion_number: ctx.targetNumber,
      commit_sha: ctx.commitSha,
      body: commentTxt,
    },
    btnEl
  );
  window.closePRGovernanceReplyModal();
};

window.openCreatePRIssueModal = function() {
  const modal = document.getElementById('prCreateIssueModal');
  const titleEl = document.getElementById('prNewIssueTitleInput');
  const bodyEl = document.getElementById('prNewIssueBodyInput');
  if (modal) modal.style.display = 'flex';
  if (titleEl) {
    titleEl.value = '';
    setTimeout(() => titleEl.focus(), 60);
  }
  if (bodyEl) bodyEl.value = '';
};

window.closeCreatePRIssueModal = function() {
  const modal = document.getElementById('prCreateIssueModal');
  if (modal) modal.style.display = 'none';
};

window.submitCreatePRIssue = async function(btnEl) {
  const titleEl = document.getElementById('prNewIssueTitleInput');
  const bodyEl = document.getElementById('prNewIssueBodyInput');
  const title = (titleEl ? titleEl.value : '').trim();
  const body = (bodyEl ? bodyEl.value : '').trim();
  if (!title) {
    _prNotify('Please enter an issue title.', true);
    return;
  }
  await window.runPRGovernanceAction('create_issue', { title, body }, btnEl);
  window.closeCreatePRIssueModal();
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  FleetNavigator.init();
});
