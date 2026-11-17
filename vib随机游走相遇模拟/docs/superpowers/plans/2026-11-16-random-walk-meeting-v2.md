# 随机游走相遇模拟第2版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从第1版独立创建“实验仪器风”的单文件随机游走相遇模拟，并保留全部原有玩法。

**Architecture:** 新版仍是离线单 HTML，内联 JavaScript 按配置、模拟、Canvas 渲染和界面控制分区。模拟状态由单一状态对象维护，绘制只读取状态；响应式布局通过面板实测尺寸为 Canvas 计算未被遮挡的观测区域。

**Tech Stack:** HTML5、CSS、原生 JavaScript、Canvas 2D、Chrome Headless + DevTools Protocol 测试。

## Global Constraints

- 原文件 `随机游走相遇模拟第1版.html` 必须保持 SHA-256 `08D046639B5A01C0E6E4AC5B77C181F90B1CCD437C278EFA7DE94581FC87699A`。
- 不修改 `随机游走相遇模拟.html` 和 `随机游走相遇模拟-优化版.html`。
- 新应用必须是单文件、UTF-8、离线可运行且无外部字体、图片、CDN 或网络请求。
- 保留空格/按钮单步、自动/暂停、重置、轨迹保留、实时数据、相遇判定和自动缩放。
- 不增加交叉穿行判定、历史列表、速度调节、种子输入或统计图表。
- 当前目录不是 Git 仓库，因此跳过所有 `git commit` 步骤，以文件哈希与测试结果作为检查点。

---

### Task 1: 建立浏览器验收测试

**Files:**
- Create: `C:/Users/lenovo/.codex/visualizations/2026/11/16/01a1e35e-6577-7360-a4c7-740293c3b61a/random-walk-v2.test.mjs`
- Test target: `E:/CodingProject/vib/随机游走相遇模拟第2版.html`

**Interfaces:**
- Consumes: Chrome executable `C:/Program Files/Google/Chrome/Application/chrome.exe` and the target HTML path.
- Produces: Node test exit code 0 on success; screenshots `random-walk-v2-desktop.png` and `random-walk-v2-mobile.png` in the visualization directory.

- [ ] **Step 1: Write the failing browser test**

The test must:

1. Fail with `TARGET_MISSING` while the new HTML does not exist.
2. Launch headless Chrome through DevTools Protocol without adding npm dependencies.
3. Inject a deterministic `Math.random` sequence before navigation.
4. Verify UTF-8 declarations, expected Chinese text, no external `src`/`href` resources, and no network requests to HTTP(S).
5. Verify initial values, two deterministic steps producing a meeting at step 2, automatic play, pause, and reset.
6. Verify Canvas pixel data is non-uniform.
7. Verify desktop and 390x844 mobile layouts keep controls inside the panel and the toast above the mobile panel.
8. Save desktop and mobile screenshots.

Core deterministic sequence:

```js
const randomSequence = [
  0, 0.25, // 第一步：甲上，乙下
  0.25, 0  // 第二步：甲下，乙上，两人在原点相遇
];
```

Core simulation assertions:

```js
assert.equal(await text('#sSteps'), '0');
assert.equal(await text('#sDist'), '0.0');
assert.equal(await text('#sMeet'), '0');
await click('#stepBtn');
await click('#stepBtn');
assert.equal(await text('#sSteps'), '2');
assert.equal(await text('#sMeet'), '1');
assert.match(await text('#sLast'), /2/);
```

- [ ] **Step 2: Run the test to verify it fails for the expected reason**

Run:

```powershell
node "C:\Users\lenovo\.codex\visualizations\2026\11\16\01a1e35e-6577-7360-a4c7-740293c3b61a\random-walk-v2.test.mjs"
```

Expected: non-zero exit code with `TARGET_MISSING`.

- [ ] **Step 3: Record the failing result**

No commit is possible because the workspace is not a Git repository. Retain the terminal failure output in the task notes and proceed to Task 2.

### Task 2: 实现单文件模拟与实验仪器界面

**Files:**
- Create: `E:/CodingProject/vib/随机游走相遇模拟第2版.html`
- Test: `C:/Users/lenovo/.codex/visualizations/2026/11/16/01a1e35e-6577-7360-a4c7-740293c3b61a/random-walk-v2.test.mjs`

