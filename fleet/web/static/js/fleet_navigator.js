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
  pinnedIds: new Set(['health', 'overview', 'antigravity', 'backlog', 'optimizer']),
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
  activeAgentId: 'health',

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
        this.updateHeaderSummary();
        this.renderPinnedTray();
        this.renderLeftSidebarDock();
        this.renderLaunchpadMatrix();
        this.renderDrawerList();
        this.renderOperationsCenter();
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
        <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" style="font-size: 12px; padding: 0 3px;" onclick="FleetNavigator.togglePin('${a.id}', event)" title="${a.is_pinned ? 'Unpin' : 'Pin'}">
          ${a.is_pinned ? '★' : '☆'}
        </button>
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
          <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" style="font-size: 12px;" onclick="FleetNavigator.togglePin('${a.id}', event)">
            ${a.is_pinned ? '★' : '☆'}
          </button>
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
          <button class="btn-pin-star ${a.is_pinned ? 'pinned' : ''}" onclick="FleetNavigator.togglePin('${a.id}', event)">
            ${a.is_pinned ? '★' : '☆'}
          </button>
        </div>

        <p class="matrix-card-desc">${a.description || 'Fleet automated agent module.'}</p>

        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.06); font-size: 11.5px;">
          <span class="badge" style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}33;">
            ${statusLabel}
          </span>
          <span style="color: var(--text-muted);">${a.category}</span>
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
          <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="FleetNavigator.switchAgent('${a.id}')">Open Pane</button>
          <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="openAgentSettingsDrawer('${a.id}')">⚙️</button>
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
          <button class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="FleetNavigator.changePage(${this.currentPage - 1})" ${this.currentPage <= 1 ? 'disabled' : ''}>← Prev</button>
          <span style="padding: 0 8px;">Page <strong>${this.currentPage}</strong> of <strong>${totalPages}</strong></span>
          <button class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="FleetNavigator.changePage(${this.currentPage + 1})" ${this.currentPage >= totalPages ? 'disabled' : ''}>Next →</button>
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
      return;
    }

    // Custom or dynamic agent stage
    this.mountDynamicAgentPane(agentId);
    this.syncActiveTabUI(agentId);
  },

  mountDynamicAgentPane(agentId) {
    const agent = this.agents.find(a => a.id === agentId);
    if (!agent) {
      if (typeof switchTab === 'function') switchTab('overview');
      return;
    }

    // Hide all standard view divs
    ['viewOverview', 'viewAntigravity', 'viewHealth', 'viewBacklog', 'viewOptimizer'].forEach(id => {
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
    if (bc) bc.innerHTML = `<span style="font-size: 20px;">${agent.icon || '⚡'}</span> <strong>${agent.name}</strong> <span style="font-size: 12px; color: var(--text-muted); font-family: monospace;">(${agent.id})</span>`;
    if (bcCat) bcCat.textContent = agent.category;
    if (bcStatus) {
      const isWorking = agent.status === 'working';
      bcStatus.className = `badge ${isWorking ? 'badge-success' : 'badge-neutral'}`;
      bcStatus.textContent = isWorking ? '● Working' : '● Standby';
    }

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

  // --- Command Palette & Unified Omnibar (Ctrl+K Spotlight / UX-05) ---
  openCommandPalette() {
    const modal = document.getElementById('commandPaletteModal');
    if (!modal) return;
    modal.style.display = 'flex';
    this.paletteSelectedIndex = 0;
    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox) outBox.style.display = 'none';
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

  onPaletteInput(query) {
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

  async executeOmnibarInput(overrideQuery) {
    const input = document.getElementById('cmdPaletteInput');
    const rawQuery = (overrideQuery !== undefined ? overrideQuery : (input ? input.value : '')).trim();
    if (!rawQuery) return;

    const outBox = document.getElementById('cmdPaletteOmnibarResult');
    if (outBox) {
      outBox.style.display = 'block';
      outBox.innerHTML = '<span style="color: var(--accent-cyan);">⚡ Dispatching via Unified Fleet Omnibar...</span>';
    }

    try {
      const res = await fetch('/api/omnibar/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: rawQuery })
      });
      const data = await res.json();
      if (!outBox) return;

      if ((data.mode === 'discovery' || data.mode === 'process_discovery') && Array.isArray(data.recommendations)) {
        const recsHtml = data.recommendations.map(r => `
          <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 8px 10px; margin-top: 6px; background: rgba(15, 23, 42, 0.75); border: 1px solid var(--border-color); border-radius: 6px;">
            <div>
              <strong style="color: var(--text); font-size: 12.5px;">${r.icon || '🤖'} ${r.name}</strong>
              <span class="badge" style="margin-left: 6px; font-size: 10px; background: rgba(16, 185, 129, 0.15); color: #10b981;">Score ${r.opportunity_score}/100</span>
              <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${r.evidence_summary || r.description || ''} (${r.estimated_minutes_saved_per_week || 30} min/wk saved)</div>
            </div>
            <button type="button" class="btn btn-sm btn-primary" style="white-space: nowrap; font-size: 11px; padding: 4px 10px;" onclick="FleetNavigator.spawnDiscoveredAgent('${r.recommendation_id}')">🚀 Spawn Agent</button>
          </div>
        `).join('');
        outBox.innerHTML = `<div><strong style="color: var(--accent-cyan);">${data.title || data.message}</strong>${recsHtml}</div>`;
      } else {
        outBox.innerHTML = `<div style="display: flex; justify-content: space-between; align-items: center; gap: 10px;">
          <span><strong style="color: var(--accent-green);">✔ ${data.title || 'Omnibar'}:</strong> ${data.message || 'Executed.'}</span>
          ${data.agent_id ? `<button type="button" class="btn btn-sm" style="font-size: 11px; padding: 2px 8px;" onclick="FleetNavigator.switchAgent('${data.agent_id}')">Open ${data.agent_id} →</button>` : ''}
        </div>`;
      }
    } catch (e) {
      if (outBox) {
        outBox.innerHTML = `<span style="color: #ef4444;">⚠️ Omnibar error: ${e.message}</span>`;
      }
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
        <div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">
          Press <strong>Enter</strong> or click <strong>Run ↵</strong> to execute query in the Unified Fleet Omnibar.
        </div>`;
      return;
    }

    list.innerHTML = this.paletteResults.map((a, idx) => {
      const isSelected = (idx === this.paletteSelectedIndex);
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
    this.paletteSelectedIndex = (this.paletteSelectedIndex + dir + this.paletteResults.length) % this.paletteResults.length;
    this.renderPaletteResults();
    const activeEl = document.querySelector('.cmd-palette-item.selected');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest' });
  },

  paletteSelectCurrent() {
    const input = document.getElementById('cmdPaletteInput');
    const rawQuery = (input ? input.value : '').trim();
    if (rawQuery.startsWith('@') || (rawQuery && this.paletteResults.length === 0)) {
      this.executeOmnibarInput(rawQuery);
      return;
    }
    if (this.paletteResults[this.paletteSelectedIndex]) {
      this.switchAgent(this.paletteResults[this.paletteSelectedIndex].id);
    }
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  FleetNavigator.init();
});
