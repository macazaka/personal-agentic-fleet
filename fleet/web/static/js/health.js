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
          let days = meta.days_remaining;
          if (days === undefined) {
            const target = new Date('2027-01-01');
            const now = new Date();
            days = Math.max(0, Math.ceil((target - now) / (1000 * 60 * 60 * 24)));
          }
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
        const summaryEl = document.getElementById('healthWaterGlassesSummary');
        if (summaryEl) summaryEl.innerText = `${glasses} / ${Math.max(1, Math.round(goalMl / 250))} Glasses`;
        const bigCount = document.getElementById('healthWaterGlassesBadge');
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
              <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; width: 36px; height: 42px; border-radius: 8px; background: ${bg}; border: 1px solid ${isFilled ? 'rgba(0, 242, 254, 0.45)' : 'rgba(255, 255, 255, 0.08)'}; cursor: pointer; transition: all 0.2s ease;" onclick="logWater(${isFilled ? -1 : 1}, ${isFilled ? -250 : 250})" title="Glass #${i}: 250ml (${isFilled ? 'Filled — Click to undo' : 'Empty — Click to log'})">
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
              <select class="ag-pill-badge purple" style="font-size: 10px; background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 4px; padding: 1px 4px; cursor: pointer; outline: none;" onchange="updateMedFrequency(${m.id}, this.value)" title="Change frequency for ${escapeHtml(m.name)}">
                <option value="Daily"${(m.frequency || 'Daily') === 'Daily' ? ' selected' : ''}>Daily</option>
                <option value="Twice Daily"${m.frequency === 'Twice Daily' ? ' selected' : ''}>Twice Daily</option>
                <option value="Weekly"${m.frequency === 'Weekly' ? ' selected' : ''}>Weekly</option>
                <option value="Monthly"${m.frequency === 'Monthly' ? ' selected' : ''}>Monthly</option>
                <option value="As Needed"${m.frequency === 'As Needed' ? ' selected' : ''}>As Needed</option>
              </select>
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

    async function updateMedFrequency(id, newFreq) {
      try {
        await fetch('/api/health/medications/update', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ id: id, frequency: newFreq })
        });
        await fetchHealthDashboard();
        fetchLogs();
      } catch (e) {
        console.error('Error updating medication frequency:', e);
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
window.updateMedFrequency = updateMedFrequency;
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

// Custom Video Playlists & Sequential Playback State
let savedVideoPlaylists = [];
let selectedVideoPlaylistId = '';
let editingPlaylistId = '';
let draftPlaylistVideos = [];
let isPlaylistBuilderOpen = false;
let activePlaybackPlaylist = null;
let activePlaybackIndex = -1;
let playlistAutoAdvance = true;

function switchExSubTab(tab) {
  const videosPanel = document.getElementById('exPanelVideos');
  const wasVideosActive = tab === 'videos' && videosPanel && videosPanel.style.display !== 'none';
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
  if (tab === 'videos') {
    if (!Array.isArray(allExerciseVideos) || allExerciseVideos.length === 0) {
      fetchExerciseVideos();
    } else {
      renderExerciseVideos();
    }
    if (videosPanel && typeof videosPanel.scrollIntoView === 'function') {
      videosPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    if (wasVideosActive) {
      openVideoVaultFolder();
    }
  }
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

    await fetchVideoPlaylists();
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

async function fetchVideoPlaylists() {
  try {
    const res = await fetch('/api/health/playlists');
    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.playlists)) {
        savedVideoPlaylists = data.playlists;
      }
    }
  } catch (err) {
    console.warn('Failed to load video playlists:', err);
  }
  if (!selectedVideoPlaylistId || !savedVideoPlaylists.some(p => p.id === selectedVideoPlaylistId)) {
    selectedVideoPlaylistId = savedVideoPlaylists.length > 0 ? savedVideoPlaylists[0].id : '';
  }
  if (!isPlaylistBuilderOpen) {
    const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
    draftPlaylistVideos = cur && Array.isArray(cur.videos) ? cur.videos.map(v => ({ ...v })) : [];
    editingPlaylistId = cur ? cur.id : '';
  }
  renderSavedVideoPlaylistsUI();
}

