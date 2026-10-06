"use strict";
/* RTRC exam board. Part 1 reads archived benchmark cells; Part 2 drives the blank-task agent flow. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const trunc = (v, n) => { const s = String(v ?? ""); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };
const pct = (a, b) => (b ? `${((a / b) * 100).toFixed(1)}%` : "—");
// A task type with no cells in the saved batches yet (ALN before the re-run) reads as 0/0.
const BT = (table, t) => (table && table[t]) || { pass: 0, n: 0, agree: 0 };
const num = (n) => (n == null || n === "" ? "—" : Number(n).toLocaleString("en-US"));
const g = (n) => (n == null || n === "" ? "—" : String(Number(n)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const numbersIn = (text) => [...new Set((String(text || "").match(/\d+(?:\.\d+)?/g) || []).map((x) => String(parseFloat(x))))];

async function api(url, body) {
  const res = await fetch(url, body === undefined ? undefined : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

const S = { facts: null, tasks: [], cells: [], cell: null, cellLive: false, record: null, memory: [], catalog: null, budgets: null,
  choice: null, edited: false, mod: null, modTask: "MOD-05", mods: {}, mxMode: "tool", runStage: "", cellStage: "", modStage: "", appJob: null };
const FLOW = {};
const TYPE_NAME = { GEN: "Generate a new model", MOD: "Modify an existing model", ALN: "Align two models (paper 1)", QRY: "Query a model", AMB: "Ambiguous: ask, don't guess", RT: "Round trip: model back to text" };
const TYPE_SHORT = { GEN: "generate", MOD: "modify", ALN: "align", QRY: "query", AMB: "ambiguous", RT: "round trip" };
const TYPE_ORDER = ["GEN", "MOD", "ALN", "QRY", "AMB", "RT"];
const TYPE_GUIDE = {
  GEN: { gets: "Requirements only, no model", gives: "A new SysML v2 model", judge: "Official Pilot syntax passes, and every required part, connection and number is present", pilot: true },
  MOD: { gets: "An existing model plus one change", gives: "The edited model", judge: "Official Pilot syntax passes, the checklist is met, and values that must stay are unchanged. MOD-05 also has a power budget (design verdict)", pilot: true },
  ALN: { gets: "A specification package and a supplier package, both read-only", gives: "One alignment package of alias and allocation declarations, plus a JSON report", judge: "Official Pilot resolves every name; every required pair is declared, no look-alike pair is, nothing but imports, aliases and allocations is declared, and unmatched elements are reported", pilot: true },
  QRY: { gets: "A model plus one question", gives: "A JSON answer", judge: "Every field equals the answer key: the numbers, and names written in full with ::", pilot: false },
  AMB: { gets: "Requirements missing a number a check needs", gives: "Text that should ask for it", judge: "Asks a question (with ?), asks about the missing quantity, and invents no number", pilot: false },
  RT: { gets: "A model", gives: "The requirements restated in sentences", judge: "Every phrase and number the answer key lists is written back", pilot: false },
};
const CONFIG_NAME = { P0: "P0 one-shot", P1: "P1 repair from errors", P2: "P2 outline first", P3: "P3 outline + retrieved notes" };
const CONFIG_NOTE = {
  P0: "One call, then submit.",
  P1: "If the official syntax check fails, the error text goes back to the model; up to 3 repairs.",
  P2: "Write an outline first (no SysML), then write from the outline.",
  P3: "Retrieve 3 notes by the task's words, add them to the outline prompt, then write from the outline.",
};
const PTAG = { p1: "Paper 1", p2: "Paper 2", p3: "Paper 3", ours: "Official tool" };
const ptag = (p) => (p ? `<i class="ptag ${p}">${PTAG[p]}</i>` : "");
const GLYPH = { pass: "✓", fail: "✕", skip: "–", run: "●", await: "…" };
const WORD = { pass: "passed", fail: "failed", skip: "skipped this time", run: "running", await: "waiting for a person", "": "not reached" };
const badge = (status) => {
  const s = String(status ?? "—");
  const cls = /FAIL|fail|false|disagree|not pass|ERROR/i.test(s) ? "fail" : /PASS|pass|agree|in brief/i.test(s) ? "pass" : "warn";
  return `<span class="badge ${cls}">${esc(s)}</span>`;
};

/* Run records saved before the page went English keep Chinese template phrases; they are evidence, so they are translated for display only. */
const TX = [
  [/已有海事模型 MaritimeISR/g, "Existing maritime model MaritimeISR"],
  [/已批准设计 /g, "Approved design "],
  [/已批准 /g, "approved "],
  [/已有模型里找到可复用的数值，走复用路径。/g, "Reusable values found in existing models: reuse path."],
  [/已有模型里没有相关数值，走新建路径。/g, "No related values in existing models: new-design path."],
  [/检索没有完成。/g, "Retrieval did not finish."],
  [/功率合计对上限/g, "Total power vs limit"],
  [/上传对上行/g, "Upload vs uplink"],
  [/记录容量/g, "Recording storage"],
  [/带数字的需求写进了模型/g, "Numbered requirements in the model"],
  [/连接条数/g, "Connections"],
  [/所有 drawW 相加 ≤ powerLimitW/g, "sum of all drawW ≤ powerLimitW"],
  [/每条需求的属性名和数值都能在解析结果里找到/g, "each requirement's attribute name and value appear in the official parse"],
  [/uploadMbps（没有就用 dataRateMbps）≤ uplinkMbps/g, "uploadMbps (or dataRateMbps) ≤ uplinkMbps"],
  [/模型里没有同时写出 powerLimitW 和 drawW。/g, "The model does not state both powerLimitW and drawW."],
  [/模型里没有同时写出 uplinkMbps 和上传速率。/g, "The model does not state both uplinkMbps and an upload rate."],
  [/需要 dataRateMbps、retentionHours、storageGB 三个数。/g, "Needs dataRateMbps, retentionHours and storageGB."],
  [/语法没过，没有核算。/g, "The parse failed, so nothing was computed."],
  [/^官方语法$/g, "Official syntax"],
  [/^规范$/g, "Rules"],
  [/模板 · 属性合同/g, "Template · attribute contract"],
  [/示例 · 检索到的已有元素/g, "Examples · retrieved existing elements"],
  [/简报 \+ 需求/g, "Brief + requirements"],
  [/这一套的变体要求/g, "What this variant must do"],
  [/\(没有检索结果\)/g, "(no retrieval results)"],
  [/模型输出里没有 SysML 包。/g, "The model output contains no SysML package."],
  [/需求里出现了简报没有的数字。不能入库，等人补数。/g, "The requirements contain numbers that are not in the brief. Nothing can go into memory until a person supplies them."],
  [/设计 (.+?) 四项核算全过，可以由人批准入库。脚本不替人选。/g, (m, k) => { const keys = k.split("、"); return `${keys.length > 1 ? "Designs" : "Design"} ${keys.join(", ")} ${keys.length > 1 ? "pass" : "passes"} all four checks and may be approved into memory by a person. The script does not choose.`; }],
  [/两套设计都有核算失败项，不能入库。可以选一个权衡方案，回到设计空间再交给 agent。/g, "Both designs fail a check, so neither can go into memory. Pick a trade-off, go back to the design space, and give it to the agent again."],
  [/映射只是提议。代码核对两边名字，官方 Pilot 再解析对齐包。两份源模型都不改。采用与否由人定。/g, "Mappings are proposals. Code checks both names exist, then the official Pilot parses the alignment package. Neither source model is edited. A person decides whether to adopt them."],
  [/检索里没有 MaritimeISR 的元素，跳过对齐。/g, "Retrieval found no MaritimeISR elements; alignment skipped."],
  [/设计 A 语法没过或没有检索结果，跳过对齐。/g, "Design A failed the parse or retrieval found nothing; alignment skipped."],
  [/^(MOD-0\d) 变更：模型改已有模型，官方工具评，再读回文字$/g, "$1 change: the model edits an existing model, the official tool judges it, then it is read back as text"],
  [/标准答案在阅卷时才打开，没有放进两次模型调用。/g, "The answer key is opened only for scoring; neither model call saw it."],
  [/这一例的模型用官方 SysML v2 文本交给 Pilot。它没有再测船、无人机、指挥船之间的链路。/g, "This model goes to the Pilot as official SysML v2 text. It does not test the links between vessel, UAV and command ship."],
  [/同一道题在主力矩阵里的 12 次存档（按现行判分），用来看判定稳不稳。这一次新写的卷单独计。/g, "The same task's 12 archived main-matrix cells (current scorer), to see whether the verdict is stable. This new run counts separately."],
  [/这两条危险需求没有交给模型改写。语法能解析它们，不算安全通过。/g, "These two hazard requirements were not given to the model to rewrite. That they parse is not a safety pass."],
];
const HAN = /[\u4e00-\u9fff]/;
const tx = (s) => (HAN.test(s) ? TX.reduce((out, [re, to]) => out.replace(re, to), s) : s);
function txDeep(v) {
  if (typeof v === "string") return tx(v);
  if (Array.isArray(v)) return v.map(txDeep);
  if (!v || typeof v !== "object") return v;
  const out = Object.fromEntries(Object.entries(v).map(([k, x]) => [k, txDeep(x)]));
  if (out.unit === "条") out.unit = out.id === "CONNECT" ? "links" : "reqs";
  return out;
}

/* ======================= flow diagram ======================= */
const MARK = { main: "#6cc7c9", feed: "#d4b46a", loop: "#e3ac46", side: "#a996e0", mem: "#79d49a" };

function makeFlow(host, spec, hooks) {
  const byId = Object.fromEntries(spec.nodes.map((n) => [n.id, n]));
  const rowOf = Object.fromEntries(spec.rows.map((r, i) => [r.id, i + 1]));
  const mains = spec.nodes.filter((n) => n.row === "main").sort((a, b) => a.col - b.col);
  const edges = spec.edges.map((e) => ({ kind: "main", route: "h", ...e }));
  let state = {};
  let selected = "";
  let paper = "";
  let replayToken = null;

  const tagsOf = (n) => (n.papers || []).map(ptag).join("") + (n.cond ? `<i class="ctag">${esc(n.cond)}</i>` : "");
  const card = (n, style) => `<button type="button" class="fn k-${n.kind || "step"}" data-node="${n.id}"${style ? ` style="${style}"` : ""}>`
    + `<span class="fn-owner">${esc(n.owner)}</span><span class="fn-state" aria-hidden="true"></span>`
    + `<span class="fn-title">${esc(n.title)}</span><span class="fn-sub">${esc(n.sub)}</span><span class="fn-tags">${tagsOf(n)}</span></button>`;
  const linkMain = (id) => {
    const queue = [id];
    const seen = new Set([id]);
    while (queue.length) {
      const cur = queue.shift();
      for (const e of edges) {
        const other = e.from === cur ? e.to : e.to === cur ? e.from : null;
        if (!other || seen.has(other)) continue;
        if (byId[other].row === "main") return other;
        seen.add(other);
        queue.push(other);
      }
    }
    return mains[0].id;
  };
  const attach = {};
  spec.nodes.filter((n) => n.row !== "main").forEach((n) => { (attach[linkMain(n.id)] ||= []).push(n.id); });
  const edgeBetween = (a, b) => edges.find((e) => (e.from === a && e.to === b) || (e.from === b && e.to === a));
  const legend = [["main", "Main flow"], ["feed", "Reads material"], ["loop", "Repair / conditional loop"], ["side", "Side path"], ...(spec.home ? [["mem", "Memory loop"]] : [])]
    .map(([k, t]) => `<span><svg viewBox="0 0 26 8" aria-hidden="true"><path d="M1 4H25" class="wire ${k}"/></svg>${t}</span>`).join("");
  const filters = [["", "All"], ["p2", "Paper 2 · retrieval"], ["p3", "Paper 3 · generation"], ["p1", "Paper 1 · alignment"], ["ours", "Official tool"]];

  host.innerHTML = `<div class="flow c${spec.cols}">
      <div class="flow-bar"><div class="flow-legend">${legend}</div>
        <div class="paper-filter" role="group" aria-label="Highlight by paper">${filters.map(([p, t]) => `<button type="button" data-paper="${p}" class="${p ? "" : "on"}">${p ? `<span class="pdot ${p}"></span>` : ""}${t}</button>`).join("")}</div></div>
      <div class="paper-caption" hidden></div>
      <div class="flow-canvas"><div class="flow-grid${spec.home ? " has-home" : ""}" style="--cols:${spec.cols}">
        ${spec.rows.map((r, i) => `<div class="flow-band" style="grid-row:${i + 1}"></div><div class="flow-band-label" style="grid-row:${i + 1}">${esc(r.label)}<small>${esc(r.hint)}</small></div>`).join("")}
        ${spec.nodes.map((n) => card(n, `grid-row:${rowOf[n.row]};grid-column:${n.col + 1}`)).join("")}
        <svg class="flow-wires" aria-hidden="true"></svg><div class="flow-labels"></div>
      </div></div>
      <ol class="flow-list">${mains.map((m) => `<li>${card(m)}${attach[m.id] ? `<div class="att">${attach[m.id].map((id) => {
        const e = edgeBetween(id, m.id) || {};
        return `<button type="button" data-node="${id}">${esc(byId[id].title)}${e.label ? ` · ${esc(e.label)}` : ""}</button>`;
      }).join("")}</div>` : ""}</li>`).join("")}</ol>
    </div>
    <div class="node-detail" hidden></div>
    <div class="flow-ctrl"></div>`;

  const flowEl = $(".flow", host);
  const grid = $(".flow-grid", host);
  const svg = $(".flow-wires", host);
  const labelLayer = $(".flow-labels", host);
  const canvas = $(".flow-canvas", host);
  const detail = $(".node-detail", host);
  const caption = $(".paper-caption", host);
  const ctrl = $(".flow-ctrl", host);
  const defs = `<defs>${Object.entries(MARK).map(([k, c]) => `<marker id="${spec.id}-m-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto"><path d="M0 0L10 5 0 10z" fill="${c}"/></marker>`).join("")}</defs>`;

  function geom(el, box) {
    const r = el.getBoundingClientRect();
    const x = r.left - box.left;
    const y = r.top - box.top;
    return { x, y, w: r.width, h: r.height, r: x + r.width, b: y + r.height, cx: x + r.width / 2, cy: y + r.height / 2 };
  }
  function rounded(pts, rad = 9) {
    const clean = pts.filter((p, i) => i === 0 || Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) > 0.5);
    let d = `M${clean[0][0].toFixed(1)} ${clean[0][1].toFixed(1)}`;
    for (let i = 1; i < clean.length - 1; i++) {
      const [x0, y0] = clean[i - 1];
      const [x1, y1] = clean[i];
      const [x2, y2] = clean[i + 1];
      const d1 = Math.hypot(x1 - x0, y1 - y0);
      const d2 = Math.hypot(x2 - x1, y2 - y1);
      const r = Math.min(rad, d1 / 2, d2 / 2);
      const ax = x1 + ((x0 - x1) * r) / d1;
      const ay = y1 + ((y0 - y1) * r) / d1;
      const bx = x1 + ((x2 - x1) * r) / d2;
      const by = y1 + ((y2 - y1) * r) / d2;
      d += ` L${ax.toFixed(1)} ${ay.toFixed(1)} Q${x1.toFixed(1)} ${y1.toFixed(1)} ${bx.toFixed(1)} ${by.toFixed(1)}`;
    }
    const last = clean[clean.length - 1];
    return `${d} L${last[0].toFixed(1)} ${last[1].toFixed(1)}`;
  }
  function route(e, A, B, G) {
    const gap = 3;
    if (e.route === "v") {
      const down = B.y >= A.b - 1;
      const y1 = down ? A.b : A.y;
      const y2 = down ? B.y - gap : B.b + gap;
      if (Math.abs(A.cx - B.cx) < 4) return { pts: [[A.cx, y1], [A.cx, y2]], lab: [A.cx, (y1 + y2) / 2, e.side === "left" ? "left" : "right"] };
      const my = (y1 + y2) / 2;
      return { pts: [[A.cx, y1], [A.cx, my], [B.cx, my], [B.cx, y2]], lab: [(A.cx + B.cx) / 2, my, "mid"] };
    }
    if (e.route === "upleft") {
      const sx = A.x + A.w * 0.3;
      const tx = B.x + B.w * 0.72;
      const gy = (A.y + B.b) / 2;
      return { pts: [[sx, A.y], [sx, gy], [tx, gy], [tx, B.b + gap]], lab: [(sx + tx) / 2, gy, "mid"] };
    }
    if (e.route === "ru") return { pts: [[A.r, A.cy], [B.cx, A.cy], [B.cx, B.b + gap]], lab: [(A.r + B.cx) / 2, A.cy, "mid"] };
    if (e.route === "rd") return { pts: [[A.r, A.cy], [B.cx, A.cy], [B.cx, B.y - gap]], lab: [(A.r + B.cx) / 2, A.cy, "mid"] };
    if (e.route === "home") {
      const xr = A.r + 13;
      const yb = G.h - 9;
      const xl = 7;
      const ty = B.y + B.h * 0.72;
      return { pts: [[A.r, A.cy], [xr, A.cy], [xr, yb], [xl, yb], [xl, ty], [B.x - gap, ty]], lab: [(xr + xl) / 2, yb, "mid"] };
    }
    if (Math.abs(A.cy - B.cy) < 4) return { pts: [[A.r, A.cy], [B.x - gap, A.cy]], lab: [(A.r + B.x) / 2, A.cy - 12, "mid"] };
    const mx = (A.r + B.x) / 2;
    return { pts: [[A.r, A.cy], [mx, A.cy], [mx, B.cy], [B.x - gap, B.cy]], lab: [mx, (A.cy + B.cy) / 2, "mid"] };
  }
  function redraw() {
    if (!canvas.offsetParent) return;
    const box = grid.getBoundingClientRect();
    const W = grid.offsetWidth;
    const H = grid.offsetHeight;
    svg.setAttribute("width", W);
    svg.setAttribute("height", H);
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const paths = [];
    const labels = [];
    for (const e of edges) {
      const a = grid.querySelector(`.fn[data-node="${e.from}"]`);
      const b = grid.querySelector(`.fn[data-node="${e.to}"]`);
      if (!a || !b) continue;
      const r = route(e, geom(a, box), geom(b, box), { w: W, h: H });
      paths.push(`<path class="wire ${e.kind}" data-from="${e.from}" data-to="${e.to}" d="${rounded(r.pts)}" marker-end="url(#${spec.id}-m-${e.kind})"/>`);
      if (e.label) labels.push(`<span class="wlabel ${e.kind} ${r.lab[2] === "mid" ? "" : r.lab[2]}" data-from="${e.from}" data-to="${e.to}" style="left:${r.lab[0].toFixed(1)}px;top:${r.lab[1].toFixed(1)}px">${esc(e.label)}</span>`);
    }
    svg.innerHTML = defs + paths.join("");
    labelLayer.innerHTML = labels.join("");
    paint();
  }
  function paint() {
    for (const el of $$(".fn", host)) {
      const id = el.dataset.node;
      const s = state[id] || "";
      el.classList.remove("is-pass", "is-fail", "is-skip", "is-run", "is-await");
      if (s) el.classList.add(`is-${s}`);
      $(".fn-state", el).textContent = GLYPH[s] || "";
      el.classList.toggle("is-sel", id === selected);
      const hit = (byId[id].papers || []).includes(paper);
      const related = !hit && paper ? (byId[id].related || {})[paper] : "";
      el.classList.toggle("p-on", !!paper && hit);
      el.classList.toggle("p-rel", !!related);
      el.classList.toggle("p-off", !!paper && !hit && !related);
      if (hit) el.dataset.pbadge = `${PTAG[paper]} is used here`;
      else if (related) el.dataset.pbadge = related;
      else delete el.dataset.pbadge;
    }
    for (const el of $$(".flow-list .att button", host)) {
      const s = state[el.dataset.node] || "";
      el.classList.remove("is-pass", "is-fail", "is-skip", "is-run", "is-await");
      if (s) el.classList.add(`is-${s}`);
    }
    const lit = (id) => !!paper && ((byId[id].papers || []).includes(paper) || !!(byId[id].related || {})[paper]);
    for (const el of $$(".wire, .wlabel", host)) {
      const { from, to } = el.dataset;
      if (!from) continue;
      const edge = edges.find((e) => e.from === from && e.to === to);
      const skipped = edge && edge.kind !== "main" && (state[from] === "skip" || state[to] === "skip");
      const onPath = lit(from) || lit(to);
      el.classList.toggle("live", el.classList.contains("wire") && state[to] === "run" && state[from] !== "skip");
      el.classList.toggle("p-path", !!paper && onPath);
      el.classList.toggle("dim", (!!paper && !onPath) || (!paper && !!skipped));
    }
  }
  function renderDetail() {
    if (!selected) { detail.hidden = true; return; }
    const n = byId[selected];
    const s = state[selected] || "";
    detail.hidden = false;
    detail.innerHTML = `<div><h4>${esc(n.owner)}</h4><div class="nd-title">${esc(n.title)}</div><div class="nd-state">${GLYPH[s] || "○"} ${WORD[s]}</div><div class="nd-tags">${tagsOf(n)}</div></div>
      <div><h4>What it does</h4><p>${esc(n.does)}</p></div>
      <div><h4>Reads → produces</h4><p><b>Reads: </b>${esc(n.input)}\n<b>Produces: </b>${esc(n.output)}</p></div>
      <div><h4>${esc(hooks.nowTitle)}</h4><p>${hooks.now(selected) || "—"}</p>${hooks.jump ? `<button type="button" class="go-step" style="margin-top:8px">${esc(hooks.jumpLabel)}</button>` : ""}</div>`;
    const btn = $(".go-step", detail);
    if (btn) btn.onclick = () => hooks.jump(selected);
  }
  function setPaper(p) {
    paper = p || "";
    if (paper) flowEl.dataset.paper = paper; else delete flowEl.dataset.paper;
    for (const b of $$(".paper-filter button", host)) b.classList.toggle("on", b.dataset.paper === paper);
    caption.hidden = !paper;
    caption.innerHTML = paper ? spec.captions[paper] || "" : "";
    paint();
  }
  host.addEventListener("click", (ev) => {
    const f = ev.target.closest(".paper-filter button");
    if (f) { setPaperAll(f.dataset.paper); return; }
    const n = ev.target.closest("[data-node]");
    if (n && host.contains(n)) flow.select(n.dataset.node);
  });
  new ResizeObserver(() => requestAnimationFrame(redraw)).observe(grid);
  window.addEventListener("resize", () => requestAnimationFrame(redraw));
  if (document.fonts) document.fonts.ready.then(redraw);

  const flow = {
    spec, byId,
    setState(next) { state = { ...next }; paint(); if (selected) renderDetail(); },
    getState: () => state,
    select(id) { selected = id; paint(); renderDetail(); },
    setPaper,
    redraw,
    setCtrl(html) { ctrl.innerHTML = html; },
    async replay(order, final) {
      const token = {};
      replayToken = token;
      const shown = {};
      flow.setState(shown);
      for (const id of order) {
        if (replayToken !== token) return;
        if (!final[id]) continue;
        shown[id] = "run";
        flow.setState(shown);
        await sleep(360);
        if (replayToken !== token) return;
        shown[id] = final[id];
        flow.setState(shown);
      }
      flow.setState(final);
    },
    stopReplay() { replayToken = null; },
  };
  redraw();
  return flow;
}

