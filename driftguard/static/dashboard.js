document.addEventListener('DOMContentLoaded', () => {
  let timelineChart = null;
  let driftRadarChart = null;
  let contextChart = null;
  let qualityScatterChart = null;

  let currentProject = 'antigravity-live';
  const envSelect = document.getElementById('env-select');
  const timeRangeSelect = document.getElementById('time-range-select');
  const severitySelect = document.getElementById('severity-select');
  let currentEnv = envSelect?.value || 'all';
  let currentTimeRange = timeRangeSelect?.value || '24h';
  let currentSeverity = severitySelect?.value || 'all';
  let isLoadingDashboard = false;
  let dashboardEvents = [];
  let dashboardAlerts = [];
  let dashboardDiagnosis = null;
  let eventSearchTerm = '';
  let eventDisplayLimit = 100;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>\"']/g, character => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '\"': '&quot;',
      "'": '&#039;'
    })[character]);
  }

  function formatMetric(value, digits = 2) {
    if (value === null || value === undefined || value === '') return '—';
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric.toLocaleString(undefined, { maximumFractionDigits: digits }) : '—';
  }

  function formatTimestamp(value) {
    if (!value) return 'Unknown time';
    const parsed = new Date(String(value).replace(' ', 'T') + (String(value).endsWith('Z') ? '' : 'Z'));
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString([], {
      dateStyle: 'medium',
      timeStyle: 'short'
    });
  }

  function showDetailModal(modalId) {
    const modalElement = document.getElementById(modalId);
    if (!modalElement) return;
    modalElement.classList.remove('hidden');
    const closeButton = modalElement.querySelector('.close-x');
    if (closeButton) closeButton.focus();
  }

  function hideDetailModal(modalId) {
    const modalElement = document.getElementById(modalId);
    if (modalElement) modalElement.classList.add('hidden');
  }
  const apiKeyInput = document.getElementById('dashboard-api-key');
  if (apiKeyInput) apiKeyInput.value = window.localStorage.getItem('driftguard_api_key') || '';

  function requestHeaders() {
    const apiKey = apiKeyInput ? apiKeyInput.value.trim() : '';
    return apiKey ? { 'X-API-Key': apiKey } : {};
  }

  function dashboardQuery(includeSeverity = true) {
    const params = new URLSearchParams();
    if (currentEnv && currentEnv !== 'all') params.set('environment', currentEnv);
    if (includeSeverity && currentSeverity && currentSeverity !== 'all') {
      params.set('severity', currentSeverity);
    }
    params.set('time_range', currentTimeRange || 'all');
    return params.toString();
  }

  function withDashboardQuery(path, includeSeverity = true) {
    return `${path}?${dashboardQuery(includeSeverity)}`;
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
      events: 'Telemetry Event Explorer',
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
        environment: currentEnv === 'all' ? null : currentEnv
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

  if (envSelect) {
    envSelect.addEventListener('change', (e) => {
      currentEnv = e.target.value;
      loadDashboardData();
    });
  }

  if (timeRangeSelect) {
    timeRangeSelect.addEventListener('change', (e) => {
      currentTimeRange = e.target.value;
      loadDashboardData();
    });
  }

  if (severitySelect) {
    severitySelect.addEventListener('change', (e) => {
      currentSeverity = e.target.value;
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
    dashboardEvents = [];
    dashboardAlerts = [];
    dashboardDiagnosis = null;
    updateMetrics(null, [], []);
    renderRecentAlerts([]);
    renderAlertsTable([]);
    renderEventExplorer([]);
    renderCharts([]);
    renderAgentDiagnosis(null);
    updateDashboardMeta(null);
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
        fetch(withDashboardQuery(`/projects/${currentProject}/summary`), { headers: requestHeaders() }),
        fetch(withDashboardQuery(`/projects/${currentProject}/metrics`), { headers: requestHeaders() }),
        fetch(withDashboardQuery(`/events/${currentProject}`, false), { headers: requestHeaders() }),
        fetch(withDashboardQuery(`/alerts/${currentProject}`), { headers: requestHeaders() }),
        fetch(withDashboardQuery(`/projects/${currentProject}/agent-diagnosis`, false), { headers: requestHeaders() })
      ]);

      const [summaryRes, metricsRes, eventsRes, alertsRes, diagnosisRes] = responses;
      for (const [response, label] of [
        [summaryRes, 'Dashboard summary unavailable'],
        [metricsRes, 'Dashboard metrics unavailable'],
        [eventsRes, 'Telemetry unavailable'],
        [alertsRes, 'Alerts unavailable'],
        [diagnosisRes, 'Agent diagnosis unavailable']
      ]) {
        if (!response.ok) throw new Error(await responseError(response, label));
      }

      const [summary, metrics, events, alerts, diagnosis] = await Promise.all(
        responses.map(response => response.json())
      );
      dashboardEvents = events || [];
      dashboardAlerts = alerts || [];
      dashboardDiagnosis = diagnosis || null;
      updateMetrics(summary, dashboardEvents, dashboardAlerts, metrics);
      updateDashboardMeta(metrics);
      renderRecentAlerts(dashboardAlerts);
      renderAlertsTable(dashboardAlerts);
      renderEventExplorer(dashboardEvents);
      renderCharts(dashboardEvents);
      renderAgentDiagnosis(dashboardDiagnosis);
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
      const detailButton = document.getElementById('open-diagnosis-btn');
      if (detailButton) detailButton.disabled = true;
      return;
    }

    status.textContent = diagnosis.status ? diagnosis.status.toUpperCase() : 'NO DATA';
    status.className = `diagnosis-badge diagnosis-${diagnosis.status || 'stable'}`;
    const detailButton = document.getElementById('open-diagnosis-btn');
    if (detailButton) detailButton.disabled = false;
    tool.textContent = diagnosis.blocking_tool || 'None';
    failures.textContent = diagnosis.failure_count ?? 0;
    retries.textContent = diagnosis.repeated_attempts ?? 0;
    wastedTokens.textContent = Number(diagnosis.wasted_tokens || 0).toLocaleString();
    message.textContent = diagnosis.diagnosis || 'No agent task diagnosis is available.';
    recommendation.textContent = diagnosis.recommendation || '';
  }

  function updateMetrics(summary, events, alerts, metrics) {
    const aggregate = metrics || summary?.aggregates || {};
    const totalEvents = aggregate.total_events ?? (events ? events.length : 0);
    const totalSavedTokens = aggregate.saved_tokens ?? (alerts ? alerts.reduce((acc, a) => acc + (a.saved_tokens || 0), 0) : 0);
    const activeAlerts = aggregate.alert_count ?? (alerts ? alerts.length : 0);
    const criticalAlerts = aggregate.critical_count ?? (alerts ? alerts.filter(a => a.severity === 'critical').length : 0);
    const warningAlerts = aggregate.warning_count ?? (alerts ? alerts.filter(a => a.severity === 'warning').length : 0);

    let avgRetrieval = aggregate.retrieval_score ?? 0;
    if (aggregate.retrieval_score == null && events && events.length > 0) {
      const scores = events.filter(e => e.retrieval_score != null).map(e => Number(e.retrieval_score));
      avgRetrieval = scores.length ? scores.reduce((acc, value) => acc + value, 0) / scores.length : 0;
    }

    const totalEvtEl = document.getElementById('metric-total-events');
    const savedTokEl = document.getElementById('metric-saved-tokens');
    const savedCostEl = document.getElementById('metric-saved-cost');
    const activeAltEl = document.getElementById('metric-active-alerts');
    const critAltEl = document.getElementById('metric-critical-alerts');
    const retValEl = document.getElementById('metric-retrieval-score');
    const alertBadgeEl = document.getElementById('alert-count-badge');
    const eventsMetaEl = document.getElementById('metric-events-meta');
    const retrievalMetaEl = document.getElementById('metric-retrieval-meta');

    if (totalEvtEl) totalEvtEl.textContent = Number(totalEvents).toLocaleString();
    if (savedTokEl) savedTokEl.textContent = totalSavedTokens >= 1000000 ? `${(totalSavedTokens / 1000000).toFixed(1)}M` : Number(totalSavedTokens).toLocaleString();
    if (savedCostEl) savedCostEl.textContent = `Token savings: ${Number(totalSavedTokens).toLocaleString()}`;
    if (activeAltEl) activeAltEl.textContent = activeAlerts;
    if (critAltEl) {
      critAltEl.textContent = currentSeverity === 'critical'
        ? `${criticalAlerts} critical requiring action`
        : currentSeverity === 'warning'
          ? `${warningAlerts} warnings in view`
          : `${criticalAlerts} critical · ${warningAlerts} warnings`;
    }
    if (retValEl) retValEl.textContent = avgRetrieval == null ? '—' : Number(avgRetrieval).toFixed(2);
    if (alertBadgeEl) alertBadgeEl.textContent = activeAlerts;
    if (eventsMetaEl) eventsMetaEl.textContent = `${currentTimeRange} · ${currentEnv === 'all' ? 'all environments' : currentEnv}`;
    if (retrievalMetaEl && summary?.environment) retrievalMetaEl.textContent = `Environment: ${summary.environment}`;
  }

  function updateDashboardMeta(metrics) {
    const timeRangeLabels = {
      '15m': 'Last 15 minutes',
      '1h': 'Last hour',
      '24h': 'Last 24 hours',
      '7d': 'Last 7 days',
      '30d': 'Last 30 days',
      all: 'All time'
    };
    const filterSummary = document.getElementById('dashboard-filter-summary');
    const lastUpdated = document.getElementById('dashboard-last-updated');
    const environmentLabel = currentEnv === 'all' ? 'All' : currentEnv;
    const severityLabel = currentSeverity === 'all' ? 'All' : currentSeverity;
    if (filterSummary) {
      filterSummary.textContent = `Window: ${timeRangeLabels[currentTimeRange] || currentTimeRange} · Environment: ${environmentLabel} · Alerts: ${severityLabel}`;
    }
    if (lastUpdated) {
      const timestamp = metrics?.last_updated;
      lastUpdated.textContent = timestamp ? `Last updated: ${timestamp} UTC` : 'Last updated: No telemetry yet';
    }
  }

  function renderRecentAlerts(alerts) {
    const stack = document.getElementById('overview-alerts-tbody');
    if (!stack) return;

    const sampleAlerts = alerts || [];

    if (sampleAlerts.length === 0) {
      stack.innerHTML = '<div class="empty-state"><strong>No alerts recorded</strong><span>Alerts for the selected project will appear here.</span></div>';
      return;
    }

    stack.innerHTML = sampleAlerts.slice(0, 3).map((a, index) => {
      const isWarning = a.severity === 'critical' || a.severity === 'warning';
      const icon = isWarning ? 'WARNING' : 'INFO';
      return `
        <div class="alert-item ${isWarning ? 'alert-warning' : ''}">
          <div class="alert-item-icon">${icon}</div>
          <div class="alert-item-body">
            <div class="alert-item-title">${escapeHtml(a.message)}</div>
            <div class="alert-item-sub">${escapeHtml(a.sub || `Project: ${currentProject}`)}</div>
          </div>
          <div class="alert-item-time">${escapeHtml(a.time || formatTimestamp(a.created_at))}</div>
          <button class="table-action-btn" type="button" data-alert-index="${index}">Inspect</button>
        </div>
      `;
    }).join('');
  }

  function renderAlertsTable(alerts) {
    const alertsTbody = document.getElementById('alerts-tbody');
    if (!alertsTbody) return;

    const sampleAlerts = (alerts && alerts.length > 0) ? alerts : [];

    if (sampleAlerts.length === 0) {
      alertsTbody.innerHTML = `<tr><td colspan="7" class="empty-table-state">No alerts recorded for the selected project.</td></tr>`;
    } else {
      alertsTbody.innerHTML = sampleAlerts.map((a, i) => `
        <tr>
          <td style="font-family: var(--font-mono); color:#A1A1AA;">alt_${i + 1}</td>
          <td><span style="color: #FFFFFF; font-weight: 800;">${escapeHtml(String(a.severity || 'stable').toUpperCase())}</span></td>
          <td>${escapeHtml(currentProject)} (${escapeHtml(a.environment || (currentEnv === 'all' ? 'all' : currentEnv))})</td>
          <td>${escapeHtml(a.message)}</td>
          <td style="font-weight: 800; color: #FFFFFF;">+${formatMetric(a.saved_tokens)}</td>
          <td style="font-family: var(--font-mono); color:#A1A1AA;">${escapeHtml(formatTimestamp(a.created_at))}</td>
          <td><button class="table-action-btn" type="button" data-alert-index="${i}">Inspect</button></td>
        </tr>
      `).join('');
    }
  }

  function renderEventExplorer(events) {
    const tbody = document.getElementById('events-explorer-tbody');
    const count = document.getElementById('event-explorer-count');
    const badge = document.getElementById('event-count-badge');
    if (!tbody) return;

    const sourceEvents = events || [];
    const normalizedSearch = eventSearchTerm.trim().toLowerCase();
    const matchingEvents = normalizedSearch
      ? sourceEvents.filter(event => JSON.stringify(event).toLowerCase().includes(normalizedSearch))
      : sourceEvents;
    const visibleEvents = matchingEvents.slice(0, eventDisplayLimit);

    if (count) count.textContent = `${matchingEvents.length} event${matchingEvents.length === 1 ? '' : 's'}`;
    if (badge) badge.textContent = sourceEvents.length;

    if (visibleEvents.length === 0) {
      const message = sourceEvents.length === 0
        ? 'No telemetry recorded for the selected project and filters.'
        : 'No events match the current search.';
      tbody.innerHTML = `<tr><td colspan="8" class="empty-table-state">${escapeHtml(message)}</td></tr>`;
      return;
    }

    tbody.innerHTML = visibleEvents.map(event => `
      <tr>
        <td class="mono-cell">#${escapeHtml(event.id)}</td>
        <td class="timestamp-cell">${escapeHtml(formatTimestamp(event.created_at))}</td>
        <td><span class="environment-chip">${escapeHtml(event.environment || 'unknown')}</span></td>
        <td>${formatMetric(event.prompt_tokens, 0)}</td>
        <td>${formatMetric(event.context_length, 0)}</td>
        <td>${formatMetric(event.retrieval_score)}</td>
        <td>${formatMetric(event.response_quality)}</td>
        <td><button class="table-action-btn" type="button" data-event-id="${escapeHtml(event.id)}">Inspect</button></td>
      </tr>
    `).join('');
  }

  function renderEventDetail(event) {
    const grid = document.getElementById('event-detail-grid');
    const json = document.getElementById('event-detail-json');
    if (!grid || !json || !event) return;
    const fields = [
      ['Event ID', event.id],
      ['Timestamp', formatTimestamp(event.created_at)],
      ['Environment', event.environment || 'Unknown'],
      ['Prompt tokens', formatMetric(event.prompt_tokens, 0)],
      ['Context length', formatMetric(event.context_length, 0)],
      ['Retrieval score', formatMetric(event.retrieval_score)],
      ['Response quality', formatMetric(event.response_quality)]
    ];
    grid.innerHTML = fields.map(([label, value]) => `
      <div class="detail-field"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>
    `).join('');
    json.textContent = JSON.stringify(event, null, 2);
    showDetailModal('event-detail-modal');
  }

  function renderAlertDetail(alert) {
    const content = document.getElementById('alert-detail-content');
    if (!content || !alert) return;
    const severity = String(alert.severity || 'stable').toLowerCase();
    content.innerHTML = `
      <div class="detail-status-row"><span class="severity-chip severity-${escapeHtml(severity)}">${escapeHtml(severity)}</span><span class="timestamp-cell">${escapeHtml(formatTimestamp(alert.created_at))}</span></div>
      <div class="detail-message">${escapeHtml(alert.message || 'No alert message available.')}</div>
      <div class="detail-grid">
        <div class="detail-field"><span>Project</span><strong>${escapeHtml(currentProject)}</strong></div>
        <div class="detail-field"><span>Environment</span><strong>${escapeHtml(alert.environment || 'Unknown')}</strong></div>
        <div class="detail-field"><span>Saved tokens</span><strong>${formatMetric(alert.saved_tokens, 0)}</strong></div>
        <div class="detail-field"><span>Severity</span><strong>${escapeHtml(severity)}</strong></div>
      </div>
      <div class="detail-recommendation"><span>Investigation note</span><p>Inspect the related telemetry window and diagnosis before changing mitigation rules.</p></div>
    `;
    showDetailModal('alert-detail-modal');
  }

  function renderDiagnosisDetail(diagnosis) {
    const content = document.getElementById('diagnosis-detail-content');
    if (!content || !diagnosis) return;
    content.innerHTML = `
      <div class="detail-status-row"><span class="severity-chip severity-${escapeHtml(diagnosis.status || 'stable')}">${escapeHtml(String(diagnosis.status || 'stable').toUpperCase())}</span><span class="timestamp-cell">Filtered current window</span></div>
      <div class="detail-grid">
        <div class="detail-field"><span>Blocking tool</span><strong>${escapeHtml(diagnosis.blocking_tool || 'None')}</strong></div>
        <div class="detail-field"><span>Failed attempts</span><strong>${formatMetric(diagnosis.failure_count, 0)}</strong></div>
        <div class="detail-field"><span>Repeated attempts</span><strong>${formatMetric(diagnosis.repeated_attempts, 0)}</strong></div>
        <div class="detail-field"><span>Wasted tokens</span><strong>${formatMetric(diagnosis.wasted_tokens, 0)}</strong></div>
      </div>
      <div class="detail-recommendation"><span>Diagnosis</span><p>${escapeHtml(diagnosis.diagnosis || 'No diagnosis available.')}</p><span>Recommendation</span><p>${escapeHtml(diagnosis.recommendation || 'Continue monitoring task and tool events.')}</p></div>
    `;
    showDetailModal('diagnosis-detail-modal');
  }

  const eventSearchInput = document.getElementById('event-search-input');
  const eventLimitSelect = document.getElementById('event-limit-select');
  const clearEventSearchBtn = document.getElementById('clear-event-search-btn');

  if (eventSearchInput) {
    eventSearchInput.addEventListener('input', event => {
      eventSearchTerm = event.target.value;
      renderEventExplorer(dashboardEvents);
    });
  }

  if (eventLimitSelect) {
    eventLimitSelect.addEventListener('change', event => {
      eventDisplayLimit = Number(event.target.value) || 100;
      renderEventExplorer(dashboardEvents);
    });
  }

  if (clearEventSearchBtn) {
    clearEventSearchBtn.addEventListener('click', () => {
      eventSearchTerm = '';
      if (eventSearchInput) eventSearchInput.value = '';
      renderEventExplorer(dashboardEvents);
      if (eventSearchInput) eventSearchInput.focus();
    });
  }

  const eventsExplorerTbody = document.getElementById('events-explorer-tbody');
  if (eventsExplorerTbody) {
    eventsExplorerTbody.addEventListener('click', event => {
      const button = event.target.closest('[data-event-id]');
      if (!button) return;
      const selectedEvent = dashboardEvents.find(item => String(item.id) === String(button.dataset.eventId));
      renderEventDetail(selectedEvent);
    });
  }

  const alertsTbody = document.getElementById('alerts-tbody');
  if (alertsTbody) {
    alertsTbody.addEventListener('click', event => {
      const button = event.target.closest('[data-alert-index]');
      if (!button) return;
      renderAlertDetail(dashboardAlerts[Number(button.dataset.alertIndex)]);
    });
  }

  const overviewAlerts = document.getElementById('overview-alerts-tbody');
  if (overviewAlerts) {
    overviewAlerts.addEventListener('click', event => {
      const button = event.target.closest('[data-alert-index]');
      if (!button) return;
      renderAlertDetail(dashboardAlerts[Number(button.dataset.alertIndex)]);
    });
  }

  const diagnosisButton = document.getElementById('open-diagnosis-btn');
  if (diagnosisButton) diagnosisButton.addEventListener('click', () => renderDiagnosisDetail(dashboardDiagnosis));

  [
    ['close-event-detail-btn', 'event-detail-modal'],
    ['close-alert-detail-btn', 'alert-detail-modal'],
    ['close-diagnosis-detail-btn', 'diagnosis-detail-modal']
  ].forEach(([buttonId, modalId]) => {
    const button = document.getElementById(buttonId);
    if (button) button.addEventListener('click', () => hideDetailModal(modalId));
  });

  ['event-detail-modal', 'alert-detail-modal', 'diagnosis-detail-modal'].forEach(modalId => {
    const modalElement = document.getElementById(modalId);
    if (modalElement) {
      modalElement.addEventListener('click', event => {
        if (event.target === modalElement) hideDetailModal(modalId);
      });
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    ['event-detail-modal', 'alert-detail-modal', 'diagnosis-detail-modal'].forEach(hideDetailModal);
  });

  function renderCharts(events) {
    const elTimeline = document.getElementById('timelineChart');
    const elRadar = document.getElementById('driftRadarChart');
    const elContext = document.getElementById('contextChart');
    const elScatter = document.getElementById('qualityScatterChart');

    const realEvents = (events && events.length > 0) ? events : [];
    
    const labels = realEvents.map((event, i) => event.created_at ? new Date(event.created_at.replace(' ', 'T') + 'Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `Event ${realEvents.length - i}`);
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
