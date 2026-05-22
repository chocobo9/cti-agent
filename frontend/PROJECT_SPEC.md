# PROJECT_SPEC.md — CTI-Agent Frontend V1.b

> 工作流约束见 `CLAUDE.md`。
> 组件 spec 见 `design-reference/V1b-spec.md`——本文件定义执行步骤和 verify，不重复 spec 内容。

---

## 1. Project Setup

### Tech Stack (spec §1)
- React 18 + TypeScript (strict)
- Vite
- CSS Modules (spec says "CSS-in-JS or CSS Modules — no Tailwind needed")
- Fonts: Geist 400/500/600/700 + Geist Mono 400/500/600 (Google Fonts)
- Icons: inline SVG (~25 icons, see `Icon` in `shared-intel.jsx`)
- No external charting library, no external component library

### Design Reference Files Location
```
design-reference/
├── V1b-spec.md          ← MUST read before every Step
├── v1b.html             ← visual reference
├── shared-intel.jsx     ← types, tokens, icons, sample data
├── v1-classic.jsx       ← chat column components
├── v2-workspace.jsx     ← pinboard components
├── fullscreen.jsx       ← modal components + NodeEdgeGraph
└── index.html           ← DO NOT copy from this
```

---

## 2. Target File Structure (spec §12 — MANDATORY)

```
src/
├── App.tsx
├── lib/
│   ├── api.ts                  // SSE/WS streaming client
│   ├── tokens.ts               // design tokens from spec §3
│   └── history.ts              // localStorage helpers from spec §11.1
├── types/
│   └── AttributionState.ts     // spec §4 types
├── components/
│   ├── chat/
│   │   ├── ChatColumn.tsx
│   │   ├── PreviousTurn.tsx
│   │   ├── UserMsg.tsx
│   │   ├── AgentIntro.tsx
│   │   ├── NodeQueue.tsx       // expandable NodeRow + NodeDetails
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
├── fixtures/
│   └── sampleState.ts          // from shared-intel.jsx INTEL object
└── pages/
    └── QueryWorkspace.tsx       // wires 3 columns + owns fullscreen state
```

禁止创建此列表以外的组件文件。辅助文件（CSS modules、test files、scripts/verify-*.mjs）除外。

**视觉验证脚本（Step 1 创建，后续 Step 使用）：**
```
scripts/
├── verify-layout.mjs     ← Step 2: Rail/Pinboard/Topbar 尺寸
├── verify-tokens.mjs     ← Step 3+: ConfidenceBadge/SourceBadge 颜色
├── verify-modals.mjs     ← Step 7: 4 个 fullscreen modal 打开/关闭/内容
└── verify-e2e.mjs        ← Step 8: 端到端流程截图
```

---

## 3. Execution Steps

### 执行顺序

```
Step 1 [I-V]: Vite scaffolding + types + tokens + mock data
  ↓
Step 2 [I-V]: Layout shell (QueryWorkspace + 3 columns) + Rail + Topbar
  ↓ ← 暂停，用户确认 layout
Step 3 [I-V]: Shared atoms (Icon, ConfidenceBadge, SourceBadge, StatusPill)
  ↓
Step 4 [I-V]: Chat column — Composer, UserMsg, AgentIntro, NodeQueue (6 nodes × 4 states × expansion)
  ↓
Step 5 [I-V]: Chat column — AttributionResult 3 render modes (Done / Running / Error) + action chips
  ↓ ← 暂停，用户确认 chat column
Step 6 [I-V]: Pinboard — segmented control + 4 pinned cards + RawJsonPanel
  ↓
Step 7 [I-V]: Fullscreen modals (4 views) + NodeEdgeGraph SVG
  ↓ ← 暂停，用户确认完整 UI
Step 8 [I-V]: Streaming (api.ts + SSE) + state management + multi-turn + localStorage history
  ↓
向用户汇报完整结果
```

---

### Step 1 — Foundation [I-V]

**Spec sections:** §1 (tech), §3 (tokens), §4 (types)
**Reference files to read:** `shared-intel.jsx` (全文)