/* ======================= flow specs ======================= */
const BENCH = {
  id: "bench", cols: 8, home: false,
  rows: [{ id: "src", label: "Sealed material", hint: "opened only at the marked step" }, { id: "main", label: "Main flow", hint: "every cell" }, { id: "side", label: "Side paths", hint: "repair · observing judges" }],
  nodes: [
    { id: "bank", row: "src", col: 1, kind: "source", owner: "Human-written · sealed", title: "Task bank, 24 tasks", sub: "task statements + baseline models",
      does: "24 tasks: GEN 5, MOD 5, QRY 5, AMB 4, RT 5. Task statements and answer keys are stored apart; the agent gets only the statement.", input: "—", output: "One task statement; GEN/MOD tasks may include a baseline model" },
    { id: "corpus", row: "src", col: 2, kind: "source", owner: "Text notes · read-only", title: "Notes corpus", sub: "bench/corpus: 2 files, 15 notes", papers: ["p2"], cond: "P3 only",
      does: "Two notes files (SysML syntax tips, maritime vocabulary) split into 15 notes. P3 scores each note by the task's words and takes the top 3. A text-only simplification of Paper 2: no graph, no vectors.", input: "Words in the task statement", output: "3 notes for the outline prompt" },
    { id: "gold", row: "src", col: 6, kind: "gold", owner: "Human-written · sealed", title: "Answer key", sub: "never shown to the agent",
      does: "assertions.yaml (names, connections, numbers, whether to ask) or answer.json. Opened only at the check step.", input: "—", output: "Checklist" },
    { id: "issue", row: "main", col: 1, owner: "Code", title: "Issue task", sub: "without the answer key",
      does: "Gives the task statement (and baseline model) to the agent. The gold folder never enters the prompt.", input: "One task from the bank", output: "Agent prompt" },
    { id: "outline", row: "main", col: 2, owner: "Model", title: "Outline", sub: "parts, ports, connections; no SysML yet", cond: "P2 / P3 only",
      does: "The model first lists the parts, ports, connections and attributes it needs as JSON, then writes from that outline. P3's outline prompt also has 3 retrieved notes.", input: "Task statement (P3: plus 3 notes)", output: "Outline JSON" },
    { id: "write", row: "main", col: 3, owner: "Model · agent under test", title: "Write the answer", sub: "flash · OpenCode · Claude", papers: ["p3"],
      does: "Answers by task type: GEN writes a new model, MOD edits the baseline, QRY answers from a model in JSON, AMB asks when information is missing, RT restates the model in words. The prompt carries SysML rules, Paper 3's \"rules\".", input: "Task statement + rules (+ outline)", output: "Answer: SysML, JSON or text" },
    { id: "syntax", row: "main", col: 4, owner: "Official tool", title: "Official syntax", sub: "SysML v2 Pilot 0.62", papers: ["ours"],
      does: "The official Pilot parses and links the answer. Only GEN and MOD answers come here. PASS means the syntax and references are valid, not that the design is right.", input: "SysML in the answer", output: "PASS / FAIL, error text, parsed model JSON" },
    { id: "watts", row: "main", col: 5, owner: "Code", title: "Read values", sub: "only officially parsed numbers",
      does: "Reads attributes and values (watts, rates) from the answer. The checklist uses only numbers from the official parse.", input: "Answer / official parse", output: "Names and values" },
    { id: "check", row: "main", col: 6, owner: "Code", title: "Check against key", sub: "names · connections · numbers · power", related: { p1: "Similar: values to keep (not Paper 1's method)" },
      does: "The answer key is opened only here and checked item by item: required elements, required connections, values that must stay, and, for tasks with a power check, whether the result is what the key expects. The task verdict passes only if all of these hold; whether the design meets its budget is reported separately as the design verdict. MOD-05's design is over budget by construction: an honest answer passes the task; raising the limit or changing numbers to fit fails it.", input: "Official parse + answer key", output: "Task verdict + design verdict" },
    { id: "gate", row: "main", col: 7, kind: "human", owner: "Person", title: "Approval gate", sub: "never approves a raised limit",
      does: "If an answer asks to relax a limit (for example raise 60 W), the run stops here for a person. No exam cell triggered it.", input: "A request to change a limit", output: "Approve / reject" },
    { id: "archive", row: "main", col: 8, owner: "Code", title: "Archive", sub: "analysis/*.jsonl",
      does: "Keeps the score row, the answer and every official parse folder, so each cell in 1.3 can be replayed.", input: "All records", output: "Score row + mvp/runs/<run id>" },
    { id: "repair", row: "side", col: 4, kind: "loop", owner: "Model", title: "Repair from errors", sub: "error text sent back, numbers kept", papers: ["p3"], cond: "P1 only · ≤3 times",
      does: "When the official syntax check fails, the task statement, the previous answer and the official error text (up to 8 lines) go back to the model with: Official validation failed. Fix the model. Do not change numbers the task said to keep. Up to 3 times. In Paper 3 a person corrects errors; here the official tool's errors do.", input: "Task statement + previous answer + error text", output: "A new answer, parsed again" },
    { id: "judge", row: "side", col: 8, kind: "judge", owner: "Observing · not scored", title: "Model judges", sub: "qwen3.8-max · Jev 1.13",
      does: "Two model judges each read the task statement, the grading criteria and the answer, say pass or fail, and are compared with the tool. They never change a score. They were told an over-budget design fails, so they are compared with the tool's design verdict; only MOD-05 has different design and task verdicts.", input: "Task statement + criteria + answer", output: "Judge verdict + whether it agrees with the tool" },
  ],
  edges: [
    { from: "issue", to: "outline" }, { from: "outline", to: "write" }, { from: "write", to: "syntax" }, { from: "syntax", to: "watts" },
    { from: "watts", to: "check" }, { from: "check", to: "gate" }, { from: "gate", to: "archive" },
    { from: "bank", to: "issue", kind: "feed", route: "v" },
    { from: "corpus", to: "outline", kind: "feed", route: "v", label: "P3: top 3 notes" },
    { from: "gold", to: "check", kind: "feed", route: "v", label: "opened only here" },
    { from: "syntax", to: "repair", kind: "loop", route: "v", label: "syntax FAIL" },
    { from: "repair", to: "write", kind: "loop", route: "upleft", label: "error text sent back" },
    { from: "archive", to: "judge", kind: "side", route: "v", label: "reads the archive", side: "left" },
  ],
  captions: {
    p2: "<b>Paper 2 (GRAG graph retrieval)</b> appears in the exam only in simplified form: P3 retrieves 3 text notes by the task's words and adds them to the outline prompt. No graph, no vectors. Full graph retrieval is used in Part 2, step ① Retrieve. <a href=\"#s03\">See the comparison in 0.3</a>",
    p3: "<b>Paper 3 (rules + template + examples, corrected from errors)</b>: the writing prompt carries SysML rules; P1 sends the official Pilot's error text back for a fix (in the paper a person corrects). GEN, MOD and QRY tasks match its create, modify and query uses. <a href=\"#s03\">See the comparison in 0.3</a>",
    p1: "<b>Paper 1 (cross-organization model alignment)</b> has no step of its own in the exam, so no step lights up here. The dashed \"Check against key\" box is only similar: MOD tasks' \"values to keep\" forbid changing existing elements. Paper 1's alignment is used in Part 2, step ④ Align; see the diagram in 2.1. <a href=\"#s21\">Go to 2.1</a>",
    ours: "<b>Official SysML v2 Pilot 0.62</b> judges syntax and links; every later number comes from its parse.",
  },
};

const APP = {
  id: "app", cols: 7, home: true,
  rows: [{ id: "src", label: "Memory", hint: "retrieval reads from here" }, { id: "main", label: "Six stages", hint: "every run" }, { id: "side", label: "Side paths", hint: "guard · repair · trade-offs" }],
  nodes: [
    { id: "mem", row: "src", col: 2, kind: "source", owner: "Memory", title: "Existing model + approved designs", sub: "MaritimeISR element cards", papers: ["p2"],
      does: "MaritimeISR.sysml is parsed by the official Pilot (428 elements); code turns 53 of them into cards (type, full name, value or connection ends), linked by 185 edges (ownership, connections). Designs a person approves are added the same way.", input: "Official parse", output: "Cards and edges" },
    { id: "brief", row: "main", col: 1, kind: "human", owner: "Person · 2.2", title: "Task brief", sub: "generated from choices, or your text",
      does: "The part and parameter choices in 2.2 generate an English brief; you can also edit the text. This is everything the agent receives.", input: "Choices in 2.2", output: "A brief" },
    { id: "retrieve", row: "main", col: 2, owner: "Code", title: "① Retrieve", sub: "words and numbers pick seeds + one hop", papers: ["p2"],
      does: "Scores every card by the brief's words and numbers: 1 point per brief word found in the card (common words like and, the removed), 1 point per number equal to a value in the card. The top 4 are seeds; their one-hop neighbours are added, up to 12 cards. No vectors, no model call.", input: "Brief + memory", output: "Matched cards, which become the \"examples\" part of the design prompt" },
    { id: "gen", row: "main", col: 3, owner: "Model", title: "② Generate", sub: "requirements → designs A / B", papers: ["p3"],
      does: "First splits the brief into numbered requirements (attribute name and value), then writes two designs: A allocates literally, B uses a different structure. Design prompt = rules + template (attribute contract) + examples (retrieved cards) + brief and requirements.", input: "Brief + retrieved cards", output: "Requirements JSON + two SysML files" },
    { id: "syntax", row: "main", col: 4, owner: "Official tool", title: "③ Official validation", sub: "Pilot parses both designs", papers: ["ours"],
      does: "The official Pilot parses each design. A FAIL goes to repair.", input: "Two SysML files", output: "PASS / FAIL, error text, parsed model" },
    { id: "align", row: "main", col: 5, owner: "Model proposes · code checks", title: "④ Align", sub: "mappings → alignment package through the Pilot", papers: ["p1"],
      does: "The model pairs design A's element names with retrieved MaritimeISR element names; code checks both names exist; code classifies each pair from the two parses and writes a separate alignment package of alias (definitions and features) and allocation (usages) statements, parsed by the official Pilot together with both source files; a person accepts or rejects each pair in 2.3. Neither source model is edited.", input: "Design A element names + MaritimeISR element names", output: "Mapping table + alignment package + Pilot result + per-pair review" },
    { id: "check", row: "main", col: 6, owner: "Code · model", title: "⑤ Budget checks · read-back", sub: "power · upload · storage · trace", papers: ["p3"],
      does: "Code checks four things with officially parsed numbers: total power ≤ limit, upload ≤ uplink capacity, recording ≤ storage, every numbered requirement is in the model. Then the model restates its own model in sentences (Paper 3's query use) and code checks every brief number is read back.", input: "Officially parsed numbers + requirements", output: "Four checks + read-back text" },
    { id: "human", row: "main", col: 7, kind: "human", owner: "Person", title: "⑥ Person decides · memory", sub: "approval needs all four checks",
      does: "A design can be approved only if all four checks pass and no requirement carries a number of unknown origin. The script never chooses. Once approved, its official parse joins memory.", input: "Checks, read-back, alignment", output: "Approve / reject; approved designs join memory" },
    { id: "source", row: "side", col: 3, kind: "guard", owner: "Code", title: "Number source check", sub: "every number must be in the brief",
      does: "Every number in the requirements must appear in the brief. If one does not, the run cannot go into memory until a person supplies it.", input: "Requirements + brief", output: "Numbers of unknown origin" },
    { id: "repair", row: "side", col: 4, kind: "loop", owner: "Model", title: "Repair from errors", sub: "error text sent back, numbers kept", papers: ["p3"],
      does: "When a design fails the official Pilot, the error text goes back to the model with: fix the syntax only, keep the numbers. Up to 3 parses per design.", input: "Original prompt + last version + error text", output: "A new version, validated again" },
    { id: "catalog", row: "side", col: 5, kind: "source", owner: "Synthetic catalog", title: "Parts catalog", sub: "5 slots, 11 parts · 3 parameters",
      does: "2 visible cameras, 3 infrared options, 2 computers, 2 uplinks, 2 storage sizes, plus recording rate, retention hours and upload rate. The choices in 2.2 come from here. Not RTX data.", input: "—", output: "Parts and parameters to choose from" },
    { id: "tradeoff", row: "side", col: 6, kind: "loop", owner: "Model · code recomputes", title: "Trade-offs", sub: "catalog choices only",
      does: "If a check fails, the model proposes 3 alternatives using only catalog parts and parameters. Its numbers are not trusted: code recomputes each one from the catalog and marks it feasible or not. 60 W cannot change.", input: "Brief + failing checks + catalog", output: "3 proposals + code's recomputation" },
  ],
  edges: [
    { from: "brief", to: "retrieve" }, { from: "retrieve", to: "gen" }, { from: "gen", to: "syntax" }, { from: "syntax", to: "align" },
    { from: "align", to: "check" }, { from: "check", to: "human" },
    { from: "mem", to: "retrieve", kind: "feed", route: "v", label: "searched by brief words and numbers" },
    { from: "mem", to: "align", kind: "feed", route: "rd", label: "alignment target: MaritimeISR" },
    { from: "gen", to: "source", kind: "side", route: "v", label: "checked one by one", side: "left" },
    { from: "syntax", to: "repair", kind: "loop", route: "v", label: "FAIL" },
    { from: "repair", to: "gen", kind: "loop", route: "upleft", label: "error text" },
    { from: "catalog", to: "tradeoff", kind: "feed", route: "h" },
    { from: "check", to: "tradeoff", kind: "loop", route: "v", label: "a check fails" },
    { from: "tradeoff", to: "human", kind: "side", route: "ru", label: "a person chooses" },
    { from: "human", to: "mem", kind: "mem", route: "home", label: "approved → memory; the next retrieval finds it" },
  ],
  captions: {
    p2: "<b>Paper 2 → ① Retrieve</b>: after the official Pilot parses MaritimeISR, every element becomes a card (type, full name, value). The brief's words and numbers score the cards; the top 4 are seeds, plus their one-hop neighbours (ownership, connection ends). Matched cards become the \"examples\" part of the design prompt. The paper uses vectors and FAISS; this uses words only. <a href=\"#s03\">See the comparison in 0.3</a>",
    p3: "<b>Paper 3 → ② Generate, repair, ⑤ read-back</b>: prompt = rules (SysML rules) + template (attribute contract: names and values) + examples (retrieved cards). Syntax errors go back as the official error text (in the paper a person corrects). ⑤ Read-back has the model restate requirements from its own model, Paper 3's query use. <a href=\"#s03\">See the comparison in 0.3</a>",
    p1: "<b>Paper 1 → ④ Align</b>: the model proposes \"design A element ↔ MaritimeISR element\" mappings, code checks both names exist and classifies each pair, then writes a separate alignment package of alias and allocation statements that the official Pilot parses with both source files. Neither source model is edited; a person accepts or rejects each pair in 2.3. <a href=\"#s03\">See the comparison in 0.3</a>",
    ours: "<b>Official SysML v2 Pilot</b>: ③ validates both designs, ④ validates the alignment package. Budget checks read only its parsed numbers.",
  },
};

/* ======================= header, TOC, part 0 ======================= */
function renderHeader() {
  const f = S.facts;
  $("#kpi-total").textContent = `${f.flash.pass} / ${f.flash.n}`;
  $("#kpi-total-sub").textContent = `${pct(f.flash.pass, f.flash.n)} · scored by the official Pilot + answer keys`;
  $("#kpi-jev").textContent = `${f.jev.agree} / ${f.jev.cells}`;
  $("#kpi-jev-sub").textContent = `Jev agrees with the tool ${pct(f.jev.agree, f.jev.cells)} · not scored`;
  const cards = f.knowledge.maritime.cards;
  $("#kpi-mem").textContent = `${cards} cards + ${S.memory.length} designs`;
  $("#kpi-mem-sub").textContent = "MaritimeISR element cards + designs a person approved";
}

function setupToc() {
  const links = $$("#toc a");
  const byId = Object.fromEntries(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const seen = new Map();
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) seen.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : null);
    const visible = [...seen.entries()].filter(([, top]) => top !== null).sort((a, b) => a[1] - b[1]);
    if (!visible.length) return;
    links.forEach((a) => a.classList.remove("on"));
    const on = byId[visible[0][0]];
    if (on) {
      on.classList.add("on");
      const toc = $("#toc");
      if (getComputedStyle(toc).display === "flex") toc.scrollLeft = on.offsetLeft - toc.clientWidth / 2 + on.offsetWidth / 2;
    }
  }, { rootMargin: "-10% 0px -55% 0px" });
  Object.keys(byId).forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
}

function failingChecks(record) {
  const out = new Set();
  for (const d of record?.designs || []) for (const c of d.checks || []) if (c.status === "FAIL") out.add(c.id);
  return [...out];
}

function renderAnswers() {
  const f = S.facts;
  const cfg = Object.fromEntries(f.configs.map((c) => [c.id, c]));
  const typeLine = TYPE_ORDER.filter((t) => BT(f.by_type, t).n).map((t) => `${t} ${BT(f.by_type, t).pass}/${BT(f.by_type, t).n}`).join(" · ");
  const r = S.record;
  let appBig = "No run yet";
  let appText = "Pick parts in 2.2 and give them to the agent.";
  if (r && Array.isArray(r.designs)) {
    const fails = failingChecks(r);
    const ok = (r.gate?.eligible || []).length;
    const approved = (r.approvals || []).length;
    appBig = approved ? `All six stages; ${approved} design(s) approved into memory` : ok ? `All six stages; ${ok} design(s) can be approved` : "All six stages; budget checks failed";
    appText = `Latest run (${r.id}): ${(r.requirements?.requirements || []).length} requirements; ${r.designs.map((d) => `design ${d.key} official validation ${d.sysml_status}`).join(", ")}; alignment package ${r.alignment?.package?.sysml_status || "not generated"}; `
      + (fails.length ? `failing checks ${fails.join(", ")}; the agent proposed ${(r.tradeoffs?.proposals || []).length} trade-offs for a person to choose.` : "all four budget checks pass.");
  }
  const cards = [
    ["Question 1 · exam", "How much do models and agents get right without seeing the answer key?", `${f.flash.pass} / ${f.flash.n} cells pass (${pct(f.flash.pass, f.flash.n)})`,
      `By task type: ${typeLine}. Generating new models (GEN) is weakest. Repairing from errors (P1 ${cfg.P1.pass}/72) did not beat one-shot (P0 ${cfg.P0.pass}/72). Two agents: OpenCode ${f.opencode.pass}/24, Claude ${f.claude.pass}/24.`, "#s12"],
    ["Question 2 · judges", "Can a model judge replace the official tool for scoring?", `No: Jev agrees on ${f.jev.agree}/${f.jev.cells}`,
      `Jev false passes ${f.jev.false_pass} cells, all GEN; false fails ${f.jev.false_fail}. qwen3.8-max agrees on only ${f.judge.agree}/${f.judge.n} and false passes ${f.judge.false_pass}. Scores come only from the official tool and the answer keys.`, "#s12"],
    ["Question 3 · real scenario", "How far does a blank task get?", appBig, appText, "#s23"],
  ];
  $("#answers").innerHTML = cards.map(([q, t, b, p, href]) => `<article><span class="q">${q}</span><p style="font-weight:700;color:var(--ink);margin-top:4px">${t}</p><b>${esc(b)}</b><p>${esc(p)}</p><p style="margin-top:6px"><a href="${href}">Details →</a></p></article>`).join("");
}

const OPS = [
  { n: "①", title: "Two flow diagrams", where: "1.1 · 2.1", href: "#s11", can: "Click a node to see what it reads, what it produces and who does it; highlight one paper's steps; replay a run.", effect: "Read-only; no model call.", tags: [["local", "local · instant"]] },
  { n: "②", title: "288-cell matrix", where: "1.3 → 1.4", href: "#s13", can: "Click any cell to see every step from issuing the task to scoring, the error text each repair received, and how the judges ruled.", effect: "Reads the archive.", tags: [["local", "local · instant"]] },
  { n: "③", title: "Exam console", where: "1.5", href: "#s15", can: "Re-run a sealed task, or write a new task with its own answer key.", effect: "Real calls to the model and the official Pilot; writes a new record.", tags: [["model", "calls a model"], ["", "20 s – 2 min"]] },
  { n: "④", title: "Design space", where: "2.2", href: "#s22", can: "Swap parts, change parameters, edit the brief, then give it to the agent.", effect: "Budgets recompute in the browser; the agent then runs the six stages of 2.1.", tags: [["local", "instant recompute"], ["model", "agent about 1–2 min"]] },
  { n: "⑤", title: "Person decides", where: "2.3", href: "#s23", can: "Send a trade-off back to 2.2; approve a design that passes all four checks into memory.", effect: "Approval writes to memory; the next ① Retrieve finds it.", tags: [["write", "writes to memory"]] },
  { n: "⑥", title: "MOD change", where: "2.4", href: "#s24", can: "Pick one of MOD-01 to MOD-05, see its latest change record, or have the model make the change again.", effect: "Two model calls and the official Pilot. Task and design verdicts are shown separately.", tags: [["model", "about 1 min"]] },
];

