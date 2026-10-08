"use strict";
/* Standalone comparison page. Same diagram language as bench/board.js section 1.1. */

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MARK = { main: "#6cc7c9", feed: "#d4b46a", loop: "#e3ac46", side: "#a996e0", mem: "#79d49a" };
const PTAG = { p1: "Held out", p2: "Retrieval", p3: "If chosen", ours: "Approval" };
const ptag = (p) => (p ? `<i class="ptag ${p}">${PTAG[p]}</i>` : "");

function makeFlow(host, spec) {
  const byId = Object.fromEntries(spec.nodes.map((n) => [n.id, n]));
  const rowOf = Object.fromEntries(spec.rows.map((r, i) => [r.id, i + 1]));
  const rowOrder = Object.fromEntries(spec.rows.map((r, i) => [r.id, i]));
  const listed = [...spec.nodes].sort((a, b) => rowOrder[a.row] - rowOrder[b.row] || a.col - b.col);
  const edges = spec.edges.map((e) => ({ kind: "main", route: "h", ...e }));
  let selected = "";
  const filters = spec.filters || [];
  const legend = [["main", "Main path"], ["feed", "Reads material"], ["loop", "Only if needed"], ["side", "Optional call"]]
    .filter(([k]) => edges.some((e) => e.kind === k) || k === "main")
    .map(([k, t]) => `<span><svg viewBox="0 0 26 8" aria-hidden="true"><path d="M1 4H25" class="wire ${k}"/></svg>${t}</span>`).join("");

  const tags = spec.tags || PTAG;
  const tag = (p) => (p && tags[p] ? `<i class="ptag ${p}">${esc(tags[p])}</i>` : "");
  const card = (n, style) => `<button type="button" class="fn k-${n.kind || "step"}" data-node="${n.id}"${style ? ` style="${style}"` : ""}>`
    + `<span class="fn-owner">${esc(n.owner)}</span><span class="fn-state" aria-hidden="true"></span>`
    + `<span class="fn-title">${esc(n.title)}</span><span class="fn-sub">${esc(n.sub)}</span>`
    + `<span class="fn-tags">${(n.papers || []).map(tag).join("")}${n.cond ? `<i class="ctag">${esc(n.cond)}</i>` : ""}</span></button>`;

  host.innerHTML = `<div class="flow c${spec.cols}">
      <div class="flow-bar"><div class="flow-legend">${legend}</div>
        ${filters.length ? `<div class="paper-filter" role="group">${filters.map(([p, t]) => `<button type="button" data-paper="${p}" class="${p ? "" : "on"}">${p ? `<span class="pdot ${p}"></span>` : ""}${t}</button>`).join("")}</div>` : ""}
      </div>
      <div class="paper-caption" hidden></div>
      <div class="flow-canvas"><div class="flow-grid" style="--cols:${spec.cols}">
        ${spec.rows.map((r, i) => `<div class="flow-band" style="grid-row:${i + 1}"></div><div class="flow-band-label" style="grid-row:${i + 1}">${esc(r.label)}<small>${esc(r.hint)}</small></div>`).join("")}
        ${spec.nodes.map((n) => card(n, `grid-row:${rowOf[n.row]};grid-column:${n.col + 1}`)).join("")}
        <svg class="flow-wires" aria-hidden="true"></svg><div class="flow-labels"></div>
      </div></div>
      <ol class="flow-list">${listed.map((m) => `<li>${card(m)}</li>`).join("")}</ol>
    </div>
    <div class="node-detail" hidden></div>`;

  const flowEl = $(".flow", host);
  const grid = $(".flow-grid", host);
  const svg = $(".flow-wires", host);
  const labelLayer = $(".flow-labels", host);
  const canvas = $(".flow-canvas", host);
  const detail = $(".node-detail", host);
  const caption = $(".paper-caption", host);
  const defs = `<defs>${Object.entries(MARK).map(([k, c]) => `<marker id="${spec.id}-m-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto"><path d="M0 0L10 5 0 10z" fill="${c}"/></marker>`).join("")}</defs>`;
  let paper = "";

  function geom(el, box) {
    const r = el.getBoundingClientRect();
    const x = r.left - box.left;
    const y = r.top - box.top;
    return { x, y, w: r.width, h: r.height, r: x + r.width, b: y + r.height, cx: x + r.width / 2, cy: y + r.height / 2 };
  }
  function rounded(pts, rad = 9) {
    const clean = pts.filter((p, i) => i === 0 || Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]) > 0.5);
    if (clean.length < 2) return "";
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
  function route(e, A, B) {
    const gap = 3;
    if (e.route === "v") {
      const y1 = B.y >= A.b - 1 ? A.b : A.y;
      const y2 = B.y >= A.b - 1 ? B.y - gap : B.b + gap;
      if (Math.abs(A.cx - B.cx) < 8) return { pts: [[A.cx, y1], [A.cx, y2]], lab: [A.cx, (y1 + y2) / 2] };
      const my = (y1 + y2) / 2;
      return { pts: [[A.cx, y1], [A.cx, my], [B.cx, my], [B.cx, y2]], lab: [(A.cx + B.cx) / 2, my] };
    }
    if (Math.abs(A.cy - B.cy) < 8) return { pts: [[A.r, A.cy], [B.x - gap, B.cy]], lab: [(A.r + B.x) / 2, A.cy - 14] };
    const mx = (A.r + B.x) / 2;
    return { pts: [[A.r, A.cy], [mx, A.cy], [mx, B.cy], [B.x - gap, B.cy]], lab: [mx, (A.cy + B.cy) / 2] };
  }
  function paint() {
    for (const el of $$(".fn", host)) {
      const id = el.dataset.node;
      const hit = (byId[id].papers || []).includes(paper);
      el.classList.toggle("is-sel", id === selected);
      el.classList.toggle("p-on", !!paper && hit);
      el.classList.toggle("p-off", !!paper && !hit);
      if (hit) el.dataset.pbadge = tags[paper] || "";
      else delete el.dataset.pbadge;
    }
    for (const el of $$(".wire, .wlabel", host)) {
      const { from, to } = el.dataset;
      if (!from) continue;
      const declared = (el.dataset.papers || "").trim().split(/\s+/).filter(Boolean);
      const on = !!paper && (declared.length
        ? declared.includes(paper)
        : ((byId[from].papers || []).includes(paper) || (byId[to].papers || []).includes(paper)));
      el.classList.toggle("p-path", on);
      el.classList.toggle("dim", !!paper && !on);
    }
  }
  function renderDetail() {
    if (!selected || !byId[selected]) { detail.hidden = true; return; }
    const n = byId[selected];
    detail.hidden = false;
    detail.innerHTML = `<div><h4>${esc(n.owner)}</h4><div class="nd-title">${esc(n.title)}</div><div class="nd-state">${esc(n.cond || "Step")}</div><div class="nd-tags">${(n.papers || []).map(tag).join("")}</div></div>
      <div><h4>What it does</h4><p>${esc(n.does)}</p></div>
      <div><h4>Reads → produces</h4><p><b>Reads: </b>${esc(n.input)}\n<b>Produces: </b>${esc(n.output)}</p></div>
      <div><h4>${esc(spec.nowTitle || "Record")}</h4><p>${esc(n.effect)}</p></div>`;
  }
  function redraw() {
    if (!canvas.offsetParent && getComputedStyle(canvas).display === "none") return;
    const box = grid.getBoundingClientRect();
    if (!box.width) return;
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
      const r = route(e, geom(a, box), geom(b, box));
      const d = rounded(r.pts);
      if (!d) continue;
      const papersAttr = (e.papers || []).length ? ` data-papers="${e.papers.join(" ")}"` : "";
      paths.push(`<path class="wire ${e.kind}" data-from="${e.from}" data-to="${e.to}"${papersAttr} d="${d}" marker-end="url(#${spec.id}-m-${e.kind})"/>`);
      if (e.label) labels.push(`<span class="wlabel ${e.kind}" data-from="${e.from}" data-to="${e.to}"${papersAttr} style="left:${r.lab[0].toFixed(1)}px;top:${r.lab[1].toFixed(1)}px">${esc(e.label)}</span>`);
    }
    svg.innerHTML = defs + paths.join("");
    labelLayer.innerHTML = labels.join("");
    paint();
  }
  function setPaper(p) {
    paper = p || "";
    if (paper) flowEl.dataset.paper = paper; else delete flowEl.dataset.paper;
    for (const b of $$(".paper-filter button", host)) b.classList.toggle("on", b.dataset.paper === paper);
    caption.hidden = !paper;
    caption.innerHTML = paper && spec.captions ? spec.captions[paper] || "" : "";
    paint();
  }
  host.addEventListener("click", (ev) => {
    const f = ev.target.closest(".paper-filter button");
    if (f && host.contains(f)) { setPaper(f.dataset.paper); return; }
    const n = ev.target.closest("[data-node]");
    if (n && host.contains(n)) { selected = n.dataset.node; paint(); renderDetail(); }
  });
  new ResizeObserver(() => requestAnimationFrame(redraw)).observe(grid);
  window.addEventListener("resize", () => requestAnimationFrame(redraw));
  if (document.fonts) document.fonts.ready.then(redraw);
  redraw();
  return { redraw };
}

