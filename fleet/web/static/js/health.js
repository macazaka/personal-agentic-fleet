// --- Health Modals Management ---
function openApolloModal() {
  const m = document.getElementById('apolloModal');
  if (m) m.style.display = 'flex';
}
function closeApolloModal() {
  const m = document.getElementById('apolloModal');
  if (m) m.style.display = 'none';
}

function openDietProtocolModal() {
  const m = document.getElementById('ffdDietModal');
  if (m) m.style.display = 'flex';
}
function closeDietProtocolModal() {
  const m = document.getElementById('ffdDietModal');
  if (m) m.style.display = 'none';
}

function openPrescriptionModal() {
  const m = document.getElementById('ffdPrescriptionModal');
  if (m) m.style.display = 'flex';
}
function closePrescriptionModal() {
  const m = document.getElementById('ffdPrescriptionModal');
  if (m) m.style.display = 'none';
}

// --- Health & Wellness Engine ---
let currentTrendMetric = 'water_ml';
let currentTrendDays = 7;
let globalHealthSummary = null;

    function toggleAddMedCard() {
      const card = document.getElementById('addMedCard');
      const btn = document.getElementById('btnToggleAddMed');
      if (!card) return;
      const isHidden = card.style.display === 'none' || card.style.display === '';
      card.style.display = isHidden ? 'block' : 'none';
      if (isHidden) {
        document.getElementById('newMedName').focus();
        if (btn) btn.innerText = '✕ Close Form';
      } else {
        if (btn) btn.innerText = '+ Add Medication';
      }
    }

    async function fetchHealthDashboard() {
      try {
        const res = await fetch('/api/health/summary');
        const data = await res.json();
        globalHealthSummary = data;

        // 0. Metabolic Profile & Countdown
        const meta = data.metabolic_profile || {};
        const daysRemainingEl = document.getElementById('ffdDaysRemaining');
        if (daysRemainingEl) {
          const days = meta.days_remaining !== undefined ? meta.days_remaining : 75;
          daysRemainingEl.innerText = `${days} Days Left`;
        }

        // 1. Hydration
        const hyd = data.hydration || {};
        const glasses = hyd.glasses || 0;
        const amountMl = hyd.amount_ml || 0;
        const goalMl = hyd.goal_ml || 2500;
        const pct = hyd.percentage !== undefined ? hyd.percentage : 0;
        const reminder = hyd.reminder_status || 'Hydration on track';
        const lastDrank = hyd.last_drank_at || '';

        const waterVal = document.getElementById('healthWaterVal');
        if (waterVal) waterVal.innerText = `${amountMl.toLocaleString()} / ${goalMl.toLocaleString()} ml (${pct}%)`;
        const waterBadge = document.getElementById('healthWaterPctBadge');
        if (waterBadge) waterBadge.innerText = `${pct}%`;
        const waterBar = document.getElementById('healthWaterBar');
        if (waterBar) waterBar.style.width = `${Math.min(100, pct)}%`;
        const waterNext = document.getElementById('healthWaterNext');
        if (waterNext) waterNext.innerText = reminder;
        const bigCount = document.getElementById('healthWaterBigCount');
        if (bigCount) bigCount.innerText = `${glasses} / ${Math.max(1, Math.round(goalMl / 250))} Glasses (${amountMl}ml)`;
        const remText = document.getElementById('healthWaterReminderText');
        if (remText) remText.innerText = reminder;
        const lastDrankEl = document.getElementById('healthWaterLastDrank');
        if (lastDrankEl) {
          lastDrankEl.innerText = lastDrank ? `Last drank: ${lastDrank.substring(11, 16)} IST` : 'Last drank: None today';
        }

        // Render Glasses Grid
        const grid = document.getElementById('healthGlassesGrid');
        if (grid) {
          const totalTargetGlasses = Math.max(10, Math.round(goalMl / 250));
          let html = '';
          for (let i = 1; i <= totalTargetGlasses; i++) {
            const isFilled = i <= glasses;
            const color = isFilled ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.15)';
            const bg = isFilled ? 'rgba(0, 242, 254, 0.2)' : 'rgba(255, 255, 255, 0.03)';
            html += `
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 34px; height: 38px; border-radius: 6px; background: ${bg}; border: 1px solid ${isFilled ? 'rgba(0, 242, 254, 0.4)' : 'rgba(255, 255, 255, 0.08)'}; cursor: pointer;" onclick="logWater(${isFilled ? -1 : 1}, ${isFilled ? -250 : 250})" title="Glass #${i}: 250ml (${isFilled ? 'Logged' : 'Pending'})">
                <span style="font-size: 15px;">🥛</span>
                <span style="font-size: 9px; font-weight: 700; color: ${color};">${i * 250 >= 1000 ? (i * 250 / 1000).toFixed(1) + 'L' : i * 250}</span>
              </div>
            `;
          }
          grid.innerHTML = html;
        }

        // 2. Medications
        const meds = data.medications || {};
        const items = meds.items || [];
        const taken = meds.taken_count || 0;
        const totalMeds = meds.total_count || 0;

        const medsBadge = document.getElementById('healthMedsBadge');
        if (medsBadge) medsBadge.innerText = `${taken} / ${totalMeds}`;
        const medsHeadline = document.getElementById('healthMedsHeadline');
        if (medsHeadline) medsHeadline.innerText = `${taken} / ${totalMeds} Taken`;
        const medsStatus = document.getElementById('healthMedsStatus');
        if (medsStatus) {
          medsStatus.innerText = totalMeds === 0 ? 'No medications scheduled' : (meds.all_taken ? '🎉 100% Adherence Today' : `${totalMeds - taken} Dose(s) Pending`);
        }
        const medsCountEl = document.getElementById('healthMedsScheduleCount');
        if (medsCountEl) medsCountEl.innerText = `${totalMeds} Scheduled`;

        const pendingMeds = items.filter(m => !m.taken_today);
        const nextDoseEl = document.getElementById('healthMedsNextDose');
        if (nextDoseEl) {
          if (pendingMeds.length > 0) {
            nextDoseEl.innerText = `Next: ${escapeHtml(pendingMeds[0].name)} at ${escapeHtml(pendingMeds[0].schedule_time)} IST`;
          } else if (totalMeds > 0) {
            nextDoseEl.innerText = 'All scheduled doses completed for today!';
          } else {
            nextDoseEl.innerText = 'No medications scheduled';
          }
        }

        renderMedicationsList(items);

        // 3. Vitals cards
        const vitals = data.latest_vitals || {};
        const sleepEl = document.getElementById('healthSleepVal');
        if (sleepEl && vitals.sleep_hours !== undefined) sleepEl.innerText = `${vitals.sleep_hours} hrs`;
        const stepsEl = document.getElementById('healthStepsVal');
        if (stepsEl && vitals.steps !== undefined) stepsEl.innerText = `${Number(vitals.steps).toLocaleString()} steps`;
        const stepsPctEl = document.getElementById('healthStepsPct');
        if (stepsPctEl && vitals.steps) {
          const stepPct = Math.round((vitals.steps / 10000) * 100);
          stepsPctEl.innerText = `${stepPct}% of 10k goal`;
        }

        // 4. Trend Chart
        renderTrendChart(currentTrendMetric, currentTrendDays, data.trends);

      } catch (e) {
        console.error('Error loading health dashboard:', e);
      }
    }

    function renderMedCardHtml(m) {
      const isTaken = m.taken_today;
      const takenTime = m.taken_at ? m.taken_at.substring(11, 16) + ' IST' : '';
      const statusBadge = isTaken
        ? `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: var(--accent-green); border: 1px solid rgba(16, 185, 129, 0.3); font-size: 11px;">✓ Taken ${takenTime ? 'at ' + takenTime : ''}</span>`
        : `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: var(--accent-amber); border: 1px solid rgba(245, 158, 11, 0.3); font-size: 11px;">⏳ Due at ${escapeHtml(m.schedule_time)} IST</span>`;

      const btnHtml = isTaken
        ? `<button class="btn" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 11.5px; padding: 4px 10px;" onclick="toggleMedication(${m.id})">✓ Taken</button>`
        : `<button class="btn btn-primary" style="font-size: 11.5px; padding: 4px 12px;" onclick="toggleMedication(${m.id})">Take Now</button>`;

      return `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 11px 13px; background: rgba(255,255,255,0.03); border: 1px solid var(--card-border); border-radius: 8px; gap: 12px; flex-wrap: wrap;">
          <div style="flex: 1; min-width: 200px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
              <strong style="color: #fff; font-size: 13.5px;">${escapeHtml(m.name)}</strong>
              <span class="ag-pill-badge gray" style="font-size: 10px;">${escapeHtml(m.dosage || '1 dose')}</span>
              <span class="ag-pill-badge purple" style="font-size: 10px;">${escapeHtml(m.frequency || 'Daily')}</span>
              ${statusBadge}
            </div>
            <div style="font-size: 11.5px; color: var(--text-muted); line-height: 1.4;">
              🕒 <strong>${escapeHtml(m.schedule_time)} IST</strong> ${m.instructions ? ' • ' + escapeHtml(m.instructions) : ''}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            ${btnHtml}
            <button class="btn-delete" onclick="deleteMedication(${m.id})" title="Remove medication">✕</button>
          </div>
        </div>
      `;
    }

    function renderMedicationsList(items) {
      const container = document.getElementById('healthMedsList');
      if (!container) return;
      if (!items || items.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 30px; color: var(--text-muted); font-size: 13px; background: rgba(0,0,0,0.2); border-radius: 8px;">
            No medications scheduled. Click "+ Add Medication" above to add your prescriptions.
          </div>
        `;
        return;
      }

      // Group into Morning, Afternoon, Evening
      const morning = items.filter(m => (m.schedule_time || '09:00') <= '11:00');
      const afternoon = items.filter(m => (m.schedule_time || '') > '11:00' && (m.schedule_time || '') <= '16:00');
      const evening = items.filter(m => (m.schedule_time || '') > '16:00');

      let sectionsHtml = '';
      if (morning.length > 0) {
        sectionsHtml += `
          <div style="margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: var(--accent-amber); margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
              <span>🌅 Morning / After Breakfast (08:30 IST)</span>
              <span class="badge" style="font-size: 10px; background: rgba(245, 158, 11, 0.15); color: var(--accent-amber);">${morning.filter(x=>x.taken_today).length}/${morning.length} Done</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">${morning.map(renderMedCardHtml).join('')}</div>
          </div>
        `;
      }
      if (afternoon.length > 0) {
        sectionsHtml += `
          <div style="margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: var(--accent-cyan); margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
              <span>☀️ Afternoon / After Lunch (13:30 IST)</span>
              <span class="badge" style="font-size: 10px; background: rgba(0, 242, 254, 0.15); color: var(--accent-cyan);">${afternoon.filter(x=>x.taken_today).length}/${afternoon.length} Done</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">${afternoon.map(renderMedCardHtml).join('')}</div>
          </div>
        `;
      }
      if (evening.length > 0) {
        sectionsHtml += `
          <div style="margin-bottom: 12px;">
            <div style="font-size: 12px; font-weight: 700; color: #c084fc; margin-bottom: 6px; display: flex; align-items: center; gap: 6px;">
              <span>🌙 Night / After Dinner (20:00 IST)</span>
              <span class="badge" style="font-size: 10px; background: rgba(192, 132, 252, 0.15); color: #c084fc;">${evening.filter(x=>x.taken_today).length}/${evening.length} Done</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px;">${evening.map(renderMedCardHtml).join('')}</div>
          </div>
        `;
      }

      container.innerHTML = sectionsHtml || items.map(renderMedCardHtml).join('');
    }

    async function logWater(deltaGlasses, deltaMl) {
      try {
        await fetch('/api/health/water', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ delta_glasses: deltaGlasses, delta_ml: deltaMl })
        });
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error logging water:', e);
      }
    }

    async function promptWaterGoal() {
      const curGoal = (globalHealthSummary && globalHealthSummary.hydration) ? globalHealthSummary.hydration.goal_ml : 2500;
      const input = prompt('Enter your daily water intake goal in milliliters (ml):', curGoal);
      if (!input) return;
      const val = parseInt(input, 10);
      if (isNaN(val) || val < 500) {
        alert('Please enter a valid goal (minimum 500 ml).');
        return;
      }
      try {
        await fetch('/api/health/water/goal', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ goal_ml: val })
        });
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error setting water goal:', e);
      }
    }

    async function submitNewMedication() {
      const name = document.getElementById('newMedName').value.trim();
      const dosage = document.getElementById('newMedDosage').value.trim();
      const scheduleTime = document.getElementById('newMedTime').value.trim() || '09:00';
      const frequency = document.getElementById('newMedFreq').value;
      const instructions = document.getElementById('newMedInstructions').value.trim();

      if (!name) {
        alert('Please enter medication name.');
        return;
      }

      try {
        await fetch('/api/health/medications', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            name: name,
            dosage: dosage,
            schedule_time: scheduleTime,
            frequency: frequency,
            instructions: instructions
          })
        });
        document.getElementById('newMedName').value = '';
        document.getElementById('newMedDosage').value = '';
        document.getElementById('newMedInstructions').value = '';
        toggleAddMedCard();
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error adding medication:', e);
      }
    }

    async function toggleMedication(id) {
      try {
        await fetch('/api/health/medications/toggle', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ id: id })
        });
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error toggling medication:', e);
      }
    }

    async function deleteMedication(id) {
      if (!confirm('Are you sure you want to delete this medication schedule?')) return;
      try {
        await fetch('/api/health/medications/delete', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ id: id })
        });
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error deleting medication:', e);
      }
    }

    function selectTrendMetric(metricType) {
      currentTrendMetric = metricType;
      ['chartTabWater', 'chartTabSleep', 'chartTabSteps', 'chartTabHr'].forEach(id => {
        const b = document.getElementById(id);
        if (b) b.classList.remove('active');
      });
      const activeMap = {
        'water_ml': 'chartTabWater',
        'fasting_glucose': 'chartTabFasting',
        'pp_glucose': 'chartTabPp',
        'weight_kg': 'chartTabWeight',
        'blood_pressure_sys': 'chartTabBp',
        'sleep_hours': 'chartTabSleep',
        'steps': 'chartTabSteps',
        'resting_hr': 'chartTabHr'
      };
      const activeBtn = document.getElementById(activeMap[metricType]);
      if (activeBtn) activeBtn.classList.add('active');
      renderTrendChart(metricType, currentTrendDays);
    }

    function updateMetricUnitHint() {
      const type = document.getElementById('quickMetricType').value;
      const unitInput = document.getElementById('quickMetricUnit');
      const valInput = document.getElementById('quickMetricValue');
      if (!unitInput) return;
      if (type === 'water_ml') { unitInput.value = 'ml'; valInput.placeholder = 'e.g. 250'; }
      else if (type === 'fasting_glucose') { unitInput.value = 'mg/dL'; valInput.placeholder = 'e.g. 98'; }
      else if (type === 'pp_glucose') { unitInput.value = 'mg/dL'; valInput.placeholder = 'e.g. 135'; }
      else if (type === 'weight_kg') { unitInput.value = 'kg'; valInput.placeholder = 'e.g. 94.5'; }
      else if (type === 'blood_pressure_sys') { unitInput.value = 'mmHg'; valInput.placeholder = 'e.g. 120'; }
      else if (type === 'blood_pressure_dia') { unitInput.value = 'mmHg'; valInput.placeholder = 'e.g. 80'; }
      else if (type === 'sleep_hours') { unitInput.value = 'hrs'; valInput.placeholder = 'e.g. 7.5'; }
      else if (type === 'steps') { unitInput.value = 'steps'; valInput.placeholder = 'e.g. 5000'; }
      else if (type === 'resting_hr') { unitInput.value = 'bpm'; valInput.placeholder = 'e.g. 68'; }
    }

    async function submitQuickVital() {
      const type = document.getElementById('quickMetricType').value;
      const val = parseFloat(document.getElementById('quickMetricValue').value);
      const unit = document.getElementById('quickMetricUnit').value.trim();

      if (isNaN(val) || val <= 0) {
        alert('Please enter a valid numeric value.');
        return;
      }

      try {
        await fetch('/api/health/metrics/log', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            metric_type: type,
            value: val,
            unit: unit
          })
        });
        document.getElementById('quickMetricValue').value = '';
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error logging vital:', e);
      }
    }

    function quickLogVital(type, val, unit) {
      fetch('/api/health/metrics/log', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ metric_type: type, value: val, unit: unit })
      }).then(() => {
        fetchHealthDashboard();
        fetchLogs();
      });
    }

    async function renderTrendChart(metricType, days, preloadedTrends) {
      const container = document.getElementById('healthTrendSvgContainer');
      if (!container) return;

      let trendData = [];
      if (preloadedTrends && preloadedTrends[metricType]) {
        trendData = preloadedTrends[metricType];
      } else {
        try {
          const res = await fetch(`/api/health/trends?metric=${encodeURIComponent(metricType)}&days=${days}`);
          trendData = await res.json();
        } catch (e) {
          console.error('Failed to fetch trend data:', e);
          trendData = [];
        }
      }

      if (!trendData || trendData.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:50px; color:var(--text-muted); font-size:13px;">No trend data available for this metric yet. Log entries to see chart.</div>`;
        return;
      }

      const configs = {
        'water_ml': { label: 'Water Intake', unit: 'ml', color: '#00f2fe', goal: 2500, minLimit: 1000, maxLimit: 3000 },
        'fasting_glucose': { label: 'Fasting Blood Sugar', unit: 'mg/dL', color: '#38bdf8', goal: 95, minLimit: 60, maxLimit: 160 },
        'pp_glucose': { label: 'Post-Meal Sugar (PPBS)', unit: 'mg/dL', color: '#ec4899', goal: 135, minLimit: 80, maxLimit: 280 },
        'weight_kg': { label: 'Body Weight', unit: 'kg', color: '#10b981', goal: 75.0, minLimit: 60, maxLimit: 100 },
        'blood_pressure_sys': { label: 'Systolic Blood Pressure', unit: 'mmHg', color: '#fb923c', goal: 120, minLimit: 90, maxLimit: 160 },
        'sleep_hours': { label: 'Night Sleep', unit: 'hrs', color: '#c084fc', goal: 8.0, minLimit: 4.0, maxLimit: 10.0 },
        'steps': { label: 'Daily Steps', unit: 'steps', color: '#f59e0b', goal: 10000, minLimit: 4000, maxLimit: 14000 },
        'resting_hr': { label: 'Resting Heart Rate', unit: 'bpm', color: '#f43f5e', goal: 68, minLimit: 50, maxLimit: 90 }
      };
      const cfg = configs[metricType] || { label: metricType, unit: '', color: '#00f2fe', goal: 100, minLimit: 0, maxLimit: 100 };

      const values = trendData.map(d => d.value);
      const avg = Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10;
      const minVal = Math.min(...values);
      const maxVal = Math.max(...values);

      const statAvg = document.getElementById('chartStatAvg');
      if (statAvg) statAvg.innerText = `${avg.toLocaleString()} ${cfg.unit}`;
      const statMin = document.getElementById('chartStatMin');
      if (statMin) statMin.innerText = `${minVal.toLocaleString()} ${cfg.unit}`;
      const statMax = document.getElementById('chartStatMax');
      if (statMax) statMax.innerText = `${maxVal.toLocaleString()} ${cfg.unit}`;
      const statGoal = document.getElementById('chartStatGoal');
      if (statGoal) statGoal.innerText = `${cfg.goal.toLocaleString()} ${cfg.unit}`;

      const width = 640;
      const height = 220;
      const padLeft = 55;
      const padRight = 25;
      const padTop = 25;
      const padBottom = 35;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      const yMin = Math.min(cfg.minLimit, Math.floor(minVal * 0.85));
      const yMax = Math.max(cfg.maxLimit, Math.ceil(maxVal * 1.15));
      const yRange = yMax - yMin || 1;

      const n = trendData.length;
      const points = trendData.map((d, i) => {
        const x = n > 1 ? padLeft + (i / (n - 1)) * plotW : padLeft + plotW / 2;
        const y = padTop + (1 - (d.value - yMin) / yRange) * plotH;
        return { x, y, date: d.date, val: d.value };
      });

      const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
      const areaD = `${pathD} L ${points[points.length - 1].x.toFixed(1)},${(padTop + plotH).toFixed(1)} L ${points[0].x.toFixed(1)},${(padTop + plotH).toFixed(1)} Z`;

      const goalY = padTop + (1 - (cfg.goal - yMin) / yRange) * plotH;

      const gridSteps = 4;
      let gridLinesHtml = '';
      for (let g = 0; g <= gridSteps; g++) {
        const valAtGrid = Math.round(yMin + (g / gridSteps) * yRange);
        const yAtGrid = padTop + (1 - g / gridSteps) * plotH;
        gridLinesHtml += `
          <line x1="${padLeft}" y1="${yAtGrid}" x2="${width - padRight}" y2="${yAtGrid}" stroke="rgba(255,255,255,0.07)" stroke-dasharray="3,3" />
          <text x="${padLeft - 8}" y="${yAtGrid + 4}" fill="#64748b" font-size="10" text-anchor="end" font-family="monospace">${valAtGrid >= 1000 ? (valAtGrid / 1000).toFixed(1) + 'k' : valAtGrid}</text>
        `;
      }

      const dotsHtml = points.map(p => {
        const dateParts = p.date.split('-');
        const shortDate = dateParts.length === 3 ? `${dateParts[1]}/${dateParts[2]}` : p.date;
        return `
          <g class="chart-point-group">
            <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="4.5" fill="${cfg.color}" stroke="#0b0f19" stroke-width="2">
              <title>${escapeHtml(p.date)}: ${p.val} ${cfg.unit}</title>
            </circle>
            <text x="${p.x.toFixed(1)}" y="${height - 12}" fill="#94a3b8" font-size="10.5" text-anchor="middle" font-family="monospace">${shortDate}</text>
          </g>
        `;
      }).join('');

      container.innerHTML = `
        <svg viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; display: block;" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <linearGradient id="trendGrad_${metricType}" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="${cfg.color}" stop-opacity="0.32" />
              <stop offset="100%" stop-color="${cfg.color}" stop-opacity="0.0" />
            </linearGradient>
          </defs>
          ${gridLinesHtml}
          <!-- Reference Goal Line -->
          <line x1="${padLeft}" y1="${goalY}" x2="${width - padRight}" y2="${goalY}" stroke="rgba(245, 158, 11, 0.45)" stroke-dasharray="4,4" stroke-width="1.5" />
          <text x="${width - padRight}" y="${goalY - 6}" fill="rgba(245, 158, 11, 0.85)" font-size="9.5" text-anchor="end" font-weight="600">Goal: ${cfg.goal} ${cfg.unit}</text>
          <!-- Area Fill -->
          <path d="${areaD}" fill="url(#trendGrad_${metricType})" />
          <!-- Trend Stroke -->
          <path d="${pathD}" fill="none" stroke="${cfg.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          <!-- Points -->
          ${dotsHtml}
        </svg>
      `;
    }

