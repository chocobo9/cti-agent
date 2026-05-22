# CTI-Agent · V1.b Implementation Spec

> Hi-fi reference: `index.html` artboard **V1.b**
> Companion files: `v1-classic.jsx`, `v2-workspace.jsx`, `fullscreen.jsx`, `shared-intel.jsx`
> Backend contract: LangGraph `AttributionState`

V1.b is the chosen frontend for CTI-Agent. It's a two-pane workspace built around the **attribution-confidence** pipeline (graph paths + RAG + evidence eval). Output is a structured `AttributionState`, not free-form text.

---

## 1. Tech & dependencies

- **Framework**: React 18, TypeScript recommended
- **Styling**: CSS-in-JS or CSS Modules — no Tailwind needed (design uses ~5 color tokens, predictable layout)
- **Fonts** (Google Fonts):
  - `Geist` 400/500/600/700 — sans
  - `Geist Mono` 400/500/600 — for IOC values, hashes, IPs, identifiers
- **Icons**: any lucide-style 1.5px-stroke set; the prototype uses inline SVGs (~25 icons total — see `Icon` in `shared-intel.jsx`)
- **No** charting library required — the only chart is a small SVG node-edge graph (see §10)

---

## 2. Layout (1440 × 900 reference, fully responsive)

```
┌─────┬─────────────────────────────────────┬──────────────────────┐
│     │ Topbar (48px)                       │                      │
│     ├─────────────────────────────────────┴──────────────────────┤
│ R   │                                                            │
│ a   │   CHAT (flex 1 1 56%)              │  PINBOARD (420px)    │
│ i   │                                     │  ┌────────────────┐  │
│ l   │   - Previous turn (collapsed)      │  │ Segmented      │  │
│     │   - User message                    │  │ Pinned │ Raw   │  │
│ 56  │   - Agent intro                     │  ├────────────────┤  │
│ px  │   - Node queue (6 nodes,            │  │ ATTRIBUTION    │  │
│     │     expandable rows)                │  │ CANDIDATES     │  │
│     │   - Attribution result card         │  │ INFRASTRUCTURE │  │
│     │     (done / running / error)        │  │ EVIDENCE CHAIN │  │
│     │                                     │  └────────────────┘  │
│     │   ───────────────────────           │                      │
│     │   Composer                          │                      │
└─────┴─────────────────────────────────────┴──────────────────────┘
```

Three columns: **Rail (56px) | Chat (flex) | Pinboard (420px)**. The pinboard width is fixed; chat takes remaining space (≥600px ideal). At narrow widths (<1100px) the pinboard can collapse to a slide-over drawer.

---

## 3. Design tokens

```ts
const tokens = {
  // base
  bg:          '#fafaf8',
  surface:     '#ffffff',
  rail:        '#fcfcfa',
  border:      '#ececea',
  divider:     '#f1f1ec',
  text:        '#0d0f12',
  textMute:    '#3a3d44',
  textSubtle:  '#6b6f78',
  textGhost:   '#9ea1a9',

  // brand accent (V1.b chat accent)
  accent:      '#3b5bdb',

  // attribution result tokens (mapped from `attribution_result` enum)
  high_confidence:   { fg: '#0a5d2b', bg: '#dcf5e6', dot: '#10b981' },
  medium_confidence: { fg: '#8a5a00', bg: '#fff3d6', dot: '#f59e0b' },
  low_confidence:    { fg: '#9c3a1b', bg: '#fde2d6', dot: '#ea580c' },
  insufficient:      { fg: '#3a3d44', bg: '#ececea', dot: '#9ca0b0' },

  // source badges (graph / rag / llm)
  src_graph: { fg: '#3b1a8f', bg: '#ede9fc' },
  src_rag:   { fg: '#0a5078', bg: '#dfecf6' },
  src_llm:   { fg: '#6b6f78', bg: '#ececea' },

  // graph status (Cypher template results)
  status_success: '#10b981',
  status_empty:   '#9ca0b0',
  status_error:   '#dc2626',
  status_no_match:'#f59e0b',
};

// radius scale: 4 / 6 / 7 / 8 / 10 / 12 / 14
// shadow: only the composer + ⤢ fullscreen modal use shadows
// gap scale: 4 / 6 / 8 / 12 / 14 / 18 / 24
```