**做什么：**
1. `npm create vite@latest cti-frontend -- --template react-ts`
2. 配置 tsconfig（strict: true, noUnusedLocals, noUnusedParameters）
3. 在 `index.html` 加 Geist + Geist Mono 字体 link
4. 删除 Vite 模板默认文件
5. 创建 `src/types/AttributionState.ts` — 逐字段从 spec §4 转写 TypeScript interface
6. 创建 `src/lib/tokens.ts` — 从 spec §3 转写 design tokens 为 const 对象
7. 创建 `src/fixtures/sampleState.ts` — 从 `shared-intel.jsx` 的 `INTEL` 对象转写为完整 `AttributionState` 实例

**类型映射规则：**
- spec §4 定义了前端 `AttributionState` interface，它包含 `enrichment` 对象（Python 后端的 `enrichment_data`）
- `narrative` 和 `sources` 字段在前端 interface 中存在但 Python TypedDict 中没有——这些来自 `attribution_report` 的展开
- `AttributionResult`, `CypherStatus`, `Source` 是 union type，不是 string
- `NodeEvent` type 也在 §4 末尾定义

**verify:**
```bash
cd cti-frontend && npx tsc --noEmit   # 0 errors
npx vite build                         # success, no warnings
# 在 App.tsx 中临时: import { sampleState } from './fixtures/sampleState'; 
# const s: AttributionState = sampleState; — tsc 不报错证明类型完整
```

**Playwright 安装（本 Step 一次性完成，后续 Step 的视觉 verify 依赖它）：**
```bash
npm install -D @playwright/test
npx playwright install chromium
```

创建 `scripts/verify-layout.mjs` 和 `scripts/verify-tokens.mjs`（见 CLAUDE.md §4 视觉验收 的模板代码）。这两个脚本在 Step 2+ 的暂停点使用。

---

### Step 2 — Layout + Rail + Topbar [I-V]

**Spec sections:** §2 (layout), §5 (topbar), §6 (rail)
**Reference files to read:** `v1-classic.jsx` (搜索 `Rail` 和 `Topbar` 部分), `V1b-spec.md` §2/§5/§6

**做什么：**
1. `pages/QueryWorkspace.tsx` — 三列 layout: Rail (56px fixed) | ChatColumn (flex) | Pinboard (420px fixed)
2. `components/rail/Rail.tsx` — spec §6: logo + new query + history + graph(reserved) + pin + avatar
3. `components/topbar/Topbar.tsx` — spec §5: breadcrumb + query_type chip + Markdown/JSON/PDF/Save buttons

**Layout 关键细节 (spec §2):**
- Rail 56px, Chat flex (min 600px ideal), Pinboard 420px fixed
- 窄屏 <1100px 时 pinboard 折叠为 slide-over drawer
- Topbar 48px 高度

**MUST 添加 `data-testid`：** `rail`, `chat-column`, `pinboard`, `topbar` on their root elements.

**暂停点:** Step 2 完成后向用户展示 layout。用户确认后继续。

**verify:**
```bash
npx tsc --noEmit
npx vite build
```

**Visual verify（暂停点 — MANDATORY）：**
```bash
# 启动 dev server
npm run dev &
sleep 3

# Playwright 布局尺寸验证
node scripts/verify-layout.mjs
# 期望输出: Rail=56px PASS, Pinboard=420px PASS, Topbar=48px PASS

# 全屏截图
npx playwright screenshot --browser=chromium --viewport-size="1440,900" http://localhost:5173 screenshot-step2.png

# 停掉 dev server
kill %1
```
将 `screenshot-step2.png` 路径和 `verify-layout.mjs` 输出粘贴到报告中。

---

### Step 3 — Shared Atoms [I-V]

**Spec sections:** §3 (tokens for badge colors), §4 (types for badge values)
**Reference files to read:** `shared-intel.jsx` (搜索 `ConfidenceBadge`, `SourceBadge`, `Icon`)

**做什么：**
1. `shared/Icon.tsx` — 从 `shared-intel.jsx` 的 `Icon` 组件提取所有 SVG icons，重写为 TypeScript
2. `shared/ConfidenceBadge.tsx` — pill with colored dot + label, 颜色映射: `high_confidence` → green, `medium_confidence` → amber, `low_confidence` → orange, `insufficient` → gray (spec §3 tokens)
3. `shared/SourceBadge.tsx` — `GRAPH` / `RAG` / `LLM` 徽章，颜色见 spec §3 `src_graph/src_rag/src_llm`
4. `shared/StatusPill.tsx` — Cypher template result status: `success` green, `empty` gray, `error` red, `no_match` amber