**Interfaces:**
- Consumes: browser DOM IDs `cv`, `stepBtn`, `autoBtn`, `resetBtn`, `sSteps`, `sDist`, `sMeet`, `sLast`, `toast`.
- Produces: a standalone page with the same IDs and behavior expected by Task 1.

- [ ] **Step 1: Add the UTF-8 HTML shell and responsive instrument layout**

The HTML must contain:

```html
<canvas id="cv" aria-label="随机游走轨迹"></canvas>
<main class="panel" id="panel">
  <header class="panel-head">
    <p class="eyebrow">RANDOM WALK / 02</p>
    <h1>两个随机游走的人</h1>
    <p class="intro">两人从同一点出发，每一步各自随机移动一格。</p>
  </header>
  <div class="controls">
    <button id="stepBtn" class="primary">走一步 <span class="kbd">空格</span></button>
    <button id="autoBtn" aria-pressed="false">自动</button>
    <button id="resetBtn">重置</button>
  </div>
  <dl class="stats">
    <div><dt>步数</dt><dd id="sSteps">0</dd></div>
    <div><dt>直线距离</dt><dd id="sDist">0.0</dd></div>
    <div><dt>相遇次数</dt><dd id="sMeet">0</dd></div>
    <div><dt>最近相遇</dt><dd id="sLast">--</dd></div>
  </dl>
  <div class="legend" aria-label="轨迹图例">...</div>
  <div class="toast" id="toast" role="status" aria-live="polite"></div>
</main>
```

- [ ] **Step 2: Add the state and deterministic simulation functions**

Use a state object with these exact properties:

```js
const state = {
  paths: { a: [{ x: 0, y: 0 }], b: [{ x: 0, y: 0 }] },
  steps: 0,
  meetings: 0,
  lastMeet: null,
  bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0 },
  pulse: 0,
  running: false,
  rafId: null
};
```

Implement `resetState()`, `takeStep()`, and `growBounds(point)`; takeStep mutates one new point per path and increments meetings only when the new points are equal.

- [ ] **Step 3: Add Canvas rendering**

Render a non-uniform dark instrument background, grid, origin, blue and orange paths, a blue circle for A, an orange diamond for B, and a pulse on meeting. Compute the visible drawing rectangle from `panel.getBoundingClientRect()` so desktop content centers to the right of the panel and mobile content centers above it.

- [ ] **Step 4: Add controls and robust animation lifecycle**

Implement one requestAnimationFrame loop, automatic stepping at 130 ms, pause state, reset behavior, roomy button focus styles, `aria-pressed`, reduced-motion handling, and a readable Canvas-context failure message.

- [ ] **Step 5: Run the acceptance test**

Run:

```powershell
node "C:\Users\lenovo\.codex\visualizations\2026\11\16\01a1e35e-6577-7360-a4c7-740293c3b61a\random-walk-v2.test.mjs"
```

Expected: `PASS` with all behavior, layout, Canvas, and dependency checks successful.

### Task 3: 验证视觉与不可变性

**Files:**
- Inspect: `随机游走相遇模拟第2版.html`
- Inspect: generated desktop/mobile screenshots
- Verify: three existing HTML files

**Interfaces:**

- Consumes: output from Task 2.
- Produces: final verification evidence for source encoding, interactivity, Canvas pixels, responsive composition, and original-file hashes.

- [ ] **Step 1: Inspect desktop and mobile screenshots**

Open both generated PNG files and check for text overflow, panel/canvas obstruction, and contrast problems.

- [ ] **Step 2: Re-run browser acceptance tests**

Run:

```powershell
node "C:\Users\lenovo\.codex\visualizations\2026\11\16\01a1e35e-6577-7360-a4c7-740293c3b61a\random-walk-v2.test.mjs"
```

Expected: exit code 0 and `PASS`.

- [ ] **Step 3: Verify the original files are byte-identical**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\随机游走相遇模拟第1版.html','.\随机游走相遇模拟.html','.\随机游走相遇模拟-优化版.html'
```

Expected hashes:

```text
08D046639B5A01C0E6E4AC5B77C181F90B1CCD437C278EFA7DE94581FC87699A
6D9DBCC5962B5204460E410CA9A9EC538B9BCACD0B40572A331934E8B2A2B9E4
ABC352BAD9DA7FE607E623AACD39298BD625ED6873E011E8A5BF6AF1872BD38C
```

- [ ] **Step 4: Confirm offline operation**

Open the new HTML directly with `file://`; expected result is a rendered simulation with no failed network request or external asset dependency.