window.openApolloModal = openApolloModal;
window.closeApolloModal = closeApolloModal;
window.openDietProtocolModal = openDietProtocolModal;
window.closeDietProtocolModal = closeDietProtocolModal;
window.openPrescriptionModal = openPrescriptionModal;
window.closePrescriptionModal = closePrescriptionModal;
window.toggleAddMedCard = toggleAddMedCard;
window.fetchHealthDashboard = fetchHealthDashboard;
window.renderMedicationsList = renderMedicationsList;
window.logWater = logWater;
window.promptWaterGoal = promptWaterGoal;
window.submitNewMedication = submitNewMedication;
window.toggleMedication = toggleMedication;
window.deleteMedication = deleteMedication;
window.selectTrendMetric = selectTrendMetric;
window.updateMetricUnitHint = updateMetricUnitHint;
window.submitQuickVital = submitQuickVital;
window.quickLogVital = quickLogVital;
window.renderTrendChart = renderTrendChart;


// ==========================================

// ==========================================
// FFD EXERCISE VIDEOS & STRENGTH TRAINING HUB
// ==========================================
let allExerciseVideos = [];
let currentPlayingVideo = null;
let currentVideoType = 'exercise';
let currentExerciseCategory = 'all';

function switchExSubTab(tab) {
  const tabs = ['videos', 'strength', 'antigravity'];
  tabs.forEach(t => {
    const btn = document.getElementById('exSubTab' + t.charAt(0).toUpperCase() + t.slice(1));
    const panel = document.getElementById('exPanel' + t.charAt(0).toUpperCase() + t.slice(1));
    if (btn) {
      if (t === tab) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    }
    if (panel) {
      if (t === tab) {
        panel.style.display = (t === 'strength' || t === 'antigravity') ? 'flex' : 'block';
      } else {
        panel.style.display = 'none';
      }
    }
  });
}

