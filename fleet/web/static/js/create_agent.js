/**
 * Fleet Zero-Code Agent Studio (Phase 1 & Phase 2) & Live CustomAgentRuntime
 * - 6 Starter Blueprints, Natural-Language Synthesis, Clarifying Chips & 1-Click Express Launch
 * - Typed Domain Fields Editor, Antigravity Intelligence Modes, Visual Preview & Sandbox Dry-Run
 * - In-Place Studio Evolution (preserving SQLite records)
 * - Live SQLite CustomAgentRuntime (KPIs, Quick Capture CRUD, Countdowns, Checklists, AI Briefings)
 */

let currentWizardStep = 1;
let currentPreviewCodeTab = 'visual';
let newlyCreatedAgentId = null;
let wizardEditAgentId = null;
let studioStarterBlueprints = [];
let studioSquadBlueprints = [];
let studioDiscoveryRecommendations = [];
let studioLastSynthesizedSpec = null;
let studioStagedDocExtraction = null;
let studioAttachmentQueue = [];
let studioStagedDocuments = [];
let studioWorkflowGuidance = null;
let studioConnectedLlmInfo = null;
let studioDocFilterFilename = '';
let studioCurrentWorkflowIr = null;
let studioCurrentRequirementsDoc = null;
let studioCurrentRecordingId = '';
let studioEvolveSuggestions = [];
let studioEvolveBaseSnapshot = null;
let studioEvolveLoading = false;
let studioEvolveRequestSeq = 0;
let studioCurrentSchedule = { type: 'time', value: '09:00', display: 'Daily at 09:00' };
let studioCurrentChecklist = [
  { key: 'review_items', label: 'Review active tracked items and deadlines' },
  { key: 'verify_routine', label: 'Verify automated check output' },
];
let studioCurrentFields = [
  { key: 'title', label: 'Item / Entry Name', type: 'text', placeholder: 'e.g. Car Insurance Policy' },
  { key: 'due_date', label: 'Target / Renewal Date', type: 'date', placeholder: 'YYYY-MM-DD' },
  { key: 'numeric_value', label: 'Amount / Metric', type: 'number', placeholder: '0.00' },
];

function _resolveToastStyle(variant) {
  if (variant === 'error') {
    return 'background: rgba(69, 10, 10, 0.96); border: 1px solid rgba(248, 113, 113, 0.65); color: #fecaca';
  }
  if (variant === 'warning') {
    return 'background: rgba(69, 26, 3, 0.95); border: 1px solid rgba(251, 191, 36, 0.6); color: #fde68a';
  }
  if (variant === 'loading') {
    return 'background: rgba(12, 74, 110, 0.95); border: 1px solid rgba(56, 189, 248, 0.6); color: #e0f2fe';
  }
  if (variant === 'success') {
    return 'background: rgba(6, 78, 59, 0.95); border: 1px solid rgba(52, 211, 153, 0.58); color: #d1fae5';
  }
  return 'background: rgba(15, 23, 42, 0.95); border: 1px solid rgba(56, 189, 248, 0.45); color: #e0f2fe';
}

function _inferToastVariant(msg, isError, explicitVariant) {
  if (explicitVariant) return explicitVariant;
  if (isError) return 'error';
  if (/^⏳/.test(msg)) return 'loading';
  if (/^⚠️/.test(msg)) return 'warning';
  if (/^(✅|✓|🎉|✨|🤖|📋|📤|📥|⏪|🔄|⚡|🤝)/.test(msg)) return 'success';
  return 'info';
}

function showFleetToast(message, isError = false, opts = {}) {
  const msg = String(message || '').trim();
  if (!msg || typeof document === 'undefined') return null;
  let container = document.getElementById('fleetGlobalToastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'fleetGlobalToastContainer';
    container.style.cssText = [
      'position: fixed',
      'right: 20px',
      'bottom: 20px',
      'z-index: 100000',
      'display: flex',
      'flex-direction: column',
      'gap: 8px',
      'max-width: min(460px, calc(100vw - 32px))',
      'pointer-events: none',
    ].join(';');
    document.body.appendChild(container);
  }

  const baseCss = [
    'pointer-events: auto',
    'display: flex',
    'align-items: flex-start',
    'justify-content: space-between',
    'gap: 10px',
    'padding: 10px 14px',
    'border-radius: 10px',
    'font-size: 12.5px',
    'font-weight: 500',
    'line-height: 1.42',
    'box-shadow: 0 12px 28px rgba(0, 0, 0, 0.5)',
    'backdrop-filter: blur(10px)',
  ].join(';');

  const variant = _inferToastVariant(msg, Boolean(isError), opts && opts.variant);
  const toast = document.createElement('div');
  toast.setAttribute('role', isError || variant === 'error' ? 'alert' : 'status');
  toast.style.cssText = `${baseCss}; ${_resolveToastStyle(variant)}`;

  const textSpan = document.createElement('div');
  textSpan.style.cssText = 'flex: 1; word-break: break-word;';
  textSpan.textContent = msg;

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.title = 'Dismiss notification';
  closeBtn.textContent = '✕';
  closeBtn.style.cssText = 'background: transparent; border: none; color: inherit; opacity: 0.78; cursor: pointer; font-size: 12px; padding: 0 2px; line-height: 1;';

  let timerId = null;
  const dismiss = () => {
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    if (toast.parentNode) toast.remove();
  };
  closeBtn.onclick = dismiss;

  const scheduleAutoDismiss = (v, customDuration) => {
    if (timerId) {
      clearTimeout(timerId);
      timerId = null;
    }
    const defaultMs = v === 'error' ? 8500 : (v === 'warning' ? 6500 : (v === 'loading' ? 0 : 4800));
    const ms = typeof customDuration === 'number' ? customDuration : defaultMs;
    if (ms > 0) {
      timerId = setTimeout(dismiss, ms);
    }
  };

  toast.appendChild(textSpan);
  toast.appendChild(closeBtn);
  container.appendChild(toast);
  scheduleAutoDismiss(variant, opts && opts.durationMs);

  return {
    el: toast,
    dismiss,
    update(nextMessage, nextIsError = false, nextOpts = {}) {
      const cleanNext = String(nextMessage || '').trim();
      if (!cleanNext) {
        dismiss();
        return;
      }
      const nextVariant = _inferToastVariant(cleanNext, Boolean(nextIsError), nextOpts && nextOpts.variant);
      toast.setAttribute('role', nextIsError || nextVariant === 'error' ? 'alert' : 'status');
      toast.style.cssText = `${baseCss}; ${_resolveToastStyle(nextVariant)}`;
      textSpan.textContent = cleanNext;
      if (!toast.parentNode && container) {
        container.appendChild(toast);
      }
      scheduleAutoDismiss(nextVariant, nextOpts && nextOpts.durationMs);
    },
  };
}

function isStudioModalVisible() {
  if (typeof document === 'undefined') return false;
  const modal = document.getElementById('createAgentModal');
  return Boolean(modal && modal.style.display && modal.style.display !== 'none');
}

function setStudioGlobalBanner(mode, message, elapsedSec = null) {
  if (typeof document === 'undefined') return;
  const banner = document.getElementById('studioGlobalActionBanner');
  if (!banner) return;
  const cleanMsg = String(message || '').trim();
  if (!cleanMsg) {
    banner.style.display = 'none';
    return;
  }

  const iconEl = document.getElementById('studioGlobalActionBannerIcon');
  const textEl = document.getElementById('studioGlobalActionBannerText');
  const timerEl = document.getElementById('studioGlobalActionBannerTimer');

  let bg = 'rgba(14, 116, 144, 0.28)';
  let border = 'rgba(56, 189, 248, 0.5)';
  let textColor = '#e0f2fe';
  let icon = '⏳';

  if (mode === 'error') {
    bg = 'rgba(127, 29, 29, 0.45)';
    border = 'rgba(248, 113, 113, 0.68)';
    textColor = '#fecaca';
    icon = '✕';
  } else if (mode === 'warning') {
    bg = 'rgba(120, 53, 15, 0.4)';
    border = 'rgba(251, 191, 36, 0.58)';
    textColor = '#fde68a';
    icon = '⚠️';
  } else if (mode === 'success') {
    bg = 'rgba(6, 78, 59, 0.38)';
    border = 'rgba(52, 211, 153, 0.55)';
    textColor = '#d1fae5';
    icon = '✅';
  }

  banner.style.background = bg;
  banner.style.borderBottom = `1px solid ${border}`;
  banner.style.color = textColor;
  banner.style.display = 'flex';

  if (iconEl) iconEl.textContent = icon;
  if (textEl) {
    textEl.style.color = textColor;
    textEl.textContent = cleanMsg;
  }
  if (timerEl) {
    if (mode === 'loading' && typeof elapsedSec === 'number') {
      timerEl.style.display = 'inline-block';
      timerEl.textContent = `${elapsedSec}s`;
    } else {
      timerEl.style.display = 'none';
    }
  }
}

function clearStudioGlobalBanner() {
  if (typeof document === 'undefined') return;
  const banner = document.getElementById('studioGlobalActionBanner');
  if (banner) banner.style.display = 'none';
}

function getActiveClickedButton() {
  if (typeof window === 'undefined' || typeof document === 'undefined') return null;
  try {
    const ev = window.event;
    if (ev) {
      if (ev.currentTarget && ev.currentTarget.tagName === 'BUTTON') {
        return ev.currentTarget;
      }
      if (ev.target && typeof ev.target.closest === 'function') {
        const closestBtn = ev.target.closest('button');
        if (closestBtn) return closestBtn;
      }
    }
  } catch (_) {}
  const active = document.activeElement;
  if (active && active.tagName === 'BUTTON') return active;
  return null;
}

/**
 * Universal async action wrapper that guarantees:
 * 1. Immediate visual button feedback (disabled + wait cursor + '⏳ ...' + ticking seconds timer).
 * 2. Live modal-wide activity banner (#studioGlobalActionBanner) when Agent Studio is open.
 * 3. Optional live loading toast that cleanly transitions to completion or error.
 * 4. Guaranteed visible error notification (red toast + modal banner) if anything throws or fails.
 */
async function runFleetAsyncAction(config, fn) {
  const cfg = config || {};
  const rawButtons = Array.isArray(cfg.buttons) ? cfg.buttons : (cfg.button ? [cfg.button] : []);
  const btnSet = new Set();

  rawButtons.forEach(item => {
    if (!item) return;
    const el = typeof item === 'string'
      ? (typeof document !== 'undefined' ? document.getElementById(item) : null)
      : item;
    if (el && el.tagName === 'BUTTON') btnSet.add(el);
  });

  if (cfg.includeActiveButton !== false) {
    const clicked = getActiveClickedButton();
    if (clicked && clicked.tagName === 'BUTTON') btnSet.add(clicked);
  }

  const busyLabel = String(cfg.busyLabel || '⏳ Working...').trim();
  const errorPrefix = String(cfg.errorPrefix || 'Action failed').trim();
  const showBanner = cfg.useStudioBanner !== undefined ? Boolean(cfg.useStudioBanner) : isStudioModalVisible();
  const bannerMsg = String(cfg.bannerMessage || busyLabel.replace(/^⏳\s*/, '')).trim();

  const savedStates = Array.from(btnSet).map(btn => ({
    btn,
    disabled: Boolean(btn.disabled),
    html: btn.innerHTML,
    opacity: btn.style.opacity,
    cursor: btn.style.cursor,
  }));

  savedStates.forEach(({ btn }) => {
    btn.disabled = true;
    btn.style.opacity = '0.78';
    btn.style.cursor = 'wait';
    btn.textContent = busyLabel;
  });

  if (showBanner && bannerMsg) {
    setStudioGlobalBanner('loading', bannerMsg, 0);
  }

  let toastHandle = null;
  if (cfg.startToast) {
    toastHandle = showFleetToast(cfg.startToast, false, { variant: 'loading', durationMs: 0 });
  }

  let elapsedSec = 0;
  const tickInterval = setInterval(() => {
    elapsedSec += 1;
    const timedLabel = `${busyLabel} (${elapsedSec}s)`;
    savedStates.forEach(({ btn }) => {
      if (btn && btn.isConnected && btn.disabled) {
        btn.textContent = timedLabel;
      }
    });
    if (showBanner && bannerMsg && isStudioModalVisible()) {
      setStudioGlobalBanner('loading', bannerMsg, elapsedSec);
    }
    if (toastHandle && elapsedSec >= 2 && cfg.startToast) {
      toastHandle.update(`${cfg.startToast} (${elapsedSec}s)`, false, { variant: 'loading', durationMs: 0 });
    }
  }, 1000);

  let succeeded = false;
  try {
    const result = await fn({ toastHandle, setStudioGlobalBanner });
    succeeded = true;
    if (showBanner && cfg.clearBannerOnSuccess !== false) {
      clearStudioGlobalBanner();
    }
    return result;
  } catch (err) {
    const rawReason = String((err && err.message) ? err.message : (err || 'Unexpected error')).trim();
    const cleanReason = rawReason.replace(/^✕\s*/, '');
    const fullErrorMsg = cleanReason.toLowerCase().startsWith(errorPrefix.toLowerCase())
      ? `✕ ${cleanReason}`
      : `✕ ${errorPrefix}: ${cleanReason}`;

    if (showBanner || isStudioModalVisible()) {
      setStudioGlobalBanner('error', fullErrorMsg);
    }
    if (toastHandle) {
      toastHandle.update(fullErrorMsg, true, { variant: 'error', durationMs: 8500 });
      toastHandle = null;
    } else {
      showFleetToast(fullErrorMsg, true, { variant: 'error', durationMs: 8500 });
    }
    if (typeof cfg.onError === 'function') {
      cfg.onError(err, fullErrorMsg);
    }
    if (cfg.rethrow) throw err;
    return undefined;
  } finally {
    clearInterval(tickInterval);
    if (succeeded && toastHandle) {
      toastHandle.dismiss();
    }
    savedStates.forEach(({ btn, disabled, html, opacity, cursor }) => {
      if (!btn) return;
      btn.disabled = disabled;
      btn.style.opacity = opacity;
      btn.style.cursor = cursor;
      btn.innerHTML = html;
    });
    if (typeof cfg.onFinally === 'function') {
      cfg.onFinally();
    }
  }
}

if (typeof window !== 'undefined') {
  window.showFleetToast = showFleetToast;
  window.setStudioGlobalBanner = setStudioGlobalBanner;
  window.clearStudioGlobalBanner = clearStudioGlobalBanner;
  window.runFleetAsyncAction = runFleetAsyncAction;
}

const FALLBACK_STUDIO_BLUEPRINTS = [
  {
    id: 'renewal_sentinel',
    title: 'Insurance & Renewal Guard',
    icon: '🛡️',
    prompt: 'Track my car, bike, and health insurance renewals, domain expiry dates, and annual bills every morning at 08:30 and alert me 15 days before any policy expires',
  },
  {
    id: 'http_uptime_watcher',
    title: 'Website & API Watcher',
    icon: '🌐',
    prompt: 'Monitor my production website URLs and API health endpoints every 30 minutes, record HTTP response latency, and alert me if any service is unreachable',
  },
  {
    id: 'git_ci_sentinel',
    title: 'Git Repo & Release Sentinel',
    icon: '🐙',
    prompt: 'Check my local git repos and release milestones every evening at 18:00 and alert me if uncommitted changes or overdue milestones exist',
  },
  {
    id: 'ai_research_digest',
    title: 'AI Research Digest',
    icon: '🧠',
    prompt: 'Capture research articles, papers, and technical notes throughout the day and synthesize an executive action summary every morning at 09:00',
  },
  {
    id: 'habit_vitals_coach',
    title: 'Habit & Vitals Coach',
    icon: '🌿',
    prompt: 'Remind me to do a posture stretch, hydration check, and log daily wellness metrics every hour with an interactive daily streak checklist',
  },
  {
    id: 'system_hygiene_guard',
    title: 'Disk & System Guard',
    icon: '🐳',
    prompt: 'Audit local disk free space and workstation storage thresholds every 2 hours and notify me when free disk capacity drops below target thresholds',
  },
];

function studioEscapeHtml(val) {
  return String(val == null ? '' : val)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function updateStudioConnectedLlmBadge(llmInfo) {
  if (llmInfo && typeof llmInfo === 'object') {
    studioConnectedLlmInfo = llmInfo;
  }
  const badge = document.getElementById('studioConnectedLlmBadge');
  if (!badge) return;
  const info = studioConnectedLlmInfo;
  if (!info) {
    badge.textContent = '🤖 Connected AFCC LLM: Auto';
    return;
  }
  const label = info.engine_used && info.engine_used !== 'tier0_deterministic_extractor'
    ? `${info.engine_used}${info.model_used ? ' • ' + info.model_used : ''}`
    : (info.active_provider_name || 'Auto Gateway');
  badge.textContent = `🤖 Connected LLM: ${label}`;
}

async function loadStudioBlueprints() {
  const row = document.getElementById('studioStarterBlueprintsRow');
  if (!row) return;
  if (studioStarterBlueprints.length === 0) {
    studioStarterBlueprints = FALLBACK_STUDIO_BLUEPRINTS;
    try {
      const res = await fetch('/api/studio/blueprints');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.blueprints) && data.blueprints.length > 0) {
          studioStarterBlueprints = data.blueprints;
        }
        if (Array.isArray(data.squad_blueprints) && data.squad_blueprints.length > 0) {
          studioSquadBlueprints = data.squad_blueprints;
        }
        if (data.connected_llm) {
          updateStudioConnectedLlmBadge(data.connected_llm);
        }
      }
    } catch (_) {
      // Fallback blueprints already loaded
    }
  } else if (studioConnectedLlmInfo) {
    updateStudioConnectedLlmBadge(studioConnectedLlmInfo);
  }
  row.innerHTML = studioStarterBlueprints.map((bp, idx) => `
    <button type="button" class="btn" title="${studioEscapeHtml(bp.prompt || bp.title || 'Apply starter blueprint')}" onclick="selectStarterBlueprint(${idx})"
      style="padding: 4px 10px; font-size: 11.5px; border-radius: 999px; background: rgba(15, 23, 42, 0.72); border: 1px solid rgba(56, 189, 248, 0.28); color: #e2e8f0; display: inline-flex; align-items: center; gap: 5px;">
      <span>${studioEscapeHtml(bp.icon || '✨')}</span>
      <span>${studioEscapeHtml(bp.title)}</span>
    </button>
  `).join('');

  const squadWrap = document.getElementById('studioSquadBlueprintsWrap');
  const squadRow = document.getElementById('studioSquadBlueprintsRow');
  if (squadWrap && squadRow) {
    if (wizardEditAgentId || studioSquadBlueprints.length === 0) {
      squadWrap.style.display = 'none';
    } else {
      squadRow.innerHTML = studioSquadBlueprints.map(sq => {
        const count = Array.isArray(sq.agents) ? sq.agents.length : 0;
        return `
          <div title="${studioEscapeHtml(sq.summary || '')}" style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 7px 4px 11px; border-radius: 999px; background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(168, 85, 247, 0.38);">
            <span style="font-size: 12px;">${studioEscapeHtml(sq.icon || '🤝')}</span>
            <span style="font-size: 11.5px; color: #f3e8ff; font-weight: 600;">${studioEscapeHtml(sq.title)}</span>
            <span style="font-size: 10px; color: #c4b5fd;">(${count} agents)</span>
            <button type="button" class="btn" title="Deploy all ${count} coordinated Squad agents in 1 click"
              onclick="deployStudioSquad('${studioEscapeHtml(sq.id)}')"
              style="padding: 2px 8px; font-size: 10.5px; border-radius: 999px; background: rgba(168, 85, 247, 0.24); border: 1px solid rgba(192, 132, 252, 0.5); color: #e9d5ff; font-weight: 700;">
              ⚡ Deploy Squad
            </button>
          </div>
        `;
      }).join('');
      squadWrap.style.display = 'block';
    }
  }
}

async function deployStudioSquad(squadId) {
  if (!squadId) return;
  await runFleetAsyncAction({
    busyLabel: '⏳ Deploying Squad...',
    bannerMessage: '🤝 Scaffolding & wiring coordinated Multi-Agent Squad...',
    startToast: '⏳ Scaffolding & wiring Multi-Agent Squad...',
    errorPrefix: 'Squad deployment failed',
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry('/api/studio/squads/deploy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ squad_id: squadId }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Squad deployment failed.');
    }
    newlyCreatedAgentId = data.primary_agent_id || (data.agents?.[0]?.id) || null;
    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();
    showFleetToast(`🤝 Deployed '${data.squad_title}' (${data.deployed_count} coordinated agents)!`, false);
    openNewlyCreatedAgent();
  });
}

function selectStarterBlueprint(idx) {
  const bp = studioStarterBlueprints[idx];
  if (!bp) return;
  const input = document.getElementById('wizardNaturalLanguageInput');
  if (input) input.value = bp.prompt || '';
  synthesizeWizardFromPrompt();
}

async function loadStudioDiscoverySuggestions() {
  const wrap = document.getElementById('studioDiscoverySuggestionsWrap');
  const row = document.getElementById('studioDiscoverySuggestionsRow');
  if (!wrap || !row) return;
  if (wizardEditAgentId) {
    wrap.style.display = 'none';
    return;
  }
  try {
    const res = await fetch('/api/discovery/recommendations');
    if (!res.ok) return;
    const data = await res.json();
    const recs = Array.isArray(data.recommendations)
      ? data.recommendations.filter(r => !(r.already_installed || r.is_installed))
      : [];
    studioDiscoveryRecommendations = recs.slice(0, 4);
    if (studioDiscoveryRecommendations.length === 0) {
      wrap.style.display = 'none';
      return;
    }
    row.innerHTML = studioDiscoveryRecommendations.map((rec, idx) => `
      <div style="display: inline-flex; align-items: center; gap: 4px; padding: 3px 6px 3px 10px; border-radius: 999px; background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(16, 185, 129, 0.35);">
        <button type="button" class="btn" title="${studioEscapeHtml(rec.reason || rec.evidence_summary || rec.prompt || rec.nl_prompt || '')}"
          onclick="selectDiscoverySuggestion(${idx})"
          style="padding: 1px 4px; font-size: 11.5px; background: transparent; border: none; color: #e2e8f0; display: inline-flex; align-items: center; gap: 5px;">
          <span>${studioEscapeHtml(rec.icon || '💡')}</span>
          <span>${studioEscapeHtml(rec.title || rec.name)}</span>
          <span style="font-size: 10px; color: #34d399;">~${Number(rec.estimated_weekly_minutes_saved || rec.estimated_minutes_saved_per_week || 20)}m/wk</span>
        </button>
        <button type="button" class="btn" title="1-Click Spawn Recommended Agent"
          onclick="event.stopPropagation(); spawnDiscoveryRecommendationFromStudio(${idx})"
          style="padding: 2px 7px; font-size: 10.5px; border-radius: 999px; background: rgba(16, 185, 129, 0.22); border: 1px solid rgba(16, 185, 129, 0.45); color: #6ee7b7; font-weight: 700;">
          ⚡ Spawn
        </button>
      </div>
    `).join('');
    wrap.style.display = 'block';
  } catch (_) {
    wrap.style.display = 'none';
  }
}

function selectDiscoverySuggestion(idx) {
  const rec = studioDiscoveryRecommendations[idx];
  if (!rec) return;
  const input = document.getElementById('wizardNaturalLanguageInput');
  if (input) input.value = rec.prompt || rec.nl_prompt || '';
  synthesizeWizardFromPrompt();
}

async function spawnDiscoveryRecommendationFromStudio(idx) {
  const rec = studioDiscoveryRecommendations[idx];
  if (!rec) return;
  const recName = rec.title || rec.name || rec.id || 'Recommended Agent';
  await runFleetAsyncAction({
    busyLabel: '⏳ Spawning...',
    bannerMessage: `⚡ Scaffolding & scheduling '${recName}'...`,
    startToast: `⏳ Spawning '${recName}'...`,
    errorPrefix: 'Discovery spawn failed',
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry('/api/discovery/spawn', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recommendation_id: rec.recommendation_id || rec.id }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Could not spawn recommended agent.');
    }
    newlyCreatedAgentId = data.agent_id;
    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();
    showFleetToast(`⚡ Spawned & scheduled '${data.manifest?.name || data.agent_id}'!`, false);
    openNewlyCreatedAgent();
  });
}

function resetWizardFormDefaults() {
  clearStudioGlobalBanner();
  wizardEditAgentId = null;
  newlyCreatedAgentId = null;
  studioLastSynthesizedSpec = null;
  studioStagedDocExtraction = null;
  studioAttachmentQueue = [];
  studioStagedDocuments = [];
  studioWorkflowGuidance = null;
  studioDocFilterFilename = '';
  studioCurrentWorkflowIr = null;
  studioCurrentRequirementsDoc = null;
  studioCurrentRecordingId = '';
  if (typeof window.StudioActivityRecorder?.resetUi === 'function') {
    window.StudioActivityRecorder.resetUi();
  }
  studioEvolveRequestSeq += 1;
  studioEvolveSuggestions = [];
  studioEvolveBaseSnapshot = null;
  studioEvolveLoading = false;
  currentWizardStep = 1;
  currentPreviewCodeTab = 'visual';
  studioCurrentSchedule = { type: 'time', value: '09:00', display: 'Daily at 09:00' };
  studioCurrentChecklist = [
    { key: 'review_items', label: 'Review active tracked items and deadlines' },
    { key: 'verify_routine', label: 'Verify automated check output' },
  ];
  studioCurrentFields = [
    { key: 'title', label: 'Item / Entry Name', type: 'text', placeholder: 'e.g. Car Insurance Policy' },
    { key: 'due_date', label: 'Target / Renewal Date', type: 'date', placeholder: 'YYYY-MM-DD' },
    { key: 'numeric_value', label: 'Amount / Metric', type: 'number', placeholder: '0.00' },
  ];

  const titleEl = document.getElementById('wizardModalTitle');
  const subEl = document.getElementById('wizardModalSubtitle');
  const badgeEl = document.getElementById('wizardModeBadge');
  const promptTitle = document.getElementById('studioPromptTitle');
  const submitBtn = document.getElementById('btnWizardSubmit');
  const expressBtn = document.getElementById('btnStudioExpressLaunch');
  const ribbonBtn = document.getElementById('btnGuidedRibbonLaunch');
  const evolveReloadBtn = document.getElementById('btnQuickApplyEvolveReload');
  const evolveDeepBtn = document.getElementById('btnApplyEvolveDeepBuild');
  const deepBtn = document.getElementById('btnWizardDeepBuild');

  if (titleEl) titleEl.textContent = 'Zero-Code Agent Studio';
  if (subEl) subEl.textContent = 'Pick a blueprint or describe your workflow in plain English — launch in 1 click or customize every detail.';
  if (badgeEl) badgeEl.textContent = 'Hybrid $0.00 + Antigravity LLM';
  if (promptTitle) promptTitle.textContent = '✨ Zero-Code Agent Studio — Describe in Plain English';
  if (submitBtn) submitBtn.textContent = '🚀 Scaffold & Activate Agent';
  if (expressBtn) expressBtn.textContent = '🚀 1-Click Express Launch';
  if (ribbonBtn) ribbonBtn.textContent = '🚀 Launch Now';
  if (evolveReloadBtn) evolveReloadBtn.textContent = '✨ Apply Selected & Hot-Reload';
  if (evolveDeepBtn) evolveDeepBtn.textContent = '🤖 Apply & Deep-Build';
  if (deepBtn) deepBtn.textContent = '🤖 Deep-Build in Antigravity';

  const nlInput = document.getElementById('wizardNaturalLanguageInput');
  const nameEl = document.getElementById('newAgentName');
  const idEl = document.getElementById('newAgentId');
  const iconEl = document.getElementById('newAgentIcon');
  const descEl = document.getElementById('newAgentDesc');
  const modeEl = document.getElementById('newAgentIntelligenceMode');
  const modelEl = document.getElementById('newAgentModel');
  const archEl = document.getElementById('newAgentArchetype');

  if (nlInput) nlInput.value = '';
  if (nameEl) nameEl.value = '';
  if (idEl) {
    idEl.value = '';
    idEl.readOnly = false;
    idEl.style.opacity = '1';
  }
  if (iconEl) iconEl.value = '⚡';
  if (descEl) descEl.value = '';
  if (modeEl) modeEl.value = 'hybrid';
  if (modelEl) modelEl.value = 'gemini-3.8-flash-low';
  if (archEl) archEl.value = 'tracker';
  setSelectedEventTriggers([]);
  setSelectedOutboundActions(['auto_create_task']);
  const recEl = document.getElementById('newAgentDefaultRecurrence');
  if (recEl) recEl.value = 'none';
  const inboxEl = document.getElementById('newAgentAutoIngestInbox');
  if (inboxEl) inboxEl.checked = true;

  const summaryBox = document.getElementById('studioSynthesisSummaryBox');
  if (summaryBox) summaryBox.style.display = 'none';
  const dryOut = document.getElementById('wizardDryRunOutput');
  if (dryOut) dryOut.style.display = 'none';
  const successBox = document.getElementById('wizardSuccessBox');
  if (successBox) successBox.style.display = 'none';
  const notice = document.getElementById('wizardStatusNotice');
  if (notice) notice.style.display = 'none';
  const footer = document.getElementById('wizardFooterBar');
  if (footer) footer.style.display = 'flex';
  const revBar = document.getElementById('studioRevisionRollbackBar');
  if (revBar) revBar.style.display = 'none';
  const evolveSec = document.getElementById('studioEvolveAdvisorSection');
  if (evolveSec) evolveSec.style.display = 'none';
  const evolveList = document.getElementById('studioEvolveSuggestionsList');
  if (evolveList) evolveList.innerHTML = '';
  const evolveCustomInp = document.getElementById('studioCustomImprovementInput');
  if (evolveCustomInp) evolveCustomInp.value = '';
  const evolveLlmSel = document.getElementById('studioEvolveLlmProvider');
  if (evolveLlmSel) evolveLlmSel.value = 'auto';
  const starterWrap = document.getElementById('studioStarterBlueprintsWrap');
  if (starterWrap) starterWrap.style.display = 'block';
  const docSec = document.getElementById('studioDocUploadSection');
  if (docSec) docSec.style.display = 'block';
  const docInput = document.getElementById('studioWizardDocInput');
  if (docInput) docInput.value = '';
  const docLlmSel = document.getElementById('studioDocLlmProvider');
  if (docLlmSel) docLlmSel.value = 'auto';
  const queueTray = document.getElementById('studioAttachmentQueueTray');
  if (queueTray) {
    queueTray.style.display = 'none';
    queueTray.innerHTML = '';
  }
  const guidedRibbon = document.getElementById('studioGuidedWorkflowRibbon');
  if (guidedRibbon) guidedRibbon.style.display = 'none';
  const docPrev = document.getElementById('studioWizardDocPreviewBox');
  if (docPrev) {
    docPrev.style.display = 'none';
    docPrev.innerHTML = '';
  }

  renderStudioFieldsEditor();
  checkWizardAgentIdCollision();
}

function openCreateAgentModal() {
  const modal = document.getElementById('createAgentModal');
  if (!modal) return;
  resetWizardFormDefaults();
  loadStudioBlueprints();
  loadStudioDiscoverySuggestions();
  if (typeof window.StudioActivityRecorder?.init === 'function') {
    window.StudioActivityRecorder.init();
  }
  switchCodePreviewTab('visual');
  goToWizardStep(1);
  modal.style.display = 'flex';

  setTimeout(() => {
    const nlInput = document.getElementById('wizardNaturalLanguageInput');
    if (nlInput) nlInput.focus();
  }, 80);
}

