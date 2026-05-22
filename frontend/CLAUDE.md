# CLAUDE.md — CTI-Agent Frontend V1.b

> 任务规格见 `PROJECT_SPEC.md`。
> 设计 spec 见 `design-reference/V1b-spec.md`——这是 single source of truth，任何组件的行为/样式/交互以该文件为准。
> 开始任何工作前，MUST 先读 PROJECT_SPEC.md 全文，再读 V1b-spec.md 全文。

---

## 0. Core Principles

1. **Pixel-perfect 还原设计稿，不是"差不多"。** V1b-spec.md 定义了每个组件的尺寸、颜色、间距、状态。`v1b.html` 是视觉参考。偏差必须有注释说明原因。
2. **Scope = V1.b ONLY。** 见 spec §14 的排除清单。见 README 的 "What to ignore" 列表。如果你不确定某个功能是否在 scope 内，去读 spec。
3. **Reference files 是原型，不是 production code。** 从 `.jsx` 文件提取逻辑/结构/tokens，重写为 React 18 + TypeScript。不要 copy Babel-standalone JSX 语法。
4. **文件结构严格遵循 spec §12。** 不允许自己发明目录结构。

---

## 1. Design Reference 文件角色

| File | 读取时机 | 提取什么 | 禁止 |
|------|---------|---------|------|
| `V1b-spec.md` | 每个 Step 开始前 | 该 Step 对应的 §section | — |
| `v1b.html` | 需要视觉对照时 | 像素级参考 | 不要 copy HTML |
| `shared-intel.jsx` | Step 2 (types/tokens) | INTEL sample data, tokens, Icon SVGs, ConfidenceBadge, SourceBadge | 不要 copy Babel JSX |
| `v1-classic.jsx` | Step 4-5 (rail, chat) | Rail, topbar, node queue, attribution-result card (3 states), composer | 转为 TSX |
| `v2-workspace.jsx` | Step 6 (pinboard) | PinboardColumn, 4 pinned cards, segmented control | 不要 copy V2 case sidebar |
| `fullscreen.jsx` | Step 7 (modals) | Fullscreen modals (4种) + NodeEdgeGraph SVG | 不要 copy design-canvas pan/zoom |
| `design-canvas.jsx` | **永远不读** | — | 这是原型工具 |

**读取规则：** 每个 Step 开始时，MUST 用 `cat` 重新读取 V1b-spec.md 的对应 section 和该 Step 指定的 reference file。不要从 context 回忆。

**路径注意：** Step 1 会创建 `cti-frontend/` 子目录，之后大部分编码工作在该子目录内。读取 design reference 时用相对路径 `../design-reference/V1b-spec.md`（从 `cti-frontend/` 内部）或 `design-reference/V1b-spec.md`（从 harness 根目录）。

---

## 2. Workflow

每个 Step 必须经过 **Implement → Verify**：

```
1. cat PROJECT_SPEC.md 中该 Step 的内容
2. cat V1b-spec.md 中该 Step 指定的 section
3. cat 该 Step 指定的 reference .jsx 文件
4. 实现代码
5. 运行 verify 命令，粘贴完整输出
6. 如果 verify 失败，修复后重跑。连续 3 次 FAIL → 停下来报告
7. 按 Section 5 报告格式输出
8. 暂停点：等用户确认后继续
```

**单步执行：** 完成一个 Step 的全部 verify 后，才能开始下一个。禁止合并。

---

## 3. Hard Bans

### 设计偏离
- 禁止添加 V1b-spec.md §14 排除的功能
- 禁止使用 spec §3 以外的颜色值（除非是 pure CSS 需要的 black/white/transparent）
- 禁止改变 §2 定义的 layout 比例（Rail 56px, Pinboard 420px, Chat flex）
- 禁止给组件加 animation/transition 除非 spec 明确定义了（shimmer, spinner, expansion）

### 代码质量
- 禁止 `any` 类型（除非第三方库强制）
- 禁止把多个 spec-defined 组件塞进一个文件
- 禁止 inline style 对象超过 3 个属性
- 禁止在组件内 hardcode mock data——所有 mock data 在 `fixtures/` 中定义
- 禁止 barrel exports（`index.ts` re-exporting）

### 执行纪律
- 禁止跳过 `npx tsc --noEmit` verify
- 禁止说"应该通过"而不实际运行
- 禁止在 verify 失败后标记 step 完成
- 禁止改动 PROJECT_SPEC.md 文件列表之外的文件（package.json 和 vite.config.ts 除外）

---

## 4. Execution Constraints

### TypeScript
- `tsconfig.json`: `strict: true`, `noUnusedLocals: true`, `noUnusedParameters: true`
- 每个 component 的 Props interface 显式定义并 export
- `AttributionState` 从 `types/AttributionState.ts` import，不在组件中重定义

