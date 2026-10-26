// --- Fleet Dashboard Application Bootstrapper & Polling Loop ---
document.addEventListener('DOMContentLoaded', () => {
  // Initial load
  if (typeof fetchVersion === 'function') fetchVersion();
  if (typeof fetchBriefing === 'function') fetchBriefing();
  if (typeof fetchTasks === 'function') fetchTasks();
  if (typeof fetchRoutines === 'function') fetchRoutines();
  if (typeof fetchSchedules === 'function') fetchSchedules();
  if (typeof fetchEmails === 'function') fetchEmails();
  if (typeof fetchLogs === 'function') fetchLogs();
  if (typeof fetchTestResults === 'function') fetchTestResults();
  if (typeof fetchModels === 'function') fetchModels();
  if (typeof fetchAgentQueue === 'function') fetchAgentQueue();
  if (typeof fetchTokenHealth === 'function') fetchTokenHealth();
  if (typeof fetchBacklog === 'function') fetchBacklog();
  if (typeof fetchOptimizerDiagnostics === 'function') fetchOptimizerDiagnostics();
  if (typeof fetchHealthDashboard === 'function') fetchHealthDashboard();
  if (typeof fetchExerciseVideos === 'function') fetchExerciseVideos();
  if (typeof initDynamicAgentTabs === 'function') initDynamicAgentTabs();
  else if (typeof switchTab === 'function') switchTab('health');

  // Auto poll updates every 8 seconds
  setInterval(() => {
    if (typeof fetchBriefing === 'function') fetchBriefing();
    if (typeof fetchTasks === 'function') fetchTasks();
    if (typeof fetchRoutines === 'function') fetchRoutines();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof fetchLogs === 'function') fetchLogs();
    if (typeof fetchTestResults === 'function') fetchTestResults();
    if (typeof fetchAgentQueue === 'function') fetchAgentQueue();
    if (currentTab === 'backlog' && typeof fetchBacklog === 'function') {
      fetchBacklog();
    } else if (currentTab === 'optimizer' && typeof fetchOptimizerDiagnostics === 'function') {
      fetchOptimizerDiagnostics();
    } else if (currentTab === 'health' && typeof fetchHealthDashboard === 'function') {
      fetchHealthDashboard();
    }
  }, 8000);
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