async function openEvolveAgentModal(agentId) {
  if (!agentId) return;
  if (typeof closeSettingsModal === 'function') {
    const sm = document.getElementById('fleetSettingsModal') || document.getElementById('settingsModal');
    if (sm && sm.style.display && sm.style.display !== 'none') closeSettingsModal();
  }
  const modal = document.getElementById('createAgentModal');
  if (!modal) return;

  await runFleetAsyncAction({
    buttons: ['btnStageEvolveAgent'],
    busyLabel: '⏳ Opening Studio...',
    useStudioBanner: false,
    errorPrefix: 'Could not open Evolve in Studio',
  }, async () => {
    resetWizardFormDefaults();
    loadStudioBlueprints();
    const discWrap = document.getElementById('studioDiscoverySuggestionsWrap');
    if (discWrap) discWrap.style.display = 'none';
    const squadWrap = document.getElementById('studioSquadBlueprintsWrap');
    if (squadWrap) squadWrap.style.display = 'none';
    const docSec = document.getElementById('studioDocUploadSection');
    if (docSec) docSec.style.display = 'none';
    const starterWrap = document.getElementById('studioStarterBlueprintsWrap');
    if (starterWrap) starterWrap.style.display = 'none';

    let manifest = null;
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(agentId)}/state`);
      if (res.ok) {
        const data = await res.json();
        manifest = data.manifest || null;
      }
    } catch (_) {}

    if (!manifest) {
      const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
      manifest = (nav?.agents || []).find(a => a.id === agentId) || null;
    }
    if (!manifest) {
      throw new Error(`Could not load agent '${agentId}' for Studio evolution.`);
    }

    wizardEditAgentId = manifest.id;

    const titleEl = document.getElementById('wizardModalTitle');
    const subEl = document.getElementById('wizardModalSubtitle');
    const badgeEl = document.getElementById('wizardModeBadge');
    const promptTitle = document.getElementById('studioPromptTitle');
    const submitBtn = document.getElementById('btnWizardSubmit');
    const expressBtn = document.getElementById('btnStudioExpressLaunch');

    const agentTypeLabel = manifest.is_custom ? 'Custom Studio Agent' : 'Built-In Core Agent';
    if (titleEl) titleEl.textContent = `✨ 10 Ways to Improve '${manifest.name}'`;
    if (subEl) subEl.textContent = `Select any of the 10 AI-generated feature improvements below, or enter your own manual items for '${manifest.name}' (${agentTypeLabel}) to undertake and improve itself.`;
    if (badgeEl) badgeEl.textContent = '10-Way AI Self-Improvement Mode';
    if (promptTitle) promptTitle.textContent = '✨ Describe New Capabilities or Refinements (Optional Re-Synthesize)';
    if (submitBtn) submitBtn.textContent = '✨ Undertake Selected & Hot-Reload';
    if (expressBtn) expressBtn.textContent = '✨ 1-Click Undertake & Reload';

    const baseSpec = {
      agent_id: manifest.id,
      name: manifest.name,
      icon: manifest.icon || '✨',
      category: manifest.category || 'Productivity',
      description: manifest.description || '',
      permissions: Array.isArray(manifest.permissions) && manifest.permissions.length
        ? [...manifest.permissions]
        : ['db:read', 'db:write', 'ui:render'],
      intelligence_mode: manifest.intelligence_mode || 'hybrid',
      model: manifest.model || 'gemini-3.8-flash-low',
      archetype: manifest.archetype || 'tracker',
      system_prompt: manifest.system_prompt || '',
      routine_task: manifest.routine_task || 'run_check',
      schedule_cadence: manifest.schedule_cadence || 'daily_morning',
      schedule: manifest.schedule ? { ...manifest.schedule } : { type: 'time', value: '09:00', display: 'Daily at 09:00' },
      ui_blocks: (manifest.ui_blocks && manifest.ui_blocks.length)
        ? [...manifest.ui_blocks]
        : ['alert_banner', 'kpi_row', 'quick_capture_bar', 'history_table'],
      fields: (manifest.fields && manifest.fields.length)
        ? manifest.fields.map(f => ({ ...f }))
        : studioCurrentFields.map(f => ({ ...f })),
      checklist_items: Array.isArray(manifest.checklist_items) && manifest.checklist_items.length
        ? manifest.checklist_items.map(c => (typeof c === 'object' ? { ...c } : c))
        : studioCurrentChecklist.map(c => ({ ...c })),
      event_triggers: Array.isArray(manifest.event_triggers) ? [...manifest.event_triggers] : [],
      outbound_actions: Array.isArray(manifest.outbound_actions) ? [...manifest.outbound_actions] : [],
      auto_ingest_inbox: Boolean(manifest.auto_ingest_inbox),
      default_recurrence: manifest.default_recurrence || 'none',
      evolution_improvements: Array.isArray(manifest.evolution_improvements)
        ? manifest.evolution_improvements.map(x => (typeof x === 'object' ? { ...x } : { title: String(x) }))
        : [],
    };
    studioEvolveBaseSnapshot = JSON.parse(JSON.stringify(baseSpec));

    populateWizardFromSpec(baseSpec);

    const nlInput = document.getElementById('wizardNaturalLanguageInput');
    if (nlInput) nlInput.value = manifest.description || '';

    const idEl = document.getElementById('newAgentId');
    if (idEl) {
      idEl.value = manifest.id;
      idEl.readOnly = true;
      idEl.style.opacity = '0.75';
    }

    const evolveSec = document.getElementById('studioEvolveAdvisorSection');
    if (evolveSec) evolveSec.style.display = 'block';

    checkWizardAgentIdCollision();
    loadAgentRevisionsForStudio(manifest.id);
    switchCodePreviewTab('visual');
    goToWizardStep(1);
    modal.style.display = 'flex';

    // Automatically generate 10 tailored improvements via AFCC's connected LLM
    fetchStudioEvolveSuggestions(manifest.id);
  });
}

async function fetchStudioEvolveSuggestions(agentId, opts = {}) {
  const targetId = agentId || wizardEditAgentId;
  if (!targetId) return;

  const reqSeq = ++studioEvolveRequestSeq;
  studioEvolveLoading = true;
  const isManualRegen = Boolean(opts.forceRefresh);

  const listEl = document.getElementById('studioEvolveSuggestionsList');
  const summaryEl = document.getElementById('studioEvolveAdvisorSummary');
  const regenBtn = document.getElementById('btnRegenerateEvolveSuggestions');
  const llmBadge = document.getElementById('studioEvolveLlmBadge');
  const providerSel = document.getElementById('studioEvolveLlmProvider');
  const chosenProvider = opts.provider || (providerSel ? providerSel.value : 'auto') || 'auto';

  const preservedCustom = studioEvolveSuggestions.filter(s => s && s.is_custom);

  if (regenBtn) {
    regenBtn.disabled = true;
    regenBtn.style.cursor = 'wait';
    regenBtn.textContent = '⏳ Analyzing...';
  }
  if (isManualRegen) {
    setStudioGlobalBanner('loading', `🔄 Generating 10 fresh tailored improvements for '${targetId}' via connected LLM...`, 0);
  }
  let elapsed = 0;
  const regenTimer = setInterval(() => {
    if (reqSeq !== studioEvolveRequestSeq) {
      clearInterval(regenTimer);
      return;
    }
    elapsed += 1;
    if (regenBtn && regenBtn.disabled) {
      regenBtn.textContent = `⏳ Analyzing (${elapsed}s)...`;
    }
    if (isManualRegen && isStudioModalVisible()) {
      setStudioGlobalBanner('loading', `🔄 Generating 10 fresh tailored improvements for '${targetId}' via connected LLM...`, elapsed);
    }
  }, 1000);

  if (summaryEl) {
    summaryEl.innerHTML = '⏳ <strong>Connected AFCC LLM</strong> is inspecting this agent\'s widgets, typed SQLite fields, EventBus hooks, vaulted documents, and runtime metrics to generate <strong>10 tailored improvements</strong>...';
  }
  if (listEl && preservedCustom.length === 0) {
    listEl.innerHTML = Array.from({ length: 4 }).map((_, i) => `
      <div style="padding: 10px 12px; border-radius: 8px; background: rgba(15, 23, 42, 0.72); border: 1px solid rgba(168, 85, 247, 0.22); opacity: ${1 - i * 0.14};">
        <div style="font-size: 11.5px; color: #c4b5fd; font-weight: 600;">✨ Synthesizing improvement #${i + 1}...</div>
        <div style="font-size: 10.5px; color: #64748b; margin-top: 3px;">Evaluating missing Studio capabilities &amp; domain logic...</div>
      </div>
    `).join('');
  }

  try {
    const baseSpecForAnalysis = studioEvolveBaseSnapshot
      ? JSON.parse(JSON.stringify(studioEvolveBaseSnapshot))
      : buildCurrentWizardSpecPayload();

    const { res, data } = await studioFetchJsonWithRetry('/api/studio/evolve/suggestions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: targetId,
        spec: baseSpecForAnalysis,
        provider: chosenProvider,
        count: 10,
        force_refresh: isManualRegen,
      }),
    });

    if (reqSeq !== studioEvolveRequestSeq) return;
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Could not generate evolution suggestions.');
    }

    const incoming = Array.isArray(data.suggestions) ? data.suggestions : [];
    const normalized = incoming.map((item, idx) => ({
      id: item.id || `evo_${idx + 1}`,
      title: item.title || `Improvement #${idx + 1}`,
      description: item.description || '',
      category: item.category || 'Studio Upgrade',
      impact: item.impact || 'medium',
      icon: item.icon || '✨',
      recommended: Boolean(item.recommended),
      is_custom: false,
      selected: false,
      source: item.source || 'llm',
      patch: (item.patch && typeof item.patch === 'object') ? item.patch : {},
      change_pills: Array.isArray(item.change_pills) ? item.change_pills : [],
    }));

    studioEvolveSuggestions = [...preservedCustom, ...normalized];

    if (llmBadge) {
      const engineLabel = data.engine_used || data.connected_llm?.display_label || chosenProvider;
      const modelLabel = data.model_used && data.model_used !== engineLabel ? ` • ${data.model_used}` : '';
      llmBadge.textContent = `🤖 ${engineLabel}${modelLabel}`;
    }
    if (summaryEl) {
      summaryEl.textContent = data.analysis_summary || `Generated ${normalized.length} tailored improvements for '${targetId}'.`;
    }
    studioEvolveLoading = false;
    if (isManualRegen) {
      clearStudioGlobalBanner();
      showFleetToast(`✨ Generated ${normalized.length} fresh tailored improvements!`, false);
    }
    renderStudioEvolveSuggestionsList();
    syncSelectedEvolveSuggestionsToWizard();
  } catch (err) {
    if (reqSeq !== studioEvolveRequestSeq) return;
    studioEvolveLoading = false;
    studioEvolveSuggestions = [...preservedCustom];
    if (isManualRegen) {
      setStudioGlobalBanner('error', `✕ Evolution Advisor failed: ${err.message}`);
    }
    showFleetToast(`✕ Evolution Advisor failed: ${err.message}`, true);
    if (summaryEl) {
      summaryEl.innerHTML = `<span style="color: #fca5a5;">✕ Could not reach Evolution Advisor (${studioEscapeHtml(err.message)}). You can retry or add your own custom improvements below.</span>`;
    }
    if (listEl && studioEvolveSuggestions.length === 0) {
      listEl.innerHTML = `
        <div style="grid-column: 1 / -1; padding: 11px 13px; border-radius: 8px; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.35); display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
          <span style="font-size: 11.5px; color: #fecaca;">Failed to load LLM suggestions: ${studioEscapeHtml(err.message)}</span>
          <button title="Retry generating 10 tailored improvements via connected LLM" type="button" class="btn" onclick="regenerateStudioEvolveSuggestions()" style="padding: 4px 10px; font-size: 11px; color: #fca5a5; border-color: rgba(248, 113, 113, 0.4);">🔄 Retry</button>
        </div>
      `;
    } else {
      renderStudioEvolveSuggestionsList();
    }
  } finally {
    clearInterval(regenTimer);
    if (reqSeq === studioEvolveRequestSeq && regenBtn) {
      regenBtn.disabled = false;
      regenBtn.style.cursor = '';
      regenBtn.textContent = '🔄 Regenerate 10';
    }
  }
}

function regenerateStudioEvolveSuggestions() {
  if (!wizardEditAgentId) return;
  fetchStudioEvolveSuggestions(wizardEditAgentId, { forceRefresh: true });
}

function renderStudioEvolveSuggestionsList() {
  const listEl = document.getElementById('studioEvolveSuggestionsList');
  const countBadge = document.getElementById('studioEvolveCountBadge');
  const selBadge = document.getElementById('studioEvolveSelectedCountBadge');
  if (!listEl) return;

  const totalCount = studioEvolveSuggestions.length;
  const selectedCount = studioEvolveSuggestions.filter(s => s && s.selected).length;
  if (countBadge) countBadge.textContent = `${totalCount} improvement${totalCount === 1 ? '' : 's'}`;
  if (selBadge) {
    selBadge.textContent = `${selectedCount} selected`;
    selBadge.style.background = selectedCount > 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(56, 189, 248, 0.14)';
    selBadge.style.borderColor = selectedCount > 0 ? 'rgba(16, 185, 129, 0.45)' : 'rgba(56, 189, 248, 0.32)';
    selBadge.style.color = selectedCount > 0 ? '#6ee7b7' : '#38bdf8';
  }

  if (totalCount === 0) {
    listEl.innerHTML = `<div style="grid-column: 1 / -1; padding: 10px; font-size: 11.5px; color: #94a3b8;">No suggestions loaded yet. Click <strong>🔄 Regenerate 10</strong> or add a custom improvement below.</div>`;
    return;
  }

  let llmCounter = 0;
  listEl.innerHTML = studioEvolveSuggestions.map((s, idx) => {
    const isChecked = Boolean(s.selected);
    const numLabel = s.is_custom ? 'CUSTOM' : `#${++llmCounter}`;
    const borderCol = isChecked
      ? 'rgba(16, 185, 129, 0.58)'
      : (s.recommended ? 'rgba(168, 85, 247, 0.38)' : 'rgba(148, 163, 184, 0.2)');
    const bgCol = isChecked
      ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.16), rgba(15, 23, 42, 0.9))'
      : 'rgba(15, 23, 42, 0.78)';

    let tagBadge = '';
    if (s.is_custom) {
      tagBadge = `<span style="font-size: 9.5px; padding: 1px 6px; border-radius: 999px; background: rgba(56, 189, 248, 0.18); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.38); font-weight: 700;">USER ADDED</span>`;
    } else if (s.recommended) {
      tagBadge = `<span style="font-size: 9.5px; padding: 1px 6px; border-radius: 999px; background: rgba(251, 191, 36, 0.16); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.38); font-weight: 700;">⭐ TOP PICK</span>`;
    } else if (s.impact === 'high') {
      tagBadge = `<span style="font-size: 9.5px; padding: 1px 6px; border-radius: 999px; background: rgba(168, 85, 247, 0.16); color: #d8b4fe; border: 1px solid rgba(168, 85, 247, 0.32);">High Impact</span>`;
    }

    const removeBtn = s.is_custom
      ? `<button title="Remove this custom improvement" type="button" class="btn" onclick="event.stopPropagation(); removeCustomEvolveImprovement(${idx});" style="padding: 1px 6px; font-size: 10px; line-height: 1.2; color: #fca5a5; border-color: rgba(248, 113, 113, 0.35); background: transparent;">✕</button>`
      : '';

    const pillsHtml = (Array.isArray(s.change_pills) && s.change_pills.length > 0)
      ? `<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px;">
          ${s.change_pills.map(p => `<span style="font-size: 9.5px; padding: 1px 6px; border-radius: 5px; background: rgba(30, 41, 59, 0.92); border: 1px solid rgba(56, 189, 248, 0.24); color: #bae6fd;">${studioEscapeHtml(p)}</span>`).join('')}
        </div>`
      : '';

    return `
      <div onclick="toggleStudioEvolveSuggestion(${idx})" style="cursor: pointer; padding: 9px 11px; border-radius: 8px; background: ${bgCol}; border: 1px solid ${borderCol}; transition: border-color 0.15s ease, background 0.15s ease; display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 6px;">
            <label onclick="event.stopPropagation();" style="display: flex; align-items: flex-start; gap: 7px; cursor: pointer; flex: 1;">
              <input type="checkbox" ${isChecked ? 'checked' : ''} onchange="toggleStudioEvolveSuggestion(${idx}, this.checked)" style="margin-top: 2px; accent-color: #10b981; cursor: pointer;">
              <span style="font-size: 12px; font-weight: 700; color: #f8fafc; line-height: 1.3;">
                <span style="font-size: 10px; color: #a78bfa; font-weight: 700; margin-right: 3px;">${studioEscapeHtml(numLabel)}</span>
                ${studioEscapeHtml(s.icon || '✨')} ${studioEscapeHtml(s.title)}
              </span>
            </label>
            <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
              ${tagBadge}
              ${removeBtn}
            </div>
          </div>
          <div style="font-size: 11px; color: #cbd5e1; line-height: 1.38; margin-top: 5px; padding-left: 20px;">
            ${studioEscapeHtml(s.description)}
          </div>
        </div>
        <div style="padding-left: 20px;">
          ${pillsHtml}
        </div>
      </div>
    `;
  }).join('');
}

function toggleStudioEvolveSuggestion(idx, explicitChecked = undefined) {
  const item = studioEvolveSuggestions[idx];
  if (!item) return;
  item.selected = explicitChecked !== undefined ? Boolean(explicitChecked) : !item.selected;
  renderStudioEvolveSuggestionsList();
  syncSelectedEvolveSuggestionsToWizard();
}

function selectPresetEvolveSuggestions(mode) {
  if (!Array.isArray(studioEvolveSuggestions) || studioEvolveSuggestions.length === 0) {
    if (studioEvolveLoading) {
      showFleetToast('⏳ Still generating 10 AI suggestions — please wait a moment...', false, { variant: 'loading', durationMs: 3000 });
    } else {
      showFleetToast('No suggestions loaded yet. Click "🔄 Regenerate 10" or add a custom improvement.', true);
    }
    return;
  }
  if (mode === 'all') {
    studioEvolveSuggestions.forEach(s => { s.selected = true; });
  } else if (mode === 'none') {
    studioEvolveSuggestions.forEach(s => { s.selected = false; });
  } else if (mode === 'top3') {
    let picked = 0;
    studioEvolveSuggestions.forEach(s => {
      if (s.is_custom) {
        s.selected = true;
      } else if (s.recommended && picked < 3) {
        s.selected = true;
        picked += 1;
      } else {
        s.selected = false;
      }
    });
    if (picked < 3) {
      studioEvolveSuggestions.forEach(s => {
        if (!s.is_custom && !s.selected && picked < 3) {
          s.selected = true;
          picked += 1;
        }
      });
    }
  }
  renderStudioEvolveSuggestionsList();
  syncSelectedEvolveSuggestionsToWizard();
  const selCount = studioEvolveSuggestions.filter(s => s && s.selected).length;
  if (mode === 'top3') {
    showFleetToast(`⭐ Selected top ${selCount} recommended improvement(s)!`, false);
  } else if (mode === 'all') {
    showFleetToast(`☑️ Selected all ${selCount} improvements!`, false);
  } else if (mode === 'none') {
    showFleetToast('Cleared selected improvements — restored current agent blueprint.', false);
  }
}

function buildClientFallbackCustomSuggestion(cleanText) {
  const shortTitle = cleanText.length <= 58 ? cleanText : (cleanText.slice(0, 55).trimEnd() + '...');
  return {
    id: `custom_${Date.now()}`,
    title: shortTitle,
    description: `Custom user-defined evolution requirement: ${cleanText}`,
    category: 'Custom Enhancement',
    impact: 'high',
    icon: '➕',
    recommended: true,
    is_custom: true,
    selected: true,
    patch: {
      system_prompt_directive: cleanText,
      code_enhancement_brief: cleanText,
    },
    change_pills: ['+AI Prompt Rule', '+Deep-Build Logic'],
  };
}

async function addCustomEvolveImprovement() {
  const inp = document.getElementById('studioCustomImprovementInput');
  const cleanText = (inp ? inp.value : '').trim();
  if (!cleanText) {
    showFleetToast('Type a custom improvement in the box first before clicking Add.', true);
    if (inp) inp.focus();
    return;
  }

  await runFleetAsyncAction({
    buttons: ['btnAddCustomEvolveImprovement'],
    busyLabel: '⏳ Adding...',
    useStudioBanner: false,
    errorPrefix: 'Could not add custom improvement',
  }, async () => {
    let newSuggestion = null;
    try {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/evolve/parse_custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: cleanText,
          id: wizardEditAgentId || undefined,
          spec: buildCurrentWizardSpecPayload(),
        }),
      });
      if (res.ok && data && data.suggestion) {
        newSuggestion = {
          ...data.suggestion,
          is_custom: true,
          selected: true,
        };
      }
    } catch (_) {
      newSuggestion = null;
    }

    if (!newSuggestion) {
      newSuggestion = buildClientFallbackCustomSuggestion(cleanText);
    }
    studioEvolveSuggestions = [newSuggestion, ...studioEvolveSuggestions];
    if (inp) {
      inp.value = '';
      inp.rows = 2;
    }
    const metaBar = document.getElementById('studioCustomImproviseMetaBar');
    if (metaBar) metaBar.style.display = 'none';
    renderStudioEvolveSuggestionsList();
    syncSelectedEvolveSuggestionsToWizard();
    showFleetToast(`➕ Added custom improvement: "${newSuggestion.title}"`, false);
  });
}

let _lastModalImproviseOriginalText = '';

async function improviseCustomEvolvePrompt() {
  const inp = document.getElementById('studioCustomImprovementInput');
  const rawText = (inp ? inp.value : '').trim();
  if (!rawText) {
    showFleetToast('Type a draft improvement idea first, then click "🪄 Improvise Prompt (LLM)" to enhance it.', true);
    if (inp) inp.focus();
    return;
  }
  const btn = document.getElementById('btnImproviseModalPrompt');
  const origLabel = btn ? btn.textContent : '🪄 Improvise Prompt (LLM)';
  const providerSel = document.getElementById('studioEvolveLlmProvider');
  const provider = providerSel ? providerSel.value : 'auto';
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ Improvising...';
  }
  try {
    _lastModalImproviseOriginalText = rawText;
    const res = await fetch('/api/studio/evolve/improvise', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: wizardEditAgentId || undefined,
        text: rawText,
        provider,
        spec: buildCurrentWizardSpecPayload(),
      }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Could not improvise prompt.');
    }
    const enhanced = String(data.improvised_text || rawText).trim();
    if (inp) {
      inp.value = enhanced;
      inp.rows = Math.min(6, Math.max(3, enhanced.split('\n').length));
      inp.focus();
    }
    const metaBar = document.getElementById('studioCustomImproviseMetaBar');
    if (metaBar) {
      const esc = (s) => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      metaBar.style.display = 'flex';
      metaBar.innerHTML = `
        <div>
          ✨ <strong>Enhanced for ${esc(data.agent_name || wizardEditAgentId || 'Agent')}</strong>
          via <code>${esc(data.model_used || 'LLM')}</code>
          <span style="color: #cbd5e1;">• Context: ${esc(data.domain_title || data.context_summary || '')} — Review or edit above before clicking ➕ Add Improvement.</span>
        </div>
        <button type="button" class="btn" onclick="restoreOriginalModalImproviseDraft()" style="padding: 3px 9px; font-size: 10.5px; border-color: rgba(248, 250, 252, 0.3); color: #f8fafc;">↩️ Restore Original</button>
      `;
    }
    showFleetToast(`🪄 Prompt enhanced with ${data.agent_name || 'agent'} context! Review before adding.`, false);
  } catch (err) {
    showFleetToast(`✕ Could not improvise prompt: ${err.message}`, true);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = origLabel;
    }
  }
}

function restoreOriginalModalImproviseDraft() {
  const inp = document.getElementById('studioCustomImprovementInput');
  if (inp && _lastModalImproviseOriginalText) {
    inp.value = _lastModalImproviseOriginalText;
    inp.rows = Math.min(5, Math.max(2, _lastModalImproviseOriginalText.split('\n').length));
    inp.focus();
  }
  const metaBar = document.getElementById('studioCustomImproviseMetaBar');
  if (metaBar) metaBar.style.display = 'none';
}

function removeCustomEvolveImprovement(idx) {
  const item = studioEvolveSuggestions[idx];
  if (!item || !item.is_custom) return;
  studioEvolveSuggestions.splice(idx, 1);
  renderStudioEvolveSuggestionsList();
  syncSelectedEvolveSuggestionsToWizard();
}

function getSelectedEvolutionImprovementsMetadata() {
  const basePrev = Array.isArray(studioEvolveBaseSnapshot?.evolution_improvements)
    ? studioEvolveBaseSnapshot.evolution_improvements
    : [];
  const activeSelected = studioEvolveSuggestions
    .filter(s => s && s.selected)
    .map(s => ({
      id: s.id || '',
      title: s.title || '',
      description: s.description || '',
      code_enhancement_brief: s.patch?.code_enhancement_brief || s.description || s.title || '',
      is_custom: Boolean(s.is_custom),
    }));
  const merged = [];
  const seen = new Set();
  [...basePrev, ...activeSelected].forEach(it => {
    const t = String(it?.title || '').trim();
    if (!t || seen.has(t.toLowerCase())) return;
    seen.add(t.toLowerCase());
    merged.push({
      id: String(it.id || ''),
      title: t,
      description: String(it.description || ''),
      code_enhancement_brief: String(it.code_enhancement_brief || it.description || ''),
      is_custom: Boolean(it.is_custom),
    });
  });
  return merged;
}

function syncSelectedEvolveSuggestionsToWizard() {
  if (!wizardEditAgentId || !studioEvolveBaseSnapshot) return;

  const base = JSON.parse(JSON.stringify(studioEvolveBaseSnapshot));
  // Preserve manual identity edits made in Step 1/2 while folding selected capability patches cleanly
  const liveName = document.getElementById('newAgentName')?.value?.trim();
  const liveIcon = document.getElementById('newAgentIcon')?.value?.trim();
  const liveDesc = document.getElementById('newAgentDesc')?.value?.trim();
  const liveCat = document.getElementById('newAgentCategory')?.value;
  const liveTask = document.getElementById('newAgentTaskName')?.value?.trim();
  const liveModel = document.getElementById('newAgentModel')?.value?.trim();
  if (liveName) base.name = liveName;
  if (liveIcon) base.icon = liveIcon;
  if (liveDesc !== undefined && liveDesc !== '') base.description = liveDesc;
  if (liveCat) base.category = liveCat;
  if (liveTask) base.routine_task = liveTask;
  if (liveModel) base.model = liveModel;

  const directives = [];
  const selectedItems = studioEvolveSuggestions.filter(s => s && s.selected);
  selectedItems.forEach(s => {
    const p = (s.patch && typeof s.patch === 'object') ? s.patch : {};
    if (Array.isArray(p.add_blocks)) {
      p.add_blocks.forEach(b => {
        if (b && !base.ui_blocks.includes(b)) base.ui_blocks.push(b);
      });
    }
    if (Array.isArray(p.add_permissions)) {
      p.add_permissions.forEach(perm => {
        if (perm && !base.permissions.includes(perm)) base.permissions.push(perm);
      });
    }
    if (p.add_field && typeof p.add_field === 'object' && p.add_field.key) {
      const existsKey = base.fields.some(f => f && f.key === p.add_field.key);
      if (!existsKey && base.fields.length < 5) {
        base.fields.push({ ...p.add_field });
      }
    }
    if (Array.isArray(p.add_event_triggers)) {
      p.add_event_triggers.forEach(t => {
        if (t && !base.event_triggers.includes(t)) base.event_triggers.push(t);
      });
    }
    if (Array.isArray(p.add_outbound_actions)) {
      p.add_outbound_actions.forEach(a => {
        if (a && !base.outbound_actions.includes(a)) base.outbound_actions.push(a);
      });
    }
    if (p.set_recurrence && p.set_recurrence !== 'none') {
      base.default_recurrence = p.set_recurrence;
    }
    if (p.set_auto_ingest_inbox === true) {
      base.auto_ingest_inbox = true;
    }
    if (p.set_schedule_cadence) {
      base.schedule_cadence = p.set_schedule_cadence;
    }
    if (p.set_intelligence_mode) {
      base.intelligence_mode = p.set_intelligence_mode;
    }
    if (Array.isArray(p.add_checklist_items)) {
      p.add_checklist_items.forEach(c => {
        const lbl = typeof c === 'object' ? String(c.label || '').trim() : String(c || '').trim();
        if (!lbl) return;
        const dup = base.checklist_items.some(ex => {
          const exLbl = typeof ex === 'object' ? String(ex.label || '').trim() : String(ex || '').trim();
          return exLbl.toLowerCase() === lbl.toLowerCase();
        });
        if (!dup) {
          const cKey = (typeof c === 'object' && c.key)
            ? c.key
            : lbl.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 28);
          base.checklist_items.push({ key: cKey || `chk_${base.checklist_items.length + 1}`, label: lbl });
        }
      });
    }
    if (p.system_prompt_directive && String(p.system_prompt_directive).trim()) {
      const dir = String(p.system_prompt_directive).trim();
      if (!directives.includes(dir) && !(base.system_prompt || '').includes(dir)) {
        directives.push(dir);
      }
    }
  });

  if (directives.length > 0) {
    const basePrompt = (base.system_prompt || '').trim();
    const bulletBlock = directives.map(d => `- ${d}`).join('\n');
    base.system_prompt = basePrompt
      ? `${basePrompt}\n\nEvolution Directives:\n${bulletBlock}`
      : `Evolution Directives:\n${bulletBlock}`;
  }

  populateWizardFromSpec(base);
  const systemPromptEl = document.getElementById('newAgentSystemPrompt');
  if (systemPromptEl) systemPromptEl.value = base.system_prompt || '';
}

function previewSelectedEvolveImprovements() {
  syncSelectedEvolveSuggestionsToWizard();
  switchCodePreviewTab('visual');
  goToWizardStep(4);
  const selCount = studioEvolveSuggestions.filter(s => s && s.selected).length;
  showFleetToast(
    selCount > 0
      ? `👁️ Applied ${selCount} selected improvement(s) to Step 4 Visual Preview!`
      : '👁️ Opened Step 4 Visual Preview & Sandbox Dry-Run.',
    false
  );
}

async function applySelectedEvolveAndReload() {
  const pendingCustom = (document.getElementById('studioCustomImprovementInput')?.value || '').trim();
  if (pendingCustom) {
    await addCustomEvolveImprovement();
  }
  syncSelectedEvolveSuggestionsToWizard();
  await submitCreateAgentWizard({ expressOpen: true });
}

async function applySelectedEvolveAndDeepBuild() {
  const pendingCustom = (document.getElementById('studioCustomImprovementInput')?.value || '').trim();
  if (pendingCustom) {
    await addCustomEvolveImprovement();
  }
  syncSelectedEvolveSuggestionsToWizard();
  await deepBuildWithAntigravity();
}

