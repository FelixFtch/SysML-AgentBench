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
      const on = !!paper && ((byId[from].papers || []).includes(paper) || (byId[to].papers || []).includes(paper));
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
      paths.push(`<path class="wire ${e.kind}" data-from="${e.from}" data-to="${e.to}" d="${d}" marker-end="url(#${spec.id}-m-${e.kind})"/>`);
      if (e.label) labels.push(`<span class="wlabel ${e.kind}" data-from="${e.from}" data-to="${e.to}" style="left:${r.lab[0].toFixed(1)}px;top:${r.lab[1].toFixed(1)}px">${esc(e.label)}</span>`);
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

function boot() {
  makeFlow($("#flow-course"), COURSE);
  makeFlow($("#flow-ours"), OURS);
  makeFlow($("#flow-search"), SEARCH);
  makeFlow($("#flow-validate"), VALIDATE);
  makeFlow($("#flow-write"), WRITE);
  makeFlow($("#flow-pipe"), PIPE);
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
