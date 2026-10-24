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