async function loadAgentRevisionsForStudio(agentId) {
  const bar = document.getElementById('studioRevisionRollbackBar');
  const sel = document.getElementById('studioRevisionSelect');
  const badge = document.getElementById('studioRevisionCountBadge');
  if (!bar || !sel) return;
  bar.style.display = 'none';
  if (!agentId) return;
  try {
    const res = await fetch(`/api/settings/agents/revisions?id=${encodeURIComponent(agentId)}`);
    if (!res.ok) return;
    const data = await res.json();
    const revs = Array.isArray(data.revisions) ? data.revisions : [];
    if (revs.length === 0) return;
    if (badge) badge.textContent = `${revs.length} saved snapshot${revs.length === 1 ? '' : 's'}`;
    sel.innerHTML = revs.map((r, i) => {
      const ts = (r.created_at || '').slice(0, 19).replace('T', ' ');
      const tag = i === 0 ? ' (Latest)' : '';
      return `<option value="${studioEscapeHtml(r.revision_id)}">${studioEscapeHtml(ts)}${tag} — ${studioEscapeHtml(r.summary || r.revision_id)}</option>`;
    }).join('');
    bar.style.display = 'flex';
  } catch (_) {
    bar.style.display = 'none';
  }
}

async function rollbackCurrentAgentRevision() {
  if (!wizardEditAgentId) return;
  const sel = document.getElementById('studioRevisionSelect');
  const revisionId = sel?.value || '';
  await runFleetAsyncAction({
    buttons: ['btnStudioRollbackRevision'],
    busyLabel: '⏳ Restoring Revision...',
    bannerMessage: `⏪ Restoring selected blueprint snapshot for '${wizardEditAgentId}' (preserving 100% of SQLite records)...`,
    startToast: `⏳ Restoring blueprint revision for '${wizardEditAgentId}'...`,
    errorPrefix: 'Revision rollback failed',
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry('/api/settings/agents/rollback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: wizardEditAgentId, revision_id: revisionId || undefined }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Rollback failed.');
    }
    newlyCreatedAgentId = data.agent_id || wizardEditAgentId;
    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();
    showFleetToast(`⏪ Restored '${data.manifest?.name || wizardEditAgentId}' from revision (SQLite records preserved)!`, false);
    openNewlyCreatedAgent();
  });
}

function closeCreateAgentModal() {
  if (typeof window.StudioActivityRecorder?.cleanup === 'function') {
    window.StudioActivityRecorder.cleanup();
  }
  const modal = document.getElementById('createAgentModal');
  if (modal) modal.style.display = 'none';
}

function closeCreateAgentModalOnBackdrop(e) {
  if (e && e.target && e.target.id === 'createAgentModal') {
    closeCreateAgentModal();
  }
}

function getExistingFleetAgentsMap() {
  const map = new Map();
  const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
  (nav?.agents || []).forEach(a => map.set(a.id, a));
  return map;
}