const COURSE = {
  id: "course", cols: 7, nowTitle: "Lecture record (not run here)",
  tags: { p1: "Held out", p2: "Retrieval", p3: "Decision text" },
  filters: [["", "All"], ["p2", "Retrieval"], ["p3", "Decision text"], ["p1", "Held out"]],
  captions: {
    p2: "<b>Retrieval.</b> The rewrite step names the documents, and the shipped prompt also names the gold numbers (60.0 ksi, 64.2 ksi, the dates). Knowledge then searches Demo_KB.",
    p3: "<b>Decision text.</b> The model writes the classification. PASS is allowed only when the retrieved text contains the requirement, the measurement, and calibration. Nothing is written to a file.",
    p1: "<b>Held out of the success path.</b> The 2018 specification is in the folder so a later demo can show a stale source. The lecture says to keep it out of Demo_KB until that demo.",
  },
  rows: [
    { id: "src", label: "Documents", hint: "uploaded, or held out" },
    { id: "main", label: "Every question", hint: "seven nodes, fixed order" },
  ],
  nodes: [
    { id: "pdfs", row: "src", col: 3, kind: "source", owner: "Four current PDFs", title: "Spec, report, calibration, manual", sub: "MAT-SPEC · TR · CAL · QMS", papers: ["p2"],
      does: "Synthetic training documents. Current yield minimum 60.0 ksi. Sample T-401-03 measured 64.2 ksi on 2026-05-17 on machine UTM-17. Calibration valid 2026-05-01 through 2027-04-30. The quality manual defines PASS, FAIL, HOLD, and a 5% review band.",
      input: "The five-file folder, minus the obsolete spec on the success path", output: "Chunks of about 1000 characters in Demo_KB",
      effect: "Lecture. Not run here. Slide 9 says to embed with text-embedding-3-small or large and keep the requirement, the result, and the calibration sentence intact." },
    { id: "old", row: "src", col: 6, kind: "gold", owner: "Obsolete PDF", title: "2018 specification", sub: "not in the success-path KB", papers: ["p1"],
      does: "OBS-MAT-SPEC-G60-2018 is in the folder on purpose. The lecture tells the class to leave it out of Demo_KB until the stale-source demo.",
      input: "The same folder", output: "A later conflict demo, not the first run",
      effect: "Lecture. If a current acceptance decision uses this file, the expected class is HOLD. Not run here." },
    { id: "chat", row: "main", col: 1, kind: "human", owner: "Person", title: "Chat input", sub: "one question, every time",
      does: "The flow file’s saved question is “Did sample T-401-03 pass the yield strength requirement?” Every later node runs for that question and for any other question.",
      input: "The question", output: "The same text, sent two ways",
      effect: "Lecture. The chain cannot skip a node. A lookup and a pass/fail decision take the same path." },
    { id: "rewrite", row: "main", col: 2, owner: "Prompt, no model", title: "Query rewrite", sub: "the gold facts are in the prompt", papers: ["p2"], cond: "Not run here",
      does: "Turns the short question into a retrieval string that names all four current documents. The copy in the flow file also contains the answers: minimum 60.0 ksi, measured 64.2 ksi, test date 2026-05-17, calibration through 2027-04-30.",
      input: "The question", output: "One long retrieval string",
      effect: "Lecture, from the flow file. Slide 8 says a raw question often retrieves only the test report. Stuffing the gold numbers makes this one demo question hit the other documents. A different sample still asks for T-401-03." },
    { id: "kb", row: "main", col: 3, owner: "Langflow Knowledge", title: "Retrieve", sub: "Demo_KB · top 10", papers: ["p2"], cond: "Not run here",
      does: "Retrieval mode. Chunk size about 1000. Top K 10. Include metadata, omit embeddings. The lecture says 10 is enough to surface spec, test, calibration, and the quality manual.",
      input: "The rewritten string", output: "A table of chunks",
      effect: "Lecture. Slide 16: if the answer is HOLD, inspect this node first. A missing requirement or a missing calibration is a retrieval miss, not a model miss." },
    { id: "parser", row: "main", col: 4, owner: "Parser", title: "Format chunks", sub: "file, index, score, text", papers: ["p2"], cond: "Not run here",
      does: "Prints each hit as source file, chunk index, retrieval score, and the text, separated by a line.",
      input: "The knowledge table", output: "Readable context for the decision prompt",
      effect: "Lecture. The model can see which PDF a sentence came from. There is no separate citation check after the answer." },
    { id: "prompt", row: "main", col: 5, owner: "Prompt", title: "Decision prompt", sub: "evidence gate and 5% margin", papers: ["p3"], cond: "Not run here",
      does: "Tells the model to use only the retrieved context. PASS needs the current requirement, the measured value, and calibration when a machine is involved. Margin = ((measured − minimum) / minimum) × 100. Above 5% is PASS. At or under 5% is PROVISIONAL PASS and human review. Below the minimum is FAIL. Missing evidence is HOLD.",
      input: "Formatted chunks and the question", output: "The prompt the model sees",
      effect: "Lecture. For this sample the stated margin is 7.0%, so the 5% line does not apply and the expected class is PASS. Tensile strength and elongation are inside 5% and would flag review on the all-requirements question." },
    { id: "llm", row: "main", col: 6, owner: "Model", title: "One model call", sub: "gpt-5.4-mini · temperature 0", papers: ["p3"], cond: "Not run here",
      does: "A single completion. The lecture names llama3.2:3b on Ollama as a local illustration, and says not to use it for the quality decision.",
      input: "The decision prompt", output: "About 600 words in six sections",
      effect: "Lecture. The classification is text. “Human review required” does not stop a write, because this chain does not write." },
    { id: "out", row: "main", col: 7, owner: "Langflow", title: "Chat output", sub: "the answer is the product", papers: ["p3"], cond: "Not run here",
      does: "Shows the model’s answer. Sections: direct answer, evidence table, the margin arithmetic, one classification, a human-review flag, sources used.",
      input: "The model text", output: "The playground message",
      effect: "Lecture. Refusing to certify a lot, refusing Inconel 718, and warning on the 2018 spec are expected sentences. Not run here." },
  ],
  edges: [
    { from: "chat", to: "rewrite" }, { from: "rewrite", to: "kb" }, { from: "kb", to: "parser" },
    { from: "parser", to: "prompt" }, { from: "prompt", to: "llm" }, { from: "llm", to: "out" },
    { from: "pdfs", to: "kb", kind: "feed", route: "v", label: "Demo_KB" },
    { from: "old", to: "kb", kind: "side", route: "v", label: "kept out of this KB" },
  ],
};