function renderOps() {
  $("#ops").innerHTML = OPS.map((o) => `<article><header><span class="op-pill">Action ${o.n}</span><b>${esc(o.title)}</b><span class="hint">${esc(o.where)}</span></header>
    <p><b>You can</b> ${esc(o.can)}</p><p><b>What happens</b> ${esc(o.effect)}</p>
    <div class="meta">${o.tags.map(([k, t]) => `<span class="tag ${k}">${esc(t)}</span>`).join("")}<a class="go" href="${o.href}">Go there →</a></div></article>`).join("")
    + `<p class="hint" style="grid-column:1/-1">The cost panel in 1.2 switches between China (Beijing) and international prices; nothing is saved.</p>`;
}

function focusNode(which, id) {
  const flow = FLOW[which];
  if (!flow) return;
  flow.select(id);
  document.getElementById(which === "bench" ? "s11" : "s21").scrollIntoView({ behavior: "smooth", block: "start" });
}

function setPaperAll(p) {
  FLOW.bench.setPaper(p);
  FLOW.app.setPaper(p);
  if (p) document.body.dataset.paper = p; else delete document.body.dataset.paper;
}

function focusPaper(p) {
  setPaperAll(p);
  document.getElementById("s21").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSources() {
  const k = S.facts.knowledge;
  const corpusChunks = k.corpus.reduce((a, c) => a + c.chunks, 0);
  const items = [
    { color: "#6c8ebf", title: "Exam task bank", size: `${k.tasks.n} tasks`, small: `+ ${k.tasks.gold} answer keys`, path: "bench/tasks/heldout/",
      how: "Written by people and sealed. GEN/MOD tasks may include a baseline model.", prompt: "The task statement goes into the prompt; the answer key never does and is opened only at \"Check against key\".", use: [["1.1 Issue task", "bench", "issue"], ["1.1 Answer key", "bench", "gold"]] },
    { color: "#d4b46a", title: "Notes corpus", size: `${k.corpus.length} files`, small: `${corpusChunks} notes`, path: k.corpus.map((c) => `bench/corpus/${c.file}`).join(" · "),
      how: "SysML syntax tips and maritime vocabulary, scored by the task statement's words.", prompt: "Only in P3's outline prompt, at most 3 notes.", use: [["1.1 Notes corpus (P3 only)", "bench", "corpus"]] },
    { color: "#1c7ed6", title: "Existing model MaritimeISR", size: `${k.maritime.cards} cards`, small: `${k.maritime.elements} elements · ${k.maritime.links} edges`, path: k.maritime.file,
      how: "The official Pilot parses it to JSON; code turns each element into a card: type, full name, value or connection ends.", prompt: "Retrieved cards become the \"examples\" part of the design prompt; the source file is not imported or edited.", use: [["2.1 ① Retrieve", "app", "retrieve"], ["2.1 ④ Alignment target", "app", "align"]] },
    { color: "#2b8a3e", title: "Approved designs", size: `${S.memory.length} designs`, small: S.memory.length ? S.memory.map((m) => `${m.run_id}·${m.design}`).join(", ") : "none approved yet", path: k.memory.file,
      how: "Only designs that pass all four checks, carry no number of unknown origin, and that a person approved.", prompt: "Retrieved together with the MaritimeISR cards, tagged \"approved\" in the prompt.", use: [["2.1 ⑥ Into memory", "app", "human"], ["2.1 ① Retrieve", "app", "retrieve"]] },
    { color: "#a996e0", title: "Synthetic parts catalog", size: `${k.catalog.options} parts`, small: `${k.catalog.slots} slots · ${k.catalog.params} parameters (incl. the fixed 60 W)`, path: "bench/discover.py · CATALOG",
      how: "Not a bill of materials and not RTX data.", prompt: "Only in the trade-off prompt; the model's numbers are not trusted, code recomputes from the catalog.", use: [["2.1 Parts catalog", "app", "catalog"], ["2.1 Trade-offs", "app", "tradeoff"]] },
    { color: "#7d8b96", title: "Official SysML v2 standard library", size: `${k.maritime.library_files} files`, small: "ships with Pilot 0.62", path: "vendor/ (not modified)",
      how: "Libraries such as ScalarValues and ISQ, loaded by the official tool when parsing.", prompt: "Not in any prompt. It is part of the tool, not the agent's memory.", use: [["1.1 Official syntax", "bench", "syntax"], ["2.1 ③ Official validation", "app", "syntax"]] },
  ];
  $("#sources").innerHTML = items.map((it) => `<article class="ks" style="--kc:${it.color}">
      <h4>${esc(it.title)}</h4><div class="size">${esc(it.size)}<small>${esc(it.small)}</small></div><div class="path">${esc(it.path)}</div>
      <dl><dt>What it is</dt><dd>${esc(it.how)}</dd><dt>In the prompt?</dt><dd>${esc(it.prompt)}</dd></dl>
      <div class="chips">${it.use.map(([t, w, id]) => `<button type="button" class="chip" data-focus="${w}:${id}">${esc(t)}</button>`).join("")}</div></article>`).join("");
}

function renderPapers() {
  const f = S.facts;
  const r = S.record && Array.isArray(S.record.designs) ? S.record : {};
  const ret = r.retrieval || {};
  const al = r.alignment || {};
  const pkg = al.package || {};
  const cfg = Object.fromEntries(f.configs.map((c) => [c.id, c]));
  const nodes = ret.nodes || [];
  const seeds = nodes.filter((n) => n.role === "seed").length;
  const graph = f.graph || {};
  const qPass = Object.values(graph).filter((x) => x.status === "PASS").length;
  const papers = [
    { key: "p2", act: "① Retrieve", title: "Paper 2 · Bader et al.: GRAG graph-retrieval QA", venue: "ISSE 2025 · one electric-vehicle model, 3 questions",
      orig: ["SysML v2 API exports JSON-LD", "converted to an RDF graph", "node + one-hop neighbours", "MiniLM vectors · FAISS threshold", "GPT-4.1 answers"],
      ours: ["official Pilot parse JSON", "one card per element, connections included", "MiniLM vectors · FAISS · cosine ≥ 0.30 + exact-name bonus", "add one-hop neighbours", "cards go into the design prompt (2.1) or the P3 outline prompt (1.1)"],
      where: [["2.1 ① Retrieve", "app", "retrieve"], ["2.1 Memory", "app", "mem"], ["1.1 Notes corpus (P3: official examples + notes)", "bench", "corpus"]],
      evidence: `Latest run: memory had ${ret.library_size ?? "—"} cards; ${nodes.length} elements matched (${seeds} seeds, ${nodes.length - seeds} neighbours), ${Object.keys(ret.numbers || {}).length} with values${ret.method ? `; retrieval method ${esc(ret.method)}` : " (this run predates vector retrieval: keyword seeds)"}. Separately, the query tasks were redone with graph retrieval: ${qPass}/${Object.keys(graph).length} QRY correct${graph["QRY-03"] ? `; QRY-03 asks for a connection count, answer key 3, graph retrieval answered ${esc(graph["QRY-03"].answer)}` : ""}. On the five QRY questions, hybrid retrieval finds 13/15 key elements against 11/15 for the earlier keyword ranking (analysis/retrieval-eval-*.json).`,
      missing: "Same embedding model and index type as the paper, on our Pilot parse instead of the API's JSON-LD; the exact-name bonus is ours. The paper's radius 0.35 was calibrated on its vehicle model and is not reused; the threshold here is calibrated on our five labelled questions. The paper's F1 of 0.904 is a retrieval metric on its own model and is not reproduced." },
    { key: "p3", act: "② Generate · modify · query", title: "Paper 3 · Longshore, Bell, Madachy (NPS)", venue: "SYM-AM-24-048 / -138 · custom GPT: rules + template + examples",
      orig: ["rules", "template", "examples", "generate the model", "a person reads errors, corrects, regenerates", "create / modify / query"],
      ours: ["rules: SysML rules", "template: attribute contract", "examples: retrieved cards", "generate requirements and two designs", "official error text sent back for repair", "read-back = query"],
      where: [["2.1 ② Generate", "app", "gen"], ["2.1 Repair from errors", "app", "repair"], ["2.1 ⑤ Read-back", "app", "check"], ["1.1 Write the answer", "bench", "write"], ["1.1 Repair (P1)", "bench", "repair"]],
      evidence: `Exam: ${f.flash.pass}/${f.flash.n} cells pass; generating new models (GEN) passes only ${f.by_type.GEN.pass}/${f.by_type.GEN.n}. P1 repair scores ${cfg.P1.pass}/72, no better than one-shot at ${cfg.P0.pass}/72: on GEN-03, P1 resubmitted the same code unchanged 4 times (visible in 1.4).${(r.designs || []).length ? ` Latest run: ${r.designs.map((d) => `design ${d.key} official validation ${d.sysml_status}, ${(d.attempts || []).length} parse(s)`).join("; ")}.` : ""}`,
      missing: "In the paper a person corrects errors; here the official tool's errors do. The paper's bicycle example model was not used and its Yes/No capability table was not built." },
    { key: "p1", act: "④ Align", title: "Paper 1 · Li, Husung, Wang: cross-organization model alignment", venue: "arXiv 2508.16181 · ISSE 2025 · seven stages, human review, source models unchanged",
      orig: ["preparation and syntax check", "element summaries", "candidate mappings (LLM)", "mapping verification", "separate alignment package", "consistency check", "export"],
      ours: ["design A × MaritimeISR", "model proposes mappings", "code checks both names and classifies each pair from the two parses", "code writes alias (definitions, features) and allocation (usages); a part usage against a definition is left to the person", "three files through the Pilot", "per-pair Accept / Reject in 2.3, sources unchanged"],
      where: [["2.1 ④ Align", "app", "align"], ["2.1 ⑥ Person decides", "app", "human"], ["1.1 Check against key (MOD values to keep)", "bench", "check"]],
      evidence: al.proposed ? `Latest run: ${al.proposed} mappings proposed, ${al.verified} with both ends present; alignment package ${esc(pkg.name || "")} official Pilot ${esc(pkg.sysml_status || "not generated")}. A misspelled element name makes the Pilot report "Couldn't resolve reference" and the package FAILs.` : "The latest run produced no alignment package.",
      missing: "No element summaries and no automatic semantic matching; only dependency, not alias or allocation. A Pilot pass shows the names resolve, not that the two sides mean the same thing; that needs a person." },
  ];
  const chain = (list) => list.map((x) => `<span>${esc(x)}</span>`).join("<i>→</i>");
  $("#papers").innerHTML = papers.map((p) => `<article class="paper p-${p.key}">
      <header><span class="act">${esc(p.act)}</span><h4>${esc(p.title)}</h4><p>${esc(p.venue)}</p></header>
      <section><h5>What the paper does</h5><div class="pipe">${chain(p.orig)}</div></section>
      <section><h5>What we do</h5><div class="pipe ours">${chain(p.ours)}</div></section>
      <section><h5>Where it sits in the flow (click to light it up)</h5><div class="chips">${p.where.map(([t, w, id]) => `<button type="button" class="chip" data-focus="${w}:${id}">${esc(t)}</button>`).join("")}<button type="button" class="chip yes" data-paper-focus="${p.key}">Highlight only this paper</button></div></section>
      <section><h5>Evidence on this page</h5><p class="evidence">${p.evidence}</p></section>
      <section><h5>Not reproduced</h5><p class="missing">${esc(p.missing)}</p></section></article>`).join("");
}

/* ======================= 1.2 scores ======================= */
function bar(label, value, max, text, cls = "") {
  return `<div class="bar-row"><span>${esc(label)}</span><div class="track"><div class="fill ${cls}" style="width:${max ? (value / max) * 100 : 0}%"></div></div><span class="v">${esc(text)}</span></div>`;
}
function stack(label, parts, total) {
  return `<div class="bar-row"><span>${esc(label)}</span><div class="track">${parts.map(([v, cls]) => `<div class="fill ${cls}" style="width:${(v / total) * 100}%"></div>`).join("")}</div><span class="v">${parts[0][0]}/${total}</span></div>`;
}

function renderScores() {
  const f = S.facts;
  const cfg = f.configs;
  $("#kpis").innerHTML = [
    ["Main model qwen3.8-flash", `${f.flash.pass}/${f.flash.n}`, `${pct(f.flash.pass, f.flash.n)} · 4 approaches × 24 tasks × 3 repeats`],
    ["OpenCode agent", `${f.opencode.pass}/${f.opencode.n}`, `MOD-05 task verdict ${f.opencode.mod05}: design over budget, limit unchanged`],
    ["Claude Code agent", `${f.claude.pass}/${f.claude.n}`, `qwen3.8-max through CCR · failed: ${f.claude.fail_tasks.join(", ") || "none"}`],
    ["SysEngBench multiple choice", `${f.sysengbench.correct}/${f.sysengbench.n}`, "answered by Jev · scored separately, not in the 288"],
  ].map(([t, b, p]) => `<div class="kpi-card"><span>${esc(t)}</span><b>${esc(b)}</b><p>${esc(p)}</p></div>`).join("");
  const maxTok = Math.max(...cfg.map((c) => c.tokens));
  const qFalseFail = f.judge.n - f.judge.agree - f.judge.false_pass;
  $("#score-panels").innerHTML = `
    <div class="panel"><h4>Pass rate</h4>
      ${cfg.map((c) => bar(CONFIG_NAME[c.id], c.pass, c.n, `${c.pass}/${c.n}`)).join("")}
      ${bar("OpenCode", f.opencode.pass, f.opencode.n, `${f.opencode.pass}/${f.opencode.n}`)}
      ${bar("Claude Code", f.claude.pass, f.claude.n, `${f.claude.pass}/${f.claude.n}`)}
      <div class="bar-sep"></div>
      ${TYPE_ORDER.map((t) => bar(`${t} ${TYPE_NAME[t]}`, BT(f.by_type, t).pass, BT(f.by_type, t).n, BT(f.by_type, t).n ? `${BT(f.by_type, t).pass}/${BT(f.by_type, t).n}` : "not run yet")).join("")}
      <p class="note">The scoring rule changed once, on October 3. The old rule failed MOD-05's honest answers and would have passed an answer that raised the limit. The current rule requires "values to keep are unchanged + check results match the answer key"; the main matrix went from ${f.rescore.archived_flash_pass} (archived) to ${f.flash.pass}, and only MOD-05 cells changed (re-scoring record ${esc(f.rescore.file)}). Across three repeats of the same task and approach, ${f.reliability.flips}/${f.reliability.groups} groups gave different results.</p></div>
    <div class="panel"><h4>Tokens (main model, 72 cells per approach)</h4>
      ${cfg.map((c) => bar(c.id, c.tokens, maxTok, num(c.tokens), "tok")).join("")}
      <div class="bar-sep"></div>
      ${cfg.map((c) => bar(`${c.id} per passing cell`, c.tokens / c.pass, Math.max(...cfg.map((x) => x.tokens / x.pass)), num(Math.round(c.tokens / c.pass)), "tok")).join("")}
      <p class="note">USD figures are in the cost panel below.</p></div>
    <div class="panel"><h4>Do the judges agree with the official tool? (288 cells)</h4>
      ${stack("Jev 1.13", [[f.jev.agree, "ok"], [f.jev.false_pass, "fp"], [f.jev.false_fail, "fn"]], f.jev.cells)}
      ${stack("qwen3.8-max", [[f.judge.agree, "ok"], [f.judge.false_pass, "fp"], [qFalseFail, "fn"]], f.judge.n)}
      <div class="legend"><span><i style="background:#2f9c7d"></i>agrees</span><span><i style="background:#d9534f"></i>false pass</span><span><i style="background:#e0a35f"></i>false fail</span></div>
      <table style="margin-top:8px"><thead><tr><th>Task type</th><th class="num">Jev agrees</th><th class="num">qwen agrees</th></tr></thead><tbody>
      ${TYPE_ORDER.filter((t) => BT(f.by_type, t).n).map((t) => `<tr><td>${t} ${TYPE_NAME[t]}</td><td class="num">${BT(f.jev.by_type, t).agree}/${BT(f.jev.by_type, t).n}</td><td class="num">${BT(f.judge.by_type, t).agree}/${BT(f.judge.by_type, t).n}</td></tr>`).join("")}
      </tbody></table>
      <p class="note">All ${f.jev.false_pass} of Jev's false passes are GEN: it passes models that fail the official syntax check. Its false fails are mostly AMB: the answer asked the right question and Jev still failed it. ${esc(f.rescore.judge_basis)}</p></div>
    <div class="panel cost" id="cost-panel"></div>`;
  renderCost(false);
}

function renderCost(intl) {
  const c = S.facts.costs;
  const pr = c.prices;
  const items = c.items.map((it) => ({ ...it, usd: usdOf(it.model, it, intl) }));
  const max = Math.max(...items.map((it) => it.usd || 0));
  const p0 = items.find((it) => it.id === "P0");
  const oc = items.find((it) => it.id === "opencode");
  const p3 = items.find((it) => it.id === "P3");
  const priceChip = (name) => {
    const m = pr.models[name];
    const use = intl && m.intl ? m.intl : m;
    return `<a class="price" href="${esc(m.source)}" target="_blank" rel="noopener"><b>${esc(name)}</b> input $${use.input} · cached $${use.cache} · output $${use.output}<small>per million tokens · official page</small></a>`;
  };
  let group = "";
  const rows = items.map((it) => {
    const head = it.group !== group ? `<div class="cost-group">${esc(it.group)}</div>` : "";
    group = it.group;
    const per = it.passes ? ` · ${money(it.usd / it.passes)} per passing cell` : "";
    const tokens = `input ${num(it.input)}${it.cached ? ` (${num(it.cached)} cached)` : ""} · output ${num(it.output)} tokens${it.calls ? ` · ${num(it.calls)} calls` : ""}`;
    return `${head}<div class="cost-row"><span class="cl">${esc(it.label)}<small>${esc(it.model)}${it.complete === false ? " · some calls not recorded" : ""}</small></span>
      <div class="track"><div class="fill" style="width:${max ? Math.max((it.usd / max) * 100, 0.6) : 0}%"></div></div>
      <span class="cv">${money(it.usd)}</span><small class="ct">${tokens}${per}</small></div>`;
  }).join("");
  const insight = p0 && oc && p3 ? `Same flash model: OpenCode spent ${money(oc.usd)} on 24 tasks, ${Math.round(oc.usd / p0.usd)}× what P0 spent on 72 cells (${money(p0.usd)}), because every step re-sends the whole workspace (mostly billed as cached input). P3 costs ${(p3.usd / p0.usd).toFixed(1)}× P0 and passes only ${p3.passes - p0.passes} more cell(s).` : "";
  $("#cost-panel").innerHTML = `<div class="cost-head"><h4>Cost in USD at official list prices</h4>
      <div class="seg-toggle" id="cost-region"><button data-region="cn" class="${intl ? "" : "on"}">${esc(pr.region)} · our region</button><button data-region="intl" class="${intl ? "on" : ""}">International · comparison</button></div></div>
    <p class="note" style="margin:0 0 8px">${esc(pr.region_note)} Prices checked ${esc(pr.checked)}.</p>
    <div class="price-row">${["qwen3.8-flash", "qwen3.8-max", "jev-1.13.0"].map(priceChip).join("")}</div>
    ${insight ? `<div class="audit" style="margin:10px 0">${esc(insight)}</div>` : ""}
    <div class="cost-rows">${rows}</div>
    <p class="note">Recorded total about ${money(items.reduce((a, it) => a + (it.group_id === "part2" || it.group_id === "mod" ? 0 : it.usd || 0), 0) + [...(c.runs || []), ...(c.mod_runs || [])].reduce((a, r) => a + (usdOf("qwen3.8-max", r, intl) || 0), 0))}. Not recorded and not above: ${esc(c.unrecorded.join(" "))}</p>`;
  $$("#cost-region button").forEach((b) => { b.onclick = () => renderCost(b.dataset.region === "intl"); });
}

/* ======================= 1.3 matrix ======================= */
function claudeCell(task) {
  const first = S.cells.find((c) => c.cohort_id === "claude1" && c.task_id === task);
  const retry = S.cells.find((c) => c.cohort_id === "claude2" && c.task_id === task);
  return first && first.status !== "PASS" && retry ? retry : first;
}

function cellClass(c) {
  if (!c) return "J-none";
  if (S.mxMode === "tool") return c.status;
  const j = S.mxMode === "jev" ? c.jev : c.qwen;
  if (!j) return "J-none";
  return j.agree ? "J-ok" : j.false_pass ? "J-fp" : "J-fn";
}

function renderGlossary() {
  const f = S.facts;
  const count = (types) => S.tasks.filter((x) => types.includes(x.type)).length;
  const modelTasks = count(["GEN", "MOD", "ALN"]);
  const textTasks = count(["QRY", "AMB", "RT"]);
  const cards = TYPE_ORDER.map((t) => {
    const g = TYPE_GUIDE[t];
    const bt = BT(f.by_type, t);
    return `<article class="gl-type ${g.pilot ? "model" : "text"}"><header><b>${t}</b><i>${esc(TYPE_SHORT[t])}</i><span>${count([t])} tasks · ${bt.n ? `${bt.pass}/${bt.n} pass` : "not run yet"}</span></header>
      <h5>${esc(TYPE_NAME[t])}</h5>
      <dl><dt>Gets</dt><dd>${esc(g.gets)}</dd><dt>Answers with</dt><dd>${esc(g.gives)}</dd><dt>Passes when</dt><dd>${esc(g.judge)}</dd></dl>
      <footer>${g.pilot ? "Official syntax check: yes" : "Official syntax check: not applicable"}</footer></article>`;
  }).join("");
  const codes = [
    ["GEN-03", "task 3 of type GEN; each type has 4–5 tasks"],
    ["P0 … P3", "four approaches with the same model: one-shot · repair from errors (up to 3) · outline first · outline + 3 retrieved notes"],
    ["1 2 3", "repeat number; every task × approach ran three times"],
    ["OC · CL", "OpenCode and Claude Code, off-the-shelf agents, one run per task, not in the 288"],
    ["↻n", "P1 cell that went through n repair rounds"],
    ["＊", "current scorer differs from the archived verdict (MOD-05 only; hover to see it)"],
    ["9/12", "row end: main-matrix cells passed out of 12 (4 approaches × 3 repeats); column foot: that column's pass rate"],
  ];
  $("#mx-guide").innerHTML = `<div class="gl-types">${cards}</div>
    <p class="gl-note"><b>Why "not applicable" shows up so often.</b> Only GEN, MOD and ALN answers are SysML, so only those ${modelTasks} tasks (${modelTasks * 12} main-matrix cells) go through the official Pilot. QRY, AMB and RT answers are JSON or text (${textTasks} tasks, ${textTasks * 12} cells); they are compared with the answer key directly. Only MOD-05 has a power budget, so a design verdict exists for its 12 cells alone.</p>
    <div class="gl-codes">${codes.map(([k, v]) => `<span><b>${esc(k)}</b>${esc(v)}</span>`).join("")}</div>`;
}

function renderMatrix() {
  renderGlossary();
  const flash = {};
  for (const c of S.cells) if (c.cohort_id === "flash") flash[`${c.task_id}|${c.configuration}|${c.repeat}`] = c;
  const cols = [];
  for (const cfg of ["P0", "P1", "P2", "P3"]) for (const r of [1, 2, 3]) cols.push({ cfg, r, get: (t) => flash[`${t}|${cfg}|${r}`] });
  cols.push({ cfg: "OC", get: (t) => S.cells.find((c) => c.cohort_id === "opencode" && c.task_id === t) });
  cols.push({ cfg: "CL", get: (t) => claudeCell(t) });
  const tasks = [...S.tasks].sort((a, b) => TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type) || a.id.localeCompare(b.id));
  const legend = {
    tool: [["#c9ecd7", "pass"], ["#f5c3bf", "fail"], ["#f3e1aa", "timeout"]],
    jev: [["#d9d1f4", "Jev agrees with the tool"], ["#f1928b", "Jev false pass"], ["#f3c98d", "Jev false fail"], ["#edf1f4", "no judge (agent columns)"]],
    qwen: [["#d9d1f4", "qwen agrees with the tool"], ["#f1928b", "qwen false pass"], ["#f3c98d", "qwen false fail"], ["#edf1f4", "no judge (agent columns)"]],
  }[S.mxMode];
  $("#mx-legend").innerHTML = legend.map(([c, t]) => `<span><i style="background:${c}"></i>${t}</span>`).join("");
  const head1 = `<tr><th></th>${["P0", "P1", "P2", "P3"].map((p) => `<th colspan="3">${CONFIG_NAME[p]}</th><th class="gap"></th>`).join("")}<th colspan="2">agents</th><th></th></tr>`;
  const head2 = `<tr><th></th>${["P0", "P1", "P2", "P3"].map(() => `<th>1</th><th>2</th><th>3</th><th class="gap"></th>`).join("")}<th title="OpenCode">OC</th><th title="Claude Code">CL</th><th>Pass</th></tr>`;
  let body = "";
  for (const type of TYPE_ORDER) {
    const group = tasks.filter((t) => t.type === type);
    const bt = BT(S.facts.by_type, type);
    body += `<tr class="grp"><th colspan="20"><b>${type}</b> = ${esc(TYPE_NAME[type])} <span class="grp-io">answer: ${esc(TYPE_GUIDE[type].gives.toLowerCase())}</span> · ${bt.n ? `main matrix ${bt.pass}/${bt.n} (${pct(bt.pass, bt.n)})` : "not in the saved batches yet (added 2026-10-06; runs in the next matrix)"}</th></tr>`;
    for (const t of group) {
      let passed = 0;
      let total = 0;
      const tds = cols.map((col, i) => {
        const c = col.get(t.id);
        if (c && c.cohort_id === "flash") { total += 1; passed += c.status === "PASS" ? 1 : 0; }
        const gap = i < 12 && col.r === 3 ? `<td class="gap"></td>` : "";
        if (!c) return `<td><button class="cell J-none" disabled>·</button></td>${gap}`;
        const rr = Number(c.repair_rounds || 0);
        const moved = c.archived_status && c.archived_status !== c.status;
        const tip = `${t.id} · ${c.cohort}${c.configuration ? ` · ${c.configuration}` : ""}${col.r ? ` repeat ${col.r}` : ""} · task verdict ${c.status}${moved ? ` (archived ${c.archived_status}; re-scored with the current rule)` : ""}${c.engineering_status && c.engineering_status !== "UNKNOWN" ? ` · design verdict ${c.engineering_status}` : ""}${c.jev ? ` · Jev ${c.jev.agree ? "agrees" : c.jev.false_pass ? "false pass" : "false fail"}` : ""}`;
        return `<td><button type="button" class="cell ${cellClass(c)}" data-cell="${esc(c.id)}" title="${esc(tip)}">${rr ? `↻${rr}` : ""}${moved ? "＊" : ""}</button></td>${gap}`;
      }).join("");
      body += `<tr><th class="rowh">${t.id}</th>${tds}<td class="rowsum">${passed}/${total}</td></tr>`;
    }
  }
  const foot = `<tr><td></td>${cols.map((col, i) => {
    const list = tasks.map((t) => col.get(t.id)).filter(Boolean);
    const p = list.filter((c) => c.status === "PASS").length;
    return `<td title="${p}/${list.length}">${list.length ? Math.round((p / list.length) * 100) : "—"}%</td>${i < 12 && col.r === 3 ? `<td class="gap"></td>` : ""}`;
  }).join("")}<td></td></tr>`;
  $("#matrix").innerHTML = `<table class="mx"><thead>${head1}${head2}</thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table>`;
  if (S.cell && !S.cellLive) { const on = $(`#matrix [data-cell="${CSS.escape(S.cell.id)}"]`); if (on) on.classList.add("on"); }
}

