// --- Fleet Dashboard Application Bootstrapper & Visibility-Aware Single-Flight Polling Loop ---
let _afccPollInFlight = false;
let _afccPollTick = 0;

async function runAfccPollTick(forceAll = false) {
  if ((typeof document !== 'undefined' && document.hidden && !forceAll) || _afccPollInFlight) {
    return;
  }
  _afccPollInFlight = true;
  try {
    _afccPollTick += 1;
    const tasks = [];
    if (typeof fetchBriefing === 'function') tasks.push(fetchBriefing());
    if (typeof fetchTasks === 'function' && (typeof isTaskEditingActive !== 'function' || !isTaskEditingActive())) {
      tasks.push(fetchTasks());
    }
    if (typeof fetchRoutines === 'function') tasks.push(fetchRoutines());
    if (typeof fetchLogs === 'function') tasks.push(fetchLogs());
    const agPollManagedByDock = Boolean(window.isAgRightDocked || (typeof currentTab !== 'undefined' && currentTab === 'antigravity'));
    if (typeof fetchAgentQueue === 'function' && !agPollManagedByDock) tasks.push(fetchAgentQueue());

    if (typeof currentTab !== 'undefined') {
      if (currentTab === 'backlog' && typeof fetchBacklog === 'function') {
        tasks.push(fetchBacklog());
      } else if (currentTab === 'optimizer' && typeof fetchOptimizerDiagnostics === 'function') {
        tasks.push(fetchOptimizerDiagnostics());
      } else if ((currentTab === 'health' || currentTab === 'tri_device') && typeof fetchHealthDashboard === 'function') {
        tasks.push(fetchHealthDashboard());
      }
    }

    // Slow-changing metadata runs every 4th tick (~60s) or on focus resume
    if (forceAll || (_afccPollTick % 4 === 0)) {
      if (typeof fetchSchedules === 'function') tasks.push(fetchSchedules());
      if (typeof fetchTestResults === 'function') tasks.push(fetchTestResults());
    }

    await Promise.allSettled(tasks);
  } finally {
    _afccPollInFlight = false;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // Initial visible-shell load (deferring hidden tabs: backlog, optimizer, health, exercise videos until selected)
  if (typeof fetchVersion === 'function') fetchVersion();
  if (typeof fetchBriefing === 'function') fetchBriefing();
  if (typeof fetchTasks === 'function') fetchTasks();
  if (typeof fetchRoutines === 'function') fetchRoutines();
  if (typeof fetchSchedules === 'function') fetchSchedules();
  if (typeof fetchEmails === 'function') fetchEmails();
  if (typeof fetchLogs === 'function') fetchLogs();
  if (typeof fetchTestResults === 'function') fetchTestResults();
  if (typeof openAntigravityRightDock === 'function') {
    openAntigravityRightDock();
  } else {
    if (typeof fetchModels === 'function') fetchModels();
    if (typeof fetchAgentQueue === 'function') fetchAgentQueue();
  }
  if (typeof initDynamicAgentTabs === 'function') initDynamicAgentTabs();
  else if (typeof switchTab === 'function') switchTab('overview');

  // Tiered visibility-aware auto poll every 15 seconds (0% background polling CPU when tab is hidden)
  setInterval(() => {
    runAfccPollTick(false);
  }, 15000);

  // Instant catch-up refresh when user returns focus to AFCC
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      runAfccPollTick(true);
      if (typeof scheduleAgPoll === 'function') {
        scheduleAgPoll(true);
      } else if (typeof fetchTranscript === 'function' && window.agChatEngineMode !== 'fleet_zero_token') {
        fetchTranscript(false);
      }
    }
  });
});


async function initDynamicAgentTabs() {
  try {
    const res = await fetch('/api/fleet/agents');
    if (!res.ok) return;
    const data = await res.json();
    if (data.status === 'ok' && Array.isArray(data.agents) && data.agents.length > 0) {
      // Dynamic injection of custom styles/scripts declared by active agents
      data.agents.forEach(agent => {
        if (agent.css_url) {
          const link = document.createElement('link');
          link.rel = 'stylesheet';
          link.href = agent.css_url;
          document.head.appendChild(link);
        }
        if (agent.js_url) {
          const script = document.createElement('script');
          script.src = agent.js_url;
          document.body.appendChild(script);
        }
      });

      // For 100+ agents scalability, delegate tab and stage management to FleetNavigator
      if (typeof FleetNavigator !== 'undefined' && typeof FleetNavigator.fetchFleetData === 'function') {
        FleetNavigator.fetchFleetData();
        return;
      }

      const navContainer = document.getElementById('dynamicNavTabs');
      if (navContainer) {
        navContainer.innerHTML = '';
        data.agents.forEach(agent => {
          const btn = document.createElement('button');
          btn.className = `nav-tab ${agent.is_default ? 'active' : ''}`;
          btn.id = `tabBtn_${agent.id}`;
          btn.innerHTML = `${agent.icon} ${agent.name}`;
          btn.onclick = () => switchTab(agent.id);
          navContainer.appendChild(btn);
        });

        // Keep currently selected tab if still active, otherwise fallback to default
        const currentActive = (typeof currentTab !== 'undefined') ? currentTab : '';
        const stillActive = data.agents.find(a => a.id === currentActive);
        const targetAgent = stillActive || data.agents.find(a => a.is_default) || data.agents[0];
        if (targetAgent && typeof switchTab === 'function') {
          switchTab(targetAgent.id);
        }
      }
    }
  } catch (err) {
    console.warn('Dynamic agent tab initialization note:', err);
  }
}