function resolveUniqueAgentId(desiredId) {
  let clean = String(desiredId || '')
    .toLowerCase()
    .replace(/[^a-z0-9_]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
  if (!clean) clean = 'custom_agent';
  if (wizardEditAgentId) return wizardEditAgentId;
  const existing = getExistingFleetAgentsMap();
  if (!existing.has(clean)) return clean;
  for (let n = 2; n <= 50; n++) {
    const candidate = `${clean}_${n}`;
    if (!existing.has(candidate)) return candidate;
  }
  return `${clean}_${Date.now() % 1000}`;
}

function checkWizardAgentIdCollision() {
  const statusEl = document.getElementById('newAgentIdStatus');
  const idEl = document.getElementById('newAgentId');
  if (!statusEl || !idEl) return;

  const raw = (idEl.value || '').trim().toLowerCase();
  if (wizardEditAgentId) {
    statusEl.style.color = '#d8b4fe';
    statusEl.innerHTML = `✏️ Evolving <code>${studioEscapeHtml(wizardEditAgentId)}</code> in-place — existing SQLite records preserved.`;
    return;
  }
  if (!raw) {
    statusEl.style.color = 'var(--text-muted)';
    statusEl.textContent = 'Auto-derived from name (lowercase snake_case).';
    return;
  }

  const existing = getExistingFleetAgentsMap();
  const hit = existing.get(raw);
  if (!hit) {
    statusEl.style.color = '#34d399';
    statusEl.innerHTML = `✓ ID <code>${studioEscapeHtml(raw)}</code> is available`;
  } else if (hit.is_custom) {
    const suggested = resolveUniqueAgentId(raw);
    statusEl.style.color = '#fbbf24';
    statusEl.innerHTML = `⚠️ <code>${studioEscapeHtml(raw)}</code> exists — will launch as <code>${studioEscapeHtml(suggested)}</code> or <a href="#" onclick="event.preventDefault(); openEvolveAgentModal('${studioEscapeHtml(raw)}');" style="color: #d8b4fe; text-decoration: underline;">Evolve existing instead</a>`;
  } else {
    const suggested = resolveUniqueAgentId(raw);
    statusEl.style.color = '#fbbf24';
    statusEl.innerHTML = `⚠️ Reserved core ID — will auto-suffix to <code>${studioEscapeHtml(suggested)}</code>`;
  }
}

function onNewAgentNameInput(name) {
  if (!wizardEditAgentId) {
    const idInput = document.getElementById('newAgentId');
    if (idInput) {
      const slug = name
        .toLowerCase()
        .replace(/[^a-z0-9_]/g, '_')
        .replace(/_+/g, '_')
        .replace(/^_+|_+$/g, '');
      idInput.value = slug;
    }
  }
  checkWizardAgentIdCollision();
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function selectWizardIcon(icon) {
  const iconInput = document.getElementById('newAgentIcon');
  if (iconInput) iconInput.value = icon;
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function applyWizardPreset(preset) {
  const perms = {
    observer: ['ui:render', 'db:read', 'db:write', 'network:outbound'],
    notifier: ['ui:render', 'db:read', 'db:write', 'event_bus:publish'],
    analyst: ['ui:render', 'db:read', 'db:write'],
    autonomous: ['ui:render', 'db:read', 'db:write', 'event_bus:publish', 'network:outbound', 'system:diagnostics'],
  };
  const selected = perms[preset] || ['ui:render', 'db:read', 'db:write'];
  const idMap = {
    perm_ui_render: 'ui:render',
    perm_db_read: 'db:read',
    perm_db_write: 'db:write',
    perm_notifications_send: 'event_bus:publish',
    perm_network_http: 'network:outbound',
    perm_system_exec: 'system:diagnostics',
  };
  Object.entries(idMap).forEach(([cid, permKey]) => {
    const el = document.getElementById(cid);
    if (el) el.checked = selected.includes(permKey);
  });

  document.querySelectorAll('.wizard-preset-card').forEach(card => card.classList.remove('active-preset'));
  if (window.event && window.event.currentTarget) {
    window.event.currentTarget.classList.add('active-preset');
  }
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function getSelectedPermissions() {
  const checked = [];
  const map = {
    perm_ui_render: 'ui:render',
    perm_db_read: 'db:read',
    perm_db_write: 'db:write',
    perm_notifications_send: 'event_bus:publish',
    perm_network_http: 'network:outbound',
    perm_system_exec: 'system:diagnostics',
  };
  for (const [id, perm] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el && el.checked) checked.push(perm);
  }
  return checked.length > 0 ? checked : ['ui:render', 'db:read', 'db:write'];
}

function getSelectedUiBlocks() {
  const blockIds = [
    'alert_banner',
    'kpi_row',
    'document_vault',
    'quick_capture_bar',
    'countdown_cards',
    'kanban_board',
    'sparkline_chart',
    'ai_insight_card',
    'agent_chat',
    'history_table',
    'habit_checklist',
    'status_timeline',
  ];
  const selected = [];
  blockIds.forEach(b => {
    const el = document.getElementById(`uiBlock_${b}`);
    if (el && el.checked) selected.push(b);
  });
  return selected.length > 0 ? selected : ['kpi_row', 'quick_capture_bar', 'history_table'];
}

function getSelectedEventTriggers() {
  const selected = [];
  document.querySelectorAll('.studio-event-trigger-cb').forEach(cb => {
    if (cb && cb.checked && cb.value) selected.push(cb.value);
  });
  return selected;
}

function setSelectedEventTriggers(triggers) {
  const active = new Set(Array.isArray(triggers) ? triggers : []);
  document.querySelectorAll('.studio-event-trigger-cb').forEach(cb => {
    if (cb) cb.checked = active.has(cb.value);
  });
}

function getSelectedOutboundActions() {
  const selected = [];
  document.querySelectorAll('.studio-outbound-action-cb').forEach(cb => {
    if (cb && cb.checked && cb.value) selected.push(cb.value);
  });
  return selected;
}

function setSelectedOutboundActions(actions) {
  const active = new Set(Array.isArray(actions) ? actions : []);
  document.querySelectorAll('.studio-outbound-action-cb').forEach(cb => {
    if (cb) cb.checked = active.has(cb.value);
  });
}

// --- Typed Domain Fields Editor (Step 3) ---
function renderStudioFieldsEditor() {
  const box = document.getElementById('studioFieldsEditorList');
  if (!box) return;
  box.innerHTML = studioCurrentFields.map((fld, idx) => `
    <div style="display: grid; grid-template-columns: 1.3fr 1fr 110px 1.4fr 32px; gap: 6px; align-items: center;">
      <input type="text" value="${studioEscapeHtml(fld.label)}" placeholder="Field Label"
        oninput="onStudioFieldEdit(${idx}, 'label', this.value)"
        style="padding: 6px 8px; border-radius: 6px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.35); color: var(--text); font-size: 12px;">
      <input type="text" value="${studioEscapeHtml(fld.key)}" placeholder="field_key"
        oninput="onStudioFieldEdit(${idx}, 'key', this.value)"
        style="padding: 6px 8px; border-radius: 6px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.35); color: var(--accent-cyan); font-family: monospace; font-size: 11.5px;">
      <select onchange="onStudioFieldEdit(${idx}, 'type', this.value)"
        style="padding: 6px 6px; border-radius: 6px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.35); color: var(--text); font-size: 12px;">
        <option value="text" ${fld.type === 'text' ? 'selected' : ''}>Text</option>
        <option value="date" ${fld.type === 'date' ? 'selected' : ''}>Date</option>
        <option value="number" ${fld.type === 'number' ? 'selected' : ''}>Number</option>
        <option value="url" ${fld.type === 'url' ? 'selected' : ''}>URL</option>
      </select>
      <input type="text" value="${studioEscapeHtml(fld.placeholder || '')}" placeholder="Placeholder hint..."
        oninput="onStudioFieldEdit(${idx}, 'placeholder', this.value)"
        style="padding: 6px 8px; border-radius: 6px; border: 1px solid var(--border-color); background: rgba(0,0,0,0.35); color: var(--text-muted); font-size: 11.5px;">
      <button type="button" class="btn" title="Remove field" ${studioCurrentFields.length <= 1 ? 'disabled' : ''}
        onclick="removeStudioFieldRow(${idx})"
        style="padding: 4px 6px; font-size: 11px; color: #f87171;">✕</button>
    </div>
  `).join('');
}

function onStudioFieldEdit(idx, prop, val) {
  if (!studioCurrentFields[idx]) return;
  if (prop === 'key') {
    studioCurrentFields[idx].key = val.toLowerCase().replace(/[^a-z0-9_]/g, '_');
  } else {
    studioCurrentFields[idx][prop] = val;
    if (prop === 'label' && idx > 0) {
      studioCurrentFields[idx].key = val.toLowerCase().replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '') || `field_${idx + 1}`;
    }
  }
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function addStudioFieldRow() {
  if (studioCurrentFields.length >= 5) {
    if (typeof showFleetToast === 'function') showFleetToast('Maximum 5 Quick-Capture fields per agent.', true);
    return;
  }
  const n = studioCurrentFields.length + 1;
  studioCurrentFields.push({
    key: `custom_field_${n}`,
    label: `Custom Field ${n}`,
    type: 'text',
    placeholder: 'Enter value...',
  });
  renderStudioFieldsEditor();
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function removeStudioFieldRow(idx) {
  if (studioCurrentFields.length <= 1) return;
  studioCurrentFields.splice(idx, 1);
  renderStudioFieldsEditor();
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function populateWizardFromSpec(spec) {
  const nameEl = document.getElementById('newAgentName');
  const idEl = document.getElementById('newAgentId');
  const iconEl = document.getElementById('newAgentIcon');
  const categoryEl = document.getElementById('newAgentCategory');
  const descEl = document.getElementById('newAgentDesc');
  const taskEl = document.getElementById('newAgentTaskName');
  const scheduleEl = document.getElementById('newAgentSchedule');
  const syncIntervalEl = document.getElementById('settingSyncInterval');
  const enableAlertsEl = document.getElementById('settingEnableAlerts');
  const systemPromptEl = document.getElementById('newAgentSystemPrompt');
  const modeEl = document.getElementById('newAgentIntelligenceMode');
  const modelEl = document.getElementById('newAgentModel');
  const archEl = document.getElementById('newAgentArchetype');

  if (nameEl) nameEl.value = spec.name || '';
  if (idEl && !wizardEditAgentId) {
    idEl.value = resolveUniqueAgentId(spec.agent_id || spec.name || '');
  }
  if (iconEl) iconEl.value = spec.icon || '✨';

  if (categoryEl && spec.category) {
    let matched = false;
    for (let i = 0; i < categoryEl.options.length; i++) {
      if (categoryEl.options[i].value.toLowerCase() === spec.category.toLowerCase() ||
          categoryEl.options[i].text.toLowerCase().includes(spec.category.toLowerCase())) {
        categoryEl.selectedIndex = i;
        matched = true;
        break;
      }
    }
    if (!matched && categoryEl.options.length > 0) categoryEl.selectedIndex = 0;
  }

  if (descEl) descEl.value = spec.description || '';
  if (modeEl && spec.intelligence_mode) modeEl.value = spec.intelligence_mode;
  if (modelEl && spec.model) modelEl.value = spec.model;
  if (archEl && spec.archetype) archEl.value = spec.archetype;
  if (spec.workflow_ir && typeof spec.workflow_ir === 'object') {
    studioCurrentWorkflowIr = spec.workflow_ir;
  }
  if (spec.requirements_doc && typeof spec.requirements_doc === 'object') {
    studioCurrentRequirementsDoc = spec.requirements_doc;
  }
  if (spec.recording_id) {
    studioCurrentRecordingId = String(spec.recording_id);
  }

  const perms = spec.permissions || ['db:read', 'db:write', 'ui:render'];
  const permCheckMap = {
    perm_ui_render: perms.includes('ui:render'),
    perm_db_read: perms.includes('db:read'),
    perm_db_write: perms.includes('db:write'),
    perm_notifications_send: perms.includes('event_bus:publish') || perms.includes('notifications:send'),
    perm_network_http: perms.includes('network:outbound') || perms.includes('network:http'),
    perm_system_exec: perms.includes('system:diagnostics') || perms.includes('system:exec'),
  };
  Object.entries(permCheckMap).forEach(([cid, isChecked]) => {
    const el = document.getElementById(cid);
    if (el) el.checked = isChecked;
  });

  if (syncIntervalEl && spec.sync_interval != null) syncIntervalEl.value = spec.sync_interval;
  if (enableAlertsEl && spec.enable_alerts != null) enableAlertsEl.value = spec.enable_alerts ? 'true' : 'false';
  if (taskEl) taskEl.value = spec.routine_task || 'run_check';
  if (scheduleEl && spec.schedule_cadence) scheduleEl.value = spec.schedule_cadence;
  if (systemPromptEl && spec.system_prompt) systemPromptEl.value = spec.system_prompt;

  if (spec.schedule && typeof spec.schedule === 'object') {
    studioCurrentSchedule = spec.schedule;
  }
  if (Array.isArray(spec.fields) && spec.fields.length > 0) {
    studioCurrentFields = spec.fields.map(f => ({ ...f }));
  }
  if (Array.isArray(spec.checklist_items) && spec.checklist_items.length > 0) {
    studioCurrentChecklist = spec.checklist_items;
  }
  renderStudioFieldsEditor();

  const blocks = spec.ui_blocks || ['kpi_row', 'quick_capture_bar', 'history_table'];
  [
    'alert_banner', 'kpi_row', 'document_vault', 'quick_capture_bar', 'countdown_cards', 'kanban_board',
    'sparkline_chart', 'ai_insight_card', 'agent_chat', 'history_table', 'habit_checklist', 'status_timeline',
  ].forEach(b => {
    const el = document.getElementById(`uiBlock_${b}`);
    if (el) el.checked = blocks.includes(b);
  });
  setSelectedEventTriggers(spec.event_triggers || []);
  setSelectedOutboundActions(spec.outbound_actions || []);
  const recEl = document.getElementById('newAgentDefaultRecurrence');
  if (recEl) recEl.value = spec.default_recurrence || 'none';
  const inboxEl = document.getElementById('newAgentAutoIngestInbox');
  if (inboxEl) inboxEl.checked = spec.auto_ingest_inbox !== undefined ? Boolean(spec.auto_ingest_inbox) : blocks.includes('document_vault');

  for (let s = 1; s <= 3; s++) {
    const pill = document.getElementById(`wizardPill_${s}`);
    if (pill) pill.classList.add('completed');
  }

  checkWizardAgentIdCollision();
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function renderStudioSynthesisSummary(spec) {
  const box = document.getElementById('studioSynthesisSummaryBox');
  const headline = document.getElementById('studioSynthesisHeadline');
  const chipsRow = document.getElementById('studioClarifyingChipsRow');
  if (!box || !headline || !chipsRow) return;

  const schedLabel = spec.schedule?.display || 'Daily at 09:00';
  const blocksCount = getSelectedUiBlocks().length;
  const triggersCount = getSelectedEventTriggers().length;
  const trigBadge = triggersCount > 0 ? ` • ⚡ ${triggersCount} EventBus trigger(s)` : '';
  headline.innerHTML = `
    <span style="font-size: 16px;">${studioEscapeHtml(spec.icon || '✨')}</span>
    <strong style="color: #34d399; margin-left: 4px;">${studioEscapeHtml(spec.name)}</strong>
    <span style="color: #94a3b8; font-size: 11.5px; margin-left: 6px;">
      • ${studioEscapeHtml(spec.archetype || 'tracker')} • ${studioEscapeHtml(schedLabel)} • ${studioCurrentFields.length} typed fields • ${blocksCount} live widgets${trigBadge}
    </span>
  `;

  const chips = Array.isArray(spec.clarifying_chips) ? spec.clarifying_chips : [];
  if (chips.length > 0) {
    chipsRow.innerHTML = `<span style="font-size: 11px; color: #94a3b8; align-self: center;">1-Click Enrichments:</span>` +
      chips.map((ch, idx) => `
        <button type="button" class="btn" id="studioChipBtn_${idx}" onclick="applyClarifyingChip(${idx})"
          style="padding: 3px 9px; font-size: 11px; border-radius: 999px; border-color: rgba(168, 85, 247, 0.4); color: #e9d5ff; background: rgba(88, 28, 135, 0.25);">
          ${studioEscapeHtml(ch.label)}
        </button>
      `).join('');
  } else {
    chipsRow.innerHTML = '';
  }
  box.style.display = 'block';
}

function applyClarifyingChip(idx) {
  const chip = studioLastSynthesizedSpec?.clarifying_chips?.[idx];
  if (!chip) return;

  if (Array.isArray(chip.add_blocks)) {
    chip.add_blocks.forEach(b => {
      const el = document.getElementById(`uiBlock_${b}`);
      if (el) el.checked = true;
    });
  }
  if (Array.isArray(chip.add_permissions)) {
    if (chip.add_permissions.includes('network:outbound')) {
      const netEl = document.getElementById('perm_network_http');
      if (netEl) netEl.checked = true;
    }
    if (chip.add_permissions.includes('system:diagnostics')) {
      const sysEl = document.getElementById('perm_system_exec');
      if (sysEl) sysEl.checked = true;
    }
  }
  if (chip.add_field && chip.add_field.key) {
    const exists = studioCurrentFields.some(f => f.key === chip.add_field.key);
    if (!exists && studioCurrentFields.length < 5) {
      studioCurrentFields.push({ ...chip.add_field });
      renderStudioFieldsEditor();
    }
  }
  if (chip.set_intelligence_mode) {
    const modeEl = document.getElementById('newAgentIntelligenceMode');
    if (modeEl) modeEl.value = chip.set_intelligence_mode;
  }

  const btn = document.getElementById(`studioChipBtn_${idx}`);
  if (btn) {
    btn.disabled = true;
    btn.style.borderColor = 'rgba(16, 185, 129, 0.45)';
    btn.style.color = '#34d399';
    btn.textContent = `✓ ${chip.label.replace(/^[+⏳🧠✅🌐⏱️📄💬\s]+/, '')}`;
  }
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const res = String(reader.result || '');
      const commaIdx = res.indexOf(',');
      resolve(commaIdx >= 0 ? res.slice(commaIdx + 1) : res);
    };
    reader.onerror = () => reject(new Error('Could not read selected file.'));
    reader.readAsDataURL(file);
  });
}

function formatStudioBytes(bytes) {
  const n = Number(bytes || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

function handleStudioWizardFilesSelected(event) {
  const files = Array.from(event?.target?.files || []);
  if (files.length > 0) {
    enqueueStudioAttachments(files, true);
  }
  if (event?.target) {
    event.target.value = '';
  }
}

function handleStudioWizardDocDrop(event) {
  if (!event) return;
  event.preventDefault();
  const sec = document.getElementById('studioDocUploadSection');
  if (sec) sec.style.borderColor = 'rgba(56, 189, 248, 0.45)';
  const droppedFiles = Array.from(event.dataTransfer?.files || []);
  if (droppedFiles.length > 0) {
    enqueueStudioAttachments(droppedFiles, true);
  }
}

function enqueueStudioAttachments(fileList, autoAnalyze = true) {
  const incoming = Array.from(fileList || []).filter(f => f && typeof f.name === 'string');
  if (incoming.length === 0) return 0;

  let added = 0;
  for (const file of incoming) {
    if (file.size > 12 * 1024 * 1024) {
      const msg = `'${file.name}' exceeds the 12 MB per-attachment limit.`;
      if (typeof showFleetToast === 'function') showFleetToast(msg, true);
      else alert(msg);
      continue;
    }
    if (studioAttachmentQueue.length >= 10) {
      const msg = 'Maximum 10 attachments can be queued per agent creation batch.';
      if (typeof showFleetToast === 'function') showFleetToast(msg, true);
      else alert(msg);
      break;
    }
    const sig = `${file.name}::${file.size}`;
    const exists = studioAttachmentQueue.some(q => `${q.name}::${q.size}` === sig);
    if (!exists) {
      studioAttachmentQueue.push(file);
      added += 1;
    }
  }

  renderStudioAttachmentQueueTray();
  if (autoAnalyze && (added > 0 || studioAttachmentQueue.length > 0)) {
    analyzeStudioDocumentForWizard();
  }
  return added;
}

function removeQueuedStudioAttachment(idx) {
  if (idx < 0 || idx >= studioAttachmentQueue.length) return;
  studioAttachmentQueue.splice(idx, 1);
  if (studioAttachmentQueue.length === 0) {
    clearStudioStagedDocExtraction();
    return;
  }
  renderStudioAttachmentQueueTray();
}

function renderStudioAttachmentQueueTray() {
  const tray = document.getElementById('studioAttachmentQueueTray');
  if (!tray) return;
  if (!Array.isArray(studioAttachmentQueue) || studioAttachmentQueue.length === 0) {
    tray.style.display = 'none';
    tray.innerHTML = '';
    return;
  }

  const pillsHtml = studioAttachmentQueue.map((file, idx) => {
    const matchedDoc = studioStagedDocuments.find(d => d.filename === file.name);
    const icon = matchedDoc?.scenario_profile?.icon || '📄';
    const itemBadge = matchedDoc ? ` • <span style="color:#34d399;">${Number(matchedDoc.items_count || 0)} item(s)</span>` : '';
    return `
      <span style="display:inline-flex; align-items:center; gap:6px; padding:4px 9px; border-radius:999px; background:rgba(15,23,42,0.9); border:1px solid rgba(56,189,248,0.32); font-size:11px; color:#e2e8f0;">
        <span>${studioEscapeHtml(icon)}</span>
        <strong style="color:#f8fafc; max-width:190px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${studioEscapeHtml(file.name)}</strong>
        <span style="color:#94a3b8; font-size:10px;">(${formatStudioBytes(file.size)})${itemBadge}</span>
        <button type="button" title="Remove '${studioEscapeHtml(file.name)}' from attachment queue" onclick="removeQueuedStudioAttachment(${idx})" style="background:none; border:none; color:#f87171; cursor:pointer; font-size:11px; padding:0 2px; line-height:1;">✕</button>
      </span>
    `;
  }).join('');

  tray.style.display = 'block';
  tray.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px;">
      <span style="font-size:11px; color:#7dd3fc; font-weight:600;">📎 Queued Attachments (${studioAttachmentQueue.length}/10) — Click '+ Add Attachments' to queue more files, then 'Analyze Attachments &amp; Guide Workflow'</span>
      <button type="button" title="Clear all queued attachments and reset staged document guidance" class="btn" onclick="clearStudioStagedDocExtraction()" style="padding:2px 8px; font-size:10.5px; color:#fca5a5; border-color:rgba(248,113,113,0.3);">✕ Clear All</button>
    </div>
    <div style="display:flex; gap:6px; flex-wrap:wrap;">${pillsHtml}</div>
  `;
}

async function analyzeStudioDocumentForWizard(overrideFiles = null) {
  if (overrideFiles) {
    const list = overrideFiles instanceof File ? [overrideFiles] : Array.from(overrideFiles || []);
    enqueueStudioAttachments(list, false);
  } else if (studioAttachmentQueue.length === 0) {
    const fileInput = document.getElementById('studioWizardDocInput');
    const fallbackFiles = Array.from(fileInput?.files || []);
    if (fallbackFiles.length > 0) {
      enqueueStudioAttachments(fallbackFiles, false);
    }
  }

  if (studioAttachmentQueue.length === 0) {
    setStudioGlobalBanner('error', 'Select or drop one or more attachments first (PDF, DOCX, XLSX, CSV, EML, ICS, TXT, or Images).');
    showFleetToast('Select or drop one or more attachments first (PDF, DOCX, XLSX, CSV, EML, ICS, TXT, or Images).', true);
    return;
  }

  const prevBox = document.getElementById('studioWizardDocPreviewBox');
  const nlPrompt = (document.getElementById('wizardNaturalLanguageInput')?.value || '').trim();
  const modelVal = (document.getElementById('newAgentModel')?.value || '').trim();
  const providerVal = (document.getElementById('studioDocLlmProvider')?.value || 'auto').trim();
  const fileCount = studioAttachmentQueue.length;
  const namesPreview = studioAttachmentQueue.slice(0, 3).map(f => f.name).join(', ') + (fileCount > 3 ? ` (+${fileCount - 3} more)` : '');

  if (prevBox) {
    prevBox.style.display = 'block';
    prevBox.innerHTML = `<div style="font-size: 12px; color: #38bdf8;">⏳ Parsing <strong>${fileCount} attachment${fileCount > 1 ? 's' : ''}</strong> (${studioEscapeHtml(namesPreview)}) &amp; synthesizing guided agent workflow via AFCC's connected LLM...</div>`;
  }

  await runFleetAsyncAction({
    buttons: ['btnAnalyzeStudioDoc'],
    busyLabel: `⏳ Analyzing ${fileCount} Attachment${fileCount > 1 ? 's' : ''}...`,
    bannerMessage: `🧠 Parsing ${fileCount} attachment${fileCount > 1 ? 's' : ''} (${namesPreview}) & guiding agent workflow via connected LLM...`,
    startToast: `⏳ Analyzing ${fileCount} attachment${fileCount > 1 ? 's' : ''} via connected LLM...`,
    errorPrefix: 'Attachment analysis failed',
    onError: (err) => {
      if (prevBox) {
        prevBox.style.display = 'block';
        prevBox.innerHTML = `<div style="font-size: 12px; color: #fca5a5;">✕ Multi-attachment analysis error: ${studioEscapeHtml(err.message)}</div>`;
      }
    },
  }, async () => {
    const documentsPayload = await Promise.all(
      studioAttachmentQueue.map(async file => ({
        filename: file.name,
        content_base64: await readFileAsBase64(file),
      }))
    );

    const { res, data } = await studioFetchJsonWithRetry('/api/studio/documents/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        documents: documentsPayload,
        prompt: nlPrompt,
        id: wizardEditAgentId || undefined,
        provider: providerVal || 'auto',
        model: modelVal || undefined,
      }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Multi-attachment workflow analysis failed.');
    }

    if (data.connected_llm) {
      updateStudioConnectedLlmBadge(data.connected_llm);
    }

    studioStagedDocuments = Array.isArray(data.documents) ? data.documents : [];
    studioWorkflowGuidance = data.workflow_guidance || null;
    studioDocFilterFilename = '';

    if (data.spec) {
      studioLastSynthesizedSpec = data.spec;
      populateWizardFromSpec(data.spec);
      renderStudioSynthesisSummary(data.spec);
    }

    const ext = data.extraction || {};
    studioStagedDocExtraction = {
      ...ext,
      items: (Array.isArray(ext.items) ? ext.items : []).map(it => ({ ...it, _checked: true })),
    };

    renderStudioAttachmentQueueTray();
    renderStudioWizardDocPreview();
    renderStudioGuidedWorkflowRibbon();

    const docTotal = Number(data.attachments_count || studioStagedDocuments.length || 1);
    showFleetToast(
      `🧭 Guided '${data.spec?.name || 'Agent'}' from ${docTotal} attachment${docTotal > 1 ? 's' : ''} & staged ${studioStagedDocExtraction.items.length} tracking item(s)!`,
      false
    );
  });
}

function applyStudioGuidedAction(idx) {
  const act = studioWorkflowGuidance?.guided_actions?.[idx];
  if (!act) return;

  if (Array.isArray(act.add_blocks)) {
    act.add_blocks.forEach(b => {
      const el = document.getElementById(`uiBlock_${b}`);
      if (el) el.checked = true;
    });
  }
  if (Array.isArray(act.add_permissions)) {
    if (act.add_permissions.includes('network:outbound')) {
      const netEl = document.getElementById('perm_network_http');
      if (netEl) netEl.checked = true;
    }
    if (act.add_permissions.includes('system:diagnostics')) {
      const sysEl = document.getElementById('perm_system_exec');
      if (sysEl) sysEl.checked = true;
    }
    if (act.add_permissions.includes('event_bus:publish')) {
      const evtEl = document.getElementById('perm_notifications_send');
      if (evtEl) evtEl.checked = true;
    }
  }
  if (act.add_field && act.add_field.key) {
    const exists = studioCurrentFields.some(f => f.key === act.add_field.key);
    if (!exists && studioCurrentFields.length < 5) {
      studioCurrentFields.push({ ...act.add_field });
      renderStudioFieldsEditor();
    }
  }
  if (act.set_recurrence) {
    const recEl = document.getElementById('newAgentDefaultRecurrence');
    if (recEl) recEl.value = act.set_recurrence;
  }
  if (Array.isArray(act.add_outbound_actions)) {
    const mergedHooks = Array.from(new Set([...getSelectedOutboundActions(), ...act.add_outbound_actions]));
    setSelectedOutboundActions(mergedHooks);
  }
  if (Array.isArray(act.add_event_triggers)) {
    const mergedTriggers = Array.from(new Set([...getSelectedEventTriggers(), ...act.add_event_triggers]));
    setSelectedEventTriggers(mergedTriggers);
  }
  if (act.set_intelligence_mode) {
    const modeEl = document.getElementById('newAgentIntelligenceMode');
    if (modeEl) modeEl.value = act.set_intelligence_mode;
  }

  act._applied = true;
  renderStudioWizardDocPreview();
  updateLiveWizardPreview();
  if (typeof showFleetToast === 'function') {
    showFleetToast(`✓ Applied AI workflow recommendation: ${act.label}`, false);
  }
}

function filterStudioStagedDocsByFile(filename) {
  studioDocFilterFilename = String(filename || '');
  renderStudioWizardDocPreview();
}

function toggleAllStudioStagedDocItems(checked) {
  if (!studioStagedDocExtraction || !Array.isArray(studioStagedDocExtraction.items)) return;
  studioStagedDocExtraction.items.forEach(it => {
    const src = it.source_document || it.extra_fields?.source_document || '';
    if (!studioDocFilterFilename || src === studioDocFilterFilename) {
      it._checked = Boolean(checked);
    }
  });
  renderStudioWizardDocPreview();
  renderStudioGuidedWorkflowRibbon();
}

function toggleStudioStagedDocItem(idx, checked) {
  if (!studioStagedDocExtraction || !Array.isArray(studioStagedDocExtraction.items)) return;
  if (studioStagedDocExtraction.items[idx]) {
    studioStagedDocExtraction.items[idx]._checked = Boolean(checked);
    renderStudioWizardDocPreview();
    renderStudioGuidedWorkflowRibbon();
  }
}

function clearStudioStagedDocExtraction() {
  studioStagedDocExtraction = null;
  studioAttachmentQueue = [];
  studioStagedDocuments = [];
  studioWorkflowGuidance = null;
  studioDocFilterFilename = '';
  studioCurrentWorkflowIr = null;
  studioCurrentRequirementsDoc = null;
  studioCurrentRecordingId = '';
  if (typeof window.StudioActivityRecorder?.resetUi === 'function') {
    window.StudioActivityRecorder.resetUi();
  }

  const docInput = document.getElementById('studioWizardDocInput');
  if (docInput) docInput.value = '';
  const tray = document.getElementById('studioAttachmentQueueTray');
  if (tray) {
    tray.style.display = 'none';
    tray.innerHTML = '';
  }
  const prevBox = document.getElementById('studioWizardDocPreviewBox');
  if (prevBox) {
    prevBox.style.display = 'none';
    prevBox.innerHTML = '';
  }
  const ribbon = document.getElementById('studioGuidedWorkflowRibbon');
  if (ribbon) ribbon.style.display = 'none';
}

const clearStudioStagedDocument = clearStudioStagedDocExtraction;

function renderStudioGuidedWorkflowRibbon() {
  const ribbon = document.getElementById('studioGuidedWorkflowRibbon');
  if (!ribbon) return;
  if (!studioWorkflowGuidance || !studioStagedDocExtraction) {
    ribbon.style.display = 'none';
    return;
  }

  const titleEl = document.getElementById('studioGuidedRibbonTitle');
  const noteEl = document.getElementById('studioGuidedRibbonStepNote');
  const metaEl = document.getElementById('studioGuidedRibbonMeta');

  const items = Array.isArray(studioStagedDocExtraction.items) ? studioStagedDocExtraction.items : [];
  const checkedCount = items.filter(it => it._checked !== false).length;
  const docCount = Math.max(1, studioStagedDocuments.length || Number(studioWorkflowGuidance.attachments_count || 1));
  const stepKey = `step_${currentWizardStep}`;
  const stepNote = studioWorkflowGuidance.step_guidance?.[stepKey] || studioWorkflowGuidance.rationale || '';
  const engineTag = studioStagedDocExtraction.model_used || studioStagedDocExtraction.engine_used || 'Connected LLM';

  if (titleEl) {
    titleEl.textContent = `${studioWorkflowGuidance.headline || 'LLM Document-Guided Workflow'} • ${engineTag}`;
  }
  if (noteEl) {
    noteEl.textContent = stepNote;
  }
  if (metaEl) {
    metaEl.textContent = `${docCount} attachment${docCount > 1 ? 's' : ''} • ${checkedCount} item${checkedCount === 1 ? '' : 's'} staged`;
  }
  ribbon.style.display = 'flex';
}

function renderStudioWizardDocPreview() {
  const prevBox = document.getElementById('studioWizardDocPreviewBox');
  if (!prevBox) return;
  if (!studioStagedDocExtraction) {
    prevBox.style.display = 'none';
    prevBox.innerHTML = '';
    return;
  }

  const ext = studioStagedDocExtraction;
  const scen = ext.scenario_profile || {};
  const guidance = studioWorkflowGuidance || {};
  const items = Array.isArray(ext.items) ? ext.items : [];
  const checkedCount = items.filter(it => it._checked !== false).length;
  const docCount = Math.max(1, studioStagedDocuments.length || Number(ext.attachments_count || 1));

  // Per-attachment filter & summary pills
  let docFilterTabsHtml = '';
  if (studioStagedDocuments.length > 0) {
    const allActive = !studioDocFilterFilename;
    const allBtn = `
      <button type="button" title="Show extracted tracking items across all uploaded attachments" class="btn" onclick="filterStudioStagedDocsByFile('')"
        style="padding:3px 9px; font-size:10.5px; border-radius:999px; background:${allActive ? 'rgba(56,189,248,0.24)' : 'rgba(15,23,42,0.75)'}; border:1px solid ${allActive ? '#38bdf8' : 'rgba(148,163,184,0.28)'}; color:${allActive ? '#e0f2fe' : '#cbd5e1'};">
        📚 All Attachments (${items.length})
      </button>
    `;
    const perFileBtns = studioStagedDocuments.map(doc => {
      const fn = doc.filename || '';
      const isAct = studioDocFilterFilename === fn;
      const countForDoc = items.filter(it => (it.source_document || it.extra_fields?.source_document || '') === fn).length;
      const dIcon = doc.scenario_profile?.icon || '📄';
      const tip = `${doc.scenario_profile?.title || 'Document'}: ${doc.document_summary || fn}`;
      return `
        <button type="button" title="${studioEscapeHtml(tip)}" class="btn" onclick="filterStudioStagedDocsByFile('${studioEscapeHtml(fn).replace(/'/g, "\\'")}')"
          style="padding:3px 9px; font-size:10.5px; border-radius:999px; background:${isAct ? 'rgba(16,185,129,0.22)' : 'rgba(15,23,42,0.75)'}; border:1px solid ${isAct ? '#34d399' : 'rgba(148,163,184,0.25)'}; color:${isAct ? '#6ee7b7' : '#cbd5e1'};">
          ${studioEscapeHtml(dIcon)} ${studioEscapeHtml(fn)} (${countForDoc})
        </button>
      `;
    }).join('');
    docFilterTabsHtml = `<div style="display:flex; gap:5px; flex-wrap:wrap; margin-bottom:8px;">${allBtn}${perFileBtns}</div>`;
  }

  // Urgent findings banner when LLM / date scanner spotted overdue items, <=30d deadlines, or clinical flags
  const urgentList = Array.isArray(guidance.urgent_findings) ? guidance.urgent_findings : [];
  const urgentHtml = urgentList.length > 0 ? `
    <div style="margin-bottom:8px; padding:7px 10px; border-radius:7px; background:rgba(245,158,11,0.12); border:1px solid rgba(251,191,36,0.35); font-size:11px; color:#fde68a;">
      <strong style="color:#fbbf24;">⚡ LLM Document Findings &amp; Automated Actions Taken:</strong>
      <ul style="margin:4px 0 0 16px; padding:0; display:flex; flex-direction:column; gap:2px;">
        ${urgentList.map(u => `<li>${studioEscapeHtml(u)}</li>`).join('')}
      </ul>
    </div>
  ` : '';

  // 1-Click AI Guided Workflow Actions + Step Navigation Pills
  const guidedActions = Array.isArray(guidance.guided_actions) ? guidance.guided_actions : [];
  const guidedChipsHtml = guidedActions.length > 0 ? `
    <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin-bottom:8px;">
      <span style="font-size:10.5px; color:#94a3b8; font-weight:600;">🧭 Guided Workflow Actions:</span>
      ${guidedActions.map((act, idx) => `
        <button type="button" id="studioGuidedActionBtn_${idx}" title="${studioEscapeHtml(act.description || act.label)}" class="btn"
          ${act._applied ? 'disabled' : ''} onclick="applyStudioGuidedAction(${idx})"
          style="padding:3px 9px; font-size:10.5px; border-radius:999px; border:1px solid ${act._applied ? 'rgba(16,185,129,0.45)' : 'rgba(56,189,248,0.38)'}; background:${act._applied ? 'rgba(16,185,129,0.16)' : 'rgba(14,116,144,0.22)'}; color:${act._applied ? '#34d399' : '#bae6fd'};">
          ${act._applied ? '✓ ' : ''}${studioEscapeHtml(act.label)}
        </button>
      `).join('')}
    </div>
  ` : '';

  const stepNavHtml = `
    <div style="display:flex; gap:6px; flex-wrap:wrap; align-items:center; margin-bottom:9px; padding:6px 9px; border-radius:7px; background:rgba(15,23,42,0.65); border:1px solid rgba(56,189,248,0.18);">
      <span style="font-size:10.5px; color:#7dd3fc; font-weight:600;">Walk Guided Steps:</span>
      <button type="button" title="${studioEscapeHtml(guidance.step_guidance?.step_2 || 'Review least-privilege sandbox permissions')}" class="btn" onclick="goToWizardStep(2)" style="padding:2px 8px; font-size:10.5px; color:#cbd5e1; border-color:rgba(148,163,184,0.3);">2. Permissions →</button>
      <button type="button" title="${studioEscapeHtml(guidance.step_guidance?.step_3 || 'Review merged schema fields, recurrence, alert hooks, and UI widgets')}" class="btn" onclick="goToWizardStep(3)" style="padding:2px 8px; font-size:10.5px; color:#cbd5e1; border-color:rgba(148,163,184,0.3);">3. Unified Schema &amp; Hooks →</button>
      <button type="button" title="${studioEscapeHtml(guidance.step_guidance?.step_4 || 'Preview live widgets and run sandbox dry-run before activation')}" class="btn" onclick="goToWizardStep(4)" style="padding:2px 8px; font-size:10.5px; color:#38bdf8; border-color:rgba(56,189,248,0.4);">4. Visual Preview &amp; Dry-Run →</button>
    </div>
  `;

  const visibleIndexedItems = items
    .map((it, idx) => ({ it, idx }))
    .filter(({ it }) => {
      if (!studioDocFilterFilename) return true;
      const src = it.source_document || it.extra_fields?.source_document || '';
      return src === studioDocFilterFilename;
    });

  const rowsHtml = visibleIndexedItems.length === 0
    ? `<div style="font-size: 11.5px; color: #94a3b8; padding: 6px 0;">Blueprint configured from uploaded attachments. You can also drop additional files into the live agent's Document Vault after launch.</div>`
    : visibleIndexedItems.map(({ it, idx }) => {
        const srcDoc = it.source_document || it.extra_fields?.source_document || '';
        const extraPairs = it.extra_fields && typeof it.extra_fields === 'object'
          ? Object.entries(it.extra_fields)
              .filter(([k, v]) => v && k !== 'source_document' && k !== 'doc_record_id')
              .slice(0, 3)
              .map(([k, v]) => `${k}: ${v}`)
              .join(' • ')
          : '';
        const srcBadge = srcDoc && docCount > 1
          ? `<span style="color:#a5b4fc; background:rgba(99,102,241,0.16); padding:1px 6px; border-radius:4px; font-size:10px;">📄 ${studioEscapeHtml(srcDoc)}</span>`
          : '';
        const dueBadge = it.due_date ? `<span style="color:#38bdf8;">📅 ${studioEscapeHtml(it.due_date)}</span>` : '';
        const numBadge = it.numeric_value ? `<span style="color:#34d399; font-family:monospace;">${Number(it.numeric_value).toLocaleString()}</span>` : '';
        return `
          <label style="display:flex; align-items:flex-start; gap:8px; padding:6px 8px; border-radius:6px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.07); cursor:pointer; font-size:11.5px;">
            <input type="checkbox" ${it._checked !== false ? 'checked' : ''} onchange="toggleStudioStagedDocItem(${idx}, this.checked)" style="margin-top:2px;">
            <div style="flex:1; min-width:0;">
              <div style="display:flex; justify-content:space-between; gap:8px; flex-wrap:wrap; align-items:center;">
                <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
                  <strong style="color:#f8fafc;">${studioEscapeHtml(it.title)}</strong>
                  ${srcBadge}
                </div>
                <div style="display:flex; gap:8px; font-size:11px;">${dueBadge}${numBadge}</div>
              </div>
              ${extraPairs ? `<div style="font-size:10.5px; color:#94a3b8; margin-top:2px;">${studioEscapeHtml(extraPairs)}</div>` : ''}
            </div>
          </label>
        `;
      }).join('');

  prevBox.style.display = 'block';
  prevBox.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
      <div style="font-size:12px; color:#e2e8f0;">
        <span>${studioEscapeHtml(scen.icon || '🧭')}</span>
        <strong style="color:#34d399;">${studioEscapeHtml(guidance.headline || scen.title || 'Documents Analyzed')}</strong>
        <span style="color:#94a3b8; font-size:11px;"> • ${docCount} file${docCount > 1 ? 's' : ''} • <code>${studioEscapeHtml(ext.model_used || ext.engine_used || 'LLM')}</code></span>
      </div>
      <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
        <span style="font-size:11px; color:#6ee7b7; font-weight:600;">✓ ${checkedCount}/${items.length} item(s) staged</span>
        ${items.length > 1 ? `<button type="button" title="Select all visible extracted items for SQLite seeding" class="btn" onclick="toggleAllStudioStagedDocItems(true)" style="padding:2px 6px; font-size:10px; color:#7dd3fc;">All</button><button type="button" title="Deselect visible extracted items" class="btn" onclick="toggleAllStudioStagedDocItems(false)" style="padding:2px 6px; font-size:10px; color:#94a3b8;">None</button>` : ''}
        <button type="button" title="Clear staged attachments and workflow guidance" class="btn" onclick="clearStudioStagedDocExtraction()" style="padding:2px 7px; font-size:10.5px; color:#94a3b8;">✕ Clear</button>
      </div>
    </div>
    ${ext.document_summary ? `<div style="font-size:11.5px; color:#e2e8f0; margin-bottom:5px;">${studioEscapeHtml(ext.document_summary)}</div>` : ''}
    ${guidance.rationale ? `<div style="font-size:11px; color:#94a3b8; margin-bottom:8px;">${studioEscapeHtml(guidance.rationale)}</div>` : ''}
    ${urgentHtml}
    ${guidedChipsHtml}
    ${stepNavHtml}
    ${docFilterTabsHtml}
    <div style="display:flex; flex-direction:column; gap:5px; max-height:195px; overflow-y:auto;">${rowsHtml}</div>
  `;
}

async function synthesizeWizardFromPrompt() {
  const input = document.getElementById('wizardNaturalLanguageInput');
  const prompt = (input?.value || '').trim();
  if (!prompt) {
    setStudioGlobalBanner('error', 'Enter a plain-English description or click one of the Starter Blueprints above.');
    showFleetToast('Please enter a plain-English description or click a Starter Blueprint above.', true);
    input?.focus();
    return;
  }

  await runFleetAsyncAction({
    buttons: ['btnSynthesizeAgentPrompt'],
    busyLabel: '⏳ Synthesizing...',
    bannerMessage: '✨ Synthesizing full agent blueprint, typed SQLite fields & schedule...',
    errorPrefix: 'Blueprint synthesis failed',
  }, async () => {
    const { res, data: spec } = await studioFetchJsonWithRetry('/api/studio/synthesize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, id: wizardEditAgentId || undefined }),
    });
    if (!res.ok || spec.status === 'error') {
      throw new Error(spec.message || 'Failed to synthesize agent spec.');
    }
    studioLastSynthesizedSpec = spec;
    populateWizardFromSpec(spec);
    renderStudioSynthesisSummary(spec);

    showFleetToast(`✨ Blueprint ready for '${spec.name}' — click Express Launch or Preview!`, false);
  });
}

async function expressLaunchFromStudio() {
  const name = (document.getElementById('newAgentName')?.value || '').trim();
  if (!name) {
    await synthesizeWizardFromPrompt();
    if (!(document.getElementById('newAgentName')?.value || '').trim()) {
      return;
    }
  }
  await submitCreateAgentWizard({ expressOpen: true });
}

function goToWizardStep(step) {
  if (step < 1 || step > 4) return;

  if (currentWizardStep === 1 && step > 1) {
    const name = (document.getElementById('newAgentName')?.value || '').trim();
    const nlVal = (document.getElementById('wizardNaturalLanguageInput')?.value || '').trim();
    if (!name && nlVal) {
      synthesizeWizardFromPrompt().then(() => {
        if ((document.getElementById('newAgentName')?.value || '').trim()) {
          goToWizardStep(step);
        }
      });
      return;
    }
    if (!name) {
      setStudioGlobalBanner('error', 'Enter an Agent Name or click "✨ Auto-Fill Wizard" / a Starter Blueprint first.');
      showFleetToast('Please enter an Agent Name or click ✨ Auto-Fill Wizard / a Starter Blueprint first.', true);
      document.getElementById('newAgentName')?.focus();
      return;
    }
    const idEl = document.getElementById('newAgentId');
    if (idEl && !(idEl.value || '').trim()) {
      onNewAgentNameInput(name);
    }
  }

  currentWizardStep = step;

  for (let s = 1; s <= 4; s++) {
    const pane = document.getElementById(`wizardStep_${s}`);
    const pill = document.getElementById(`wizardPill_${s}`);
    if (pane) pane.style.display = (s === step) ? 'block' : 'none';
    if (pill) {
      pill.classList.remove('active', 'completed');
      if (s === step) pill.classList.add('active');
      else if (s < step) pill.classList.add('completed');
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
  renderStudioGuidedWorkflowRibbon();
}

function nextWizardStep() {
  goToWizardStep(currentWizardStep + 1);
}

function prevWizardStep() {
  goToWizardStep(currentWizardStep - 1);
}

function switchCodePreviewTab(tabKey) {
  currentPreviewCodeTab = tabKey;
  ['visual', 'py', 'json', 'html'].forEach(t => {
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
  const visualPane = document.getElementById('wizardVisualPreviewPane');
  const codePane = document.getElementById('wizardCodePreview');
  if (visualPane) visualPane.style.display = (tabKey === 'visual') ? 'block' : 'none';
  if (codePane) codePane.style.display = (tabKey === 'visual') ? 'none' : 'block';
  updateLiveWizardPreview();
  renderStudioGuidedWorkflowRibbon();
}

function toPascalCase(str) {
  return String(str || 'custom_agent')
    .split('_')
    .filter(Boolean)
    .map(p => p.charAt(0).toUpperCase() + p.slice(1))
    .join('');
}

function buildCurrentWizardSpecPayload() {
  const name = (document.getElementById('newAgentName')?.value || 'My Custom Agent').trim();
  const rawId = (document.getElementById('newAgentId')?.value || 'my_custom_agent').trim();
  const id = wizardEditAgentId || resolveUniqueAgentId(rawId);
  const icon = (document.getElementById('newAgentIcon')?.value || '⚡').trim();
  const desc = (document.getElementById('newAgentDesc')?.value || 'Custom user agent package.').trim();
  const category = document.getElementById('newAgentCategory')?.value || 'Productivity';
  const perms = getSelectedPermissions();
  const uiBlocks = getSelectedUiBlocks();
  const routineTask = (document.getElementById('newAgentTaskName')?.value || 'run_check').trim();
  const scheduleCadence = document.getElementById('newAgentSchedule')?.value || 'daily_morning';
  const intelligenceMode = document.getElementById('newAgentIntelligenceMode')?.value || 'hybrid';
  const model = (document.getElementById('newAgentModel')?.value || 'gemini-3.8-flash-low').trim();
  const archetype = document.getElementById('newAgentArchetype')?.value || 'tracker';
  const syncInterval = parseInt(document.getElementById('settingSyncInterval')?.value || '85', 10);
  const enableAlerts = document.getElementById('settingEnableAlerts')?.value === 'true';
  const systemPrompt = (document.getElementById('newAgentSystemPrompt')?.value || '').trim();

  let scheduleObj = { ...studioCurrentSchedule };
  if (scheduleCadence === 'every_30_min') {
    scheduleObj = { type: 'cron', value: '*/30 * * * *', display: 'Every 30m' };
  } else if (scheduleCadence === 'hourly') {
    scheduleObj = { type: 'interval_hours', value: 1, display: 'Every 1h' };
  } else if (scheduleCadence === 'manual_only') {
    scheduleObj = { type: 'manual', value: 'manual', display: 'Manual Only' };
  } else if (!scheduleObj.display || scheduleObj.type === 'cron' || scheduleObj.type === 'interval_hours') {
    scheduleObj = { type: 'time', value: '09:00', time: '09:00', display: 'Daily at 09:00' };
  }

  const evoImps = wizardEditAgentId ? getSelectedEvolutionImprovementsMetadata() : [];

  return {
    id,
    agent_id: id,
    name,
    icon,
    description: desc,
    category,
    archetype,
    intelligence_mode: intelligenceMode,
    model,
    permissions: perms,
    ui_blocks: uiBlocks,
    fields: studioCurrentFields,
    checklist_items: studioCurrentChecklist,
    event_triggers: getSelectedEventTriggers(),
    outbound_actions: getSelectedOutboundActions(),
    auto_ingest_inbox: Boolean(document.getElementById('newAgentAutoIngestInbox')?.checked),
    default_recurrence: document.getElementById('newAgentDefaultRecurrence')?.value || 'none',
    evolution_improvements: evoImps.length > 0 ? evoImps : undefined,
    routine_task: routineTask,
    schedule_cadence: scheduleCadence,
    schedule: scheduleObj,
    system_prompt: systemPrompt || undefined,
    workflow_ir: studioCurrentWorkflowIr || undefined,
    requirements_doc: studioCurrentRequirementsDoc || undefined,
    recording_id: studioCurrentRecordingId || undefined,
    settings: {
      target_threshold: syncInterval,
      enabled_notifications: enableAlerts,
    },
  };
}

function renderVisualPreviewMockup(spec) {
  const blocks = spec.ui_blocks || [];
  const parts = [];

  if (blocks.includes('alert_banner')) {
    const trigNote = Array.isArray(spec.event_triggers) && spec.event_triggers.length > 0
      ? ` • ⚡ ${spec.event_triggers.length} trigger(s)`
      : '';
    parts.push(`
      <div style="display:flex; justify-content:space-between; align-items:center; padding:9px 12px; border-radius:8px; background:rgba(16,185,129,0.12); border:1px solid rgba(16,185,129,0.3); font-size:11.5px;">
        <div>🟢 <strong style="color:#10b981;">${studioEscapeHtml(spec.name)} Active</strong> <span style="color:#94a3b8;">• ${studioEscapeHtml(spec.schedule.display)} • <code>${studioEscapeHtml(spec.routine_task)}</code>${trigNote}</span></div>
        <span style="padding:2px 8px; border-radius:999px; background:rgba(15,23,42,0.7); color:#38bdf8; font-size:10.5px;">${spec.intelligence_mode === 'llm' ? '🧠 Antigravity LLM' : '⚡ $0.00 + On-Demand AI'}</span>
      </div>
    `);
  }
  if (blocks.includes('kpi_row')) {
    parts.push(`
      <div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:8px;">
        <div style="padding:9px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px; color:#94a3b8;">STATUS</div><div style="font-size:14px; font-weight:700; color:#10b981;">Ready</div></div>
        <div style="padding:9px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px; color:#94a3b8;">TRACKED</div><div style="font-size:14px; font-weight:700; color:#f8fafc;">SQLite</div></div>
        <div style="padding:9px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px; color:#94a3b8;">DUE SOON</div><div style="font-size:14px; font-weight:700; color:#38bdf8;">0</div></div>
        <div style="padding:9px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.08);"><div style="font-size:10px; color:#94a3b8;">CADENCE</div><div style="font-size:12.5px; font-weight:700; color:#38bdf8;">${studioEscapeHtml(spec.schedule.display)}</div></div>
      </div>
    `);
  }
  if (blocks.includes('document_vault')) {
    parts.push(`
      <div style="padding:10px 12px; border-radius:8px; background:linear-gradient(135deg, rgba(14,116,144,0.18), rgba(15,23,42,0.75)); border:1px dashed rgba(56,189,248,0.4); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div>
          <div style="font-size:11.5px; color:#e0f2fe; font-weight:700;">📄 Document Upload &amp; AI Tracking Extractor</div>
          <div style="font-size:10px; color:#94a3b8;">Drop PDF, DOCX, XLSX, CSV, EML, ICS, or Image scans → LLM extracts structured items into SQLite</div>
        </div>
        <span style="padding:4px 10px; border-radius:6px; background:rgba(56,189,248,0.2); color:#38bdf8; font-size:10.5px; font-weight:700;">🧠 Extract Items</span>
      </div>
    `);
  }
  if (blocks.includes('quick_capture_bar')) {
    const fInputs = (spec.fields || []).map(f => `
      <div style="flex:1; min-width:110px;">
        <div style="font-size:9.5px; color:#94a3b8; font-weight:600; margin-bottom:2px;">${studioEscapeHtml(f.label)} (${studioEscapeHtml(f.type)})</div>
        <div style="padding:5px 8px; border-radius:6px; background:rgba(0,0,0,0.4); border:1px solid rgba(255,255,255,0.12); color:#64748b; font-size:11px;">${studioEscapeHtml(f.placeholder || f.label)}</div>
      </div>
    `).join('');
    parts.push(`
      <div style="padding:10px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(255,255,255,0.08); display:flex; flex-wrap:wrap; gap:8px; align-items:flex-end;">
        ${fInputs}
        <span style="padding:5px 10px; border-radius:6px; background:rgba(56,189,248,0.15); color:#38bdf8; font-size:11px; font-weight:600;">➕ Save Entry</span>
        <span style="padding:5px 10px; border-radius:6px; background:rgba(16,185,129,0.2); color:#34d399; font-size:11px; font-weight:600;">▶ Run ${studioEscapeHtml(spec.routine_task)}</span>
      </div>
    `);
  }
  if (blocks.includes('kanban_board')) {
    parts.push(`
      <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; font-size:10.5px;">
        <div style="padding:7px 9px; border-radius:7px; background:rgba(15,23,42,0.75); border:1px solid rgba(56,189,248,0.25); color:#38bdf8; font-weight:600;">📋 Active / Safe</div>
        <div style="padding:7px 9px; border-radius:7px; background:rgba(15,23,42,0.75); border:1px solid rgba(251,191,36,0.3); color:#fbbf24; font-weight:600;">⏳ Due Soon / Attention</div>
        <div style="padding:7px 9px; border-radius:7px; background:rgba(15,23,42,0.75); border:1px solid rgba(16,185,129,0.3); color:#34d399; font-weight:600;">✅ Completed</div>
      </div>
    `);
  }
  if (blocks.includes('sparkline_chart')) {
    parts.push(`
      <div style="padding:9px 12px; border-radius:8px; background:rgba(15,23,42,0.75); border:1px solid rgba(56,189,248,0.2); display:flex; justify-content:space-between; align-items:center; gap:12px;">
        <div style="font-size:11px; color:#e2e8f0; font-weight:600;">📈 Live SVG Metric &amp; Latency Sparkline</div>
        <svg viewBox="0 0 120 26" style="width:120px; height:24px;"><polyline fill="none" stroke="#38bdf8" stroke-width="2" points="4,20 28,14 52,17 76,8 100,11 116,4"/></svg>
      </div>
    `);
  }
  const extraPills = [];
  if (blocks.includes('countdown_cards')) extraPills.push('⏳ Live 15-Day Renewal Countdown Cards');
  if (blocks.includes('ai_insight_card')) extraPills.push(`🧠 Antigravity AI Briefing (${studioEscapeHtml(spec.model)})`);
  if (blocks.includes('agent_chat')) extraPills.push('💬 Grounded Agent Q&amp;A &amp; Command Chat');
  if (blocks.includes('habit_checklist')) extraPills.push('✅ Persistent Daily Streak Checklist');
  if (blocks.includes('history_table')) extraPills.push('📋 SQLite Records & Run History Table');
  if (blocks.includes('status_timeline')) extraPills.push('⏱️ Autonomic Event Timeline');
  if (spec.auto_ingest_inbox) extraPills.push(`📥 Watched Drop-Folder (fleet/data/user/inbox/${studioEscapeHtml(spec.id)}/)`);
  if (Array.isArray(spec.outbound_actions) && spec.outbound_actions.length > 0) {
    extraPills.push(`🔄 Hooks: ${spec.outbound_actions.map(studioEscapeHtml).join(', ')}`);
  }
  if (Array.isArray(spec.event_triggers) && spec.event_triggers.length > 0) {
    extraPills.push(`⚡ EventBus: ${spec.event_triggers.map(studioEscapeHtml).join(', ')}`);
  }
  if (Array.isArray(spec.evolution_improvements) && spec.evolution_improvements.length > 0) {
    extraPills.push(`✨ ${spec.evolution_improvements.length} Evolution Improvement(s) Applied`);
  }

  if (extraPills.length > 0) {
    parts.push(`
      <div style="display:flex; flex-wrap:wrap; gap:6px;">
        ${extraPills.map(p => `<span style="padding:5px 10px; border-radius:6px; background:rgba(30,41,59,0.8); border:1px solid rgba(255,255,255,0.08); font-size:11px; color:#cbd5e1;">${p}</span>`).join('')}
      </div>
    `);
  }
  return `<div style="display:flex; flex-direction:column; gap:8px;">${parts.join('')}</div>`;
}

function updateLiveWizardPreview() {
  const spec = buildCurrentWizardSpecPayload();

  const sumIcon = document.getElementById('previewSummaryIcon');
  const sumName = document.getElementById('previewSummaryName');
  const sumId = document.getElementById('previewSummaryId');
  const sumPerms = document.getElementById('previewSummaryPerms');

  if (sumIcon) sumIcon.textContent = spec.icon;
  if (sumName) sumName.textContent = spec.name;
  if (sumId) {
    const trigTxt = spec.event_triggers.length > 0 ? ` | ⚡ ${spec.event_triggers.length} trigger(s)` : '';
    sumId.textContent = `id: ${spec.id} | ${spec.archetype} | ${spec.intelligence_mode} | ${spec.fields.length} fields | ${spec.ui_blocks.length} widgets${trigTxt}`;
  }
  if (sumPerms) {
    sumPerms.innerHTML = spec.permissions.map(p =>
      `<span class="badge" style="background: rgba(56,189,248,0.12); color: var(--accent-cyan); font-size: 11px; padding: 2px 7px;">${studioEscapeHtml(p)}</span>`
    ).join('');
  }

  const visualPane = document.getElementById('wizardVisualPreviewPane');
  if (visualPane && currentPreviewCodeTab === 'visual') {
    visualPane.innerHTML = renderVisualPreviewMockup(spec);
  }

  const pre = document.getElementById('wizardCodePreview');
  if (!pre || currentPreviewCodeTab === 'visual') return;

  const pascalName = toPascalCase(spec.id) + 'Agent';

  if (currentPreviewCodeTab === 'py') {
    pre.textContent = `"""
${spec.name} (${spec.id}) — Synthesized by Fleet Zero-Code Agent Studio.
Goal: ${spec.description}
"""

from typing import Any, Dict, List, Optional
from fleet.core.base_agent import FleetAgent
from fleet.core.agent_studio import execute_studio_agent_runtime


class ${pascalName}(FleetAgent):
    archetype = "${spec.archetype}"
    intelligence_mode = "${spec.intelligence_mode}"
    routine_task = "${spec.routine_task}"

    @property
    def id(self) -> str:
        return "${spec.id}"

    @property
    def name(self) -> str:
        return "${spec.name}"

    @property
    def icon(self) -> str:
        return "${spec.icon}"

    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        active_task = task or self.routine_task
        return execute_studio_agent_runtime(self, task=active_task, payload=payload)
`;
  } else if (currentPreviewCodeTab === 'json') {
    pre.textContent = JSON.stringify({
      id: spec.id,
      name: spec.name,
      version: '2.0.0',
      icon: spec.icon,
      category: spec.category,
      archetype: spec.archetype,
      intelligence_mode: spec.intelligence_mode,
      model: spec.model,
      description: spec.description,
      permissions: spec.permissions,
      ui_blocks: spec.ui_blocks,
      fields: spec.fields,
      event_triggers: spec.event_triggers,
      outbound_actions: spec.outbound_actions,
      auto_ingest_inbox: spec.auto_ingest_inbox,
      default_recurrence: spec.default_recurrence,
      evolution_improvements: spec.evolution_improvements,
      routine_task: spec.routine_task,
      schedule_cadence: spec.schedule_cadence,
      schedule: spec.schedule,
    }, null, 2);
  } else if (currentPreviewCodeTab === 'html') {
    pre.textContent = `<div class="panel-section" id="studio_panel_${spec.id}" data-studio-agent="${spec.id}">
  <!-- Live SQLite Declarative Blocks: ${spec.ui_blocks.join(', ')} -->
  <!-- Typed Quick-Capture Fields: ${spec.fields.map(f => `${f.key}:${f.type}`).join(', ')} -->
  <!-- Automatically hydrated on mount by CustomAgentRuntime.mount('${spec.id}') -->
</div>`;
  }
}

async function runWizardDryRun() {
  const out = document.getElementById('wizardDryRunOutput');
  const sampleInput = (document.getElementById('wizardDryRunSampleInput')?.value || '').trim();
  const spec = buildCurrentWizardSpecPayload();

  if (out) {
    out.style.display = 'block';
    out.style.background = 'rgba(15, 23, 42, 0.8)';
    out.style.border = '1px solid rgba(56, 189, 248, 0.25)';
    out.style.color = '#94a3b8';
    out.textContent = '⏳ Auditing AST, permissions, and simulating sandbox execution...';
  }

  await runFleetAsyncAction({
    buttons: ['btnWizardDryRun'],
    busyLabel: '⏳ Running Dry-Run...',
    bannerMessage: `🧪 Auditing Python AST, least-privilege permissions & simulating '${spec.routine_task}'...`,
    errorPrefix: 'Sandbox dry-run failed',
    onError: (err) => {
      if (out) {
        out.style.display = 'block';
        out.style.background = 'rgba(239, 68, 68, 0.14)';
        out.style.border = '1px solid rgba(239, 68, 68, 0.35)';
        out.style.color = '#fca5a5';
        out.textContent = '✕ Dry-run failed: ' + err.message;
      }
    },
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry('/api/studio/dry_run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ spec, sample_input: sampleInput }),
    });
    if (!res.ok || data.status !== 'ok') {
      throw new Error(data.message || 'Dry-run validation failed.');
    }
    if (out) {
      out.style.display = 'block';
      out.style.background = 'rgba(16, 185, 129, 0.12)';
      out.style.border = '1px solid rgba(16, 185, 129, 0.35)';
      out.style.color = '#6ee7b7';
      out.innerHTML = (data.checks || []).map(c => `<div>✓ ${studioEscapeHtml(c)}</div>`).join('') +
        `<div style="color:#94a3b8; margin-top:4px;">Completed in ${data.duration_ms}ms (0 production DB writes)</div>`;
    }
    showFleetToast(`✅ Sandbox dry-run passed in ${data.duration_ms}ms (0 DB writes)!`, false);
  });
}

function attachStagedStudioDocumentsToPayload(targetObj, isEvolve) {
  if (isEvolve || (!studioStagedDocExtraction && studioStagedDocuments.length === 0)) {
    return targetObj;
  }
  const checkedItems = ((studioStagedDocExtraction && studioStagedDocExtraction.items) || [])
    .filter(it => it._checked !== false)
    .map(({ _checked, ...cleanItem }) => cleanItem);

  const perDocCheckedCounts = {};
  checkedItems.forEach(it => {
    const src = it.source_document || it.extra_fields?.source_document || '';
    if (src) perDocCheckedCounts[src] = (perDocCheckedCounts[src] || 0) + 1;
  });

  if (studioStagedDocuments.length > 0) {
    targetObj.initial_documents = studioStagedDocuments.map(doc => ({
      filename: doc.filename || 'uploaded_document',
      detected_scenario: doc.detected_scenario || '',
      scenario_title: doc.scenario_profile?.title || '',
      scenario_icon: doc.scenario_profile?.icon || '📄',
      document_summary: doc.document_summary || '',
      engine_used: doc.engine_used || studioStagedDocExtraction?.engine_used || '',
      model_used: doc.model_used || studioStagedDocExtraction?.model_used || '',
      items_count: perDocCheckedCounts[doc.filename] ?? Number(doc.items_count || 0),
      vault_rel_path: doc.vault?.vault_rel_path || '',
      sha256: doc.vault?.sha256 || '',
    }));
  }

  if (studioStagedDocExtraction) {
    targetObj.initial_document = {
      filename: (studioStagedDocuments[0]?.filename) || studioStagedDocExtraction.filename || 'uploaded_document',
      detected_scenario: studioStagedDocExtraction.detected_scenario || '',
      scenario_title: studioStagedDocExtraction.scenario_profile?.title || '',
      document_summary: studioStagedDocExtraction.document_summary || '',
      engine_used: studioStagedDocExtraction.engine_used || '',
      model_used: studioStagedDocExtraction.model_used || '',
      items_count: checkedItems.length,
      vault_rel_path: studioStagedDocExtraction.vault?.vault_rel_path || '',
      sha256: studioStagedDocExtraction.vault?.sha256 || '',
    };
  }
  targetObj.initial_records = checkedItems;
  return targetObj;
}

async function studioFetchJsonWithRetry(url, options = {}, retries = 2) {
  let lastErr = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(url, options);
      const rawText = await res.text();
      let data = {};
      if (rawText) {
        try {
          data = JSON.parse(rawText);
        } catch (_parseErr) {
          throw new Error(`Invalid JSON response from ${url} (HTTP ${res.status}).`);
        }
      }
      return { res, data };
    } catch (err) {
      lastErr = err;
      const msg = String(err && err.message ? err.message : err || '');
      const isNetworkGlitch = (
        err instanceof TypeError ||
        /failed to fetch|networkerror|load failed|connection reset|econnreset/i.test(msg)
      );
      if (isNetworkGlitch && attempt < retries) {
        await new Promise(resolve => setTimeout(resolve, 650 * (attempt + 1)));
        continue;
      }
      if (isNetworkGlitch) {
        const origin = (typeof window !== 'undefined' && window.location && window.location.origin)
          ? window.location.origin
          : 'http://127.0.0.1:7890';
        throw new Error(`Cannot reach AFCC server at ${origin} (${msg || 'network connection interrupted'}). Ensure Fleet is running and click retry.`);
      }
      throw err;
    }
  }
  throw lastErr || new Error('Request failed.');
}

async function deepBuildWithAntigravity() {
  if (wizardEditAgentId) {
    const pendingCustom = (document.getElementById('studioCustomImprovementInput')?.value || '').trim();
    if (pendingCustom) {
      await addCustomEvolveImprovement();
    }
  }
  const spec = buildCurrentWizardSpecPayload();
  const out = document.getElementById('wizardDryRunOutput');
  const isEvolve = Boolean(wizardEditAgentId);

  if (!spec.name || !spec.id) {
    setStudioGlobalBanner('error', 'Agent Name and ID are required before running Deep-Build.');
    showFleetToast('✕ Deep-Build requires an Agent Name and ID.', true);
    document.getElementById('newAgentName')?.focus();
    return;
  }

  if (out) {
    out.style.display = 'none';
  }

  await runFleetAsyncAction({
    buttons: ['btnWizardDeepBuild', 'btnApplyEvolveDeepBuild'],
    busyLabel: '⏳ Dispatching Deep-Build...',
    bannerMessage: isEvolve
      ? `🤖 Applying selected improvements & dispatching Deep-Build brief for '${spec.name}' to Antigravity Live...`
      : `🤖 Scaffolding '${spec.name}' & dispatching bespoke Deep-Build brief to Antigravity Live...`,
    startToast: `⏳ Scaffolding '${spec.name}' & dispatching Deep-Build to Antigravity Live...`,
    errorPrefix: 'Deep-Build failed',
    onError: (err) => {
      if (out) {
        out.style.display = 'block';
        out.style.background = 'rgba(239, 68, 68, 0.14)';
        out.style.border = '1px solid rgba(239, 68, 68, 0.35)';
        out.style.color = '#fca5a5';
        out.textContent = '✕ Deep-Build error: ' + err.message;
      }
    },
  }, async () => {
    const deepPayload = attachStagedStudioDocumentsToPayload({
      spec,
      scaffold_first: true,
      is_evolve: isEvolve,
      model: spec.model,
    }, isEvolve);
    const { res, data } = await studioFetchJsonWithRetry('/api/studio/deep_build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(deepPayload),
    });

    const dispatchStatus = String(data.dispatch_status || data.dispatch?.status || '').toLowerCase();
    if (!res.ok || data.status === 'error' || ['error', 'failed', 'blocked', 'busy'].includes(dispatchStatus)) {
      throw new Error(data.message || data.dispatch?.message || 'Failed to dispatch Deep-Build.');
    }

    newlyCreatedAgentId = data.agent_id || spec.id;
    clearStudioStagedDocExtraction();

    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();

    closeCreateAgentModal();

    if (typeof window !== 'undefined' && window.isAgRightDocked && newlyCreatedAgentId && nav && typeof nav.switchAgent === 'function') {
      nav.switchAgent(newlyCreatedAgentId);
      if (typeof setAgChatEngineMode === 'function') setAgChatEngineMode('antigravity_live');
    } else if (nav && typeof nav.switchAgent === 'function') {
      nav.switchAgent('antigravity');
      if (typeof setAgChatEngineMode === 'function') setAgChatEngineMode('antigravity_live');
    } else if (typeof switchTab === 'function') {
      switchTab('antigravity');
      if (typeof setAgChatEngineMode === 'function') setAgChatEngineMode('antigravity_live');
    }

    if (typeof fetchTranscript === 'function') {
      fetchTranscript(true);
    }
    if (typeof fetchAgentQueue === 'function') {
      fetchAgentQueue();
    }

    if (dispatchStatus === 'vaulted' || data.dispatch?.type === 'token_exhausted') {
      showFleetToast(`⚠️ ${data.message || `Scaffolded '${spec.name}' — Deep-Build prompt vaulted due to token quota.`}`, false, { variant: 'warning' });
    } else {
      showFleetToast(`🤖 ${data.message || `Scaffolded '${spec.name}' & launched Deep-Build in Antigravity Live!`}`, false);
    }
  });
}

async function cloneCustomAgentFromUI(agentId) {
  if (!agentId) return;
  await runFleetAsyncAction({
    buttons: ['btnStageCloneAgent'],
    busyLabel: '⏳ Cloning...',
    useStudioBanner: false,
    startToast: `⏳ Cloning '${agentId}' blueprint...`,
    errorPrefix: 'Clone failed',
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry('/api/settings/agents/clone', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_id: agentId }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Clone failed.');
    }
    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();

    showFleetToast(`📋 Cloned into '${data.manifest?.name || data.agent_id}' (0 private records copied)!`, false);
    const settingsModal = document.getElementById('fleetSettingsModal') || document.getElementById('settingsModal');
    const settingsOpen = settingsModal && settingsModal.style.display && settingsModal.style.display !== 'none';
    if (!settingsOpen && nav && typeof nav.switchAgent === 'function') {
      nav.switchAgent(data.agent_id);
    }
  });
}

function downloadJsonFile(filename, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 150);
}

async function exportAgentPackFromUI(agentId) {
  if (!agentId) return;
  await runFleetAsyncAction({
    buttons: ['btnStageExportAgent', 'btnWizardExportBlueprint'],
    busyLabel: '⏳ Exporting...',
    errorPrefix: 'Export failed',
  }, async () => {
    const { res, data } = await studioFetchJsonWithRetry(`/api/agents/export?id=${encodeURIComponent(agentId)}`);
    if (!res.ok || data.status !== 'ok' || !data.pack) {
      throw new Error(data.message || 'Could not export agent pack.');
    }
    downloadJsonFile(`${data.pack.agent_id}.fleetagent.json`, data.pack);
    showFleetToast(`📤 Exported '${data.pack.agent_id}.fleetagent.json' (SHA-256 verified)!`, false);
  });
}

async function exportCurrentWizardSpecOrAgent() {
  const spec = buildCurrentWizardSpecPayload();
  const existing = getExistingFleetAgentsMap();
  if (wizardEditAgentId && existing.has(wizardEditAgentId)) {
    await exportAgentPackFromUI(wizardEditAgentId);
    return;
  }
  if (newlyCreatedAgentId && existing.has(newlyCreatedAgentId)) {
    await exportAgentPackFromUI(newlyCreatedAgentId);
    return;
  }
  if (existing.has(spec.id)) {
    await exportAgentPackFromUI(spec.id);
    return;
  }
  const pascalName = toPascalCase(spec.id) + 'Agent';
  const draftPack = {
    format: 'fleetagent-v1',
    agent_id: spec.id,
    manifest: {
      id: spec.id,
      name: spec.name,
      version: '2.0.0',
      icon: spec.icon,
      category: spec.category,
      archetype: spec.archetype,
      intelligence_mode: spec.intelligence_mode,
      model: spec.model,
      description: spec.description,
      permissions: spec.permissions,
      ui_blocks: spec.ui_blocks,
      fields: spec.fields,
      checklist_items: spec.checklist_items,
      event_triggers: spec.event_triggers,
      outbound_actions: spec.outbound_actions,
      auto_ingest_inbox: spec.auto_ingest_inbox,
      default_recurrence: spec.default_recurrence,
      evolution_improvements: spec.evolution_improvements,
      routine_task: spec.routine_task,
      schedule_cadence: spec.schedule_cadence,
      schedule: spec.schedule,
    },
    agent_code: `from typing import Any, Dict, Optional\nfrom fleet.core.base_agent import FleetAgent\nfrom fleet.core.agent_studio import execute_studio_agent_runtime\n\nclass ${pascalName}(FleetAgent):\n    archetype = "${spec.archetype}"\n    intelligence_mode = "${spec.intelligence_mode}"\n    routine_task = "${spec.routine_task}"\n\n    @property\n    def id(self) -> str:\n        return "${spec.id}"\n\n    @property\n    def name(self) -> str:\n        return "${spec.name}"\n\n    @property\n    def icon(self) -> str:\n        return "${spec.icon}"\n\n    def execute_task(self, task: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:\n        return execute_studio_agent_runtime(self, task=task or self.routine_task, payload=payload)\n`,
    panel_html: `<div class="panel-section" id="studio_panel_${spec.id}" data-studio-agent="${spec.id}"></div>`,
  };
  downloadJsonFile(`${spec.id}.fleetagent.json`, draftPack);
  if (typeof showFleetToast === 'function') {
    showFleetToast(`📤 Exported draft '${spec.id}.fleetagent.json'!`, false);
  }
}

function triggerImportAgentPackFile() {
  const inp = document.getElementById('importFleetAgentFileInput');
  if (inp) {
    inp.value = '';
    inp.click();
  }
}

async function handleImportAgentPackFile(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  await runFleetAsyncAction({
    busyLabel: '⏳ Importing...',
    bannerMessage: `📥 Auditing SHA-256 signature & importing '${file.name}' into your Fleet...`,
    startToast: `⏳ Auditing & importing '${file.name}'...`,
    errorPrefix: 'Import failed',
  }, async () => {
    const rawText = await file.text();
    const parsed = JSON.parse(rawText);
    const pack = parsed.pack && typeof parsed.pack === 'object' ? parsed.pack : parsed;
    const { res, data } = await studioFetchJsonWithRetry('/api/agents/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pack }),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Import validation failed.');
    }
    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
    if (typeof fetchSchedules === 'function') fetchSchedules();
    if (typeof loadSettingsData === 'function') loadSettingsData();

    closeCreateAgentModal();
    showFleetToast(`📥 Audited & imported '${data.name || data.agent_id}' into your Fleet!`, false);
    const settingsModal = document.getElementById('fleetSettingsModal') || document.getElementById('settingsModal');
    const settingsOpen = settingsModal && settingsModal.style.display && settingsModal.style.display !== 'none';
    if (!settingsOpen && nav && typeof nav.switchAgent === 'function') {
      nav.switchAgent(data.agent_id);
    }
  });
}

function copyWizardSkillPrompt() {
  const spec = buildCurrentWizardSpecPayload();
  const promptText = `Please extend my custom Personal Agentic Fleet agent '${spec.name}' (id: '${spec.id}'):
- Archetype: ${spec.archetype} (${spec.intelligence_mode} mode, model: ${spec.model})
- Permissions: [${spec.permissions.join(', ')}]
- Typed Fields: ${spec.fields.map(f => `${f.label} (${f.key}:${f.type})`).join(', ')}
- EventBus Triggers: [${(spec.event_triggers || []).join(', ') || 'none'}]
- Goal: ${spec.description}`;

  navigator.clipboard.writeText(promptText).then(() => {
    showFleetToast('📋 Agent Studio specification copied to clipboard!', false);
  }).catch(() => {
    showFleetToast('✕ Clipboard copy unavailable in this browser context.', true);
  });
}

async function submitCreateAgentWizard(opts = {}) {
  if (wizardEditAgentId) {
    const pendingCustom = (document.getElementById('studioCustomImprovementInput')?.value || '').trim();
    if (pendingCustom) {
      await addCustomEvolveImprovement();
    }
  }
  const spec = buildCurrentWizardSpecPayload();
  const notice = document.getElementById('wizardStatusNotice');
  const submitBtn = document.getElementById('btnWizardSubmit');
  const isEvolve = Boolean(wizardEditAgentId);

  if (!spec.name || !spec.id) {
    const reqMsg = 'Agent Name and ID are required before launching.';
    setStudioGlobalBanner('error', reqMsg);
    showFleetToast(`✕ ${reqMsg}`, true);
    if (notice) {
      notice.style.display = 'block';
      notice.style.background = 'rgba(239, 68, 68, 0.15)';
      notice.style.color = '#fca5a5';
      notice.style.border = '1px solid rgba(239, 68, 68, 0.3)';
      notice.textContent = reqMsg;
    }
    document.getElementById('newAgentName')?.focus();
    return;
  }

  if (notice) notice.style.display = 'none';

  await runFleetAsyncAction({
    buttons: ['btnWizardSubmit', 'btnStudioExpressLaunch', 'btnQuickApplyEvolveReload', 'btnGuidedRibbonLaunch'],
    busyLabel: isEvolve ? '⏳ Hot-Reloading Agent...' : '⏳ Scaffolding & Launching...',
    bannerMessage: isEvolve
      ? `✨ Applying selected improvements & hot-reloading '${spec.name}' (preserving 100% of SQLite records)...`
      : `🚀 Scaffolding, scheduling & activating '${spec.name}'...`,
    startToast: isEvolve
      ? `⏳ Applying improvements & hot-reloading '${spec.name}'...`
      : `⏳ Scaffolding & activating '${spec.name}'...`,
    errorPrefix: isEvolve ? 'Agent hot-reload failed' : 'Agent creation failed',
    onError: (err) => {
      if (notice) {
        notice.style.display = 'block';
        notice.style.background = 'rgba(239, 68, 68, 0.15)';
        notice.style.color = '#fca5a5';
        notice.style.border = '1px solid rgba(239, 68, 68, 0.3)';
        notice.textContent = '✕ Error saving agent: ' + err.message;
      }
    },
    onFinally: () => {
      if (submitBtn) {
        submitBtn.textContent = isEvolve ? '✨ Save & Hot-Reload Agent' : '🚀 Scaffold & Activate Agent';
      }
    },
  }, async () => {
    const endpoint = isEvolve ? '/api/settings/agents/evolve' : '/api/settings/agents/create';
    const runImmediateEl = document.getElementById('wizardRunImmediately');
    const payload = attachStagedStudioDocumentsToPayload({
      ...spec,
      run_immediately: !isEvolve && (runImmediateEl ? runImmediateEl.checked : true),
    }, isEvolve);

    const { res, data } = await studioFetchJsonWithRetry(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || 'Server error saving agent.');
    }

    newlyCreatedAgentId = data.agent_id || spec.id;
    const seededCount = Number(data.seeded_records_count || 0);
    const seededDocsCount = Number(data.seeded_documents_count || 0);
    if (!isEvolve) {
      clearStudioStagedDocExtraction();
    }

    const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
    if (nav && typeof nav.fetchFleetData === 'function') {
      await nav.fetchFleetData();
    } else if (typeof fetchAgents === 'function') {
      await fetchAgents();
    }
    if (typeof fetchSchedules === 'function') {
      fetchSchedules();
    }
    if (typeof loadSettingsData === 'function') {
      loadSettingsData();
    }

    const undertakenCount = Number(
      data.undertaken_summary?.undertaken_count ||
      (Array.isArray(spec.evolution_improvements) ? spec.evolution_improvements.length : 0)
    );
    const seedParts = [];
    if (seededDocsCount > 0) seedParts.push(`${seededDocsCount} attachment(s) vaulted`);
    if (seededCount > 0) seedParts.push(`${seededCount} item(s) tracked`);
    const seedNote = seedParts.length > 0 ? ` (${seedParts.join(', ')})` : '';
    showFleetToast(
      isEvolve
        ? `✨ '${spec.name}' undertook ${undertakenCount || 'selected'} self-improvement(s) & hot-reloaded!`
        : `🎉 '${spec.name}' created, scheduled & activated${seedNote}!`,
      false
    );

    if (nav && typeof nav.renderActiveAgentSelfImprovementsBanner === 'function') {
      if (isEvolve && nav._selfImproveMonitorOpen) {
        nav._selfImproveMonitorOpen[newlyCreatedAgentId] = true;
      }
      nav.renderActiveAgentSelfImprovementsBanner(newlyCreatedAgentId);
    }
    if (typeof window.fetchFeatureBacklog === 'function') {
      try { window.fetchFeatureBacklog(); } catch (_) {}
    }

    if (opts.expressOpen || isEvolve) {
      openNewlyCreatedAgent();
      return;
    }

    const footer = document.getElementById('wizardFooterBar');
    if (footer) footer.style.display = 'none';

    const successTitle = document.getElementById('wizardSuccessTitle');
    const successBox = document.getElementById('wizardSuccessBox');
    const successMsg = document.getElementById('wizardSuccessMsg');
    if (successTitle) {
      successTitle.textContent = isEvolve
        ? 'Agent Evolved & Hot-Reloaded!'
        : 'Agent Created, Scheduled & Activated!';
    }
    if (successMsg) {
      const vaultHtml = seededDocsCount > 0
        ? ` Vaulted <strong>${seededDocsCount}</strong> attachment(s) for grounded RAG Q&amp;A.`
        : '';
      const seedHtml = seededCount > 0
        ? ` Pre-seeded <strong>${seededCount}</strong> extracted tracking item(s) into SQLite.`
        : '';
      successMsg.innerHTML = `<strong>${studioEscapeHtml(spec.icon)} ${studioEscapeHtml(spec.name)}</strong> (<code>${studioEscapeHtml(newlyCreatedAgentId)}</code>) is live with ${spec.fields.length} typed fields, ${spec.ui_blocks.length} SQLite widgets, and schedule <strong>${studioEscapeHtml(spec.schedule.display)}</strong>.${vaultHtml}${seedHtml}`;
    }
    if (successBox) successBox.style.display = 'block';
  });
}

function openNewlyCreatedAgent() {
  closeCreateAgentModal();
  if (!newlyCreatedAgentId) return;
  const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
  if (nav && typeof nav.switchAgent === 'function') {
    nav.switchAgent(newlyCreatedAgentId);
  } else if (typeof switchView === 'function') {
    switchView(newlyCreatedAgentId);
  }
}

const _STUDIO_META_KEY_LABELS = {
  policy_number: 'Policy #',
  policy_reg_no: 'Policy/Reg #',
  policy_no: 'Policy #',
  reference_no: 'Ref #',
  invoice_number: 'Invoice/Ref #',
  reference_code: 'Ref #',
  insurer: 'Insurer',
  insurer_provider: 'Insurer',
  provider_name: 'Provider',
  counterparty: 'Provider',
  asset: 'Asset',
  vehicle_reg: 'Asset',
  recurrence: 'Cycle',
  reference_range: 'Ref Range',
  reference_note: 'Ref Note',
  renewal_count: 'Renewals',
};

const _STUDIO_INTERNAL_META_KEYS = new Set([
  'source_document',
  'doc_record_id',
  'scenario',
  'ingestion_source',
  'created_via',
  'sha256',
  'vault_rel_path',
  'previous_due_date',
  'last_renewed_at',
]);

function cleanStudioVaultFilename(rawName) {
  return String(rawName || '')
    .trim()
    .replace(/^\d{8}_\d{6}_[0-9a-fA-F]{6,16}_/, '')
    .replace(/^dup_[0-9a-fA-F]{6,16}_/, '');
}

function formatCleanRecordMetadata(dataObj, titleText = '', maxPairs = 4, useMarkdownCode = false) {
  if (!dataObj || typeof dataObj !== 'object') return '';
  const titleNorm = String(titleText || '').trim().toLowerCase().replace(/\s+/g, ' ');
  const seenValues = new Set();
  const priority = [
    'policy_number', 'policy_reg_no', 'policy_no', 'invoice_number',
    'reference_no', 'reference_code', 'asset', 'insurer', 'insurer_provider',
    'provider_name', 'counterparty', 'reference_range', 'reference_note', 'recurrence',
  ];
  const allKeys = [
    ...priority.filter(k => Object.prototype.hasOwnProperty.call(dataObj, k)),
    ...Object.keys(dataObj).filter(k => !priority.includes(k)),
  ];

  const badges = [];
  for (const key of allKeys) {
    if (_STUDIO_INTERNAL_META_KEYS.has(key)) continue;
    const rawVal = dataObj[key];
    if (rawVal === '' || rawVal == null) continue;
    const valStr = String(rawVal).trim();
    if (!valStr) continue;
    const valNorm = valStr.toLowerCase().replace(/\s+/g, ' ');
    if (seenValues.has(valNorm)) continue;
    if (
      valNorm.length >= 4 &&
      titleNorm.includes(valNorm) &&
      ['insurer', 'insurer_provider', 'provider_name', 'counterparty', 'asset', 'vehicle_reg'].includes(key)
    ) {
      seenValues.add(valNorm);
      continue;
    }
    seenValues.add(valNorm);
    const label = _STUDIO_META_KEY_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, ch => ch.toUpperCase());
    if (key === 'recurrence') {
      const cycDisp = valStr.replace(/_/g, '-').replace(/\b\w/g, ch => ch.toUpperCase());
      badges.push(`${label}: ${cycDisp}`);
    } else if (useMarkdownCode && ['policy_number', 'policy_reg_no', 'policy_no', 'invoice_number', 'reference_no', 'reference_code', 'asset'].includes(key)) {
      badges.push(`${label}: \`${valStr}\``);
    } else {
      badges.push(`${label}: ${valStr}`);
    }
    if (badges.length >= maxPairs) break;
  }
  return badges.join(' • ');
}

function _cleanLegacyBracketMetadata(recordChunk) {
  return String(recordChunk || '').replace(/^([\s\S]*?)\s*\[([^\]]+)\]\s*$/, (_full, head, bracketInner) => {
    const obj = {};
    bracketInner.split(/,\s*(?=[a-zA-Z0-9_]+\s*:)/).forEach(pair => {
      const colonIdx = pair.indexOf(':');
      if (colonIdx > 0) {
        const k = pair.slice(0, colonIdx).trim();
        const v = pair.slice(colonIdx + 1).trim();
        if (k && v) obj[k] = v;
      }
    });
    if (Object.keys(obj).length === 0) return `${head} [${bracketInner}]`;
    const cleaned = formatCleanRecordMetadata(obj, head, 4, true);
    return cleaned ? `${head.trim()} • ${cleaned}` : head.trim();
  });
}