const OURS = {
  id: "ours", cols: 8, nowTitle: "Measured in this repository",
  tags: { p3: "May skip", ours: "Approval" },
  filters: [["", "All"], ["p3", "May skip"], ["ours", "Approval"]],
  captions: {
    p3: "<b>May skip.</b> These cards run only when the agent calls them. “Add a sensor” called tools and then asked for numbers. It did not start a design.",
    ours: "<b>Approval.</b> Write to memory pauses the job. The person approves or rejects the card. The service still refuses a design that missed a check.",
  },
  rows: [
    { id: "main", label: "Every message", hint: "the agent may call nothing" },
    { id: "tools", label: "Tools", hint: "only if the agent calls the card" },
  ],
  nodes: [
    { id: "msg", row: "main", col: 1, kind: "human", owner: "Engineer", title: "Message", sub: "any wording",
      does: "The engineer writes in the playground. The agent is told not to invent a number, not to move a stated limit, and to show the brief and wait before a design run.",
      input: "The message", output: "The agent’s context",
      effect: "Comparison, 2026-10-07, local Qwen3.8-27B. Six scripted turns, fresh sessions, same wording on both outers." },
    { id: "agent", row: "main", col: 2, owner: "Langflow Agent", title: "Chooses tools", sub: "local 27B · may call none",
      does: "Langflow’s Agent component. It sees the tool cards wired to it. It can answer from the conversation, call one card, or call several. It does not walk them in a fixed order.",
      input: "The message and earlier turns", output: "Tool calls, or an answer with no tool",
      effect: "“Add a sensor”: six tool calls, then a request for four numbers, no design run (20 s). “Which projects, and the power limit?”: list plus search, all three at 60 W, and it quoted PowerLimitUnchanged (10 s). The 30 W lidar question: 7 + 14 + 30 = 51 ≤ 60, 3/3 on fresh sessions." },
    { id: "reply", row: "main", col: 8, owner: "Langflow Agent", title: "Reply", sub: "after tools, or without them",
      does: "The playground message. Verdicts are supposed to be quoted from tools, with the run id. A chat sum is supposed to show the arithmetic.",
      input: "Tool results, or the conversation alone", output: "The answer the engineer reads",
      effect: "The lidar sum was right 3/3 on both outers after the script asked for the arithmetic. Earlier the same evening the OpenCode outer once called 51 W “still 19 W over.” The pipeline’s checks do not depend on that sentence." },
    { id: "list", row: "tools", col: 1, owner: "One card", title: "List projects", sub: "MCP · one read", papers: ["p3"], cond: "Measured",
      does: "Lists MaritimeISR and every approved design, with the brief and the key numbers of each approved design.",
      input: "No argument", output: "Project names, briefs, numbers",
      effect: "Turn 1. Both approved designs are 60 W. The Langflow agent also searched and quoted the MaritimeISR limit. The OpenCode outer said the list had no limit for MaritimeISR and offered to read the file. It did not." },
    { id: "read", row: "tools", col: 2, owner: "One card", title: "Read a project", sub: "MCP · one file", papers: ["p3"], cond: "Not called alone",
      does: "Returns the SysML text of MaritimeISR or of an approved design, cut at 12000 characters.",
      input: "A project name or a run id", output: "SysML text",
      effect: "The scripted comparison never called this card by itself." },
    { id: "search", row: "tools", col: 3, owner: "A flow", title: "Memory search", sub: "five cards · no model", papers: ["p3"], cond: "Measured",
      does: "Runs the memory-search flow: the words, the card library, MiniLM + FAISS seeds, one hop, the cards. Section 3.1 is that chain.",
      input: "The engineer’s words", output: "Cards with source and score",
      effect: "“Uplink and upload rates”: 2 neighbours, 6 cards, the R9 requirement cards and the Uplink parts of both approved designs, with sources. 20 s. No model call." },
    { id: "pipe", row: "tools", col: 4, owner: "A flow", title: "Design pipeline", sub: "2 to 10 minutes", papers: ["p3"], cond: "Measured",
      does: "Runs the design pipeline after the engineer confirms the brief. Section 3.4 is that chain. An empty or misnamed argument is refused.",
      input: "The confirmed brief, under the generated argument name", output: "The review, the run id, the four checks",
      effect: "Run 20261007T064005, OpenCode outer: the brief was unchanged. Both designs PASS at parse 1. POWER 49 ≤ 60 W, LINK 12 ≤ 20 Mbps, STORE 64.8 ≤ 256 GB, TRACE 9/9, alignment 6/6. Run 20261007T071503 used the page default instead of the confirmed brief (see 3.4)." },
    { id: "valid", row: "tools", col: 5, owner: "A flow", title: "Validate SysML", sub: "official Pilot", papers: ["p3"], cond: "Measured",
      does: "Saves pasted text as a file and parses it with the official Pilot. Section 3.2 is that chain.",
      input: "SysML text and a package name", output: "PASS or FAIL, and the first diagnostics",
      effect: "“package Probe {…}”: official Pilot PASS. 10 s." },
    { id: "record", row: "tools", col: 6, owner: "One card", title: "Record decision", sub: "Reject or Send back", papers: ["p3"], cond: "Measured",
      does: "Writes the engineer’s decision onto the run. It does not write the design into memory.",
      input: "Run id, Reject or Send back, a reason", output: "A line on the run record",
      effect: "Turn 5, both outers: Send back, reason “comparison test”. 5 s. Nothing was added to memory." },
    { id: "cameo", row: "tools", col: 7, owner: "One card", title: "Export for Cameo", sub: "files only", papers: ["p3"], cond: "Not called",
      does: "Writes the designs that passed the Pilot as .sysml files for a person to open in Cameo. Cameo has no headless command. The Pilot stays the judge.",
      input: "A run id", output: "Files under analysis/cameo-exports/<run>/",
      effect: "The scripted comparison did not call this card." },
    { id: "write", row: "tools", col: 8, kind: "human", owner: "A flow · pauses", title: "Write to memory", sub: "approval card, then the gate", papers: ["ours", "p3"], cond: "Measured",
      does: "The job pauses. Approve runs the write flow: gate, write, record, re-read the library, refresh the knowledge base. Reject does not run it. Section 3.3 is the chain after Approve.",
      input: "Run id and design A or B, after the card", output: "A memory line, or a refusal",
      effect: "Design A of 20261003T150116 is already in memory. The job paused on the card. After Approve the gate refused. approved.jsonl stayed at two lines. 15 s." },
  ],
  edges: [
    { from: "msg", to: "agent" },
    { from: "agent", to: "reply", label: "then answers" },
    { from: "agent", to: "list", kind: "side", route: "v" },
    { from: "agent", to: "read", kind: "side", route: "v" },
    { from: "agent", to: "search", kind: "side", route: "v" },
    { from: "agent", to: "pipe", kind: "side", route: "v" },
    { from: "agent", to: "valid", kind: "side", route: "v" },
    { from: "agent", to: "record", kind: "side", route: "v" },
    { from: "agent", to: "cameo", kind: "side", route: "v" },
    { from: "agent", to: "write", kind: "side", route: "v", label: "pauses first" },
  ],
};

function chain(id, cols, rows, nodes, edges) {
  return { id, cols, nowTitle: "Measured in this repository", rows, nodes, edges };
}

const SEARCH = chain("search", 5,
  [{ id: "main", label: "Memory search", hint: "every call, no model" }],
  [
    { id: "q", row: "main", col: 1, owner: "Code", title: "Search words", sub: "the engineer’s words", cond: "Measured",
      does: "Uses the text the agent passed in. It does not rewrite the question and it does not insert known answers.",
      input: "The query string", output: "Words and numbers from that string",
      effect: "The check phrase was “uplink and upload rates”. The gold rates were not written into the query." },
    { id: "lib", row: "main", col: 2, owner: "Code", title: "Card library", sub: "MaritimeISR + approved designs",
      does: "Rebuilds cards from the official parse of MaritimeISR and from every line in the approval file. A new approval is visible on the next call.",
      input: "The model files", output: "Element cards",
      effect: "Two approved designs were in the file during the check (20261003T144529 and 20261003T150116)." },
    { id: "seed", row: "main", col: 3, owner: "Code", title: "FAISS seeds", sub: "MiniLM · cosine ≥ 0.30",
      does: "Embeds the query and the cards. Keeps seeds at cosine 0.30 or better, plus an exact-name bonus. The index code is the frozen exam retrieval.",
      input: "Query + cards", output: "Up to 4 seeds",
      effect: "Same retrieval the results page uses. No second ranking." },
    { id: "hop", row: "main", col: 4, owner: "Code", title: "One hop", sub: "owners and connection ends",
      does: "Adds neighbours of the seeds, up to the card limit. Neighbours are ownership and connection ends, not a second search.",
      input: "Seeds", output: "Seeds plus neighbours",
      effect: "The uplink query returned 2 neighbours and 6 cards in total." },
    { id: "cards", row: "main", col: 5, owner: "Code", title: "Cards back", sub: "source, score, text", cond: "Measured",
      does: "Returns the card text, which project it came from, and the score. The agent is supposed to quote those, not replace them.",
      input: "The picked cards", output: "The tool result",
      effect: "R9 requirement cards and the Uplink parts of both approved designs, with sources. 20 s." },
  ],
  [{ from: "q", to: "lib" }, { from: "lib", to: "seed" }, { from: "seed", to: "hop" }, { from: "hop", to: "cards" }]);

const VALIDATE = chain("valid", 4,
  [{ id: "main", label: "Validate SysML", hint: "every call" }],
  [
    { id: "paste", row: "main", col: 1, kind: "human", owner: "Engineer", title: "Pasted text", sub: "a package in the text",
      does: "The agent passes the SysML the engineer pasted, and the package name.",
      input: "Text", output: "The same text",
      effect: "The check used a small package named Probe." },
    { id: "file", row: "main", col: 2, owner: "Code", title: "Save the file", sub: "<package>.sysml",
      does: "Writes the text to a file under the exam inbox so the Pilot sees a file, not a string.",
      input: "The text", output: "A .sysml file",
      effect: "The file is the input the official tool accepts. The assistant does not edit it afterward." },
    { id: "pilot", row: "main", col: 3, kind: "judge", owner: "Official tool", title: "SysML v2 Pilot", sub: "syntax and references", cond: "Measured",
      does: "Parses and links the file. PASS means the text is legal SysML v2. It does not mean the design meets a budget.",
      input: "The file", output: "PASS or FAIL, diagnostics",
      effect: "package Probe: official Pilot PASS. 10 s." },
    { id: "verdict", row: "main", col: 4, owner: "Code", title: "Verdict back", sub: "first diagnostics",
      does: "Returns the status and up to twelve diagnostics. The agent is supposed to quote them.",
      input: "The Pilot result", output: "The tool result",
      effect: "The unfolded agent reported official Pilot PASS for package Probe." },
  ],
  [{ from: "paste", to: "file" }, { from: "file", to: "pilot" }, { from: "pilot", to: "verdict" }]);

