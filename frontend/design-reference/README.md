# CTI-Agent · Frontend handoff

This project contains a high-fidelity React prototype of the CTI-Agent frontend.

## ➡ Implement V1.b ONLY

The **canonical implementation spec** is **[`V1b-spec.md`](./V1b-spec.md)**. Read it first — it covers:

- Backend contract (`AttributionState` shape from LangGraph)
- Layout (3 columns: rail / chat / pinboard)
- Design tokens (colors, fonts, radii, spacing)
- Every component spec
- Interactions, states (done / running / error), multi-turn behaviour
- Fullscreen modal detail views
- File-structure recommendation for the production codebase

## Visual reference

Open **`v1b.html`** to see the V1.b prototype rendered fullscreen (the single canonical design).

`index.html` is the design-exploration canvas with multiple variants — useful to see the design history, but **do not implement everything you see there**.

## What's in the project

| File | Role | Implement? |
|------|------|-----------|
| **`V1b-spec.md`** | The implementation spec — the source of truth | ✅ Follow this |
| **`v1b.html`** | Standalone V1.b preview (single-page) | ✅ Visual reference |
| `shared-intel.jsx` | Sample `AttributionState` data + design tokens + Icon set + ConfidenceBadge / SourceBadge | ✅ Lift tokens & types |
| `v1-classic.jsx` | V1.b's chat side: rail, topbar, multi-turn, node queue, attribution-result card (3 states), composer | ✅ Use as reference |
| `v2-workspace.jsx` | The `PinboardColumn` + 4 pinned cards + segmented control (used as V1.b's right pane) | ✅ Use `PinboardColumn` & pinned cards |
| `fullscreen.jsx` | The ⤢ fullscreen modals (Attribution / Candidates / Infrastructure / Evidence) + `NodeEdgeGraph` | ✅ Use as reference |
| `index.html` | Design-exploration canvas (V1 / V1.b / V1.c / V2 side by side) | ⚠️ Reference only — DON'T copy literally |
| `design-canvas.jsx` | Prototyping wrapper (pan/zoom/artboard chrome) | ❌ Throw away — not part of product |

## What to ignore in `index.html`

The exploration canvas shows four artboards. **Only V1.b is the design to ship.** The others exist purely for design comparison:

- ❌ **V1** (tabbed right panel) — earlier variant, superseded
- ✅ **V1.b** (pinboard right panel) — **THIS is what to implement**
- ❌ **V1.c** (V1.b with inline node-edge graph in Candidates card) — saved for future evaluation; do not ship
- ❌ **V2** (3-column workspace with case sidebar) — reference for the pinboard pattern; not for implementation

## Tech assumptions for production

- React 18 + TypeScript
- The prototype uses Babel-standalone + inline JSX. Production should be a proper toolchain (Vite / Next.js).
- Real backend: a `POST /query` (or WebSocket / SSE) that returns / streams `AttributionState`. See spec §4 for the data contract and §11 for streaming / loading / error handling.
- No external charting library needed — the only chart is a small SVG node-edge graph (see spec §10).
- Fonts: Geist + Geist Mono (Google Fonts). No paid fonts.

## What is **explicitly NOT** in V1.b (don't add these)

The backend doesn't support these — the design intentionally omits them:

- ❌ Risk score 0–100 (no such field in `AttributionState`)
- ❌ VirusTotal detection ratio (not integrated)
- ❌ MITRE ATT&CK TTP mapping
- ❌ Playbook generation
- ❌ Cases / persistent case management (replaced by client-side history in `localStorage`)
- ❌ STIX 2.1 export
- ❌ Per-IP malicious verdict badges (no per-IP reputation source)
- ❌ Sandbox detonation UI

See spec §14 for the full list.