**verify:**
```bash
npx tsc --noEmit
npx vite build
# 在 App.tsx 临时渲染 4 种 ConfidenceBadge + 3 种 SourceBadge + 4 种 StatusPill 确认颜色正确
```

---

### Step 4 — Chat Column (Structure) [I-V]

**Spec sections:** §7.1–7.4, §7.6–7.7
**Reference files to read:** `v1-classic.jsx` (完整文件)

**做什么：**
1. `chat/ChatColumn.tsx` — 垂直 scrollable area 容器
2. `chat/PreviousTurn.tsx` — spec §7.1: collapsed row: time + domain + result badge + actor + confidence + chevron
3. `chat/UserMsg.tsx` — spec §7.2: right-aligned dark bubble, max-width 460px, radius 16 (BR corner 6)
4. `chat/AgentIntro.tsx` — spec §7.3: routing summary paragraph
5. `chat/NodeQueue.tsx` — spec §7.4: **核心复杂组件**
   - 6 rows, 每行: chevron + status indicator (4 states) + index + label + sub-summary + duration
   - **Expansion content per node**: spec §7.4 table 定义了每个 node 展开后显示什么
   - status indicator: done(green check pill) / running(spinning ring) / error(red X pill) / queued(dashed gray ring)
6. `chat/Composer.tsx` — spec §7.7: textarea + attach icon + model badge + send button + disclaimer

**NodeQueue 是这个 Step 最难的部分。** 每个 node 的展开内容不同（spec §7.4 table），不要用一个 generic 展开模板应付 6 种不同的内容。

**MUST 添加 `data-testid`：** `node-queue`, `node-row-supervisor`, `node-row-infrastructure`, ..., `node-row-report`, `composer`

**verify:**
```bash
npx tsc --noEmit
npx vite build
# dev server: Chat column 渲染 mock data: 1 PreviousTurn + 1 UserMsg + 1 AgentIntro + NodeQueue (6 nodes, mix of done/running/queued)
# 点击 node row → 展开对应内容
```

---

### Step 5 — Attribution Result Card (3 modes) [I-V]

**Spec sections:** §7.5 (三种 render mode 的完整定义), §7.6 (action chips wiring)
**Reference files to read:** `v1-classic.jsx` (搜索 `AttributionResultCard`)

**做什么：**
1. `chat/AttributionResult/Done.tsx` — spec §7.5A: headline + confidence badge + 4-cell stat grid + narrative + action chips
2. `chat/AttributionResult/Running.tsx` — spec §7.5B: shimmer bar + spinner + skeleton lines (95%/88%/60%) + "已完成 N/6 node" footer
3. `chat/AttributionResult/Error.tsx` — spec §7.5C: red left border + error message + 3 action buttons (重试/仅跑graph/查看日志)

**Action chips wiring (spec §7.6):**
- 查看证据链 → pinboard 切换到 Pinned + scroll Evidence card / 或直接 open Evidence fullscreen
- 展开候选演员 → open Candidates fullscreen
- 复制 Markdown → clipboard
- 导出 JSON → blob download

**MUST 添加 `data-testid`：** `attribution-result-done`, `attribution-result-running`, `attribution-result-error`

**暂停点:** Step 5 完成后向用户展示完整 Chat column (含 3 种 card 状态)。

**verify:**
```bash
npx tsc --noEmit
npx vite build
```

**Visual verify（暂停点 — MANDATORY）：**
```bash
npm run dev &
sleep 3

# 截图：App 临时渲染 3 种 AttributionResult 状态（垂直堆叠或通过 state 切换）
npx playwright screenshot --browser=chromium --viewport-size="1440,900" http://localhost:5173 screenshot-step5.png

# Playwright token 验证: confidence badge 颜色
node scripts/verify-tokens.mjs
# 期望: High confidence bg PASS, Medium confidence bg PASS, etc.

kill %1
```
将截图和 token 验证输出粘贴到报告中。用户对照 v1b.html 确认视觉一致后继续。