const WRITE = chain("write", 6,
  [{ id: "main", label: "Write to memory", hint: "after the approval card" }],
  [
    { id: "card", row: "main", col: 1, kind: "human", owner: "Person", title: "Approval card", sub: "the job is paused", cond: "Measured",
      does: "The unfolded assistant does not enter this flow until the person approves the card. Reject leaves the flow unrun.",
      input: "The agent’s request to run the flow", output: "Approve or Reject",
      effect: "The 150116 request paused the job. The check then pressed Approve, so the later cards did run." },
    { id: "gate", row: "main", col: 2, kind: "guard", owner: "Code", title: "Gate", sub: "read only", cond: "Measured",
      does: "Refuses when the Pilot is not PASS, when POWER, LINK, STORE, or TRACE is not PASS, when a requirement number is not in the brief, or when that design is already in memory.",
      input: "The run record", output: "Allowed, or the reason",
      effect: "Design A of 20261003T150116: already in memory. Pilot PASS, four checks PASS. The gate refused the write." },
    { id: "save", row: "main", col: 3, owner: "Code", title: "Write", sub: "only if the gate allows",
      does: "Appends one line to the approval file and copies the SysML next to the memory. A refusal writes nothing.",
      input: "The gate", output: "A line, or no change",
      effect: "The result text was “not approved: This design is already in memory.” approved.jsonl stayed at two lines." },
    { id: "rec", row: "main", col: 4, owner: "Code", title: "Record", sub: "on the run",
      does: "Records the outcome on the run. A refusal is still reported, so the agent cannot describe the last card alone as a success.",
      input: "The write result", output: "The run note",
      effect: "The flow returned the whole story (gate, write, record). An earlier build returned only the last card, and the agent said “written”." },
    { id: "lib", row: "main", col: 5, owner: "Code", title: "Library re-read", sub: "next search sees it",
      does: "The search tools re-read the approval file on every call. This card does that read again so the returned text shows the library after the write.",
      input: "The approval file", output: "The card count",
      effect: "No new design. The library was unchanged." },
    { id: "kb", row: "main", col: 6, owner: "Langflow Knowledge", title: "Refresh rtrc_memory", sub: "new cards only",
      does: "Embeds cards that are not already in the Langflow knowledge base. Duplicates are skipped. About 45 cards for one new design.",
      input: "The library", output: "The knowledge base",
      effect: "The ingest ran and added no rows. The three-card assistant does not run this step; that path still needs F0 once after an approval." },
  ],
  [{ from: "card", to: "gate" }, { from: "gate", to: "save" }, { from: "save", to: "rec" }, { from: "rec", to: "lib" }, { from: "lib", to: "kb" }]);

const PIPE = {
  id: "pipe", cols: 8, nowTitle: "Measured in this repository",
  rows: [
    { id: "src", label: "Shown to the writer", hint: "read-only cards" },
    { id: "main", label: "Design pipeline", hint: "when the agent calls it" },
    { id: "side", label: "Only if needed", hint: "empty brief · a failed check" },
  ],
  nodes: [
    { id: "rules", row: "src", col: 4, kind: "source", owner: "Read-only card", title: "Rules", sub: "given to OpenCode",
      does: "The SysML rules the sandboxed writer sees. The card is on the canvas so the text is visible. It is not a second author.",
      input: "The pipeline’s prompt", output: "The same text, shown",
      effect: "Part of the design prompt. The comparison did not score this card alone." },
    { id: "template", row: "src", col: 5, kind: "source", owner: "Read-only card", title: "Attribute template", sub: "names and values",
      does: "The attribute contract: which names carry power, rates, and storage, and that the values come from the brief.",
      input: "The pipeline’s prompt", output: "The same text, shown",
      effect: "The checks later look for those names on the official parse. A missing name becomes UNKNOWN, not a guessed number." },
    { id: "examples", row: "src", col: 6, kind: "source", owner: "Read-only card", title: "Examples", sub: "retrieved cards, or the similar project",
      does: "The cards retrieved for this brief, or the similar project when the path is reuse. OpenCode sees them as examples.",
      input: "Step ①", output: "Example text in the prompt",
      effect: "Run 064005 started from the similar project. The brief’s numbers were the ones the engineer confirmed, not the examples’ numbers." },
    { id: "brief", row: "main", col: 1, kind: "human", owner: "The agent", title: "Confirmed brief", sub: "empty is refused",
      does: "The brief the engineer confirmed, passed as the flow argument. If the argument is missing or empty, the start node refuses instead of using the page’s default brief.",
      input: "The confirmed paragraph", output: "The run’s brief",
      effect: "Run 20261007T074333: the brief arrived word for word. Run 20261007T071503, before this refusal: a misnamed argument was ignored and the page default ran (41 W, 25 W, 12 W)." },
    { id: "mem", row: "main", col: 2, owner: "Code", title: "① Memory", sub: "same search as 3.1",
      does: "Searches the memory with the brief. Decides whether a similar project exists.",
      input: "The brief", output: "Cards, and similar or new",
      effect: "Run 064005 reused a similar project. The search does not rewrite the brief." },
    { id: "req", row: "main", col: 3, owner: "Model", title: "② Requirements", sub: "numbered, from the brief",
      does: "Splits the brief into numbered requirements. A number that is not in the brief blocks later approval.",
      input: "The brief and the cards", output: "Requirements",
      effect: "On the runs that reached the gate, unsourced numbers were not what failed. Design B of 074333 failed later, on empty content." },
    { id: "write", row: "main", col: 4, owner: "OpenCode · sandbox", title: "③ Two designs", sub: "local 27B · ./validate",
      does: "OpenCode writes design A (adapt the similar project when there is one) and design B (from scratch). It can call the Pilot, read the errors, and edit the file. The results page must be stopped.",
      input: "Rules, template, examples, brief, requirements", output: "Two SysML files",
      effect: "Run 064005: both PASS at the first parse (the turn took 255 s). Run 074333: design B came back as an empty package after 544 s." },
    { id: "pilot", row: "main", col: 5, kind: "judge", owner: "Official tool", title: "④ Pilot", sub: "syntax only",
      does: "Parses both files. PASS is syntax and references. Budgets are the next cards.",
      input: "The two files", output: "PASS or FAIL per design",
      effect: "Run 074333 design B: Pilot PASS on an empty package. TRACE was then 0/9 and POWER UNKNOWN. A syntax pass did not enter memory." },
    { id: "align", row: "main", col: 6, owner: "Model, then code", title: "⑤ Align", sub: "design A ↔ MaritimeISR",
      does: "Proposes pairs between design A and MaritimeISR. Code checks the names. The alignment package is parsed with both sources. Neither source file is edited.",
      input: "Design A and the retrieved model", output: "Pairs and a package",
      effect: "Run 064005: alignment 6/6, package PASS." },
    { id: "checks", row: "main", col: 7, owner: "Code", title: "⑥ Four checks", sub: "parsed numbers only",
      does: "POWER: sum of drawW ≤ powerLimitW. LINK: upload ≤ uplink. STORE: rate × hours × 3600 ÷ 8000 ≤ storage. TRACE: each numbered requirement’s name and value are on the parse. Read-back is recorded. It does not by itself block the write.",
      input: "The official parse", output: "PASS, FAIL, or UNKNOWN",
      effect: "Run 064005, both designs: POWER 49 ≤ 60 W, LINK 12 ≤ 20 Mbps, STORE 64.8 ≤ 256 GB, TRACE 9/9. Run 074333 design A: all four PASS. Design B: TRACE 0/9 FAIL, POWER UNKNOWN." },
    { id: "review", row: "main", col: 8, owner: "Code", title: "⑦ Review", sub: "back to the agent",
      does: "Returns the review text, the run id, and the checks. The agent is told to compare the “Brief:” line with the confirmed brief before it presents the verdicts.",
      input: "The whole run", output: "The tool result",
      effect: "Run 071503 returned the default brief’s failures (POWER 78/60, LINK 18/8). The agent repeated that review and did not say the brief had changed. The later run’s brief matched." },
    { id: "empty", row: "side", col: 1, kind: "guard", owner: "Code", title: "Empty brief", sub: "refused", cond: "The fix",
      does: "When this flow is used as a tool, a missing brief stops the run. It does not fall through to the 2.2 demo brief.",
      input: "An empty argument", output: "A refusal",
      effect: "This is the fix for run 071503. That run is the measurement of the hole: the page default is over the 60 W and 8 Mbps limits on purpose." },
    { id: "trade", row: "side", col: 7, kind: "loop", owner: "Model, then code", title: "Trade-offs", sub: "only if a check fails",
      does: "If a check fails, the model proposes alternatives from the catalog. Code recomputes them. The 60 W limit is not a proposal.",
      input: "The failing checks", output: "Proposals, marked feasible or not",
      effect: "Run 064005 did not need them: no check failed. Run 074333 design B failed TRACE; the gate, not a trade-off, kept it out of memory." },
  ],
  edges: [
    { from: "brief", to: "mem" }, { from: "mem", to: "req" }, { from: "req", to: "write" }, { from: "write", to: "pilot" },
    { from: "pilot", to: "align" }, { from: "align", to: "checks" }, { from: "checks", to: "review" },
    { from: "rules", to: "write", kind: "feed", route: "v" },
    { from: "template", to: "write", kind: "feed", route: "v" },
    { from: "examples", to: "write", kind: "feed", route: "v", label: "examples" },
    { from: "brief", to: "empty", kind: "loop", route: "v", label: "argument empty" },
    { from: "checks", to: "trade", kind: "loop", route: "v", label: "a check fails" },
  ],
};