/* ======================= 1.4 one cell ======================= */
const BENCH_STEP = { "Issue task": "issue", "Retrieve notes": "corpus", "Outline": "outline", "Write answer": "write", "Official syntax": "syntax", "Repair from errors": "repair", "Read values": "watts", "Check against key": "check", "Approval gate": "gate", "Archive": "archive" };
const BENCH_ORDER = ["bank", "issue", "corpus", "outline", "write", "syntax", "repair", "watts", "gold", "check", "gate", "archive", "judge"];

function benchStates(d, live) {
  const st = { bank: "pass" };
  for (const s of d.steps || []) { const id = BENCH_STEP[s.title]; if (id && s.state !== "wait") st[id] = s.state; }
  const cfg = d.configuration;
  if (!live) {
    st.outline = cfg === "P2" || cfg === "P3" ? (d.outline ? "pass" : "skip") : "skip";
    st.corpus = cfg === "P3" ? ((d.retrieved || []).length ? "pass" : "skip") : "skip";
  } else {
    if (cfg !== "P2" && cfg !== "P3") st.outline = "skip";
    if (cfg !== "P3") st.corpus = "skip";
  }
  if ((d.attempts || []).length > 1 && (!st.repair || st.repair === "skip")) st.repair = d.sysml_status === "PASS" ? "pass" : "fail";
  st.gold = st.check && st.check !== "skip" ? "pass" : st.check === "skip" ? "skip" : "";
  const judgeWrong = (d.jev && !d.jev.agree) || (d.qwen && !d.qwen.agree);
  st.judge = live ? (st.archive ? "skip" : "") : !d.jev && !d.qwen ? "skip" : judgeWrong ? "fail" : "pass";
  if (live && d.phase && BENCH_STEP[d.phase]) st[BENCH_STEP[d.phase]] = "run";
  return st;
}

function stepDetail(d, title) {
  return (d.steps || []).find((s) => s.title === title)?.detail || "";
}

function benchNow(id) {
  const d = S.cell;
  if (!d) return "No cell selected yet. Click one in 1.3.";
  const st = FLOW.bench.getState()[id] || "";
  const map = Object.entries(BENCH_STEP).find(([, v]) => v === id);
  if (id === "bank") return esc(`${d.task_id} (${TYPE_NAME[d.type] || d.type})`);
  if (id === "gold") return st === "pass" ? "This cell opened the answer key at the check step. The text is at the bottom left of 1.4." : "This cell did not reach the check step.";
  if (id === "corpus") return d.configuration === "P3" ? esc(`${(d.retrieved || []).length} notes: ${(d.retrieved || []).map((x) => x.source).join(", ")}`) : "Not a P3 cell, so no notes were retrieved.";
  if (id === "outline") return d.outline ? esc(`Outline of ${d.outline.length} characters; full text in 1.4.`) : "This cell has no outline.";
  if (id === "judge") {
    if (!d.jev && !d.qwen) return "No judge record for this cell (agent column or live run).";
    return esc(`Jev: pass probability ${d.jev?.p_pass ?? "—"}, ${d.jev ? judgeWord(d, d.jev) : "—"}. qwen: ${d.qwen?.verdict ?? "—"}, ${d.qwen ? judgeWord(d, d.qwen) : "—"}.`);
  }
  if (id === "syntax" || id === "repair") {
    const at = d.attempts || [];
    if (!at.length) return esc(stepDetail(d, map ? map[0] : "") || "This cell has no official parse.");
    return esc(at.map((a) => `attempt ${a.attempt} ${a.status}${a.same_as_previous ? " (identical to the previous one)" : ""}`).join(" → "));
  }
  return esc(trunc(stepDetail(d, map ? map[0] : ""), 220)) || WORD[st];
}

function benchStages(d, live) {
  const st = benchStates(d, live);
  const at = d.attempts || [];
  const list = [{ id: "issue", title: "Issue task", state: st.issue || "", sub: "task statement only, no answer key" }];
  if (d.configuration === "P3") list.push({ id: "corpus", title: "Retrieve notes", state: st.corpus || "", sub: `${(d.retrieved || []).length} notes`, paper: "p2" });
  if (d.configuration === "P2" || d.configuration === "P3") list.push({ id: "outline", title: "Outline", state: st.outline || "", sub: d.outline ? `${d.outline.length} characters` : "" });
  list.push({ id: "write", title: "Write the answer", state: st.write || "", sub: d.tokens ? `${num(d.tokens)} tokens · ${(d.calls || []).length} calls` : d.cohort, paper: "p3" });
  if (d.type === "GEN" || d.type === "MOD" || at.length) {
    list.push({ id: "syntax", title: "Official syntax", state: st.syntax || "", sub: at.length ? `${at.length} parse(s) · last ${at[at.length - 1].status}` : stepDetail(d, "Official syntax"), paper: "ours" });
    if (at.length > 1 || (st.repair && st.repair !== "skip")) list.push({ id: "repair", title: "Repair from errors", state: st.repair || "", sub: `${Math.max(at.length - 1, 0)} round(s) · what each received`, paper: "p3" });
  }
  list.push({ id: "watts", title: "Read values", state: st.watts || "", sub: stepDetail(d, "Read values") });
  list.push({ id: "check", title: "Check against key", state: st.check || "", sub: stepDetail(d, "Check against key") });
  list.push({ id: "gate", title: "Approval gate", state: st.gate || "", sub: stepDetail(d, "Approval gate") });
  list.push({ id: "archive", title: "Archive", state: st.archive || "", sub: stepDetail(d, "Archive") });
  if (!live) {
    const wrong = [d.jev && !d.jev.agree ? "Jev" : "", d.qwen && !d.qwen.agree ? "qwen" : ""].filter(Boolean);
    list.push({ id: "judge", title: "Model judges (not scored)", state: st.judge || "",
      word: !d.jev && !d.qwen ? "no judges" : wrong.length === 2 ? "both wrong" : wrong.length ? `${wrong[0]} wrong` : "both right",
      sub: d.jev || d.qwen ? `Jev ${d.jev ? (d.jev.agree ? "agrees with the tool" : "disagrees with the tool") : "—"} · qwen ${d.qwen ? (d.qwen.agree ? "agrees with the tool" : "disagrees with the tool") : "—"}` : "no judge record" });
  }
  return list;
}

function stageList(host, stages, current, attr) {
  host.innerHTML = stages.map((s) => `<button type="button" class="stage ${s.state || ""}${s.id === current ? " on" : ""}" data-${attr}="${s.id}" data-paper="${s.paper || ""}"><span class="dot"></span><span><b>${esc(s.title)}${ptag(s.paper)}</b><small>${esc(trunc(s.sub, 60))}</small></span><span class="st">${esc(s.word || WORD[s.state || ""])}</span></button>`).join("");
}

function attemptsHTML(attempts, sentLine) {
  if (!attempts.length) return `<p class="hint">This cell has no official parse record.</p>`;
  return `<div class="attempts">${attempts.map((a, i) => {
    const head = `<header><b>Attempt ${a.attempt} sent to the official Pilot</b>${badge(a.status)}${a.same_as_previous ? `<span class="badge warn">identical to the previous one</span>` : ""}<span class="hint mono">${esc(a.run_id || "no run folder")}</span></header>`;
    const diag = a.diagnostics?.length ? `<div><div class="block-h">Official error text${i < attempts.length - 1 ? " (these lines go back to the model next round)" : ""}</div><ul class="diag">${a.diagnostics.map((x) => `<li><span>${x.line != null ? `line ${x.line}` : "—"}</span>${esc(x.message)}</li>`).join("")}</ul></div>` : `<div><div class="block-h">Official errors</div><p class="hint">No errors.</p></div>`;
    const body = a.same_as_previous ? `<div class="same">The model sent back exactly the same code as last time, with the same errors. The repair did nothing.</div>` : `<div class="body">${diag}<div><div class="block-h">This answer</div><pre class="code">${esc(a.text || a.source || "(not recorded)")}</pre></div></div>`;
    const arrow = i < attempts.length - 1 ? `<div class="loop-arrow">↻ ${esc(sentLine)}</div>` : "";
    return `<div class="attempt ${String(a.status).toLowerCase()}">${head}${body}</div>${arrow}`;
  }).join("")}</div>`;
}

function cellDetailHTML(d, id) {
  const io = (who, title, read, give) => `<div class="who">${esc(who)}</div><h4 class="dt">${esc(title)}</h4><div class="io"><div><h5>Reads</h5><p>${esc(read)}</p></div><div><h5>Produces</h5><p>${esc(give)}</p></div></div>`;
  const at = d.attempts || [];
  switch (id) {
    case "issue":
      return io("Code", "Issue task", `Task bank bench/tasks/heldout/${d.task_id}`, "Task statement (text at the bottom left)") + `<div class="audit"><b>Check</b>The prompt has no answer key. The key is opened only at "Check against key".</div>`;
    case "corpus":
      return io("Code · simplified Paper 2", "Retrieve notes", "Words in the task statement + 15 notes", "The 3 highest-scoring notes")
        + ((d.retrieved || []).map((x) => `<div class="block-h" style="margin-top:8px">${esc(x.source)}${x.score != null ? ` · score ${x.score}` : ""}</div><pre class="code light">${esc(x.text)}</pre>`).join("") || `<p class="hint">No notes retrieved.</p>`)
        + `<div class="audit"><b>Check</b>Notes go only into the outline prompt; they contain no answer key.</div>`;
    case "outline":
      return io("Model", "Outline", "Task statement (P3: plus 3 notes)", "Outline JSON, no SysML") + `<pre class="code light">${esc(d.outline || "(no outline)")}</pre>`;
    case "write":
      return io("Model · agent under test", "Write the answer", `Task statement + SysML rules${d.outline ? " + outline" : ""}`, d.type === "GEN" || d.type === "MOD" ? "A SysML package" : "Text or JSON")
        + `<p class="hint">${esc(d.cohort)} · ${esc(d.configuration || "")}${d.tokens ? ` · ${num(d.tokens)} tokens · calls ${esc((d.calls || []).join(", "))}` : ""}. The final answer is at the bottom right${at.length > 1 ? "; every attempt is under \"Official syntax\"" : ""}.</p>`;
    case "syntax":
      return io("Official tool", "Official syntax", "SysML in the answer", "PASS / FAIL + error text") + attemptsHTML(at, "the task statement, the previous answer and these error lines go back to the model: fix it, keep the task's numbers")
        + `<div class="audit"><b>Note</b>PASS only means the official tool can parse it, not that the design is right.</div>`;
    case "repair": {
      const same = at.filter((a) => a.same_as_previous).length;
      return io("Model", "Repair from errors", "Task statement + previous answer + official error text (up to 8 lines)", "A new answer, parsed again")
        + `<div class="audit ${d.sysml_status === "PASS" ? "pass" : "fail"}"><b>Result</b>${Math.max(at.length - 1, 0)} repair round(s), last ${esc(d.sysml_status || "—")}.${same ? ` ${same} of them sent back code identical to the previous attempt.` : ""}</div>`
        + `<p class="hint" style="margin:8px 0">The exact sentence sent to the model: Official validation failed. Fix the model. Do not change numbers the task said to keep. (followed by the error text)</p>`
        + attemptsHTML(at, "sent back: task statement + previous answer + the error text above");
    }
    case "watts":
      return io("Code", "Read values", "Answer / official parse", "Names and values") + `<p>${esc(stepDetail(d, "Read values") || "—")}</p>`;
    case "check":
      return io("Code", "Check against key", "Official parse + answer key", "PASS / FAIL + reason") + `<div class="audit ${d.status === "PASS" ? "pass" : "fail"}"><b>${esc(d.status || "—")}</b>${esc(stepDetail(d, "Check against key"))}</div><p class="hint" style="margin-top:8px">The answer key text is at the bottom left.</p>`;
    case "gate":
      return io("Person", "Approval gate", "A request to change a limit", "Approve / reject") + `<p>${esc(stepDetail(d, "Approval gate"))}</p>`;
    case "archive":
      return io("Code", "Archive", "All records", "Score row + run folders") + `<p>${esc(stepDetail(d, "Archive"))}</p>${at.length ? `<p class="hint mono">${at.map((a) => esc(a.run_id || "")).join(" · ")}</p>` : ""}`;
    case "judge":
      return io("Observing · not scored", "Model judges", "Task statement + criteria + answer (not the tool's result)", "Pass / fail")
        + `<table><thead><tr><th>Judge</th><th>Verdict</th><th>Against the tool</th></tr></thead><tbody>
          <tr><td>Jev 1.13</td><td>${d.jev ? `pass probability ${esc(d.jev.p_pass)}` : "—"}</td><td>${d.jev ? badge(d.jev.agree ? "agrees" : d.jev.false_pass ? "false pass" : "false fail") : "—"}</td></tr>
          <tr><td>qwen3.8-max</td><td>${esc(d.qwen?.verdict ?? "—")}</td><td>${d.qwen ? badge(d.qwen.agree ? "agrees" : d.qwen.false_pass ? "false pass" : "false fail") : "—"}</td></tr></tbody></table>
          <div class="audit"><b>Note</b>The tool's task verdict is ${esc(d.status)}${d.engineering_status && d.engineering_status !== "UNKNOWN" ? `, design verdict ${esc(d.engineering_status)}` : ""}. The judges were told an over-budget design fails, so they are compared with the design verdict; only MOD-05 has different verdicts. Judges never change a score; they show whether a model could replace the tool.</div>`;
    default:
      return "";
  }
}

function judgeWord(d, judge) {
  const basis = d.status === "PASS" && d.engineering_status === "FAIL" ? "the tool's design verdict" : "the tool";
  return judge.agree ? `agrees with ${basis}` : judge.false_pass ? `false pass (vs ${basis})` : `false fail (vs ${basis})`;
}

const MODEL_OF = { flash: "qwen3.8-flash", opencode: "qwen3.8-flash", claude1: "qwen3.8-max", claude2: "qwen3.8-max" };

function usdOf(model, t, intl = false) {
  let price = ((S.facts && S.facts.costs && S.facts.costs.prices.models) || {})[model];
  if (!price || !t) return null;
  if (intl && price.intl) price = price.intl;
  const cached = t.cached || 0;
  return (Math.max((t.input || 0) - cached, 0) * price.input + cached * price.cache + (t.output || 0) * price.output) / 1e6;
}

const money = (usd) => (usd == null ? "—" : usd === 0 ? "$0" : usd < 0.01 ? `$${usd.toFixed(5)}` : `$${usd.toFixed(4)}`);

function sceneCtx(d, live) {
  const v = d.verdict || {};
  return { task: d.task_id, type: d.type, status: live ? null : d.status, sysml: d.sysml_status, live: !!live,
    repairs: Math.max((d.attempts || []).length - 1, 0), attempts: (d.attempts || []).length,
    design: (v.checks || []).length ? v.engineering_status : null, verdict: v, answer: d.answer };
}

function verdictBar(items) {
  return `<div class="vbar">${items.filter(Boolean).map(([label, value, tone, sub]) => `<div class="vb ${tone || ""}"><span>${esc(label)}</span><b>${esc(value)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</div>`).join("")}</div>`;
}

function designItem(sysml, v) {
  const check = (v.checks || [])[0];
  if (!check) return null;
  if (sysml !== "PASS") return ["Design verdict", "not judged", "", "the official syntax check failed first"];
  return ["Design verdict", v.engineering_status, v.engineering_status === "PASS" ? "pass" : "fail",
    `${check.total_w ?? "—"} W against a ${check.limit_w ?? "—"} W limit; the key expects ${check.expected}`];
}

const canonValue = (v) => (Array.isArray(v) ? v.map(canonValue).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)))
  : v && typeof v === "object" ? Object.fromEntries(Object.keys(v).sort().map((k) => [k, canonValue(v[k])])) : v);
const canon = (v) => JSON.stringify(canonValue(v));
const itemName = (m) => (typeof m === "string" ? m.split("::").pop() : m.qualified_name ? `${m.qualified_name.split("::").pop()} = ${m.actual ?? "—"} (should be ${m.expected})` : JSON.stringify(m));