---

### Step 6 — Pinboard [I-V]

**Spec sections:** §8 (全部)
**Reference files to read:** `v2-workspace.jsx` (完整文件)

**做什么：**
1. `pinboard/Pinboard.tsx` — spec §8.1: segmented control `[Pinned | Raw JSON]`
2. `pinboard/PinCard.tsx` — 共享卡片 chrome: icon tile + tag + title + ⤢ button
3. `pinboard/AttributionCard.tsx` — spec §8.2 Card 1: confidence bars + flag chips
4. `pinboard/CandidatesCard.tsx` — spec §8.2 Card 2: actor rows (expandable, with SourceBadge + confidence bar)
5. `pinboard/InfrastructureCard.tsx` — spec §8.2 Card 3: RDAP grid + passive DNS rows + certs + fingerprint badges
6. `pinboard/EvidenceChainCard.tsx` — spec §8.2 Card 4: numbered evidence chain + count chips
7. `pinboard/RawJsonPanel.tsx` — spec §8.3: `<pre>` + Copy button with "Copied" feedback

**每张卡的 tag 颜色已在 spec §8.2 定义——MUST 精确使用。**

**MUST 添加 `data-testid`：** `pinboard`, `pin-card-attribution`, `pin-card-candidates`, `pin-card-infrastructure`, `pin-card-evidence`, `raw-json-panel`, `segmented-control`

**verify:**
```bash
npx tsc --noEmit
npx vite build
# Pinboard 渲染: segmented control 切换正常, 4 张 Pinned cards 用 sampleState 填充
# Raw JSON 显示完整 JSON + Copy 按钮
# 每张 card 的 ⤢ 按钮存在（点击暂时无反应，Step 7 实现）
```

---

### Step 7 — Fullscreen Modals + NodeEdgeGraph [I-V]

**Spec sections:** §9 (modals), §10 (node-edge graph)
**Reference files to read:** `fullscreen.jsx` (完整文件)

**做什么：**
1. `fullscreen/FullscreenModal.tsx` — spec §9 chrome: backdrop blur + white card min(1100px,92%) + header + ESC close
2. `fullscreen/AttributionFs.tsx` — spec §9.1: verdict hero + confidence/temporal bars + flags + sources
3. `fullscreen/CandidatesFs.tsx` — spec §9.2: two-column (candidates list + NodeEdgeGraph)
4. `fullscreen/InfrastructureFs.tsx` — spec §9.3: KV grid + DNS Gantt timeline + certs + fingerprints
5. `fullscreen/EvidenceFs.tsx` — spec §9.4: numbered evidence cards + 2-column (graph paths + RAG chunks)
6. `fullscreen/NodeEdgeGraph.tsx` — spec §10: pure SVG, nodes by kind (domain/actor/cluster/ip/sibling/campaign), edges solid/dashed, colors per spec §10

**NodeEdgeGraph 关键：**
- 从 `graph_paths` results 提取 nodes 和 edges
- Stroke color by kind: `domain #0d0f12`, `cluster #a4a8c2`, `actor accent(#3b5bdb)`, `ip #10b981`, `sibling #9ca0b0`, `campaign #f59e0b`
- 不需要 force-directed layout——可以用预设位置（spec 说 "initial implementation can hard-code positions"）
- White fill, label inside circle (mono for IPs/domains, sans for names)

**Wire ⤢ buttons:** pinboard cards 的 expand 按钮现在触发对应 fullscreen modal。

**MUST 添加 `data-testid`：** `fullscreen-modal`, `node-edge-graph`, and each pin card's expand button.

**暂停点:** Step 7 完成后向用户展示完整 UI（三列 + modals）。

**verify:**
```bash
npx tsc --noEmit
npx vite build
```