---

## 4. Backend contract — `AttributionState`

The frontend consumes one JSON object per query. Shape (TypeScript):

```ts
type AttributionResult = 'high_confidence' | 'medium_confidence' | 'low_confidence' | 'insufficient';
type CypherStatus      = 'success' | 'empty' | 'error' | 'no_match';
type Source            = 'graph' | 'rag' | 'llm';

interface AttributionState {
  // identity
  query:        string;            // user question, e.g. "谁控制 hamadryas.online？"
  domain:       string;            // extracted IOC under investigation
  query_type:   'structural' | 'semantic' | 'mixed';

  // result
  attribution_result:        AttributionResult;
  confidence:                number; // 0–1
  temporal_confidence:       number; // 0–1 (180d half-life decay)
  is_shared_infrastructure:  boolean;
  needs_more_evidence:       boolean;

  candidate_actors: {
    actor_name:          string;
    confidence:          number;     // 0–1
    source:              Source;
    supporting_evidence: string[];   // human-readable bullets
  }[];

  // enrichment (pre-staged in Neo4j, surfaced by graph queries)
  enrichment: {
    passive_dns:  { ip: string; first_seen: string; last_seen: string }[];
    current_ips:  string[];
    rdap:         { creation_date: string; expiration_date: string; registrar: string };
    certificates: { fingerprint: string; issuer: string; san_list: string[];
                    not_before: string; not_after: string }[];
    geoip:        { ip: string; asn_number: number; asn_name: string;
                    country: string; city: string }[];
    jarm_hash:    string;
    favicon_hash: string;
  };

  // pipeline transparency
  graph_paths:   { status: CypherStatus; template: string; summary: string }[];
  rag_chunks:    { chunk_id: string; source: string; rrf_score: number; snippet: string }[];
  evidence_chain: string[];    // 1 line per reasoning step
  narrative:      string;       // final synthesized answer (markdown ok)
  sources:        { type: 'graph' | 'rag'; detail: string }[];
}
```

### Pipeline events (for the node queue UI)

The 6 LangGraph nodes are:

| # | id               | label                    | sub (one-line summary)                    |
|---|------------------|--------------------------|-------------------------------------------|
| 1 | `supervisor`     | Supervisor 路由           | `query_type → structural`                  |
| 2 | `infrastructure` | Infrastructure (Cypher×5)| `5 templates · 4 success / 1 empty`        |
| 3 | `intelligence`   | Intelligence (RAG)        | `12 chunks · top 3 RRF > 0.6`              |
| 4 | `graph_probe`    | Graph 验证                | `3 candidate actors validated`             |
| 5 | `evidence_eval`  | Evidence 评估             | `confidence = 0.85 · no iter.`             |
| 6 | `report`         | Report 合成               | `rendering markdown…`                      |

**Recommended streaming approach** (per backend handoff doc): wrap `graph.astream(stream_mode='values')` with an SSE/WebSocket adapter that emits one event per node transition:

```ts
type NodeEvent = {
  type: 'node_start' | 'node_done' | 'node_error';
  node_id: string;
  ts: number;     // ms epoch
  duration_ms?: number;
  error?: string;
  // optional: partial state snapshot
};
```

If streaming isn't available yet, the UI falls back to a single "all-done" render with timings computed retroactively from `state.timings` (which the backend should attach).

---

## 5. Top bar (48px)

```
[Queries]  ›  hamadryas.online  [structural query]                [Markdown] [JSON] [PDF]  [Save]
```

- Left breadcrumb: workspace breadcrumb + current domain (mono font) + small chip showing `query_type`
- Right buttons (all 28px height, 7px radius):
  - **Markdown** — `navigator.clipboard.writeText(render_report_markdown(state))` + toast
  - **JSON**     — `Blob` download of `attribution_report.model_dump()`
  - **PDF**      — client-side `html2pdf.js` (or similar) over the chat + pinboard region
  - **Save**     — primary black button. Writes to `localStorage` history (see §11) and sidebar updates

