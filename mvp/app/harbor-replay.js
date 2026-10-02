/* A local, synthetic byte-processing replay. It does not execute the engineering model. */
(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const BASE_TIME = Date.UTC(2026, 8, 22, 12, 0, 0);
  const LIMITATIONS = [
    "Synthetic canvas scenes and JPEG bytes; no camera video or thermal measurements.",
    "No H.264 decoding, thermal inference, actual RF, SSD, or throughput testing.",
    "The resized JPEG preview is not a validated P2 processing algorithm.",
    "Saved-run Mbps, W and GB are engineering model values, not replay measurements.",
    "Archive and subscriber buffers exist only in this page's memory; reset clears them."
  ];
  const STAGES = [
    ["Generate synthetic observations", "Draw reproducible harbor scenes and encode real JPEG blobs in this browser.", "sensors"],
    ["Validate the interface envelope", "Check source identity, sequence, millisecond timestamp, dimensions and JPEG signature. Invalid data stops here.", "ingest"],
    ["Normalize and fingerprint", "Convert validated timestamps to UTC and compute SHA-256 over the actual JPEG bytes using WebCrypto.", "ingest"],
    ["Archive and verify readback", "Copy original bytes into separate in-memory buffers, copy them back, and verify their hashes. This is not an SSD test.", "storage"],
    ["Apply the recorded upload decision", "Only a saved run with preview_approved=true produces a resized side-by-side JPEG. Otherwise both original JPEGs are preserved.", "processor"],
    ["Route the upload", "Use an actual browser MessageChannel. A simulated outage or a missing/failing saved uplink check retains the packet in a local queue.", "router"],
    ["Relay to two subscribers", "The browser-local shore relay sends the received bytes through two MessageChannels; both subscribers verify every checksum.", "shore"]
  ];
  let state = null;
  const clone = value => JSON.parse(JSON.stringify(value));
  const pretty = value => JSON.stringify(value, null, 2);
  const text = (id, value) => { if ($(id)) $(id).textContent = value; };
  const summary = frames => frames.map(f => ({ ...f.header, byte_length: f.bytes.byteLength }));
  const assertCurrent = s => { if (s !== state || s.cancelled) throw new Error("Replay cancelled by a run change."); };
  const digest = async bytes => {
    if (!window.crypto?.subtle) throw new Error("WebCrypto SHA-256 is unavailable. Open the localhost workbench in a supported browser.");
    const hash = await window.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(hash), x => x.toString(16).padStart(2, "0")).join("");
  };
  function controls() {
    if (!state) return;
    for (const id of ["harbor-replay-all", "harbor-replay-next"]) if ($(id)) $(id).disabled = !state.enabled || state.busy || state.failed || state.next >= STAGES.length;
    if ($("harbor-replay-reset")) $("harbor-replay-reset").disabled = state.busy || !state.enabled;
    if ($("harbor-replay-scenario")) $("harbor-replay-scenario").disabled = state.busy || !state.enabled;
    if ($("harbor-replay-download")) $("harbor-replay-download").disabled = state.busy || !state.logs.length;
  }
  function inspect(index, entry) {
    const stage = STAGES[index];
    text("harbor-stage-title", `${index + 1} / ${stage[0]}`);
    text("harbor-stage-explanation", stage[1]);
    text("harbor-input-json", pretty(entry?.input ?? { state: "Not executed", stage: index + 1 }));
    text("harbor-output-json", pretty(entry?.output ?? { state: "Not executed; use Next step or Replay all." }));
    document.querySelectorAll(".harbor-step").forEach(el => {
      const active = Number(el.dataset.harborStep) === index;
      el.classList.toggle("harbor-active", active); el.setAttribute("aria-pressed", String(active));
    });
    document.querySelectorAll("[data-harbor-component]").forEach(el => el.classList.toggle("harbor-active", el.dataset.harborComponent === stage[2] || (index === 6 && el.dataset.harborComponent === "peer")));
  }
  function appendLog(s, index, status, input, output) {
    const entry = { stage: index + 1, name: STAGES[index][0], status, recorded_at: new Date().toISOString(), input, output };
    s.logs.push(entry); inspect(index, entry);
    const step = document.querySelector(`.harbor-step[data-harbor-step="${index}"]`);
    step?.classList.toggle("done", status === "DONE");
    step?.classList.toggle("failed", status === "ERROR" || status === "REJECTED");
    const row = document.createElement("div"); row.className = "harbor-log-entry";
    row.textContent = `${index + 1}. ${entry.name} — ${status}`;
    $("harbor-replay-log")?.append(row);
  }
  function placeholder(id, label) {
    const canvas = $(id), ctx = canvas?.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#102736"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#c9e3e9"; ctx.font = `${Math.max(16, canvas.width / 36)}px sans-serif`;
    ctx.fillText(label, canvas.width * .05, canvas.height * .52, canvas.width * .9);
  }
  function reset() {
    if (!state || state.busy) return;
    const record = state.record; state.key = null; window.updateHarborRun(record);
  }
  window.updateHarborRun = record => {
    const result = record?.result || {}, config = result.config;
    const key = result.run_id || record?.record_id || null;
    if (state && key && key === state.key) return;
    if (state) { state.cancelled = true; for (const cancel of [...state.cancellations]) cancel(); }
    const enabled = Boolean(!result.reference_name && config && typeof config.case_name === "string" && Number.isFinite(config.data_rate_mbps));
    state = { key, record: clone(record || {}), config: clone(config || {}), checks: clone(result.checks || []), enabled,
      busy: false, cancelled: false, failed: false, next: 0, logs: [], originals: [], archive: [], outbound: [], queue: [], shore: null, subscribers: [], preview: null, cancellations: new Set(),
      scenario: $("harbor-replay-scenario")?.value || "normal" };
    text("harbor-run-context", enabled ? `${config.case_name} · ${key || "No run ID"} · Recorded preview decision: ${config.preview_approved === true ? "approved" : "not approved"}. Browser-local synthetic replay only.` : "Select a saved marine gateway run. Public references and records without a marine configuration cannot run this replay.");
    const metric = id => state.checks.find(c => c.id === id);
    const format = check => check && typeof check.actual === "number" ? `${check.actual} / ${check.limit} ${check.unit || ""} · ${check.status}` : "No saved check";
    text("harbor-rate-value", enabled ? `${config.data_rate_mbps} Mbps · modeled input` : "Not applicable");
    text("harbor-storage-value", enabled ? format(metric("R-STORE-001")) : "Not applicable");
    text("harbor-power-value", enabled ? format(metric("R-POWER-001")) : "Not applicable");
    text("harbor-link-value", enabled ? format(state.checks.find(c => /^R-UPLOAD-/.test(c.id))) : "Not applicable");
    text("harbor-replay-status", enabled ? "READY — synthetic images; no hardware or external network connection." : "UNAVAILABLE — a saved marine configuration is required.");
    $("harbor-replay-log")?.replaceChildren();
    document.querySelectorAll(".harbor-step").forEach(el => el.classList.remove("done", "failed"));
    placeholder("harbor-eo-canvas", "Synthetic EO scene · not generated");
    placeholder("harbor-ir-canvas", "Synthetic thermal-style scene · not generated");
    placeholder("harbor-preview-canvas", "Preview · not generated");
    for (const id of ["harbor-eo-meta", "harbor-ir-meta", "harbor-preview-meta"]) text(id, "No replay bytes generated.");
    inspect(0); controls();
  };
  function scene(canvas, thermal) {
    if (!canvas) throw new Error("Replay canvas is missing from the page.");
    const ctx = canvas.getContext("2d"); if (!ctx) throw new Error("Canvas 2D is unavailable.");
    const w = canvas.width, h = canvas.height; ctx.save(); ctx.scale(w / 960, h / 540);
    const sky = ctx.createLinearGradient(0, 0, 0, 540);
    sky.addColorStop(0, thermal ? "#19104e" : "#b9d9e8"); sky.addColorStop(1, thermal ? "#31206a" : "#497f94");
    ctx.fillStyle = sky; ctx.fillRect(0, 0, 960, 540);
    ctx.fillStyle = thermal ? "#43217c" : "#90a8ad";
    for (let i = 0; i < 12; i++) ctx.fillRect(i * 87, 160 - (i * 37 % 70), 73, 120);
    ctx.fillStyle = thermal ? "#221654" : "#356e86"; ctx.fillRect(0, 245, 960, 295);
    ctx.strokeStyle = thermal ? "#57328f" : "#83bac5"; ctx.lineWidth = 2;
    for (let i = 0; i < 80; i++) { const x = (i * 137) % 960, y = 263 + (i * 41) % 263; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 14 + i % 29, y); ctx.stroke(); }
    ctx.fillStyle = thermal ? "#be4a76" : "#6b7377";
    ctx.beginPath(); ctx.moveTo(0, 205); ctx.lineTo(335, 255); ctx.lineTo(395, 540); ctx.lineTo(0, 540); ctx.fill();
    for (let i = 0; i < 5; i++) { ctx.fillStyle = thermal ? ["#e98558", "#f3b86a"][i % 2] : ["#b36e49", "#688f9a"][i % 2]; ctx.fillRect(25 + i * 46, 240 + i * 17, 40, 72); }
    ctx.strokeStyle = thermal ? "#ffd886" : "#637786"; ctx.lineWidth = 9;
    ctx.beginPath(); ctx.moveTo(145, 230); ctx.lineTo(145, 72); ctx.lineTo(342, 72); ctx.lineTo(314, 130); ctx.stroke();
    ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(285, 72); ctx.lineTo(285, 188); ctx.stroke();
    const boat = (x, y, scale) => {
      ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
      ctx.fillStyle = thermal ? "#fcb65d" : "#e8ece4"; ctx.beginPath(); ctx.moveTo(-82, 0); ctx.lineTo(85, 0); ctx.lineTo(57, 32); ctx.lineTo(-55, 32); ctx.fill();
      ctx.fillStyle = thermal ? "#ffeaa0" : "#e5ae55"; ctx.fillRect(-36, -42, 73, 42);
      ctx.fillStyle = thermal ? "#e77152" : "#284b65"; ctx.fillRect(-23, -32, 18, 16); ctx.fillRect(6, -32, 18, 16);
      ctx.strokeStyle = thermal ? "#ffebac" : "#dce5de"; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(0, -42); ctx.lineTo(0, -83); ctx.stroke(); ctx.restore();
    };
    boat(849, 278, .43);
    // H-07 is a manually assigned reference subject, not a detected object.
    ctx.save(); ctx.translate(646, 388);
    ctx.fillStyle = thermal ? "#e76f54" : "#f49c37";
    ctx.beginPath(); ctx.ellipse(0, 10, 60, 17, 0, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(-37, 1); ctx.lineTo(-24, -104); ctx.lineTo(24, -104); ctx.lineTo(37, 1); ctx.fill();
    ctx.fillStyle = thermal ? "#963b73" : "#202d35";
    ctx.fillRect(-28, -76, 56, 15); ctx.fillRect(-33, -31, 66, 15);
    ctx.fillStyle = thermal ? "#ffd886" : "#ed8c25";
    ctx.beginPath(); ctx.moveTo(-27, -104); ctx.lineTo(0, -145); ctx.lineTo(27, -104); ctx.fill();
    ctx.fillStyle = thermal ? "#fff2bd" : "#f8efb7";
    ctx.fillRect(-7, -165, 14, 18); ctx.fillStyle = thermal ? "#faad65" : "#53616a"; ctx.fillRect(-12, -169, 24, 5);
    ctx.restore();
    ctx.fillStyle = "rgba(5,17,30,.8)"; ctx.fillRect(414, 446, 463, 34);
    ctx.fillStyle = "#ffffff"; ctx.font = "17px sans-serif";
    ctx.fillText("H-07 reference subject · manually assigned", 426, 469, 440);
    ctx.fillStyle = "rgba(5,17,30,.85)"; ctx.fillRect(0, 0, 960, 47); ctx.fillRect(0, 505, 960, 35);
    ctx.fillStyle = "#ffffff"; ctx.font = "20px sans-serif";
    ctx.fillText(thermal ? "SYNTHETIC THERMAL-STYLE VIEW · NO TEMPERATURE DATA" : "SYNTHETIC EO VIEW · HARBOR INSPECTION SCENE", 18, 30, 920);
    ctx.font = "16px monospace"; ctx.fillText("FRAME 0001 · LOCAL PROCEDURAL SCENE · NOT CAMERA FOOTAGE", 18, 528, 920); ctx.restore();
  }
  async function encode(canvas, s) {
    const blob = await new Promise((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error("JPEG encoding failed.")), "image/jpeg", .82));
    assertCurrent(s); if (blob.type !== "image/jpeg") throw new Error("This browser did not return JPEG bytes.");
    const bytes = new Uint8Array(await blob.arrayBuffer()); assertCurrent(s); return bytes;
  }
  function frame(source, canvas, bytes, timestamp) {
    return { header: { source, sequence: 1, timestamp_ms: timestamp, mime_type: "image/jpeg", width: canvas.width, height: canvas.height, synthetic: true }, bytes };
  }
  async function verifyFrames(frames, s) {
    for (const f of frames) {
      const hash = await digest(f.bytes); assertCurrent(s);
      if (!f.header.sha256 || hash !== f.header.sha256) throw new Error(`Checksum mismatch for ${f.header.source}.`);
    }
  }
  function channelSend(packet, s) {
    return new Promise((resolve, reject) => {
      assertCurrent(s); const channel = new MessageChannel(); let finished = false;
      const finish = (error, value) => {
        if (finished) return; finished = true; clearTimeout(timer); channel.port1.close(); channel.port2.close(); s.cancellations.delete(cancel);
        error ? reject(error) : resolve(value);
      };
      const cancel = () => finish(new Error("Replay cancelled by a run change."));
      const timer = setTimeout(() => finish(new Error("Browser MessageChannel delivery timed out.")), 2000);
      s.cancellations.add(cancel);
      channel.port2.onmessage = event => finish(null, event.data);
      channel.port2.onmessageerror = () => finish(new Error("Browser MessageChannel could not deserialize the packet."));
      try { channel.port1.postMessage(packet); } catch (error) { finish(error); }
    });
  }
  async function execute(s, index) {
    let input, output, status = "DONE";
    if (index === 0) {
      input = { generator: "procedural-harbor-v1", frame_time_ms: BASE_TIME, scenario: s.scenario, reproducibility: "Fixed scene and timestamp; JPEG encoders may differ across browsers." };
      for (const [id, source, thermal, offset] of [["harbor-eo-canvas", "EO-01", false, 0], ["harbor-ir-canvas", "IR-01", true, 40]]) {
        const canvas = $(id); scene(canvas, thermal); const bytes = await encode(canvas, s);
        const timestamp = s.scenario === "bad_timestamp" ? Math.floor((BASE_TIME + offset) / 1000) : BASE_TIME + offset;
        s.originals.push(frame(source, canvas, bytes, timestamp));
        text(thermal ? "harbor-ir-meta" : "harbor-eo-meta", `Synthetic ${canvas.width} × ${canvas.height} · JPEG ${bytes.byteLength.toLocaleString()} bytes · sequence 1`);
      }
      output = { frames: summary(s.originals), note: LIMITATIONS[0] };
    } else if (index === 1) {
      input = { frames: summary(s.originals), contract: "EO-01 / IR-01; positive integer sequence; timestamp_ms in years 2000–2100; nonempty JPEG." };
      const errors = [], seen = new Set();
      for (const f of s.originals) {
        const h = f.header, key = `${h.source}:${h.sequence}`;
        if (!["EO-01", "IR-01"].includes(h.source)) errors.push("Unknown source identity.");
        if (!Number.isSafeInteger(h.sequence) || h.sequence < 1 || seen.has(key)) errors.push("Invalid or duplicate source sequence."); seen.add(key);
        if (!Number.isSafeInteger(h.timestamp_ms) || h.timestamp_ms < Date.UTC(2000, 0, 1) || h.timestamp_ms >= Date.UTC(2101, 0, 1)) errors.push(`${h.source}: timestamp_ms must be milliseconds in years 2000–2100; seconds are rejected.`);
        if (h.mime_type !== "image/jpeg" || f.bytes.length < 4 || f.bytes[0] !== 255 || f.bytes[1] !== 216) errors.push("Invalid JPEG payload.");
        if (!(h.width > 0 && h.height > 0)) errors.push("Invalid image dimensions.");
      }
      output = { accepted: !errors.length, errors, frame_count: s.originals.length };
      if (errors.length) { s.failed = true; status = "REJECTED"; }
    } else if (index === 2) {
      input = { frames: summary(s.originals), hash_algorithm: "WebCrypto SHA-256" };
      for (const f of s.originals) { f.header.timestamp_utc = new Date(f.header.timestamp_ms).toISOString(); f.header.sha256 = await digest(f.bytes); assertCurrent(s); }
      output = { normalized_frames: summary(s.originals) };
    } else if (index === 3) {
      input = { frames: summary(s.originals), archive_medium: "separate in-memory Uint8Array buffers" };
      s.archive = s.originals.map(f => ({ header: clone(f.header), bytes: f.bytes.slice() }));
      const readback = s.archive.map(f => ({ header: clone(f.header), bytes: f.bytes.slice() })); await verifyFrames(readback, s);
      output = { archived_bytes: s.archive.reduce((n, f) => n + f.bytes.length, 0), independent_buffers: s.archive.every((f, i) => f.bytes.buffer !== s.originals[i].bytes.buffer), readback_sha256_verified: true, retention: "Page memory only; export evidence before reset." };
    } else if (index === 4) {
      input = { recorded_preview_approved: s.config.preview_approved === true, frames: summary(s.archive) };
      if (s.config.preview_approved === true) {
        const canvas = $("harbor-preview-canvas"), ctx = canvas?.getContext("2d"); if (!ctx) throw new Error("Preview canvas is unavailable.");
        ctx.fillStyle = "#102736"; ctx.fillRect(0, 0, canvas.width, canvas.height);
        for (const [i, id] of ["harbor-eo-canvas", "harbor-ir-canvas"].entries()) {
          const image = $(id), scale = Math.min((canvas.width / 2 - 12) / image.width, (canvas.height - 60) / image.height);
          const width = image.width * scale, height = image.height * scale;
          ctx.drawImage(image, i * canvas.width / 2 + (canvas.width / 2 - width) / 2, 32 + (canvas.height - 60 - height) / 2, width, height);
        }
        ctx.fillStyle = "#ffffff"; ctx.font = "16px sans-serif"; ctx.fillText("SYNTHETIC JPEG PREVIEW · NOT A VALIDATED P2 ALGORITHM", 15, 23, canvas.width - 30);
        const bytes = await encode(canvas, s); s.preview = frame("PREVIEW-JPEG", canvas, bytes, BASE_TIME);
        s.preview.header.timestamp_utc = new Date(BASE_TIME).toISOString(); s.preview.header.sha256 = await digest(bytes); assertCurrent(s);
        s.outbound = [s.preview]; text("harbor-preview-meta", `Actual resized JPEG · ${bytes.length.toLocaleString()} bytes · recorded preview approval used; no approval changed.`);
      } else {
        s.outbound = s.archive.map(f => ({ header: clone(f.header), bytes: f.bytes.slice() }));
        placeholder("harbor-preview-canvas", "Preview not approved · original JPEGs retained"); text("harbor-preview-meta", "No preview generated. Both original JPEGs are retained for upload.");
      }
      output = { mode: s.preview ? "RESIZED_JPEG_DEMONSTRATION" : "ORIGINAL_JPEG_PAIR", frames: summary(s.outbound), original_archive_unchanged: true, note: LIMITATIONS[2] };
    } else if (index === 5) {
      const check = s.checks.find(c => /^R-UPLOAD-/.test(c.id));
      input = { frames: summary(s.outbound), saved_uplink_check: check || null, scenario: s.scenario, transport: "browser MessageChannel; no external network" };
      const reasons = [];
      if (s.scenario === "link_down") reasons.push("SIMULATED_LINK_DOWN");
      if (check?.status !== "PASS") reasons.push(check?.status === "FAIL" ? "MODELED_CAPACITY_FAIL" : "MODELED_UPLINK_NOT_VERIFIED");
      if (reasons.length) { s.queue = s.outbound.map(f => ({ header: clone(f.header), bytes: f.bytes.slice() })); status = "QUEUED"; output = { delivered: false, reasons, queued_frames: summary(s.queue), queue_medium: "page memory; no messages sent" }; }
      else { s.shore = await channelSend({ destination: "browser-local-shore", frames: s.outbound }, s); assertCurrent(s); await verifyFrames(s.shore.frames, s); output = { delivered: true, destination: s.shore.destination, received_frames: summary(s.shore.frames), sha256_verified: true }; }
    } else {
      input = { shore_received: Boolean(s.shore), subscriber_names: ["shore-analyst", "peer-platform"], transport: "two browser MessageChannels" };
      if (!s.shore) { status = "QUEUED"; output = { forwarded: false, subscribers_received: 0, reason: "No uplink packet reached the shore relay. Original archive and queued bytes remain in page memory." }; }
      else {
        for (const name of input.subscriber_names) { const received = await channelSend({ destination: name, frames: s.shore.frames }, s); assertCurrent(s); await verifyFrames(received.frames, s); s.subscribers.push({ name, sha256_verified: true, frames: summary(received.frames) }); }
        output = { forwarded: true, subscribers: s.subscribers, note: "Independent browser-local cloned packets; no actual shore or vessel connection." };
      }
    }
    assertCurrent(s); appendLog(s, index, status, input, output); s.next++;
    text("harbor-replay-status", s.failed ? "REJECTED — invalid interface data; downstream steps were not executed." : s.next === 7 ? (s.queue.length ? "QUEUED — data retained in page memory; no subscriber delivery." : "COMPLETED — JPEG byte copies and browser-local checksum checks succeeded; hardware acceptance remains untested.") : `${status} — step ${s.next} of 7. ${s.queue.length ? "Uplink retained in page memory." : "No hardware measurement claimed."}`);
  }
  async function advance(all) {
    const s = state; if (!s?.enabled || s.busy || s.failed || s.next >= 7) return;
    s.busy = true; controls();
    try {
      do {
        assertCurrent(s); text("harbor-replay-status", `RUNNING — ${STAGES[s.next][0]}`); inspect(s.next);
        await execute(s, s.next);
        if (all && !s.failed && s.next < 7) await new Promise(resolve => setTimeout(resolve, 180));
      } while (all && !s.failed && s.next < 7);
    } catch (error) {
      if (s === state && !s.cancelled) { s.failed = true; appendLog(s, Math.min(s.next, 6), "ERROR", { stage: s.next + 1 }, { error: String(error.message || error) }); text("harbor-replay-status", `ERROR — ${error.message || error}`); }
    } finally { if (s === state) { s.busy = false; controls(); } }
  }
  function base64(bytes) {
    let binary = ""; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768)); return btoa(binary);
  }
  function download() {
    const s = state; if (!s || s.busy || !s.logs.length) return;
    const evidence = { schema: "harbor-browser-replay-v1", exported_at: new Date().toISOString(), limitations: LIMITATIONS,
      request: s.record.request || {}, selected_run_id: s.key, saved_config: s.config, saved_checks: s.checks,
      scenario: s.scenario, generator: "procedural-harbor-v1", frame_time_ms: BASE_TIME, completed_stages: s.next, failed: s.failed,
      original_frames: s.originals.map(f => ({ ...f.header, byte_length: f.bytes.length, payload_base64: base64(f.bytes) })),
      preview: s.preview ? { ...s.preview.header, byte_length: s.preview.bytes.length, payload_base64: base64(s.preview.bytes) } : null,
      archive: summary(s.archive), queued: summary(s.queue), subscribers: s.subscribers, log: s.logs };
    const url = URL.createObjectURL(new Blob([pretty(evidence)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = `harbor-replay-${String(s.key || "local").replace(/[^a-zA-Z0-9_-]/g, "_")}-${s.scenario}.json`;
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function bind() {
    $("harbor-replay-next")?.addEventListener("click", () => advance(false));
    $("harbor-replay-all")?.addEventListener("click", () => advance(true));
    $("harbor-replay-reset")?.addEventListener("click", reset);
    $("harbor-replay-download")?.addEventListener("click", download);
    $("harbor-replay-scenario")?.addEventListener("change", () => { if (!state?.busy) reset(); });
    document.querySelectorAll(".harbor-step").forEach(el => el.addEventListener("click", () => {
      const index = Number(el.dataset.harborStep); if (!state?.busy && Number.isInteger(index) && STAGES[index]) inspect(index, state?.logs.find(entry => entry.stage === index + 1));
    }));
    if (typeof currentRecord !== "undefined" && currentRecord) window.updateHarborRun(currentRecord);
    else if (!state) window.updateHarborRun(null);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind, { once: true }); else bind();
})();