function listCheck(sysml, v) {
  if (sysml !== "PASS") return ["Checklist", "not applied", "", "the official syntax check failed first"];
  const parts = [["part", v.must_exist], ["connection", v.must_connect], ["kept value", v.must_preserve]].filter(([, x]) => x && x.expected);
  const hit = parts.reduce((a, [, x]) => a + x.hit, 0);
  const total = parts.reduce((a, [, x]) => a + x.expected, 0);
  const miss = parts.flatMap(([n, x]) => (x.missing || []).map((m) => `${n} ${itemName(m)}`));
  const invented = (v.invented_numbers || []).length;
  return ["Checklist", `${hit}/${total} items`, miss.length || invented ? "fail" : "pass",
    miss.length ? `missing: ${miss.slice(0, 2).join("; ")}${miss.length > 2 ? " …" : ""}` : invented ? `${invented} number(s) not in the task` : "parts, connections and kept values all present"];
}

function alignCheck(sysml, v) {
  if (sysml !== "PASS") return ["Mappings", "not applied", "", "the official parse of sources + package failed first"];
  const map = v.must_map || {};
  const miss = (map.missing || []).map((m) => m.kind === "allocation" ? `${m.from} → ${m.to}` : `alias ${m.name} → ${m.target}`);
  const bad = ((v.must_not_map || {}).violations || []).map((m) => `alias ${m.name} → ${m.target}`);
  const stray = v.stray_declarations || [];
  const un = v.unmatched || {};
  const ok = !miss.length && !bad.length && !stray.length && !(un.missing || []).length;
  const why = miss.length ? `missing: ${miss.slice(0, 2).join("; ")}${miss.length > 2 ? " …" : ""}`
    : bad.length ? `look-alike pair declared: ${bad[0]}`
    : stray.length ? `declares its own elements: ${stray.slice(0, 2).join("; ")}`
    : (un.missing || []).length ? `unmatched not reported: ${un.missing.slice(0, 2).join("; ")}`
    : `precision ${v.precision ?? "—"} · recall ${v.recall ?? "—"} · unmatched reported ${un.hit ?? 0}/${un.expected ?? 0}`;
  return ["Mappings", `${map.hit ?? 0}/${map.expected ?? 0} pairs`, ok ? "pass" : "fail", why];
}

function answerCheck(type, v) {
  const short = (x) => trunc(typeof x === "string" ? x : JSON.stringify(x), 48);
  if (type === "QRY") {
    const exp = v.expected || {};
    const keys = Object.keys(exp);
    if (!v.actual || typeof v.actual !== "object") return ["Answer vs key", "no JSON found", "fail", v.reason ? trunc(v.reason, 80) : "the answer has no JSON to compare"];
    const bad = keys.filter((k) => canon(v.actual[k]) !== canon(exp[k]));
    const extra = Object.keys(v.actual).filter((k) => !(k in exp));
    const tail = (x) => String(x).split(/::|\./).pop();
    const why = (k) => {
      const want = exp[k];
      const got = v.actual[k];
      if (Array.isArray(want) && Array.isArray(got)) {
        const wrong = want.map((w) => [w, got.find((a) => a !== w && tail(a) === tail(w))]).find(([, a]) => a);
        if (wrong) return `${k}: wrote "${wrong[1]}", the key has "${wrong[0]}"`;
        return `${k}: ${want.filter((w) => got.includes(w)).length}/${want.length} items match`;
      }
      if (typeof want === "string" && typeof got === "string" && tail(want) === tail(got)) return `${k}: wrote "${got}", the key has "${want}"`;
      return `${k}: answered ${short(got)}; the key has ${short(want)}`;
    };
    return ["Answer vs key", `${keys.length - bad.length}/${keys.length} field${keys.length === 1 ? "" : "s"} match`, bad.length || extra.length ? "fail" : "pass",
      bad.length ? why(bad[0]) : extra.length ? `extra field ${extra[0]}` : "identical to the answer key"];
  }
  if (type === "AMB") {
    const missing = v.missing_questions || [];
    const parts = [["uses a question mark", !!v.asked], [`asks about the missing quantity${missing[0] ? ` (${missing[0][0]})` : ""}`, !missing.length], ["invents no number", !v.invented_number]];
    const ok = parts.filter(([, y]) => y).length;
    return ["Question checks", `${ok}/3 met`, ok === 3 ? "pass" : "fail", parts.map(([n, y]) => `${y ? "✓" : "✕"} ${n}`).join(" · ")];
  }
  if (type === "RT") {
    const miss = v.missing || [];
    return ["Phrases written back", `${v.hit ?? "—"}/${v.expected ?? "—"}`, miss.length ? "fail" : "pass",
      miss.length ? `missing ${miss.map((m) => `"${m}"`).join(", ")}` : "every required phrase is there"];
  }
  return null;
}

const VERDICT_RULE = {
  GEN: "official syntax and every checklist item must pass",
  MOD: "official syntax, checklist and kept values must all pass",
  ALN: "names resolve, every required pair declared, no look-alike pair, sources untouched, unmatched reported",
  QRY: "no model submitted: the JSON must equal the answer key",
  AMB: "no model submitted: all three question checks must hold",
  RT: "no model submitted: every required phrase must be written back",
};

function renderCell(d, live) {
  S.cell = d;
  S.cellLive = live;
  const at = d.attempts || [];
  const running = live && d.status === "RUNNING";
  const status = running ? "running" : d.status || "—";
  const cls = d.status === "PASS" ? "pass" : d.status === "FAIL" ? "fail" : "";
  const model = d.model || MODEL_OF[d.cohort_id] || "";
  const cost = d.usage && (d.usage.input || d.usage.output) ? usdOf(model, d.usage) : null;
  const alignTask = d.type === "ALN";
  const modelTask = d.type === "GEN" || d.type === "MOD" || alignTask;
  const v = d.verdict || {};
  const pending = ["Check", "—", "", "runs after the answer arrives"];
  $("#cell-head").innerHTML = `<div class="scene-wrap" id="cell-scene"></div>` + verdictBar([
    ["Task verdict", status, `big ${cls}`, d.archived_status && d.archived_status !== d.status ? `archived verdict ${d.archived_status}; re-scored with the current rule` : running ? "running" : VERDICT_RULE[d.type] || "every checklist item must match"],
    modelTask ? ["Official syntax", d.sysml_status || "—", d.sysml_status === "PASS" ? "pass" : d.sysml_status ? "fail" : "", `${at.length} parse(s)${at.length > 1 ? ` · ${at.length - 1} repair(s)` : ""}${alignTask ? " · sources + package together" : ""}`] : null,
    running && !Object.keys(v).length ? pending : alignTask ? alignCheck(d.sysml_status, v) : modelTask ? listCheck(d.sysml_status, v) : answerCheck(d.type, v),
    modelTask && !alignTask ? designItem(d.sysml_status, v) : null,
    ["Jev (not scored)", d.jev ? `pass probability ${d.jev.p_pass}` : "—", d.jev ? (d.jev.agree ? "pass" : "fail") : "", d.jev ? judgeWord(d, d.jev) : "no record"],
    ["qwen (not scored)", d.qwen ? d.qwen.verdict : "—", d.qwen ? (d.qwen.agree ? "pass" : "fail") : "", d.qwen ? judgeWord(d, d.qwen) : "no record"],
    ["This cell", `${d.task_id} · ${d.configuration || ""}${d.repeat ? ` · repeat ${d.repeat}` : ""}`, "", `${d.cohort || ""}${model ? ` · ${model}` : ""}${d.tokens ? ` · ${num(d.tokens)} tokens` : ""}${cost != null ? ` · ${money(cost)}` : ""}`],
  ]);
  if (window.SceneKit) SceneKit.render($("#cell-scene"), sceneCtx(d, live));
  const stages = benchStages(d, live);
  if (!stages.find((s) => s.id === S.cellStage)) {
    S.cellStage = (stages.find((s) => s.id === "repair") || stages.find((s) => s.state === "fail") || stages.find((s) => s.id === "write") || stages[0]).id;
  }
  stageList($("#cell-steps"), stages, S.cellStage, "cstage");
  $("#cell-detail").innerHTML = cellDetailHTML(d, S.cellStage);
  const last = at.length ? at[at.length - 1] : null;
  $("#cell-original").innerHTML = `<div class="stack"><div><div class="block-h">Task statement (everything the agent saw)</div><pre class="code light">${esc(d.requirements || "(no task statement)")}</pre></div>
      <div><div class="block-h">Answer key (hidden from the agent, opened only for scoring)</div><pre class="code light">${esc(d.gold || "(no answer key)")}</pre></div></div>
    <div class="stack"><div><div class="block-h">Agent's final answer</div><pre class="code">${esc(d.answer || last?.text || "(no answer yet)")}</pre></div>
      <div class="audit ${cls}"><b>Verdict: ${esc(status)}</b>${esc(stepDetail(d, "Check against key") || "")}${d.sysml_status ? ` Official syntax ${esc(d.sysml_status)}.` : ""}</div></div>`;
  FLOW.bench.setState(benchStates(d, live));
  FLOW.bench.setCtrl(`<span class="hint">The 1.1 diagram now shows: ${esc(d.task_id)} · ${esc(d.cohort || "")}${d.configuration ? ` · ${esc(d.configuration)}` : ""}${d.repeat ? ` repeat ${esc(d.repeat)}` : ""}${live ? " (running)" : " (archive)"}</span>${live ? "" : `<button type="button" id="bench-replay">Replay this cell step by step</button>`}<a href="#s14" class="hint">See the full process in 1.4 →</a>`);
  const rp = $("#bench-replay");
  if (rp) rp.onclick = () => FLOW.bench.replay(BENCH_ORDER, benchStates(d, false));
  $$("#matrix .cell.on").forEach((b) => b.classList.remove("on"));
  if (!live) { const on = $(`#matrix [data-cell="${CSS.escape(d.id)}"]`); if (on) on.classList.add("on"); }
}

async function loadCell(id, stage = "") {
  const d = await api(`/api/cell?id=${encodeURIComponent(id)}`);
  S.cellStage = stage;
  renderCell(d, false);
}

/* ======================= 1.5 console ======================= */
const EXAMPLES = {
  GEN: { type: "GEN", package: "Tug", req: "Package name: Tug\n\nWrite one SysML v2 package named Tug. Define part def Winch with attribute pullKN : Real = 20.0. Add a part usage tug that contains part winch : Winch. Do not add any other numbers.",
    gold: "task_id: INBOX\npackage: Tug\nmust_exist:\n- qualified_name: Tug::Winch\n- qualified_name: Tug::tug\n- qualified_name: Tug::tug::winch\nmust_connect: []\nmust_preserve:\n- qualified_name: Tug::Winch::pullKN\n  value: 20.0\n" },
  QRY: { type: "QRY", package: "Inbox", req: "Read this SysML v2 model and answer.\n\npackage Harbor {\n    part pilotBoat;\n    part tug;\n    part buoy;\n}\n\nHow many part usages are in package Harbor? Reply with one JSON object: {\"parts\": <number>}.",
    gold: "{\"parts\": 3}" },
  AMB: { type: "AMB", package: "Inbox", req: "A harbor drone streams video to the operator console. No bit rate and no latency figure are given. If a number needed for a check is missing, ask for it. Do not invent a value and do not write SysML.",
    gold: "task_id: INBOX\nshould_ask:\n- - bit rate\n  - bitrate\n  - mbps\n  - bandwidth\n- - latency\n  - delay\nmust_not_invent_number: true\n" },
};

function liveDetail(job) {
  const usage = { input: 0, cached: 0, output: 0 };
  for (const slot of Object.values((job.usage && job.usage.by_model) || {})) {
    usage.input += slot.prompt_tokens;
    usage.cached += slot.cached_tokens;
    usage.output += slot.completion_tokens;
  }
  return { id: job.id, task_id: job.task_id, type: job.type, configuration: job.configuration, repeat: "", cohort: "This run", status: job.status === "error" ? "ERROR" : job.status_label,
    sysml_status: job.sysml_status, steps: job.steps, requirements: job.requirements, answer: job.answer, gold: job.gold, outline: job.outline,
    retrieved: job.retrieved, attempts: job.attempts, phase: job.phase, jev: null, qwen: null, model: job.model, verdict: job.verdict || {},
    engineering_status: job.engineering_status, usage, tokens: usage.input + usage.output || null };
}

function miniSteps(host, steps, phase) {
  host.innerHTML = steps.map((s) => `<span class="${s.title === phase ? "run" : s.state === "wait" ? "" : s.state}">${esc(s.title)}</span>`).join("");
}

async function pollBench(id, statusEl, miniEl) {
  S.cellStage = "";
  for (;;) {
    let job;
    try { job = await api(`/api/job?id=${id}`); } catch (e) { statusEl.textContent = `Could not read progress: ${e.message}`; return; }
    miniSteps(miniEl, job.steps || [], job.phase);
    statusEl.textContent = job.status === "running" ? `${job.phase || "Working"}: ${job.phase_detail || ""}` : job.status === "done" ? `Finished: ${job.status_label}. 1.4 shows the full process of this run.` : `Error: ${job.error}`;
    renderCell(liveDetail(job), job.status === "running");
    if (job.status !== "running") break;
    await sleep(800);
  }
}

function setupConsole() {
  $("#run-task").innerHTML = TYPE_ORDER.map((t) => `<optgroup label="${t} · ${TYPE_NAME[t]}">${S.tasks.filter((x) => x.type === t).map((x) => `<option value="${x.id}">${x.id}</option>`).join("")}</optgroup>`).join("");
  $("#run-task").value = "GEN-03";
  $("#run-config").value = "P1";
  const note = () => { $("#run-config-note").textContent = CONFIG_NOTE[$("#run-config").value]; };
  $("#run-config").addEventListener("change", note);
  note();
  $("#run-go").addEventListener("click", async () => {
    const statusEl = $("#run-status");
    try {
      const { id } = await api("/api/run", { mode: "existing", task_id: $("#run-task").value, configuration: $("#run-config").value, model: $("#run-model").value });
      statusEl.textContent = "Started.";
      document.getElementById("s11").scrollIntoView({ behavior: "smooth", block: "start" });
      await pollBench(id, statusEl, $("#run-mini"));
    } catch (e) { statusEl.textContent = e.message; }
  });
  $$("#s15 [data-example]").forEach((b) => b.addEventListener("click", () => {
    const ex = EXAMPLES[b.dataset.example];
    $("#new-type").value = ex.type;
    $("#new-package").value = ex.package;
    $("#new-req").value = ex.req;
    $("#new-gold").value = ex.gold;
    $("#new-status").textContent = `Filled in the ${ex.type} example. Edit it if you like, then click "Create task and run".`;
  }));
  $("#new-go").addEventListener("click", async () => {
    const statusEl = $("#new-status");
    try {
      const { id } = await api("/api/run", { mode: "new", type: $("#new-type").value, package: $("#new-package").value, requirements: $("#new-req").value, gold: $("#new-gold").value, configuration: $("#new-config").value, model: $("#new-model").value });
      statusEl.textContent = "Started.";
      document.getElementById("s11").scrollIntoView({ behavior: "smooth", block: "start" });
      await pollBench(id, statusEl, $("#run-mini"));
    } catch (e) { statusEl.textContent = e.message; }
  });
}

function renderTrace() {
  const trace = S.facts.opencode.trace || [];
  $("#trace").innerHTML = trace.map((t, i) => `<div><b>${i + 1} · ${esc(t.tool)} · ${esc(t.status)}</b>${esc(trunc(t.target, 160))}</div>`).join("") || `<p class="hint">No tool-call record.</p>`;
}

/* ======================= 2.1 / 2.3 discovery run ======================= */
const APP_NODE = { brief: "brief", retrieve: "retrieve", requirements: "gen", source: "source", design: "gen", syntax: "syntax", repair: "repair", align: "align", simulate: "check", tradeoff: "tradeoff", readback: "check", gate: "human" };
const APP_ORDER = ["brief", "mem", "retrieve", "gen", "source", "syntax", "repair", "align", "check", "catalog", "tradeoff", "human"];
const RANK = { run: 5, fail: 4, await: 3, pass: 2, skip: 1 };
const merge = (a, b) => ((RANK[b] || 0) > (RANK[a] || 0) ? b : a);

function appStatesFromSteps(steps) {
  const st = {};
  for (const s of steps || []) {
    if (s.state === "wait") continue;
    const id = APP_NODE[s.key];
    st[id] = merge(st[id], s.state);
  }
  if (st.retrieve) st.mem = "pass";
  if (st.tradeoff) st.catalog = st.tradeoff === "skip" ? "skip" : "pass";
  if (st.human === "pass") st.human = "await";
  return st;
}

function appStatesFromRecord(r) {
  if (!r || !Array.isArray(r.designs)) return {};
  const ds = r.designs;
  const req = r.requirements || {};
  const al = r.alignment || {};
  const tr = r.tradeoffs || {};
  const fails = failingChecks(r);
  const rounds = ds.reduce((a, d) => a + (d.repair_rounds || 0), 0);
  const syntaxOk = ds.every((d) => d.sysml_status === "PASS");
  const feasible = (tr.proposals || []).filter((p) => p.feasible).length;
  return {
    mem: "pass", brief: "pass",
    retrieve: (r.retrieval?.nodes || []).length ? "pass" : "fail",
    gen: (req.requirements || []).length && ds.length ? "pass" : "fail",
    source: (req.unsourced || []).length ? "fail" : "pass",
    syntax: syntaxOk ? "pass" : "fail",
    repair: rounds ? (syntaxOk ? "pass" : "fail") : "skip",
    align: al.package ? (al.verified && al.package.sysml_status === "PASS" ? "pass" : "fail") : al.proposed ? "fail" : "skip",
    check: fails.length || !syntaxOk ? "fail" : "pass",
    catalog: (tr.proposals || []).length ? "pass" : "skip",
    tradeoff: (tr.proposals || []).length ? (feasible ? "pass" : "fail") : "skip",
    human: (r.approvals || []).length ? "pass" : (r.gate?.eligible || []).length ? "await" : "fail",
  };
}

function appNow(id) {
  const r = S.record;
  if (S.appJob && S.appJob.status === "running") {
    const keys = Object.entries(APP_NODE).filter(([, v]) => v === id).map(([k]) => k);
    const lines = (S.appJob.steps || []).filter((s) => keys.includes(s.key) && s.state !== "wait").map((s) => `${s.title}: ${s.detail}`);
    return esc(lines.join("\n")) || "Not reached yet.";
  }
  if (!r || !Array.isArray(r.designs)) return "No run recorded yet.";
  const ret = r.retrieval || {};
  const req = r.requirements || {};
  const al = r.alignment || {};
  const tr = r.tradeoffs || {};
  switch (id) {
    case "mem": return esc((ret.sources || []).map((s) => `${s.label}: ${s.cards} cards`).join("\n") || "—");
    case "brief": return esc(trunc(r.brief, 220));
    case "retrieve": return esc(`${(ret.nodes || []).length} matched: ${(ret.nodes || []).map((n) => `${n.short}${n.value != null ? `=${g(n.value)}` : ""}`).join(", ")}`);
    case "gen": return esc(`${(req.requirements || []).length} requirements, ${(req.questions || []).length} questions; wrote design ${r.designs.map((d) => d.key).join(", ")}.`);
    case "source": return esc((req.unsourced || []).length ? `Unknown origin: ${req.unsourced.map((u) => `${u.id} ${u.numbers.join(",")}`).join("; ")}` : "Every number in the requirements is in the brief.");
    case "syntax": return esc(r.designs.map((d) => `Design ${d.key}: ${d.sysml_status}, ${(d.attempts || []).length} parse(s)`).join("\n"));
    case "repair": return esc(r.designs.map((d) => `Design ${d.key}: ${d.repair_rounds || 0} repair round(s)`).join("\n"));
    case "align": return esc(al.proposed ? `${al.proposed} mappings proposed, ${al.verified} with both ends present; alignment package official Pilot ${al.package?.sysml_status || "not generated"}.` : al.note || al.error || "No alignment.");
    case "check": return esc(r.designs.map((d) => `Design ${d.key}: ${(d.checks || []).filter((c) => c.status !== "INFO").map((c) => `${c.id} ${c.status}`).join(" · ")}`).join("\n"));
    case "catalog": return "5 part slots, 3 parameters, 60 W fixed.";
    case "tradeoff": return esc((tr.proposals || []).length ? `${tr.proposals.length} proposals; ${(tr.proposals || []).filter((p) => p.feasible).length} feasible after code recomputes them.` : "All checks passed, or no proposals were generated.");
    case "human": return esc((r.approvals || []).length ? `Approved: ${r.approvals.map((a) => `design ${a.design}`).join(", ")}` : r.gate?.effect || "—");
    default: return "";
  }
}