const ARCH_PATTERNS = [
  { id: "single", name: "Single agent", built: true, one: "One model, one call, no tool." },
  { id: "react", name: "ReAct", built: true, one: "One model loops: think, tool, result." },
  { id: "plan", name: "Plan and execute", built: false, one: "A planner writes the steps. A cheaper model follows them." },
  { id: "multi", name: "Multi-agent", built: false, one: "Several agents, different tools, hand work to each other." },
  { id: "router", name: "Router + skill", built: false, one: "A classifier picks one existing skill." },
  { id: "board", name: "Blackboard", built: false, one: "Agents wake up when a shared board changes." },
  { id: "graph", name: "Graph workflow", built: true, one: "The program orders the steps. A branch is a condition." },
];

const ARCH_ROWS = [
  { id: "p03", name: "Direct model chat · P0–P3", where: "Project 1", marks: { single: "on", graph: "on" },
    say: "One picture, four highlights. Your words go in as written and the conversation continues (decision 036). P0 answers once. P1 adds the repair loop from the official Pilot's complete error list. P2 adds an outline when you ask for a model. P3 adds retrieval of official examples with your own words. The program orders those steps; the model fills them.",
    shape: [["P0 write once", ""], ["P1 repair", "loop"], ["P2 outline", ""], ["P3 retrieve", ""]] },
  { id: "sand", name: "OpenCode and Claude Code sandbox chat", where: "Project 2", marks: { react: "on" },
    say: "One model loops: write or read a file, or run ./validate, then read the result. No second agent and no project memory. One sandbox and one agent session per chat, so “change the last one” has something to change. Nothing here is scored, so the chat runs while this results page is up (decision 036).",
    shape: [["Model", "loop"], ["File or ./validate", ""], ["Result", ""], ["Model again", "loop"]] },
  { id: "pilot", name: "Langflow Agent, Pilot only chat", where: "Project 2", marks: { react: "on" },
    say: "Langflow’s Agent keeps the last 30 messages and may call one tool, the official Pilot. It does not search memory or run a design. This chat runs while port 8770 is up.",
    shape: [["Last 30 messages", ""], ["Agent", "loop"], ["Official Pilot", ""], ["Answer", ""]] },
  { id: "mem", name: "OpenCode with memory · Langflow Agent with memory", where: "Projects 3 and 4", marks: { react: "on", graph: "in" },
    say: "The outer model chooses the cards and the conversation continues. One card, run the design, is a fixed graph: memory, requirements, two designs, Pilot, alignment, four checks, trade-offs only if a check fails. Writing each design is another ReAct loop, sandboxed OpenCode with ./validate. That inner sandbox needs port 8770 stopped.",
    shape: [["Outer ReAct", "loop"], ["Chooses a card", ""], ["Design graph", ""], ["Inner ./validate", "loop"]] },
  { id: "pipe", name: "Design agent flow and the four tool flows", where: "Projects 5 and 6", marks: { graph: "on" },
    say: "Not a chat box. Cards run in order. Trade-offs are a branch. Step 8 waits for a person. The memory chats call the four tools in project 5.",
    shape: [["Memory", ""], ["Requirements", ""], ["Designs", ""], ["Checks", ""], ["Person at 8", ""]] },
];

const ARCH_PROPOSALS = [
  { id: "plan", name: "Plan and execute",
    why: "Numbered requirements are one fixed card. No model writes a step list for a cheaper model to follow.",
    build: "After memory search, one model call returns JSON: devices, limits, missing numbers. Code stops if a limit is missing. The cards that already exist then run in today’s order. The plan must not skip the Pilot or the four checks." },
  { id: "multi", name: "Multi-agent",
    why: "The outer model calls the pipeline. OpenCode writes the files. They do not assign work to each other.",
    build: "Keep sandboxed OpenCode as the only writer. After the four checks, one reviewer call sees the check results and the two package names. Give it no file tool and no memory write." },
  { id: "router", name: "Router + skill",
    why: "Nothing classifies the message. A person picks the task type, or the same model both understands you and picks the tool.",
    build: "One flow, Chat router. One classification call, then a conditional router starts a chat that already exists. If the label is weak, stay on the memory assistant." },
  { id: "board", name: "Blackboard",
    why: "Approved designs can be searched later. During one design, cards pass a message forward. Nothing wakes up because a shared board changed.",
    build: "Use the run record as the board. Each design card writes only its own section. The outer agent reads that record. A card runs when its inputs are present. Do not add agents that poll the board." },
];

function renderArch(host) {
  if (!host) return;
  let selected = "mem";
  const head = ARCH_PATTERNS.map((p) => `<div class="arch-h ${p.built ? "on" : "off"}"><button type="button" data-arch="${p.id}">${esc(p.name)}<small>${p.built ? "Built" : "Not built"}</small></button></div>`).join("");
  const body = ARCH_ROWS.map((row) => {
    const cells = ARCH_PATTERNS.map((p) => {
      const mark = row.marks[p.id] || "";
      const label = mark === "on" ? "This chat" : mark === "in" ? "Inside a tool" : "";
      return `<div class="arch-cell ${mark}"><button type="button" data-row="${row.id}" data-arch="${p.id}">${label}</button></div>`;
    }).join("");
    return `<div class="arch-name"><button type="button" data-row="${row.id}">${esc(row.name)}<small>${esc(row.where)}</small></button></div>${cells}`;
  }).join("");
  host.innerHTML = `<div class="arch-grid"><div></div>${head}${body}</div><div class="arch-detail"></div><div class="prop-grid"></div>`;
  const detail = $(".arch-detail", host);
  const props = $(".prop-grid", host);
  function paint() {
    const row = ARCH_ROWS.find((r) => r.id === selected) || ARCH_ROWS[0];
    for (const el of $$(".arch-name, .arch-cell", host)) {
      const btn = $("button", el);
      el.classList.toggle("is-sel", btn && btn.dataset.row === selected);
    }
    const shape = row.shape.map(([t, k]) => `<span class="${k}">${esc(t)}</span>`).join('<em>→</em>');
    detail.innerHTML = `<article><span class="q">${esc(row.where)}</span><b>${esc(row.name)}</b><p>${esc(row.say)}</p><div class="arch-shapes">${shape}</div></article>
      <article><span class="q">Marks on this row</span><b>${ARCH_PATTERNS.filter((p) => row.marks[p.id]).map((p) => p.name).join(" · ") || "None"}</b><p>${ARCH_PATTERNS.filter((p) => row.marks[p.id]).map((p) => `${p.name}: ${p.one}`).join(" ")}</p></article>`;
  }
  props.innerHTML = ARCH_PROPOSALS.map((p) => `<article class="prop"><b>${esc(p.name)} · not built</b><p>${esc(p.why)}</p><p style="margin-top:6px"><b style="display:inline;color:var(--navy)">Add: </b>${esc(p.build)}</p></article>`).join("");
  host.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-row]");
    if (!btn || !host.contains(btn)) return;
    selected = btn.dataset.row;
    paint();
  });
  paint();
}

