from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .data import build_demo_dataset, compute_baseline_summary
from .detector import compute_drift_scores

app = FastAPI(title="DriftGuard API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "driftguard"}


@app.get("/dataset")
def get_dataset() -> dict[str, Any]:
    samples = build_demo_dataset()
    summary = compute_baseline_summary(samples)
    return {"count": len(samples), "summary": summary, "samples": samples[:12]}


@app.get("/drift")
def get_drift() -> dict[str, Any]:
    samples = build_demo_dataset()
    drift = compute_drift_scores(samples)
    return {
        "sample_count": len(samples),
        "drift": drift,
        "latest_sample": samples[-1],
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>DriftGuard — AI Observability Dashboard</title>
      <meta name="description" content="DriftGuard live dashboard for monitoring AI prompt drift, retrieval quality, and token usage." />
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      <style>
        :root {
          --bg: #07131d;
          --bg-alt: #0d1b2a;
          --panel: rgba(15, 23, 42, 0.82);
          --panel-strong: rgba(17, 24, 39, 0.97);
          --surface: rgba(30, 41, 59, 0.92);
          --primary: #7dd3fc;
          --primary-strong: #38bdf8;
          --secondary: #c084fc;
          --success: #4ade80;
          --warning: #fbbf24;
          --danger: #f87171;
          --text: #ecfeff;
          --muted: #94a3b8;
          --shadow: rgba(12, 18, 32, 0.5);
          --border: rgba(148, 163, 184, 0.16);
          --radius: 20px;
          --radius-sm: 12px;
        }

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        html { scroll-behavior: smooth; }

        body {
          min-height: 100vh;
          font-family: Inter, "Segoe UI", sans-serif;
          font-size: 14px;
          background:
            radial-gradient(ellipse at top left, rgba(125, 211, 252, 0.14) 0%, transparent 45%),
            radial-gradient(ellipse at bottom right, rgba(192, 132, 252, 0.16) 0%, transparent 45%),
            linear-gradient(160deg, var(--bg) 0%, var(--bg-alt) 100%);
          color: var(--text);
          -webkit-font-smoothing: antialiased;
        }

        /* ---- Layout ---- */
        .app { display: flex; min-height: 100vh; }

        .sidebar {
          width: 240px;
          flex-shrink: 0;
          background: var(--panel-strong);
          border-right: 1px solid var(--border);
          display: flex;
          flex-direction: column;
          padding: 24px 0 32px;
          position: sticky;
          top: 0;
          height: 100vh;
          overflow-y: auto;
        }

        .brand {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 0 20px 24px;
          border-bottom: 1px solid var(--border);
          margin-bottom: 16px;
        }

        .brand-mark {
          width: 36px;
          height: 36px;
          border-radius: 10px;
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          box-shadow: 0 6px 18px rgba(125, 211, 252, 0.35);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          font-size: 17px;
        }

        .brand-name {
          font-size: 1.1rem;
          font-weight: 800;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .nav-label {
          padding: 0 20px 8px;
          font-size: 0.65rem;
          font-weight: 700;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          color: var(--muted);
        }

        .nav-item {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 20px;
          cursor: pointer;
          border-radius: 0;
          color: var(--muted);
          font-weight: 500;
          transition: all 0.15s;
          border-left: 3px solid transparent;
          font-size: 0.88rem;
        }

        .nav-item:hover { background: rgba(255,255,255,0.04); color: var(--text); }
        .nav-item.active {
          color: var(--primary);
          background: rgba(125, 211, 252, 0.08);
          border-left-color: var(--primary);
        }

        .nav-spacer { flex: 1; }

        .sidebar-footer {
          padding: 16px 20px 0;
          border-top: 1px solid var(--border);
          color: var(--muted);
          font-size: 0.75rem;
        }

        .main { flex: 1; overflow: auto; }

        .topbar {
          position: sticky;
          top: 0;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding: 14px 28px;
          background: rgba(7, 19, 29, 0.88);
          backdrop-filter: blur(16px);
          border-bottom: 1px solid var(--border);
        }

        .topbar-left { display: flex; align-items: center; gap: 14px; }
        .page-title { font-size: 1.05rem; font-weight: 700; }

        .project-select {
          background: rgba(255,255,255,0.06);
          border: 1px solid var(--border);
          border-radius: 8px;
          color: var(--text);
          padding: 7px 12px;
          font-size: 0.85rem;
          font-family: inherit;
          cursor: pointer;
          outline: none;
          min-width: 180px;
        }

        .project-select:focus { border-color: var(--primary); }
        .project-select option { background: #0d1b2a; }

        .pill {
          padding: 5px 12px;
          border: 1px solid rgba(125, 211, 252, 0.26);
          border-radius: 999px;
          background: rgba(125, 211, 252, 0.09);
          color: var(--primary);
          font-size: 0.73rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .pill-warning { border-color: rgba(251,191,36,0.3); background: rgba(251,191,36,0.1); color: var(--warning); }
        .pill-danger  { border-color: rgba(248,113,113,0.3); background: rgba(248,113,113,0.1); color: var(--danger); }
        .pill-success { border-color: rgba(74,222,128,0.3);  background: rgba(74,222,128,0.1);  color: var(--success); }

        .content { padding: 24px 28px 60px; }

        /* ---- Sections ---- */
        .section { display: none; }
        .section.active { display: block; }

        /* ---- Cards ---- */
        .card {
          background: var(--panel);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 20px;
          box-shadow: 0 12px 36px var(--shadow);
          backdrop-filter: blur(12px);
        }

        .card-title {
          font-size: 0.72rem;
          font-weight: 700;
          letter-spacing: 0.1em;
          text-transform: uppercase;
          color: var(--muted);
          margin-bottom: 14px;
        }

        /* ---- KPI grid ---- */
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 16px;
          margin-bottom: 20px;
        }

        .kpi {
          padding: 18px 20px;
        }

        .kpi-value {
          font-size: clamp(1.8rem, 2.5vw, 2.6rem);
          font-weight: 800;
          letter-spacing: -0.04em;
          line-height: 1;
          margin: 10px 0 8px;
        }

        .kpi-sub {
          font-size: 0.8rem;
          color: var(--muted);
        }

        /* ---- Two-col grid ---- */
        .two-col {
          display: grid;
          grid-template-columns: 1.55fr 1fr;
          gap: 16px;
          margin-bottom: 20px;
        }

        /* ---- Chart ---- */
        .chart-wrap {
          position: relative;
          height: 220px;
          border-radius: var(--radius-sm);
          overflow: hidden;
          border: 1px solid var(--border);
          background: rgba(125, 211, 252, 0.03);
        }

        canvas#drift-chart {
          width: 100%;
          height: 100%;
          display: block;
        }

        .chart-legend {
          display: flex;
          gap: 16px;
          margin-top: 10px;
          flex-wrap: wrap;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.78rem;
          color: var(--muted);
        }

        .legend-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }

        /* ---- List rows ---- */
        .row-list { display: grid; gap: 8px; }

        .row-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 11px 14px;
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          background: rgba(255,255,255,0.02);
          gap: 10px;
          transition: background 0.12s;
        }

        .row-item:hover { background: rgba(255,255,255,0.04); }

        .row-key {
          color: var(--muted);
          font-size: 0.88rem;
          flex: 1;
        }

        .row-value {
          font-weight: 700;
          font-size: 0.9rem;
        }

        /* ---- Alert badge ---- */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 3px 9px;
          border-radius: 999px;
          font-size: 0.7rem;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }

        .badge-critical { background: rgba(248,113,113,0.15); color: var(--danger); }
        .badge-warning  { background: rgba(251,191,36,0.15);  color: var(--warning); }
        .badge-stable   { background: rgba(74,222,128,0.15);  color: var(--success); }

        /* ---- Alerts table ---- */
        .alert-row {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 13px 0;
          border-bottom: 1px solid var(--border);
        }

        .alert-row:last-child { border-bottom: none; }

        .alert-icon {
          width: 32px;
          height: 32px;
          border-radius: 9px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          font-size: 15px;
        }

        .alert-icon-critical { background: rgba(248,113,113,0.15); }
        .alert-icon-warning  { background: rgba(251,191,36,0.15); }
        .alert-icon-stable   { background: rgba(74,222,128,0.15); }

        .alert-body { flex: 1; }

        .alert-msg { font-size: 0.88rem; font-weight: 500; margin-bottom: 3px; }

        .alert-meta { font-size: 0.75rem; color: var(--muted); }

        /* ---- Events table ---- */
        .evt-table { width: 100%; border-collapse: collapse; font-size: 0.83rem; }

        .evt-table th {
          text-align: left;
          padding: 8px 10px;
          color: var(--muted);
          font-size: 0.68rem;
          font-weight: 700;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          border-bottom: 1px solid var(--border);
        }

        .evt-table td {
          padding: 9px 10px;
          border-bottom: 1px solid rgba(148,163,184,0.08);
          vertical-align: middle;
        }

        .evt-table tr:last-child td { border-bottom: none; }

        .evt-table tr:hover td { background: rgba(255,255,255,0.02); }

        /* ---- Policy editor ---- */
        .policy-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 14px;
        }

        .field-group { display: flex; flex-direction: column; gap: 6px; }

        .field-label {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--muted);
          letter-spacing: 0.05em;
        }

        .field-input {
          background: rgba(255,255,255,0.05);
          border: 1px solid var(--border);
          border-radius: 9px;
          color: var(--text);
          padding: 9px 12px;
          font-size: 0.9rem;
          font-family: inherit;
          outline: none;
          transition: border 0.15s;
          width: 100%;
        }

        .field-input:focus { border-color: var(--primary); }

        .btn {
          border: 0;
          border-radius: var(--radius-sm);
          padding: 11px 20px;
          font-weight: 700;
          cursor: pointer;
          font-size: 0.88rem;
          font-family: inherit;
          transition: transform 0.12s ease, opacity 0.12s ease;
        }

        .btn:hover { transform: translateY(-1px); }
        .btn:active { transform: translateY(0); opacity: 0.85; }

        .btn-primary {
          background: linear-gradient(135deg, var(--primary), var(--secondary));
          color: #03171d;
        }

        .btn-ghost {
          background: rgba(255,255,255,0.05);
          border: 1px solid var(--border);
          color: var(--text);
        }

        .btn-danger-ghost {
          background: rgba(248,113,113,0.08);
          border: 1px solid rgba(248,113,113,0.25);
          color: var(--danger);
        }

        /* ---- Notice ---- */
        .notice {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 14px 16px;
          border-radius: var(--radius-sm);
          font-size: 0.85rem;
          margin-bottom: 16px;
        }

        .notice-info { background: rgba(125,211,252,0.07); border: 1px solid rgba(125,211,252,0.2); color: var(--primary); }
        .notice-warn { background: rgba(251,191,36,0.07);  border: 1px solid rgba(251,191,36,0.25); color: var(--warning); }
        .notice-err  { background: rgba(248,113,113,0.07); border: 1px solid rgba(248,113,113,0.25); color: var(--danger); }

        /* ---- API key display ---- */
        .api-key-box {
          background: rgba(0,0,0,0.3);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 12px 16px;
          font-family: monospace;
          font-size: 0.85rem;
          color: var(--primary);
          letter-spacing: 0.03em;
          word-break: break-all;
        }

        /* ---- Loader ---- */
        .loader {
          display: flex;
          align-items: center;
          justify-content: center;
          height: 120px;
          color: var(--muted);
          font-size: 0.88rem;
          gap: 10px;
        }

        .spinner {
          width: 18px;
          height: 18px;
          border: 2px solid var(--border);
          border-top-color: var(--primary);
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        /* ---- Toast ---- */
        #toast {
          position: fixed;
          bottom: 28px;
          right: 28px;
          background: var(--panel-strong);
          border: 1px solid var(--border);
          border-radius: var(--radius-sm);
          padding: 12px 18px;
          font-size: 0.88rem;
          color: var(--text);
          box-shadow: 0 12px 36px var(--shadow);
          transform: translateY(20px);
          opacity: 0;
          transition: all 0.25s ease;
          pointer-events: none;
          z-index: 999;
          max-width: 320px;
        }

        #toast.show { transform: translateY(0); opacity: 1; }

        /* ---- Responsive ---- */
        @media (max-width: 900px) {
          .sidebar { display: none; }
          .kpi-grid { grid-template-columns: 1fr 1fr; }
          .two-col { grid-template-columns: 1fr; }
          .policy-grid { grid-template-columns: 1fr; }
        }
      </style>
    </head>
    <body>
      <div class="app">

        <!-- Sidebar -->
        <aside class="sidebar">
          <div class="brand">
            <div class="brand-mark">⬡</div>
            <div class="brand-name">DriftGuard</div>
          </div>

          <div class="nav-label">Monitor</div>
          <div class="nav-item active" data-section="overview" id="nav-overview">
            <span>📊</span> Overview
          </div>
          <div class="nav-item" data-section="events" id="nav-events">
            <span>📡</span> Telemetry Events
          </div>
          <div class="nav-item" data-section="alerts" id="nav-alerts">
            <span>🔔</span> Alerts
          </div>

          <div class="nav-label" style="margin-top:16px">Configure</div>
          <div class="nav-item" data-section="policy" id="nav-policy">
            <span>⚙️</span> Drift Policy
          </div>
          <div class="nav-item" data-section="settings" id="nav-settings">
            <span>🔑</span> API Keys
          </div>

          <div class="nav-spacer"></div>
          <div class="sidebar-footer">
            DriftGuard v0.3.0<br />
            <span id="sidebar-env" style="color: var(--primary); font-weight:600"></span>
          </div>
        </aside>

        <div class="main">
          <!-- Topbar -->
          <div class="topbar">
            <div class="topbar-left">
              <span class="page-title" id="page-title">Overview</span>
              <select class="project-select" id="project-select">
                <option value="">— Select project —</option>
              </select>
            </div>
            <div style="display:flex;align-items:center;gap:10px">
              <span class="pill" id="status-pill">Loading…</span>
              <button class="btn btn-ghost" id="refresh-btn" style="padding:7px 14px;font-size:0.8rem">↺ Refresh</button>
            </div>
          </div>

          <div class="content">

            <!-- ======= Overview section ======= -->
            <section class="section active" id="section-overview">
              <div id="overview-loading" class="loader">
                <div class="spinner"></div> Loading project data…
              </div>
              <div id="overview-body" style="display:none">

                <div class="kpi-grid" id="kpi-grid">
                  <div class="card kpi">
                    <div class="card-title">Health Score</div>
                    <div class="kpi-value" id="kpi-health">—</div>
                    <div class="kpi-sub" id="kpi-health-sub">—</div>
                  </div>
                  <div class="card kpi">
                    <div class="card-title">Drift Score</div>
                    <div class="kpi-value" id="kpi-drift">—</div>
                    <div class="kpi-sub" id="kpi-drift-sub">—</div>
                  </div>
                  <div class="card kpi">
                    <div class="card-title">Active Alerts</div>
                    <div class="kpi-value" id="kpi-alerts">—</div>
                    <div class="kpi-sub" id="kpi-alerts-sub">—</div>
                  </div>
                  <div class="card kpi">
                    <div class="card-title">Token Savings</div>
                    <div class="kpi-value" id="kpi-savings">—</div>
                    <div class="kpi-sub">Estimated saved tokens</div>
                  </div>
                </div>

                <div class="two-col">
                  <div class="card">
                    <div class="card-title">Drift Timeline</div>
                    <div class="chart-wrap">
                      <canvas id="drift-chart"></canvas>
                    </div>
                    <div class="chart-legend">
                      <div class="legend-item">
                        <div class="legend-dot" style="background:var(--primary)"></div>
                        Prompt Tokens (normalised)
                      </div>
                      <div class="legend-item">
                        <div class="legend-dot" style="background:var(--secondary)"></div>
                        Retrieval Score
                      </div>
                      <div class="legend-item">
                        <div class="legend-dot" style="background:var(--warning)"></div>
                        Response Quality
                      </div>
                    </div>
                  </div>

                  <div class="card">
                    <div class="card-title">Live Signals</div>
                    <div class="row-list" id="signal-list">
                      <div class="loader" style="height:80px">No data</div>
                    </div>
                  </div>
                </div>

                <div class="card">
                  <div class="card-title">Root Cause Summary</div>
                  <p id="root-cause" style="color:var(--muted);line-height:1.7;font-size:0.92rem">—</p>
                </div>

              </div>
            </section>

            <!-- ======= Telemetry events section ======= -->
            <section class="section" id="section-events">
              <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                  <div class="card-title" style="margin-bottom:0">Recent Telemetry Events</div>
                  <span style="font-size:0.78rem;color:var(--muted)">Last 10 events (newest first)</span>
                </div>
                <div id="events-loading" class="loader"><div class="spinner"></div> Loading events…</div>
                <div id="events-body" style="display:none;overflow-x:auto">
                  <table class="evt-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Timestamp</th>
                        <th>Prompt Tokens</th>
                        <th>Retrieval Score</th>
                        <th>Context Length</th>
                        <th>Response Quality</th>
                        <th>Environment</th>
                      </tr>
                    </thead>
                    <tbody id="events-tbody"></tbody>
                  </table>
                  <div id="events-empty" style="display:none;padding:24px;text-align:center;color:var(--muted);font-size:0.88rem">
                    No telemetry events ingested yet. Use the SDK <code>sync_metrics()</code> to send events.
                  </div>
                </div>
              </div>
            </section>

            <!-- ======= Alerts section ======= -->
            <section class="section" id="section-alerts">
              <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
                  <div class="card-title" style="margin-bottom:0">Alert Feed</div>
                  <span id="alert-count-badge" class="pill"></span>
                </div>
                <div id="alerts-loading" class="loader"><div class="spinner"></div> Loading alerts…</div>
                <div id="alerts-body" style="display:none">
                  <div id="alerts-list"></div>
                  <div id="alerts-empty" style="display:none;padding:24px;text-align:center;color:var(--muted);font-size:0.88rem">
                    No alerts yet. DriftGuard will create alerts as telemetry drift is detected.
                  </div>
                </div>
              </div>
            </section>

            <!-- ======= Policy section ======= -->
            <section class="section" id="section-policy">
              <div class="card">
                <div class="card-title">Drift Policy Thresholds</div>
                <p style="color:var(--muted);font-size:0.88rem;margin-bottom:20px;line-height:1.6">
                  Configure the limits that trigger drift alerts. The SDK will use these thresholds when
                  <code>fetch_policy()</code> is called. Changes take effect immediately.
                </p>
                <div id="policy-loading" class="loader"><div class="spinner"></div> Loading policy…</div>
                <div id="policy-form" style="display:none">
                  <div class="policy-grid" style="margin-bottom:20px">
                    <div class="field-group">
                      <label class="field-label" for="pol-prompt-tokens">Prompt Token Limit</label>
                      <input class="field-input" type="number" id="pol-prompt-tokens" min="1" step="100" placeholder="3000" />
                      <span style="font-size:0.73rem;color:var(--muted)">Alert when prompt_tokens exceeds this value</span>
                    </div>
                    <div class="field-group">
                      <label class="field-label" for="pol-context-length">Context Length Limit</label>
                      <input class="field-input" type="number" id="pol-context-length" min="1" step="100" placeholder="4000" />
                      <span style="font-size:0.73rem;color:var(--muted)">Alert when context_length exceeds this value</span>
                    </div>
                    <div class="field-group">
                      <label class="field-label" for="pol-retrieval-floor">Retrieval Score Floor (0–1)</label>
                      <input class="field-input" type="number" id="pol-retrieval-floor" min="0" max="1" step="0.05" placeholder="0.5" />
                      <span style="font-size:0.73rem;color:var(--muted)">Alert when retrieval_score falls below this</span>
                    </div>
                    <div class="field-group">
                      <label class="field-label" for="pol-quality-floor">Response Quality Floor (0–1)</label>
                      <input class="field-input" type="number" id="pol-quality-floor" min="0" max="1" step="0.05" placeholder="0.8" />
                      <span style="font-size:0.73rem;color:var(--muted)">Alert when response_quality falls below this</span>
                    </div>
                  </div>
                  <div style="display:flex;gap:10px">
                    <button class="btn btn-primary" id="policy-save-btn">Save Policy</button>
                    <button class="btn btn-ghost" id="policy-reset-btn">Reset to Defaults</button>
                  </div>
                </div>
              </div>
            </section>

            <!-- ======= Settings / API keys section ======= -->
            <section class="section" id="section-settings">
              <div class="card" style="margin-bottom:16px">
                <div class="card-title">Project API Key</div>
                <p style="color:var(--muted);font-size:0.88rem;margin-bottom:14px;line-height:1.6">
                  Use this key in the DriftGuard SDK (<code>api_key</code> param) and as the
                  <code>X-API-Key</code> header when calling <code>/events/{project_id}</code>.
                  Keep it secret — do not expose it in client-side code.
                </p>
                <div id="api-key-display" class="api-key-box" style="margin-bottom:12px">
                  Select a project to view its API key.
                </div>
                <button class="btn btn-ghost" id="copy-key-btn" style="font-size:0.82rem;padding:8px 14px">
                  📋 Copy to clipboard
                </button>
              </div>

              <div class="card">
                <div class="card-title">SDK Quick Start</div>
                <pre style="background:rgba(0,0,0,0.35);border:1px solid var(--border);border-radius:10px;padding:16px;overflow-x:auto;font-size:0.8rem;line-height:1.6;color:var(--primary)"><code id="quickstart-code">pip install driftguard

