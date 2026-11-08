// --- PC Performance Optimizer ---
    async function fetchOptimizerDiagnostics() {
      const refreshBtn = document.getElementById('btnRefreshOpt');
      if (refreshBtn) refreshBtn.innerText = '🔄 Scanning...';
      try {
        const res = await fetch('/api/optimizer/diagnostics');
        const data = await res.json();
        if (data.status !== 'success') return;

        // Health Score badge
        const scoreBadge = document.getElementById('optimizerScoreBadge');
        if (scoreBadge) {
          scoreBadge.innerText = `Health Score: ${data.health_score}/100 (${data.score_status})`;
          if (data.health_score >= 85) {
            scoreBadge.style.color = 'var(--accent-green)';
            scoreBadge.style.background = 'rgba(16, 185, 129, 0.15)';
          } else if (data.health_score >= 70) {
            scoreBadge.style.color = 'var(--accent-cyan)';
            scoreBadge.style.background = 'rgba(0, 242, 254, 0.15)';
          } else {
            scoreBadge.style.color = 'var(--accent-pink)';
            scoreBadge.style.background = 'rgba(244, 63, 94, 0.15)';
          }
        }

        // Quick Overview Card
        const qRam = document.getElementById('quickOptRam');
        if (qRam && data.memory) qRam.innerText = `${data.memory.percent_used}%`;
        const qDisk = document.getElementById('quickOptDisk');
        if (qDisk && data.disk) qDisk.innerText = `${data.disk.free_gb} GB`;
        const qTemp = document.getElementById('quickOptTemp');
        if (qTemp && data.temp_bloat) qTemp.innerText = `${data.temp_bloat.size_mb} MB`;
        const qAdvice = document.getElementById('quickOptAdvice');
        if (qAdvice) {
          if (data.recommendations && data.recommendations.length > 0) {
            qAdvice.innerText = `${data.recommendations.length} action(s) available to boost speed.`;
          } else {
            qAdvice.innerText = 'System is tuned & operating optimally.';
          }
        }

        // Diagnostic Grid Cards
        // 1. RAM
        if (data.memory) {
          const ramBadge = document.getElementById('optRamBadge');
          if (ramBadge) ramBadge.innerText = `${data.memory.percent_used}%`;
          const ramUsage = document.getElementById('optRamUsage');
          if (ramUsage) ramUsage.innerText = `${data.memory.used_gb} GB / ${data.memory.total_gb} GB`;
          const ramBar = document.getElementById('optRamBar');
          if (ramBar) ramBar.style.width = `${Math.min(100, data.memory.percent_used)}%`;
          const ramAvail = document.getElementById('optRamAvail');
          if (ramAvail) ramAvail.innerText = `Available: ${data.memory.avail_gb} GB`;
        }

        // 2. Disk
        if (data.disk) {
          const diskBadge = document.getElementById('optDiskBadge');
          if (diskBadge) diskBadge.innerText = `${Math.round(100 - data.disk.percent_used)}% Free`;
          const diskUsage = document.getElementById('optDiskUsage');
          if (diskUsage) diskUsage.innerText = `${data.disk.free_gb} GB Free`;
          const diskBar = document.getElementById('optDiskBar');
          if (diskBar) diskBar.style.width = `${Math.min(100, data.disk.percent_used)}%`;
          const diskTotal = document.getElementById('optDiskTotal');
          if (diskTotal) diskTotal.innerText = `Total: ${data.disk.total_gb} GB`;
          const diskPercent = document.getElementById('optDiskPercent');
          if (diskPercent) diskPercent.innerText = `${data.disk.percent_used}% Used`;
        }

        // 3. Temp Bloat
        if (data.temp_bloat) {
          const tempBadge = document.getElementById('optTempBadge');
          if (tempBadge) tempBadge.innerText = `${data.temp_bloat.size_mb} MB`;
          const tempSize = document.getElementById('optTempSize');
          if (tempSize) tempSize.innerText = `${data.temp_bloat.size_mb} MB Junk`;
          const tempFiles = document.getElementById('optTempFiles');
          if (tempFiles) tempFiles.innerText = `${data.temp_bloat.file_count} files in Windows Temp`;
        }

        // 4. Startup Apps
        const startupBadge = document.getElementById('optStartupBadge');
        if (startupBadge) startupBadge.innerText = `${data.startup_apps_count || 0} Apps`;
        const startupCount = document.getElementById('optStartupCount');
        if (startupCount) startupCount.innerText = `${data.startup_apps_count || 0} Active on Boot`;

        // 5. OS & Software Upgrades
        if (data.upgrades) {
          renderOptimizerUpgrades(data.upgrades);
        }

        // Render Recommendations
        const recomCount = document.getElementById('optRecomCount');
        if (recomCount) recomCount.innerText = `${data.recommendations ? data.recommendations.length : 0} Actions Available`;
        renderOptimizerRecommendations(data.recommendations || []);

        // Render Top Processes
        const procCount = document.getElementById('optProcessCount');
        if (procCount) procCount.innerText = `${data.top_processes ? data.top_processes.length : 0} Processes`;
        renderOptimizerProcesses(data.top_processes || []);

      } catch (e) {
        console.error('Error fetching optimizer diagnostics:', e);
      } finally {
        if (refreshBtn) refreshBtn.innerText = '🔄 Rescan System';
      }
    }

    function renderOptimizerUpgrades(upg) {
      if (!upg) return;
      const osInfo = upg.os_info || {};
      const osUpdates = Array.isArray(upg.os_updates)
        ? upg.os_updates
        : (Array.isArray(osInfo.pending_os_updates) ? osInfo.pending_os_updates : []);
      const swPackages = Array.isArray(upg.software_upgrades)
        ? upg.software_upgrades
        : (upg.software_upgrades && Array.isArray(upg.software_upgrades.packages) ? upg.software_upgrades.packages : []);
      const policy = upg.policy || {};
      const totalPending = Number(upg.total_pending_count !== undefined ? upg.total_pending_count : (upg.total_pending || (osUpdates.length + swPackages.length)));
      const secCount = Number(upg.security_critical_count !== undefined ? upg.security_critical_count : (upg.security_or_critical_count || 0));
      const osDisplayName = osInfo.display_version || osInfo.os_name || osInfo.os_family || 'OS';
      const osBuildStr = osInfo.build_number || osInfo.os_build || osInfo.os_version || 'Current';

      // Metric Card
      const upgBadge = document.getElementById('optUpgradesBadge');
      if (upgBadge) {
        if (totalPending === 0 && !osInfo.pending_reboot) {
          upgBadge.innerText = 'Up to Date';
          upgBadge.style.color = 'var(--accent-green)';
          upgBadge.style.background = 'rgba(16, 185, 129, 0.15)';
        } else if (secCount > 0 || osInfo.pending_reboot) {
          upgBadge.innerText = osInfo.pending_reboot ? 'Reboot Needed' : `${secCount} Critical`;
          upgBadge.style.color = 'var(--accent-pink)';
          upgBadge.style.background = 'rgba(244, 63, 94, 0.15)';
        } else {
          upgBadge.innerText = `${totalPending} Available`;
          upgBadge.style.color = 'var(--accent-amber)';
          upgBadge.style.background = 'rgba(245, 158, 11, 0.15)';
        }
      }

      const upgCount = document.getElementById('optUpgradesCount');
      if (upgCount) {
        upgCount.innerText = `${totalPending} Pending`;
      }
      const upgOsSub = document.getElementById('optUpgradesOsSub');
      if (upgOsSub) {
        upgOsSub.innerText = `${osDisplayName} (Build ${osBuildStr})`;
      }
      const upgSecSub = document.getElementById('optUpgradesSecuritySub');
      if (upgSecSub) {
        upgSecSub.innerText = `${secCount} Security / Critical`;
      }

      // Hub Pills & Policy Checkboxes
      const osPill = document.getElementById('optOsVersionPill');
      if (osPill) {
        osPill.innerText = `🖥 ${osDisplayName} • Build ${osBuildStr}`;
      }
      const rebootPill = document.getElementById('optRebootPill');
      if (rebootPill) {
        rebootPill.style.display = osInfo.pending_reboot ? 'inline-block' : 'none';
      }

      const chkSec = document.getElementById('optPolicySecurity');
      if (chkSec && policy.auto_install_security_and_patch !== undefined) {
        chkSec.checked = !!policy.auto_install_security_and_patch;
      }
      const chkAll = document.getElementById('optPolicyAllApps');
      if (chkAll && policy.auto_install_all_software !== undefined) {
        chkAll.checked = !!policy.auto_install_all_software;
      }
      const chkOs = document.getElementById('optPolicyOsPatches');
      if (chkOs && policy.auto_install_os_patches !== undefined) {
        chkOs.checked = !!policy.auto_install_os_patches;
      }

      // Render Pending OS + Software Upgrades List
      const listEl = document.getElementById('optUpgradesList');
      if (!listEl) return;

      if (osUpdates.length === 0 && swPackages.length === 0) {
        listEl.innerHTML = `
          <div style="text-align: center; padding: 20px; color: var(--accent-green); background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.22); border-radius: 8px; font-size: 12.5px;">
            ✅ <strong>OS &amp; All Installed Software Up to Date!</strong> Autonomous manager checks every 12 hours silently.
          </div>
        `;
        return;
      }

      const rows = [];
      osUpdates.forEach(u => {
        const kbId = u.id || u.kb || '';
        const kbLabel = kbId ? ` (${escapeHtml(String(kbId))})` : '';
        rows.push(`
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(244, 63, 94, 0.06); border: 1px solid rgba(244, 63, 94, 0.25); border-radius: 8px; gap: 10px; flex-wrap: wrap;">
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span class="badge" style="background: rgba(244, 63, 94, 0.18); color: #f87171; font-size: 10.5px;">🛡 OS Update</span>
                <strong style="color: #fff; font-size: 13px;">${escapeHtml(String(u.title || 'OS System Update'))}${kbLabel}</strong>
              </div>
              <span style="font-size: 11.5px; color: var(--text-muted);">Severity: ${escapeHtml(String(u.severity || 'Important'))} • Source: ${escapeHtml(String(u.source || 'System Update'))}</span>
            </div>
            <button class="btn" style="font-size: 11.5px; padding: 5px 12px; border-color: #f87171; color: #f87171;" onclick="runAutoUpgradeNow()">⬆️ Stage OS Patch</button>
          </div>
        `);
      });

      swPackages.forEach(pkg => {
        const isSec = pkg.category === 'Security & Critical' || pkg.is_security_or_critical;
        const isDev = pkg.category === 'Developer Tools';
        const catStyle = isSec
          ? 'background: rgba(244, 63, 94, 0.18); color: #f87171;'
          : (isDev ? 'background: rgba(56, 189, 248, 0.16); color: #38bdf8;' : 'background: rgba(168, 85, 247, 0.15); color: #c084fc;');
        const pkgId = String(pkg.id || pkg.name || '');
        rows.push(`
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: rgba(255,255,255,0.025); border: 1px solid var(--card-border); border-radius: 8px; gap: 10px; flex-wrap: wrap;">
            <div style="display: flex; flex-direction: column; gap: 2px;">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span class="badge" style="${catStyle} font-size: 10.5px;">${escapeHtml(String(pkg.category || 'Application'))}</span>
                <strong style="color: #fff; font-size: 13px;">${escapeHtml(String(pkg.name || pkgId))}</strong>
                <span style="font-size: 11px; color: var(--text-muted); font-family: monospace;">(${escapeHtml(pkgId)})</span>
              </div>
              <span style="font-size: 11.5px; color: var(--text-muted);">Installed: <code style="color: #cbd5e1;">${escapeHtml(String(pkg.current_version || '?'))}</code> → Available: <code style="color: var(--accent-green); font-weight: 600;">${escapeHtml(String(pkg.available_version || 'Latest'))}</code> • Source: ${escapeHtml(String(pkg.source || 'winget'))}</span>
            </div>
            <button class="btn" style="font-size: 11.5px; padding: 5px 12px; border-color: var(--accent-cyan); color: var(--accent-cyan);" onclick="runAutoUpgradeNow('${escapeHtml(pkgId)}')">⬆️ Upgrade</button>
          </div>
        `);
      });

      listEl.innerHTML = rows.join('');
    }

    async function scanOptimizerUpgradesNow() {
      const btn = document.getElementById('btnOptScanUpgrades');
      const topBtn = document.getElementById('btnScanUpgradesTop');
      if (btn) { btn.innerText = '🔍 Scanning...'; btn.disabled = true; }
      if (topBtn) { topBtn.innerText = '⬆️ Scanning...'; topBtn.disabled = true; }
      try {
        const res = await fetch('/api/optimizer/upgrades?refresh=1');
        const data = await res.json();
        if (data.status === 'success') {
          renderOptimizerUpgrades(data);
          showOptimizerToast(`Upgrade scan complete: ${data.overall_status || 'Up to Date'}`, true);
        } else {
          showOptimizerToast(data.message || 'Upgrade scan returned an error.', false);
        }
      } catch (e) {
        showOptimizerToast('Failed to scan upgrades: ' + e.message, false);
      } finally {
        if (btn) { btn.innerText = '🔍 Scan Upgrades Now'; btn.disabled = false; }
        if (topBtn) { topBtn.innerText = '⬆️ Check Upgrades'; topBtn.disabled = false; }
      }
    }

    async function runAutoUpgradeNow(packageId = '') {
      const btn = document.getElementById('btnOptRunAutoUpgrade');
      if (btn) { btn.innerText = '⬆️ Upgrading Silently...'; btn.disabled = true; }
      try {
        const payload = packageId
          ? { mode: 'install_specific', package_ids: [packageId] }
          : { mode: 'auto_manage', force_scan: true };
        const res = await fetch('/api/optimizer/upgrades/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        showOptimizerToast(data.message || 'Autonomous upgrade run completed!', data.status === 'success' || data.status === 'partial');
        await scanOptimizerUpgradesNow();
        fetchOptimizerDiagnostics();
        if (typeof fetchLogs === 'function') fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to run upgrades: ' + e.message, false);
      } finally {
        if (btn) { btn.innerText = '⬆️ Auto-Upgrade All Now'; btn.disabled = false; }
      }
    }

    async function toggleUpgradePolicySetting(key, enabled) {
      try {
        const payload = {};
        payload[key] = !!enabled;
        const res = await fetch('/api/optimizer/upgrades/policy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'success') {
          showOptimizerToast('Autonomous upgrade policy saved.', true);
        }
      } catch (e) {
        showOptimizerToast('Failed to update upgrade policy: ' + e.message, false);
      }
    }

    function renderOptimizerRecommendations(recoms) {
      const container = document.getElementById('optRecommendationsList');
      if (!container) return;
      if (!recoms || recoms.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 26px; color: var(--accent-green); background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 8px; font-size: 13px;">
            🎉 <strong>All Systems Optimal!</strong> No critical performance bottlenecks detected.
          </div>
        `;
        return;
      }

      container.innerHTML = recoms.map(r => {
        const impactBadge = r.impact === 'High' 
          ? '<span class="badge" style="background: rgba(244, 63, 94, 0.15); color: var(--accent-pink); border: 1px solid rgba(244, 63, 94, 0.3);">High Impact</span>'
          : '<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.3);">Medium Impact</span>';

        return `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 14px 16px; background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; gap: 14px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 240px;">
              <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                <strong style="color: #fff; font-size: 13.5px;">${escapeHtml(r.title)}</strong>
                ${impactBadge}
              </div>
              <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">${escapeHtml(r.description)}</div>
            </div>
            <button class="btn ${r.btn_class || 'btn-primary'}" style="font-size: 12px; white-space: nowrap; padding: 6px 14px;" onclick="triggerOptimizerAction('${r.action_id}')">
              ${escapeHtml(r.button_text)}
            </button>
          </div>
        `;
      }).join('');
    }

    function renderOptimizerProcesses(procs) {
      const container = document.getElementById('optProcessList');
      if (!container) return;
      if (!procs || procs.length === 0) {
        container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 20px; font-size: 12px;">No process telemetry available.</div>`;
        return;
      }

      container.innerHTML = procs.map(p => `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 6px; font-size: 12px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="color: #38bdf8; font-family: monospace; font-size: 11px;">#${p.pid}</span>
            <strong style="color: var(--text);">${escapeHtml(p.name)}</strong>
          </div>
          <span style="font-weight: 600; color: var(--accent-cyan); font-family: monospace;">${p.mem_mb} MB</span>
        </div>
      `).join('');
    }

    function showOptimizerToast(msg, isSuccess = true) {
      const banner = document.getElementById('optimizerActionBanner');
      const text = document.getElementById('optimizerActionBannerText');
      if (!banner || !text) return;
      banner.style.display = 'flex';
      text.innerText = msg;
      if (isSuccess) {
        banner.style.background = 'rgba(16, 185, 129, 0.15)';
        banner.style.border = '1px solid rgba(16, 185, 129, 0.4)';
        banner.style.color = '#34d399';
      } else {
        banner.style.background = 'rgba(239, 68, 68, 0.15)';
        banner.style.border = '1px solid rgba(239, 68, 68, 0.4)';
        banner.style.color = '#f87171';
      }
      setTimeout(() => {
        if (banner) banner.style.display = 'none';
      }, 6000);
    }

    async function triggerOptimizerAction(actionId) {
      if (actionId === 'clean_temp') return runCleanTemp();
      if (actionId === 'flush_dns') return runFlushDns();
      if (actionId === 'purge_caches') return runPurgeDevCaches();
      if (actionId === 'optimize_ram') return runOptimizeRam();
      if (actionId === 'open_startup') return runOpenStartupSettings();
      if (actionId === 'manage_upgrades') return runAutoUpgradeNow();
    }

    async function runCleanTemp() {
      try {
        const res = await fetch('/api/optimizer/clean_temp', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || 'Cleaned temp files!', data.status === 'success');
        fetchOptimizerDiagnostics();
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to clean temp: ' + e.message, false);
      }
    }

    async function runFlushDns() {
      try {
        const res = await fetch('/api/optimizer/flush_dns', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || 'DNS Cache Flushed!', data.status === 'success');
        fetchOptimizerDiagnostics();
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to flush DNS: ' + e.message, false);
      }
    }

    async function runPurgeDevCaches() {
      try {
        const res = await fetch('/api/optimizer/purge_caches', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || 'Dev Caches Purged!', data.status === 'success');
        fetchOptimizerDiagnostics();
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to purge caches: ' + e.message, false);
      }
    }

    async function runOptimizeRam() {
      try {
        const res = await fetch('/api/optimizer/optimize_ram', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || 'RAM Optimized!', data.status === 'success');
        fetchOptimizerDiagnostics();
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to optimize RAM: ' + e.message, false);
      }
    }

    async function runOpenStartupSettings() {
      try {
        const res = await fetch('/api/optimizer/open_startup', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || 'Opened Startup Settings.', data.status === 'success');
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Failed to open startup settings: ' + e.message, false);
      }
    }

    async function runCompleteOptimization() {
      const btn = document.getElementById('btnAutoTune');
      if (btn) {
        btn.innerText = '⚡ Tuning PC...';
        btn.disabled = true;
      }
      try {
        const res = await fetch('/api/optimizer/auto_tune', { method: 'POST', headers: {'Content-Type': 'application/json'} });
        const data = await res.json();
        showOptimizerToast(data.message || '1-Click Optimization complete!', data.status === 'success');
        fetchOptimizerDiagnostics();
        fetchLogs();
      } catch (e) {
        showOptimizerToast('Optimization failed: ' + e.message, false);
      } finally {
        if (btn) {
          btn.innerText = '⚡ 1-Click Complete Tuning';
          btn.disabled = false;
        }
      }
    }

    // --- Health & Wellness Engine ---

window.fetchOptimizerDiagnostics = fetchOptimizerDiagnostics;
window.renderOptimizerUpgrades = renderOptimizerUpgrades;
window.scanOptimizerUpgradesNow = scanOptimizerUpgradesNow;
window.runAutoUpgradeNow = runAutoUpgradeNow;
window.toggleUpgradePolicySetting = toggleUpgradePolicySetting;
window.renderOptimizerRecommendations = renderOptimizerRecommendations;
window.renderOptimizerProcesses = renderOptimizerProcesses;
window.showOptimizerToast = showOptimizerToast;
window.triggerOptimizerAction = triggerOptimizerAction;
window.runCleanTemp = runCleanTemp;
window.runFlushDns = runFlushDns;
window.runPurgeDevCaches = runPurgeDevCaches;
window.runOptimizeRam = runOptimizeRam;
window.runOpenStartupSettings = runOpenStartupSettings;
window.runCompleteOptimization = runCompleteOptimization;