**Visual verify（暂停点 — MANDATORY, 多截图）：**
```bash
npm run dev &
sleep 3

# 截图 1: 完整三列 layout（默认状态）
npx playwright screenshot --browser=chromium --viewport-size="1440,900" http://localhost:5173 screenshot-step7-main.png

# 截图 2-5: 用 Playwright 脚本自动打开每个 fullscreen modal 并截图
node scripts/verify-modals.mjs
# verify-modals.mjs 内容: 
#   点击每个 pin card 的 ⤢ 按钮 → 截图 → 按 Escape → 下一个
#   输出: screenshot-step7-attribution-fs.png, screenshot-step7-candidates-fs.png,
#         screenshot-step7-infrastructure-fs.png, screenshot-step7-evidence-fs.png
#   同时验证: modal backdrop blur 存在, ESC 关闭生效, NodeEdgeGraph SVG 渲染了 ≥3 个 circle 元素

kill %1
```

**verify-modals.mjs 的验证点（MUST 全部 PASS）：**
- Modal 打开时 backdrop 存在（`backdrop-filter` computed style 非 none）
- Modal 宽度 ≤ `min(1100px, 92vw)`
- ESC 按键后 modal 关闭（`.fullscreen-modal` 不再存在于 DOM）
- CandidatesFs modal 中 `[data-testid="node-edge-graph"]` 存在且包含 ≥3 个 `<circle>` SVG 元素
- 每个 modal 的 header 有 close button

将全部截图路径和验证输出粘贴到报告中。

---

### Step 8 — Streaming + State Management + Multi-turn + History [I-V]

**Spec sections:** §4 (NodeEvent), §11 (全部: history, multi-turn, loading, error, needs_more_evidence)
**Reference files to read:** `V1b-spec.md` §11 全文

**做什么：**
1. `lib/api.ts` — SSE client: `POST /query` → parse `NodeEvent` stream (spec §4 末尾)
   - Fallback: 如果 SSE 不可用，mock mode 模拟 2 秒延迟 + sequential node events
   - Mock mode 通过 `VITE_MOCK=true` 环境变量切换
2. `lib/history.ts` — spec §11.1: localStorage `cti.history.v1`, max 50 entries FIFO
3. App-level state management (React Context + useReducer):
   - `currentTurn: AttributionState | null`
   - `previousTurns: AttributionState[]`
   - `nodeStatuses: Record<string, NodeStatus>`
   - `activeModal: ModalType | null`
   - `pinnedView: 'pinned' | 'raw'`
4. Multi-turn (spec §11.2): in-memory turns array, chat renders current expanded + previous collapsed, pinboard follows focus
5. Loading state (spec §11.3): card → Running mode, node queue live updates
6. Error state (spec §11.4): card → Error mode, action buttons wired
7. `needs_more_evidence` banner (spec §11.5): small banner inside Attribution card

**verify:**
```bash
npx tsc --noEmit
npx vite build
```

**Final Visual Verify（MANDATORY — 最终验收）：**
```bash
VITE_MOCK=true npm run dev &
sleep 3

# 端到端场景截图
node scripts/verify-e2e.mjs
# verify-e2e.mjs 执行：
#   1. 在 Composer 输入 "谁控制 hamadryas.online？" → 点击发送
#   2. 等待 mock delay → 截图 Running 状态: screenshot-step8-running.png
#      验证: NodeQueue 有 ≥1 个 running node, AttributionResult 显示 skeleton
#   3. 等待 mock 完成 → 截图 Done 状态: screenshot-step8-done.png
#      验证: Done card 显示 actor name + confidence badge + narrative
#   4. 在 Composer 输入第二个 query → 等待完成
#      截图: screenshot-step8-multiturn.png
#      验证: 第一个 query 折叠成 PreviousTurn row, 第二个 query 展开
#   5. page.reload() → 截图: screenshot-step8-history.png
#      验证: 打开 history → 有 2 条记录
#   6. 全屏截图 1440x900: screenshot-step8-final.png

kill %1
```

将全部截图和验证输出粘贴到报告中。这是最终交付物。

---

## 4. Accessibility (spec §13)

在每个 Step 中同步实现，不作为独立 step：
- `Esc` closes fullscreen modal (Step 7)
- `Cmd/Ctrl + Enter` sends composer (Step 4)
- All buttons keyboard-focusable, visible focus ring 1.5px outline accent color
- Status colors paired with icons/text (never color-only) — 贯穿所有 Step
- IOC values copyable (single-click `<code>` or copy buttons) — Step 6/7
