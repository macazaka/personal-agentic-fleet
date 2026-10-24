// --- Unit Test Suite & Code Coverage Card ---
    async function fetchTestResults() {
      try {
        const res = await fetch('/api/test_results');
        const data = await res.json();
        if (!data || data.error) return;

        const passPct = data.pass_pct !== undefined ? data.pass_pct : 100.0;
        const total = data.total_tests || 0;
        const passed = data.passed_tests || 0;
        const cov = data.coverage_pct !== undefined ? data.coverage_pct : 98.0;
        const dur = data.duration_sec !== undefined ? data.duration_sec + 's' : '-';
        const ts = data.timestamp || '-';
        const status = data.status || 'PASS';

        document.getElementById('testPassPct').innerText = `${passPct}%`;
        document.getElementById('testRunCount').innerText = `${passed} / ${total}`;
        document.getElementById('testCoveragePct').innerText = `${cov}%`;
        document.getElementById('testDuration').innerText = dur;
        document.getElementById('testLastRun').innerText = ts;

        const badge = document.getElementById('testStatusBadge');
        if (badge) {
          badge.innerText = status;
          if (status === 'PASS') {
            badge.style.background = 'rgba(16, 185, 129, 0.15)';
            badge.style.color = 'var(--accent-green)';
            badge.style.borderColor = 'rgba(16, 185, 129, 0.3)';
          } else {
            badge.style.background = 'rgba(244, 63, 94, 0.15)';
            badge.style.color = 'var(--accent-pink)';
            badge.style.borderColor = 'rgba(244, 63, 94, 0.3)';
          }
        }
      } catch (e) {
        console.error('Error fetching test results:', e);
      }
    }

    async function runTestsNow() {
      const btn = document.getElementById('btnRunTests');
      btn.innerText = '⏳ Running Tests...';
      btn.disabled = true;
      try {
        const res = await fetch('/api/run_tests', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'}
        });
        await fetchTestResults();
        await fetchLogs();
      } catch (e) {
        console.error('Error running tests:', e);
      } finally {
        btn.innerText = '⚡ Run Tests Now';
        btn.disabled = false;
      }
    }

    // --- Feature Backlog Management ---

window.fetchTestResults = fetchTestResults;
window.runTestsNow = runTestsNow;
