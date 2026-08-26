document.addEventListener('DOMContentLoaded', () => {
  let timelineChart = null;
  let driftRadarChart = null;
  let contextChart = null;
  let qualityScatterChart = null;

  let currentProject = 'antigravity-live';
  let currentEnv = 'prod';
  let isLoadingDashboard = false;
  const apiKeyInput = document.getElementById('dashboard-api-key');
  if (apiKeyInput) apiKeyInput.value = window.localStorage.getItem('driftguard_api_key') || '';

  function requestHeaders() {
    const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
    return apiKey ? { 'X-API-Key': apiKey } : {};
  }

  const projectModal = document.getElementById('project-modal');
  const createProjectBtn = document.getElementById('create-project-btn');
  const closeProjectModalBtn = document.getElementById('close-project-modal-btn');
  const cancelProjectModalBtn = document.getElementById('cancel-project-modal-btn');
  const projectForm = document.getElementById('project-form');
  const projectCreateStatus = document.getElementById('project-create-status');

  function closeProjectModal() {
    if (projectModal) projectModal.classList.add('hidden');
  }

  if (createProjectBtn && projectModal) {
    createProjectBtn.addEventListener('click', () => projectModal.classList.remove('hidden'));
  }
  if (closeProjectModalBtn) closeProjectModalBtn.addEventListener('click', closeProjectModal);
  if (cancelProjectModalBtn) cancelProjectModalBtn.addEventListener('click', closeProjectModal);

  if (projectForm) {
    projectForm.addEventListener('submit', async (event) => {
      event.preventDefault();
      if (!projectForm.checkValidity()) {
        projectForm.reportValidity();
        return;
      }
      const submitButton = projectForm.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;
      const payload = {
        project_id: document.getElementById('new-project-id').value.trim(),
        name: document.getElementById('new-project-name').value.trim(),
        environment: document.getElementById('new-project-environment').value
      };

      try {
        const response = await fetch('/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `Project creation failed (${response.status})`);

        currentProject = result.project_id;
        if (apiKeyInput) {
          apiKeyInput.value = result.api_key;
          window.localStorage.setItem('driftguard_api_key', result.api_key);
        }
        if (projectCreateStatus) {
          projectCreateStatus.textContent = 'Project created. The generated key is now active in this dashboard.';
          projectCreateStatus.style.color = '#FFFFFF';
        }
        setStatus('Project created and connected');
        closeProjectModal();
        await loadProjects();
        if (projectSelect) projectSelect.value = currentProject;
        await loadDashboardData();
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Project creation failed. Please try again.';
        if (projectCreateStatus) {
          projectCreateStatus.textContent = message;
          projectCreateStatus.style.color = '#FDA4AF';
        }
        setStatus(message, true);
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  function setStatus(message, isError = false) {
    const status = document.getElementById('dashboard-status');
    if (!status) return;
    status.textContent = message;
    status.classList.toggle('status-error', isError);
    status.classList.add('visible');
    window.clearTimeout(setStatus.timer);
    setStatus.timer = window.setTimeout(() => status.classList.remove('visible'), 3500);
  }

  function setLoading(loading) {
    isLoadingDashboard = loading;
    const indicator = document.getElementById('dashboard-loading-indicator');
    const mainContent = document.querySelector('.main-content');
    const refreshButton = document.getElementById('refresh-btn');
    if (indicator) indicator.hidden = !loading;
    if (mainContent) mainContent.setAttribute('aria-busy', String(loading));
    if (refreshButton) refreshButton.disabled = loading;
  }

  async function responseError(response, fallbackMessage) {
    let detail = '';
    try {
      const payload = await response.json();
      detail = payload.detail || '';
    } catch (error) {
      // The backend may return an empty or non-JSON response for infrastructure errors.
    }

    if (response.status === 401 || response.status === 403) {
      return 'Access denied. Check that the selected project and DriftGuard API key match.';
    }
    if (response.status === 404) {
      return 'Project not found. Create or select an available project.';
    }
    return detail || `${fallbackMessage} (${response.status})`;
  }

  // ---------------------------------------------------------------------------
  // Anime.js Micro-Animations
  // ---------------------------------------------------------------------------
  function animateCards() {
    if (typeof anime !== 'undefined') {
      anime({
        targets: '.anime-card, .anime-panel',
        translateY: [8, 0],
        opacity: [0, 1],
        delay: anime.stagger(60),
        duration: 420,
        easing: 'easeOutQuad'
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Navigation Tab Switching with Anime.js Effects
  // ---------------------------------------------------------------------------
  const navItems = document.querySelectorAll('.nav-item');
  const tabContents = document.querySelectorAll('.tab-content');
  const pageTitle = document.getElementById('page-title');

  window.switchTab = (tabId) => {
    navItems.forEach(item => {
      if (item.dataset.tab === tabId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    tabContents.forEach(tab => {
      if (tab.id === `tab-${tabId}`) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    const titles = {
      overview: 'Operational Overview',
      alerts: 'Complete Drift Alerts Feed',
      analytics: 'Drift & Quality Analytics',
      policy: 'Mitigation Rules & Policies',
      quickstart: 'SDK Quickstart Integration'
    };
    if (pageTitle && titles[tabId]) {
      pageTitle.textContent = titles[tabId];
    }

    animateCards();
  };

  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const tabId = item.dataset.tab;
      switchTab(tabId);
    });
  });

  // ---------------------------------------------------------------------------
  // Modal & Event Simulation Buttons
  // ---------------------------------------------------------------------------
  const modal = document.getElementById('ingest-modal');
  const simulateBtn = document.getElementById('simulate-event-btn');
  const closeModalBtn = document.getElementById('close-modal-btn');
  const cancelModalBtn = document.getElementById('cancel-modal-btn');
  const telemetryForm = document.getElementById('telemetry-form');

  if (simulateBtn) {
    simulateBtn.addEventListener('click', () => {
      modal.classList.remove('hidden');
      if (typeof anime !== 'undefined') {
        anime({
          targets: '.modal-box',
          scale: [0.85, 1],
          opacity: [0, 1],
          duration: 300,
          easing: 'easeOutBack'
        });
      }
    });
  }

  if (closeModalBtn) closeModalBtn.addEventListener('click', () => modal.classList.add('hidden'));
  if (cancelModalBtn) cancelModalBtn.addEventListener('click', () => modal.classList.add('hidden'));

  if (telemetryForm) {
    telemetryForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!telemetryForm.checkValidity()) {
        telemetryForm.reportValidity();
        return;
      }
      const submitButton = telemetryForm.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;
      const eventData = {
        prompt_tokens: parseFloat(document.getElementById('input-prompt-tokens').value),
        context_length: parseFloat(document.getElementById('input-context-length').value),
        retrieval_score: parseFloat(document.getElementById('input-retrieval-score').value),
        response_quality: parseFloat(document.getElementById('input-response-quality').value),
        environment: currentEnv
      };

      try {
        const response = await fetch(`/projects/${currentProject}/events`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...requestHeaders() },
          body: JSON.stringify(eventData)
        });

        if (!response.ok) throw new Error(`Telemetry request failed (${response.status})`);

        modal.classList.add('hidden');
        setStatus('Telemetry event posted');
        loadDashboardData();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Telemetry event failed. Please try again.';
        console.error('Failed to send telemetry event:', err);
        setStatus(message, true);
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Policy Rules Save Form Button
  // ---------------------------------------------------------------------------
  const policyForm = document.getElementById('policy-form');
  const policyStatus = document.getElementById('policy-save-status');

  if (policyForm) {
    policyForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!policyForm.checkValidity()) {
        policyForm.reportValidity();
        return;
      }
      const submitButton = policyForm.querySelector('button[type="submit"]');
      if (submitButton) submitButton.disabled = true;
      const updates = {
        prompt_token_limit: parseFloat(document.getElementById('policy-prompt-limit').value),
        context_length_limit: parseFloat(document.getElementById('policy-context-limit').value),
        retrieval_score_floor: parseFloat(document.getElementById('policy-retrieval-floor').value),
        response_quality_floor: parseFloat(document.getElementById('policy-quality-floor').value)
      };

      try {
        const response = await fetch(`/projects/${currentProject}/policy`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...requestHeaders() },
          body: JSON.stringify(updates)
        });
        if (!response.ok) throw new Error(`Policy request failed (${response.status})`);
        if (policyStatus) {
          policyStatus.textContent = 'Policy rules saved successfully';
          policyStatus.style.color = '#FFFFFF';
          setTimeout(() => policyStatus.textContent = '', 3000);
        }
        setStatus('Policy updated');
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Policy update failed. Please try again.';
        if (policyStatus) {
          policyStatus.textContent = `✕ ${message}`;
          policyStatus.style.color = '#FDA4AF';
        }
        setStatus(message, true);
      } finally {
        if (submitButton) submitButton.disabled = false;
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Styled Dropdowns (Project & Environment)
  // ---------------------------------------------------------------------------
  async function loadProjects() {
    const select = document.getElementById('project-select');
    if (select) select.disabled = true;
    try {
      const res = await fetch('/projects', { headers: requestHeaders() });
      if (!res.ok) throw new Error(await responseError(res, 'Project list unavailable'));
      const projects = await res.json();
      if (projects && projects.length > 0) {
        if (select) {
          select.innerHTML = projects.map(p =>
            `<option value="${p.project_id}">${p.name} (${p.project_id})</option>`
          ).join('');
        }

        const found = projects.find(p => p.project_id === 'antigravity-live');
        currentProject = found ? found.project_id : projects[0].project_id;
        if (select) select.value = currentProject;
      } else {
        currentProject = '';
        if (select) {
          select.innerHTML = '<option value="">No projects available</option>';
          select.value = '';
        }
        setStatus('No projects found. Create a project to begin.', false);
      }
    } catch (err) {
      currentProject = '';
      if (select) select.innerHTML = '<option value="">Unable to load projects</option>';
      const message = err instanceof Error ? err.message : 'Unable to load projects.';
      console.warn('Failed to fetch projects list:', err);
      setStatus(message, true);
    } finally {
      if (select) select.disabled = false;
    }
  }

  const projectSelect = document.getElementById('project-select');
  if (projectSelect) {
    projectSelect.addEventListener('change', (e) => {
      currentProject = e.target.value;
      if (currentProject) {
        loadDashboardData();
      } else {
        renderEmptyDashboard('Select a project or create one to view telemetry.');
      }
    });
  }

  if (apiKeyInput) {
    apiKeyInput.addEventListener('change', () => {
      window.localStorage.setItem('driftguard_api_key', apiKeyInput.value.trim());
      loadProjects().then(loadDashboardData);
    });
  }

  const envSelect = document.getElementById('env-select');
  if (envSelect) {
    envSelect.addEventListener('change', (e) => {
      currentEnv = e.target.value;
      loadDashboardData();
    });
  }

  // ---------------------------------------------------------------------------
  // Refresh Data Button
  // ---------------------------------------------------------------------------
  const refreshBtn = document.getElementById('refresh-btn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (typeof anime !== 'undefined') {
        anime({
          targets: '#refresh-btn',
          rotate: '1turn',
          duration: 400,
          easing: 'easeInOutQuad'
        });
      }
      loadDashboardData();
    });
  }

  // ---------------------------------------------------------------------------
  // Load Main Telemetry & Dashboard Data
  // ---------------------------------------------------------------------------
  function renderEmptyDashboard(message = 'No telemetry recorded for this project.') {
    updateMetrics(null, [], []);
    renderRecentAlerts([]);
    renderAlertsTable([]);
    renderCharts([]);
    renderAgentDiagnosis(null);
    const diagnosisMessage = document.getElementById('diagnosis-message');
    if (diagnosisMessage) diagnosisMessage.textContent = message;
  }

  async function loadDashboardData() {
    if (!currentProject) {
      setLoading(false);
      renderEmptyDashboard('Select a project or create one to view telemetry.');
      return;
    }

    setLoading(true);
    setStatus('Loading dashboard data…');
    try {
      const responses = await Promise.all([
        fetch(`/projects/${currentProject}/summary`, { headers: requestHeaders() }),
        fetch(`/events/${currentProject}`, { headers: requestHeaders() }),
        fetch(`/alerts/${currentProject}`, { headers: requestHeaders() }),
        fetch(`/projects/${currentProject}/agent-diagnosis`, { headers: requestHeaders() })
      ]);

      const [summaryRes, eventsRes, alertsRes, diagnosisRes] = responses;
      for (const [response, label] of [
        [summaryRes, 'Dashboard summary unavailable'],
        [eventsRes, 'Telemetry unavailable'],
        [alertsRes, 'Alerts unavailable'],
        [diagnosisRes, 'Agent diagnosis unavailable']
      ]) {
        if (!response.ok) throw new Error(await responseError(response, label));
      }

      const [summary, events, alerts, diagnosis] = await Promise.all(
        responses.map(response => response.json())
      );
      updateMetrics(summary, events, alerts);
      renderRecentAlerts(alerts);
      renderAlertsTable(alerts);
      renderCharts(events);
      renderAgentDiagnosis(diagnosis);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Dashboard data unavailable. Please try again.';
      console.warn('Backend API fetching:', err);
      renderEmptyDashboard('Data could not be loaded. Check the project key and backend connection.');
      setStatus(message, true);
    } finally {
      setLoading(false);
    }
  }

  function renderAgentDiagnosis(diagnosis) {
    const status = document.getElementById('agent-diagnosis-status');
    const tool = document.getElementById('diagnosis-tool');
    const failures = document.getElementById('diagnosis-failures');
    const retries = document.getElementById('diagnosis-retries');
    const wastedTokens = document.getElementById('diagnosis-wasted-tokens');
    const message = document.getElementById('diagnosis-message');
    const recommendation = document.getElementById('diagnosis-recommendation');
    if (!status) return;
    if (!diagnosis) {
      status.textContent = 'NO DATA';
      status.className = 'diagnosis-badge diagnosis-stable';
      if (tool) tool.textContent = 'None';
      if (failures) failures.textContent = '0';
      if (retries) retries.textContent = '0';
      if (wastedTokens) wastedTokens.textContent = '0';
      if (message) message.textContent = 'No agent task diagnosis is available.';
      if (recommendation) recommendation.textContent = '';
      return;
    }

    status.textContent = diagnosis.status ? diagnosis.status.toUpperCase() : 'NO DATA';
    status.className = `diagnosis-badge diagnosis-${diagnosis.status || 'stable'}`;
    tool.textContent = diagnosis.blocking_tool || 'None';
    failures.textContent = diagnosis.failure_count ?? 0;
    retries.textContent = diagnosis.repeated_attempts ?? 0;
    wastedTokens.textContent = Number(diagnosis.wasted_tokens || 0).toLocaleString();
    message.textContent = diagnosis.diagnosis || 'No agent task diagnosis is available.';
    recommendation.textContent = diagnosis.recommendation || '';
  }

  function updateMetrics(summary, events, alerts) {
    const totalEvents = events ? events.length : 0;
    const totalSavedTokens = alerts ? alerts.reduce((acc, a) => acc + (a.saved_tokens || 0), 0) : 0;
    const activeAlerts = alerts ? alerts.length : 0;
    const criticalAlerts = alerts ? alerts.filter(a => a.severity === 'critical' || a.severity === 'warning').length : 0;

    let avgRetrieval = 0;
    if (events && events.length > 0) {
      const sum = events.reduce((acc, e) => acc + (e.retrieval_score || 0), 0);
      avgRetrieval = sum / events.length;
    }

    const totalEvtEl = document.getElementById('metric-total-events');
    const savedTokEl = document.getElementById('metric-saved-tokens');
    const savedCostEl = document.getElementById('metric-saved-cost');
    const activeAltEl = document.getElementById('metric-active-alerts');
    const critAltEl = document.getElementById('metric-critical-alerts');
    const retValEl = document.getElementById('metric-retrieval-score');
    const alertBadgeEl = document.getElementById('alert-count-badge');

    if (totalEvtEl) totalEvtEl.textContent = totalEvents.toLocaleString();
    if (savedTokEl) savedTokEl.textContent = totalSavedTokens >= 1000000 ? `${(totalSavedTokens / 1000000).toFixed(1)}M` : totalSavedTokens.toLocaleString();
    if (savedCostEl) savedCostEl.textContent = `+$${(totalSavedTokens * 0.00002).toFixed(2)} saved`;
    if (activeAltEl) activeAltEl.textContent = activeAlerts;
    if (critAltEl) critAltEl.textContent = `${criticalAlerts} critical requiring action`;
    if (retValEl) retValEl.textContent = avgRetrieval.toFixed(2);
    if (alertBadgeEl) alertBadgeEl.textContent = activeAlerts;
  }

  function renderRecentAlerts(alerts) {
    const stack = document.getElementById('overview-alerts-tbody');
    if (!stack) return;

    const sampleAlerts = alerts || [];

    if (sampleAlerts.length === 0) {
      stack.innerHTML = '<div class="empty-state"><strong>No alerts recorded</strong><span>Alerts for the selected project will appear here.</span></div>';
      return;
    }

    stack.innerHTML = sampleAlerts.slice(0, 3).map(a => {
      const isWarning = a.severity === 'critical' || a.severity === 'warning';
      const icon = isWarning ? 'WARNING' : 'INFO';
      return `
        <div class="alert-item ${isWarning ? 'alert-warning' : ''}">
          <div class="alert-item-icon">${icon}</div>
          <div class="alert-item-body">
            <div class="alert-item-title">${a.message}</div>
            <div class="alert-item-sub">${a.sub || `Project: ${currentProject}`}</div>
          </div>
          <div class="alert-item-time">${a.time || 'Live'}</div>
        </div>
      `;
    }).join('');
  }

  function renderAlertsTable(alerts) {
    const alertsTbody = document.getElementById('alerts-tbody');
    if (!alertsTbody) return;

    const sampleAlerts = (alerts && alerts.length > 0) ? alerts : [];

    if (sampleAlerts.length === 0) {
      alertsTbody.innerHTML = `<tr><td colspan="6" class="empty-table-state">No alerts recorded for the selected project.</td></tr>`;
    } else {
      alertsTbody.innerHTML = sampleAlerts.map((a, i) => `
        <tr>
          <td style="font-family: var(--font-mono); color:#A1A1AA;">alt_${i + 1}</td>
          <td><span style="color: #FFFFFF; font-weight: 800;">${a.severity.toUpperCase()}</span></td>
          <td>${currentProject} (${currentEnv})</td>
          <td>${a.message}</td>
          <td style="font-weight: 800; color: #FFFFFF;">+${a.saved_tokens}</td>
          <td style="font-family: var(--font-mono); color:#A1A1AA;">Live</td>
        </tr>
      `).join('');
    }
  }

  function renderCharts(events) {
    const elTimeline = document.getElementById('timelineChart');
    const elRadar = document.getElementById('driftRadarChart');
    const elContext = document.getElementById('contextChart');
    const elScatter = document.getElementById('qualityScatterChart');

    const realEvents = (events && events.length > 0) ? events : [];
    
    const labels = realEvents.map((_, i) => `Event ${realEvents.length - i}`);
    const tokenData = realEvents.map(e => e.prompt_tokens || 0);
    const retrievalData = realEvents.map(e => e.retrieval_score ?? null);
    const qualityData = realEvents.map(e => e.response_quality ?? null);

    if (!realEvents.length) {
      [elTimeline, elRadar, elContext, elScatter].forEach(canvas => {
        if (canvas) {
          canvas.style.display = 'none';
          const emptyState = document.createElement('div');
          emptyState.className = 'empty-state chart-empty-state';
          emptyState.textContent = 'No telemetry recorded for this project.';
          canvas.parentElement.appendChild(emptyState);
        }
      });
      return;
    }

    [elTimeline, elRadar, elContext, elScatter].forEach(canvas => {
      if (canvas) {
        canvas.style.display = '';
        const emptyState = canvas.parentElement.querySelector('.chart-empty-state');
        if (emptyState) emptyState.remove();
      }
    });

    if (elTimeline) {
      const ctxTimeline = elTimeline.getContext('2d');
      if (timelineChart) timelineChart.destroy();
      timelineChart = new Chart(ctxTimeline, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Prompt Tokens',
              data: tokenData,
              borderColor: '#FFFFFF',
              backgroundColor: 'rgba(255, 255, 255, 0.08)',
              borderWidth: 2.5,
              yAxisID: 'y',
              tension: 0.4,
              fill: false
            },
            {
              label: 'Retrieval Score',
              data: retrievalData,
              borderColor: '#A1A1AA',
              borderWidth: 2.5,
              yAxisID: 'y1',
              tension: 0.4,
              fill: false
            },
            {
              label: 'Quality Score',
              data: qualityData,
              borderColor: '#D4D4D8',
              borderWidth: 2.5,
              yAxisID: 'y1',
              tension: 0.4,
              fill: false
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#A1A1AA', font: { family: 'JetBrains Mono', size: 10 } } },
            y: { type: 'linear', position: 'left', grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#A1A1AA', font: { family: 'JetBrains Mono', size: 10 } } },
            y1: { type: 'linear', position: 'right', min: 0, max: 1, grid: { drawOnChartArea: false }, ticks: { color: '#A1A1AA', font: { family: 'JetBrains Mono', size: 10 } } }
          }
        }
      });
    }

    if (elRadar) {
      const ctxRadar = elRadar.getContext('2d');
      if (driftRadarChart) driftRadarChart.destroy();
      driftRadarChart = new Chart(ctxRadar, {
        type: 'radar',
        data: {
          labels: ['Prompt Drift', 'Retrieval Shift', 'Quality Loss', 'Context Bloat', 'Latency Risk'],
          datasets: [{
            label: 'Risk Vector',
            data: [
              Math.min(1, Math.max(...realEvents.map(e => e.prompt_tokens || 0)) / 3000),
              1 - (realEvents.reduce((sum, e) => sum + (e.retrieval_score ?? 1), 0) / realEvents.length),
              1 - (realEvents.reduce((sum, e) => sum + (e.response_quality ?? 1), 0) / realEvents.length),
              Math.min(1, Math.max(...realEvents.map(e => e.context_length || 0)) / 4000),
              null
            ],
            borderColor: '#FFFFFF',
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            borderWidth: 2.5
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            r: {
              angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
              grid: { color: 'rgba(255, 255, 255, 0.1)' },
              pointLabels: { color: '#F4F4F5', font: { family: 'Plus Jakarta Sans', size: 10, weight: 'bold' } },
              ticks: { display: false }
            }
          }
        }
      });
    }

    if (elContext) {
      const ctxContext = elContext.getContext('2d');
      if (contextChart) contextChart.destroy();
      contextChart = new Chart(ctxContext, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: 'Context Length',
            data: realEvents.map(e => e.context_length || 0),
            backgroundColor: '#D4D4D8',
            borderRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { grid: { display: false }, ticks: { color: '#A1A1AA' } },
            y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#A1A1AA' } }
          }
        }
      });
    }

    if (elScatter) {
      const ctxScatter = elScatter.getContext('2d');
      if (qualityScatterChart) qualityScatterChart.destroy();
      qualityScatterChart = new Chart(ctxScatter, {
        type: 'scatter',
        data: {
          datasets: [{
            label: 'Events',
            data: realEvents.map(e => ({ x: e.prompt_tokens || 0, y: e.response_quality ?? null })),
            backgroundColor: '#FFFFFF',
            pointRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { title: { display: true, text: 'Tokens', color: '#A1A1AA' }, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#A1A1AA' } },
            y: { title: { display: true, text: 'Quality', color: '#A1A1AA' }, min: 0, max: 1.0, grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#A1A1AA' } }
          }
        }
      });
    }
  }

  // Initial load
  loadProjects().then(() => {
    loadDashboardData();
    animateCards();
  });
});