---

## 6. Left rail (56px)

```
[Logo: black 30px square, "C"]
─────
[+]        New query (clears chat, focuses composer)
[history]  History list (shown as right-side drawer)
[graph]    [reserved — future: cross-query graph view]
[pin]      Saved/pinned queries
─────
[Avatar SY]
```

Active state: light background `#ececea`, dark icon. Inactive: transparent, gray icon.

---

## 7. Chat column

Vertical layout (top → bottom) inside scrollable area:

### 7.1 Previous turn (collapsed) — multi-turn UI

A thin clickable row above the current turn:

```
[time icon]  3h ago   auth-microsft365.com — 谁在用？   [Medium]  TA-577 · 0.62   ›
```

- Click → load that previous query's state and switch pinboard to its artifacts
- Background `#fff`, border `1px solid #ececea`, radius 8, padding `8px 12px`
- All previous turns from current session show here, newest last; tap on header to expand all

### 7.2 User message
Right-aligned, dark bubble (`#0d0f12` bg, white text), max-width `460px`, radius 16 (BR corner 6), 26px gray avatar circle on the right.

### 7.3 Agent intro (one paragraph)
Short routing summary: `路由为<结构化查询>。已运行 6 个 node：infrastructure → intelligence → graph_probe → evidence_eval → 合成报告。`

### 7.4 Node queue
A white-card list of 6 rows, one per pipeline node.

**Per row:**
- Chevron (▸ / ▾) on the far left — present if row is expandable (any node not in `queued` state)
- Status indicator:
  - `done` → green check inside soft green pill (`#e6f6ee` bg)
  - `running` → 14px ring with spinning top-color
  - `error` → red X inside soft red pill (`#fde6e6` bg)
  - `queued` → dashed gray ring
- Index `1.` `2.` `3.` … (mono, gray)
- Node label (sans, 13px, weight 500)
- Sub-summary (`· ${node.sub}`, gray)
- Right-aligned: duration (`240ms`) or status text (`running…`, `queued`, `failed`)

**Expansion content (per node):**

| Node            | Expanded body                                                                         |
|-----------------|---------------------------------------------------------------------------------------|
| `supervisor`    | `query_type` key-value                                                                |
| `infrastructure`| For each `graph_paths[i]`: `[status pill] template_name … summary`                    |
| `intelligence`  | For each top RAG chunk: `[source pill] chunk_id  "snippet"  RRF 0.82`                  |
| `graph_probe`   | For each `candidate_actors[i]`: `✓  TA-577  [GRAPH]  0.85`                            |
| `evidence_eval` | Key-value list: `confidence: 0.85`, `temporal_confidence: 0.72`, `is_shared…: false`, …|
| `report`        | One sentence: `Rendering markdown / JSON / IOC list. N sources, M-char narrative.`     |

Row hover: subtle gray bg. Click anywhere on the row toggles expansion.

### 7.5 Attribution result card

This card has **three render modes** keyed by pipeline state:

#### A. `done` — success card
```
┌─────────────────────────────────────────────────┐
│ hamadryas.online                [HIGH CONF.]    │   ← mono headline + confidence badge
├─────────────────────────────────────────────────┤
│ TOP ACTOR  CONFIDENCE  TEMPORAL  SHARED INFRA   │   ← 4-cell stat grid
│ TA-577     0.85        0.72      No             │
├─────────────────────────────────────────────────┤
│ {narrative — 2-3 sentence summary}              │
├─────────────────────────────────────────────────┤
│ [查看证据链] [展开候选演员] [复制 Markdown] [导出 JSON] │   ← action chips
└─────────────────────────────────────────────────┘
```

Confidence badge: pill with dot + label (e.g. `● High confidence`), color per token.

#### B. `running` — skeleton card
- Same outer chrome
- Top bar shimmer (moving gradient stripe)
- Title row: spinner + domain + pill `Analyzing…`
- Stat grid labels visible, values replaced by `70%`-width gray bars
- Narrative replaced by 3 gray skeleton lines (95% / 88% / 60%)
- Footer text: `已完成 3 / 6 个 node · 预计 2–3s 后完成`

