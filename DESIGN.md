# Design System: DriftGuard

**Project:** DriftGuard
**Purpose:** A professional observability console for monitoring LLM quality, detecting prompt and retrieval drift, diagnosing failed agent tools, and reducing wasted tokens.
**Design source:** Existing DriftGuard dashboard shell and backend product language.

## 1. Visual Theme & Atmosphere

DriftGuard is a dense, serious developer operations interface. The visual language is dark, precise, and technical without becoming noisy or cyberpunk-themed. It should feel like a trusted control room for AI reliability: calm when systems are healthy, unmistakable when intervention is needed, and optimized for scanning live metrics rather than browsing marketing content.

Use a near-black workspace with a faint technical grid, graphite navigation surfaces, thin borders, compact panels, and restrained glow only for active or critical states. Favor strong hierarchy, short labels, monospace telemetry values, and clear status color semantics. Avoid decorative hero sections, stock imagery, login or signup screens, excessive gradients, and oversized rounded cards.

The UI represents real product capabilities. Do not imply that DriftGuard automatically observes private Copilot sessions or silently changes model providers. Use precise language such as "normalized telemetry," "agent event," "blocking tool," "wasted tokens," and "recommendation."

## 2. Color Palette & Roles

### Core surfaces

- **Pitch Black Workspace (#000000):** Primary application background and dashboard canvas.
- **Obsidian Sidebar (#020202):** Fixed navigation rail and brand area.
- **Graphite Panel (#050505):** Cards, charts, tables, drawers, and focused content surfaces.
- **Raised Graphite (#0A0A0A):** Hovered panels, selected rows, and secondary elevated surfaces.
- **Input Black (#030303):** Selects, text inputs, code blocks, and compact filter controls.

### Text and structure

- **Signal White (#FFFFFF):** Page titles, primary values, active navigation, and high-priority labels.
- **Telemetry Gray (#F4F4F5):** Body text, secondary metric labels, and readable operational copy.
- **Muted Zinc (#A1A1AA):** Supporting text, timestamps, inactive navigation, and helper copy.
- **Hairline Zinc (#171717):** Default borders, dividers, table rules, and quiet separation.

### Semantic accents

- **Electric Cyan (#28C7D9):** Primary interaction accent, active navigation, links, telemetry trend lines, focus rings, and refresh actions. Use sparingly against the black canvas.
- **Signal Green (#42D392):** Healthy system state, successful ingestion, saved tokens, positive trends, and online status.
- **Amber Warning (#F2B84B):** Degraded metrics, policy thresholds, pending actions, and warning alerts.
- **Coral Critical (#F06464):** Critical drift, blocked tasks, failed tools, error states, and actions requiring immediate review.
- **Violet Diagnostic (#A78BFA):** Optional secondary analytical series only when four or more metrics must be distinguished. Never use as the dominant brand color.

Accent colors are semantic, not decorative. Every colored chart series, badge, dot, and border must communicate a state or category. Pair color with text, icons, or shape so meaning is not color-dependent.

## 3. Typography Rules

- **Display and headings:** Space Grotesk, 600-800 weight. Use for the DriftGuard wordmark, page titles, section titles, and prominent metric values.
- **Interface and body:** Plus Jakarta Sans, 500-700 weight. Use for navigation, labels, controls, descriptions, tables, and alerts.
- **Telemetry and code:** JetBrains Mono, 500-700 weight. Use for token counts, risk scores, event IDs, timestamps, API keys, task IDs, tool names, code examples, and diagnostic output.
- **Heading scale:** Page titles are compact and operational, generally 28-32px. Section headings are 16-20px. Avoid display-scale marketing typography.
- **Label treatment:** Use concise uppercase labels with modest tracking for metric categories and filter labels. Do not apply excessive letter spacing to paragraphs or values.
- **Numerical hierarchy:** Large metric values should be easy to scan, with the unit or comparison rendered smaller and muted beneath or beside the value.
- **Line height:** Use approximately 1.2 for headings and 1.5 for body copy. Keep dense tables and telemetry rows closer to 1.35 for efficient scanning.

## 4. Component Stylings

### Buttons

Buttons have compact, subtly rounded corners (6-8px), a clear 40-44px minimum height, and visible focus states. Primary actions use Electric Cyan (#28C7D9) with dark text or a dark surface with a cyan border depending on contrast. Secondary actions use Graphite surfaces with Hairline Zinc borders. Destructive or urgent actions use Coral Critical (#F06464) only when the action itself is destructive.

Use familiar icons inside action buttons where appropriate: refresh, play/test, copy, save, filter, expand, and close. Icon-only buttons require accessible labels and tooltips. Hover states should brighten the border or surface without causing layout shift.

### Navigation

The sidebar is fixed on desktop and approximately 240-260px wide. Navigation items are compact rows with 8px corner rounding, muted text by default, and a dark raised active state with a clear cyan edge or indicator. Badges show event and alert counts using monospace text and semantic colors.

On mobile, collapse the sidebar into a labeled menu control. Preserve the active location and keep the system status visible near the top of the opened navigation.

### Metric cards

Metric cards are compact, square-edged or subtly rounded containers with a graphite background, thin border, and no heavy shadow. Each card contains a small category label, a large monospace value, and a concise comparison or state line. Critical cards may use a coral border or value, but do not turn the whole card into a saturated block.

Recommended overview metrics include total telemetry events, saved tokens, active alerts, mean retrieval score, drift risk, response quality, failed attempts, and estimated saved cost.

### Charts and analytics panels

Charts sit inside unframed or lightly framed panels with enough padding for axis labels and legends. Use cyan for prompt or volume series, green for retrieval or healthy quality, amber for warnings, and coral for critical events. Include hover tooltips, explicit legends, readable axes, and an empty state when there is no telemetry.

Use line or area charts for time series, compact bars for comparisons, a risk breakdown for root causes, and sparklines for card-level trends. Do not use 3D charts or ornamental chart effects.

### Tables and event explorer

Tables use a dark graphite surface, hairline row separators, compact 44-52px rows, and monospace values for IDs, timestamps, token counts, and scores. Status cells contain both a semantic color and a text label. Support search, filtering, sortable columns where useful, and a detail drawer for inspecting a selected event without losing the current table position.

### Alerts and diagnosis

Alert rows should make severity scannable through a left border, status icon, text label, timestamp, affected metric, and recommended action. The Agent Task Diagnosis panel should clearly expose task ID, trace ID, blocking tool, failed attempts, repeated attempts, wasted tokens, error type, severity, and recommendation.

The most important diagnosis should be stated plainly, for example: "The terminal tool failed three times while running tests; 6,420 tokens were spent on retries."

### Inputs, selects, and policy controls

Inputs and selects use Input Black (#030303), Hairline Zinc borders, 6px corner rounding, and a cyan focus ring. Labels are visible and concise. API key fields are password inputs with helper text and no provider-secret language. Policy editors use labeled numeric inputs, threshold descriptions, save/reset controls, and explicit success or error feedback.

### Code blocks

SDK integration examples use JetBrains Mono on Input Black with syntax color limited to readable cyan, green, amber, and muted gray. Include copy controls with an accessible label and a brief copied confirmation. Show provider-neutral examples for `capture_metrics`, `capture_agent_event`, `sync_metrics`, and `fetch_agent_diagnosis`.

### Drawers, modals, and overlays

Use drawers for event and alert detail because users should retain dashboard context. Use modals only for focused actions such as creating a project or confirming a destructive policy change. Overlays use a near-black scrim, compact graphite surface, 8px rounding, and a visible close button. Never stack cards inside cards without a clear functional reason.

## 5. Layout Principles

- Use a fixed desktop sidebar with a flexible main content region. The main content should be capped near 1600px and use generous outer gutters without wasting vertical space.
- Organize overview content into a four-column metric row, followed by two-column analytics panels, then alerts and diagnosis sections. Collapse to one column below tablet widths.
- Prefer 8px spacing increments. Use approximately 16-24px internal panel padding and 24-40px between major dashboard sections.
- Keep filters and context selectors in the global header. They should remain visible near the content they affect and should not be hidden inside decorative cards.
- Use stable dimensions for charts, metric cards, tables, navigation rows, and icon controls so hover states and dynamic data do not move surrounding content.
- Keep important status and diagnosis content above the fold. Long event tables and SDK examples can scroll within their own region.
- On mobile, stack metrics, allow chart overflow when necessary, make tables horizontally scrollable, and keep Refresh, Test Telemetry, and filter access reachable without excessive scrolling.
- Use a subtle 32px technical grid or fine linear pattern behind the workspace at very low opacity. It should add atmosphere without competing with data.

## 6. Interaction and Motion

Motion is functional and restrained. Use 150-220ms ease-out transitions for navigation, buttons, filters, drawers, and chart state changes. Use a short page-load reveal for major dashboard sections with a small stagger, but avoid continuous ambient animation except for the online status pulse.

### Dynamic Hover Ring

Use the Dynamic Hover Ring as an optional desktop pointer enhancement for clickable dashboard elements and links:

- A small crisp dot follows the pointer in real time.
- A larger outer ring follows with a slight delay, creating a controlled trailing effect.
- When the pointer enters a link, button, select, copy control, table row, or other explicitly interactive element, the ring expands smoothly, shifts to Electric Cyan (#28C7D9), and may become a low-opacity filled circle.
- Hide the default cursor only while the custom pointer is active and only on fine-pointer devices. Keep the native cursor on touch and coarse-pointer devices.
- Implement the ring with two fixed, pointer-events-none elements positioned from `clientX` and `clientY`. Use CSS transforms for movement and `mix-blend-mode: difference` only where contrast remains readable.
- Use light JavaScript or GSAP for pointer tracking and hover enter/leave state. Prefer `requestAnimationFrame` or a lightweight motion utility; do not add a large animation dependency solely for this effect.
- Keep the dot crisp at approximately 6px and the ring approximately 28-36px at rest. Expand the ring to approximately 48-64px over interactive controls.
- Do not let the ring block clicks, obscure text, interfere with keyboard focus, or appear in screenshots intended for reduced-motion users.
- Add `@media (prefers-reduced-motion: reduce)` rules that disable trailing interpolation and expansion transitions. Do not hide focus outlines when the ring is enabled.
- Scope the behavior to `@media (hover: hover) and (pointer: fine)` and disable it when the document is not the active window.

The hover ring is a quiet brand detail, not the primary way users discover interaction. All controls must remain understandable and usable without it.

## 7. Accessibility and State Rules

- Maintain visible keyboard focus with a 2px Electric Cyan (#28C7D9) outline or equivalent high-contrast treatment.
- Provide text labels for all severity states and pair status colors with icons or symbols.
- Use semantic headings, landmarks, labels, live regions for refresh status, and accessible names for icon-only controls.
- Support `prefers-reduced-motion`, keyboard navigation, zoom, and touch input.
- Define loading, empty, error, offline, and success states for dashboard data, charts, event tables, alerts, project creation, policy saves, and test telemetry.
- Never use the hover ring, animation, or color alone to communicate system health or action availability.

## 8. Product Language

Use concise, factual interface language:

- "Operational Overview"
- "Telemetry & Drift Timeline"
- "Drift Risk Breakdown"
- "Active Alerts"
- "Agent Task Diagnosis"
- "Blocking Tool"
- "Repeated Attempts"
- "Wasted Tokens"
- "Mitigation Recommendation"
- "Test Telemetry"
- "SDK Integration"
- "System Online"

Avoid generic marketing phrases, account-growth language, signup prompts, and claims that DriftGuard automatically intercepts private agent sessions.