function getActivePlaylistVideosForCardState() {
  if (isPlaylistBuilderOpen) {
    return draftPlaylistVideos;
  }
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  return cur && Array.isArray(cur.videos) ? cur.videos : [];
}

function getVideoPlaylistPosition(filename) {
  const list = getActivePlaylistVideosForCardState();
  const idx = list.findIndex(item => item.filename === filename);
  return idx >= 0 ? idx + 1 : 0;
}

function renderSavedVideoPlaylistsUI() {
  const sel = document.getElementById('savedVideoPlaylistSelect');
  const summaryEl = document.getElementById('playlistSummaryBadge');
  if (sel) {
    if (savedVideoPlaylists.length === 0) {
      sel.innerHTML = '<option value="">No saved playlists yet — click + New Playlist</option>';
    } else {
      sel.innerHTML = savedVideoPlaylists.map(p => {
        const count = Array.isArray(p.videos) ? p.videos.length : 0;
        const selectedAttr = p.id === selectedVideoPlaylistId ? 'selected' : '';
        return `<option value="${escapeHtml(p.id)}" ${selectedAttr}>🎵 ${escapeHtml(p.name)} (${count} video${count === 1 ? '' : 's'})</option>`;
      }).join('');
    }
  }
  if (summaryEl) {
    const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
    if (isPlaylistBuilderOpen) {
      summaryEl.innerHTML = `<strong style="color: var(--accent-cyan);">Building Playlist (${draftPlaylistVideos.length} video${draftPlaylistVideos.length === 1 ? '' : 's'})</strong> • Click <strong style="color: #34d399;">+ Playlist</strong> on any card below to queue`;
    } else if (cur && Array.isArray(cur.videos)) {
      summaryEl.innerHTML = `Selected: <strong style="color: #fff;">${escapeHtml(cur.name)}</strong> (${cur.videos.length} video${cur.videos.length === 1 ? '' : 's'}) • Click <strong style="color: var(--accent-cyan);">+ Playlist</strong> on any video card to add`;
    } else {
      summaryEl.innerHTML = `Click <strong style="color: var(--accent-cyan);">+ Playlist</strong> on any video card below to build a custom playlist`;
    }
  }
  renderPlaylistDraftBuilder();
}