const P03 = {
  id: "p03", cols: 7, nowTitle: "How this approach runs",
  tags: { p0: "P0", p1: "P1", p2: "P2", p3: "P3" },
  filters: [["", "All"], ["p0", "P0 one-shot"], ["p1", "P1 repair"], ["p2", "P2 outline"], ["p3", "P3 retrieval"]],
  captions: {
    p0: "<b>P0.</b> Write once. The Pilot parses a SysML answer once and does not send the errors back.",
    p1: "<b>P1.</b> P0, plus the repair loop: the full error list goes back into the same conversation until the parse passes or the round cap is hit. No outline and no retrieval.",
    p2: "<b>P2.</b> P1, plus one outline call before the model writes SysML. No retrieval.",
    p3: "<b>P3.</b> P2, plus retrieval of official SysML examples before the outline. Not MaritimeISR.",
  },
  rows: [{ id: "src", label: "What it reads", hint: "P3 only" }, { id: "main", label: "Every message", hint: "the program picks the step" }],
  nodes: [
    { id: "lib", row: "src", col: 2, kind: "source", owner: "Official examples", title: "Example library", sub: "not our memory", papers: ["p3"],
      does: "MiniLM + FAISS over the official SysML examples, then one hop. MaritimeISR and the approved designs are not in this library.",
      input: "The task text", output: "Example cards",
      effect: "Only P3 reads this. P0, P1, and P2 do not." },
    { id: "in", row: "main", col: 1, kind: "human", owner: "Person", title: "Chat input", sub: "your words, as written", papers: ["p0", "p1", "p2", "p3"],
      does: "Your message goes to the model as written, with the last 30 messages of this session (decision 036). The flow you opened fixes P0, P1, P2, or P3. Nothing is scored.",
      input: "The message", output: "The task text",
      effect: "Project 1. Direct model chat · P0 through P3." },
    { id: "ret", row: "main", col: 2, owner: "Code", title: "Retrieve", sub: "before the outline", papers: ["p3"], cond: "P3 only",
      does: "The program retrieves. The query is the task text. There is no model call in this step, and the model cannot skip it on P3.",
      input: "The task text", output: "Notes for the outline",
      effect: "This is what P3 adds in front of P2." },
    { id: "outl", row: "main", col: 3, owner: "One model call", title: "Outline", sub: "parts, ports, attributes", papers: ["p2", "p3"], cond: "P2 and P3",
      does: "One call lists the parts, ports, connections, and attributes. It does not write SysML yet. On P3 the retrieved notes are in the prompt.",
      input: "The task, and on P3 the example cards", output: "A JSON outline",
      effect: "This is what P2 adds in front of P1. P0 and P1 skip it." },
    { id: "write", row: "main", col: 4, owner: "One model call", title: "Write", sub: "the answer", papers: ["p0", "p1", "p2", "p3"],
      does: "The model writes the answer. On P0 and P1 that is from the task alone. On P2 and P3 it also has the outline.",
      input: "The task, and the outline when there is one", output: "A first answer",
      effect: "Every approach reaches this step. The program calls it." },
    { id: "once", row: "main", col: 5, owner: "Official Pilot", title: "Validate once", sub: "no second try", papers: ["p0"], cond: "P0 only",
      does: "A SysML answer is parsed once. The error list is not sent back. Query, ambiguity, and round-trip answers are not parsed.",
      input: "The answer", output: "PASS or FAIL, kept as the answer",
      effect: "P0 stops here. P1, P2, and P3 use the repair node instead." },
    { id: "pilot", row: "main", col: 6, owner: "Official Pilot", title: "Repair from errors", sub: "same loop on P1, P2, P3", papers: ["p1", "p2", "p3"], cond: "If the parse fails",
      does: "The full error list is pasted back into the same conversation. Earlier versions and earlier error lists stay visible. The model rewrites until the parse passes or the round cap is hit (default 20).",
      input: "The answer", output: "The last rewrite",
      effect: "This is what P1 adds over P0. P2 and P3 keep this loop." },
    { id: "out", row: "main", col: 7, owner: "Langflow", title: "Chat output", sub: "not scored", papers: ["p0", "p1", "p2", "p3"],
      does: "Shows the last answer. A chat run has no answer key.",
      input: "The last text", output: "The playground message",
      effect: "The conversation continues; the next message can refer to this reply." },
  ],
  edges: [
    { from: "in", to: "write", papers: ["p0", "p1"], label: "P0 · P1" },
    { from: "in", to: "outl", papers: ["p2"] },
    { from: "in", to: "ret", papers: ["p3"] },
    { from: "ret", to: "outl", papers: ["p3"] },
    { from: "outl", to: "write", papers: ["p2", "p3"] },
    { from: "write", to: "once", papers: ["p0"], label: "P0" },
    { from: "once", to: "out", papers: ["p0"] },
    { from: "write", to: "pilot", papers: ["p1", "p2", "p3"], label: "P1–P3" },
    { from: "pilot", to: "out", papers: ["p1", "p2", "p3"] },
    { from: "lib", to: "ret", kind: "feed", route: "v", papers: ["p3"], label: "P3 only" },
    { from: "pilot", to: "write", kind: "loop", papers: ["p1", "p2", "p3"], label: "errors back" },
  ],
};

const SAND = {
  id: "sand", cols: 4, nowTitle: "How this chat runs",
  tags: { p3: "May skip" },
  filters: [["", "All"], ["p3", "May skip"]],
  captions: { p3: "<b>May skip.</b> The model decides whether to read, write, or run ./validate. It can also answer without a tool." },
  rows: [{ id: "main", label: "Every message", hint: "one sandbox per chat" }, { id: "tools", label: "Tools it may call", hint: "files and ./validate" }],
  nodes: [
    { id: "in", row: "main", col: 1, kind: "human", owner: "Person", title: "Chat input", sub: "saved as requirements.md",
      does: "Your text is written as input/requirements.md of a fresh task folder. The previous message is not in that folder.",
      input: "The message", output: "One task folder",
      effect: "Project 2. OpenCode in the sandbox chat, and Claude Code in the sandbox chat. They run while port 8770 is up: a conversation is not scored (decision 036)." },
    { id: "agent", row: "main", col: 2, owner: "One model", title: "OpenCode or Claude Code", sub: "ReAct loop",
      does: "One model in the bubblewrap sandbox. It chooses the next action: read a file, write a file, or run ./validate. Then it reads the result and chooses again. There is no second agent.",
      input: "The task folder and AGENTS.md", output: "answer.md, or the last message",
      effect: "Single-agent ReAct. The loop count is not fixed." },
    { id: "out", row: "main", col: 4, owner: "Langflow", title: "Chat output", sub: "not scored",
      does: "Returns the agent's reply. The sandbox and the agent's own session stay for this chat, so the next message can say “change the last one”.",
      input: "answer.md", output: "The playground message",
      effect: "No project memory." },
    { id: "read", row: "tools", col: 1, owner: "Tool", title: "Read a file", sub: "in the sandbox", papers: ["p3"], cond: "If it chooses",
      does: "Reads a file in the task folder. The repository and the answer keys are not in the sandbox.",
      input: "A path in the task folder", output: "File text",
      effect: "Optional. The model may skip it." },
    { id: "edit", row: "tools", col: 2, owner: "Tool", title: "Write a file", sub: "the SysML", papers: ["p3"], cond: "If it chooses",
      does: "Writes or edits a file in the task folder. The next ./validate reads that file.",
      input: "The model’s edit", output: "A file",
      effect: "Optional." },
    { id: "val", row: "tools", col: 3, owner: "Tool", title: "./validate", sub: "official Pilot", papers: ["p3"], cond: "If it chooses",
      does: "The sandbox wrapper around the official Pilot. The model sees PASS or FAIL and the diagnostics, then decides whether to edit again.",
      input: "The package name and the files", output: "PASS or FAIL",
      effect: "This is the act step of the ReAct loop." },
  ],
  edges: [
    { from: "in", to: "agent" }, { from: "agent", to: "out", label: "then answers" },
    { from: "agent", to: "read", kind: "side", route: "v", label: "may call" },
    { from: "agent", to: "edit", kind: "side", route: "v" },
    { from: "agent", to: "val", kind: "side", route: "v" },
    { from: "val", to: "agent", kind: "loop", label: "result" },
  ],
};

const PILOT = {
  id: "pilotc", cols: 4, nowTitle: "How this chat runs",
  tags: { p3: "May skip" },
  filters: [["", "All"], ["p3", "May skip"]],
  captions: { p3: "<b>May skip.</b> The only tool is the official Pilot. The agent can answer from the last 30 messages without calling it." },
  rows: [{ id: "src", label: "What it reads", hint: "the conversation" }, { id: "main", label: "Every message", hint: "one agent" }],
  nodes: [
    { id: "hist", row: "src", col: 2, kind: "source", owner: "This playground", title: "Last 30 messages", sub: "no project memory",
      does: "Langflow keeps the recent turns of this playground session. It does not know MaritimeISR or the approved designs.",
      input: "Earlier messages in this chat", output: "Context for the agent",
      effect: "This is why you can say “change the last answer” here, and not in P0 or the sandbox chats." },
    { id: "in", row: "main", col: 1, kind: "human", owner: "Person", title: "Chat input", sub: "any wording",
      does: "You write in the playground. There is no task-type dropdown.",
      input: "The message", output: "The agent’s input",
      effect: "Project 2, Langflow Agent, Pilot only chat. It runs while port 8770 is up." },
    { id: "agent", row: "main", col: 2, owner: "Langflow Agent", title: "Chooses the Pilot", sub: "qwen3.8-flash · ReAct",
      does: "One agent. It may call the Pilot on text it wrote, read the diagnostics, and call it again. It may also answer with no tool.",
      input: "The message and the last 30 turns", output: "An answer, after zero or more Pilot calls",
      effect: "Single-agent ReAct. One tool." },
    { id: "tool", row: "main", col: 3, owner: "One tool", title: "Official Pilot", sub: "may skip", papers: ["p3"], cond: "If it chooses",
      does: "Saves the pasted SysML and parses it. Returns PASS or FAIL and the diagnostics.",
      input: "SysML text", output: "The Pilot result",
      effect: "The only card on this chat." },
    { id: "out", row: "main", col: 4, owner: "Langflow", title: "Chat output", sub: "not scored",
      does: "The playground reply. Nothing is written to project memory.",
      input: "The agent’s text", output: "The message you read",
      effect: "No design pipeline." },
  ],
  edges: [
    { from: "in", to: "agent" }, { from: "agent", to: "out", label: "then answers" },
    { from: "hist", to: "agent", kind: "feed", route: "v", label: "30 messages" },
    { from: "agent", to: "tool", kind: "side", label: "may call" },
    { from: "tool", to: "agent", kind: "loop", label: "PASS or FAIL" },
  ],
};