#### C. `error` — red bordered card
```
🔥 Pipeline halted
intelligence node 失败：RAG retrieval timeout (vector store unreachable after 30s)。
前 2 个 node 的结果仍可看，但未能完成归因。
[重试 pipeline] [仅跑 graph (跳过 RAG)] [查看错误日志]
```

Border-left red `#a31a1a`, soft red-pink border.

### 7.6 Action chips → these wire to:

| Chip               | Action                                                                 |
|--------------------|------------------------------------------------------------------------|
| 查看证据链          | Switch pinboard segmented control to *Pinned*, scroll Evidence card into view, or open Evidence ⤢ fullscreen directly |
| 展开候选演员        | Open Candidates ⤢ fullscreen                                            |
| 复制 Markdown       | Same as topbar Markdown button                                          |
| 导出 JSON           | Same as topbar JSON button                                              |

### 7.7 Composer

White card at bottom, radius 14, padding `12 14 10`:
- Multi-line textarea (placeholder: `追问 / 提供更多 IOC… e.g. "用 SAN 模式查相邻域名"`)
- Bottom row: attach icon + model badge (`DeepSeek · LangGraph`) on left, send button (30px dark square) on right
- Below card, centered: `归因结果基于 graph + RAG 证据 · 仅供参考`
- `Cmd/Ctrl + Enter` to send

---

## 8. Pinboard (right column, 420px)

### 8.1 Header — segmented control

Two segments only:

```
[ Pinned | Raw JSON ]
```

`Pinned` is default. Background `#eef0f6`, active segment white with subtle shadow.

### 8.2 Pinned view — 4 cards stacked vertically, scrollable

All cards share the **PinCard chrome**:
- 22px icon tile (tag accent bg @ 8% opacity)
- Tag label (10px, weight 700, letterSpacing 0.8, uppercase, in accent color)
- Title (14px, weight 600)
- ⤢ button top-right (26px transparent button with `ext` icon) — opens fullscreen modal

#### Card 1 — ATTRIBUTION RESULT
- Tag color = `attribution_result` token dot color
- Title: `{label}  ·  {confidence.toFixed(2)}`
- Body:
  - Two horizontal confidence bars (`Attribution` and `Temporal (180d HL)`) with value pills on right
  - Two flag chips (gray bg, 5x9 padding): `Shared infra: Dedicated/CDN detected`, `Evidence sufficiency: sufficient/iterate`

#### Card 2 — CANDIDATE ACTORS
- Tag color `#7c3aed`
- Title: `{N} ranked`
- Body: list of candidate rows. **Each row is expandable** (click chevron):
  - Collapsed: `▸  TA-577  [GRAPH]            0.85`
  - + thin black confidence bar (3px)
  - Expanded: list of `supporting_evidence` strings, mono, with `•` bullet, left border

#### Card 3 — INFRASTRUCTURE
- Tag color = accent `#3b5bdb`
- Title: `{N} resolutions · {M} certs`
- Body sections (top → bottom):
  1. **RDAP grid** (3 cells): Registered / Registrar / Expires
  2. **Passive DNS** label + per-IP rows: `IP   [LIVE]   country·ASN   first→last`
  3. **Certificates** label + per-cert rows: `🔒 fingerprint   issuer`
  4. **Fingerprint badges** row: `[🖐 JARM 2ad2ad…]` `[🖐 favicon ab12…]`

#### Card 4 — EVIDENCE CHAIN
- Tag color `#10b981`
- Title: `Reasoning trail · transparent`
- Body: numbered evidence_chain steps in a left-bordered list. Below: 2 count chips: `5 Cypher templates`, `3 RAG chunks`

### 8.3 Raw JSON view
Full `AttributionState` JSON in `<pre>`, mono, scrollable. Top right: `[Copy]` button → `navigator.clipboard.writeText(JSON.stringify(state, null, 2))`; on success, button briefly shows `Copied` with green tick (1.4s).