### Styling
- CSS Modules（`.module.css`）或内联 CSS-in-JS，spec §1 说 "no Tailwind needed"
- Design tokens 从 `lib/tokens.ts` 引用，值 MUST 与 spec §3 完全一致
- 每个颜色值在 tokens.ts 中只出现一次，组件通过 token name 引用

### 测试基础
- 每个 Step verify 至少：`npx tsc --noEmit` + `npx vite build`
- 有交互逻辑的组件（modal open/close, segmented control, expansion）MUST 有测试

### 视觉验收（MANDATORY at every pause point）

编译通过 ≠ 渲染正确。前端项目的 verify 如果只有 tsc + vite build，等于没 verify。

**工具链：** Step 1 结束时 MUST 安装 Playwright：
```bash
npm install -D @playwright/test
npx playwright install chromium
```

**视觉 verify 流程（每个暂停点 + Step 8 最终验收）：**
```
1. 确保 dev server 在后台运行 (npm run dev &)
2. 用 Playwright 截图：
   npx playwright screenshot --browser=chromium http://localhost:5173 screenshot-stepN.png
3. 粘贴截图文件路径到报告中（用户会打开看）
4. 对截图做自检——对照 v1b.html 的等价区域，检查：
   a. 布局比例是否正确（Rail 56px, Pinboard 420px, Chat flex）
   b. 颜色是否与 tokens 一致（至少肉眼级别）
   c. 字体是否正确（Geist sans / Geist Mono for IOCs）
   d. 间距/圆角是否接近 spec（不要求像素精确，但不能明显偏离）
   e. 组件是否渲染了 mock data（不能是空白/placeholder）
5. 在报告中写出自检结果（看到了什么/哪里可能有偏差）
```

**关键 Playwright 验证命令（暂停点用）：**

布局尺寸验证：
```js
// verify-layout.mjs — Step 2 暂停点用
import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:5173');
await page.waitForTimeout(2000);

// Rail width
const rail = await page.locator('[data-testid="rail"]').boundingBox();
console.log(`Rail width: ${rail?.width}px (expected: 56px) ${Math.abs((rail?.width||0) - 56) < 2 ? 'PASS' : 'FAIL'}`);

// Pinboard width
const pinboard = await page.locator('[data-testid="pinboard"]').boundingBox();
console.log(`Pinboard width: ${pinboard?.width}px (expected: 420px) ${Math.abs((pinboard?.width||0) - 420) < 2 ? 'PASS' : 'FAIL'}`);

// Topbar height
const topbar = await page.locator('[data-testid="topbar"]').boundingBox();
console.log(`Topbar height: ${topbar?.height}px (expected: 48px) ${Math.abs((topbar?.height||0) - 48) < 2 ? 'PASS' : 'FAIL'}`);

await page.screenshot({ path: 'screenshot-layout.png', fullPage: true });
await browser.close();
```

颜色 token 验证：
```js
// verify-tokens.mjs — Step 3 之后用
// 检查 ConfidenceBadge 的 background-color 是否匹配 spec §3 tokens
const badge = await page.locator('[data-testid="confidence-badge-high"]');
const bg = await badge.evaluate(el => getComputedStyle(el).backgroundColor);
console.log(`High confidence bg: ${bg} (expected: rgb(220,245,230) / #dcf5e6) ${bg === 'rgb(220, 245, 230)' ? 'PASS' : 'FAIL'}`);
```

**data-testid 命名规则：** 每个需要视觉验证的容器 MUST 添加 `data-testid` 属性：
- `rail`, `chat-column`, `pinboard`, `topbar`
- `node-queue`, `node-row-{id}`, `node-row-{id}-expanded`
- `attribution-result-done`, `attribution-result-running`, `attribution-result-error`
- `pin-card-attribution`, `pin-card-candidates`, `pin-card-infrastructure`, `pin-card-evidence`
- `confidence-badge-{level}`, `source-badge-{type}`, `status-pill-{status}`
- `fullscreen-modal`, `node-edge-graph`

---

## 5. Reporting Format

```
## 进度：Step N — {name}

### 改动
- 新增: {文件路径列表}
- 修改: {文件路径列表}

### Spec 对照（逐条）
- §{N} {组件名}: {spec 要求} → {实际实现} ✅/⚠️

### Compile Verify
- `npx tsc --noEmit`: {输出}
- `npx vite build`: {输出}

### Visual Verify（暂停点 only）
- 截图: {screenshot-stepN.png 路径}
- 布局自检: Rail={实际}px Pinboard={实际}px Topbar={实际}px {PASS/FAIL}
- Playwright 尺寸验证: {verify-layout.mjs 输出，粘贴}
- 自检发现: {与 v1b.html 的差异描述，"无明显偏差" 或具体问题}

### 问题
- {偏离 spec 的地方及原因}

等你确认后继续下一个 Step。
```