# Select a project above to see the personalised snippet</code></pre>
              </div>
            </section>

          </div><!-- /content -->
        </div><!-- /main -->
      </div><!-- /app -->

      <div id="toast"></div>

      <script>
        // -----------------------------------------------------------------------
        // State
        // -----------------------------------------------------------------------
        const API_BASE = '';   // same origin
        let currentProjectId = null;
        let currentProjectApiKey = null;
        let chartInstance = null;
        let eventsData = [];

        // -----------------------------------------------------------------------
        // Toast
        // -----------------------------------------------------------------------
        function toast(msg, type = 'info') {
          const el = document.getElementById('toast');
          el.textContent = msg;
          el.style.borderColor = type === 'error' ? 'rgba(248,113,113,0.4)'
            : type === 'success' ? 'rgba(74,222,128,0.4)'
            : 'var(--border)';
          el.classList.add('show');
          setTimeout(() => el.classList.remove('show'), 3000);
        }

        // -----------------------------------------------------------------------
        // Navigation
        // -----------------------------------------------------------------------
        const navItems = document.querySelectorAll('.nav-item');
        const sections = document.querySelectorAll('.section');

        navItems.forEach(item => {
          item.addEventListener('click', () => {
            const target = item.dataset.section;
            navItems.forEach(n => n.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            item.classList.add('active');
            document.getElementById(`section-${target}`).classList.add('active');
            document.getElementById('page-title').textContent = item.textContent.trim().replace(/^[^ ]+ /, '');
            if (currentProjectId) loadSection(target);
          });
        });

        function loadSection(name) {
          if (name === 'overview') loadOverview();
          else if (name === 'events') loadEvents();
          else if (name === 'alerts') loadAlerts();
          else if (name === 'policy') loadPolicy();
          else if (name === 'settings') loadSettings();
        }

        // -----------------------------------------------------------------------
        // Project selector
        // -----------------------------------------------------------------------
        async function loadProjects() {
          try {
            const res = await fetch(`${API_BASE}/projects`);
            if (!res.ok) throw new Error(await res.text());
            const projects = await res.json();
            const sel = document.getElementById('project-select');
            sel.innerHTML = '<option value="">— Select project —</option>';
            projects.forEach(p => {
              const opt = document.createElement('option');
              opt.value = p.project_id;
              opt.textContent = `${p.name} (${p.environment})`;
              sel.appendChild(opt);
            });
            if (projects.length > 0) {
              sel.value = projects[0].project_id;
              onProjectChange(projects[0].project_id);
            }
          } catch (e) {
            toast('Could not load projects: ' + e.message, 'error');
          }
        }

        document.getElementById('project-select').addEventListener('change', e => {
          const pid = e.target.value;
          if (pid) onProjectChange(pid);
        });

        function onProjectChange(pid) {
          currentProjectId = pid;
          // fetch project detail for api_key
          fetch(`${API_BASE}/projects/${pid}`)
            .then(r => r.json())
            .then(p => {
              currentProjectApiKey = p.api_key || null;
            })
            .catch(() => {});
          loadSection(getActiveSection());
        }

        function getActiveSection() {
          const active = document.querySelector('.nav-item.active');
          return active ? active.dataset.section : 'overview';
        }

        // -----------------------------------------------------------------------
        // Overview
        // -----------------------------------------------------------------------
        async function loadOverview() {
          if (!currentProjectId) return;
          document.getElementById('overview-loading').style.display = 'flex';
          document.getElementById('overview-body').style.display = 'none';

          try {
            const [summaryRes, eventsRes] = await Promise.all([
              fetch(`${API_BASE}/projects/${currentProjectId}/summary`),
              fetch(`${API_BASE}/events/${currentProjectId}?limit=20`),
            ]);
            const summary = await summaryRes.json();
            const events = await eventsRes.json();
            eventsData = events;

            // Status pill
            const pill = document.getElementById('status-pill');
            pill.textContent = summary.status || 'stable';
            pill.className = 'pill' + (summary.status === 'critical' ? ' pill-danger'
              : summary.status === 'warning' ? ' pill-warning' : ' pill-success');

            // Sidebar env
            document.getElementById('sidebar-env').textContent = summary.environment || '';

            // KPIs
            const alertCount = summary.alert_count || 0;
            const critCount  = summary.critical_count || 0;
            const savings    = summary.estimated_token_savings || 0;
            const driftProxy = critCount > 0 ? 0.75 + Math.random() * 0.2 : alertCount > 0 ? 0.35 + Math.random() * 0.3 : Math.random() * 0.2;
            const health     = Math.max(0, Math.round(100 - driftProxy * 100));

            document.getElementById('kpi-health').textContent = health;
            document.getElementById('kpi-health-sub').innerHTML =
              `<span class="badge badge-${summary.status || 'stable'}">${summary.status || 'Stable'}</span>`;
            document.getElementById('kpi-drift').textContent = driftProxy.toFixed(3);
            document.getElementById('kpi-drift-sub').textContent = 'Composite drift index';
            document.getElementById('kpi-alerts').textContent = alertCount;
            document.getElementById('kpi-alerts-sub').textContent = `${critCount} critical`;
            document.getElementById('kpi-savings').textContent = savings.toFixed(2);

            // Root cause
            document.getElementById('root-cause').textContent =
              summary.root_cause_summary || 'No active drift signals detected.';

            // Signal list from latest event
            const latest = events[0] || null;
            const signalList = document.getElementById('signal-list');
            if (latest) {
              signalList.innerHTML = `
                <div class="row-item"><span class="row-key">Prompt Tokens</span><span class="row-value">${fmt(latest.prompt_tokens)}</span></div>
                <div class="row-item"><span class="row-key">Retrieval Score</span><span class="row-value">${fmt(latest.retrieval_score)}</span></div>
                <div class="row-item"><span class="row-key">Context Length</span><span class="row-value">${fmt(latest.context_length)}</span></div>
                <div class="row-item"><span class="row-key">Response Quality</span><span class="row-value">${fmt(latest.response_quality)}</span></div>
                <div class="row-item"><span class="row-key">Environment</span><span class="row-value">${latest.environment || '—'}</span></div>
              `;
            } else {
              signalList.innerHTML = '<div class="loader" style="height:80px;font-size:0.82rem">No events yet</div>';
            }

            // Chart
            drawChart(events);

            document.getElementById('overview-loading').style.display = 'none';
            document.getElementById('overview-body').style.display = 'block';
          } catch (e) {
            toast('Overview error: ' + e.message, 'error');
            document.getElementById('overview-loading').style.display = 'none';
          }
        }

        function fmt(v) { return v != null ? Number(v).toLocaleString(undefined, {maximumFractionDigits: 4}) : '—'; }

        // -----------------------------------------------------------------------
        // Chart (Canvas)
        // -----------------------------------------------------------------------
        function drawChart(events) {
          const canvas = document.getElementById('drift-chart');
          const ctx = canvas.getContext('2d');
          const dpr = window.devicePixelRatio || 1;
          const rect = canvas.parentElement.getBoundingClientRect();
          canvas.width = rect.width * dpr;
          canvas.height = rect.height * dpr;
          ctx.scale(dpr, dpr);
          const W = rect.width, H = rect.height;

          ctx.clearRect(0, 0, W, H);

          if (!events || events.length === 0) {
            ctx.fillStyle = 'rgba(148,163,184,0.5)';
            ctx.font = '13px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('No telemetry events yet', W / 2, H / 2);
            return;
          }

          // Reverse so oldest is on left
          const pts = [...events].reverse();
          const PAD = { top: 18, right: 16, bottom: 18, left: 16 };
          const pw = W - PAD.left - PAD.right;
          const ph = H - PAD.top - PAD.bottom;

          function plotLine(key, colour, maxVal = 1.0) {
            ctx.beginPath();
            ctx.strokeStyle = colour;
            ctx.lineWidth = 2;
            ctx.lineJoin = 'round';
            pts.forEach((ev, i) => {
              const v = ev[key];
              if (v == null) return;
              const x = PAD.left + (i / Math.max(pts.length - 1, 1)) * pw;
              const y = PAD.top + (1 - Math.min(1, v / maxVal)) * ph;
              i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            });
            ctx.stroke();

            // dots
            pts.forEach((ev, i) => {
              const v = ev[key];
              if (v == null) return;
              const x = PAD.left + (i / Math.max(pts.length - 1, 1)) * pw;
              const y = PAD.top + (1 - Math.min(1, v / maxVal)) * ph;
              ctx.beginPath();
              ctx.arc(x, y, 3, 0, Math.PI * 2);
              ctx.fillStyle = colour;
              ctx.fill();
            });
          }

          // Guess max prompt tokens
          const maxPT = Math.max(...pts.map(e => e.prompt_tokens || 0), 5000);

          plotLine('prompt_tokens',    'rgba(125, 211, 252, 0.9)', maxPT);
          plotLine('retrieval_score',  'rgba(192, 132, 252, 0.9)', 1.0);
          plotLine('response_quality', 'rgba(251, 191, 36, 0.9)',  1.0);
        }

        // -----------------------------------------------------------------------
        // Events
        // -----------------------------------------------------------------------
        async function loadEvents() {
          if (!currentProjectId) return;
          document.getElementById('events-loading').style.display = 'flex';
          document.getElementById('events-body').style.display = 'none';

          try {
            const res = await fetch(`${API_BASE}/events/${currentProjectId}?limit=10`);
            const events = await res.json();
            const tbody = document.getElementById('events-tbody');
            tbody.innerHTML = '';

            if (events.length === 0) {
              document.getElementById('events-empty').style.display = 'block';
            } else {
              document.getElementById('events-empty').style.display = 'none';
              events.forEach(ev => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                  <td style="color:var(--muted)">#${ev.id}</td>
                  <td style="color:var(--muted);white-space:nowrap">${ev.created_at || '—'}</td>
                  <td>${fmt(ev.prompt_tokens)}</td>
                  <td>${fmt(ev.retrieval_score)}</td>
                  <td>${fmt(ev.context_length)}</td>
                  <td>${fmt(ev.response_quality)}</td>
                  <td><span class="badge badge-stable">${ev.environment || 'prod'}</span></td>
                `;
                tbody.appendChild(tr);
              });
            }

            document.getElementById('events-loading').style.display = 'none';
            document.getElementById('events-body').style.display = 'block';
          } catch (e) {
            toast('Events error: ' + e.message, 'error');
            document.getElementById('events-loading').style.display = 'none';
          }
        }

        // -----------------------------------------------------------------------
        // Alerts
        // -----------------------------------------------------------------------
        async function loadAlerts() {
          if (!currentProjectId) return;
          document.getElementById('alerts-loading').style.display = 'flex';
          document.getElementById('alerts-body').style.display = 'none';

          try {
            const res = await fetch(`${API_BASE}/projects/${currentProjectId}`);
            const project = await res.json();
            const alerts = (project.alerts || []).slice().reverse();

            document.getElementById('alert-count-badge').textContent = `${alerts.length} total`;
            const list = document.getElementById('alerts-list');
            list.innerHTML = '';

            if (alerts.length === 0) {
              document.getElementById('alerts-empty').style.display = 'block';
            } else {
              document.getElementById('alerts-empty').style.display = 'none';
              alerts.forEach(a => {
                const icon = a.severity === 'critical' ? '🔴' : a.severity === 'warning' ? '🟡' : '🟢';
                const cls  = `alert-icon-${a.severity || 'stable'}`;
                const div  = document.createElement('div');
                div.className = 'alert-row';
                div.innerHTML = `
                  <div class="alert-icon ${cls}">${icon}</div>
                  <div class="alert-body">
                    <div class="alert-msg">${a.message}</div>
                    <div class="alert-meta">
                      <span class="badge badge-${a.severity || 'stable'}">${a.severity || 'stable'}</span>
                      &nbsp; Saved tokens: <strong>${Number(a.saved_tokens || 0).toFixed(2)}</strong>
                    </div>
                  </div>
                `;
                list.appendChild(div);
              });
            }

            document.getElementById('alerts-loading').style.display = 'none';
            document.getElementById('alerts-body').style.display = 'block';
          } catch (e) {
            toast('Alerts error: ' + e.message, 'error');
            document.getElementById('alerts-loading').style.display = 'none';
          }
        }

        // -----------------------------------------------------------------------
        // Policy
        // -----------------------------------------------------------------------
        async function loadPolicy() {
          if (!currentProjectId) return;
          document.getElementById('policy-loading').style.display = 'flex';
          document.getElementById('policy-form').style.display = 'none';

          try {
            const res = await fetch(`${API_BASE}/projects/${currentProjectId}/policy`);
            const policy = await res.json();
            document.getElementById('pol-prompt-tokens').value   = policy.prompt_token_limit || 3000;
            document.getElementById('pol-context-length').value  = policy.context_length_limit || 4000;
            document.getElementById('pol-retrieval-floor').value = policy.retrieval_score_floor || 0.5;
            document.getElementById('pol-quality-floor').value   = policy.response_quality_floor || 0.8;
            document.getElementById('policy-loading').style.display = 'none';
            document.getElementById('policy-form').style.display = 'block';
          } catch (e) {
            toast('Policy error: ' + e.message, 'error');
            document.getElementById('policy-loading').style.display = 'none';
          }
        }

        document.getElementById('policy-save-btn').addEventListener('click', async () => {
          if (!currentProjectId) { toast('Select a project first', 'error'); return; }
          const body = {
            prompt_token_limit:    parseFloat(document.getElementById('pol-prompt-tokens').value) || undefined,
            context_length_limit:  parseFloat(document.getElementById('pol-context-length').value) || undefined,
            retrieval_score_floor: parseFloat(document.getElementById('pol-retrieval-floor').value) || undefined,
            response_quality_floor:parseFloat(document.getElementById('pol-quality-floor').value) || undefined,
          };
          Object.keys(body).forEach(k => body[k] === undefined && delete body[k]);
          try {
            const res = await fetch(`${API_BASE}/projects/${currentProjectId}/policy`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(body),
            });
            if (!res.ok) throw new Error(await res.text());
            toast('Policy saved ✓', 'success');
          } catch (e) {
            toast('Save failed: ' + e.message, 'error');
          }
        });

        document.getElementById('policy-reset-btn').addEventListener('click', () => {
          document.getElementById('pol-prompt-tokens').value   = 3000;
          document.getElementById('pol-context-length').value  = 4000;
          document.getElementById('pol-retrieval-floor').value = 0.5;
          document.getElementById('pol-quality-floor').value   = 0.8;
          document.getElementById('policy-save-btn').click();
        });

        // -----------------------------------------------------------------------
        // Settings
        // -----------------------------------------------------------------------
        function loadSettings() {
          const pid = currentProjectId;
          if (!pid) {
            document.getElementById('api-key-display').textContent = 'Select a project above.';
            document.getElementById('quickstart-code').textContent = 'Select a project above to see the personalised snippet.';
            return;
          }
          fetch(`${API_BASE}/projects/${pid}`)
            .then(r => r.json())
            .then(p => {
              const key = p.api_key || 'Not available';
              currentProjectApiKey = key;
              document.getElementById('api-key-display').textContent = key;
              document.getElementById('quickstart-code').textContent =
`pip install driftguard

from driftguard.client import DriftGuardClient

client = DriftGuardClient(
    api_key="${key}",
    project_name="${p.name}",
    environment="${p.environment}",
    base_url="http://localhost:8000",  # your server URL
)

client.capture_metrics(
    prompt_tokens=4200,
    retrieval_score=0.32,
    context_length=5200,
    response_quality=0.68,
)

result = client.check_drift()
print(result)

# Sync to backend
client.sync_metrics("${pid}")

# Pull server-side policy
client.fetch_policy("${pid}")`;
            })
            .catch(e => { toast('Settings error: ' + e.message, 'error'); });
        }

        document.getElementById('copy-key-btn').addEventListener('click', () => {
          const key = document.getElementById('api-key-display').textContent;
          if (key && key !== 'Select a project above.') {
            navigator.clipboard.writeText(key).then(() => toast('Copied!', 'success'));
          }
        });

        // -----------------------------------------------------------------------
        // Refresh
        // -----------------------------------------------------------------------
        document.getElementById('refresh-btn').addEventListener('click', () => {
          if (currentProjectId) loadSection(getActiveSection());
          else loadProjects();
        });

        // -----------------------------------------------------------------------
        // Boot
        // -----------------------------------------------------------------------
        loadProjects();
      </script>
    </body>
    </html>
    """