---

## 9. Fullscreen card modals

Opened by clicking ⤢ on any pinned card. Modal covers the whole V1.b area (not the viewport — scoped to the workspace).

**Modal chrome:**
- Backdrop: `rgba(13,17,36,0.45)` + `backdrop-filter: blur(3px)`
- Body: white card, `min(1100px, 92%)` wide, max-height `88%`
- Header: 14px padding, accent icon tile + section title + close button (X, Esc-handled)
- Body: scroll on overflow

### 9.1 Attribution fullscreen
- Big confidence "verdict" hero band (accent-tinted bg with left border)
- Two detail blocks side-by-side: Attribution confidence + Temporal confidence (both with progress bars and explanatory subtext)
- Two flag blocks below (Shared infra / Evidence sufficiency)
- "Sources used" list at bottom

### 9.2 Candidates fullscreen — **contains the big node-edge graph**
Two-column grid:
- Left: Candidates list (same as pinned but fully expanded, all evidence visible)
- Right: **Attribution path** — node-edge SVG graph (see §10) inside a bordered panel, with footer line citing `T2_domain_to_actor · T3_infrastructure_pivot`

### 9.3 Infrastructure fullscreen
Vertical sections:
1. 6-cell KV grid (Domain / Registrar / Registered / Expires / Active IPs / Certificates)
2. **Passive DNS timeline** — Gantt-style: each IP row has [IP+LIVE chip] | [country·ASN] | [bar from first→last seen] | [date range mono]
3. **Certificates** — each cert in a 3-col row: Fingerprint / SAN list / Validity dates
4. **Fingerprints** — JARM and favicon as larger cards, each with `[copy]` button + a one-line hint about how to pivot

### 9.4 Evidence fullscreen
- **Evidence chain** as numbered card list (1, 2, 3…)
- Below, 2-column grid:
  - Left: Graph paths (Cypher) — each as `[STATUS pill] template_name` + summary line
  - Right: RAG chunks (top by RRF) — each with `[source pill] chunk_id   RRF 0.82` + italic snippet

---

## 10. Node-edge graph component

Used in Candidates fullscreen. Lightweight SVG, no graph library needed.

**Data source**: extract from `state.graph_paths` results — every node returned (domain, IPs, clusters, actors, siblings, campaigns) becomes a graph node, every relationship becomes an edge.

**Visual rules:**
- 30px radius for primary nodes (domain, actor), 22 for cluster, ~14–18 for satellites
- Stroke color by kind: `domain #0d0f12`, `cluster #a4a8c2`, `actor accent`, `ip #10b981`, `sibling #9ca0b0`, `campaign #f59e0b`
- White fill, label inside circle (mono for IPs/domains/hashes, sans for names)
- Edges: solid `#cdd1de` 1.2px with arrowhead for hierarchy (domain→cluster→actor); dashed for lateral (cluster→sibling, domain→IP)
- Small legend at bottom of canvas