function appStages(r) {
  const req = r.requirements || {};
  const ret = r.retrieval || {};
  const ds = r.designs || [];
  const al = r.alignment || {};
  const tr = r.tradeoffs || {};
  const gate = r.gate || {};
  const fails = failingChecks(r);
  const feasible = (tr.proposals || []).filter((p) => p.feasible).length;
  const out = [
    { id: "brief", node: "brief", title: "Task brief", state: "pass", sub: r.brief },
    { id: "retrieve", node: "retrieve", title: "① Retrieve from memory", state: (ret.nodes || []).length ? "pass" : "fail", sub: `${(ret.nodes || []).length} elements · ${Object.keys(ret.numbers || {}).length} values`, paper: "p2" },
    { id: "requirements", node: "gen", title: "② Write requirements", state: (req.requirements || []).length ? "pass" : "fail", sub: `${(req.requirements || []).length} requirements · ${(req.questions || []).length} questions`, paper: "p3" },
    { id: "source", node: "source", title: "Number source check", state: (req.unsourced || []).length ? "fail" : "pass", sub: (req.unsourced || []).length ? `${req.unsourced.length} carry numbers not in the brief` : "every number is in the brief" },
  ];
  for (const d of ds) {
    out.push({ id: `design-${d.key}`, node: "gen", title: `② Write design ${d.key}`, state: d.source ? "pass" : "fail", sub: "prompt = rules + template + examples + brief", paper: "p3" });
    out.push({ id: `syntax-${d.key}`, node: (d.attempts || []).length > 1 ? "repair" : "syntax", title: `③ Official validation ${d.key}`, state: d.sysml_status === "PASS" ? "pass" : "fail", sub: `${(d.attempts || []).length} parse(s) · ${d.repair_rounds || 0} repair(s)`, paper: "ours" });
  }
  out.push({ id: "align", node: "align", title: "④ Align with MaritimeISR", state: al.package ? (al.verified && al.package.sysml_status === "PASS" ? "pass" : "fail") : al.proposed ? "fail" : "skip", sub: al.proposed ? `${al.verified}/${al.proposed} mappings · package ${al.package?.sysml_status || "—"}` : "skipped", paper: "p1" });
  out.push({ id: "simulate", node: "check", title: "⑤ Budget checks", state: fails.length ? "fail" : "pass", sub: fails.length ? `failing: ${fails.join(", ")}` : "all four pass" });
  out.push({ id: "tradeoff", node: "tradeoff", title: "Trade-offs", state: (tr.proposals || []).length ? (feasible ? "pass" : "fail") : "skip", sub: (tr.proposals || []).length ? `${tr.proposals.length} proposals · ${feasible} feasible` : "not needed" });
  out.push({ id: "readback", node: "check", title: "⑤ Read back", state: ds.some((d) => d.read_back) ? "pass" : "skip", sub: "the model restates requirements from its own model", paper: "p3" });
  out.push({ id: "gate", node: "human", title: "⑥ Person decides · memory", state: (r.approvals || []).length ? "pass" : (gate.eligible || []).length ? "await" : "fail", sub: (r.approvals || []).length ? "approved into memory" : (gate.eligible || []).length ? `can approve: design ${gate.eligible.join(", ")}` : "neither design can go into memory" });
  return out;
}

function retrievalGraph(ret) {
  const nodes = ret.nodes || [];
  const seeds = nodes.filter((n) => n.role === "seed");
  const nb = nodes.filter((n) => n.role !== "seed");
  if (!nodes.length) return `<p class="hint">No matches.</p>`;
  const rows = Math.max(seeds.length, nb.length, 2);
  const W = 860;
  const H = rows * 50 + 46;
  const bw = 250;
  const bh = 36;
  const qx = 16;
  const sx = 270;
  const nx = 590;
  const ys = (i, n) => 34 + ((H - 44) * (i + 0.5)) / n - bh / 2;
  const pos = {};
  seeds.forEach((n, i) => { pos[n.id] = { x: sx, y: ys(i, seeds.length) }; });
  nb.forEach((n, i) => { pos[n.id] = { x: nx, y: ys(i, nb.length) }; });
  const color = (n) => (n.source === "MaritimeISR" ? "#4ea3f0" : "#63c890");
  const label = (n) => trunc(`${n.short}${n.value != null ? ` = ${g(n.value)}` : n.ends ? ` (${n.ends.join(" → ")})` : ""}`, 34);
  const qy = H / 2;
  let out = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Retrieval result">`;
  out += `<text x="${sx}" y="18" fill="#9fc0d0" font-size="12" font-weight="700">Seeds: top ${seeds.length} cards</text><text x="${nx}" y="18" fill="#9fc0d0" font-size="12" font-weight="700">One-hop neighbours: ${nb.length}</text>`;
  out += `<rect x="${qx}" y="${qy - 32}" width="200" height="64" rx="10" fill="#14304a" stroke="#6cc7c9"/><text x="${qx + 12}" y="${qy - 8}" fill="#e6f2f6" font-size="13" font-weight="700">Words in the brief</text><text x="${qx + 12}" y="${qy + 12}" fill="#a9c3cf" font-size="11">${(ret.query_words || []).length} words, ${(ret.words || []).length} found in cards</text>`;
  seeds.forEach((n) => {
    const p = pos[n.id];
    const y = p.y + bh / 2;
    out += `<path d="M${qx + 200} ${qy} C ${qx + 240} ${qy}, ${sx - 40} ${y}, ${sx} ${y}" fill="none" stroke="#6cc7c9" stroke-width="1.6"/><text x="${sx - 40}" y="${y - 6}" fill="#9fe0dc" font-size="10.5">${n.score} hits</text>`;
  });
  for (const e of ret.edges || []) {
    const a = pos[e.from];
    const b = pos[e.to];
    if (!a || !b) continue;
    out += `<path d="M${a.x + bw} ${a.y + bh / 2} C ${a.x + bw + 40} ${a.y + bh / 2}, ${b.x - 40} ${b.y + bh / 2}, ${b.x} ${b.y + bh / 2}" fill="none" stroke="#d4b46a" stroke-dasharray="4 4" stroke-width="1.6"/><text x="${b.x - 34}" y="${b.y + bh / 2 - 6}" fill="#ecd9a3" font-size="10.5">${e.kind === "connect" ? "connects" : "owns"}</text>`;
  }
  for (const n of nodes) {
    const p = pos[n.id];
    out += `<rect x="${p.x}" y="${p.y}" width="${bw}" height="${bh}" rx="8" fill="#183a4a" stroke="${color(n)}" stroke-width="1.6"/><text x="${p.x + 10}" y="${p.y + 15}" fill="#e6f2f6" font-size="12" font-weight="700">${esc(label(n))}</text><text x="${p.x + 10}" y="${p.y + 29}" fill="#a9c3cf" font-size="10">${esc(n.type)} · ${n.source === "MaritimeISR" ? "MaritimeISR" : "approved design"}</text>`;
  }
  if (!nb.length) out += `<text x="${nx}" y="${H / 2}" fill="#a9c3cf" font-size="12">the seeds' neighbours are not cards, or are already seeds</text>`;
  return `${out}</svg>`;
}

function structureHTML(d) {
  const nums = d.numbers || {};
  const prefix = `Design${d.key}::`;
  const groups = {};
  for (const [q, v] of Object.entries(nums)) {
    const segs = q.replace(prefix, "").split("::");
    const attr = segs.pop();
    const path = segs.join("::") || "(package)";
    (groups[path] ||= []).push([attr, v]);
  }
  const tops = Object.keys(groups).filter((p) => !p.includes("::"));
  const devices = Object.keys(groups).filter((p) => p.includes("::"));
  if (!tops.length && !devices.length) return `<p class="hint">No attributes with values in the official parse.</p>`;
  const chips = (list) => list.map(([a, v]) => `<span class="qchip">${esc(a)} = ${esc(g(v))}</span>`).join("");
  return `<div class="struct">${(tops.length ? tops : ["(package)"]).map((t) => `<div class="vessel"><b>part ${esc(t)}</b><div class="attrs">${chips(groups[t] || [])}</div>
      <div class="devs">${devices.filter((p) => p.startsWith(`${t}::`) || !tops.length).map((p) => `<div class="dev"><b>${esc(p.split("::").slice(1).join("::") || p)}</b>${chips(groups[p])}</div>`).join("")}</div></div>`).join("")}
    ${(d.connections || []).length ? `<div class="conn">${d.connections.length} connections: ${d.connections.map((c) => esc(`${c[0]} → ${c[1]}`)).join(" · ")}</div>` : `<div class="conn">No connections in the official parse.</div>`}</div>`;
}

function promptComposer(parts) {
  const colors = { rules: "#f6d67a", contract: "#fbe7a9", examples: "#a9cdf3", task: "#dfe6eb", variant: "#eef2f5" };
  const total = parts.reduce((a, p) => a + (p.text || "").length, 0) || 1;
  const barHTML = parts.map((p) => `<span style="flex:${Math.max((p.text || "").length / total, 0.06)};background:${colors[p.key] || "#eee"}" title="${esc(p.label)} · ${(p.text || "").length} characters">${esc(p.label)}</span>`).join("");
  const rows = parts.map((p) => {
    const text = p.text || "";
    const lines = text.split("\n");
    const shown = p.key === "rules" ? `${lines.slice(0, 4).join("\n")}\n… (${lines.length} lines, ${text.length} characters in all)` : text;
    return `<div class="block-h" style="margin-top:8px">${esc(p.label)} ${ptag(p.paper)} · ${text.length} characters</div><pre class="code light">${esc(shown)}</pre>`;
  }).join("");
  return `<div class="composer">${barHTML}</div>${rows}`;
}

function checksHTML(d) {
  const list = (d.checks || []).filter((c) => c.status !== "INFO");
  return list.map((c) => {
    const known = c.actual != null && c.limit != null;
    const scale = known ? Math.max(c.actual, c.limit) * 1.15 || 1 : 1;
    return `<div class="check-row ${c.status}"><div><b>${esc(c.id)} · ${esc(c.label)}</b><small>${esc(c.formula || "")}</small>${known ? `<div class="meter ${c.status}" style="margin-top:6px"><div class="track"><div class="fill" style="width:${(Math.min(c.actual, c.limit) / scale) * 100}%"></div>${c.actual > c.limit ? `<div class="over" style="left:${(c.limit / scale) * 100}%;width:${((c.actual - c.limit) / scale) * 100}%"></div>` : ""}<div class="lim" style="left:calc(${(c.limit / scale) * 100}% - 1px)"></div></div></div>` : `<small>${esc(c.detail || "")}</small>`}</div>
      <div style="text-align:right">${badge(c.status)}<div class="hint">${known ? `${esc(g(c.actual))} / ${esc(g(c.limit))} ${esc(c.unit)}` : ""}</div></div></div>`;
  }).join("") + ((d.checks || []).find((c) => c.id === "CONNECT") ? `<p class="hint">${(d.checks || []).find((c) => c.id === "CONNECT").actual} connections (recorded, not judged).</p>` : "");
}