function normalizeLegacyRagResponse(rawText) {
  let text = String(rawText || '').trim();
  if (!text) return '';

  // Always strip ugly vault timestamp/hash prefixes from cited filenames
  text = text.replace(/\d{8}_\d{6}_[0-9a-fA-F]{6,16}_(?=[A-Za-z0-9_.-])/g, '');

  // Auto-reflow legacy single-paragraph Grounded RAG responses already saved in SQLite
  if (!text.includes('\n') && (text.includes('Matching tracked records:') || text.includes('From vaulted documents:'))) {
    const sections = [];
    let recordsPart = text;
    let docsPart = '';

    const docSplitIdx = text.indexOf('From vaulted documents:');
    if (docSplitIdx !== -1) {
      recordsPart = text.slice(0, docSplitIdx).trim().replace(/\.$/, '');
      docsPart = text.slice(docSplitIdx + 'From vaulted documents:'.length).trim();
    }

    if (recordsPart.startsWith('Matching tracked records:')) {
      const body = recordsPart.slice('Matching tracked records:'.length).trim().replace(/\.$/, '');
      const rawItems = body.split(/;\s+(?=\*\*|[A-Z0-9])/);
      const itemBullets = rawItems
        .map(it => _cleanLegacyBracketMetadata(it.trim().replace(/\.$/, '')))
        .filter(Boolean)
        .map(it => `- ${it}`);
      if (itemBullets.length > 0) {
        sections.push(`### 📋 Matching Tracked Records (${itemBullets.length})\n${itemBullets.join('\n')}`);
      }
    } else if (recordsPart) {
      sections.push(recordsPart);
    }

    if (docsPart) {
      const rawDocItems = docsPart.split(/\s+\|\s+/).map(s => s.trim()).filter(Boolean);
      const meaningful = rawDocItems.filter(
        s => !/:\s*(?:your (?:car|bike|two-wheeler) insurance policy|document is here)\s*$/i.test(s)
      );
      const finalDocs = (meaningful.length > 0 ? meaningful : rawDocItems).map(s => `- ${s}`);
      if (finalDocs.length > 0) {
        sections.push(`### 📄 Vaulted Document Findings\n${finalDocs.join('\n')}`);
      }
    }

    if (sections.length > 0) {
      return sections.join('\n\n');
    }
  }

  return text;
}