function onSelectSavedVideoPlaylist(playlistId) {
  selectedVideoPlaylistId = String(playlistId || '');
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  if (cur) {
    editingPlaylistId = cur.id;
    draftPlaylistVideos = Array.isArray(cur.videos) ? cur.videos.map(v => ({ ...v })) : [];
    const nameInput = document.getElementById('playlistNameInput');
    if (nameInput && isPlaylistBuilderOpen) {
      nameInput.value = cur.name || '';
    }
  }
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function openPlaylistBuilder(nameValue, playlistId, videosList) {
  isPlaylistBuilderOpen = true;
  editingPlaylistId = String(playlistId || '');
  draftPlaylistVideos = Array.isArray(videosList) ? videosList.map(v => ({ ...v })) : [];
  const panel = document.getElementById('videoPlaylistBuilderPanel');
  const nameInput = document.getElementById('playlistNameInput');
  if (panel) panel.style.display = 'flex';
  if (nameInput) {
    nameInput.value = nameValue || '';
  }
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function closePlaylistBuilder() {
  isPlaylistBuilderOpen = false;
  const panel = document.getElementById('videoPlaylistBuilderPanel');
  if (panel) panel.style.display = 'none';
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  draftPlaylistVideos = cur && Array.isArray(cur.videos) ? cur.videos.map(v => ({ ...v })) : [];
  editingPlaylistId = cur ? cur.id : '';
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function startNewVideoPlaylist() {
  openPlaylistBuilder('', '', []);
  const nameInput = document.getElementById('playlistNameInput');
  if (nameInput && typeof nameInput.focus === 'function') {
    nameInput.focus({ preventScroll: true });
  }
}

function editSelectedPlaylist() {
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  if (!cur) {
    startNewVideoPlaylist();
    return;
  }
  openPlaylistBuilder(cur.name || '', cur.id, cur.videos || []);
}

function clearDraftVideoPlaylist() {
  draftPlaylistVideos = [];
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function renderPlaylistDraftBuilder() {
  const container = document.getElementById('playlistDraftItemsList');
  if (!container) return;
  if (draftPlaylistVideos.length === 0) {
    container.innerHTML = `<div style="padding: 10px 12px; border: 1px dashed rgba(56, 189, 248, 0.3); border-radius: 6px; font-size: 12px; color: var(--text-muted); text-align: center;">No videos in this playlist yet. Click <strong style="color: var(--accent-cyan);">+ Playlist</strong> on any video card below in the order you want them to play!</div>`;
    return;
  }
  container.innerHTML = draftPlaylistVideos.map((v, idx) => {
    const fnSafe = escapeJsAttrStr(v.filename);
    return `
      <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
          <span style="font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 999px; background: rgba(56, 189, 248, 0.18); color: #38bdf8;">#${idx + 1}</span>
          <span style="font-size: 12px; font-weight: 600; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(v.title || v.filename)}</span>
          <span style="font-size: 10.5px; color: var(--text-muted); white-space: nowrap;">(${escapeHtml(v.category || 'FFD Video')})</span>
        </div>
        <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
          <button class="btn" style="font-size: 10.5px; padding: 2px 7px;" onclick="playDraftPlaylistFromIndex(${idx})" title="Play playlist starting from this video">▶</button>
          <button class="btn" style="font-size: 10.5px; padding: 2px 6px;" ${idx === 0 ? 'disabled' : ''} onclick="moveVideoInPlaylistDraft(${idx}, -1)" title="Move up">↑</button>
          <button class="btn" style="font-size: 10.5px; padding: 2px 6px;" ${idx === draftPlaylistVideos.length - 1 ? 'disabled' : ''} onclick="moveVideoInPlaylistDraft(${idx}, 1)" title="Move down">↓</button>
          <button class="btn-delete" style="font-size: 11px; padding: 2px 6px;" onclick="removeVideoFromPlaylistDraft('${fnSafe}')" title="Remove from playlist">✕</button>
        </div>
      </div>
    `;
  }).join('');
}

function addVideoToPlaylistDraft(filename, title, category) {
  if (!isPlaylistBuilderOpen) {
    const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
    if (cur) {
      openPlaylistBuilder(cur.name, cur.id, cur.videos || []);
    } else {
      openPlaylistBuilder('My Custom Workout Playlist', '', []);
    }
  }
  const existingIdx = draftPlaylistVideos.findIndex(v => v.filename === filename);
  if (existingIdx >= 0) {
    draftPlaylistVideos.splice(existingIdx, 1);
  } else {
    draftPlaylistVideos.push({
      filename,
      title: title || filename,
      category: category || 'FFD Video'
    });
  }
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function removeVideoFromPlaylistDraft(filename) {
  draftPlaylistVideos = draftPlaylistVideos.filter(v => v.filename !== filename);
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

function moveVideoInPlaylistDraft(index, delta) {
  const target = index + delta;
  if (target < 0 || target >= draftPlaylistVideos.length) return;
  const temp = draftPlaylistVideos[index];
  draftPlaylistVideos[index] = draftPlaylistVideos[target];
  draftPlaylistVideos[target] = temp;
  renderSavedVideoPlaylistsUI();
  renderExerciseVideos();
}

async function saveCurrentVideoPlaylist() {
  const nameInput = document.getElementById('playlistNameInput');
  const name = (nameInput ? nameInput.value : '').trim();
  if (!name) {
    alert('Please enter a name for your playlist.');
    if (nameInput) nameInput.focus();
    return null;
  }
  if (draftPlaylistVideos.length === 0) {
    alert('Please add at least one video to your playlist by clicking "+ Playlist" on any video card below.');
    return null;
  }
  try {
    const res = await fetch('/api/health/playlists/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        id: editingPlaylistId || undefined,
        name,
        videos: draftPlaylistVideos
      })
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      alert(data.error || 'Failed to save playlist');
      return null;
    }
    if (Array.isArray(data.playlists)) {
      savedVideoPlaylists = data.playlists;
    }
    if (data.playlist && data.playlist.id) {
      selectedVideoPlaylistId = data.playlist.id;
      editingPlaylistId = data.playlist.id;
    }
    isPlaylistBuilderOpen = false;
    const panel = document.getElementById('videoPlaylistBuilderPanel');
    if (panel) panel.style.display = 'none';
    renderSavedVideoPlaylistsUI();
    renderExerciseVideos();
    if (typeof showToast === 'function') {
      showToast(`✅ Saved playlist "${name}" (${draftPlaylistVideos.length} videos)`);
    }
    return data.playlist;
  } catch (err) {
    console.error('Error saving playlist:', err);
    return null;
  }
}

async function saveAndPlayVideoPlaylist() {
  const saved = await saveCurrentVideoPlaylist();
  if (saved && Array.isArray(saved.videos) && saved.videos.length > 0) {
    startPlaylistPlayback(saved, 0);
  }
}

async function deleteSelectedPlaylist() {
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  if (!cur) return;
  try {
    const res = await fetch('/api/health/playlists/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: cur.id, name: cur.name })
    });
    const data = await res.json();
    if (Array.isArray(data.playlists)) {
      savedVideoPlaylists = data.playlists;
    }
    selectedVideoPlaylistId = savedVideoPlaylists.length > 0 ? savedVideoPlaylists[0].id : '';
    closePlaylistBuilder();
    if (typeof showToast === 'function') {
      showToast(`🗑 Deleted playlist "${cur.name}"`);
    }
  } catch (err) {
    console.error('Error deleting playlist:', err);
  }
}

function playSelectedPlaylist() {
  if (isPlaylistBuilderOpen && draftPlaylistVideos.length > 0) {
    const nameInput = document.getElementById('playlistNameInput');
    const tempName = (nameInput && nameInput.value.trim()) || 'Custom Playlist Queue';
    startPlaylistPlayback({ id: editingPlaylistId || 'draft', name: tempName, videos: draftPlaylistVideos.slice() }, 0);
    return;
  }
  const cur = savedVideoPlaylists.find(p => p.id === selectedVideoPlaylistId);
  if (!cur || !Array.isArray(cur.videos) || cur.videos.length === 0) {
    alert('Please select a playlist or click "+ New Playlist" to add videos first.');
    return;
  }
  startPlaylistPlayback(cur, 0);
}

function playDraftPlaylistFromIndex(index) {
  if (draftPlaylistVideos.length === 0) return;
  const nameInput = document.getElementById('playlistNameInput');
  const tempName = (nameInput && nameInput.value.trim()) || 'Custom Playlist Queue';
  startPlaylistPlayback({ id: editingPlaylistId || 'draft', name: tempName, videos: draftPlaylistVideos.slice() }, index);
}

function startPlaylistPlayback(playlistObj, startIndex = 0) {
  if (!playlistObj || !Array.isArray(playlistObj.videos) || playlistObj.videos.length === 0) return;
  activePlaybackPlaylist = {
    id: playlistObj.id || 'custom',
    name: playlistObj.name || 'Video Playlist',
    videos: playlistObj.videos.slice()
  };
  playPlaylistAtIndex(startIndex);
}

function playPlaylistAtIndex(index) {
  if (!activePlaybackPlaylist || !Array.isArray(activePlaybackPlaylist.videos)) return;
  const total = activePlaybackPlaylist.videos.length;
  if (index < 0 || index >= total) return;
  activePlaybackIndex = index;
  const item = activePlaybackPlaylist.videos[index];
  _launchVideoModal(item.filename, item.title || item.filename, item.category || 'FFD Video', true);
  renderModalPlaylistBar();
}

function playNextInPlaylist() {
  if (!activePlaybackPlaylist || !Array.isArray(activePlaybackPlaylist.videos)) return;
  if (activePlaybackIndex + 1 < activePlaybackPlaylist.videos.length) {
    playPlaylistAtIndex(activePlaybackIndex + 1);
  }
}

function playPrevInPlaylist() {
  if (!activePlaybackPlaylist || !Array.isArray(activePlaybackPlaylist.videos)) return;
  if (activePlaybackIndex - 1 >= 0) {
    playPlaylistAtIndex(activePlaybackIndex - 1);
  }
}

function togglePlaylistAutoAdvance() {
  playlistAutoAdvance = !playlistAutoAdvance;
  renderModalPlaylistBar();
}

function renderModalPlaylistBar() {
  const bar = document.getElementById('videoModalPlaylistBar');
  const statusEl = document.getElementById('videoModalPlaylistStatus');
  const prevBtn = document.getElementById('btnPlaylistPrev');
  const nextBtn = document.getElementById('btnPlaylistNext');
  const autoBtn = document.getElementById('btnPlaylistAutoAdvance');
  const tracksEl = document.getElementById('videoModalPlaylistTracks');
  if (!bar) return;

  if (!activePlaybackPlaylist || !Array.isArray(activePlaybackPlaylist.videos) || activePlaybackPlaylist.videos.length === 0) {
    bar.style.display = 'none';
    return;
  }

  bar.style.display = 'flex';
  const videos = activePlaybackPlaylist.videos;
  const total = videos.length;
  const curNum = activePlaybackIndex + 1;
  if (statusEl) {
    statusEl.innerText = `${activePlaybackPlaylist.name} • Playing ${curNum} of ${total}`;
  }
  if (prevBtn) prevBtn.disabled = activePlaybackIndex <= 0;
  if (nextBtn) nextBtn.disabled = activePlaybackIndex >= total - 1;
  if (autoBtn) {
    autoBtn.innerText = `🔁 Auto-Play Next: ${playlistAutoAdvance ? 'ON' : 'OFF'}`;
    autoBtn.style.background = playlistAutoAdvance ? 'rgba(16, 185, 129, 0.16)' : 'rgba(148, 163, 184, 0.12)';
    autoBtn.style.borderColor = playlistAutoAdvance ? 'rgba(16, 185, 129, 0.45)' : 'rgba(148, 163, 184, 0.3)';
    autoBtn.style.color = playlistAutoAdvance ? '#34d399' : 'var(--text-muted)';
  }
  if (tracksEl) {
    tracksEl.innerHTML = videos.map((v, idx) => {
      const isCur = idx === activePlaybackIndex;
      const chipStyle = isCur
        ? 'background: rgba(56, 189, 248, 0.24); border: 1px solid #38bdf8; color: #fff; font-weight: 700;'
        : 'background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.12); color: var(--text-muted);';
      return `<button class="btn" onclick="playPlaylistAtIndex(${idx})" style="font-size: 11px; padding: 3px 9px; white-space: nowrap; ${chipStyle}">${isCur ? '▶ ' : ''}${idx + 1}. ${escapeHtml(v.title || v.filename)}</button>`;
    }).join('');
  }
}

function escapeJsAttrStr(str) {
  return String(str || '')
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '&quot;')
    .replace(/\r?\n/g, ' ');
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
      : `${icon} ${escapeHtml(cat)}`;
    const isActive = currentExerciseCategory === cat ? 'active' : '';
    const safeCat = escapeJsAttrStr(cat);

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

function _getVideoCardTheme(category, videoType) {
  const map = {
    "World's Best Warm-Up & Mobility": { icon: '🔥', bg: 'linear-gradient(135deg, #1e1b4b 0%, #7c2d12 55%, #0f172a 100%)', accent: '#fb923c' },
    'Super Brain Yoga & Flexibility': { icon: '🧠', bg: 'linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #020617 100%)', accent: '#38bdf8' },
    'Surya Namaskar Series': { icon: '🧘', bg: 'linear-gradient(135deg, #064e3b 0%, #0f766e 55%, #0f172a 100%)', accent: '#34d399' },
    'Nitric Oxide Dump (NOD)': { icon: '💨', bg: 'linear-gradient(135deg, #0c4a6e 0%, #0369a1 55%, #0f172a 100%)', accent: '#38bdf8' },
    'Upper Body & Strength': { icon: '💪', bg: 'linear-gradient(135deg, #311042 0%, #6b21a8 55%, #0f172a 100%)', accent: '#c084fc' },
    'Anti-Gravity & Glucose Drop': { icon: '🏃‍♂️', bg: 'linear-gradient(135deg, #064e3b 0%, #0284c7 55%, #0f172a 100%)', accent: '#2dd4bf' },
    'Weighted Walking & Aerobic': { icon: '🚶‍♂️', bg: 'linear-gradient(135deg, #1e293b 0%, #0f766e 55%, #020617 100%)', accent: '#34d399' },
    'Desk & Office Conditioning': { icon: '🪑', bg: 'linear-gradient(135deg, #1e1b4b 0%, #3730a3 55%, #0f172a 100%)', accent: '#818cf8' },
    'Smoothies & Green Drinks': { icon: '🥤', bg: 'linear-gradient(135deg, #052e16 0%, #15803d 55%, #0f172a 100%)', accent: '#4ade80' },
    'Vitamins & Micronutrients': { icon: '💊', bg: 'linear-gradient(135deg, #422006 0%, #b45309 55%, #0f172a 100%)', accent: '#fbbf24' },
    'Tea, Coffee & Beverages': { icon: '☕', bg: 'linear-gradient(135deg, #27170e 0%, #78350f 55%, #0f172a 100%)', accent: '#f59e0b' }
  };
  return map[category] || {
    icon: videoType === 'diet' ? '🥗' : '🏋️‍♂️',
    bg: 'linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #020617 100%)',
    accent: '#38bdf8'
  };
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
    const cleanTitle = escapeJsAttrStr(title);
    const filenameSafe = escapeJsAttrStr(v.filename);
    const catSafe = escapeJsAttrStr(v.category || 'FFD Video');
    const theme = _getVideoCardTheme(v.category, v.video_type);
    const playlistPos = getVideoPlaylistPosition(v.filename);
    const playlistBtnHtml = playlistPos > 0
      ? `<button class="btn" title="In playlist (#${playlistPos}) — click to remove from queue" style="font-size: 11px; padding: 5px 8px; background: rgba(16, 185, 129, 0.16); border-color: rgba(16, 185, 129, 0.45); color: #34d399; font-weight: 600;" onclick="addVideoToPlaylistDraft('${filenameSafe}', '${cleanTitle}', '${catSafe}')">✓ #${playlistPos}</button>`
      : `<button class="btn" title="Add video to playlist" style="font-size: 11px; padding: 5px 8px; border-color: rgba(56, 189, 248, 0.4); color: #38bdf8;" onclick="addVideoToPlaylistDraft('${filenameSafe}', '${cleanTitle}', '${catSafe}')">+ Playlist</button>`;

    return `
      <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; justify-content: space-between; transition: transform 0.15s, border-color 0.15s;">
        <div>
          <!-- Zero-Stream Instant Visual Preview Card (prevents HTTP connection & decoder exhaustion) -->
          <div onclick="playExerciseVideo('${filenameSafe}', '${cleanTitle}', '${catSafe}')" style="position: relative; width: 100%; height: 130px; background: ${theme.bg}; border-radius: 6px; overflow: hidden; margin-bottom: 10px; cursor: pointer; border: 1px solid rgba(255,255,255,0.1);" title="Click to play video">
            <div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; opacity: 0.18; font-size: 64px; pointer-events: none;">${theme.icon}</div>
            <div style="position: absolute; inset: 0; background: radial-gradient(circle at center, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.55) 100%); display: flex; align-items: center; justify-content: center;">
              <div style="width: 42px; height: 42px; border-radius: 50%; background: rgba(0, 242, 254, 0.92); display: flex; align-items: center; justify-content: center; color: #000; font-size: 16px; font-weight: bold; box-shadow: 0 4px 16px rgba(0,0,0,0.65);">▶</div>
            </div>
            <span style="position: absolute; bottom: 6px; right: 8px; font-size: 10px; background: rgba(0,0,0,0.85); color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: 600;">${v.size_mb || 0} MB</span>
            <span style="position: absolute; top: 6px; left: 8px; font-size: 9.5px; background: rgba(0, 0, 0, 0.55); border: 1px solid ${theme.accent}; color: ${theme.accent}; padding: 1px 6px; border-radius: 4px; font-weight: 600;">${theme.icon} ${escapeHtml(v.category)}</span>
          </div>

          <!-- Title -->
          <div style="font-size: 12.5px; font-weight: 600; color: #fff; line-height: 1.35; margin-bottom: 6px;">${escapeHtml(title)}</div>
        </div>

        <!-- Action Buttons -->
        <div style="display: flex; gap: 6px; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 8px;">
          <button class="btn btn-primary" style="flex: 1; font-size: 11px; padding: 5px 8px; display: flex; align-items: center; justify-content: center; gap: 4px;" onclick="playExerciseVideo('${filenameSafe}', '${cleanTitle}', '${catSafe}')">
            ▶ Watch
          </button>
          ${playlistBtnHtml}
          <button class="btn" title="Open in Windows Media Player" style="font-size: 11px; padding: 5px 8px;" onclick="openVideoInSystem('${filenameSafe}')">
            🖥 Open
          </button>
        </div>
      </div>
    `;
  }).join('');
}

function _launchVideoModal(filename, title, category, keepPlaylistMode = false) {
  if (!keepPlaylistMode) {
    activePlaybackPlaylist = null;
    activePlaybackIndex = -1;
    renderModalPlaylistBar();
  }
  currentPlayingVideo = filename;
  const modal = document.getElementById('exerciseVideoModal');
  const modalTitle = document.getElementById('videoModalTitle');
  const modalCat = document.getElementById('videoModalCategory');
  const modalPath = document.getElementById('videoModalPath');
  const statusBanner = document.getElementById('videoModalStatusBanner');
  const statusText = document.getElementById('videoModalStatusText');
  const player = document.getElementById('exerciseVideoPlayer');

  if (modalTitle) modalTitle.innerText = title || filename;
  if (modalCat) modalCat.innerText = category || 'FFD Video';
  if (modalPath) modalPath.innerText = './data/videos/' + filename;
  if (statusBanner) statusBanner.style.display = 'none';

  // Ensure any other video element on the page is paused/released so the modal player has exclusive decoder & HTTP access
  document.querySelectorAll('video').forEach(vEl => {
    if (vEl !== player) {
      try {
        vEl.pause();
        vEl.removeAttribute('src');
        vEl.load();
      } catch (_) {}
    }
  });

  if (modal) modal.style.display = 'flex';

  if (player) {
    player.onended = () => {
      if (
        activePlaybackPlaylist
        && Array.isArray(activePlaybackPlaylist.videos)
        && playlistAutoAdvance
        && activePlaybackIndex + 1 < activePlaybackPlaylist.videos.length
      ) {
        playPlaylistAtIndex(activePlaybackIndex + 1);
      }
    };
    player.onerror = () => {
      if (statusBanner && statusText) {
        statusBanner.style.display = 'flex';
        statusText.innerText = '⚠️ Browser HTML5 video decoder could not render this stream directly. Click "Play in Windows Media Player" to watch.';
      }
    };
    player.onloadeddata = () => {
      if (statusBanner) statusBanner.style.display = 'none';
    };
    player.pause();
    player.src = '/api/health/video/stream?file=' + encodeURIComponent(filename);
    player.load();
    const playPromise = player.play();
    if (playPromise && typeof playPromise.catch === 'function') {
      playPromise.catch(e => {
        console.log('Autoplay paused or awaiting user click:', e);
      });
    }
  }
}

function playExerciseVideo(filename, title, category) {
  _launchVideoModal(filename, title, category, false);
}

function closeVideoModal() {
  const modal = document.getElementById('exerciseVideoModal');
  const player = document.getElementById('exerciseVideoPlayer');
  const statusBanner = document.getElementById('videoModalStatusBanner');
  if (player) {
    player.onended = null;
    player.onerror = null;
    player.onloadeddata = null;
    player.pause();
    player.removeAttribute('src');
    player.load();
  }
  if (statusBanner) statusBanner.style.display = 'none';
  if (modal) modal.style.display = 'none';
  currentPlayingVideo = null;
  activePlaybackPlaylist = null;
  activePlaybackIndex = -1;
}

async function openVideoVaultFolder() {
  try {
    const res = await fetch('/api/health/video/open_folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (data.status === 'opened' || data.ok) {
      if (typeof showToast === 'function') {
        showToast('📂 Opened Video Vault folder in File Explorer');
      }
    } else {
      alert('Could not open Video Vault folder: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    console.error('Error opening Video Vault folder:', err);
  }
}

async function openCurrentVideoInSystem() {
  if (!currentPlayingVideo) return;
  await openVideoInSystem(currentPlayingVideo);
}

async function openVideoInSystem(filename) {
  try {
    const res = await fetch('/api/health/video/open_system?file=' + encodeURIComponent(filename), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename })
    });
    const data = await res.json();
    if (data.status === 'opened' || data.status === 'ok' || data.ok) {
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

// Attach all video, playlist & strength functions to window
window.switchExSubTab = switchExSubTab;
window.switchVideoType = switchVideoType;
window.fetchExerciseVideos = fetchExerciseVideos;
window.fetchVideoPlaylists = fetchVideoPlaylists;
window.onSelectSavedVideoPlaylist = onSelectSavedVideoPlaylist;
window.startNewVideoPlaylist = startNewVideoPlaylist;
window.editSelectedPlaylist = editSelectedPlaylist;
window.closePlaylistBuilder = closePlaylistBuilder;
window.clearDraftVideoPlaylist = clearDraftVideoPlaylist;
window.addVideoToPlaylistDraft = addVideoToPlaylistDraft;
window.removeVideoFromPlaylistDraft = removeVideoFromPlaylistDraft;
window.moveVideoInPlaylistDraft = moveVideoInPlaylistDraft;
window.saveCurrentVideoPlaylist = saveCurrentVideoPlaylist;
window.saveAndPlayVideoPlaylist = saveAndPlayVideoPlaylist;
window.deleteSelectedPlaylist = deleteSelectedPlaylist;
window.playSelectedPlaylist = playSelectedPlaylist;
window.playDraftPlaylistFromIndex = playDraftPlaylistFromIndex;
window.playPlaylistAtIndex = playPlaylistAtIndex;
window.playNextInPlaylist = playNextInPlaylist;
window.playPrevInPlaylist = playPrevInPlaylist;
window.togglePlaylistAutoAdvance = togglePlaylistAutoAdvance;
window.renderVideoCategoryFilters = renderVideoCategoryFilters;
window.filterVideoCategory = filterVideoCategory;
window.renderExerciseVideos = renderExerciseVideos;
window.playExerciseVideo = playExerciseVideo;
window.closeVideoModal = closeVideoModal;
window.openVideoVaultFolder = openVideoVaultFolder;
window.openCurrentVideoInSystem = openCurrentVideoInSystem;
window.openVideoInSystem = openVideoInSystem;