function switchVideoType(type) {
  currentVideoType = type;
  currentExerciseCategory = 'all';

  const btnEx = document.getElementById('vTypeBtnExercise');
  const btnDiet = document.getElementById('vTypeBtnDiet');
  if (btnEx && btnDiet) {
    if (type === 'exercise') {
      btnEx.classList.add('active');
      btnDiet.classList.remove('active');
    } else {
      btnDiet.classList.add('active');
      btnEx.classList.remove('active');
    }
  }

  renderVideoCategoryFilters();
  renderExerciseVideos();
}

async function fetchExerciseVideos() {
  try {
    const res = await fetch('/api/health/videos');
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    if (Array.isArray(data)) {
      allExerciseVideos = data;
    } else if (data && Array.isArray(data.videos)) {
      allExerciseVideos = data.videos;
    }

    // Update counts
    const exCount = allExerciseVideos.filter(v => v.video_type === 'exercise').length;
    const dietCount = allExerciseVideos.filter(v => v.video_type === 'diet').length;
    const countExEl = document.getElementById('countExerciseVideos');
    const countDietEl = document.getElementById('countDietVideos');
    if (countExEl) countExEl.innerText = exCount;
    if (countDietEl) countDietEl.innerText = dietCount;

    renderVideoCategoryFilters();
    renderExerciseVideos();
  } catch (err) {
    console.warn('Failed to fetch exercise videos:', err);
    const grid = document.getElementById('exerciseVideosGrid');
    if (grid) {
      grid.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; grid-column: 1/-1; padding: 12px;">No videos found or unable to access video directory.</div>';
    }
  }
}