function runDetailHTML(r, id) {
  const io = (who, title, read, give) => `<div class="who">${esc(who)}</div><h4 class="dt">${esc(title)}</h4><div class="io"><div><h5>Reads</h5><p>${esc(read)}</p></div><div><h5>Produces</h5><p>${esc(give)}</p></div></div>`;
  const ret = r.retrieval || {};
  const req = r.requirements || {};
  const ds = r.designs || [];
  const al = r.alignment || {};
  const tr = r.tradeoffs || {};
  if (id === "brief") {
    const nums = numbersIn(r.brief);
    return io("Person · 2.2", "Task brief", "The choices in 2.2, or your edited text", "This text goes verbatim into every later prompt") + `<pre class="code light">${esc(r.brief)}</pre>`
      + `<div class="block-h" style="margin-top:10px">Numbers in the brief (the number source check accepts only these)</div><div class="words">${nums.map((n) => `<span class="hit">${esc(n)}</span>`).join("")}</div>`;
  }
  if (id === "retrieve") {
    const hits = new Set(ret.words || []);
    return io("Code · Paper 2", "① Retrieve from memory", "Words in the brief + memory cards", "Matched cards, verbatim, as the \"examples\" part of the design prompt")
      + `<div class="block-h">Memory = these sources (${esc(ret.library_size ?? "—")} cards in all)</div><div class="chips" style="margin-bottom:10px">${(ret.sources || []).map((s) => `<span class="chip">${esc(s.label)} · ${esc(s.cards)} cards · <span class="mono">${esc(s.path)}</span></span>`).join("")}</div>`
      + `<div class="block-h">Query words and numbers (blue = found in at least one card)</div><div class="words" style="margin-bottom:10px">${(ret.query_words || []).map((w) => `<span class="${hits.has(w) ? "hit" : ""}">${esc(w)}</span>`).join("")}</div>`
      + `<div class="rgraph">${retrievalGraph(ret)}</div>`
      + `<table style="margin-top:10px"><thead><tr><th>Role</th><th>Card (text that enters the prompt)</th><th class="num">Score</th><th>Source</th></tr></thead><tbody>${(ret.nodes || []).map((n) => `<tr><td>${n.role === "seed" ? "seed" : "neighbour"}</td><td class="mono" style="font-size:11.5px">${esc(n.text)}</td><td class="num">${esc(n.score)}</td><td>${esc(n.source)}</td></tr>`).join("")}</tbody></table>`
      + `<div class="audit"><b>Note</b>${esc(ret.note || "")} Score = query words found in the card + values equal to a number in the brief. No vectors; this step calls no model.</div>`;
  }
  if (id === "requirements") {
    return io("Model · Paper 3", "② Write requirements", "The brief", "Numbered requirements (attribute name and value) + questions")
      + `<table class="req-table"><thead><tr><th>ID</th><th>Requirement</th><th>Attribute = value</th><th>Number source</th></tr></thead><tbody>${(req.requirements || []).map((q) => `<tr><td>${esc(q.id)}</td><td>${esc(q.text)}</td><td>${q.quantity ? `<span class="qchip">${esc(q.quantity.name)} = ${esc(g(q.quantity.value))} ${esc(q.quantity.unit || "")}</span>` : "—"}</td><td>${(q.unsourced_numbers || []).length ? badge(`unknown origin ${q.unsourced_numbers.join(",")}`) : badge("in brief")}</td></tr>`).join("")}</tbody></table>`
      + ((req.questions || []).length ? `<div class="block-h" style="margin-top:10px">The model's questions</div><ul>${req.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : `<p class="hint" style="margin-top:8px">The model asked no questions.</p>`);
  }
  if (id === "source") {
    const un = req.unsourced || [];
    return io("Code", "Number source check", "Numbers in each requirement + numbers in the brief", "Numbers of unknown origin")
      + `<div class="audit ${un.length ? "fail" : "pass"}"><b>${un.length ? "Numbers of unknown origin" : "Pass"}</b>${un.length ? esc(un.map((u) => `${u.id}: ${u.numbers.join(", ")}`).join("; ")) + ". This run cannot go into memory until a person supplies them." : "Every number in the requirements appears in the brief."}</div>`
      + `<div class="block-h" style="margin-top:10px">Numbers in the brief</div><div class="words">${numbersIn(r.brief).map((n) => `<span class="hit">${esc(n)}</span>`).join("")}</div>`;
  }
  const dm = /^(design|syntax)-(\w+)$/.exec(id);
  if (dm) {
    const d = ds.find((x) => x.key === dm[2]);
    if (!d) return "<p class='hint'>No such design.</p>";
    if (dm[1] === "design") {
      return io("Model · Paper 3", `② Write design ${d.key}`, "Rules + template + examples + brief and requirements (each part's text below)", "A SysML package")
        + `<div class="block-h">The prompt has 5 parts (width = length)</div>${promptComposer(d.prompt_parts || [])}`
        + `<div class="block-h" style="margin-top:12px">The submitted model: structure from the official parse</div>${d.sysml_status === "PASS" ? structureHTML(d) : `<p class="hint">The parse failed, so there is no structure. See the code under "③ Official validation ${esc(d.key)}".</p>`}`
        + `<p class="hint" style="margin-top:6px">${esc(d.model || "")}${d.usage?.total_tokens ? ` · ${num(d.usage.total_tokens)} tokens` : ""}</p>`;
    }
    return io("Official tool", `③ Official validation ${d.key}`, "Design SysML", "PASS / FAIL + error text; a FAIL goes to repair")
      + attemptsHTML((d.attempts || []).map((a, i, all) => ({ ...a, text: a.text || (i === all.length - 1 ? d.source : "(this run did not keep intermediate versions; see the errors)") })), "the original prompt, the last version and the error text above go back to the model: fix syntax only, keep the numbers")
      + `<div class="audit"><b>Note</b>PASS only means the official tool can parse it. Whether the design is right is decided at "⑤ Budget checks".</div>`;
  }
  if (id === "align") {
    const pkg = al.package || {};
    const old = al.proposed && !("declared" in al);
    const construct = (m) => m.construct ? `<span class="badge ${m.construct === "alias" ? "ok" : "info"}">${esc(m.construct)}</span>` : m.ok ? `<span class="badge warn">refused</span>` : `<span class="badge bad">name missing</span>`;
    const review = (m) => {
      if (!m.ok) return `<span class="hint">—</span>`;
      if (m.review) return `<span class="badge ${m.review.decision === "accept" ? "ok" : "bad"}">${esc(m.review.decision)}ed</span><span class="hint"> ${esc((m.review.reviewed_at || "").slice(0, 16))}</span>`;
      return `<button type="button" class="mini" data-review="${m.index ?? ""}" data-decision="accept">Accept</button> <button type="button" class="mini" data-review="${m.index ?? ""}" data-decision="reject">Reject</button>`;
    };
    const rows = (al.mappings || []).map((m) => `<tr><td><span class="mono" style="font-size:11.5px">${esc(m.design)}</span><div class="hint">↔ <span class="mono">${esc(m.existing)}</span></div><div class="hint">${esc(m.reason)}</div></td><td>${badge(m.ok ? "PASS" : "FAIL")}</td><td>${construct(m)}${m.refused ? `<div class="hint">${esc(m.refused)}</div>` : m.statement ? `<div class="hint mono">${esc(m.statement)}</div>` : ""}${m.level ? `<div class="hint">${esc(m.level)}</div>` : ""}</td><td>${review(m)}</td></tr>`).join("");
    const accepted = (al.mappings || []).filter((m) => m.review?.decision === "accept").length;
    const rejected = (al.mappings || []).filter((m) => m.review?.decision === "reject").length;
    return io("Model proposes · code checks and writes · official tool · person reviews · Paper 1", "④ Align with MaritimeISR", `Design A element names (${(ds[0]?.elements || []).length}) + retrieved MaritimeISR element names (${(al.existing_names || []).length})`, "Mapping table, a separate alignment package, a per-pair review")
      + (al.proposed ? `<div class="tbl-scroll"><table class="align-table"><thead><tr><th>Design A element ↔ MaritimeISR element, with the model's reason</th><th>Both ends exist</th><th>Construct (decided by code from the two parses)</th><th>Person</th></tr></thead><tbody>${rows}</tbody></table></div>
         <p class="hint">${old ? "This run predates the alias / allocation package (it used dependency statements); pairs can still be reviewed." : `alias = a definition or a definition's feature; allocation = a usage reached through usages. A part usage against a part definition is not declared (typing it is a design decision) and a category mismatch is refused: ${(al.refused || []).length} pair(s) left undeclared.`} Reviewed: ${accepted} accepted, ${rejected} rejected. Reviews are appended to analysis/memory/alignment-reviews.jsonl and cannot be undone from the page.</p>` : `<p class="hint">${esc(al.note || al.error || "No alignment.")}</p>`)
      + (pkg.source ? `<div class="two-col" style="margin-top:12px"><div><div class="block-h">Alignment package (${old ? "written by the agent" : "written by code from the verified pairs"}, a separate file)</div><pre class="code">${esc(pkg.source)}</pre></div>
          <div><div class="block-h">The official Pilot parses these three files together</div><div class="chips" style="margin-bottom:8px">${(pkg.files || []).map((f) => `<span class="chip">${esc(f)}</span>`).join("")}</div>
          <div class="audit ${pkg.sysml_status === "PASS" ? "pass" : "fail"}"><b>Official Pilot ${esc(pkg.sysml_status)}</b>${pkg.sysml_status === "PASS" ? "Every name in the alignment package resolves in the two source models." : esc((pkg.diagnostics || []).map((x) => x.message).join("; "))}</div><p class="hint mono" style="margin-top:6px">${esc(pkg.run_id || "")}</p></div></div>` : "")
      + `<div class="audit"><b>Limits</b>Neither source model was edited. A Pilot pass shows the names resolve, not that the two sides mean the same thing; that is what the Accept / Reject column records.</div>`;
  }
  if (id === "simulate") {
    return io("Code", "⑤ Budget checks", "Officially parsed numbers + requirements", "Four checks (same formulas as the three tables in 2.2)")
      + `<div class="two-col">${ds.map((d) => `<div><div class="block-h">Design ${esc(d.key)}</div>${checksHTML(d)}</div>`).join("")}</div>`
      + `<div class="audit"><b>Note</b>The checks read only officially parsed numbers. Numbers the model states in prose do not count.</div>`;
  }
  if (id === "tradeoff") {
    const ps = tr.proposals || [];
    if (!ps.length) return io("Model · code recomputes", "Trade-offs", "Brief + failing checks + parts catalog", "3 proposals") + `<p class="hint">${esc(tr.error || "All checks pass; no trade-off needed.")}</p>`;
    return io("Model · code recomputes", "Trade-offs", "Brief + failing checks + parts catalog", "3 proposals; code recomputes them from the catalog and ignores the model's numbers")
      + `<div class="proposals">${ps.map((p, i) => {
        const b = p.budgets || {};
        const c = p.choice || {};
        const label = (slot) => S.catalog?.slots?.[slot]?.options?.[c[slot]]?.label || c[slot] || "—";
        return `<div class="proposal ${p.feasible ? "ok" : "bad"}"><h5>${esc(p.title)}</h5><p>${esc(p.rationale)}</p>
          <p class="hint">visible ${esc(label("visible_camera"))} · infrared ${esc(label("ir_camera"))} · computer ${esc(label("computer"))} · uplink ${esc(label("uplink"))} · storage ${esc(label("storage"))} · record ${esc(c.dataRateMbps)} Mbps · keep ${esc(c.retentionHours)} h · upload ${esc(c.uploadMbps)} Mbps</p>
          ${p.valid ? `<div class="mini"><span class="${b.power?.status}">power ${esc(g(b.power?.actual))}/${esc(g(b.power?.limit))} W</span><span class="${b.link?.status}">upload ${esc(g(b.link?.actual))}/${esc(g(b.link?.limit))}</span><span class="${b.store?.status}">storage ${esc(g(b.store?.actual))}/${esc(g(b.store?.limit))} GB</span></div>` : `<p class="hint" style="color:var(--fail)">Uses an option outside the catalog; discarded.</p>`}
          ${p.valid ? `<button type="button" class="${p.feasible ? "cta" : ""}" data-adopt="${i}">Send back to the 2.2 design space</button>` : ""}</div>`;
      }).join("")}</div><p class="hint" style="margin-top:8px">Sending back only changes the choices in 2.2; nothing runs automatically. Review it in 2.2, then give it to the agent.</p>`;
  }
  if (id === "readback") {
    return io("Model · Paper 3's query use", "⑤ Read back", "Only the SysML the model wrote", "Sentences restating the requirements; code checks every brief number")
      + `<div class="two-col">${ds.map((d) => `<div><div class="block-h">Design ${esc(d.key)}</div>${d.read_back ? `<pre class="code light">${esc(d.read_back)}</pre><div class="words" style="margin-top:6px">${Object.entries(d.read_back_numbers || {}).map(([n, ok]) => `<span class="${ok ? "hit" : ""}" title="${ok ? "in the read-back" : "not in the read-back"}">${esc(n)} ${ok ? "✓" : "✕"}</span>`).join("")}</div>` : `<p class="hint">The parse failed, so there is no read-back.</p>`}</div>`).join("")}</div>`;
  }
  if (id === "gate") {
    const approvals = r.approvals || [];
    const reasons = Object.fromEntries(ds.map((d) => [d.key, blockReason(r, d)]));
    return io("Person", "⑥ Person decides · memory", "Checks, read-back, alignment", "Approve or not; approved designs join memory")
      + `<div class="audit ${(r.gate?.eligible || []).length ? "pass" : "fail"}"><b>The script's conclusion</b>${esc(r.gate?.effect || "")}</div>`
      + `<div class="approve-row" style="margin-top:10px">${ds.map((d) => {
        const done = approvals.find((a) => a.design === d.key);
        const why = reasons[d.key];
        return `<div class="approve-card ${!why ? "ok" : ""}"><b>Design ${esc(d.key)}</b><div>${(d.checks || []).filter((c) => ["POWER", "LINK", "STORE", "TRACE"].includes(c.id)).map((c) => `${badge(`${c.id} ${c.status}`)}`).join(" ")}</div>
          ${done ? `<div class="audit pass"><b>In memory</b>${esc(done.approved_at)}. The next ① Retrieve will find it.</div>` : why ? `<p class="why">Cannot approve: ${esc(why)}</p><button type="button" disabled>Approve design ${esc(d.key)} into memory</button>` : `<button type="button" class="cta" data-approve="${esc(d.key)}">Approve design ${esc(d.key)} into memory</button><p class="hint">Approval writes analysis/memory/approved.jsonl and cannot be undone from the page.</p>`}</div>`;
      }).join("")}</div>`
      + `<div class="block-h" style="margin-top:12px">Approved designs in memory (${S.memory.length})</div><div class="memlist">${S.memory.length ? S.memory.map((m) => `<div>${esc(m.run_id)} · design ${esc(m.design)} · ${esc(m.approved_at)}</div>`).join("") : "None yet."}</div>`;
  }
  return "";
}

function blockReason(r, d) {
  if ((r.requirements?.unsourced || []).length) return "The requirements contain numbers that are not in the brief.";
  if (d.sysml_status !== "PASS") return "The official parse failed.";
  const by = Object.fromEntries((d.checks || []).map((c) => [c.id, c]));
  for (const key of ["POWER", "LINK", "STORE", "TRACE"]) {
    const c = by[key];
    if (!c || c.status !== "PASS") return `The ${key} check did not pass (${c?.status || "missing"}).`;
  }
  return "";
}

function runCost(r) {
  if (r.usage && r.usage.by_model) {
    let usd = 0;
    let tokens = 0;
    for (const [model, s] of Object.entries(r.usage.by_model)) {
      const t = { input: s.prompt_tokens, cached: s.cached_tokens, output: s.completion_tokens };
      usd += usdOf(model in ((S.facts.costs || {}).prices || { models: {} }).models ? model : "qwen3.8-max", t) || 0;
      tokens += t.input + t.output;
    }
    return { usd, tokens, complete: true };
  }
  const t = { input: 0, cached: 0, output: 0 };
  for (const u of [r.requirements && r.requirements.usage, ...(r.designs || []).map((d) => d.usage), r.tradeoffs && r.tradeoffs.usage]) {
    if (!u) continue;
    t.input += u.prompt_tokens || 0;
    t.output += u.completion_tokens || 0;
    t.cached += (u.prompt_tokens_details || {}).cached_tokens || 0;
  }
  return { usd: usdOf("qwen3.8-max", t), tokens: t.input + t.output, complete: false };
}

function renderRun() {
  const r = S.record;
  if (!r || !Array.isArray(r.designs)) {
    $("#run-head").innerHTML = `<div class="audit">No run in the current format yet. Click "Give to the agent" in 2.2.</div>`;
    $("#run-steps").innerHTML = "";
    $("#run-detail").innerHTML = "";
    FLOW.app.setState({});
    return;
  }
  const fails = failingChecks(r);
  const al = r.alignment || {};
  const chips = [
    [`${(r.requirements?.requirements || []).length} requirements`, (r.requirements?.unsourced || []).length ? "no" : "yes"],
    ...r.designs.map((d) => [`Design ${d.key}: official validation ${d.sysml_status} · ${(d.attempts || []).length} parse(s)`, d.sysml_status === "PASS" ? "yes" : "no"]),
    [al.proposed ? `Alignment ${al.verified}/${al.proposed} · package ${al.package?.sysml_status || "—"}` : "Alignment: skipped", al.package?.sysml_status === "PASS" ? "yes" : "no"],
    [fails.length ? `Failing checks: ${fails.join(", ")}` : "All four budget checks pass", fails.length ? "no" : "yes"],
    [(r.approvals || []).length ? `In memory: design ${r.approvals.map((a) => a.design).join(", ")}` : (r.gate?.eligible || []).length ? `Can approve: design ${r.gate.eligible.join(", ")}` : "Cannot go into memory", (r.approvals || []).length || (r.gate?.eligible || []).length ? "yes" : "no"],
  ];
  const cost = runCost(r);
  if (cost.tokens) chips.push([`${num(cost.tokens)} tokens ≈ ${money(cost.usd)}${cost.complete ? "" : " (alignment and read-back not recorded)"}`, ""]);
  $("#run-head").innerHTML = `<div class="audit" style="margin:0 0 4px"><b>Run ${esc(r.id)}</b>${esc(trunc(r.brief, 200))}</div><div class="chips" style="margin:8px 0 0">${chips.map(([t, c]) => `<span class="chip ${c}">${esc(t)}</span>`).join("")}</div>`;
  const stages = appStages(r);
  if (!stages.find((s) => s.id === S.runStage)) S.runStage = (stages.find((s) => s.id === "gate" && s.state === "await") || stages.find((s) => s.state === "fail") || stages[1]).id;
  stageList($("#run-steps"), stages, S.runStage, "rstage");
  $("#run-detail").innerHTML = runDetailHTML(r, S.runStage);
  FLOW.app.setState(appStatesFromRecord(r));
  FLOW.app.setCtrl(`<span class="hint">The 2.1 diagram now shows run ${esc(r.id)} (archive)</span><button type="button" id="app-replay">Replay this run step by step</button><a href="#s23" class="hint">See every step in 2.3 →</a>`);
  $("#app-replay").onclick = () => FLOW.app.replay(APP_ORDER, appStatesFromRecord(r));
}

function renderRunLive(job) {
  const steps = job.steps || [];
  $("#run-head").innerHTML = `<div class="audit" style="margin:0"><b>Running</b>${esc(trunc(job.brief, 200))}</div>`;
  const cur = steps.find((s) => s.state === "run") || [...steps].reverse().find((s) => s.state !== "wait") || steps[0];
  stageList($("#run-steps"), steps.map((s) => ({ id: s.key, title: s.title, state: s.state === "wait" ? "" : s.state, sub: s.detail })), cur?.key, "rstage-live");
  $("#run-detail").innerHTML = `<div class="who">Progress</div><h4 class="dt">${esc(cur?.title || "")}</h4><p>${esc(cur?.detail || "")}</p><p class="hint" style="margin-top:10px">When it finishes, this becomes the full record: every step's input, output and checks.</p>`;
  FLOW.app.setState(appStatesFromSteps(steps));
  FLOW.app.setCtrl(`<span class="hint">The 2.1 diagram is following this run.</span>`);
}

function jumpToRunStage(nodeId) {
  if (!S.record || !Array.isArray(S.record.designs)) return;
  const target = { mem: "retrieve", catalog: "tradeoff", repair: "syntax-A" }[nodeId];
  const stages = appStages(S.record);
  const hit = target ? stages.find((s) => s.id === target) : stages.find((s) => s.node === nodeId);
  if (!hit) return;
  S.runStage = hit.id;
  renderRun();
  document.getElementById("s23").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function startDiscover() {
  const statusEl = $("#discover-status");
  const brief = $("#brief").value.trim();
  try {
    const { id } = await api("/api/discover", { brief });
    statusEl.textContent = "Started. The 2.1 diagram will follow along.";
    document.getElementById("s21").scrollIntoView({ behavior: "smooth", block: "start" });
    for (;;) {
      const job = await api(`/api/job?id=${id}`);
      S.appJob = job;
      if (job.status === "running") {
        renderRunLive(job);
        const cur = (job.steps || []).find((s) => s.state === "run");
        statusEl.textContent = cur ? `${cur.title}: ${cur.detail}` : "Working.";
        await sleep(900);
        continue;
      }
      S.appJob = null;
      if (job.status === "done" && job.record) {
        S.record = txDeep(job.record);
        S.runStage = "";
        statusEl.textContent = `Finished: run ${job.record.id}. Results are in 2.3.`;
        renderRun();
        renderPapers();
        renderAnswers();
        renderCaps();
      } else {
        statusEl.textContent = `Error: ${job.error || "unknown"}`;
        renderRunLive(job);
      }
      break;
    }
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

async function approveDesign(key) {
  const r = S.record;
  try {
    const out = await api("/api/approve", { run_id: r.id, design: key });
    S.record = txDeep(out.record);
    S.memory = out.memory;
    S.runStage = "gate";
    renderRun();
    renderHeader();
    renderSources();
    renderAnswers();
    renderCaps();
  } catch (e) {
    alert(`Not approved: ${e.message}`);
  }
}

async function reviewMapping(index, decision) {
  const r = S.record;
  try {
    const out = await api("/api/review-mapping", { run_id: r.id, index: Number(index), decision });
    S.record = txDeep(out.record);
    S.runStage = "align";
    renderRun();
  } catch (e) {
    alert(`Not recorded: ${e.message}`);
  }
}

/* ======================= 2.2 design space ======================= */
const SLOT_FOCUS = { visible_camera: "sensors", ir_camera: "sensors", computer: "processor", uplink: "router", storage: "storage", dataRateMbps: "storage", retentionHours: "storage", uploadMbps: "router" };
const SLOT_ATTR = { visible_camera: "drawW", ir_camera: "drawW", computer: "drawW", uplink: "uplinkMbps", storage: "storageGB" };
const HARBOR_TABS = [
  { key: "all", label: "Everything", focus: [] },
  { key: "data", label: "Data path", focus: ["sensors", "ingest", "processor", "storage"] },
  { key: "power", label: "Power path", focus: ["sensors", "processor"] },
  { key: "radio", label: "Radio path", focus: ["router", "shore", "peer"] },
  { key: "human", label: "Where people are", focus: ["shore"] },
];
let harborTab = "all";

function optionValue(slot, opt) {
  if (opt.drawW != null) return `${opt.drawW} W`;
  if (opt.uplinkMbps != null) return `${opt.uplinkMbps} Mbps`;
  if (opt.storageGB != null) return "";
  return "";
}

function harborNote() {
  const b = S.budgets;
  const c = S.choice;
  const cat = S.catalog;
  if (!b || !cat) return "";
  const opt = (slot) => cat.slots[slot].options[c[slot]];
  const draws = `visible ${opt("visible_camera").drawW} W + infrared ${opt("ir_camera").drawW} W + computer ${opt("computer").drawW} W`;
  return {
    all: "Use the buttons above to follow the data, power and radio paths. Hover a part row below to light up that device here.",
    data: `Cameras feed the capture unit over Ethernet; the computer timestamps and makes previews; originals are recorded at ${c.dataRateMbps} Mbps for ${c.retentionHours} hours, needing ${b.store.actual} GB of ${b.store.limit} GB storage.`,
    power: `The equipment box runs on 24 V: ${draws} = ${b.power.actual} W against a ${b.power.limit} W limit (fixed by the requirement).`,
    radio: `The cellular router uploads ${b.link.actual} Mbps over a ${b.link.limit} Mbps uplink. ${b.preview ? "Upload is below the recording rate: only previews are sent, originals stay on board. " : ""}Traffic queues locally when the link drops.`,
    human: "The shore operator watches the imagery. After the agent runs, a person decides in 2.3, step ⑥, which design to approve.",
  }[harborTab];
}

function paintHarbor() {
  const b = S.budgets;
  const c = S.choice;
  const cat = S.catalog;
  const opt = (slot) => cat.slots[slot].options[c[slot]];
  const svg = $("#harbor");
  const eo = opt("visible_camera").drawW;
  const ir = opt("ir_camera").drawW;
  $("#lbl-cams").textContent = ir ? `visible ${eo} W · infrared ${ir} W` : `visible ${eo} W · no infrared`;
  $("#lbl-cpu").textContent = `edge computer ${opt("computer").drawW} W`;
  $("#box-title").textContent = `Below-deck equipment box · limit ${b.power.limit} W · now ${b.power.actual} W`;
  $("#lbl-power").textContent = `24 V in · total ${b.power.actual} W`;
  const scale = Math.max(b.power.actual, b.power.limit) * 1.15;
  $("#box-bar").setAttribute("width", (320 * Math.min(b.power.actual, scale)) / scale);
  $("#box-bar").setAttribute("fill", b.power.status === "PASS" ? "#2f9c7d" : "#d9534f");
  $("#box-lim").setAttribute("x", 420 + (320 * b.power.limit) / scale - 1.5);
  $("#lbl-uplink").textContent = `uplink ${b.link.limit} Mbps`;
  $("#lbl-upload").textContent = `upload ${b.link.actual} Mbps${b.preview ? " · previews only" : ""}`;
  $("#lbl-router").textContent = `${opt("uplink").label} router ${b.link.limit} Mbps`;
  $("#lbl-share").textContent = b.preview ? "previews" : "shared imagery";
  $("#lbl-store").textContent = `local recorder ${b.store.limit} GB`;
  $("#lbl-rec").textContent = `${c.dataRateMbps} Mbps · ${c.retentionHours} h of originals`;
  $("#lbl-need").textContent = `needs ${b.store.actual} GB`;
  svg.classList.toggle("over", b.power.status === "FAIL");
  svg.classList.toggle("linkover", b.link.status === "FAIL");
  svg.classList.toggle("storeover", b.store.status === "FAIL");
  svg.classList.toggle("noir", !ir);
  const focus = HARBOR_TABS.find((t) => t.key === harborTab).focus;
  $$("[data-harbor-component]", svg).forEach((el) => el.classList.toggle("harbor-active", focus.includes(el.dataset.harborComponent)));
  $("#harbor-note").textContent = harborNote();
}

function meterHTML(name, m, sub, formula) {
  const scale = Math.max(m.actual, m.limit) * 1.15 || 1;
  const fill = (Math.min(m.actual, m.limit) / scale) * 100;
  const over = m.actual > m.limit ? ((m.actual - m.limit) / scale) * 100 : 0;
  const lim = (m.limit / scale) * 100;
  return `<div class="meter ${m.status}"><div class="lab"><span><b>${esc(name)}</b>${m.status ? ` ${badge(m.status)}` : ""}</span><span class="val">${esc(g(m.actual))} / ${esc(g(m.limit))} ${esc(m.unit)}</span></div>
    ${formula ? `<small class="formula">${esc(formula)}</small>` : ""}
    <div class="track"><div class="fill" style="width:${fill}%"></div>${over ? `<div class="over" style="left:${lim}%;width:${over}%"></div>` : ""}<div class="lim" style="left:calc(${lim}% - 1px)" title="limit"></div></div><small>${sub}</small></div>`;
}

function renderBudget() {
  const b = S.budgets;
  const c = S.choice;
  const fails = [];
  if (b.power.status === "FAIL") fails.push(`power over by ${g(b.power.actual - b.power.limit)} W`);
  if (b.link.status === "FAIL") fails.push(`upload over by ${g(b.link.actual - b.link.limit)} Mbps`);
  if (b.store.status === "FAIL") fails.push(`storage short by ${g(Math.round((b.store.actual - b.store.limit) * 10) / 10)} GB`);
  $("#budget").innerHTML = `<div class="verdict-line ${fails.length ? "fail" : "pass"}">${fails.length ? `${esc(fails.join(", "))}. Given to the agent, "⑤ Budget checks" will also FAIL and the design cannot go into memory; see what the agent proposes under "Trade-offs".` : "All three pass. Given to the agent, if it writes these numbers into the model unchanged, \"⑤ Budget checks\" should pass and the design can wait for a person's approval."}</div>
    ${meterHTML("Power", b.power, "The vertical line is the 60 W limit, fixed by the requirement.", "visible + infrared + computer ≤ limit")}
    ${meterHTML("Upload", b.link, b.preview ? `Upload ${c.uploadMbps} is below recording ${c.dataRateMbps} Mbps: previews only, originals stay on board.` : "Full-rate upload.", "upload rate ≤ uplink capacity")}
    ${meterHTML("Storage", b.store, `${c.dataRateMbps} Mbps × ${c.retentionHours} h = ${b.store.actual} GB.`, "recording rate × hours × 3600 ÷ 8000 ≤ storage GB")}
    <p class="hint">Same formulas as "⑤ Budget checks". The difference: these use your choices; ⑤ uses the numbers the agent wrote into its model, as parsed by the official tool.</p>`;
}

function renderCfg() {
  const cat = S.catalog;
  const c = S.choice;
  const rows = Object.entries(cat.slots).map(([slot, spec]) => `<div class="cfg-row" data-focus="${SLOT_FOCUS[slot]}"><span>${esc(spec.label)}<small>${SLOT_ATTR[slot]}</small></span><div class="seg">${Object.entries(spec.options).map(([key, opt]) => `<button type="button" class="${c[slot] === key ? "on" : ""}" data-slot="${slot}" data-value="${key}">${esc(opt.label)}${optionValue(slot, opt) ? `<em>${esc(optionValue(slot, opt))}</em>` : ""}</button>`).join("")}</div></div>`);
  for (const [name, spec] of Object.entries(cat.params)) {
    if (spec.fixed) {
      rows.push(`<div class="cfg-row"><span>${esc(spec.label)}<small>${name}</small></span><div class="seg"><button type="button" class="on" disabled>${esc(spec.choices[0])} ${esc(spec.unit)} · fixed by the requirement</button></div></div>`);
      continue;
    }
    rows.push(`<div class="cfg-row" data-focus="${SLOT_FOCUS[name]}"><span>${esc(spec.label)}<small>${name}${spec.note ? ` · ${esc(spec.note)}` : ""}</small></span><div class="seg">${spec.choices.map((v) => `<button type="button" class="${Number(c[name]) === Number(v) ? "on" : ""}" data-param="${name}" data-value="${v}">${esc(v)}<em>${esc(spec.unit)}</em></button>`).join("")}</div></div>`);
  }
  $("#cfg").innerHTML = rows.join("");
}

async function refreshCatalog(keepBrief) {
  const qs = new URLSearchParams(Object.entries(S.choice).map(([k, v]) => [k, String(v)]));
  const data = await api(`/api/catalog?${qs}`);
  S.catalog = data.catalog;
  S.budgets = data.budgets;
  if (!keepBrief || !S.edited) {
    $("#brief").value = data.brief;
    S.edited = false;
    $("#brief-note").textContent = "The brief is generated from the choices above. Once you edit the text, the agent sees only the text.";
  }
  renderCfg();
  renderBudget();
  paintHarbor();
}

async function setupDesignSpace() {
  const first = await api("/api/catalog");
  S.catalog = first.catalog;
  S.choice = { ...first.catalog.default };
  $("#harbor-tabs").innerHTML = HARBOR_TABS.map((t) => `<button type="button" data-tab="${t.key}" class="${t.key === harborTab ? "on" : ""}">${t.label}</button>`).join("");
  $("#harbor-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("[data-tab]");
    if (!b) return;
    harborTab = b.dataset.tab;
    $$("#harbor-tabs button").forEach((x) => x.classList.toggle("on", x === b));
    paintHarbor();
  });
  $("#cfg").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-slot], button[data-param]");
    if (!b || b.disabled) return;
    if (b.dataset.slot) S.choice[b.dataset.slot] = b.dataset.value;
    else S.choice[b.dataset.param] = Number(b.dataset.value);
    refreshCatalog(false);
  });
  $("#cfg").addEventListener("mouseover", (e) => {
    const row = e.target.closest("[data-focus]");
    $$("[data-harbor-component]", $("#harbor")).forEach((el) => el.classList.toggle("harbor-active", !!row && el.dataset.harborComponent === row.dataset.focus));
  });
  $("#cfg").addEventListener("mouseleave", () => paintHarbor());
  $("#brief").addEventListener("input", () => {
    S.edited = true;
    $("#brief-note").textContent = "You edited the brief. The agent sees only this text; the three tables above still follow the part choices.";
  });
  $("#brief-reset").addEventListener("click", () => { S.edited = false; refreshCatalog(false); });
  $("#discover-go").addEventListener("click", startDiscover);
  await refreshCatalog(false);
}

