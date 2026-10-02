"use strict";
const $ = (id) => document.getElementById(id);
let currentRecord = null;
let submitting = false;
let parsedElements = [];
let selectedId = new URLSearchParams(location.search).get("run");
const pretty = (value, fallback = "Not returned") => value === undefined || value === null ? fallback : typeof value === "string" ? value : JSON.stringify(value, null, 2);

function message(text = "") {
  $("message").textContent = text;
  $("message").hidden = !text;
}
function badge(element, value) {
  element.textContent = pretty(value, "UNKNOWN");
  const status = String(value || "UNKNOWN").toUpperCase();
  element.className = "badge " + (status === "PASS" || status === "VALID" ? "good" : /FAIL|ERROR|INVALID/.test(status) ? "bad" : /RUNNING|UNKNOWN|UNAVAILABLE/.test(status) ? "warn" : "");
}
async function request(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`);
    error.data = data;
    throw error;
  }
  return data;
}
function render(record) {
  currentRecord = record;
  selectedId = record.record_id;
  if (selectedId) history.replaceState(null, "", "?run=" + encodeURIComponent(selectedId));
  const result = record.result || {};
  $("project-context").textContent = result.reference_name ? "Public reference model · Sources, parsing and review evidence" : "Observation data subsystem · Models, checks and evidence";
  $("case-notice").textContent = result.reference_name ? "Public source import. Real official SysML parsing. Source provenance is retained; static validation does not establish engineering acceptance or hardware performance. Marine gateway budgets are not applied to this reference." : "Synthetic engineering case. Real SysML parsing. Case parameters exercise the workflow; they are not controlled RTX product data. Parsing and engineering checks are reported separately. Execution complete does not mean verification passed.";
  const sysml = result.sysml || {};
  $("run-title").textContent = record.request?.case_name || record.request?.reference_name || "Engineering run record";
  const approval = typeof record.request?.preview_approved === "boolean" ? ` · Recorded P2 decision: ${record.request.preview_approved ? "approved" : "not approved"}` : "";
  $("run-meta").textContent = `${record.created_at || ""} · ${record.finished_at ? "Finished" : "Running"}${approval}`;
  badge($("record-status"), record.status);
  badge($("engine-status"), result.status || (record.status === "ERROR" ? "ERROR" : "UNKNOWN"));
  badge($("sysml-status"), typeof sysml === "object" ? sysml.status : sysml);
  $("run-id").textContent = "run_id: " + (result.run_id || record.record_id || "Not returned");
  $("model-path").textContent = result.model_path || "Engine did not return model_path";
  $("diagnostics").textContent = pretty(sysml.diagnostics, record.error || "Engine did not return diagnostics");
  $("manifest").textContent = pretty(result.source_manifest, "Engine did not return source_manifest");
  $("diff").textContent = pretty(result.diff, "Engine did not return diff");
  $("model-text").textContent = pretty(result.model_text, "Engine has not returned model source.");
  $("model-elements").textContent = pretty(result.model_elements, "Engine did not return model_elements");
  renderModel(result.model_elements);
  renderLineage(record);
  if (typeof window.updateHarborRun === "function") window.updateHarborRun(record);
  window.dispatchEvent(new CustomEvent("workbench:run", {detail: record}));
  $("raw-result").textContent = JSON.stringify(record, null, 2);
  $("export-link").hidden = !record.record_id;
  $("export-link").href = `/api/runs/${encodeURIComponent(record.record_id)}/export.zip`;
  const checks = result.checks;
  $("checks").replaceChildren();
  if (Array.isArray(checks)) {
    $("check-count").textContent = String(checks.length) + " checks";
    for (const check of checks) {
      const card = document.createElement("div"); card.className = "check";
      const heading = document.createElement("div"); heading.className = "check-heading";
      const title = document.createElement("strong"); title.textContent = check?.label || check?.name || check?.id || check?.check_id || "Engineering check";
      const state = document.createElement("span"); badge(state, check?.status);
      heading.append(title, state);
      const metric = document.createElement("p"); metric.className = "check-metric";
      if (typeof check?.actual === "number" && typeof check?.limit === "number") metric.textContent = `Actual ${check.actual} / limit ${check.limit} ${check.unit || ""}`;
      else metric.textContent = check?.detail || "Inspect the recorded evidence for this check.";
      const evidence = document.createElement("details"); evidence.className = "check-evidence";
      const summary = document.createElement("summary"); summary.textContent = "Inspect check evidence";
      const detail = document.createElement("pre"); detail.textContent = pretty(check);
      evidence.append(summary, detail);
      card.append(heading, metric, evidence); $("checks").append(card);
    }
    if (!checks.length) $("checks").textContent = "The engine returned no checks; this is not a passing result.";
  } else {
    $("check-count").textContent = "Not returned";
    $("checks").textContent = pretty(checks, "The engine has not returned checks.");
  }
  if (record.error || result.error) message(record.error || result.error);
}
function elementButton(element) {
  const button = document.createElement("button"); button.type = "button"; button.className = "element-button";
  const name = document.createElement("strong"); name.textContent = element.name || element.qualifiedName || element.id || "Unnamed element";
  const type = document.createElement("small"); type.textContent = pretty(element.type, "Unknown type");
  button.append(name, type); button.title = element.qualifiedName || element.id || "";
  button.addEventListener("click", () => {$("element-detail").textContent = pretty(element);});
  return button;
}
function renderTree() {
  const filter = $("model-filter").value.trim().toLocaleLowerCase();
  const target = $("model-tree"); target.replaceChildren();
  if (!parsedElements.length) { target.textContent = "This run returned no parsed elements."; return; }
  const byName = new Map(parsedElements.filter(e => e.qualifiedName).map(e => [e.qualifiedName, e]));
  const children = new Map();
  for (const element of parsedElements) {
    const key = typeof element.owner === "string" && byName.has(element.owner) ? element.owner : null;
    if (!children.has(key)) children.set(key, []);
    children.get(key).push(element);
  }
  if (filter) {
    const matches = parsedElements.filter(e => [e.name, e.qualifiedName, e.type].some(v => typeof v === "string" && v.toLocaleLowerCase().includes(filter)));
    for (const element of matches) target.append(elementButton(element));
    if (!matches.length) target.textContent = "No matching elements.";
    return;
  }
  const visited = new Set();
  function add(element, parent, depth) {
    const key = element.qualifiedName || element.id;
    if (visited.has(key)) return;
    visited.add(key);
    const owned = children.get(element.qualifiedName) || [];
    const node = document.createElement("div"); node.className = "tree-node";
    if (owned.length) {
      const details = document.createElement("details"); details.open = depth < 2;
      const summary = document.createElement("summary"); summary.append(elementButton(element));
      const branch = document.createElement("div"); branch.className = "tree-branch";
      owned.forEach(child => add(child, branch, depth + 1));
      details.append(summary, branch); node.append(details);
    } else node.append(elementButton(element));
    parent.append(node);
  }
  (children.get(null) || []).forEach(element => add(element, target, 0));
  // Cyclic or incomplete owner exports remain inspectable, without invented parents.
  parsedElements.filter(e => !visited.has(e.qualifiedName || e.id)).forEach(element => add(element, target, 0));
}
function renderModel(elements) {
  parsedElements = Array.isArray(elements) ? elements.filter(e => e && typeof e === "object") : [];
  renderTopology(parsedElements);
  $("model-filter").value = "";
  $("element-detail").textContent = "Select an element to inspect its actual parsed fields.";
  const parts = parsedElements.filter(e => /Part(Usage|Definition)/.test(String(e.type)));
  const connections = parsedElements.filter(e => /Connection|Connector|BindingConnector|FlowConnection/.test(String(e.type)));
  $("model-summary").textContent = `${parsedElements.length} named elements · ${parts.length} part usages/definitions · ${connections.length} connection elements. Hierarchy uses owner; endpoints use exported references. Unresolved relationships are not invented.`;
  renderTree();
  const container = $("model-connections"); container.replaceChildren();
  for (const element of connections) {
    const row = document.createElement("div"); row.className = "connection-row";
    row.append(elementButton(element));
    const endpoints = document.createElement("p");
    const related = Array.isArray(element.relatedFeature) ? element.relatedFeature : [];
    const ends = Array.isArray(element.connectorEnd) ? element.connectorEnd : [];
    endpoints.textContent = related.length ? "Related features: " + related.join(" ↔ ") : ends.length ? "Connector end references: " + ends.join(" ↔ ") + " (target features are not resolved in this view)" : "No endpoint references exported; inspect the raw element fields.";
    row.append(endpoints); container.append(row);
  }
  if (!connections.length) container.textContent = "No named connection elements in this export.";
}
function renderTopology(elements) {
  const box = $("model-topology"); box.replaceChildren();
  $("topology-section").hidden = true;
  const owner = elements.find(e => e.type === "PartDefinition" && e.qualifiedName === "MarineGateway::Gateway");
  if (!owner) return;
  const nodes = elements.filter(e => e.type === "PartUsage" && e.owner === owner.qualifiedName);
  const resolve = ref => typeof ref === "string" ? nodes.find(n => ref === n.qualifiedName || ref.startsWith(n.qualifiedName + ".")) : undefined;
  const edges = elements.filter(e => /Connection|Connector/.test(String(e.type)) && e.owner === owner.qualifiedName).flatMap(element => {
    const refs = element.relatedFeature || [];
    if (refs.length !== 2) return [];
    const source = resolve(refs[0]), target = resolve(refs[1]);
    return source && target ? [{element, source, target}] : [];
  });
  if (!nodes.length || !edges.length) return;
  const incoming = new Map(nodes.map(n => [n.qualifiedName, 0]));
  const rank = new Map(nodes.map(n => [n.qualifiedName, 0]));
  edges.forEach(e => incoming.set(e.target.qualifiedName, incoming.get(e.target.qualifiedName) + 1));
  const queue = nodes.filter(n => incoming.get(n.qualifiedName) === 0);
  for (let i = 0; i < queue.length; i++) {
    const node = queue[i];
    for (const edge of edges.filter(e => e.source === node)) {
      const name = edge.target.qualifiedName;
      rank.set(name, Math.max(rank.get(name), rank.get(node.qualifiedName) + 1));
      incoming.set(name, incoming.get(name) - 1);
      if (incoming.get(name) === 0) queue.push(edge.target);
    }
  }
  const columns = new Map();
  for (const node of nodes) {
    const column = rank.get(node.qualifiedName);
    if (!columns.has(column)) columns.set(column, []);
    columns.get(column).push(node);
  }
  const rows = Math.max(...Array.from(columns.values(), column => column.length));
  const width = (Math.max(...columns.keys()) + 1) * 158 + 20, height = Math.max(160, rows * 78 + 40);
  const positions = new Map();
  for (const [column, members] of columns) members.forEach((node, index) => positions.set(node.qualifiedName, {x:18 + column * 158, y:height / 2 + (index - (members.length - 1) / 2) * 78 - 22}));
  const ns = "http://www.w3.org/2000/svg";
  function svgElement(tag, attrs = {}) {
    const element = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([name, value]) => element.setAttribute(name, String(value)));
    return element;
  }
  const svg = svgElement("svg", {viewBox:`0 0 ${width} ${height}`, role:"img", "aria-label":"Gateway parts and connections derived from the official parsed model"});
  function select(element, target) {
    $("element-detail").textContent = pretty(element);
    svg.querySelectorAll(".topology-selected").forEach(item => item.classList.remove("topology-selected"));
    target.classList.add("topology-selected");
  }
  for (const edge of edges) {
    const a = positions.get(edge.source.qualifiedName), b = positions.get(edge.target.qualifiedName);
    const x1 = a.x + 132, y1 = a.y + 22, x2 = b.x, y2 = b.y + 22, middle = (x1 + x2) / 2;
    const group = svgElement("g", {class:"topology-edge", tabindex:"0", role:"button", "aria-label":edge.element.name});
    const path = `M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}`;
    group.append(svgElement("path", {d:path, class:"edge-hit"}), svgElement("path", {d:path, class:"edge-line"}));
    const title = svgElement("title"); title.textContent = edge.element.name + ": " + edge.element.relatedFeature.join(" ↔ "); group.append(title);
    group.addEventListener("click", () => select(edge.element, group));
    group.addEventListener("keydown", event => {if (event.key === "Enter") select(edge.element, group);});
    svg.append(group);
  }
  for (const node of nodes) {
    const position = positions.get(node.qualifiedName);
    const group = svgElement("g", {class:"topology-node", tabindex:"0", role:"button", "aria-label":node.name});
    group.append(svgElement("rect", {x:position.x, y:position.y, width:132, height:44, rx:7}));
    const label = svgElement("text", {x:position.x+66, y:position.y+26, "text-anchor":"middle"}); label.textContent = node.name; group.append(label);
    const title = svgElement("title"); title.textContent = node.qualifiedName; group.append(title);
    group.addEventListener("click", () => select(node, group));
    group.addEventListener("keydown", event => {if (event.key === "Enter") select(node, group);});
    svg.append(group);
  }
  box.append(svg); $("topology-section").hidden = false;
  $("topology-caption").textContent = `${nodes.length} actual part usages and ${edges.length} resolved connections. Layout follows exported endpoint order; lines do not claim verified runtime behavior. Select a part or line to inspect its parsed evidence below.`;
}
async function loadRecord(id) {
  message();
  try { render(await request("/api/runs/" + encodeURIComponent(id))); await Promise.all([refreshHistory(), refreshSources()]); }
  catch (error) { message(error.message); }
}
async function refreshHistory() {
  const data = await request("/api/history");
  $("history").replaceChildren();
  for (const run of data.runs || []) {
    const button = document.createElement("button"); button.type = "button";
    button.className = "history-item" + (run.record_id === selectedId ? " selected" : "");
    const title = document.createElement("strong"); title.textContent = run.request?.case_name || run.request?.reference_name || run.record_id;
    const meta = document.createElement("small"); meta.textContent = `${run.created_at} · ${run.status}`;
    button.append(title, meta); button.addEventListener("click", () => loadRecord(run.record_id));
    $("history").append(button);
  }
  if (!(data.runs || []).length) $("history").textContent = "No run records yet";
  return data.runs || [];
}
async function refreshSources() {
  const runQuery = selectedId ? "&record_id=" + encodeURIComponent(selectedId) : "";
  const data = await request("/api/sources?" + runQuery.slice(1));
  $("sources-list").replaceChildren();
  for (const file of data.files || []) {
    const button = document.createElement("button"); button.className = "source-item"; button.type = "button";
    button.textContent = `${file.path} (${file.size} B)`;
    button.addEventListener("click", async () => {
      try {
        const source = await request("/api/source?path=" + encodeURIComponent(file.path) + runQuery);
        $("source-title").textContent = source.path; $("source-text").textContent = source.text;
      } catch (error) { message(error.message); }
    });
    $("sources-list").append(button);
  }
  if (!(data.files || []).length) $("sources-list").textContent = "No displayable engineering text files are available.";
}
async function refreshStatus() {
  try {
    const status = await request("/api/status");
    const busy = Boolean(status.active_run);
    badge($("service-state"), busy ? "RUNNING" : status.engine_file_present ? "Local service connected" : "Engine not installed");
    $("project-root").textContent = "Project directory: " + status.project_root;
    $("run-button").disabled = submitting || busy;
    document.querySelectorAll(".reference-button").forEach(button => {button.disabled = submitting || busy;});
    $("run-button").textContent = busy || submitting ? "Tools running…" : "Run engineering checks";
    if (busy) $("run-progress").textContent = `Executing ${status.active_run.request?.case_name || status.active_run.request?.reference_name || "Engineering check"}. Waiting for real tool results.`;
    else if (!submitting) $("run-progress").textContent = "";
  } catch (error) {
    badge($("service-state"), "ERROR");
    $("run-progress").textContent = "Cannot connect to the local service; check its terminal.";
  }
}
$("run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submitting) return;
  message(); submitting = true; $("run-button").disabled = true; $("run-button").textContent = "Tools running…";
  $("run-progress").textContent = "Submitted. Waiting for real SysML tools and engineering checks.";
  const dataRate = $("data-rate").value, linkRate = $("link-rate").value;
  try {
    const record = await request("/api/run", {method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({case_name: $("case-name").value, data_rate_mbps: dataRate === "" ? null : Number(dataRate), link_mbps: linkRate === "" ? null : Number(linkRate), preview_approved: $("preview-approved").checked})});
    render(record);
  } catch (error) {
    if (error.data?.record_id) render(error.data);
    message(error.message);
  } finally {
    submitting = false;
    await Promise.allSettled([refreshHistory(), refreshSources(), refreshStatus()]);
  }
});
document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(tab => {const active = tab === button; tab.classList.toggle("active", active); tab.setAttribute("aria-pressed", String(active));});
  document.querySelectorAll(".view").forEach(view => {view.hidden = view.id !== "view-" + button.dataset.view;});
}));
document.querySelectorAll(".reference-button").forEach(button => button.addEventListener("click", async () => {
  if (submitting) return;
  submitting = true; message();
  $("reference-progress").textContent = "Running the real reference importer and SysML tools…";
  document.querySelectorAll(".reference-button").forEach(item => {item.disabled = true;});
  try {
    render(await request("/api/reference", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({reference_name: button.dataset.reference})}));
    $("reference-progress").textContent = "Execution finished. Inspect the actual checks and their limits.";
  } catch (error) {
    if (error.data?.record_id) render(error.data);
    message(error.message); $("reference-progress").textContent = "Reference execution failed.";
  } finally { submitting = false; await Promise.allSettled([refreshHistory(), refreshSources(), refreshStatus()]); }
}));
$("agent-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("agent-button").disabled = true;
  $("agent-result").textContent = "Connecting to the real agent…";
  try {
    const result = await request("/api/agent", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({message: $("agent-message").value, case_name: $("case-name").value, preview_approved: $("preview-approved").checked})});
    $("agent-result").textContent = pretty(result);
    if (result.record_id && result.request) render(result);
    await refreshHistory();
  } catch (error) { $("agent-result").textContent = "ERROR · " + error.message; }
  finally { $("agent-button").disabled = false; }
});
$("refresh-history").addEventListener("click", () => refreshHistory().catch(error => message(error.message)));
$("model-filter").addEventListener("input", renderTree);
$("refresh-sources").addEventListener("click", () => refreshSources().catch(error => message(error.message)));
$("copy-model").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText($("model-text").textContent); $("copy-model").textContent = "Copied"; setTimeout(() => {$("copy-model").textContent = "Copy";}, 1500); }
  catch { message("Automatic clipboard access is unavailable. Select and copy the model text manually."); }
});
// Architectural stages explain the code path; they never modify a case or submit a run.
const architectureStages = {
  sources: {
    title: "01 · Read & snapshot", owner: "Owner: Python engine / read-only source access",
    input: "A selected configuration in legacy.sqlite, requirement JSON, two supplier models and interface documents, plus explicit user overrides.",
    action: "Read actual database rows and controlled files. Record source identities and copy evidence into the new run directory.",
    output: "Source snapshots, row provenance and source-manifest.json with hashes. The original database is read-only; this is not an RTX production connector.",
    code: "Code: engine.py · snapshot_sources / models/render_model.py"
  },
  model: {
    title: "02 · Build SysML v2", owner: "Owner: deterministic Python renderer",
    input: "Source configuration, selected candidate structure, bounded data/link overrides, supplier packages and the explicit preview decision.",
    action: "Fill a versioned SysML template; declare requirements, parts, attributes and connections; import the separate payload and sharing-link models. Preserve links back to source records.",
    output: "MarineGateway.sysml, PayloadSupplier.sysml, SharingLinkSupplier.sysml, source_mapping.json and model hashes. This is real model source, but generation is template-based, not arbitrary LLM synthesis.",
    code: "Code: models/render_model.py · models/gateway.sysml.tmpl / Output: runs/<id>/model/"
  },
  parse: {
    title: "03 · Parse & link", owner: "Owner: official SysML v2 Pilot on Java 21",
    input: "The generated multi-file .sysml package and matching standard libraries from the pinned official release.",
    action: "Parse, resolve imported references and run static validation using the official Xtext/EMF implementation. Export actual semantic elements and model references.",
    output: "model.json, ast-elements.json, validation.json and tool logs. The viewer and checks use this export. A failed parse blocks calculations; the input database is never used as a fallback model.",
    code: "Code: toolchain/validate.py · toolchain/SysMLHeadless.java / Pinned toolchain: Pilot 2026-08, kernel 0.62.0"
  },
  checks: {
    title: "04 · Check & compare", owner: "Owner: independent Python checks, not the LLM",
    input: "Supported parsed values, unit expressions, scoped model connections, the fixed user decision and the latest valid baseline when available.",
    action: "Check storage, bandwidth, power, the supported unit and topology contracts, decision binding and static-warning review. Compare named elements and full model text with the baseline.",
    output: "checks.json and diff.json with evidence. Parsing PASS and budget PASS do not imply acceptance: missing quality, latency and hardware evidence leaves the overall engineering status UNKNOWN.",
    code: "Code: engine.py · ModelView / evaluate / model_diff / Output: runs/<id>/checks.json, diff.json"
  },
  evidence: {
    title: "05 · Save & review", owner: "Owner: local service + human engineer",
    input: "The request, source snapshots, model source, official tool output, engineering checks and requirement decision from this run.",
    action: "Persist a distinct run directory and hash inventory. Return JSON to the browser; expose actual model elements, diagnostics, source files and changes for review. On the agent path, return bounded results to the same conversation.",
    output: "result.json, decision.json, evidence-manifest.json and a complete downloadable run ZIP. History reopens stored evidence; the separate reopen utility can revalidate it. A fresh run does not overwrite the legacy system.",
    code: "Code: engine.py / app/server.py / reopen.py · Storage: runs/<id>/ + app/data/history/"
  }
};
document.querySelectorAll(".architecture-stage").forEach(button => button.addEventListener("click", () => {
  const stage = architectureStages[button.dataset.stage];
  if (!stage) return;
  document.querySelectorAll(".architecture-stage").forEach(item => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  for (const field of ["title", "owner", "input", "action", "output", "code"]) $("stage-" + field).textContent = stage[field];
}));
$("guide-toggle").addEventListener("click", () => {
  const expanded = $("guide-toggle").getAttribute("aria-expanded") === "true";
  $("architecture-content").hidden = expanded;
  $("guide-toggle").setAttribute("aria-expanded", String(!expanded));
  $("guide-toggle").textContent = expanded ? "Expand guide" : "Collapse guide";
});
document.querySelectorAll(".guide-start").forEach(link => link.addEventListener("click", event => {
  event.preventDefault();
  $("workbench").scrollIntoView({block: "start"});
  $("case-name").focus({preventScroll: true});
}));
const mapNodes = [
  {id:"request",x:38,y:76,w:222,h:107,kicker:"HUMAN / BROWSER",title:"Engineering request",lines:["Case, change, approval","Engineer owns the decision"],
    copy:"The engineer chooses a configuration and numeric changes, or submits a natural-language request. The preview decision is explicit and cannot be granted by the agent.",format:"Transport: browser → local service / HTTP POST JSON",example:'{ case_name, data_rate_mbps,\n  link_mbps, preview_approved }\n  → validate request → route to tools'},
  {id:"controller",x:366,y:76,w:270,h:107,kicker:"LOCAL PYTHON SERVICE",title:"Route & control execution",lines:["/api/run · /api/agent · /api/reference","Validate requests + preserve run records"],
    copy:"Manual runs invoke run_case directly. Agent requests enter one bounded tool loop. Public references use a separate run_reference path and are not merged into the maritime case.",format:"Code: app/server.py / HTTP JSON → local Python calls",example:"/api/run → run_case\n/api/agent → run_agent → tools\n/api/reference → run_reference"},
  {id:"agent",x:737,y:76,w:245,h:107,kind:"agent",kicker:"ONE AGENT · OPTIONAL",title:"Read → call → inspect ↶",lines:["Read evidence, then call run_design","Same conversation; bounded loop"],
    copy:"One model conversation chooses query_legacy, read_engineering_source and run_design. Database and requirement reads are enforced before a design call. Results return to the same agent; there are no separate planner, modeler or checker agents.",format:"Code: agent.py / 8 model responses maximum / provider still pending",example:"request → query_legacy\n  → read_engineering_source\n  → run_design → actual tool JSON\n  → same agent → repeat or answer"},
  {id:"provider",x:1062,y:76,w:246,h:107,kind:"agent",kicker:"MODEL PROVIDER · PENDING",title:"Configured language model",lines:["Prompt + selected tool outputs","Returns text or structured tool calls"],
    copy:"The service sends the conversation and selected tool results to the configured OpenAI-compatible endpoint. The model returns text or tool-call arguments. A local or remote provider must be configured before this path runs.",format:"Transport: model endpoint / request and response JSON; remote endpoints use HTTPS",example:"messages + tool schemas\n  → model inference\n  → text or tool_calls\nNo configured model in this demo"},
  {id:"sources",x:38,y:359,w:222,h:148,kicker:"LEGACY EVIDENCE · READ ONLY",title:"SQLite + source files",lines:["Requirements + supplier models","Interface docs + reuse records","Source IDs / revisions / hashes"],stage:"sources",
    copy:"Actual rows from the synthetic SQLite fixture and controlled files supply the candidate. Source identities and original files are retained. This is not an automatic extraction of an RTX enterprise database.",format:"Files: fixtures/legacy.sqlite + JSON + supplier .sysml",example:"SQL row + requirement decision\n  → read + snapshot\n  → structured configuration\n     with source IDs and hashes"},
  {id:"model",x:366,y:359,w:270,h:148,kicker:"PYTHON · READ + SNAPSHOT + RENDER",title:"Structured data → SysML v2",lines:["Parts, requirements and connections","Templates + two supplier packages","Paper 01 / sources · 03 / templates"],stage:"model",
    copy:"The renderer combines the selected configuration and explicit overrides with a SysML template, while preserving supplier packages. Three active budget requirement families are formalized; the entire source requirement set is not automatically formalized.",format:"Code: models/render_model.py / configuration JSON → multi-file SysML package",example:"configuration + user decision\n  → deterministic template\n  → MarineGateway.sysml\n     + supplier models + source mapping"},
  {id:"parse",x:737,y:359,w:245,h:148,kicker:"JAVA 21 · OFFICIAL SYSML PILOT",title:"Text → semantic model",lines:["Parse + link + static validation","IDs, types, owners and references","Parse failure blocks engineering checks"],stage:"parse",
    copy:"The official Pilot toolchain parses the model and resolves imports using matching libraries. The exported semantic model and AST provide the real types, references and supported values consumed by the checks.",format:"Code: toolchain/validate.py / .sysml → official export + AST + diagnostics",example:".sysml text + standard libraries\n  → official parser / linker\n  → model.json + ast-elements.json\n     + validation.json"},
  {id:"checks",x:1062,y:359,w:246,h:148,kicker:"INDEPENDENT PYTHON CHECKS",title:"Model → calculations",lines:["Storage / link / power / contracts","PASS / FAIL / UNKNOWN + diff","Paper 03 / real tool feedback"],stage:"checks",
    copy:"Independent Python checks read supported values and relationships from the official model export. They calculate budgets and check bounded contracts. The LLM neither computes authoritative verdicts nor turns missing physical evidence into PASS.",format:"Code: engine.py / parsed model → check results and model differences",example:"parsed rate + duration + capacity\n  → storage budget calculation\n  → actual, limit, margin, verdict\nMissing hardware evidence → UNKNOWN"},
  {id:"review",x:38,y:661,w:222,h:105,kicker:"HUMAN / BROWSER",title:"Inspect, compare, export",lines:["Model tree + checks + provenance","Next change → new request / run"],
    copy:"The browser renders saved result JSON and actual parsed model elements. The engineer reviews the source, model, changes and checks before making a new requirement decision. A later change creates another run.",format:"Transport: local service → browser / HTTP JSON or ZIP download",example:"saved result.json\n  → model / checks / source views\n  → human review\n  → export or a new change request"},
  {id:"evidence",x:366,y:661,w:270,h:105,kicker:"LOCAL FILE STORE",title:"Versioned run evidence",lines:["runs/<id>/ · manifests + decision","Original sources are preserved"],stage:"evidence",
    copy:"Each run preserves input snapshots, model files, parser output, checks and the decision. A hash inventory supports integrity checks and a complete ZIP can be exported. Hashes are not signatures and no standard SysML repository server is deployed.",format:"Storage: local files / runs/<id>/ and app/data/history/",example:"sources + model + tool outputs\n  → distinct run directory + hashes\n  → result.json + evidence manifest\n  → reviewable, exportable run"},
  {id:"memory",x:1062,y:661,w:246,h:105,kind:"future",kicker:"PAPER 02 · FUTURE / NOT RUNNING",title:"Graph + retrieval memory",lines:["RDF / embeddings / revision filters","Evidence-linked context for the agent"],
    copy:"Proposed next step: convert versioned model exports into provenance-linked graph records and retrieve relevant nodes and neighbors for the same agent. GRAG, Graphiti and ACE are references, not active services or learned memory in this MVP.",format:"Proposed: semantic export → RDF / vector index → retrieved context",example:"versioned model + provenance\n  → graph / embeddings / index\n  → configuration-filtered retrieval\n  → agent context (not connected)"}
];
const svgNS = "http://www.w3.org/2000/svg";
function mapSvg(tag, attrs, parent, text) {
  const el = document.createElementNS(svgNS, tag);
  for (const [key,value] of Object.entries(attrs || {})) el.setAttribute(key,String(value));
  if (text !== undefined) el.textContent = text;
  parent.append(el); return el;
}
function buildArchitectureMap() {
  const svg = $("system-architecture");
  mapSvg("title",{},svg,"Engineering workbench: data transformations and the single-agent feedback loop");
  const defs = mapSvg("defs",{},svg);
  for (const [kind,color] of [["tool","#70c9cb"],["agent","#efbf72"],["future","#bcaae1"]]) {
    const marker = mapSvg("marker",{id:"map-arrow-"+kind,viewBox:"0 0 10 10",refX:9,refY:5,markerWidth:6,markerHeight:6,orient:"auto-start-reverse"},defs);
    mapSvg("path",{d:"M0 0 L10 5 L0 10 z",fill:color},marker);
  }
  for (const lane of [{y:26,h:191,title:"01 / REQUEST & ORCHESTRATION"},{y:302,h:245,title:"02 / LOCAL ENGINEERING TOOLS · SOURCE → MODEL → VALIDATION"}]) {
    mapSvg("rect",{class:"map-lane",x:18,y:lane.y,width:1324,height:lane.h,rx:12},svg);
    mapSvg("text",{class:"map-lane-label",x:38,y:lane.y+25},svg,lane.title);
  }
  mapSvg("text",{class:"map-lane-label",x:38,y:634},svg,"03 / PERSISTENCE, REVIEW & THE NEXT CHANGE");
  const edges = [
    {d:"M260 128 H366",x:313,y:111,label:"HTTP JSON"},
    {d:"M466 183 V359",x:479,y:253,label:"Manual: run_case",sub:"case + overrides + decision",kind:"manual",anchor:"start"},
    {d:"M636 128 H737",x:687,y:111,label:"message",kind:"agent"},
    {d:"M982 128 H1062",x:1023,y:95,label:"model API",sub:"JSON ↔ JSON",kind:"agent",both:true},
    {d:"M810 183 V265 H606 V359",x:665,y:249,label:"tool calls",kind:"agent"},
    {d:"M1190 359 V240 H918 V183",x:1100,y:259,label:"tool results → same agent",kind:"agent"},
    {d:"M260 430 H366",x:313,y:396,label:"read-only",sub:"rows + IDs"},
    {d:"M636 430 H737",x:687,y:397,label:".sysml",sub:"+ imports"},
    {d:"M982 430 H1062",x:1023,y:397,label:"semantic",sub:"JSON + AST"},
    {d:"M466 507 V570 H560 V661",x:852,y:596,label:"snapshots + model files + diagnostics + checks + hashes"},
    {d:"M860 507 V570 H560",noArrow:true},
    {d:"M1190 507 V570 H860",noArrow:true},
    {d:"M366 710 H260",x:313,y:678,label:"HTTP JSON",sub:"or ZIP export"},
    {d:"M636 710 H1062",x:848,y:690,label:"versioned semantic export → index",kind:"future"},
    {d:"M1308 710 H1330 V225 H963 V183",x:1110,y:210,label:"retrieved context · future",kind:"future"}
  ];
  for (const edge of edges) {
    const g = mapSvg("g",{class:"map-edge"+(edge.kind ? " map-"+edge.kind : "")},svg);
    const marker = "url(#map-arrow-"+(["agent","future"].includes(edge.kind) ? edge.kind : "tool")+")";
    mapSvg("path",{d:edge.d,"marker-end":edge.noArrow ? "none" : marker,...(edge.both ? {"marker-start":marker} : {})},g);
    if (edge.label) mapSvg("text",{x:edge.x,y:edge.y,"text-anchor":edge.anchor || "middle"},g,edge.label);
    if (edge.sub) mapSvg("text",{class:"secondary",x:edge.x,y:edge.y+18,"text-anchor":edge.anchor || "middle"},g,edge.sub);
  }
  for (const node of mapNodes) {
    const g = mapSvg("g",{class:"map-node"+(node.kind ? " map-"+node.kind : ""),"data-map-node":node.id,role:"button",tabindex:0,"aria-label":"Inspect "+node.title,"aria-pressed":"false"},svg);
    mapSvg("rect",{x:node.x,y:node.y,width:node.w,height:node.h,rx:8},g);
    mapSvg("text",{class:"map-node-kicker",x:node.x+17,y:node.y+24},g,node.kicker);
    mapSvg("text",{class:"map-node-title",x:node.x+17,y:node.y+49},g,node.title);
    node.lines.forEach((line,i)=>mapSvg("text",{class:i===node.lines.length-1 ? "map-node-note" : "",x:node.x+17,y:node.y+73+i*22},g,line));
    const select = () => {
      document.querySelectorAll(".map-node").forEach(item => {item.classList.toggle("selected",item===g);item.setAttribute("aria-pressed",String(item===g));});
      $("map-detail-state").textContent = node.kind==="future" ? "PROPOSED · NOT EXECUTED" : node.kind==="agent" ? "CONNECTOR IMPLEMENTED · PROVIDER PENDING" : "IMPLEMENTED COMPONENT";
      $("map-detail-title").textContent=node.title;
      $("map-detail-copy").textContent=node.copy;
      $("map-detail-format").textContent=node.format;
      $("map-detail-example").textContent=node.example;
      if (node.stage) document.querySelector('.architecture-stage[data-stage="'+node.stage+'"]').click();
    };
    g.addEventListener("click",select);
    g.addEventListener("keydown",event=>{if(event.key==="Enter" || event.key===" "){event.preventDefault();select();}});
  }
}
function renderLineage(record) {
  const result = record.result || {}, config = result.config || {};
  const container = $("lineage-steps"); container.replaceChildren();
  if (result.reference_name || typeof config.data_rate_mbps !== "number") {
    $("lineage-context").textContent = result.reference_name ? "This is a public reference run. Maritime budget lineage does not apply; inspect its source and parsed model in the workbench." : "No maritime configuration returned. Run a case to inspect actual artifacts.";
    return;
  }
  const override = config.runtime_overrides?.data_rate_mbps;
  const element = result.model_elements?.find(e=>e.qualifiedName==="MarineGateway::Gateway::dataRateMbps");
  const modelLine = result.model_text?.split("\n").find(line=>line.includes("attribute :>> dataRateMbps"));
  const check = result.checks?.find(c=>c.id==="R-STORE-001");
  $("lineage-context").textContent = result.case_name+" · "+result.run_id+" · Values below are read from this saved run; changing the form does not change this evidence.";
  const cards = [
    ["1 / SOURCE & REQUEST",override ? override.old_value+" → "+override.new_value+" Mbps" : config.data_rate_mbps+" Mbps",(override ? "Explicit rate override" : "Selected configuration")+" · configs row "+config.source_rowid+"\n"+config.source_id],
    ["2 / GENERATED SYSML",modelLine?.trim() || "No model text returned","Actual line from MarineGateway.sysml"],
    ["3 / OFFICIAL SEMANTICS",element?.type || "No parsed attribute returned",element ? element.qualifiedName+"\nID: "+element.id : "Official parser evidence is unavailable."],
    ["4 / ENGINEERING EVIDENCE",check && typeof check.actual==="number" ? check.actual+" / "+check.limit+" "+check.unit : "No storage result returned",check ? "Storage verdict: "+check.status+"\nOverall acceptance: "+result.status+"\n"+config.data_rate_mbps+" Mbps · "+config.retention_hours+" h · "+config.storage_gb+" GB × "+config.payload_fraction+" usable" : "A missing check is not a passing result."]
  ];
  for (const [label,value,detail] of cards) {
    const card=document.createElement("div"),heading=document.createElement("span"),strong=document.createElement("strong"),p=document.createElement("p");
    heading.textContent=label;strong.textContent=value;p.textContent=detail;card.append(heading,strong,p);container.append(card);
  }
}
buildArchitectureMap();
function setGraphExpanded(expanded) {
  $("system-map-frame").classList.toggle("map-expanded",expanded);
  document.body.classList.toggle("graph-expanded",expanded);
  $("graph-expand").setAttribute("aria-expanded",String(expanded));
  $("graph-expand").textContent=expanded ? "Close expanded view ×" : "Expand graph ⤢";
}
$("graph-expand").addEventListener("click",()=>setGraphExpanded($("graph-expand").getAttribute("aria-expanded")!=="true"));
document.addEventListener("keydown",event=>{if(event.key==="Escape" && $("graph-expand").getAttribute("aria-expanded")==="true"){setGraphExpanded(false);$("graph-expand").focus();}});
document.querySelectorAll(".graph-mode").forEach(button=>button.addEventListener("click",()=>{
  $("system-architecture").dataset.mode=button.dataset.mode;
  document.querySelectorAll(".graph-mode").forEach(item=>{const active=item===button;item.classList.toggle("active",active);item.setAttribute("aria-pressed",String(active));});
}));
(async () => {
  await refreshStatus();
  try {
    const runs = await refreshHistory();
    if (selectedId) await loadRecord(selectedId);
    else if (runs.length) await loadRecord(runs[0].record_id);
    await refreshSources();
  } catch (error) { message(error.message); }
  setInterval(refreshStatus, 1800);
})();