const MEM = {
  id: "memc", cols: 7, nowTitle: "How this chat runs",
  tags: { p3: "May skip", p2: "Inside the design" },
  filters: [["", "All"], ["p3", "May skip"], ["p2", "Inside the design"]],
  captions: {
    p3: "<b>May skip.</b> The outer model chooses which card to call. It can call none.",
    p2: "<b>Inside the design.</b> These cards run left to right only when the model calls “run the design”. Writing each design is another ReAct loop.",
  },
  rows: [
    { id: "main", label: "Every message", hint: "the conversation continues" },
    { id: "tools", label: "Cards it may call", hint: "ReAct" },
    { id: "graph", label: "Inside “run the design”", hint: "a fixed graph" },
  ],
  nodes: [
    { id: "in", row: "main", col: 1, kind: "human", owner: "Engineer", title: "Message", sub: "projects 3 and 4",
      does: "You talk as you would to a colleague: ask what exists, describe a need, confirm a brief, or decide. The session keeps the earlier turns.",
      input: "The message", output: "The outer agent’s context",
      effect: "OpenCode with memory chat, and the three Langflow Agent with memory chats. Same tools. The outer harness differs." },
    { id: "agent", row: "main", col: 2, owner: "One model", title: "Chooses a card", sub: "ReAct",
      does: "One model decides which card to call, or answers with none. It does not walk the cards in order.",
      input: "The message and the session", output: "Zero or more tool calls, then a reply",
      effect: "Project 3’s outer model is OpenCode. Project 4’s outer model is Langflow’s Agent. Both are one ReAct loop." },
    { id: "out", row: "main", col: 7, owner: "The same model", title: "Reply", sub: "after the cards",
      does: "The playground message. It is supposed to quote tool results and not invent a number.",
      input: "Tool results, or the conversation", output: "The answer",
      effect: "The conversation continues, so the next message can refer to this one." },
    { id: "search", row: "tools", col: 1, owner: "A flow", title: "Memory search", sub: "may skip", papers: ["p3"], cond: "If it chooses",
      does: "Library, MiniLM + FAISS seeds, one hop, cards. No model in that flow.",
      input: "A few search words", output: "Cards with source and score",
      effect: "MaritimeISR and approved designs. Not the official-example library used by P3." },
    { id: "valid", row: "tools", col: 2, owner: "A flow", title: "Validate SysML", sub: "official Pilot", papers: ["p3"], cond: "If it chooses",
      does: "Saves pasted text and runs the official Pilot.",
      input: "SysML text", output: "PASS or FAIL",
      effect: "Optional." },
    { id: "pipe", row: "tools", col: 3, owner: "A flow", title: "Run the design", sub: "opens the bottom row", papers: ["p3", "p2"], cond: "If you confirmed",
      does: "Starts the fixed graph on the bottom row. Needs port 8770 stopped, because the writers are sandboxed OpenCode.",
      input: "The confirmed brief, word for word", output: "The review and the run id",
      effect: "This is the dashed “inside a tool” cell on the grid above." },
    { id: "write", row: "tools", col: 5, kind: "human", owner: "A flow · pauses", title: "Write to memory", sub: "after you approve", papers: ["p3"], cond: "If you name a design",
      does: "Pauses for approval, then checks the Pilot and the four checks. A miss is not written.",
      input: "Run id and design A or B", output: "A memory line, or a refusal",
      effect: "Optional. The agent is not supposed to call it before you decide." },
    { id: "mem", row: "graph", col: 1, owner: "Code", title: "Memory", sub: "fixed first step", papers: ["p2"],
      does: "The design graph starts by reading memory. The outer model does not reorder this.",
      input: "The brief", output: "Related cards",
      effect: "Graph workflow, inside the one tool." },
    { id: "req", row: "graph", col: 2, owner: "One model call", title: "Requirements", sub: "numbered", papers: ["p2"],
      does: "One call writes numbered requirements from the brief and the cards. Missing numbers become questions.",
      input: "Brief and cards", output: "Requirements",
      effect: "A fixed step, not a plan the executor can reorder." },
    { id: "des", row: "graph", col: 3, owner: "Sandboxed OpenCode", title: "Designs A and B", sub: "another ReAct loop", papers: ["p2"],
      does: "A second OpenCode, in a sandbox, writes each design. It loops on ./validate. The outer model does not write the files.",
      input: "The requirements", output: "Two packages",
      effect: "ReAct nested inside the graph." },
    { id: "chk", row: "graph", col: 5, owner: "Code", title: "Pilot, align, four checks", sub: "then a branch", papers: ["p2"],
      does: "The official Pilot, then alignment, then POWER, LINK, STORE, and TRACE. Trade-offs run only if a check fails.",
      input: "The two designs", output: "Pass or fail per check",
      effect: "The branch is code." },
    { id: "trade", row: "graph", col: 6, owner: "One model call", title: "Trade-offs", sub: "only if a check fails", papers: ["p2"], cond: "Only if needed",
      does: "Three options, then the catalog recomputes. A passing design skips this node.",
      input: "The failed check", output: "Options",
      effect: "Optional inside the graph." },
  ],
  edges: [
    { from: "in", to: "agent" }, { from: "agent", to: "out", label: "then answers" },
    { from: "agent", to: "search", kind: "side", route: "v", label: "may call" },
    { from: "agent", to: "valid", kind: "side", route: "v" },
    { from: "agent", to: "pipe", kind: "side", route: "v" },
    { from: "agent", to: "write", kind: "side", route: "v" },
    { from: "pipe", to: "mem", kind: "feed", route: "v", label: "starts the graph" },
    { from: "mem", to: "req" }, { from: "req", to: "des" }, { from: "des", to: "chk" },
    { from: "chk", to: "trade", kind: "loop", label: "only if a check fails" },
  ],
};

const DESIGN = {
  id: "designg", cols: 8, nowTitle: "How this flow runs",
  tags: { p3: "Only if a check fails" },
  filters: [["", "All"], ["p3", "Only if a check fails"]],
  captions: { p3: "<b>Only if a check fails.</b> Trade-offs are the branch. A design that passes all four checks does not take it." },
  rows: [{ id: "src", label: "What it reads", hint: "memory" }, { id: "main", label: "Every run", hint: "fixed order" }],
  nodes: [
    { id: "lib", row: "src", col: 1, kind: "source", owner: "Memory", title: "MaritimeISR and approved designs", sub: "the library",
      does: "The card library the search step reads. Not the official-example library.",
      input: "Approved designs and MaritimeISR", output: "Cards",
      effect: "Projects 5 and 6. The memory chats call this graph. It is not itself a chat." },
    { id: "search", row: "main", col: 1, owner: "Code", title: "Search memory", sub: "no model",
      does: "MiniLM + FAISS seeds, then one hop.",
      input: "The brief", output: "Cards",
      effect: "Always first." },
    { id: "req", row: "main", col: 2, owner: "One model call", title: "Requirements", sub: "numbered",
      does: "One call. Missing numbers stay questions. The call does not invent them.",
      input: "Brief and cards", output: "Requirements",
      effect: "A fixed step." },
    { id: "ab", row: "main", col: 3, owner: "Sandboxed OpenCode", title: "Designs A and B", sub: "./validate loop",
      does: "Each design is a ReAct loop with the official Pilot as ./validate.",
      input: "The requirements", output: "Two packages",
      effect: "Needs port 8770 stopped." },
    { id: "pilot", row: "main", col: 4, owner: "Official Pilot", title: "Parse", sub: "syntax only",
      does: "Parses each package. A legal file can still fail a later check.",
      input: "The packages", output: "PASS or FAIL",
      effect: "Always." },
    { id: "align", row: "main", col: 5, owner: "Code, then one call", title: "Align", sub: "names checked by code",
      does: "A model proposes pairs with MaritimeISR. Code checks the names.",
      input: "The designs and memory", output: "Pairs",
      effect: "Always." },
    { id: "checks", row: "main", col: 6, owner: "Code", title: "Four checks", sub: "power, link, store, trace",
      does: "Reads the parsed watts and rates. Actual must be within the limit. The model does not grade these.",
      input: "The parsed model", output: "Four results",
      effect: "A fail opens the trade-off branch." },
    { id: "person", row: "main", col: 8, kind: "human", owner: "Person", title: "Step 8", sub: "approve, reject, send back",
      does: "The run pauses. Approve then meets the gate: Pilot PASS and all four checks PASS.",
      input: "The review", output: "A decision",
      effect: "The graph waits here. It does not continue by itself." },
    { id: "trade", row: "main", col: 7, owner: "One model call", title: "Trade-offs", sub: "only if a check fails", papers: ["p3"], cond: "Only if needed",
      does: "Three options. Code recomputes from the catalog. The failed watts are not quietly edited into a pass.",
      input: "The failed check", output: "Options back into the review",
      effect: "Skipped when every check passes." },
  ],
  edges: [
    { from: "search", to: "req" }, { from: "req", to: "ab" }, { from: "ab", to: "pilot" },
    { from: "pilot", to: "align" }, { from: "align", to: "checks" }, { from: "checks", to: "person" },
    { from: "lib", to: "search", kind: "feed", route: "v", label: "library" },
    { from: "checks", to: "trade", kind: "side", label: "only if a check fails" },
    { from: "trade", to: "person", kind: "loop" },
  ],
};

