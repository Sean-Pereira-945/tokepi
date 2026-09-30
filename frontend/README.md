# DriftGuard dashboard

The web dashboard for DriftGuard. It's a React 19 + Vite 6 + Tailwind CSS v4 single-page app. It talks only to the DriftGuard HTTP API (see [`docs/api.md`](../docs/api.md)), and the DriftGuard server hosts the built files.

Every number on screen comes from the API. If a value is missing, the dashboard shows "—". Nothing is filled in on the client.

## Install

```sh
cd frontend
npm install
```

## Develop

Run the backend on port 8000 and the Vite dev server on port 5173:

```sh
# terminal 1, from the repo root
python -m driftguard.server.cli --port 8000

# terminal 2
cd frontend
npm run dev
```

Open http://localhost:5173. Vite proxies `/auth`, `/projects`, `/events`, `/agent-events`, `/health` and the `/ws` WebSocket to `http://127.0.0.1:8000`, so everything is served from one origin, just as in production.

## Build

```sh
npm run lint    # tsc --noEmit (strict)
npm run build   # tsc --noEmit && vite build
```

The build writes to `../driftguard/server/static/` (`index.html` plus `assets/`), and the server serves that folder at `/`. The folder is gitignored, so it gets built at release or packaging time.

## How it works

- **Auth.** Sign in or create an account (sign-up is hidden when `GET /auth/config` reports `allow_signup: false`). The session token is kept in `localStorage` under `driftguard.session` and sent as `Authorization: Bearer <token>`. Any 401 clears it and returns you to the sign-in screen.
- **Filters.** The environment and time-range selects in the header apply to every view as the documented `environment` and `time_range` query params. `environment` is left out when set to "all". The selected project and filters are remembered in `localStorage`.
- **Realtime.** For the selected project, the dashboard opens a WebSocket to `/ws/projects/{id}` and sends the session token as the second subprotocol (`["driftguard", token]`), never in the URL. Alert messages refresh the alerts, summary and diagnosis, and a new critical alert shows a toast. The socket reconnects with exponential backoff up to 30 s. Close code 4401 signs you out.
- **Routing.** Routes are hash-based (`#/alerts`), so the server needs no SPA fallback routes.

## `src/` layout

```
src/
  main.tsx, App.tsx      entry point, session gate, app shell and view switch
  api.ts                 typed fetch client, ApiError, token storage, 401 handling
  types.ts               types mirroring docs/api.md
  index.css              Tailwind theme tokens (colors, fonts, motion) and base styles
  state/
    session.tsx          session context (sign in / out / expire)
    workspace.tsx        projects, selected project, filters, refresh keys, summary, realtime
    queries.ts           useProjectQuery: fetch with project and filters applied
  lib/
    format.ts            number/date formatting ("—" for missing values)
    storage.ts           guarded localStorage access
    useResource.ts       loading/error/data hook with abort and stale-data refresh
    useRealtime.ts       WebSocket with backoff and connection state
    useDialog.ts         focus trap, Escape, and scroll lock for modals and drawers
    route.ts             hash router and nav items
    validation.ts        project ID, email and number parsing
  components/            shell (Sidebar, Header, ConnectionIndicator), primitives (Button,
                         Field, Panel, Overlay, Badges, States, Table, Copy, MetricCard,
                         Toasts, Logo), and modals (CreateProjectModal, TestTelemetryModal)
  charts/                Recharts wrappers: timeline, metric line, scatter, severity bars,
                         risk breakdown
  views/                 SignIn, NoProjects, Overview, AgentDiagnosis, Events, Alerts,
                         Analytics, Policy, SdkIntegration, ProjectSettings
```