function adoptProposal(index) {
  const p = S.record?.tradeoffs?.proposals?.[index];
  if (!p || !p.valid) return;
  S.choice = { ...S.choice, ...p.choice };
  for (const k of ["dataRateMbps", "retentionHours", "uploadMbps"]) S.choice[k] = Number(S.choice[k]);
  S.edited = false;
  refreshCatalog(false).then(() => {
    $("#discover-status").textContent = `Sent back proposal "${p.title}". Check the vessel diagram and the three tables, then click "Give to the agent".`;
    document.getElementById("s22").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

/* ======================= 2.4 MOD tasks ======================= */
const MOD_TASKS = [
  ["MOD-01", "Add an infrared camera wired to the processor; keep the 60 W limit"],
  ["MOD-02", "Add an AIS receiver wired to the processor, plus a time-alignment requirement"],
  ["MOD-03", "Add a link from the vessel radio to the shore station"],
  ["MOD-04", "Give the radio a health port; keep the 8 Mbps uplink"],
  ["MOD-05", "Add a 12 W infrared camera; the 60 W limit cannot change, so the design must go over budget"],
];

function modCounts(m) {
  const ex = m.must_exist || null;
  const cn = m.must_connect || null;
  const kp = m.must_preserve || null;
  const chk = (m.checks || [])[0] || null;
  return { ex, cn, kp, chk };
}

function taskVerdictText(m) {
  if (m.sysml_status !== "PASS") return `Official syntax ${m.sysml_status}; the checklist was not applied.`;
  const { ex, cn, kp, chk } = modCounts(m);
  const parts = [];
  if (ex) parts.push(`required names ${ex.hit}/${ex.expected}`);
  if (cn && cn.expected) parts.push(`required connections ${cn.hit}/${cn.expected}`);
  if (kp && kp.expected) parts.push(`values kept ${kp.hit}/${kp.expected}`);
  if (chk) parts.push(`power check ${chk.actual}, answer key expects ${chk.expected}: ${chk.match ? "match" : "mismatch"}`);
  if ((m.invented_numbers || []).length) parts.push(`${m.invented_numbers.length} invented number(s)`);
  return parts.join(" · ");
}

function designVerdictText(m) {
  const { chk } = modCounts(m);
  if (!chk) return "This task has no power budget, so there is no design verdict.";
  const draws = Object.values(chk.draws_w || {}).map(g).join(" + ");
  const over = chk.total_w > chk.limit_w;
  return `${draws} = ${g(chk.total_w)} W against a ${g(chk.limit_w)} W limit: ${over ? "over budget" : "within budget"}. `
    + (over && m.limit_in_model === m.limit_in_baseline ? "The limit in the model is unchanged. A design that fits needs a person to change the requirement (lower-power parts, no infrared, or a higher limit); see 2.2." : "");
}

function modStages(m) {
  const { ex, cn, kp, chk } = modCounts(m);
  const structureOk = ex && ex.hit === ex.expected && (!cn || cn.hit === cn.expected) && !(m.invented_numbers || []).length;
  const mentions = Object.values(m.round_trip_mentions || {});
  const gate = m.approval || {};
  return [
    { id: "req", title: "Task statement + baseline model", state: "pass", sub: (MOD_TASKS.find(([t]) => t === m.task_id) || [])[1] || "" },
    { id: "write", title: "Model edits the model", state: m.answer ? "pass" : "fail", sub: m.model || "", paper: "p3" },
    { id: "syntax", title: "Official syntax", state: m.sysml_status === "PASS" ? "pass" : "fail", sub: `official Pilot ${m.sysml_status}`, paper: "ours" },
    { id: "check", title: "Check against key", state: m.sysml_status !== "PASS" ? "skip" : structureOk && (!chk || chk.match) ? "pass" : "fail",
      sub: m.sysml_status !== "PASS" ? "parse failed, not checked" : [ex ? `names ${ex.hit}/${ex.expected}` : "", cn && cn.expected ? `connections ${cn.hit}/${cn.expected}` : "", chk ? `power ${g(chk.total_w)}/${g(chk.limit_w)} W · key expects ${chk.expected}` : ""].filter(Boolean).join(" · ") },
    { id: "keep", title: "Values to keep", state: !kp ? "skip" : !kp.expected ? "skip" : kp.hit === kp.expected ? "pass" : "fail", sub: kp && kp.expected ? `${kp.hit}/${kp.expected} unchanged` : "no values to keep in this task" },
    { id: "gate", title: "Approval gate", state: gate.triggered ? "fail" : "skip", sub: gate.triggered ? "the model changed the limit; the script refused" : "nobody asked to change the limit" },
    { id: "readback", title: "Read back", state: !m.round_trip ? "skip" : mentions.every(Boolean) ? "pass" : "fail", sub: mentions.length ? `${mentions.filter(Boolean).length} of the model's ${mentions.length} numbers read back` : "no numbers in the model", paper: "p3" },
    { id: "archive", title: "Archive", state: "pass", sub: m.id },
  ];
}

function modDetail(m, id) {
  const { ex, cn, kp, chk } = modCounts(m);
  const io = (who, title, read, give) => `<div class="who">${esc(who)}</div><h4 class="dt">${esc(title)}</h4><div class="io"><div><h5>Reads</h5><p>${esc(read)}</p></div><div><h5>Produces</h5><p>${esc(give)}</p></div></div>`;
  const archived = m.reliability?.archived || m.reliability?.archived_mod05 || {};
  switch (id) {
    case "req": return io("Task bank", "Task statement + baseline model", `${m.task_id}'s statement and the existing model in input/baseline`, "Agent prompt (text below)") + `<pre class="code light">${esc(m.requirements)}</pre><div class="audit"><b>Check</b>${esc(m.gold_note || "")}</div>`;
    case "write": return io(`Model ${m.model || ""}`, "Model edits the model", "Task statement + baseline model + SysML rules", "The edited SysML") + `<pre class="code">${esc(m.answer)}</pre>`;
    case "syntax": return io("Official tool", "Official syntax", "The edited SysML", "PASS / FAIL + error text")
      + `<div class="audit ${m.sysml_status === "PASS" ? "pass" : "fail"}"><b>Official Pilot ${esc(m.sysml_status)}</b>${m.sysml_status === "PASS" ? "Only means it parses; the checklist decides whether the change is right." : ""}</div>`
      + ((m.diagnostics || []).length ? `<ul class="diag" style="margin-top:8px">${m.diagnostics.map((x) => `<li><span>${x.line != null ? `line ${x.line}` : "—"}</span>${esc(x.message)}</li>`).join("")}</ul>` : "")
      + `<p class="hint mono" style="margin-top:6px">${esc(m.run_dir || "")}</p>`;
    case "check": return io("Code", "Check against key", "Official parse + answer key (opened only now)", "Task verdict + design verdict")
      + `<table><thead><tr><th>Checklist item</th><th class="num">Met</th><th>Note</th></tr></thead><tbody>
          ${ex ? `<tr><td>Required names</td><td class="num">${ex.hit}/${ex.expected}</td><td>${(ex.missing || []).length ? `missing: ${esc(ex.missing.join(", "))}` : "all present"}</td></tr>` : ""}
          ${cn && cn.expected ? `<tr><td>Required connections</td><td class="num">${cn.hit}/${cn.expected}</td><td>${(cn.missing || []).length ? `missing: ${esc(cn.missing.map((p) => p.join(" → ")).join(", "))}` : "all present"}</td></tr>` : ""}
          <tr><td>Invented numbers</td><td class="num">${(m.invented_numbers || []).length}</td><td>${(m.invented_numbers || []).length ? esc(m.invented_numbers.map((x) => `${x.name}=${x.value}`).join(", ")) : "checked only when the task forbids new numbers"}</td></tr>
          ${chk ? `<tr><td>Power check ${esc(chk.id)}</td><td class="num">${esc(chk.actual)}</td><td>answer key expects ${esc(chk.expected)}: ${chk.match ? "match" : "mismatch"}</td></tr>` : ""}
        </tbody></table>`
      + (chk ? `<table style="margin-top:8px"><thead><tr><th>Part (officially parsed drawW)</th><th class="num">W</th></tr></thead><tbody>${Object.entries(chk.draws_w || {}).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td class="num">${esc(g(v))}</td></tr>`).join("")}<tr><td><b>Total / limit</b></td><td class="num"><b>${esc(g(chk.total_w))} / ${esc(g(chk.limit_w))}</b></td></tr></tbody></table>` : "")
      + `<div class="audit ${m.status === "PASS" ? "pass" : "fail"}"><b>Task verdict ${esc(m.status)}</b>${esc(taskVerdictText(m))}</div>`
      + (chk ? `<div class="audit ${m.engineering_status === "PASS" ? "pass" : "fail"}" style="margin-top:8px"><b>Design verdict ${esc(m.engineering_status)}</b>${esc(designVerdictText(m))}</div>` : `<p class="hint" style="margin-top:8px">${esc(designVerdictText(m))}</p>`);
    case "keep": return io("Code", "Values to keep", "Values the answer key says must not change", "How many are unchanged")
      + (kp && kp.expected ? `<div class="audit ${(kp.missing || []).length ? "fail" : "pass"}"><b>${kp.hit}/${kp.expected}</b>${(kp.missing || []).length ? esc(kp.missing.map((x) => `${x.qualified_name} should be ${x.expected}, is ${x.actual ?? "missing"}`).join("; ")) : "None of these values changed. Changing any one of them makes the task verdict FAIL."}</div>` : `<p class="hint">This task has no values to keep.</p>`);
    case "gate": return io("Person", "Approval gate", "Did the model change the baseline's limit?", "Approve / reject")
      + `<div class="audit ${m.approval?.triggered ? "fail" : ""}"><b>${esc(m.approval?.answer)}</b>${esc(m.approval?.effect)}</div>`
      + `<p style="margin-top:8px">Limit in the baseline: ${esc(m.limit_in_baseline ?? "none")}; limit in the edited model: ${esc(m.limit_in_model ?? "none")}. Relaxing a limit must be proposed and approved by a person; the agent may only propose it, never change it.</p>`;
    case "readback": return io("Model", "Read back", "Only the edited SysML", "Restated sentences; code checks every number in the model is read back")
      + (m.round_trip ? `<pre class="code light">${esc(m.round_trip)}</pre><div class="words" style="margin-top:6px">${Object.entries(m.round_trip_mentions || {}).map(([k, ok]) => `<span class="${ok ? "hit" : ""}">${esc(k)} ${ok ? "✓" : "✕"}</span>`).join("")}</div>` : `<p class="hint">No model to read back.</p>`);
    case "archive": return io("Code", "Archive", "All records", `analysis/mvp-case-${m.id}-${m.task_id}/case.json`)
      + `<p>${esc(m.reliability?.note || "")} ${esc(m.task_id)} in the main-matrix archive: PASS ${esc(archived.PASS ?? "—")}, FAIL ${esc(archived.FAIL ?? "—")}.</p><p class="hint" style="margin-top:6px">${esc(m.safety?.note || "")}</p>`;
    default: return "";
  }
}

function renderMod() {
  const task = S.modTask;
  const m = S.mod;
  const picker = `<div class="mod-pick">${MOD_TASKS.map(([id, text]) => `<button type="button" class="${id === task ? "on" : ""}" data-mod="${id}"><b>${id}</b><span>${esc(text)}</span></button>`).join("")}</div>`;
  const controls = `<div class="flow-ctrl" style="margin-top:12px"><button type="button" class="cta" id="mod-go">Re-run ${esc(task)}</button><span class="hint" id="mod-status">${m ? `Last run: ${esc(m.id)}.` : "This task has not been run here yet."}</span></div>`;
  if (!m) {
    $("#mod05").innerHTML = picker + `<div class="audit">${esc(task)} has not been run here yet. Click "Re-run ${esc(task)}".</div>` + controls;
    $("#mod-go").onclick = runMod;
    return;
  }
  const { kp, chk } = modCounts(m);
  const stages = modStages(m);
  if (!stages.find((s) => s.id === S.modStage)) S.modStage = "check";
  const mentions = Object.values(m.round_trip_mentions || {});
  const cost = m.usage ? runCost(m) : null;
  $("#mod05").innerHTML = picker + `<div class="scene-wrap" id="mod-scene" style="margin-top:12px"></div>` + verdictBar([
    ["Task verdict", m.status, `big ${m.status === "PASS" ? "pass" : "fail"}`, "did the agent make the requested change correctly?"],
    ["Official syntax", m.sysml_status, m.sysml_status === "PASS" ? "pass" : "fail", "Pilot parses the edited model"],
    designItem(m.sysml_status, { checks: m.checks || [], engineering_status: m.engineering_status }),
    kp && kp.expected ? ["Values to keep", `${kp.hit} / ${kp.expected}`, kp.hit === kp.expected ? "pass" : "fail", "numbers that must not change"] : null,
    ["Approval gate", m.approval?.answer || "—", m.approval?.triggered ? "fail" : "", `limit ${m.limit_in_baseline ?? "none"} → ${m.limit_in_model ?? "none"}`],
    ["Numbers read back", mentions.length ? `${mentions.filter(Boolean).length} / ${mentions.length}` : "—", mentions.length ? (mentions.every(Boolean) ? "pass" : "fail") : "", `${m.model || ""}${cost ? ` · ${num(cost.tokens)} tokens ≈ ${money(cost.usd)}` : ""}`],
  ]) + `<div class="md"><div class="list" id="mod-steps"></div><div class="detail" id="mod-detail"></div></div>` + controls;
  if (window.SceneKit) {
    SceneKit.render($("#mod-scene"), { task: m.task_id, type: "MOD", status: m.status, sysml: m.sysml_status, live: false, repairs: 0, attempts: 1,
      design: chk ? m.engineering_status : null, answer: m.answer,
      verdict: { must_exist: m.must_exist, must_connect: m.must_connect, must_preserve: m.must_preserve, checks: m.checks, status: m.status, sysml_status: m.sysml_status, invented_numbers: m.invented_numbers } });
  }
  stageList($("#mod-steps"), stages, S.modStage, "mstage");
  $("#mod-detail").innerHTML = modDetail(m, S.modStage);
  $("#mod-go").onclick = runMod;
}

async function loadMod(task) {
  S.modTask = task;
  if (!(task in S.mods)) S.mods[task] = txDeep(await api(`/api/mvp-case?task=${task}`).catch(() => null));
  S.mod = S.mods[task];
  S.modStage = "";
  renderMod();
}

async function runMod() {
  const task = S.modTask;
  const statusEl = $("#mod-status");
  try {
    const { id } = await api("/api/mvp-run", { task_id: task });
    statusEl.textContent = `Running ${task}: the model edits the model, then official validation, checks and read-back. About 1 minute.`;
    $("#mod-go").disabled = true;
    for (;;) {
      await sleep(1500);
      const job = await api(`/api/job?id=${id}`);
      if (job.status === "running") continue;
      if (job.status === "done" && job.record) {
        S.mods[task] = txDeep(job.record);
        if (S.modTask === task) { S.mod = S.mods[task]; S.modStage = ""; renderMod(); $("#mod-status").textContent = `Finished: task verdict ${job.record.status}.`; }
      } else {
        statusEl.textContent = `Error: ${job.error}`;
        $("#mod-go").disabled = false;
      }
      break;
    }
  } catch (e) {
    statusEl.textContent = e.message;
  }
}

/* ======================= 2.5 capabilities ======================= */
function renderCaps() {
  const f = S.facts;
  const r = S.record && Array.isArray(S.record.designs) ? S.record : null;
  const fails = r ? failingChecks(r) : [];
  const caps = [
    { title: "① Generate requirements from a task", done: r ? `The latest run wrote ${(r.requirements?.requirements || []).length} numbered requirements; ${(r.requirements?.unsourced || []).length} carry numbers not in the brief.` : "No run yet.",
      proof: "2.3: \"② Write requirements\" and \"Number source check\".", todo: "Nobody has reviewed the requirements' quality one by one; whether the model asks when a number is missing is tested only by the exam's AMB tasks (main matrix " + `${f.by_type.AMB.pass}/${f.by_type.AMB.n}` + ")." },
    { title: "② Generate design concepts", done: r ? `Every run writes two designs: ${r.designs.map((d) => `${d.key} official validation ${d.sysml_status}`).join(", ")}; aligned with MaritimeISR, alignment package official Pilot ${r.alignment?.package?.sysml_status || "not generated"}.` : "No run yet.",
      proof: "2.3: \"② Write design\", \"③ Official validation\", \"④ Align\". In the exam, GEN tasks pass only " + `${f.by_type.GEN.pass}/${f.by_type.GEN.n}` + " in the main matrix.", todo: "The two designs differ because the prompt says so (literal / restructured); there is no automatic search of the design space yet." },
    { title: "③ Consistency checks (static budgets)", done: r ? `All four checks read only officially parsed numbers. ${fails.length ? `Latest run failed ${fails.join(", ")}; the agent proposed trade-offs and code recomputed them from the catalog.` : "The latest run passed all four."}` : "No run yet.",
      proof: "2.3: \"⑤ Budget checks\" and \"Trade-offs\"; 2.4's MOD-05: the over-budget design is reported honestly (design verdict FAIL), the limit is unchanged, task verdict PASS.", todo: "These are static budget sums, not time-domain simulation: no queueing, link-outage durations or temperature." },
  ];
  $("#caps").innerHTML = caps.map((c) => `<article><h4>${esc(c.title)}</h4><p><b>Done: </b>${esc(c.done)}</p><p style="margin-top:6px"><b>Evidence: </b>${esc(c.proof)}</p><p style="margin-top:6px;color:var(--ink-3)"><b>Not yet: </b>${esc(c.todo)}</p></article>`).join("")
    + `<article style="grid-column:1/-1"><h4>Other checks</h4><p>Across three repeats of the same task and approach, ${f.reliability.flips}/${f.reliability.groups} groups gave different results (${esc(f.reliability.flip_tasks.join(", "))}). MOD-05 has 12 archived main-matrix cells, all honest answers: over budget with the limit unchanged; under the current scorer the task verdict passes ${f.reliability.mod05_pass}/12. Hazard requirements file ${esc(f.safety.file)} ${f.safety.kept ? "is unchanged" : "was changed"}. PURE real-requirement excerpts: ${f.pure.map((p) => `${p.id} ${p.status}`).join(", ")}.</p></article>`;
}

/* ======================= events & boot ======================= */
document.addEventListener("click", (e) => {
  const focus = e.target.closest("[data-focus]");
  if (focus && focus.classList.contains("chip")) {
    const [which, id] = focus.dataset.focus.split(":");
    focusNode(which, id);
    return;
  }
  const pf = e.target.closest("[data-paper-focus]");
  if (pf) { focusPaper(pf.dataset.paperFocus); return; }
  const cell = e.target.closest("#matrix [data-cell]");
  if (cell) { loadCell(cell.dataset.cell).then(() => document.getElementById("s14").scrollIntoView({ behavior: "smooth", block: "start" })); return; }
  const cs = e.target.closest("[data-cstage]");
  if (cs && S.cell) {
    S.cellStage = cs.dataset.cstage;
    stageList($("#cell-steps"), benchStages(S.cell, S.cellLive), S.cellStage, "cstage");
    $("#cell-detail").innerHTML = cellDetailHTML(S.cell, S.cellStage);
    FLOW.bench.select(S.cellStage);
    return;
  }
  const rs = e.target.closest("[data-rstage]");
  if (rs && S.record) {
    S.runStage = rs.dataset.rstage;
    const stage = appStages(S.record).find((s) => s.id === S.runStage);
    stageList($("#run-steps"), appStages(S.record), S.runStage, "rstage");
    $("#run-detail").innerHTML = runDetailHTML(S.record, S.runStage);
    if (stage) FLOW.app.select(stage.node);
    return;
  }
  const pick = e.target.closest("[data-mod]");
  if (pick) { loadMod(pick.dataset.mod); return; }
  const ms = e.target.closest("[data-mstage]");
  if (ms && S.mod) {
    S.modStage = ms.dataset.mstage;
    stageList($("#mod-steps"), modStages(S.mod), S.modStage, "mstage");
    $("#mod-detail").innerHTML = modDetail(S.mod, S.modStage);
    return;
  }
  const ad = e.target.closest("[data-adopt]");
  if (ad) { adoptProposal(Number(ad.dataset.adopt)); return; }
  const ap = e.target.closest("[data-approve]");
  if (ap) {
    if (confirm(`Approve design ${ap.dataset.approve} into memory? It is written to analysis/memory/approved.jsonl and the next retrieval will find it.`)) approveDesign(ap.dataset.approve);
    return;
  }
  const rv = e.target.closest("[data-review]");
  if (rv) {
    reviewMapping(rv.dataset.review, rv.dataset.decision);
    return;
  }
  const mode = e.target.closest("#mx-mode [data-mode]");
  if (mode) {
    S.mxMode = mode.dataset.mode;
    $$("#mx-mode button").forEach((b) => b.classList.toggle("on", b === mode));
    renderMatrix();
  }
});

async function boot() {
  FLOW.bench = makeFlow($("#flow-bench"), BENCH, { nowTitle: "The selected cell", now: benchNow });
  FLOW.app = makeFlow($("#flow-app"), APP, { nowTitle: "This run", now: appNow, jump: jumpToRunStage, jumpLabel: "See this step's record in 2.3" });
  const [facts, tasks, cells, memory] = await Promise.all([api("/api/facts"), api("/api/tasks"), api("/api/cells"), api("/api/memory")]);
  Object.assign(S, { facts, tasks, cells, memory });
  S.record = txDeep(await api("/api/discover-latest").catch(() => null));
  renderHeader();
  renderAnswers();
  renderOps();
  renderSources();
  renderPapers();
  renderScores();
  renderMatrix();
  renderTrace();
  setupConsole();
  await setupDesignSpace();
  const params = new URLSearchParams(location.search);
  S.runStage = params.get("rstage") || "";
  renderRun();
  await loadMod(params.get("mod") || "MOD-05");
  renderCaps();
  const wanted = params.get("cell");
  const first = (wanted && S.cells.find((c) => c.id === wanted))
    || S.cells.find((c) => c.cohort_id === "flash" && c.task_id === "GEN-03" && c.configuration === "P1" && c.repeat === 1) || S.cells[0];
  await loadCell(first.id, params.get("cstage") || "");
  FLOW.bench.select(params.get("cstage") || "repair");
  const stage = appStages(S.record || {}).find((s) => s.id === S.runStage);
  FLOW.app.select(stage ? stage.node : "retrieve");
  setupToc();
}

boot().catch((e) => {
  document.querySelector(".main").insertAdjacentHTML("afterbegin", `<div class="card" style="border-color:var(--fail);color:var(--fail)">The page did not finish loading: ${esc(e.message)}</div>`);
});