function renderVideoCategoryFilters() {
  const row = document.getElementById('videoCategoryFiltersRow');
  if (!row) return;

  const relevant = allExerciseVideos.filter(v => v.video_type === currentVideoType);
  const categories = ['all', ...Array.from(new Set(relevant.map(v => v.category))).sort()];

  const categoryIcons = {
    'all': currentVideoType === 'exercise' ? '🏋️‍♂️' : '🥗',
    'Anti-Gravity & Glucose Drop': '🏃‍♂️',
    'Nitric Oxide Dump (NOD)': '💨',
    "World's Best Warm-Up & Mobility": '🔥',
    'Surya Namaskar Series': '🧘',
    'Super Brain Yoga & Flexibility': '🧠',
    'Desk & Office Conditioning': '🪑',
    'Upper Body & Strength': '💪',
    'Weighted Walking & Aerobic': '🚶‍♂️',
    'Smoothies & Green Drinks': '🥤',
    'Vitamins & Micronutrients': '💊',
    'Tea, Coffee & Beverages': '☕',
    'Diet & Nutrition': '🥗'
  };

  row.innerHTML = categories.map(cat => {
    const icon = categoryIcons[cat] || '📹';
    const label = cat === 'all'
      ? (currentVideoType === 'exercise' ? `All Exercise (${relevant.length})` : `All Diet (${relevant.length})`)
      : `${icon} ${cat}`;
    const isActive = currentExerciseCategory === cat ? 'active' : '';
    const safeCat = cat.replace(/'/g, "\'");

    return `
      <button class="filter-btn ${isActive}" onclick="filterVideoCategory('${safeCat}')" style="font-size: 11px; padding: 4px 10px; border-radius: 6px;">
        ${label}
      </button>
    `;
  }).join('');
}

function filterVideoCategory(category) {
  currentExerciseCategory = category;
  renderVideoCategoryFilters();
  renderExerciseVideos();
}

function renderExerciseVideos() {
  const grid = document.getElementById('exerciseVideosGrid');
  const countBadge = document.getElementById('videoCountBadge');
  if (!grid) return;

  const typeVideos = allExerciseVideos.filter(v => v.video_type === currentVideoType);
  const filtered = currentExerciseCategory === 'all'
    ? typeVideos
    : typeVideos.filter(v => v.category === currentExerciseCategory);

  if (countBadge) {
    const typeLabel = currentVideoType === 'exercise' ? 'Exercise & Movement' : 'Diet & Nutrition';
    countBadge.innerText = `Showing ${filtered.length} of ${typeVideos.length} ${typeLabel} videos`;
  }

  if (filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column: 1/-1; color: var(--text-muted); font-size: 12px; padding: 24px; text-align: center;">No videos match the selected filter.</div>';
    return;
  }

  grid.innerHTML = filtered.map(v => {
    const title = v.title || v.clean_title || v.filename;
    const cleanTitle = title.replace(/'/g, "\'");
    const filenameSafe = v.filename.replace(/'/g, "\'");
    const catSafe = (v.category || 'FFD Video').replace(/'/g, "\'");
    const streamUrl = '/api/health/video/stream?file=' + encodeURIComponent(v.filename);

    return `
      <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.15s, border-color 0.15s;">
        <div>
          <!-- Live Video Thumbnail -->
          <div onclick="playExerciseVideo('${filenameSafe}', '${cleanTitle}', '${catSafe}')" style="position: relative; width: 100%; height: 130px; background: #070d18; border-radius: 6px; overflow: hidden; margin-bottom: 10px; cursor: pointer; border: 1px solid rgba(255,255,255,0.08);" title="Click to play video">
            <video src="${streamUrl}#t=1.0" preload="metadata" muted playsinline style="width: 100%; height: 100%; object-fit: cover; display: block; pointer-events: none; opacity: 0.88;"></video>
            <div style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.65) 100%); display: flex; align-items: center; justify-content: center;">
              <div style="width: 38px; height: 38px; border-radius: 50%; background: rgba(0, 242, 254, 0.9); display: flex; align-items: center; justify-content: center; color: #000; font-size: 15px; font-weight: bold; box-shadow: 0 4px 14px rgba(0,0,0,0.6);">▶</div>
            </div>
            <span style="position: absolute; bottom: 6px; right: 8px; font-size: 10px; background: rgba(0,0,0,0.85); color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: 600;">${v.size_mb || 0} MB</span>
            <span style="position: absolute; top: 6px; left: 8px; font-size: 9.5px; background: rgba(0, 242, 254, 0.2); border: 1px solid rgba(0, 242, 254, 0.4); color: var(--accent-cyan); padding: 1px 6px; border-radius: 4px; font-weight: 600;">${v.category}</span>
          </div>

          <!-- Title -->
          <div style="font-size: 12.5px; font-weight: 600; color: #fff; line-height: 1.35; margin-bottom: 6px;">${title}</div>
        </div>

        <!-- Action Buttons -->
        <div style="display: flex; gap: 6px; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">
          <button class="btn btn-primary" style="flex: 1; font-size: 11px; padding: 5px 8px; display: flex; align-items: center; justify-content: center; gap: 4px;" onclick="playExerciseVideo('${filenameSafe}', '${cleanTitle}', '${catSafe}')">
            ▶ Watch
          </button>
          <button class="btn" title="Open in Windows Media Player" style="font-size: 11px; padding: 5px 8px;" onclick="openVideoInSystem('${filenameSafe}')">
            🖥 Open
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function playExerciseVideo(filename, title, category) {
  currentPlayingVideo = filename;
  const modal = document.getElementById('exerciseVideoModal');
  const modalTitle = document.getElementById('videoModalTitle');
  const modalCat = document.getElementById('videoModalCategory');
  const modalPath = document.getElementById('videoModalPath');
  const player = document.getElementById('exerciseVideoPlayer');

  if (modalTitle) modalTitle.innerText = title || filename;
  if (modalCat) modalCat.innerText = category || 'FFD Video';
  if (modalPath) modalPath.innerText = './data/videos/' + filename;

  if (player) {
    player.src = '/api/health/video/stream?file=' + encodeURIComponent(filename);
    player.load();
    player.play().catch(e => console.log('Autoplay prevented or paused:', e));
  }

  if (modal) modal.style.display = 'flex';
}

function closeVideoModal() {
  const modal = document.getElementById('exerciseVideoModal');
  const player = document.getElementById('exerciseVideoPlayer');
  if (player) {
    player.pause();
    player.src = '';
  }
  if (modal) modal.style.display = 'none';
  currentPlayingVideo = null;
}

async function openCurrentVideoInSystem() {
  if (!currentPlayingVideo) return;
  await openVideoInSystem(currentPlayingVideo);
}

async function openVideoInSystem(filename) {
  try {
    const res = await fetch('/api/health/video/open_system?file=' + encodeURIComponent(filename), { method: 'POST' });
    const data = await res.json();
    if (data.status === 'ok') {
      if (typeof showToast === 'function') {
        showToast('Opened ' + (data.filename || filename) + ' in system media player');
      }
    } else {
      alert('Could not open video: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    console.error('Error opening video in system player:', err);
  }
}

// Attach all video & strength functions to window
window.switchExSubTab = switchExSubTab;
window.switchVideoType = switchVideoType;
window.fetchExerciseVideos = fetchExerciseVideos;
window.renderVideoCategoryFilters = renderVideoCategoryFilters;
window.filterVideoCategory = filterVideoCategory;
window.renderExerciseVideos = renderExerciseVideos;
window.playExerciseVideo = playExerciseVideo;
window.closeVideoModal = closeVideoModal;
window.openCurrentVideoInSystem = openCurrentVideoInSystem;
window.openVideoInSystem = openVideoInSystem;