A force-directed layout is **not** required — initial implementation can hard-code positions per `graph_paths` result kind (the backend's templates return predictable shapes).

> Variant **V1.c** also embeds a compact 360×150 version of this graph at the top of the Candidates pinned card. Decide later whether to ship V1.b (cleaner) or V1.c (more "at-a-glance" attribution).

---

## 11. State, persistence, error handling

### 11.1 History (left rail "history" icon)
- Stored in `localStorage` under key `cti.history.v1`
- Schema: `Array<{ id: string; ts: number; query: string; domain: string; result: AttributionResult; top_actor: string; top_confidence: number; state: AttributionState }>`
- Max 50 entries (FIFO eviction)
- Clicking a history row replays the saved state into chat + pinboard

### 11.2 Multi-turn within a session
- In-memory `turns: Array<AttributionState>`
- Chat renders the **current** turn fully expanded. Previous turns render as collapsed rows above the user message (see §7.1).
- Pinboard always reflects the currently-focused turn (latest by default; clicking a previous turn row switches focus).

### 11.3 Loading state
- Triggered when streaming is active (`node_start` received, `node_done` not yet received for all nodes)
- Attribution result card switches to render mode **B (running)** until final `node_done` for `report` arrives
- Node queue shows live status per node

### 11.4 Error state
- Triggered when any node emits `node_error` OR when overall pipeline yields `attribution_result: 'insufficient'` with `error` flag set
- Attribution card switches to render mode **C (error)**
- Action buttons: **Retry pipeline** (re-send same query), **仅跑 graph (跳过 RAG)** (re-send with `skip_rag: true` param — backend must support), **查看错误日志** (open log drawer)

### 11.5 `needs_more_evidence: true`
- Show a small banner inside the Attribution card (above action chips): `证据不足 — 建议提供更多 IOC 或运行额外模板`
- Don't block the result; just nudge

---

## 12. Recommended file structure

```
src/
├── App.tsx
├── lib/
│   ├── api.ts                  // SSE/WS streaming client, POST /query
│   ├── tokens.ts               // design tokens from §3
│   └── history.ts              // localStorage helpers from §11.1
├── types/
│   └── AttributionState.ts     // §4 types
├── components/
│   ├── chat/
│   │   ├── ChatColumn.tsx
│   │   ├── PreviousTurn.tsx
│   │   ├── UserMsg.tsx
│   │   ├── AgentIntro.tsx
│   │   ├── NodeQueue.tsx       // includes expandable NodeRow + NodeDetails
│   │   ├── AttributionResult/
│   │   │   ├── Done.tsx
│   │   │   ├── Running.tsx
│   │   │   └── Error.tsx
│   │   └── Composer.tsx
│   ├── pinboard/
│   │   ├── Pinboard.tsx        // segmented control + view switcher
│   │   ├── PinCard.tsx
│   │   ├── AttributionCard.tsx
│   │   ├── CandidatesCard.tsx
│   │   ├── InfrastructureCard.tsx
│   │   ├── EvidenceChainCard.tsx
│   │   └── RawJsonPanel.tsx
│   ├── fullscreen/
│   │   ├── FullscreenModal.tsx
│   │   ├── AttributionFs.tsx
│   │   ├── CandidatesFs.tsx
│   │   ├── InfrastructureFs.tsx
│   │   ├── EvidenceFs.tsx
│   │   └── NodeEdgeGraph.tsx
│   ├── shared/
│   │   ├── ConfidenceBadge.tsx
│   │   ├── SourceBadge.tsx
│   │   ├── StatusPill.tsx
│   │   └── Icon.tsx
│   ├── topbar/Topbar.tsx
│   └── rail/Rail.tsx
└── pages/
    └── QueryWorkspace.tsx      // wires the 3 columns together + owns fullscreen state
```

---

## 13. Accessibility & keyboard

- `Esc` closes fullscreen modal
- `Cmd/Ctrl + Enter` sends composer
- `Cmd/Ctrl + K` focuses topbar search (optional, future)
- All buttons keyboard-focusable, visible focus ring (1.5px outline, accent color)
- Status colors paired with icons/text (never color-only)
- All IOC values copyable (single-click any `<code>` element or use dedicated copy buttons)

---

## 14. Things explicitly NOT in V1.b (per design decisions)

- ❌ Risk score 0–100 (backend doesn't compute one)
- ❌ VirusTotal detection ratio
- ❌ MITRE ATT&CK TTP mapping
- ❌ Playbook generation card
- ❌ Cases / persistent case management (replaced by history)
- ❌ STIX 2.1 export
- ❌ Per-IP malicious verdict badges
- ❌ Sandbox detonation UI

---

## 15. Reference prototype

Open `index.html` artboard **V1.b** for the canonical visual reference. Source code:
- `v1-classic.jsx`   — chat side, rail, topbar, attribution-result card with 3 states
- `v2-workspace.jsx` — `PinboardColumn` + 4 pinned cards (V1.b imports it as the right pane)
- `fullscreen.jsx`   — fullscreen modal + 4 detail views + NodeEdgeGraph
- `shared-intel.jsx` — sample `INTEL` data + tokens + Icon set