function formatStudioAgentResponseHtml(rawText) {
  const normalized = normalizeLegacyRagResponse(rawText);
  if (!normalized) return '';
  if (typeof window !== 'undefined' && typeof window.formatMarkdown === 'function') {
    return window.formatMarkdown(normalized);
  }
  if (typeof formatMarkdown === 'function') {
    return formatMarkdown(normalized);
  }
  return studioEscapeHtml(normalized)
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:#f8fafc;">$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="color:#7dd3fc;">$1</code>')
    .replace(/\n/g, '<br>');
}

// ============================================================================
// Phase 1: Universal Live CustomAgentRuntime (SQLite State, CRUD, Checklists, AI)
// ============================================================================

const CustomAgentRuntime = {
  _lastStateByAgent: {},
  _lastManifestByAgent: {},
  _searchQueryByAgent: {},
  _editingRecordByAgent: {},
  _pendingExtractionByAgent: {},

  async mount(agentId) {
    if (!agentId) return;
    const panel = document.getElementById(`studio_panel_${agentId}`);
    if (!panel) return;
    this.bindDocFileInputFeedback(agentId);
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(agentId)}/state`);
      if (!res.ok) {
        if (res.status !== 404 && typeof showFleetToast === 'function') {
          const errPayload = await res.json().catch(() => ({}));
          showFleetToast(`✕ Failed to load '${agentId}' state: ${errPayload.message || `HTTP ${res.status}`}`, true);
        }
        return;
      }
      const data = await res.json();
      if (data && data.state) {
        this.renderState(agentId, data.state, data.manifest);
      }
    } catch (err) {
      console.warn(`CustomAgentRuntime mount failed for ${agentId}:`, err);
      if (typeof showFleetToast === 'function') {
        showFleetToast(`✕ Failed to load '${agentId}' state: ${err.message || err}`, true);
      }
    }
  },

  bindDocFileInputFeedback(agentId) {
    const fileInput = document.getElementById(`${agentId}_doc_file_input`);
    if (!fileInput || fileInput.dataset.studioBound === '1') return;
    fileInput.dataset.studioBound = '1';
    fileInput.addEventListener('change', () => {
      const files = Array.from(fileInput.files || []).filter(f => f && f.name);
      const btn = document.getElementById(`${agentId}_doc_extract_btn`);
      const prevBox = document.getElementById(`${agentId}_doc_preview_box`);
      if (btn && !btn.disabled) {
        btn.textContent = files.length > 0 ? `🧠 Extract Items (${files.length})` : '🧠 Extract Items';
      }
      if (files.length > 0 && prevBox && !this._pendingExtractionByAgent[agentId]) {
        const names = files.slice(0, 3).map(f => f.name).join(', ') + (files.length > 3 ? ` +${files.length - 3} more` : '');
        prevBox.style.display = 'block';
        prevBox.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; font-size:12px; color:#7dd3fc;">
            <div>📎 <strong>${files.length} file${files.length === 1 ? '' : 's'}</strong> staged (${studioEscapeHtml(names)}) — click <strong>🧠 Extract Items (${files.length})</strong> to extract trackable items.</div>
            <button type="button" title="Run AI tracking extraction now" class="btn btn-primary" onclick="CustomAgentRuntime.uploadAndExtractDocument('${studioEscapeHtml(agentId)}')" style="padding:4px 10px; font-size:11px; font-weight:700;">🧠 Extract Now</button>
          </div>
        `;
      }
    });
  },

  renderState(agentId, state, manifest) {
    if (!state) return;
    this._lastStateByAgent[agentId] = state;
    if (manifest) this._lastManifestByAgent[agentId] = manifest;
    const effManifest = manifest || this._lastManifestByAgent[agentId] || null;
    const kpis = state.kpis || {};

    // 1. KPI Row
    const elStatus = document.getElementById(`${agentId}_kpi_status`);
    const elEntries = document.getElementById(`${agentId}_kpi_entries`);
    const elDue = document.getElementById(`${agentId}_kpi_due`);
    const elRuns = document.getElementById(`${agentId}_kpi_runs`);

    const hasWarning = (kpis.due_soon || 0) > 0 || kpis.last_status === 'warning';
    if (elStatus) {
      elStatus.textContent = hasWarning ? 'Attention' : (kpis.total_runs > 0 ? 'Nominal' : 'Ready');
      elStatus.style.color = hasWarning ? '#fbbf24' : '#10b981';
    }
    if (elEntries) {
      const sumSuffix = kpis.numeric_sum ? ` (${Number(kpis.numeric_sum).toLocaleString()})` : '';
      elEntries.textContent = `${kpis.total_entries || 0}${sumSuffix}`;
    }
    if (elDue) {
      elDue.textContent = String(kpis.due_soon || 0);
      elDue.style.color = (kpis.due_soon || 0) > 0 ? '#f87171' : '#38bdf8';
    }
    if (elRuns && effManifest?.schedule?.display) {
      elRuns.textContent = `${effManifest.schedule.display} (${kpis.total_runs || 0} runs)`;
    } else if (elRuns && kpis.total_runs != null) {
      elRuns.title = `${kpis.total_runs} total runs logged`;
    }

    // 2. Alert Banner
    const banner = document.getElementById(`${agentId}_alert_banner`);
    const dot = document.getElementById(`${agentId}_alert_dot`);
    const bTitle = document.getElementById(`${agentId}_alert_title`);
    if (banner && bTitle) {
      if (hasWarning) {
        banner.style.background = 'rgba(245, 158, 11, 0.12)';
        banner.style.borderColor = 'rgba(245, 158, 11, 0.38)';
        if (dot) dot.textContent = '🟠';
        bTitle.style.color = '#fbbf24';
        bTitle.textContent = `${kpis.due_soon || 1} Upcoming Deadline / Threshold Alert(s) Detected`;
      } else {
        banner.style.background = 'rgba(16, 185, 129, 0.1)';
        banner.style.borderColor = 'rgba(16, 185, 129, 0.3)';
        if (dot) dot.textContent = '🟢';
        bTitle.style.color = '#10b981';
        if (effManifest?.name) bTitle.textContent = `${effManifest.name} Active & Nominal`;
      }
    }

    // 3. Countdown & Renewal Cards
    const cdBox = document.getElementById(`${agentId}_countdown_box`);
    const cdBadge = document.getElementById(`${agentId}_countdown_badge`);
    if (cdBox) {
      const countdowns = state.countdowns || [];
      if (cdBadge) cdBadge.textContent = `${countdowns.length} dated item(s)`;
      if (countdowns.length === 0) {
        cdBox.innerHTML = `<div style="padding: 10px 12px; border-radius: 8px; background: rgba(0, 0, 0, 0.25);">Add an entry with a date above to see live countdowns and 15-day renewal alerts.</div>`;
      } else {
        cdBox.innerHTML = countdowns.map(c => {
          const days = c.days_left;
          let color = '#34d399';
          let pill = `${days}d left`;
          if (c.is_completed) {
            color = '#10b981';
            pill = '✓ COMPLETED';
          } else if (days < 0) {
            color = '#f87171';
            pill = `${Math.abs(days)}d OVERDUE`;
          } else if (days <= 15) {
            color = '#fbbf24';
            pill = days === 0 ? 'DUE TODAY' : `Due in ${days}d`;
          }
          const extra = formatCleanRecordMetadata(c.data, c.title, 2);
          const amt = c.numeric_value ? ` • ${Number(c.numeric_value).toLocaleString()}` : '';
          const renewBtnHtml = !c.is_completed
            ? `<button type="button" class="btn" title="Renew / Roll Forward to next cycle" onclick="CustomAgentRuntime.renewRecord('${studioEscapeHtml(agentId)}', ${Number(c.id)})" style="padding: 1px 7px; font-size: 10px; border-radius: 999px; border-color: rgba(56, 189, 248, 0.4); color: #7dd3fc;">🔄 Renew</button>`
            : '';
          return `
            <div style="padding: 11px 13px; border-radius: 8px; background: rgba(0,0,0,0.32); border: 1px solid ${color}44; display: flex; flex-direction: column; gap: 4px;">
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px;">
                <strong style="color: #f8fafc; font-size: 12.5px;">${studioEscapeHtml(c.title)}</strong>
                <div style="display: inline-flex; align-items: center; gap: 5px;">
                  ${renewBtnHtml}
                  <span style="font-size: 10.5px; font-weight: 700; padding: 2px 7px; border-radius: 999px; background: ${color}22; color: ${color};">${pill}</span>
                </div>
              </div>
              <div style="font-size: 11px; color: #94a3b8;">📅 ${studioEscapeHtml(c.due_date)}${studioEscapeHtml(amt)}${extra ? ' • ' + studioEscapeHtml(extra) : ''}</div>
            </div>
          `;
        }).join('');
      }
    }

    // 4. AI Briefing & Insight Card
    const insightBox = document.getElementById(`${agentId}_insight_box`);
    if (insightBox && state.latest_insight) {
      const ins = state.latest_insight;
      const summary = ins.data?.summary || ins.title || '';
      const modelTag = ins.data?.model ? ` (${studioEscapeHtml(ins.data.model)})` : '';
      const formatted = formatStudioAgentResponseHtml(summary);
      insightBox.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 11px; color: #c4b5fd; margin-bottom: 6px; padding-bottom: 5px; border-bottom: 1px solid rgba(167, 139, 250, 0.18); font-weight: 600;">
          <span>🧠 Executive Briefing${modelTag}</span>
          <span style="color: #94a3b8; font-weight: 400;">${studioEscapeHtml((ins.updated_at || '').slice(0, 16).replace('T', ' '))}</span>
        </div>
        <div style="font-size: 12.5px; color: #e2e8f0; line-height: 1.56;">${formatted}</div>
      `;
    }

    // 5. Daily Action Checklist
    const checkBox = document.getElementById(`${agentId}_checklist_box`);
    const streakEl = document.getElementById(`${agentId}_checklist_streak`);
    if (streakEl && Array.isArray(state.checklist)) {
      const streakTxt = state.checklist_streak > 0 ? ` • 🔥 ${state.checklist_streak}` : '';
      streakEl.textContent = `${state.checklist_done || 0} / ${state.checklist_total || state.checklist.length} Done${streakTxt}`;
    }
    if (checkBox && Array.isArray(state.checklist) && state.checklist.length > 0) {
      checkBox.innerHTML = state.checklist.map(item => `
        <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; ${item.checked ? 'text-decoration: line-through; color: #64748b;' : 'color: #e2e8f0;'}">
          <input type="checkbox" ${item.checked ? 'checked' : ''}
            onchange="CustomAgentRuntime.toggleCheck('${studioEscapeHtml(agentId)}', '${studioEscapeHtml(item.item_key)}', this.checked, '${studioEscapeHtml(item.label)}')">
          <span>${studioEscapeHtml(item.label)}</span>
        </label>
      `).join('');
    }

    // 6. History & SQLite Records Table (Phase 4: Live Search, Inline Edit, Complete Toggle & CSV Export)
    const histBox = document.getElementById(`${agentId}_history_box`);
    const histCount = document.getElementById(`${agentId}_history_count`);
    if (histBox) {
      const allEntries = state.entries || [];
      const allRuns = state.runs || [];
      const query = String(this._searchQueryByAgent[agentId] || '').trim().toLowerCase();
      const entries = query
        ? allEntries.filter(e =>
            String(e.title || '').toLowerCase().includes(query) ||
            String(e.due_date || '').toLowerCase().includes(query) ||
            String(e.status || '').toLowerCase().includes(query) ||
            JSON.stringify(e.data || {}).toLowerCase().includes(query)
          )
        : allEntries;
      const runs = query
        ? allRuns.filter(r => String(r.title || '').toLowerCase().includes(query))
        : allRuns;

      if (histCount) histCount.textContent = `${allEntries.length} entries • ${allRuns.length} runs`;

      // Provide fallback toolbar for pre-Phase-4 panels that don't have #${agentId}_history_search in header
      const hasHeaderSearch = Boolean(document.getElementById(`${agentId}_history_search`));
      const fallbackToolbar = !hasHeaderSearch ? `
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
          <input type="search" value="${studioEscapeHtml(this._searchQueryByAgent[agentId] || '')}" placeholder="Filter records..."
            oninput="CustomAgentRuntime.filterHistory('${studioEscapeHtml(agentId)}', this.value)"
            style="padding: 4px 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.14); background: rgba(0,0,0,0.35); color: #f8fafc; font-size: 11.5px; min-width: 155px;">
          <a href="/api/fleet/agents/${encodeURIComponent(agentId)}/export.csv" download="${studioEscapeHtml(agentId)}_records.csv"
            class="btn btn-secondary" style="padding: 4px 10px; font-size: 11px; text-decoration: none; border-color: rgba(16, 185, 129, 0.4); color: #34d399;">📥 Export CSV</a>
        </div>
      ` : '';

      if (allEntries.length === 0 && allRuns.length === 0) {
        histBox.innerHTML = `${fallbackToolbar}<div style="color: #94a3b8;">No records yet — add your first item in Quick Capture above or click <strong>▶ Run</strong>.</div>`;
      } else if (entries.length === 0 && runs.length === 0) {
        histBox.innerHTML = `${fallbackToolbar}<div style="color: #94a3b8;">No records match filter "<strong>${studioEscapeHtml(query)}</strong>".</div>`;
      } else {
        const editingId = Number(this._editingRecordByAgent[agentId] || 0);
        const entryRows = entries.map(e => {
          const recId = Number(e.id);
          const isCompleted = ['completed', 'done', 'resolved'].includes(String(e.status || '').toLowerCase());
          if (editingId === recId) {
            return `
              <tr style="border-bottom: 1px solid rgba(56,189,248,0.25); background: rgba(56,189,248,0.08);">
                <td style="padding: 7px 8px;"><span style="padding:2px 6px; border-radius:4px; background:rgba(168,85,247,0.2); color:#d8b4fe; font-size:10.5px;">EDIT</span></td>
                <td style="padding: 6px 8px;">
                  <input type="text" id="${studioEscapeHtml(agentId)}_edit_title_${recId}" value="${studioEscapeHtml(e.title)}"
                    style="width:100%; padding:5px 8px; border-radius:6px; border:1px solid rgba(56,189,248,0.4); background:rgba(0,0,0,0.45); color:#f8fafc; font-size:12px;">
                </td>
                <td style="padding: 6px 8px;">
                  <input type="date" id="${studioEscapeHtml(agentId)}_edit_due_${recId}" value="${studioEscapeHtml((e.due_date || '').slice(0, 10))}"
                    style="padding:5px 7px; border-radius:6px; border:1px solid rgba(56,189,248,0.4); background:rgba(0,0,0,0.45); color:#f8fafc; font-size:11.5px;">
                </td>
                <td style="padding: 6px 8px;">
                  <input type="number" step="any" id="${studioEscapeHtml(agentId)}_edit_num_${recId}" value="${e.numeric_value ? Number(e.numeric_value) : ''}" placeholder="0"
                    style="width:92px; padding:5px 7px; border-radius:6px; border:1px solid rgba(56,189,248,0.4); background:rgba(0,0,0,0.45); color:#34d399; font-size:11.5px;">
                </td>
                <td style="padding: 6px 8px; text-align: right; white-space: nowrap;">
                  <button type="button" class="btn" title="Save changes" onclick="CustomAgentRuntime.saveEditedRecord('${studioEscapeHtml(agentId)}', ${recId})" style="padding: 3px 8px; font-size: 11px; color: #34d399; border-color: rgba(16,185,129,0.45);">💾 Save</button>
                  <button type="button" class="btn" title="Cancel edit" onclick="CustomAgentRuntime.cancelEditRecord('${studioEscapeHtml(agentId)}')" style="padding: 3px 7px; font-size: 11px; color: #94a3b8;">✕</button>
                </td>
              </tr>
            `;
          }
          const rawSrcDoc = e.data && typeof e.data === 'object' ? e.data.source_document : '';
          const srcDoc = cleanStudioVaultFilename(rawSrcDoc);
          const extra = formatCleanRecordMetadata(e.data, e.title, 5);
          const srcChipHtml = srcDoc
            ? `<span title="Extracted from uploaded document: ${studioEscapeHtml(srcDoc)}" style="margin-left:5px; padding:1px 6px; border-radius:4px; background:rgba(14,116,144,0.28); color:#7dd3fc; font-size:10px; font-weight:500;">📎 ${studioEscapeHtml(srcDoc)}</span>`
            : '';
          const badgeHtml = isCompleted
            ? `<span style="padding:2px 6px; border-radius:4px; background:rgba(16,185,129,0.18); color:#34d399; font-size:10.5px;">DONE</span>`
            : `<span style="padding:2px 6px; border-radius:4px; background:rgba(56,189,248,0.14); color:#38bdf8; font-size:10.5px;">ENTRY</span>`;
          const titleStyle = isCompleted ? 'color:#64748b; text-decoration:line-through;' : 'color:#f8fafc;';
          const nextStatus = isCompleted ? 'ok' : 'completed';
          const toggleLabel = isCompleted ? '↩' : '✓';
          const toggleTitle = isCompleted ? 'Reopen item' : 'Mark completed';
          const renewActionBtn = e.due_date && !isCompleted
            ? `<button type="button" class="btn" title="Renew / Roll Forward to next cycle" onclick="CustomAgentRuntime.renewRecord('${studioEscapeHtml(agentId)}', ${recId})" style="padding: 2px 7px; font-size: 11px; color: #7dd3fc;">🔄</button>`
            : '';
          return `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.06);">
              <td style="padding: 7px 8px;">${badgeHtml}</td>
              <td style="padding: 7px 8px; ${titleStyle} font-weight: 600;">${studioEscapeHtml(e.title)}${srcChipHtml}<div style="font-size:11px; color:#94a3b8; font-weight:400; text-decoration:none;">${studioEscapeHtml(extra)}</div></td>
              <td style="padding: 7px 8px; color: #cbd5e1;">${e.due_date ? '📅 ' + studioEscapeHtml(e.due_date) : '—'}</td>
              <td style="padding: 7px 8px; color: #34d399; font-family: monospace;">${e.numeric_value ? Number(e.numeric_value).toLocaleString() : '—'}</td>
              <td style="padding: 7px 8px; text-align: right; white-space: nowrap;">
                ${renewActionBtn}
                <button type="button" class="btn" title="${toggleTitle}" onclick="CustomAgentRuntime.setRecordStatus('${studioEscapeHtml(agentId)}', ${recId}, '${nextStatus}')" style="padding: 2px 7px; font-size: 11px; color: #34d399;">${toggleLabel}</button>
                <button type="button" class="btn" title="Inline edit entry" onclick="CustomAgentRuntime.editRecord('${studioEscapeHtml(agentId)}', ${recId})" style="padding: 2px 7px; font-size: 11px; color: #38bdf8;">✏️</button>
                <button type="button" class="btn" title="Delete entry" onclick="CustomAgentRuntime.deleteRecord('${studioEscapeHtml(agentId)}', ${recId})" style="padding: 2px 7px; font-size: 11px; color: #f87171;">✕</button>
              </td>
            </tr>
          `;
        }).join('');

        const runRows = runs.slice(0, 8).map(r => {
          const badgeColor = r.status === 'warning' ? '#fbbf24' : '#34d399';
          return `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
              <td style="padding: 6px 8px;"><span style="padding:2px 6px; border-radius:4px; background:${badgeColor}22; color:${badgeColor}; font-size:10.5px;">RUN</span></td>
              <td colspan="2" style="padding: 6px 8px; color: #cbd5e1; font-size: 12px;">${studioEscapeHtml(r.title)}</td>
              <td style="padding: 6px 8px; color: #64748b; font-size: 11px;">${studioEscapeHtml((r.created_at || '').slice(11, 19))}</td>
              <td style="padding: 6px 8px; text-align: right;">
                <button type="button" class="btn" title="Remove log" onclick="CustomAgentRuntime.deleteRecord('${studioEscapeHtml(agentId)}', ${Number(r.id)})" style="padding: 2px 7px; font-size: 11px; color: #64748b;">✕</button>
              </td>
            </tr>
          `;
        }).join('');

        histBox.innerHTML = `
          ${fallbackToolbar}
          <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <thead>
              <tr style="text-align: left; color: #64748b; font-size: 10.5px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.08);">
                <th style="padding: 5px 8px;">Type</th>
                <th style="padding: 5px 8px;">Item / Summary</th>
                <th style="padding: 5px 8px;">Date</th>
                <th style="padding: 5px 8px;">Value / Time</th>
                <th style="padding: 5px 8px; text-align: right;">Action</th>
              </tr>
            </thead>
            <tbody>${entryRows}${runRows}</tbody>
          </table>
        `;
      }
    }

    // 6b. Status Kanban Board Block (Phase 4 10th UI Block)
    const kanbanBox = document.getElementById(`${agentId}_kanban_box`);
    const kanbanBadge = document.getElementById(`${agentId}_kanban_badge`);
    if (kanbanBox) {
      const entries = state.entries || [];
      const cdMap = new Map();
      (state.countdowns || []).forEach(c => cdMap.set(Number(c.id), c));

      const colActive = [];
      const colAttention = [];
      const colDone = [];

      entries.forEach(e => {
        const st = String(e.status || 'ok').toLowerCase();
        const cd = cdMap.get(Number(e.id));
        if (['completed', 'done', 'resolved'].includes(st)) {
          colDone.push({ entry: e, cd });
        } else if (st === 'warning' || st === 'attention' || (cd && typeof cd.days_left === 'number' && cd.days_left <= 15)) {
          colAttention.push({ entry: e, cd });
        } else {
          colActive.push({ entry: e, cd });
        }
      });

      if (kanbanBadge) {
        kanbanBadge.textContent = `${colActive.length} Active • ${colAttention.length} Attention • ${colDone.length} Completed`;
      }

      const renderCol = (title, accent, list, stageKey) => {
        const cards = list.length === 0
          ? `<div style="font-size: 11px; color: #64748b; padding: 8px 4px;">No items in this column</div>`
          : list.map(({ entry, cd }) => {
              const rid = Number(entry.id);
              const dueLabel = cd
                ? (cd.days_left < 0 ? `${Math.abs(cd.days_left)}d overdue` : `${cd.days_left}d left`)
                : (entry.due_date || '');
              const valLabel = entry.numeric_value ? ` • ${Number(entry.numeric_value).toLocaleString()}` : '';
              let actionsHtml = '';
              if (stageKey !== 'attention' && stageKey !== 'done') {
                actionsHtml += `<button type="button" class="btn" title="Move to Attention" onclick="CustomAgentRuntime.setRecordStatus('${studioEscapeHtml(agentId)}', ${rid}, 'warning')" style="padding: 1px 6px; font-size: 10px; color: #fbbf24;">⏳</button>`;
              }
              if (stageKey !== 'done') {
                actionsHtml += `<button type="button" class="btn" title="Mark Completed" onclick="CustomAgentRuntime.setRecordStatus('${studioEscapeHtml(agentId)}', ${rid}, 'completed')" style="padding: 1px 6px; font-size: 10px; color: #34d399;">✓ Done</button>`;
              } else {
                actionsHtml += `<button type="button" class="btn" title="Reopen to Active" onclick="CustomAgentRuntime.setRecordStatus('${studioEscapeHtml(agentId)}', ${rid}, 'ok')" style="padding: 1px 6px; font-size: 10px; color: #38bdf8;">↩ Reopen</button>`;
              }
              return `
                <div style="padding: 8px 10px; border-radius: 7px; background: rgba(15, 23, 42, 0.85); border: 1px solid ${accent}33; display: flex; flex-direction: column; gap: 4px;">
                  <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 6px;">
                    <strong style="font-size: 12px; color: ${stageKey === 'done' ? '#94a3b8' : '#f8fafc'}; ${stageKey === 'done' ? 'text-decoration: line-through;' : ''}">${studioEscapeHtml(entry.title)}</strong>
                    <div style="display: flex; gap: 4px;">${actionsHtml}</div>
                  </div>
                  ${(dueLabel || valLabel) ? `<div style="font-size: 10.5px; color: #94a3b8;">${dueLabel ? '📅 ' + studioEscapeHtml(dueLabel) : ''}${studioEscapeHtml(valLabel)}</div>` : ''}
                </div>
              `;
            }).join('');

        return `
          <div style="padding: 10px; border-radius: 8px; background: rgba(0, 0, 0, 0.28); border-top: 2px solid ${accent}; display: flex; flex-direction: column; gap: 7px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <strong style="font-size: 11.5px; color: ${accent};">${title}</strong>
              <span style="font-size: 10.5px; padding: 1px 7px; border-radius: 999px; background: ${accent}20; color: ${accent}; font-weight: 700;">${list.length}</span>
            </div>
            ${cards}
          </div>
        `;
      };

      kanbanBox.innerHTML = [
        renderCol('📋 Active / Safe', '#38bdf8', colActive, 'active'),
        renderCol('⏳ Due Soon / Attention', '#fbbf24', colAttention, 'attention'),
        renderCol('✅ Completed', '#34d399', colDone, 'done'),
      ].join('');
    }

    // 7. Autonomic Event Timeline
    const tlBox = document.getElementById(`${agentId}_timeline_box`);
    if (tlBox && Array.isArray(state.runs) && state.runs.length > 0) {
      tlBox.innerHTML = state.runs.slice(0, 6).map(r => {
        const ts = (r.created_at || '').slice(0, 19).replace('T', ' ');
        const tag = r.status === 'warning' ? '[WARN]' : '[OK]';
        const col = r.status === 'warning' ? '#fbbf24' : '#38bdf8';
        return `<div style="color:${col};">${studioEscapeHtml(ts)} ${tag} ${studioEscapeHtml(r.title)}</div>`;
      }).join('');
    }

    // 8. Trend Sparkline Chart (Phase 3 Inline SVG)
    const sparkBox = document.getElementById(`${agentId}_sparkline_box`);
    const sparkStats = document.getElementById(`${agentId}_sparkline_stats`);
    if (sparkBox) {
      const series = [];
      const cycleChron = (state.cycle_history || []).slice().reverse();
      cycleChron.forEach(ch => {
        const val = Number(ch.numeric_value);
        if (Number.isFinite(val) && val > 0) {
          series.push({ label: ch.data?.item_title || ch.title || 'Cycle', value: val });
        }
      });
      const entriesChron = (state.entries || []).slice().reverse();
      entriesChron.forEach(e => {
        const val = Number(e.numeric_value);
        if (Number.isFinite(val) && val > 0) {
          series.push({ label: e.title || 'Entry', value: val });
        }
      });
      if (series.length === 0 && Array.isArray(state.runs)) {
        state.runs.slice().reverse().forEach(r => {
          const probes = r.data?.metrics?.http_probes;
          if (Array.isArray(probes) && probes.length > 0) {
            const lat = Number(probes[0].latency_ms);
            if (Number.isFinite(lat) && lat >= 0) {
              series.push({ label: `${probes[0].name || 'HTTP'} (ms)`, value: lat });
            }
          } else {
            const diskUsed = Number(r.data?.metrics?.disk_used_pct);
            if (Number.isFinite(diskUsed) && diskUsed > 0) {
              series.push({ label: 'Disk %', value: diskUsed });
            }
          }
        });
      }
      const pts = series.slice(-20);
      if (pts.length === 0) {
        if (sparkStats) sparkStats.textContent = 'Min: -- • Avg: -- • Latest: --';
      } else {
        const vals = pts.map(p => p.value);
        const minV = Math.min(...vals);
        const maxV = Math.max(...vals);
        const avgV = vals.reduce((a, b) => a + b, 0) / vals.length;
        const latestV = vals[vals.length - 1];
        if (sparkStats) {
          sparkStats.textContent = `Min: ${minV.toLocaleString(undefined, { maximumFractionDigits: 1 })} • Avg: ${avgV.toLocaleString(undefined, { maximumFractionDigits: 1 })} • Latest: ${latestV.toLocaleString(undefined, { maximumFractionDigits: 1 })}`;
        }
        const W = 420;
        const H = 74;
        const padX = 14;
        const padY = 12;
        const span = Math.max(maxV - minV, 1);
        const coords = pts.map((p, idx) => {
          const x = pts.length === 1 ? W / 2 : padX + (idx / (pts.length - 1)) * (W - padX * 2);
          const y = H - padY - ((p.value - minV) / span) * (H - padY * 2);
          return { x: Number(x.toFixed(1)), y: Number(y.toFixed(1)), label: p.label, value: p.value };
        });
        const polyPoints = coords.map(c => `${c.x},${c.y}`).join(' ');
        const areaPoints = `${coords[0].x},${H - 4} ${polyPoints} ${coords[coords.length - 1].x},${H - 4}`;
        const dotsSvg = coords.map(c =>
          `<circle cx="${c.x}" cy="${c.y}" r="3.4" fill="#38bdf8" stroke="#0f172a" stroke-width="1.5"><title>${studioEscapeHtml(c.label)}: ${c.value}</title></circle>`
        ).join('');
        sparkBox.innerHTML = `
          <svg viewBox="0 0 ${W} ${H}" style="width: 100%; height: 76px; overflow: visible;">
            <polygon points="${areaPoints}" fill="rgba(56, 189, 248, 0.14)"></polygon>
            <polyline fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" points="${polyPoints}"></polyline>
            ${dotsSvg}
          </svg>
        `;
      }
    }

    // 9. Document Upload & AI Extractor History Ledger (Phase 5 11th UI Block + Multi-Attachment)
    const docFileInp = document.getElementById(`${agentId}_doc_file_input`);
    if (docFileInp && !docFileInp.multiple) {
      docFileInp.multiple = true;
    }
    const docBadge = document.getElementById(`${agentId}_doc_count_badge`);
    const docHistBox = document.getElementById(`${agentId}_doc_history_box`);
    const docs = Array.isArray(state.documents) ? state.documents : [];
    if (docBadge) {
      docBadge.textContent = docs.length > 0
        ? `${docs.length} document${docs.length === 1 ? '' : 's'} ingested`
        : 'PDF • DOCX • XLSX • CSV • EML • Image';
    }
    if (docHistBox) {
      if (docs.length === 0) {
        docHistBox.style.display = 'none';
        docHistBox.innerHTML = '';
      } else {
        docHistBox.style.display = 'block';
        docHistBox.innerHTML = `
          <div style="font-size: 10.5px; color: #7dd3fc; font-weight: 700; text-transform: uppercase; margin-bottom: 5px;">Recent Ingested Documents (Vaulted)</div>
          <div style="display: flex; flex-wrap: wrap; gap: 6px;">
            ${docs.slice(0, 8).map(d => {
              const dm = d.data && typeof d.data === 'object' ? d.data : {};
              const icon = dm.scenario_icon || '📄';
              const cnt = Number(dm.items_count ?? d.numeric_value ?? 0);
              const mdl = dm.model_used || dm.engine_used || '';
              const cleanDocTitle = cleanStudioVaultFilename(d.title || dm.filename || 'document');
              return `
                <div title="${studioEscapeHtml(dm.summary || cleanDocTitle)}" style="display: inline-flex; align-items: center; gap: 6px; padding: 4px 9px; border-radius: 999px; background: rgba(15, 23, 42, 0.78); border: 1px solid rgba(56, 189, 248, 0.25); font-size: 11px; color: #e2e8f0;">
                  <span>${studioEscapeHtml(icon)}</span>
                  <strong>${studioEscapeHtml(cleanDocTitle)}</strong>
                  <span style="color: #34d399;">${cnt} item${cnt === 1 ? '' : 's'}</span>
                  ${mdl ? `<span style="color: #64748b; font-size: 10px;">(${studioEscapeHtml(mdl)})</span>` : ''}
                  <button type="button" title="Re-extract tracking items from this vaulted document using connected LLM" class="btn" onclick="CustomAgentRuntime.reextractVaultDocuments('${studioEscapeHtml(agentId)}', ${Number(d.id)})" style="padding: 0 4px; font-size: 10.5px; color: #38bdf8; background: transparent; border: none; cursor: pointer;">🔄</button>
                  <button type="button" title="Remove document log entry" class="btn" onclick="CustomAgentRuntime.deleteRecord('${studioEscapeHtml(agentId)}', ${Number(d.id)})" style="padding: 0 4px; font-size: 10px; color: #64748b; background: transparent; border: none;">✕</button>
                </div>
              `;
            }).join('')}
          </div>
        `;
      }
    }

    // 10. Grounded Agent Q&A & Command Chat Block (Phase 6 12th UI Block)
    const chatLog = document.getElementById(`${agentId}_chat_log`);
    if (chatLog) {
      chatLog.style.maxHeight = '380px';
      chatLog.style.gap = '10px';
      const chats = Array.isArray(state.chat_history) ? state.chat_history : [];
      if (chats.length === 0) {
        chatLog.innerHTML = `<div style="color: #94a3b8; font-size: 12px;">Ask any question about tracked items or uploaded PDFs/docs, or type a direct command below (e.g. <code>add Policy Renewal due 2026-12-15 for 18500</code>).</div>`;
      } else {
        chatLog.innerHTML = chats.map(ch => {
          const cd = ch.data && typeof ch.data === 'object' ? ch.data : {};
          const q = cd.question || ch.title || '';
          const ansRaw = cd.answer || '';
          const ansHtml = formatStudioAgentResponseHtml(ansRaw);
          const rawEngine = String(cd.engine || '').trim();
          const isZeroCost = rawEngine.includes('$0.00') || rawEngine.startsWith('deterministic');
          const engineBadgeHtml = rawEngine
            ? `<span style="font-size: 10px; padding: 2px 8px; border-radius: 999px; background: ${isZeroCost ? 'rgba(16, 185, 129, 0.14)' : 'rgba(139, 92, 246, 0.18)'}; border: 1px solid ${isZeroCost ? 'rgba(52, 211, 153, 0.3)' : 'rgba(167, 139, 250, 0.35)'}; color: ${isZeroCost ? '#6ee7b7' : '#ddd6fe'}; font-weight: 500; white-space: nowrap;">${isZeroCost ? '⚡ ' : '🧠 '}${studioEscapeHtml(rawEngine)}</span>`
            : '';
          return `
            <div style="display: flex; flex-direction: column; gap: 7px; padding: 10px 13px; border-radius: 9px; background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(56, 189, 248, 0.16); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.22);">
              <div style="display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; padding-bottom: 6px; border-bottom: 1px solid rgba(255, 255, 255, 0.07);">
                <div style="font-size: 12px; color: #7dd3fc; font-weight: 600;">💬 You: <span style="color: #f0f9ff;">${studioEscapeHtml(q)}</span></div>
                ${engineBadgeHtml}
              </div>
              <div style="font-size: 12.5px; color: #e2e8f0; line-height: 1.56;">${ansHtml}</div>
            </div>
          `;
        }).join('');
        chatLog.scrollTop = chatLog.scrollHeight;
      }
    }

    // 11. Pending Headless Recorded Workflow Input Checkpoints
    const pendingRuns = Array.isArray(state.pending_workflow_runs) ? state.pending_workflow_runs : [];
    const promptBox = document.getElementById(`${agentId}_workflow_input_prompt_box`);
    if (promptBox) {
      if (pendingRuns.length > 0) {
        const pd = pendingRuns[0].data && typeof pendingRuns[0].data === 'object' ? pendingRuns[0].data : {};
        this.renderWorkflowInputPrompt(agentId, pd.run_id || '', pd.pending_inputs || [], pendingRuns[0].title || 'Runtime input required', Boolean(pd.dry_run));
      } else {
        promptBox.style.display = 'none';
        promptBox.innerHTML = '';
      }
    }
  },

  handleDocDrop(event, agentId) {
    if (!event) return;
    event.preventDefault();
    const card = document.getElementById(`${agentId}_doc_vault_card`);
    if (card) card.style.borderColor = 'rgba(56, 189, 248, 0.42)';
    const droppedFiles = Array.from(event.dataTransfer?.files || []);
    if (droppedFiles.length > 0) {
      this.uploadAndExtractDocument(agentId, droppedFiles);
    }
  },

  async uploadAndExtractDocument(agentId, overrideFiles = null) {
    this.bindDocFileInputFeedback(agentId);
    const fileInput = document.getElementById(`${agentId}_doc_file_input`);
    const hintInput = document.getElementById(`${agentId}_doc_hint_input`);
    const autoCommitEl = document.getElementById(`${agentId}_doc_auto_commit`);
    const btn = document.getElementById(`${agentId}_doc_extract_btn`);
    const prevBox = document.getElementById(`${agentId}_doc_preview_box`);

    const rawList = overrideFiles
      ? (overrideFiles instanceof File ? [overrideFiles] : Array.from(overrideFiles || []))
      : Array.from(fileInput?.files || []);
    const files = rawList.filter(f => f && typeof f.name === 'string');

    if (files.length === 0) {
      const lastState = this._lastStateByAgent[agentId] || {};
      const vaultedDocs = Array.isArray(lastState.documents) ? lastState.documents : [];
      if (vaultedDocs.length > 0) {
        return this.reextractVaultDocuments(agentId, 0);
      }
      if (prevBox) {
        prevBox.style.display = 'block';
        prevBox.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; font-size:12px; color:#fbbf24;">
            <div>📂 <strong>No new file selected yet.</strong> Choose or drag-and-drop PDFs, DOCX, XLSX, CSV, EML, ICS, TXT, or Images — or re-extract from any files stored in this agent's vault folder:</div>
            <div style="display:flex; gap:7px; align-items:center; flex-wrap:wrap;">
              <button type="button" title="Open file picker to select documents" class="btn btn-primary" onclick="document.getElementById('${studioEscapeHtml(agentId)}_doc_file_input')?.click()" style="padding:4px 10px; font-size:11.5px; font-weight:700;">📂 Choose Files...</button>
              <button type="button" title="Re-extract tracking items from previously vaulted files on disk" class="btn btn-secondary" onclick="CustomAgentRuntime.reextractVaultDocuments('${studioEscapeHtml(agentId)}', 0)" style="padding:4px 10px; font-size:11.5px; border-color:rgba(56,189,248,0.45); color:#7dd3fc;">🔄 Re-Extract from Vault</button>
              <button type="button" title="Dismiss notice" class="btn" onclick="CustomAgentRuntime.dismissExtractedPreview('${studioEscapeHtml(agentId)}')" style="padding:3px 7px; font-size:11px; color:#94a3b8;">✕</button>
            </div>
          </div>
        `;
      }
      if (typeof showFleetToast === 'function') {
        showFleetToast('Select one or more documents to extract (or click "🔄 Re-Extract from Vault").', true);
      }
      if (fileInput && typeof fileInput.click === 'function') {
        try { fileInput.click(); } catch (_e) {}
      }
      return;
    }
    if (files.length > 10) {
      if (typeof showFleetToast === 'function') showFleetToast('Maximum 10 attachments allowed per extraction batch.', true);
      return;
    }
    for (const f of files) {
      if (f.size > 12 * 1024 * 1024) {
        if (typeof showFleetToast === 'function') showFleetToast(`'${f.name}' exceeds 12 MB upload limit.`, true);
        return;
      }
    }

    const autoCommit = Boolean(autoCommitEl && autoCommitEl.checked);
    const extractionHint = (hintInput?.value || '').trim();
    const labelNames = files.length === 1
      ? files[0].name
      : `${files.length} attachments (${files.slice(0, 3).map(f => f.name).join(', ')})`;

    if (prevBox) {
      prevBox.style.display = 'block';
      prevBox.innerHTML = `<div style="font-size: 12px; color: #38bdf8;">⏳ Parsing <strong>${studioEscapeHtml(labelNames)}</strong> &amp; extracting tracking items via connected LLM...</div>`;
    }

    await runFleetAsyncAction({
      buttons: [btn],
      useStudioBanner: false,
      busyLabel: files.length > 1 ? `⏳ Extracting (${files.length})...` : '⏳ Extracting...',
      startToast: `⏳ Extracting items from ${labelNames}...`,
      errorPrefix: 'Document extraction failed',
      onError: (err) => {
        if (prevBox) {
          prevBox.style.display = 'block';
          prevBox.innerHTML = `<div style="font-size: 12px; color: #fca5a5;">✕ Extraction failed: ${studioEscapeHtml(err.message)}</div>`;
        }
      },
      onFinally: () => {
        if (btn) {
          const remaining = Array.from(fileInput?.files || []).length;
          btn.textContent = remaining > 0 ? `🧠 Extract Items (${remaining})` : '🧠 Extract Items';
        }
      },
    }, async () => {
      const documentsPayload = await Promise.all(
        files.map(async f => ({
          filename: f.name,
          content_base64: await readFileAsBase64(f),
        }))
      );
      const reqBody = files.length === 1
        ? {
            filename: documentsPayload[0].filename,
            content_base64: documentsPayload[0].content_base64,
            extraction_hint: extractionHint,
            auto_commit: autoCommit,
          }
        : {
            documents: documentsPayload,
            extraction_hint: extractionHint,
            auto_commit: autoCommit,
          };

      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/documents/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not extract items from document.');
      }

      if (fileInput) fileInput.value = '';
      this._handleExtractionSuccess(agentId, data, labelNames, files.length);
    });
  },

  async reextractVaultDocuments(agentId, docRecordId = 0) {
    const hintInput = document.getElementById(`${agentId}_doc_hint_input`);
    const autoCommitEl = document.getElementById(`${agentId}_doc_auto_commit`);
    const btn = document.getElementById(`${agentId}_doc_extract_btn`);
    const prevBox = document.getElementById(`${agentId}_doc_preview_box`);

    const autoCommit = Boolean(autoCommitEl && autoCommitEl.checked);
    const extractionHint = (hintInput?.value || '').trim();
    const lastState = this._lastStateByAgent[agentId] || {};
    const vaultedDocs = Array.isArray(lastState.documents) ? lastState.documents : [];
    const targetDoc = docRecordId > 0 ? vaultedDocs.find(d => Number(d.id) === Number(docRecordId)) : null;
    const scopeLabel = targetDoc
      ? targetDoc.title
      : (vaultedDocs.length > 0 ? `${vaultedDocs.length} vaulted document(s)` : 'agent vault');

    if (prevBox) {
      prevBox.style.display = 'block';
      prevBox.innerHTML = `<div style="font-size: 12px; color: #38bdf8;">⏳ Extracting tracking items from <strong>${studioEscapeHtml(scopeLabel)}</strong> via connected LLM...</div>`;
    }

    await runFleetAsyncAction({
      buttons: [btn],
      useStudioBanner: false,
      busyLabel: '⏳ Extracting Vault...',
      startToast: `⏳ Extracting items from ${scopeLabel}...`,
      errorPrefix: 'Vault extraction failed',
      onError: (err) => {
        if (prevBox) {
          prevBox.style.display = 'block';
          prevBox.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; font-size:12px; color:#fca5a5;">
              <div>✕ ${studioEscapeHtml(err.message)}</div>
              <button type="button" title="Select files to upload" class="btn btn-primary" onclick="document.getElementById('${studioEscapeHtml(agentId)}_doc_file_input')?.click()" style="padding:4px 10px; font-size:11px;">📂 Choose Files...</button>
            </div>
          `;
        }
      },
      onFinally: () => {
        if (btn) btn.textContent = '🧠 Extract Items';
      },
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/documents/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reextract_vault: true,
          doc_record_id: Number(docRecordId || 0),
          extraction_hint: extractionHint,
          auto_commit: autoCommit,
        }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not re-extract vaulted documents.');
      }
      this._handleExtractionSuccess(agentId, data, scopeLabel, Number(data.attachments_count || 1));
    });
  },

  _handleExtractionSuccess(agentId, data, labelNames, fallbackCount = 1) {
    const prevBox = document.getElementById(`${agentId}_doc_preview_box`);
    if (data.state) this.renderState(agentId, data.state);
    const ext = data.extraction || {};
    if (data.auto_committed) {
      delete this._pendingExtractionByAgent[agentId];
      if (prevBox) {
        prevBox.style.display = 'block';
        prevBox.innerHTML = `
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; flex-wrap:wrap; font-size:12px; color:#6ee7b7;">
            <div>✅ Auto-tracked <strong>${Number(data.committed_count || 0)}</strong> item(s) from <strong>${studioEscapeHtml(ext.filename || labelNames)}</strong> (${studioEscapeHtml(ext.model_used || ext.engine_used || 'LLM')}).</div>
            <button type="button" title="Dismiss message" class="btn" onclick="CustomAgentRuntime.dismissExtractedPreview('${studioEscapeHtml(agentId)}')" style="padding:2px 7px; font-size:11px; color:#94a3b8;">✕</button>
          </div>
          ${ext.document_summary ? `<div style="font-size:11.5px; color:#cbd5e1; margin-top:5px;">${studioEscapeHtml(ext.document_summary)}</div>` : ''}
        `;
      }
      if (typeof fetchBriefing === 'function') fetchBriefing();
      if (typeof showFleetToast === 'function') {
        showFleetToast(`✅ Extracted & tracked ${data.committed_count} item(s) from '${ext.filename || labelNames}'!`, false);
      }
    } else {
      this._pendingExtractionByAgent[agentId] = {
        doc_record_id: data.doc_record_id || 0,
        documents_count: Number(data.attachments_count || fallbackCount || 1),
        extraction: ext,
      };
      this.renderDocExtractionPreview(agentId);
      if (typeof showFleetToast === 'function') {
        showFleetToast(`📄 Extracted ${ext.items_count || 0} candidate item(s) — review & click Track Selected!`, false);
      }
    }
  },

  renderDocExtractionPreview(agentId) {
    const prevBox = document.getElementById(`${agentId}_doc_preview_box`);
    const pending = this._pendingExtractionByAgent[agentId];
    if (!prevBox || !pending || !pending.extraction) return;

    const ext = pending.extraction;
    const scen = ext.scenario_profile || {};
    const items = Array.isArray(ext.items) ? ext.items : [];

    if (items.length === 0) {
      prevBox.style.display = 'block';
      prevBox.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
          <div style="font-size:12px; color:#fbbf24;">⚠️ Document parsed (${studioEscapeHtml(ext.filename)}), but no structured tracking items were detected. Try adding an optional focus hint above.</div>
          <button type="button" title="Dismiss preview" class="btn" onclick="CustomAgentRuntime.dismissExtractedPreview('${studioEscapeHtml(agentId)}')" style="padding:2px 8px; font-size:11px; color:#94a3b8;">✕</button>
        </div>
      `;
      return;
    }

    const showSrcBadge = Number(pending.documents_count || 1) > 1;
    const rowsHtml = items.map((it, idx) => {
      const srcDoc = cleanStudioVaultFilename(it.source_document || it.extra_fields?.source_document || '');
      const extraPairs = formatCleanRecordMetadata(it.extra_fields, it.title || '', 5);
      return `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.07);">
          <td style="padding: 6px 6px; vertical-align: top;">
            <input type="checkbox" id="${studioEscapeHtml(agentId)}_ext_chk_${idx}" checked>
          </td>
          <td style="padding: 5px 6px;">
            <input type="text" id="${studioEscapeHtml(agentId)}_ext_title_${idx}" value="${studioEscapeHtml(it.title || '')}"
              style="width:100%; box-sizing:border-box; padding:5px 8px; border-radius:6px; border:1px solid rgba(56,189,248,0.32); background:rgba(15,23,42,0.85); color:#f8fafc; font-size:12px;">
            <div style="display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin-top:3px;">
              ${showSrcBadge && srcDoc ? `<span style="font-size:10px; padding:1px 6px; border-radius:999px; background:rgba(56,189,248,0.14); color:#7dd3fc;">📎 ${studioEscapeHtml(srcDoc)}</span>` : ''}
              ${extraPairs ? `<span style="font-size:10.5px; color:#94a3b8;">${studioEscapeHtml(extraPairs)}</span>` : ''}
            </div>
          </td>
          <td style="padding: 5px 6px; vertical-align: top;">
            <input type="date" id="${studioEscapeHtml(agentId)}_ext_due_${idx}" value="${studioEscapeHtml((it.due_date || '').slice(0, 10))}"
              style="padding:5px 7px; border-radius:6px; border:1px solid rgba(56,189,248,0.32); background:rgba(15,23,42,0.85); color:#f8fafc; font-size:11.5px;">
          </td>
          <td style="padding: 5px 6px; vertical-align: top;">
            <input type="number" step="any" id="${studioEscapeHtml(agentId)}_ext_num_${idx}" value="${it.numeric_value ? Number(it.numeric_value) : ''}" placeholder="0"
              style="width:95px; padding:5px 7px; border-radius:6px; border:1px solid rgba(56,189,248,0.32); background:rgba(15,23,42,0.85); color:#34d399; font-size:11.5px;">
          </td>
        </tr>
      `;
    }).join('');

    prevBox.style.display = 'block';
    prevBox.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:6px;">
        <div style="font-size:12px; color:#e2e8f0;">
          <span>${studioEscapeHtml(scen.icon || '📄')}</span>
          <strong style="color:#38bdf8;">${studioEscapeHtml(scen.title || 'Extracted Tracking Items')}</strong>
          <span style="color:#94a3b8; font-size:11px;"> • ${studioEscapeHtml(ext.filename)} • <code>${studioEscapeHtml(ext.model_used || ext.engine_used || 'LLM')}</code></span>
        </div>
        <div style="display:flex; gap:7px; align-items:center; flex-wrap:wrap;">
          <button type="button" title="Select new files from disk instead" class="btn btn-secondary" onclick="document.getElementById('${studioEscapeHtml(agentId)}_doc_file_input')?.click()" style="padding:4px 9px; font-size:11px; color:#7dd3fc; border-color:rgba(56,189,248,0.35);">📂 Choose New Files</button>
          <button type="button" title="Save selected extracted items into SQLite tracker" id="${studioEscapeHtml(agentId)}_doc_commit_btn" class="btn btn-primary" onclick="CustomAgentRuntime.commitExtractedItems('${studioEscapeHtml(agentId)}')" style="padding:5px 12px; font-size:11.5px; font-weight:700; background:linear-gradient(135deg,#10b981,#06b6d4); color:#041318;">✅ Track Selected (${items.length})</button>
          <button type="button" title="Dismiss extraction preview" class="btn" onclick="CustomAgentRuntime.dismissExtractedPreview('${studioEscapeHtml(agentId)}')" style="padding:4px 8px; font-size:11px; color:#94a3b8;">✕ Dismiss</button>
        </div>
      </div>
      ${ext.document_summary ? `<div style="font-size:11.5px; color:#cbd5e1; margin-bottom:8px;">${studioEscapeHtml(ext.document_summary)}</div>` : ''}
      <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:11.5px;">
          <thead>
            <tr style="text-align:left; color:#64748b; font-size:10px; text-transform:uppercase; border-bottom:1px solid rgba(255,255,255,0.08);">
              <th style="padding:4px 6px; width:26px;">✓</th>
              <th style="padding:4px 6px;">Extracted Item &amp; Metadata (Editable)</th>
              <th style="padding:4px 6px; width:135px;">Target / Expiry Date</th>
              <th style="padding:4px 6px; width:105px;">Amount / Value</th>
            </tr>
          </thead>
          <tbody>${rowsHtml}</tbody>
        </table>
      </div>
    `;
  },

  dismissExtractedPreview(agentId) {
    delete this._pendingExtractionByAgent[agentId];
    const prevBox = document.getElementById(`${agentId}_doc_preview_box`);
    if (prevBox) {
      prevBox.style.display = 'none';
      prevBox.innerHTML = '';
    }
  },

  async commitExtractedItems(agentId) {
    const pending = this._pendingExtractionByAgent[agentId];
    if (!pending || !pending.extraction) return;
    const rawItems = Array.isArray(pending.extraction.items) ? pending.extraction.items : [];
    const selectedItems = [];

    rawItems.forEach((orig, idx) => {
      const chk = document.getElementById(`${agentId}_ext_chk_${idx}`);
      if (chk && !chk.checked) return;
      const titleEl = document.getElementById(`${agentId}_ext_title_${idx}`);
      const dueEl = document.getElementById(`${agentId}_ext_due_${idx}`);
      const numEl = document.getElementById(`${agentId}_ext_num_${idx}`);
      const title = (titleEl?.value || orig.title || '').trim();
      if (!title) return;
      selectedItems.push({
        title,
        due_date: (dueEl?.value || '').trim(),
        numeric_value: numEl?.value !== '' ? Number(numEl?.value || 0) : 0,
        extra_fields: orig.extra_fields || {},
      });
    });

    if (selectedItems.length === 0) {
      if (typeof showFleetToast === 'function') showFleetToast('✕ Select at least one extracted item to track.', true);
      return;
    }

    await runFleetAsyncAction({
      buttons: [`${agentId}_doc_commit_btn`],
      useStudioBanner: false,
      busyLabel: '⏳ Saving...',
      errorPrefix: 'Commit failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/documents/commit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          doc_record_id: pending.doc_record_id || 0,
          source_document: pending.extraction.filename || '',
          items: selectedItems,
        }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not commit extracted items.');
      }

      const fname = pending.extraction.filename || 'document';
      this.dismissExtractedPreview(agentId);
      if (data.state) this.renderState(agentId, data.state);
      if (typeof fetchBriefing === 'function') fetchBriefing();
      showFleetToast(`✅ Tracked ${data.committed_count} item(s) from '${fname}' in SQLite!`, false);
    });
  },

  async submitRecord(agentId) {
    const panel = document.getElementById(`studio_panel_${agentId}`);
    if (!panel) return;

    const fields = {};
    const inputs = panel.querySelectorAll('[data-studio-field]');
    if (inputs.length > 0) {
      inputs.forEach(inp => {
        const k = inp.getAttribute('data-studio-field');
        if (k) fields[k] = (inp.value || '').trim();
      });
    } else {
      const legacy = document.getElementById(`${agentId}_quick_input`);
      if (legacy) fields.title = (legacy.value || '').trim();
    }

    const firstVal = fields.title || Object.values(fields).find(Boolean) || '';
    if (!firstVal) {
      if (typeof showFleetToast === 'function') showFleetToast('✕ Please fill in the primary item field first.', true);
      return;
    }
    if (!fields.title) fields.title = firstVal;

    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Saving...',
      errorPrefix: 'Error saving entry',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/records`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fields }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not save entry.');
      }
      inputs.forEach(inp => { inp.value = ''; });
      const legacy = document.getElementById(`${agentId}_quick_input`);
      if (legacy) legacy.value = '';

      if (data.state) this.renderState(agentId, data.state);
      showFleetToast(`✓ Saved '${fields.title}' to SQLite!`, false);
    });
  },

  filterHistory(agentId, query) {
    this._searchQueryByAgent[agentId] = String(query || '');
    const st = this._lastStateByAgent[agentId];
    if (st) {
      this.renderState(agentId, st, this._lastManifestByAgent[agentId]);
    }
  },

  editRecord(agentId, recordId) {
    this._editingRecordByAgent[agentId] = Number(recordId);
    const st = this._lastStateByAgent[agentId];
    if (st) {
      this.renderState(agentId, st, this._lastManifestByAgent[agentId]);
    }
  },

  cancelEditRecord(agentId) {
    delete this._editingRecordByAgent[agentId];
    const st = this._lastStateByAgent[agentId];
    if (st) {
      this.renderState(agentId, st, this._lastManifestByAgent[agentId]);
    }
  },

  async saveEditedRecord(agentId, recordId) {
    const titleEl = document.getElementById(`${agentId}_edit_title_${recordId}`);
    const dueEl = document.getElementById(`${agentId}_edit_due_${recordId}`);
    const numEl = document.getElementById(`${agentId}_edit_num_${recordId}`);
    const title = (titleEl?.value || '').trim();
    if (!title) {
      if (typeof showFleetToast === 'function') showFleetToast('✕ Title cannot be empty.', true);
      return;
    }
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Saving...',
      errorPrefix: 'Update failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/records/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          record_id: Number(recordId),
          title,
          due_date: (dueEl?.value || '').trim(),
          numeric_value: numEl?.value !== '' ? Number(numEl?.value || 0) : 0,
        }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Update failed.');
      }
      delete this._editingRecordByAgent[agentId];
      if (data.state) this.renderState(agentId, data.state);
      if (typeof fetchBriefing === 'function') fetchBriefing();
      showFleetToast(`✓ Updated '${title}'!`, false);
    });
  },

  async setRecordStatus(agentId, recordId, status) {
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Updating...',
      errorPrefix: 'Could not update record status',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/records/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_id: Number(recordId), status }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Status update failed.');
      }
      if (data.state) {
        this.renderState(agentId, data.state);
        if (typeof fetchBriefing === 'function') fetchBriefing();
      }
    });
  },

  async deleteRecord(agentId, recordId) {
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳...',
      errorPrefix: 'Could not delete record',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/records/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_id: recordId }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Delete failed.');
      }
      if (data.state) {
        this.renderState(agentId, data.state);
        if (typeof fetchBriefing === 'function') fetchBriefing();
      }
      showFleetToast('🗑️ Entry removed.', false);
    });
  },

  async toggleCheck(agentId, itemKey, checked, label = '') {
    await runFleetAsyncAction({
      useStudioBanner: false,
      includeActiveButton: false,
      errorPrefix: 'Checklist update failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/checklist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_key: itemKey, checked: Boolean(checked), label }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Checklist toggle failed.');
      }
      if (data.state) {
        this.renderState(agentId, data.state);
      }
    });
  },

  renderWorkflowInputPrompt(agentId, runId, pendingInputs, message = '', dryRun = false) {
    const box = document.getElementById(`${agentId}_workflow_input_prompt_box`);
    if (!box) return;
    const fields = Array.isArray(pendingInputs) ? pendingInputs : [];
    if (fields.length === 0) {
      box.style.display = 'none';
      box.innerHTML = '';
      return;
    }
    const safeAid = studioEscapeHtml(agentId);
    const safeRid = studioEscapeHtml(runId);
    const inputsHtml = fields.map((fld, idx) => {
      const key = String(fld.key || `input_${idx}`);
      const isSec = Boolean(fld.sensitive) || fld.type === 'secret';
      const inpType = isSec ? 'password' : (['date', 'number', 'url'].includes(fld.type) ? fld.type : 'text');
      const defVal = isSec ? '' : String(fld.default || '');
      return `
        <div style="display:flex; flex-direction:column; gap:3px; min-width:190px; flex:1;">
          <label style="font-size:11px; color:#fde68a; font-weight:700;">${studioEscapeHtml(fld.label || key)}${fld.required ? ' *' : ''}${isSec ? ' 🔒' : ''}</label>
          <input type="${inpType}" autocomplete="off" data-wf-input-key="${studioEscapeHtml(key)}" data-wf-secret="${isSec ? '1' : '0'}" value="${studioEscapeHtml(defVal)}" placeholder="${studioEscapeHtml(fld.prompt || key)}" style="padding:7px 10px; border-radius:6px; border:1px solid rgba(251,191,36,0.45); background:rgba(2,6,23,0.85); color:#f8fafc; font-size:12px;">
          <div style="font-size:10px; color:#cbd5e1;">${studioEscapeHtml(fld.prompt || '')}</div>
        </div>
      `;
    }).join('');
    box.style.display = 'block';
    box.innerHTML = `
      <div style="font-size:12px; font-weight:700; color:#fbbf24; margin-bottom:7px;">⏸️ ${studioEscapeHtml(message || 'Headless agent requires your input to continue:')}</div>
      <div style="display:flex; flex-wrap:wrap; gap:9px; align-items:flex-end; margin-bottom:8px;">${inputsHtml}</div>
      <div style="display:flex; gap:8px; justify-content:flex-end; flex-wrap:wrap;">
        <button type="button" title="Submit inputs and resume headless workflow execution" class="btn btn-primary" onclick="CustomAgentRuntime.resumeRecordedWorkflow('${safeAid}', '${safeRid}', ${Boolean(dryRun)})" style="padding:6px 14px; font-size:11.5px; font-weight:700;">▶ Submit Inputs &amp; Resume Headless</button>
      </div>
    `;
    setTimeout(() => { box.querySelector('input')?.focus(); }, 40);
  },

  async runRecordedWorkflow(agentId, dryRun = false) {
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: dryRun ? '⏳ Simulating Dry-Run...' : '⏳ Running Headless...',
      startToast: dryRun ? '⏳ Running dry-run simulation...' : '⏳ Running headless workflow...',
      errorPrefix: 'Headless workflow run failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/workflows/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, dry_run: Boolean(dryRun), inputs: {} }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Workflow execution failed.');
      }
      if (data.state) this.renderState(agentId, data.state);
      const r = data.result || {};
      if (r.status === 'waiting_for_input') {
        this.renderWorkflowInputPrompt(agentId, r.run_id || '', r.pending_inputs || [], r.message || '', Boolean(dryRun));
        showFleetToast(r.message || '⏸️ Agent paused awaiting user input.', false);
      } else {
        showFleetToast(r.message || '✅ Headless workflow completed.', r.health_status === 'warning');
      }
    });
  },

  async resumeRecordedWorkflow(agentId, runId, dryRun = false) {
    const box = document.getElementById(`${agentId}_workflow_input_prompt_box`);
    const inputs = {};
    if (box) {
      box.querySelectorAll('[data-wf-input-key]').forEach(el => {
        const k = el.getAttribute('data-wf-input-key');
        if (k) inputs[k] = el.value;
        if (el.getAttribute('data-wf-secret') === '1') {
          el.value = '';
        }
      });
    }
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Resuming Headless Run...',
      startToast: '⏳ Resuming headless workflow from checkpoint...',
      errorPrefix: 'Workflow resume failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/workflows/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ agent_id: agentId, run_id: runId, inputs, dry_run: Boolean(dryRun) }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Could not resume workflow.');
      }
      if (data.state) this.renderState(agentId, data.state);
      const r = data.result || {};
      if (r.status === 'waiting_for_input') {
        this.renderWorkflowInputPrompt(agentId, r.run_id || runId, r.pending_inputs || [], r.message || '', Boolean(dryRun));
        showFleetToast(r.message || '⏸️ Agent needs next input.', false);
      } else {
        showFleetToast(r.message || '✅ Headless workflow resumed & completed.', r.health_status === 'warning');
      }
    });
  },

  async runTask(agentId, taskName) {
    const targetTask = taskName || 'run_check';
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: `⏳ Running ${targetTask}...`,
      startToast: `⏳ Running '${targetTask}'...`,
      errorPrefix: `Run '${targetTask}' failed`,
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: targetTask }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Execution failed');
      }
      if (data.state) this.renderState(agentId, data.state);
      if (data.result?.status === 'waiting_for_input') {
        this.renderWorkflowInputPrompt(
          agentId,
          data.result.run_id || '',
          data.result.pending_inputs || [],
          data.result.message || '',
          Boolean(data.result.dry_run)
        );
      }
      showFleetToast(data.result?.message || `✓ Completed '${targetTask}'`, data.result?.health_status === 'warning');
    });
  },

  async runAiAnalyze(agentId) {
    const insightBox = document.getElementById(`${agentId}_insight_box`);
    if (insightBox) {
      insightBox.innerHTML = `<span style="color:#c4b5fd;">⏳ Synthesizing executive briefing with Antigravity LLM...</span>`;
    }
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Synthesizing Briefing...',
      startToast: '⏳ Synthesizing executive briefing with Antigravity LLM...',
      errorPrefix: 'AI briefing failed',
      onError: (err) => {
        if (insightBox) {
          insightBox.innerHTML = `<span style="color:#fca5a5;">✕ AI analysis failed: ${studioEscapeHtml(err.message)}</span>`;
        }
      },
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: 'ai_analyze' }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'AI analysis failed');
      }
      if (data.state) this.renderState(agentId, data.state);
      if (insightBox && !data.state?.latest_insight && data.result?.message) {
        insightBox.textContent = data.result.message;
      }
      showFleetToast('✨ Antigravity AI Briefing updated!', false);
    });
  },

  async renewRecord(agentId, recordId, cycle = '') {
    await runFleetAsyncAction({
      useStudioBanner: false,
      busyLabel: '⏳ Rolling Forward...',
      errorPrefix: 'Renewal failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/records/renew`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_id: Number(recordId), cycle: cycle || undefined }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Renewal roll-forward failed.');
      }
      if (data.state) this.renderState(agentId, data.state);
      if (typeof fetchBriefing === 'function') fetchBriefing();
      const ren = data.renewed || {};
      showFleetToast(`🔄 Rolled '${ren.title || 'item'}' forward (${ren.cycle}) → ${ren.next_due_date}!`, false);
    });
  },

  async scanInboxFolder(agentId) {
    const btn = document.getElementById(`${agentId}_scan_inbox_btn`);
    await runFleetAsyncAction({
      buttons: [btn],
      useStudioBanner: false,
      busyLabel: '⏳ Scanning...',
      startToast: '⏳ Scanning watched inbox folder...',
      errorPrefix: 'Inbox scan failed',
      onFinally: () => {
        if (btn) btn.textContent = '📥 Scan Inbox';
      },
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/documents/scan_inbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Inbox scan failed.');
      }
      if (data.state) this.renderState(agentId, data.state);
      if (typeof fetchBriefing === 'function') fetchBriefing();
      const sc = data.scan || {};
      if ((sc.ingested_documents_count || 0) > 0) {
        showFleetToast(`📥 Auto-ingested ${sc.ingested_documents_count} doc(s) (${sc.committed_items_count} item(s)) from ${sc.inbox_path}!`, false);
      } else {
        showFleetToast(`📥 Watched folder ready (${sc.inbox_path}) — drop PDFs/DOCX/XLSX/CSV/EML there anytime!`, false);
      }
    });
  },

  async sendAgentChat(agentId, presetPrompt = '') {
    const inp = document.getElementById(`${agentId}_chat_input`);
    const btn = document.getElementById(`${agentId}_chat_send_btn`);
    const chatLog = document.getElementById(`${agentId}_chat_log`);
    const message = String(presetPrompt || inp?.value || '').trim();
    if (!message) {
      inp?.focus();
      return;
    }
    if (!presetPrompt && inp) inp.value = '';
    let pendingDiv = null;
    if (chatLog) {
      pendingDiv = document.createElement('div');
      pendingDiv.style.cssText = 'font-size: 11.5px; color: #94a3b8; padding: 4px 8px;';
      pendingDiv.textContent = `⏳ Grounding answer for: "${message}"...`;
      chatLog.appendChild(pendingDiv);
      chatLog.scrollTop = chatLog.scrollHeight;
    }
    await runFleetAsyncAction({
      buttons: [btn],
      useStudioBanner: false,
      busyLabel: '⏳ Thinking...',
      errorPrefix: 'Agent chat failed',
      onError: (err) => {
        if (pendingDiv && pendingDiv.isConnected) {
          pendingDiv.style.color = '#fca5a5';
          pendingDiv.textContent = `✕ Chat error: ${err.message}`;
        }
      },
      onFinally: () => {
        if (btn) btn.textContent = '💬 Ask / Command';
      },
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry(`/api/fleet/agents/${encodeURIComponent(agentId)}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Agent chat error.');
      }
      if (data.state) this.renderState(agentId, data.state);
      if (data.mutation && typeof fetchBriefing === 'function') fetchBriefing();
    });
  },
};

function _pruneExpiredCompletedUndertakings(items, maxAgeHours = 24) {
  if (!Array.isArray(items)) return [];
  const cutoffMs = Date.now() - Math.max(1, Number(maxAgeHours) || 24) * 3600 * 1000;
  return items.filter((item) => {
    if (!item || typeof item !== 'object') return false;
    const status = String(item.status || '').toLowerCase();
    if (status !== 'completed' && status !== 'done') return true;
    const rawTs = item.completed_at || item.updated_at || item.created_at || '';
    const parsedMs = rawTs ? Date.parse(String(rawTs)) : NaN;
    if (Number.isNaN(parsedMs)) return true;
    return parsedMs >= cutoffMs;
  });
}

function toggleEvolveHeaderPopover(agentId, event) {
  if (event && typeof event.stopPropagation === 'function') {
    event.stopPropagation();
  }
  const popId = agentId ? `${agentId}_evolve_header_popover` : 'studioEvolveHeaderPopover';
  const popEl = document.getElementById(popId) || document.getElementById('studioEvolveHeaderPopover');
  if (!popEl) {
    if (agentId) openEvolveAgentModal(agentId);
    return false;
  }
  const isOpen = popEl.style.display === 'block' || popEl.style.display === 'flex';
  popEl.style.display = isOpen ? 'none' : 'block';
  return !isOpen;
}

function closeEvolveHeaderPopover(agentId) {
  const popId = agentId ? `${agentId}_evolve_header_popover` : 'studioEvolveHeaderPopover';
  const popEl = document.getElementById(popId) || document.getElementById('studioEvolveHeaderPopover');
  if (popEl) {
    popEl.style.display = 'none';
  }
}

// ============================================================================
// Multimodal Activity + Voice Narration Recorder -> Requirements -> Sandbox -> Live
// ============================================================================

const StudioActivityRecorder = {
  _sessionId: '',
  _captureToken: '',
  _bookmarkletJs: '',
  _isRecording: false,
  _startedAtMs: 0,
  _pollTimer: null,
  _mediaStream: null,
  _mediaRecorder: null,
  _audioChunks: [],
  _speechRec: null,
  _lastDraft: null,
  _lastSandboxReport: null,

  init() {
    this.loadSavedSessions();
    this.refreshStatusOnce();
  },

  resetUi() {
    this.cleanup();
    this._sessionId = '';
    this._captureToken = '';
    this._bookmarkletJs = '';
    this._lastDraft = null;
    this._lastSandboxReport = null;
    this._setBadge('Idle', '#94a3b8');
    const itBadge = document.getElementById('studioRecIterationBadge');
    if (itBadge) { itBadge.style.display = 'none'; itBadge.textContent = 'v1'; }
    const evCnt = document.getElementById('studioRecEventCount');
    if (evCnt) evCnt.textContent = '0';
    const auCnt = document.getElementById('studioRecAudioCount');
    if (auCnt) auCnt.textContent = '0';
    const evFeed = document.getElementById('studioRecLiveFeed');
    if (evFeed) evFeed.textContent = 'No captured screen steps yet.';
    const auFeed = document.getElementById('studioRecAudioFeed');
    if (auFeed) auFeed.textContent = 'Speak aloud while recording to explain intent & inputs...';
    ['studioRecRequirementsBox', 'studioRecUnitTestBox', 'studioRecSandboxTheater', 'studioRecIteratePublishBar'].forEach(id => {
      const el = document.getElementById(id);
      if (el) { el.style.display = 'none'; el.innerHTML = el.id === 'studioRecIteratePublishBar' ? el.innerHTML : ''; }
    });
    const chk = document.getElementById('studioRecApproveChk');
    if (chk) chk.checked = false;
  },

  _setBadge(text, color = '#94a3b8') {
    const b = document.getElementById('studioRecStatusBadge');
    if (b) {
      b.textContent = text;
      b.style.color = color;
      b.style.borderColor = color;
    }
  },

  _releaseMicAndTimers() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
    if (this._speechRec) {
      try { this._speechRec.onend = null; this._speechRec.stop(); } catch (_) {}
      this._speechRec = null;
    }
    if (this._mediaRecorder && this._mediaRecorder.state !== 'inactive') {
      try { this._mediaRecorder.stop(); } catch (_) {}
    }
    this._mediaRecorder = null;
    if (this._mediaStream) {
      try { this._mediaStream.getTracks().forEach(t => t.stop()); } catch (_) {}
      this._mediaStream = null;
    }
  },

  cleanup() {
    this._isRecording = false;
    this._releaseMicAndTimers();
  },

  async loadSavedSessions() {
    try {
      const res = await fetch('/api/studio/recorder/sessions?limit=20');
      if (!res.ok) return;
      const data = await res.json();
      const list = Array.isArray(data.sessions) ? data.sessions : [];
      const sel = document.getElementById('studioRecSavedSelect');
      if (!sel) return;
      sel.innerHTML = `<option value="">Saved Recordings (${list.length})</option>` + list.map(s =>
        `<option value="${studioEscapeHtml(s.session_id)}">${studioEscapeHtml(s.label || s.session_id)} (${s.events_count || 0} steps • ${s.lifecycle_status || 'recorded'})</option>`
      ).join('');
      if (this._sessionId) sel.value = this._sessionId;
    } catch (_) {}
  },

  selectSavedSession(sid) {
    if (!sid) return;
    this._sessionId = sid;
    studioCurrentRecordingId = sid;
    showFleetToast(`📂 Selected recording '${sid}' — click Build Req Doc & Flow next.`, false);
  },

  async start() {
    const mode = document.getElementById('recorderModeSelect')?.value || 'browser';
    const startUrl = (document.getElementById('recorderStartUrlInput')?.value || '').trim();
    const launchBrowser = Boolean(document.getElementById('recorderLaunchBrowserChk')?.checked);
    const recordAudio = Boolean(document.getElementById('recorderAudioNarrationChk')?.checked);
    const label = (document.getElementById('newAgentName')?.value || '').trim();

    this._audioChunks = [];
    this._startedAtMs = Date.now();

    if (recordAudio) {
      await this._startAudioCapture();
    }

    await runFleetAsyncAction({
      buttons: ['btnStudioRecStart'],
      useStudioBanner: false,
      busyLabel: '⏳ Starting Recorder...',
      errorPrefix: 'Could not start recording',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, start_url: startUrl, launch_browser: launchBrowser, record_audio: recordAudio, label }),
      });
      if (!res.ok || data.status === 'error') {
        this._releaseMicAndTimers();
        throw new Error(data.message || 'Start recording failed.');
      }
      this._sessionId = data.session_id || '';
      this._captureToken = data.capture_token || '';
      this._bookmarkletJs = data.bookmarklet_js || '';
      this._isRecording = true;
      studioCurrentRecordingId = this._sessionId;
      this._setBadge(`🔴 Recording (${mode})`, '#f87171');
      if (this._pollTimer) clearInterval(this._pollTimer);
      this._pollTimer = setInterval(() => this.refreshStatusOnce(), 1500);
      await this.refreshStatusOnce();
      showFleetToast(data.message || '🔴 Recording started!', false);
    });
  },

  async _startAudioCapture() {
    if (navigator.mediaDevices && typeof navigator.mediaDevices.getUserMedia === 'function') {
      try {
        this._mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        if (typeof MediaRecorder !== 'undefined') {
          this._mediaRecorder = new MediaRecorder(this._mediaStream);
          this._mediaRecorder.ondataavailable = (ev) => {
            if (ev.data && ev.data.size > 0) this._audioChunks.push(ev.data);
          };
          this._mediaRecorder.start(1000);
        }
      } catch (_) {}
    }
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      try {
        const rec = new SpeechRec();
        rec.continuous = true;
        rec.interimResults = false;
        rec.lang = 'en-US';
        rec.onresult = (event) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
              const transcript = String(event.results[i][0]?.transcript || '').trim();
              if (transcript) {
                const offsetSec = Number(((Date.now() - this._startedAtMs) / 1000).toFixed(2));
                this._postAudioSegment(transcript, offsetSec);
              }
            }
          }
        };
        rec.onend = () => {
          if (this._isRecording && this._speechRec === rec) {
            try { rec.start(); } catch (_) {}
          }
        };
        rec.start();
        this._speechRec = rec;
      } catch (_) {}
    }
  },

  async _postAudioSegment(transcript, offsetSec = 0) {
    if (!transcript) return;
    try {
      await fetch('/api/studio/recorder/audio_segment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this._sessionId || undefined,
          capture_token: this._captureToken || undefined,
          offset_sec: offsetSec,
          transcript,
          is_final: true,
        }),
      });
      await this.refreshStatusOnce();
    } catch (_) {}
  },

  async addManualNarration() {
    const inp = document.getElementById('studioRecManualNarrationInput');
    const txt = (inp?.value || '').trim();
    if (!txt) return;
    const offsetSec = this._startedAtMs ? Number(((Date.now() - this._startedAtMs) / 1000).toFixed(2)) : 0;
    await this._postAudioSegment(txt, offsetSec);
    if (inp) inp.value = '';
  },

  async _collectAudioBlobBase64() {
    if (!this._mediaRecorder) return { audio_base64: '', audio_mime: 'audio/webm' };
    const rec = this._mediaRecorder;
    const mime = rec.mimeType || 'audio/webm';
    if (rec.state !== 'inactive') {
      await new Promise(resolve => {
        rec.onstop = resolve;
        try { rec.stop(); } catch (_) { resolve(); }
      });
    }
    if (!this._audioChunks.length) return { audio_base64: '', audio_mime: mime };
    const blob = new Blob(this._audioChunks, { type: mime });
    const dataUrl = await new Promise(resolve => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(String(reader.result || ''));
      reader.readAsDataURL(blob);
    });
    return { audio_base64: dataUrl, audio_mime: mime };
  },

  async stop() {
    const audioPayload = await this._collectAudioBlobBase64();
    this._isRecording = false;
    this._releaseMicAndTimers();
    await runFleetAsyncAction({
      buttons: ['btnStudioRecStop'],
      useStudioBanner: false,
      busyLabel: '⏳ Saving Recording...',
      errorPrefix: 'Stop recording failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this._sessionId || undefined,
          audio_base64: audioPayload.audio_base64 || '',
          audio_mime: audioPayload.audio_mime || 'audio/webm',
        }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Stop recording failed.');
      }
      this._sessionId = data.session_id || this._sessionId;
      studioCurrentRecordingId = this._sessionId;
      this._setBadge(`Saved (${data.events_count || 0} steps • ${data.audio_segments_count || 0} audio)`, '#34d399');
      await this.loadSavedSessions();
      showFleetToast(`⏹️ Saved ${data.events_count || 0} screen steps & ${data.audio_segments_count || 0} voice notes!`, false);
    });
  },

  async markDynamicInput() {
    const label = window.prompt('Input Field Label (the live headless agent will ask the user for this):', 'Policy Number');
    if (!label) return;
    const promptQ = window.prompt('Question prompt to ask user at runtime:', `Enter ${label}:`) || `Enter ${label}:`;
    const isSensitive = window.confirm('Is this input sensitive (Password / OTP / Secret)? Click OK for Yes, Cancel for No.');
    const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/mark_input', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: this._sessionId || undefined,
        label,
        prompt_question: promptQ,
        sensitive: isSensitive,
        input_type: isSensitive ? 'secret' : 'text',
        required: true,
      }),
    });
    if (!res.ok || data.status === 'error') {
      showFleetToast(`✕ ${data.message || 'Could not mark input.'}`, true);
      return;
    }
    await this.refreshStatusOnce();
    showFleetToast(`❓ Marked dynamic input '${label}'!`, false);
  },

  copyBookmarklet() {
    if (!this._bookmarkletJs) {
      showFleetToast('Start a Browser recording first to generate a session bookmarklet.', true);
      return;
    }
    navigator.clipboard?.writeText(this._bookmarkletJs).then(() => {
      showFleetToast('🔖 Bookmarklet copied! Paste/run in your target browser tab to record.', false);
    }).catch(() => {
      window.prompt('Copy Bookmarklet:', this._bookmarkletJs);
    });
  },

  async refreshStatusOnce() {
    try {
      const res = await fetch('/api/studio/recorder/status?limit=25');
      if (!res.ok) return;
      const st = await res.json();
      if (!st.active) return;
      const evCnt = document.getElementById('studioRecEventCount');
      if (evCnt) evCnt.textContent = String(st.events_count || 0);
      const auCnt = document.getElementById('studioRecAudioCount');
      if (auCnt) auCnt.textContent = String(st.audio_segments_count || 0);
      const evFeed = document.getElementById('studioRecLiveFeed');
      if (evFeed && Array.isArray(st.recent_events) && st.recent_events.length > 0) {
        evFeed.innerHTML = st.recent_events.map(e =>
          `<div>[${studioEscapeHtml(String(e.offset_sec || 0))}s] <strong>${studioEscapeHtml(e.action)}</strong> ${studioEscapeHtml(e.title || e.url || e.locators?.text || '')}</div>`
        ).join('');
        evFeed.scrollTop = evFeed.scrollHeight;
      }
      const auFeed = document.getElementById('studioRecAudioFeed');
      if (auFeed && Array.isArray(st.audio_segments) && st.audio_segments.length > 0) {
        auFeed.innerHTML = st.audio_segments.map(a =>
          `<div>[${studioEscapeHtml(String(a.offset_sec || 0))}s] "${studioEscapeHtml(a.transcript)}"</div>`
        ).join('');
        auFeed.scrollTop = auFeed.scrollHeight;
      }
    } catch (_) {}
  },

  _renderDraftBoxes(payload) {
    this._lastDraft = payload;
    const req = payload.requirements_doc || {};
    const spec = payload.spec || {};
    if (spec && spec.workflow_ir) {
      studioCurrentWorkflowIr = spec.workflow_ir;
      studioCurrentRequirementsDoc = req;
      studioCurrentRecordingId = this._sessionId;
    }
    const itBadge = document.getElementById('studioRecIterationBadge');
    if (itBadge) {
      itBadge.style.display = 'inline-block';
      itBadge.textContent = `v${payload.iteration_version || req.version || 1}`;
    }
    const reqBox = document.getElementById('studioRecRequirementsBox');
    if (reqBox) {
      const frCount = (req.functional_requirements || []).length;
      const inpCount = (req.input_schema || []).length;
      const healNotes = Array.isArray(payload.healing_actions) && payload.healing_actions.length
        ? `<div style="margin-top:5px;color:#fbbf24;">🔧 Healing applied: ${payload.healing_actions.map(studioEscapeHtml).join(' • ')}</div>`
        : '';
      reqBox.style.display = 'block';
      reqBox.innerHTML = `
        <div style="font-weight:700;color:#38bdf8;margin-bottom:4px;">📋 ${studioEscapeHtml(req.title || spec.name || 'Requirements Document')} (v${payload.iteration_version || 1})</div>
        <div style="color:#cbd5e1;margin-bottom:6px;">${studioEscapeHtml(req.summary || '')} • <strong>${frCount}</strong> FRs • <strong>${inpCount}</strong> runtime input(s)</div>
        ${healNotes}
        <details style="margin-top:4px;"><summary style="cursor:pointer;color:#7dd3fc;">View Mermaid Process Flow &amp; Trace Matrix</summary>
          <pre style="margin-top:6px;padding:8px;border-radius:6px;background:rgba(15,23,42,0.9);overflow-x:auto;font-size:10.5px;color:#a5f3fc;">${studioEscapeHtml(req.mermaid_process_flow || '')}</pre>
        </details>
      `;
    }
    if (payload.unit_test_report) {
      this._renderUnitTestReport(payload.unit_test_report);
    }
    const iterBar = document.getElementById('studioRecIteratePublishBar');
    if (iterBar) iterBar.style.display = 'block';
  },

  _renderUnitTestReport(rep) {
    const box = document.getElementById('studioRecUnitTestBox');
    if (!box || !rep) return;
    const ok = rep.status === 'passed';
    box.style.display = 'block';
    box.style.borderColor = ok ? 'rgba(52, 211, 153, 0.45)' : 'rgba(248, 113, 113, 0.45)';
    box.innerHTML = `
      <div style="font-weight:700;color:${ok ? '#34d399' : '#fca5a5'};">${ok ? '✅' : '✕'} Isolated Pytest Suite: ${rep.passed || 0}/${rep.total || 0} Passed (${rep.duration_ms || 0} ms)</div>
      <details style="margin-top:4px;"><summary style="cursor:pointer;color:#d8b4fe;">Test Runner Output</summary>
        <pre style="margin-top:4px;font-size:10.5px;white-space:pre-wrap;color:#e2e8f0;">${studioEscapeHtml(rep.output || '')}</pre>
      </details>
    `;
  },

  async convertToRequirements() {
    if (!this._sessionId) {
      showFleetToast('Record or select a saved recording first.', true);
      return;
    }
    await runFleetAsyncAction({
      buttons: ['btnStudioRecConvert'],
      useStudioBanner: false,
      busyLabel: '⏳ Fusing Audio & Screen...',
      errorPrefix: 'Synthesis failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/convert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this._sessionId,
          label: (document.getElementById('newAgentName')?.value || '').trim(),
          use_llm: true,
          auto_run_tests: true,
        }),
      });
      if (!res.ok || data.status === 'error') {
        throw new Error(data.message || 'Requirements synthesis failed.');
      }
      this._renderDraftBoxes(data);
      if (data.spec) populateWizardFromSpec(data.spec);
      this._setBadge('Requirements & Tests Ready', '#38bdf8');
      showFleetToast('🧠 Requirements Document, Process Flow & Unit Tests generated!', false);
    });
  },

  async runUnitTests() {
    if (!this._sessionId) {
      showFleetToast('Record & synthesize a session first.', true);
      return;
    }
    await runFleetAsyncAction({
      buttons: ['btnStudioRecRunTests'],
      useStudioBanner: false,
      busyLabel: '⏳ Running Pytest Suite...',
      errorPrefix: 'Unit test execution failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/run_tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: this._sessionId }),
      });
      if (!res.ok) throw new Error(data.message || 'Pytest run failed.');
      this._renderUnitTestReport(data);
      showFleetToast(`🧪 Pytest: ${data.passed || 0}/${data.total || 0} passed!`, data.status !== 'passed');
    });
  },

  async runVisibleSandbox(inputs = {}) {
    if (!this._sessionId) {
      showFleetToast('Record & synthesize a session first.', true);
      return;
    }
    await runFleetAsyncAction({
      buttons: ['btnStudioRecSandbox'],
      useStudioBanner: false,
      busyLabel: '⏳ Running Visible Sandbox...',
      errorPrefix: 'Sandbox dry-run failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/sandbox_run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: this._sessionId, inputs, visible_browser: true }),
      });
      if (!res.ok || data.status === 'error') throw new Error(data.message || 'Sandbox error.');
      this._lastSandboxReport = data;
      const box = document.getElementById('studioRecSandboxTheater');
      const iterBar = document.getElementById('studioRecIteratePublishBar');
      if (iterBar) iterBar.style.display = 'block';
      if (!box) return;
      box.style.display = 'block';

      if (data.status === 'waiting_for_input') {
        const fieldsHtml = (data.pending_inputs || []).map(f => {
          const isSec = Boolean(f.sensitive) || f.type === 'secret';
          return `<label style="display:flex;flex-direction:column;gap:2px;font-size:11px;min-width:170px;flex:1;">
            <span style="color:#fde68a;font-weight:700;">${studioEscapeHtml(f.label || f.key)}${isSec ? ' 🔒' : ''}</span>
            <input type="${isSec ? 'password' : 'text'}" data-sbx-input-key="${studioEscapeHtml(f.key)}" value="${isSec ? '' : studioEscapeHtml(f.default || '')}" placeholder="${studioEscapeHtml(f.prompt || '')}" style="padding:5px 8px;border-radius:6px;border:1px solid rgba(251,191,36,0.45);background:rgba(2,6,23,0.9);color:#fff;font-size:11.5px;">
          </label>`;
        }).join('');
        box.innerHTML = `
          <div style="font-weight:700;color:#fbbf24;margin-bottom:6px;">⏸️ Visible Sandbox Input Check — Agent Asking User Before Replay:</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;">${fieldsHtml}</div>
          <button type="button" title="Submit test values into visible sandbox dry-run" class="btn btn-primary" onclick="StudioActivityRecorder.submitSandboxInputs()" style="padding:5px 12px;font-size:11px;font-weight:700;">▶ Continue Visible Sandbox Dry-Run</button>
        `;
        return;
      }

      const stepsHtml = (data.steps || []).map((s, idx) => {
        const col = s.status === 'failed' ? '#f87171' : (s.status === 'healed' ? '#fbbf24' : '#34d399');
        return `<div style="padding:4px 8px;border-left:3px solid ${col};margin-bottom:4px;background:rgba(2,6,23,0.5);">
          <strong style="color:${col};">#${idx + 1} [${studioEscapeHtml(s.status?.toUpperCase())}]</strong> ${studioEscapeHtml(s.description || s.step_id)}
          ${s.tier ? `<span style="color:#94a3b8;font-size:10px;"> (${studioEscapeHtml(s.tier)})</span>` : ''}
          ${s.reason ? `<div style="color:#fca5a5;font-size:10.5px;">Reason: ${studioEscapeHtml(s.reason)}</div>` : ''}
        </div>`;
      }).join('');
      const ok = data.failed_count === 0;
      box.innerHTML = `
        <div style="font-weight:700;color:${ok ? '#34d399' : '#fca5a5'};margin-bottom:6px;">👁️ Visible Sandbox (${studioEscapeHtml(data.visible_mode)}) — ${data.passed_count}/${data.total_steps} Passed • ${data.failed_count} Failed</div>
        ${stepsHtml}
      `;
      this._setBadge(ok ? 'Sandbox Passed' : 'Needs Self-Healing', ok ? '#34d399' : '#fbbf24');
      showFleetToast(ok ? '✅ Visible Sandbox Dry-Run passed!' : '⚠️ Sandbox captured failure(s) — click Self-Heal & Re-Iterate!', !ok);
    });
  },

  submitSandboxInputs() {
    const box = document.getElementById('studioRecSandboxTheater');
    const inputs = {};
    box?.querySelectorAll('[data-sbx-input-key]').forEach(el => {
      const k = el.getAttribute('data-sbx-input-key');
      if (k) inputs[k] = el.value;
    });
    this.runVisibleSandbox(inputs);
  },

  speakFeedback() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      document.getElementById('studioRecFeedbackInput')?.focus();
      showFleetToast('Type your correction directly in the feedback box.', false);
      return;
    }
    const rec = new SpeechRec();
    rec.lang = 'en-US';
    rec.onresult = (e) => {
      const txt = e.results?.[0]?.[0]?.transcript || '';
      const inp = document.getElementById('studioRecFeedbackInput');
      if (inp && txt) inp.value = txt;
      showFleetToast('🎙️ Captured spoken correction — click Self-Heal & Re-Iterate!', false);
    };
    rec.start();
  },

  async applyHealAndIterate() {
    if (!this._sessionId) return;
    const feedback = (document.getElementById('studioRecFeedbackInput')?.value || '').trim();
    const failures = this._lastSandboxReport?.failures || undefined;
    await runFleetAsyncAction({
      buttons: ['btnStudioRecHeal'],
      useStudioBanner: false,
      busyLabel: '⏳ Self-Healing & Iterating...',
      errorPrefix: 'Self-healing failed',
    }, async () => {
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/heal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this._sessionId,
          failures,
          user_audio_feedback: feedback,
          rerun_tests: true,
        }),
      });
      if (!res.ok || data.status === 'error') throw new Error(data.message || 'Self-healing error.');
      this._renderDraftBoxes(data);
      if (data.spec) populateWizardFromSpec(data.spec);
      const inp = document.getElementById('studioRecFeedbackInput');
      if (inp) inp.value = '';
      showFleetToast(`🔧 Self-healed to v${data.iteration_version}! Re-run Visible Sandbox to verify.`, false);
    });
  },

  loadIntoStudioWizard() {
    if (this._lastDraft?.spec) {
      populateWizardFromSpec(this._lastDraft.spec);
      goToWizardStep(4);
    } else {
      showFleetToast('Build Requirements Doc & Flow first before inspecting Steps 1-4.', true);
    }
  },

  async publishLiveAgent() {
    if (!this._sessionId) return;
    const approved = Boolean(document.getElementById('studioRecApproveChk')?.checked);
    if (!approved) {
      showFleetToast('Please check "I approve the Requirements Doc & Visible Sandbox Run" before publishing.', true);
      return;
    }
    await runFleetAsyncAction({
      buttons: ['btnStudioRecPublish'],
      useStudioBanner: false,
      busyLabel: '⏳ Publishing Live Headless Agent...',
      errorPrefix: 'Publish failed',
    }, async () => {
      const overrides = buildCurrentWizardSpecPayload();
      const { res, data } = await studioFetchJsonWithRetry('/api/studio/recorder/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: this._sessionId, user_approved: true, overrides }),
      });
      if (!res.ok || data.status === 'error') throw new Error(data.message || 'Publish failed.');
      newlyCreatedAgentId = data.agent_id;
      const nav = window.FleetNavigator || (typeof FleetNavigator !== 'undefined' ? FleetNavigator : null);
      if (nav && typeof nav.fetchFleetData === 'function') await nav.fetchFleetData();
      if (typeof fetchSchedules === 'function') fetchSchedules();
      if (typeof loadSettingsData === 'function') loadSettingsData();
      showFleetToast(data.message || '🚀 Published Live Headless Agent!', false);
      openNewlyCreatedAgent();
    });
  },
};

window.StudioActivityRecorder = StudioActivityRecorder;
window.CustomAgentRuntime = CustomAgentRuntime;
window._pruneExpiredCompletedUndertakings = _pruneExpiredCompletedUndertakings;
window.toggleEvolveHeaderPopover = toggleEvolveHeaderPopover;
window.closeEvolveHeaderPopover = closeEvolveHeaderPopover;
window.deployStudioSquad = deployStudioSquad;
window.openEvolveAgentModal = openEvolveAgentModal;
window.rollbackCurrentAgentRevision = rollbackCurrentAgentRevision;
window.deepBuildWithAntigravity = deepBuildWithAntigravity;
window.cloneCustomAgentFromUI = cloneCustomAgentFromUI;
window.exportAgentPackFromUI = exportAgentPackFromUI;
window.exportCurrentWizardSpecOrAgent = exportCurrentWizardSpecOrAgent;
window.triggerImportAgentPackFile = triggerImportAgentPackFile;
window.handleImportAgentPackFile = handleImportAgentPackFile;
window.analyzeStudioDocumentForWizard = analyzeStudioDocumentForWizard;
window.handleStudioWizardDocDrop = handleStudioWizardDocDrop;
window.toggleStudioStagedDocItem = toggleStudioStagedDocItem;
window.clearStudioStagedDocExtraction = clearStudioStagedDocExtraction;
window.clearStudioStagedDocument = clearStudioStagedDocExtraction;
window.normalizeLegacyRagResponse = normalizeLegacyRagResponse;
window.formatStudioAgentResponseHtml = formatStudioAgentResponseHtml;