const PLAN = {
  id: "planp", cols: 5, nowTitle: "Proposal, not in Langflow",
  rows: [{ id: "main", label: "Proposed", hint: "not built" }],
  nodes: [
    { id: "search", row: "main", col: 1, owner: "Already built", title: "Search memory", sub: "stays first",
      does: "The design graph’s current first card. This proposal does not replace it.",
      input: "The brief", output: "Cards", effect: "Exists today." },
    { id: "plan", row: "main", col: 2, owner: "Would be new", title: "One plan call", sub: "JSON",
      does: "One model call returns devices, limits, and missing numbers. Code stops if a limit is missing. The plan is shown to the engineer.",
      input: "Brief and cards", output: "A step list", effect: "Not built. This is the plan-and-execute piece." },
    { id: "rest", row: "main", col: 3, owner: "Already built", title: "Today’s cards, same order", sub: "requirements through checks",
      does: "Requirements, two designs, Pilot, alignment, four checks. The plan must not skip the Pilot or the checks, and it must not reorder them.",
      input: "The plan", output: "The review", effect: "The executor is the graph we already run, not a cheaper model inventing steps." },
    { id: "person", row: "main", col: 5, kind: "human", owner: "Person", title: "Still step 8", sub: "unchanged",
      does: "Approve, reject, or send back, as today.",
      input: "The review", output: "A decision", effect: "Not a new role." },
  ],
  edges: [{ from: "search", to: "plan" }, { from: "plan", to: "rest" }, { from: "rest", to: "person" }],
};

const MULTI = {
  id: "multip", cols: 4, nowTitle: "Proposal, not in Langflow",
  rows: [{ id: "main", label: "Proposed", hint: "two roles, one caller" }],
  nodes: [
    { id: "outer", row: "main", col: 1, owner: "Already built", title: "Outer agent", sub: "only calls",
      does: "The memory chat’s outer model. In this proposal it does not write the design and it does not grade it. It calls the writer, then the reviewer, then shows the review.",
      input: "The confirmed brief", output: "Tool calls", effect: "Exists today as the caller." },
    { id: "writer", row: "main", col: 2, owner: "Already built", title: "Sandboxed OpenCode", sub: "the only writer",
      does: "Writes the files with ./validate, as it does now. The reviewer cannot edit those files.",
      input: "The requirements", output: "Two packages", effect: "Exists today inside the design graph." },
    { id: "review", row: "main", col: 3, owner: "Would be new", title: "Reviewer call", sub: "no file tool",
      does: "One call. It sees the four check results and the two package names. It has no file tool and no memory write.",
      input: "Check results and package names", output: "A short review", effect: "Not built. This is the second role." },
    { id: "show", row: "main", col: 4, owner: "Already built", title: "Outer agent presents it", sub: "no second conversation",
      does: "The outer agent shows that review. The two roles do not message each other.",
      input: "The review", output: "The playground message", effect: "One caller." },
  ],
  edges: [{ from: "outer", to: "writer" }, { from: "writer", to: "review" }, { from: "review", to: "show" }],
};

const ROUTER = {
  id: "routerp", cols: 6, nowTitle: "Proposal, not in Langflow",
  tags: { p3: "One of these" },
  filters: [["", "All"], ["p3", "One of these"]],
  captions: { p3: "<b>One of these.</b> The router starts one existing chat. A weak label stays on the memory assistant." },
  rows: [{ id: "main", label: "Proposed", hint: "not built" }],
  nodes: [
    { id: "in", row: "main", col: 1, kind: "human", owner: "Person", title: "One message", sub: "no dropdown",
      does: "You would type once. You would not pick P0 or the sandbox yourself, unless you still open that flow directly.",
      input: "The message", output: "Text for the classifier", effect: "The chats themselves already exist." },
    { id: "cls", row: "main", col: 2, owner: "Would be new", title: "One classification call", sub: "a label",
      does: "Labels the message as write-once, repair, sandbox, Pilot-only, or memory assistant.",
      input: "The message", output: "One label", effect: "Not built." },
    { id: "p0", row: "main", col: 3, owner: "Already built", title: "P0 or P1–P3", sub: "one skill", papers: ["p3"], cond: "One label",
      does: "The direct-model chats in project 1.",
      input: "The message", output: "That chat’s answer", effect: "Exists today." },
    { id: "sand", row: "main", col: 4, owner: "Already built", title: "Sandbox or Pilot-only", sub: "one skill", papers: ["p3"], cond: "One label",
      does: "A project 2 chat. The sandbox ones still need port 8770 stopped.",
      input: "The message", output: "That chat’s answer", effect: "Exists today." },
    { id: "mem", row: "main", col: 5, owner: "Already built", title: "Memory assistant", sub: "the fallback", papers: ["p3"], cond: "Weak label stays here",
      does: "Projects 3 and 4. If the label is weak, the router does not guess. It stays here.",
      input: "The message", output: "That chat’s answer", effect: "Exists today." },
  ],
  edges: [
    { from: "in", to: "cls" },
    { from: "cls", to: "p0", kind: "side", label: "one of these" },
    { from: "cls", to: "sand", kind: "side" },
    { from: "cls", to: "mem", kind: "main", label: "or stay" },
  ],
};

const BOARD = {
  id: "boardp", cols: 5, nowTitle: "Proposal, not in Langflow",
  rows: [{ id: "main", label: "Proposed", hint: "one record, no polling" }],
  nodes: [
    { id: "rec", row: "main", col: 1, kind: "source", owner: "Already stored", title: "The run record", sub: "the board",
      does: "The record a design run already writes. In this proposal every card reads it and writes only its own section.",
      input: "The run id", output: "Brief, requirements, designs, Pilot, checks", effect: "The file exists. The cards do not yet treat it as the only state." },
    { id: "cards", row: "main", col: 2, owner: "Already built", title: "Design cards", sub: "write one section each",
      does: "Search writes the cards it found. Requirements writes the numbered list. Designs write A and B. The Pilot and the four checks write their results. A card runs when its inputs are on the record.",
      input: "Its section of the record", output: "Its own section", effect: "Not built as a board. Today the cards pass a message forward." },
    { id: "outer", row: "main", col: 4, owner: "Already built", title: "Outer agent reads it", sub: "does not poll",
      does: "The memory chat reads the same record instead of a long tool message. No extra agent wakes up because a field changed.",
      input: "The record", output: "The reply", effect: "Not built." },
  ],
  edges: [
    { from: "rec", to: "cards", kind: "feed", label: "read" },
    { from: "cards", to: "rec", kind: "loop", label: "write one section" },
    { from: "rec", to: "outer", label: "then the reply" },
  ],
};

function boot() {
  makeFlow($("#flow-course"), COURSE);
  makeFlow($("#flow-ours"), OURS);
  makeFlow($("#flow-search"), SEARCH);
  makeFlow($("#flow-validate"), VALIDATE);
  makeFlow($("#flow-write"), WRITE);
  makeFlow($("#flow-pipe"), PIPE);
  renderArch($("#arch"));
  makeFlow($("#flow-p03"), P03);
  makeFlow($("#flow-sand"), SAND);
  makeFlow($("#flow-pilot"), PILOT);
  makeFlow($("#flow-mem"), MEM);
  makeFlow($("#flow-design"), DESIGN);
  makeFlow($("#flow-plan"), PLAN);
  makeFlow($("#flow-multi"), MULTI);
  makeFlow($("#flow-router"), ROUTER);
  makeFlow($("#flow-board"), BOARD);
  const links = $$("#toc a");
  const byId = Object.fromEntries(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const seen = new Map();
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) seen.set(e.target.id, e.isIntersecting ? e.boundingClientRect.top : null);
    const visible = [...seen.entries()].filter(([, top]) => top !== null).sort((a, b) => a[1] - b[1]);
    if (!visible.length) return;
    links.forEach((a) => a.classList.remove("on"));
    const on = byId[visible[0][0]];
    if (on) on.classList.add("on");
  }, { rootMargin: "-10% 0px -55% 0px" });
  Object.keys(byId).forEach((id) => { const el = document.getElementById(id); if (el) io.observe(el); });
}

boot();
