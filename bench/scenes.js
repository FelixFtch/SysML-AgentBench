/* Animated scene for each exam task (1.4) and each MOD change run (2.4).
   Left: the platforms the task is about, with data moving along every link the task asks for.
   Right: the checklist the scorer applied, coloured from the scored answer of that cell. */
(function () {
  "use strict";

  const W = 960;
  const H = 340;
  const BX = 588;
  const BW = 360;
  const SANS = "Inter, 'Noto Sans SC', 'PingFang SC', sans-serif";
  const MONO = "'JetBrains Mono', ui-monospace, Menlo, monospace";
  const C = { img: "#5fd3c6", trk: "#f2b33d", lnk: "#b6a1f0", pwr: "#f0d08a", ok: "#63c890", bad: "#ff8a80", lock: "#f6c768",
    dim: "#6f8a9c", add: "#ff9f43", txt: "#e6f2f6", sub: "#a9c3cf" };
  const TYPE = { GEN: "generate a new model", MOD: "modify an existing model", ALN: "align two models", QRY: "query a model", AMB: "ask, don't guess", RT: "model back to text" };
  let seq = 0;

  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const tw = (s, size) => [...String(s)].reduce((w, ch) => w + (ch.charCodeAt(0) > 0x2e80 ? size : size * 0.58), 0);
  const reduced = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  const strip = (q) => String(q || "").split("::").slice(1).join("::");

  function fit(text, maxW, size) {
    let t = String(text ?? "");
    if (tw(t, size) <= maxW) return t;
    while (t.length > 1 && tw(`${t}…`, size) > maxW) t = t.slice(0, -1);
    return `${t}…`;
  }

  function wrap(text, maxW, size, maxLines) {
    const words = String(text ?? "").replace(/\s+/g, " ").trim().split(/(?<=\s)|(?=[\u2e80-\uffff])/);
    const lines = [];
    let cur = "";
    for (const w of words) {
      if (tw(cur + w, size) > maxW && cur) {
        lines.push(cur.trimEnd());
        cur = w.trimStart();
        if (lines.length === maxLines) break;
      } else {
        cur += w;
      }
    }
    if (lines.length < maxLines && cur) lines.push(cur.trimEnd());
    if (lines.length === maxLines && words.join("").length > lines.join(" ").length + 2) lines[maxLines - 1] = fit(`${lines[maxLines - 1]}…`, maxW, size);
    return lines;
  }

  /* ---------------- what the scorer found ---------------- */
  function judge(ctx) {
    const v = ctx.verdict || {};
    const judged = !!v.must_exist && !ctx.live;
    const missE = new Set(((v.must_exist || {}).missing || []).map(strip));
    const missC = new Set(((v.must_connect || {}).missing || []).map((pair) => pair.slice().sort().join("|")));
    const missP = {};
    for (const m of (v.must_preserve || {}).missing || []) missP[strip(m.qualified_name)] = m;
    return {
      v,
      judged,
      el: (key) => (!judged ? "unknown" : missE.has(key) ? "miss" : "ok"),
      cn: (a, b) => (!judged ? "unknown" : missC.has([a, b].sort().join("|")) ? "miss" : "ok"),
      keep: (key) => (!judged ? "unknown" : missP[key] ? "miss" : "ok"),
      keepInfo: (key) => missP[key],
    };
  }

  /* ---------------- drawing primitives ---------------- */
  function defs(p) {
    const marks = { img: C.img, trk: C.trk, lnk: C.lnk, pwr: C.pwr, bad: C.bad, dim: C.dim, add: C.add, ok: C.ok };
    return `<defs>
      <linearGradient id="${p}-sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#091b2b"/><stop offset="1" stop-color="#18445f"/></linearGradient>
      <linearGradient id="${p}-sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#15495f"/><stop offset="1" stop-color="#09263a"/></linearGradient>
      <linearGradient id="${p}-hull" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#eef5f8"/><stop offset="1" stop-color="#9db7c4"/></linearGradient>
      <linearGradient id="${p}-land" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3d5b48"/><stop offset="1" stop-color="#22362b"/></linearGradient>
      <radialGradient id="${p}-spot"><stop offset="0" stop-color="#fff3b3" stop-opacity=".38"/><stop offset="1" stop-color="#fff3b3" stop-opacity="0"/></radialGradient>
      ${Object.entries(marks).map(([k, c]) => `<marker id="${p}-m-${k}" viewBox="0 0 10 10" refX="8.5" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto"><path d="M0 0L10 5 0 10z" fill="${c}"/></marker>`).join("")}
    </defs>`;
  }

  function backdrop(p) {
    const wave = (y, cls, op) => {
      let d = `M-80 ${y}`;
      for (let x = -80; x < 640; x += 40) d += " q20 -5 40 0";
      return `<path class="sc-wave ${cls}" d="${d}" fill="none" stroke="#4a9ab3" stroke-width="1.5" opacity="${op}"/>`;
    };
    const stars = [[40, 30], [96, 18], [170, 44], [230, 22], [300, 36], [372, 16], [430, 48], [508, 26], [556, 58]]
      .map(([x, y], i) => `<circle class="sc-twinkle" style="animation-delay:${i * 0.37}s" cx="${x}" cy="${y}" r="1.2" fill="#dff3ff"/>`).join("");
    return `<rect width="${W}" height="${H}" fill="url(#${p}-sky)"/>${stars}
      <circle cx="514" cy="74" r="20" fill="#f7e9b5" opacity=".14"/><circle cx="514" cy="74" r="11" fill="#f7e9b5" opacity=".28"/>
      <rect y="132" width="${BX - 6}" height="${H - 132}" fill="url(#${p}-sea)"/>
      <path d="M0 132 H${BX - 6}" stroke="#4c8ea6" stroke-width="1.2" opacity=".75"/>
      <g>${wave(150, "w1", 0.42)}${wave(184, "w2", 0.34)}${wave(226, "w1", 0.26)}${wave(272, "w2", 0.2)}${wave(318, "w1", 0.16)}</g>`;
  }

  const TONE = {
    plain: ["rgba(8,26,40,.88)", "#3e6680", C.txt], bad: ["rgba(70,18,24,.94)", C.bad, "#ffd2cd"], ok: ["rgba(10,48,36,.92)", C.ok, "#c9f5dc"],
    add: ["rgba(72,40,8,.94)", C.add, "#ffe1c2"], lock: ["rgba(64,48,10,.94)", C.lock, "#fff0c4"], dim: ["rgba(20,34,46,.9)", C.dim, "#b8c9d4"],
    img: ["rgba(8,44,48,.92)", C.img, "#cff7f2"], trk: ["rgba(60,44,10,.92)", C.trk, "#ffe7b3"], lnk: ["rgba(40,30,70,.92)", C.lnk, "#e7deff"],
  };

  function pill(cx, cy, text, tone = "plain", size = 11.5, anchor = "middle") {
    const [fill, stroke, color] = TONE[tone] || TONE.plain;
    const w = tw(text, size) + 16;
    const h = size + 9;
    const x = anchor === "middle" ? cx - w / 2 : anchor === "start" ? cx : cx - w;
    return `<g><rect x="${x.toFixed(1)}" y="${(cy - h / 2).toFixed(1)}" width="${w.toFixed(1)}" height="${h}" rx="${h / 2}" fill="${fill}" stroke="${stroke}" stroke-width="1.2"/>`
      + `<text x="${(x + w / 2).toFixed(1)}" y="${(cy + size * 0.36).toFixed(1)}" text-anchor="middle" font-size="${size}" font-weight="700" fill="${color}">${esc(text)}</text></g>`;
  }

  const toneOf = (state, fallback = "plain") => (state === "miss" ? "bad" : state === "unknown" ? "dim" : fallback);

  function link(p, id, a, b, kind, state, o = {}) {
    const color = state === "miss" ? C.bad : state === "unknown" ? C.dim : o.added ? C.add : C[kind];
    const mark = state === "miss" ? "bad" : state === "unknown" ? "dim" : o.added ? "add" : kind;
    const c = o.c;
    const d = c ? `M${a[0]} ${a[1]} Q${c[0]} ${c[1]} ${b[0]} ${b[1]}` : `M${a[0]} ${a[1]} L${b[0]} ${b[1]}`;
    const pid = `${p}-${id}`;
    const dash = state === "ok" || state === "plain" ? `stroke-dasharray="9 7" class="sc-flow"` : state === "miss" ? `stroke-dasharray="5 6"` : `stroke-dasharray="2 6"`;
    let s = "";
    if (o.added && state === "ok") s += `<path d="${d}" fill="none" stroke="${C.add}" stroke-width="8" opacity=".18" class="sc-pulse"/>`;
    s += `<path id="${pid}" d="${d}" fill="none" stroke="${color}" stroke-width="${o.w || 2.4}" stroke-linecap="round" ${dash} marker-end="url(#${p}-m-${mark})"/>`;
    if ((state === "ok" || state === "plain") && !reduced()) {
      const n = o.packets || 2;
      const dur = o.dur || 2.4;
      for (let i = 0; i < n; i++) {
        s += `<circle r="${o.r || 4.2}" fill="${color}" stroke="#08202f" stroke-width="1"><animateMotion dur="${dur}s" begin="${((i * dur) / n).toFixed(2)}s" repeatCount="indefinite"><mpath href="#${pid}"/></animateMotion></circle>`;
      }
    }
    const lx = c ? 0.25 * a[0] + 0.5 * c[0] + 0.25 * b[0] : (a[0] + b[0]) / 2;
    const ly = c ? 0.25 * a[1] + 0.5 * c[1] + 0.25 * b[1] : (a[1] + b[1]) / 2;
    if (o.label) s += pill(lx + (o.lx || 0), ly + (o.ly ?? -13), o.label, state === "miss" ? "bad" : state === "unknown" ? "dim" : o.added ? "add" : kind, 10.5);
    if (state === "miss") s += pill(lx + (o.lx || 0), ly + (o.ly ?? -13) + 21, "link missing", "bad", 10.5);
    return s;
  }

  function block(x, y, w, h, title, sub, state, o = {}) {
    const stroke = state === "miss" ? C.bad : state === "unknown" ? C.dim : o.added ? C.add : "#5fb6b4";
    const fill = state === "miss" ? "rgba(72,20,26,.82)" : o.added ? "rgba(74,44,12,.82)" : "rgba(13,50,66,.94)";
    let s = `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${fill}" stroke="${stroke}" stroke-width="${o.added || state === "miss" ? 2 : 1.4}" ${state === "miss" ? 'stroke-dasharray="5 4"' : ""}/>`;
    s += `<text x="${x + 9}" y="${y + 17}" font-size="12.5" font-weight="800" fill="${C.txt}">${esc(title)}</text>`;
    if (sub) s += `<text x="${x + 9}" y="${y + 31}" font-size="10" fill="${C.sub}">${esc(fit(sub, w - 14, 10))}</text>`;
    if (state === "miss") s += pill(x + w - 3, y, "missing", "bad", 10, "end");
    else if (o.added) s += pill(x + w - 3, y, state === "unknown" ? "to add" : "added", state === "unknown" ? "dim" : "add", 10, "end");
    else if (o.lock) s += pill(x + w - 3, y, "kept", state === "unknown" ? "dim" : "lock", 10, "end");
    return `<g>${s}</g>`;
  }

  function inside(x, y, w, h, title, from) {
    let s = "";
    if (from) s += `<path d="M${from[0]} ${from[1]} V${y}" stroke="#7fb6c4" stroke-dasharray="3 4" opacity=".75"/><circle cx="${from[0]}" cy="${from[1]}" r="3" fill="#7fb6c4"/>`;
    return `${s}<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="rgba(5,18,28,.78)" stroke="#2f5870"/>`
      + `<text x="${x + 12}" y="${y + 16}" font-size="10.5" fill="${C.sub}" font-weight="800" letter-spacing=".4">${esc(title)}</text>`;
  }

  function stamp(x, y, text) {
    return `<g transform="translate(${x} ${y}) rotate(-7)"><rect x="${-tw(text, 15) / 2 - 18}" y="-19" width="${tw(text, 15) + 36}" height="38" rx="6" fill="rgba(80,14,20,.62)" stroke="${C.bad}" stroke-width="2.5"/>`
      + `<text text-anchor="middle" y="6" font-size="15" font-weight="800" fill="#ffc7c1" letter-spacing="1">${esc(text)}</text></g>`;
  }

  function spotlight(x, y, r, n) {
    let s = `<circle cx="${x}" cy="${y}" r="${r * 1.6}" fill="url(#${spotId})"/>`;
    s += `<circle class="sc-ring" cx="${x}" cy="${y}" r="${r}" fill="none" stroke="#fff3b3" stroke-width="2"/>`;
    if (n != null) s += `<g><circle cx="${x + r * 0.75}" cy="${y - r * 0.75}" r="11" fill="#fff3b3"/><text x="${x + r * 0.75}" y="${y - r * 0.75 + 4}" text-anchor="middle" font-size="12" font-weight="800" fill="#10233a">${n}</text></g>`;
    return s;
  }
  let spotId = "";

  /* ---------------- platforms ---------------- */
  const stateStroke = (st, normal) => (st === "miss" ? C.bad : st === "add" ? C.add : st === "unknown" ? C.dim : normal);

  function usv(p, x, y, s = 1, o = {}) {
    const P = (dx, dy) => [+(x + dx * s).toFixed(1), +(y + dy * s).toFixed(1)];
    let g = `<g transform="translate(${x} ${y}) scale(${s})" opacity="${o.faint ? 0.5 : 1}"><g class="sc-bob">`;
    g += `<ellipse cx="0" cy="5" rx="80" ry="6" fill="#041624" opacity=".5"/>`;
    g += `<path d="M-74 0 L58 0 L80 -16 L-62 -16 Z" fill="url(#${p}-hull)" stroke="${stateStroke(o.state, "#9db6c2")}" stroke-width="1.6"/>`;
    g += `<path d="M-66 -7 H70" stroke="#e07b39" stroke-width="4"/>`;
    g += `<path d="M-34 -16 L-27 -38 H12 L20 -16 Z" fill="#d3e3ea" stroke="#93afbb"/>`;
    g += [-24, -12, 0].map((wx) => `<rect x="${wx}" y="-33" width="9" height="7" rx="1.5" fill="#24506a"/>`).join("");
    g += `<path d="M-4 -38 V-62" stroke="#b9cbd4" stroke-width="3"/>`;
    if (o.eo !== false) g += `<circle cx="-4" cy="-66" r="6.5" fill="#2b5d72" stroke="${stateStroke(o.eoState, "#7fd3d0")}" stroke-width="2.2"/><circle cx="-2" cy="-67" r="2" fill="#bff3ff"/>`;
    if (o.ir) g += `<circle cx="8" cy="-57" r="4.8" fill="#e0893c" stroke="${stateStroke(o.irState, "#ffd09a")}" stroke-width="2"/>`;
    if (o.ais) g += `<path d="M-22 -38 V-62" stroke="${stateStroke(o.aisState, "#d5e4ea")}" stroke-width="2.2"/><circle cx="-22" cy="-63" r="2.6" fill="${stateStroke(o.aisState, "#d5e4ea")}"/>`;
    if (o.radio) g += `<path d="M36 -16 V-50" stroke="${stateStroke(o.radioState, "#c3aedf")}" stroke-width="2.6"/><path d="M28 -54 Q36 -62 44 -54 M24 -59 Q36 -72 48 -59" fill="none" stroke="${stateStroke(o.radioState, "#c3aedf")}" stroke-width="2"/>`;
    g += `</g><path class="sc-wake" d="M-78 3 q-18 4 -36 0 q-18 -4 -36 0" fill="none" stroke="#a6dbe6" stroke-width="2" stroke-dasharray="6 7" opacity=".55"/></g>`;
    return { svg: g, a: { eo: P(-4, -66), ir: P(8, -57), ais: P(-22, -63), radio: P(36, -58), hull: P(-6, -6), bow: P(80, -16), stern: P(-74, -6), top: P(-4, -76) } };
  }

  function uav(p, x, y, s = 1, o = {}) {
    const P = (dx, dy) => [+(x + dx * s).toFixed(1), +(y + dy * s).toFixed(1)];
    let g = `<g transform="translate(${x} ${y}) scale(${s})" opacity="${o.faint ? 0.5 : 1}"><g class="sc-fly">`;
    g += `<path d="M-14 -3 L-4 -3 L22 -28 L12 -28 Z" fill="#c9dbe3" stroke="#93afbb"/>`;
    g += `<path d="M-50 0 Q-20 -10 30 -6 Q47 -3 50 0 Q47 3 30 6 Q-20 10 -50 0 Z" fill="#e4edf2" stroke="${stateStroke(o.state, "#9db6c2")}" stroke-width="1.5"/>`;
    g += `<path d="M-14 3 L-4 3 L16 22 L6 22 Z" fill="#b8ccd6" stroke="#93afbb"/>`;
    g += `<path d="M-47 -1 L-56 -18 L-45 -18 L-39 -2 Z" fill="#c9dbe3" stroke="#93afbb"/>`;
    g += `<ellipse class="sc-prop" cx="-53" cy="0" rx="2" ry="10" fill="#e8f1f5" opacity=".9"/>`;
    if (o.eo !== false) g += `<circle cx="18" cy="8" r="4.8" fill="#2b5d72" stroke="${stateStroke(o.eoState, "#7fd3d0")}" stroke-width="2"/>`;
    if (o.radar) g += `<rect x="-14" y="4" width="18" height="7" rx="3.5" fill="#41657a" stroke="${stateStroke(o.radarState, "#f2b33d")}" stroke-width="1.8"/>`;
    if (o.radio) g += `<path d="M-30 -5 V-17" stroke="${stateStroke(o.radioState, "#c3aedf")}" stroke-width="2"/><path d="M-36 -20 Q-30 -26 -24 -20" fill="none" stroke="${stateStroke(o.radioState, "#c3aedf")}" stroke-width="1.8"/>`;
    g += `</g></g>`;
    return { svg: g, a: { eo: P(18, 12), radar: P(-5, 12), radio: P(-30, -20), body: P(0, 4), tail: P(-50, 0), nose: P(50, 0) } };
  }

  function ship(p, x, y, s = 1, o = {}) {
    const P = (dx, dy) => [+(x + dx * s).toFixed(1), +(y + dy * s).toFixed(1)];
    let g = `<g transform="translate(${x} ${y}) scale(${s})" opacity="${o.faint ? 0.5 : 1}"><g class="sc-bob sc-slow">`;
    g += `<ellipse cx="0" cy="6" rx="130" ry="7" fill="#041624" opacity=".5"/>`;
    g += `<path d="M-122 0 L108 0 L136 -24 L-112 -24 Z" fill="url(#${p}-hull)" stroke="${stateStroke(o.state, "#9db6c2")}" stroke-width="1.6"/>`;
    g += `<path d="M-114 -10 H120" stroke="#2f5f7a" stroke-width="4"/>`;
    g += `<path d="M-64 -24 L-54 -62 H22 L34 -24 Z" fill="#d3e3ea" stroke="#93afbb"/>`;
    g += [-50, -36, -22, -8, 6].map((wx) => `<rect x="${wx}" y="-56" width="10" height="7" rx="1.5" fill="#24506a"/>`).join("");
    g += `<path d="M-14 -62 V-98" stroke="#b9cbd4" stroke-width="3"/><path d="M-26 -84 H-2" stroke="#b9cbd4" stroke-width="2"/>`;
    g += `<g transform="translate(-14 -102)"><g class="sc-radar"><rect x="-17" y="-3" width="34" height="6" rx="3" fill="#e6eef2"/></g></g>`;
    if (o.fusion) g += `<rect x="-44" y="-44" width="52" height="16" rx="4" fill="#0e3445" stroke="${stateStroke(o.fusionState, C.img)}" stroke-width="1.8"/><circle class="sc-pulse" cx="-34" cy="-36" r="4" fill="${stateStroke(o.fusionState, C.img)}"/><text x="-26" y="-32" font-size="9" fill="#cfeaf0" font-weight="700">fusion</text>`;
    g += `</g></g>`;
    return { svg: g, a: { portL: P(-110, -16), portL2: P(-92, -30), portR: P(124, -18), mast: P(-14, -98), fusion: P(-18, -36), deck: P(0, -24), top: P(-14, -110) } };
  }

  function land(x0) {
    return `<path d="M${x0} ${H} L${x0} 176 Q${x0 + 12} 146 ${x0 + 46} 136 L${BX - 6} 128 L${BX - 6} ${H} Z" fill="url(#LAND)" stroke="#5f7f63" stroke-width="1.2"/>`
      + `<path d="M${x0 + 2} 176 Q${x0 + 14} 148 ${x0 + 46} 138" fill="none" stroke="#c9b98a" stroke-width="3" opacity=".55"/>`;
  }

  function station(x, y, s = 1, o = {}) {
    const P = (dx, dy) => [+(x + dx * s).toFixed(1), +(y + dy * s).toFixed(1)];
    let g = `<g transform="translate(${x} ${y}) scale(${s})">`;
    g += `<rect x="-46" y="-56" width="92" height="56" rx="4" fill="#5b7280" stroke="${stateStroke(o.state, "#a9bdc8")}" stroke-width="1.6"/>`;
    g += [-36, -18, 0, 18].map((wx) => `<rect x="${wx}" y="-46" width="12" height="9" rx="1.5" fill="#ffe8a3" opacity=".75" class="sc-twinkle" style="animation-delay:${(wx + 40) / 30}s"/>`).join("");
    g += `<path d="M30 -56 V-96" stroke="#c9d6dd" stroke-width="3"/><path d="M18 -98 Q30 -112 42 -98" fill="none" stroke="#c9d6dd" stroke-width="3"/>`;
    g += `<g transform="translate(30 -104)"><circle class="sc-ring" r="10" fill="none" stroke="#c3aedf" stroke-width="1.5"/></g>`;
    if (o.archive) {
      g += [0, 1, 2].map((i) => `<rect x="${-40 + i * 16}" y="-24" width="12" height="22" rx="2" fill="#20313b" stroke="${stateStroke(o.archiveState, "#7fb6c4")}"/>`
        + `<circle class="sc-blink" style="animation-delay:${i * 0.3}s" cx="${-34 + i * 16}" cy="-18" r="1.8" fill="#63c890"/><circle class="sc-blink" style="animation-delay:${i * 0.3 + 0.5}s" cx="${-34 + i * 16}" cy="-10" r="1.8" fill="#f2b33d"/>`).join("");
    }
    g += `</g>`;
    return { svg: g, a: { antenna: P(30, -104), door: P(-46, -20), roof: P(0, -56), racks: P(-24, -14) } };
  }

  function contact(x, y, s = 0.6) {
    return `<g transform="translate(${x} ${y}) scale(${s})"><g class="sc-bob"><path d="M-40 0 L32 0 L44 -10 L-34 -10 Z" fill="#8aa1ad" stroke="#c3d3db"/><path d="M-12 -10 L-8 -22 H10 L14 -10 Z" fill="#a7bcc6"/></g></g>`;
  }

  function ping(x, y, color = C.trk) {
    return [0, 0.8, 1.6].map((d) => `<circle class="sc-ring" style="animation-delay:${d}s" cx="${x}" cy="${y}" r="14" fill="none" stroke="${color}" stroke-width="1.6"/>`).join("");
  }

  function sweep(x, y, r, color, state) {
    const c = state === "miss" ? C.bad : state === "unknown" ? C.dim : color;
    const wedge = `<path d="M0 0 L${-r * 0.32} ${r} A${r} ${r} 0 0 0 ${r * 0.32} ${r} Z" fill="${c}" opacity=".16"/><path d="M0 0 L0 ${r}" stroke="${c}" stroke-width="1.5" opacity=".7"/>`;
    if (reduced()) return `<g transform="translate(${x} ${y})">${wedge}</g>`;
    return `<g transform="translate(${x} ${y})"><g>${wedge}<animateTransform attributeName="transform" type="rotate" values="-38;38;-38" dur="4s" repeatCount="indefinite"/></g></g>`;
  }

  function cone(from, to, spread, color) {
    return `<path class="sc-pulse" d="M${from[0]} ${from[1]} L${to[0] - spread} ${to[1]} L${to[0] + spread} ${to[1]} Z" fill="${color}" opacity=".14" stroke="${color}" stroke-opacity=".5" stroke-dasharray="4 4"/>`;
  }

  function doc(x, y, title, sub, state, o = {}) {
    const stroke = state === "miss" ? C.bad : state === "unknown" ? C.dim : o.added ? C.add : "#d9e4ea";
    return `<g transform="translate(${x} ${y})"><path d="M0 0 H30 L40 10 V48 H0 Z" fill="#eef4f7" stroke="${stroke}" stroke-width="2"/><path d="M30 0 V10 H40" fill="none" stroke="#b9c9d2"/>`
      + [16, 24, 32, 40].map((ly) => `<path d="M6 ${ly} H${ly === 40 ? 24 : 34}" stroke="#9fb3bf" stroke-width="2"/>`).join("")
      + `<text x="50" y="18" font-size="12" font-weight="800" fill="${C.txt}">${esc(title)}</text><text x="50" y="34" font-size="10.5" fill="${C.sub}">${esc(sub)}</text>`
      + (state === "miss" ? pill(44, 0, "missing", "bad", 10, "end") : o.added ? pill(44, 0, "added", state === "unknown" ? "dim" : "add", 10, "end") : "") + `</g>`;
  }

  function timer(x, y, r, label, state) {
    const c = state === "miss" ? C.bad : state === "unknown" ? C.dim : C.img;
    const len = 2 * Math.PI * r;
    let s = `<circle cx="${x}" cy="${y}" r="${r}" fill="rgba(6,22,34,.85)" stroke="#2f5870" stroke-width="5"/>`;
    s += `<circle cx="${x}" cy="${y}" r="${r}" fill="none" stroke="${c}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${len.toFixed(1)}" stroke-dashoffset="${len.toFixed(1)}" transform="rotate(-90 ${x} ${y})">`
      + (reduced() ? "" : `<animate attributeName="stroke-dashoffset" values="${len.toFixed(1)};0" dur="2s" repeatCount="indefinite"/>`) + `</circle>`;
    s += `<text x="${x}" y="${y + 5}" text-anchor="middle" font-size="14" font-weight="800" fill="${C.txt}">2.0 s</text>`;
    s += pill(x, y + r + 16, label, toneOf(state, "img"), 10.5);
    return s;
  }

  function calendar(x, y, days, state) {
    const c = state === "miss" ? C.bad : state === "unknown" ? C.dim : C.lnk;
    let s = `<rect x="${x - 6}" y="${y - 18}" width="${6 * 16 + 12}" height="${5 * 14 + 26}" rx="6" fill="rgba(6,22,34,.85)" stroke="#2f5870"/>`;
    s += `<text x="${x}" y="${y - 5}" font-size="10" font-weight="800" fill="${C.sub}">days kept</text>`;
    for (let i = 0; i < days; i++) {
      const cx = x + (i % 6) * 16;
      const cy = y + Math.floor(i / 6) * 14;
      s += `<rect x="${cx}" y="${cy}" width="12" height="10" rx="2" fill="${c}" opacity=".9">${reduced() ? "" : `<animate attributeName="opacity" values="0.12;0.95;0.95" keyTimes="0;0.15;1" dur="4s" begin="${(i * 0.09).toFixed(2)}s" repeatCount="indefinite"/>`}</rect>`;
    }
    return s;
  }

  function fog(x, y, text) {
    return `<g class="sc-drift"><circle cx="${x}" cy="${y}" r="22" fill="#cfd8de" opacity=".12"/><circle cx="${x + 16}" cy="${y + 4}" r="16" fill="#cfd8de" opacity=".1"/>${pill(x + 6, y, text, "lock", 12)}</g>`;
  }

  /* ---------------- the checklist board ---------------- */
  const ICON = { ok: ["✓", C.ok], miss: ["✕", C.bad], bad: ["✕", C.bad], unknown: ["·", C.dim], add: ["+", C.add], lock: ["■", C.lock], info: ["•", C.sub], ask: ["?", C.lock], cont: ["", C.sub] };
  const para = (text, size, mono) => wrap(text, BW - 46, size, 3).map((t, i) => ({ text: t, state: i ? "cont" : "info", mono }));

  function statusPills(ctx, x, y) {
    const pills = [];
    if (ctx.live) pills.push(["running", "lock"]);
    else if (ctx.status) pills.push([`task ${ctx.status}`, ctx.status === "PASS" ? "ok" : "bad"]);
    if (ctx.type === "GEN" || ctx.type === "MOD") {
      if (ctx.sysml) pills.push([`syntax ${ctx.sysml}`, ctx.sysml === "PASS" ? "ok" : "bad"]);
      if (ctx.repairs) pills.push([`${ctx.repairs} repair${ctx.repairs > 1 ? "s" : ""}`, "lock"]);
    }
    if (ctx.design && ctx.design !== "UNKNOWN") pills.push([`design ${ctx.design}`, ctx.design === "PASS" ? "ok" : "bad"]);
    let cx = x;
    return pills.map(([t, tone]) => { const s = pill(cx, y, t, tone, 10.5, "start"); cx += tw(t, 10.5) + 22; return s; }).join("");
  }

  function boardLine(x, y, w, it) {
    const [glyph, color] = ICON[it.state] || ICON.info;
    const noteW = it.note ? tw(it.note, 10.5) + 12 : 0;
    let s = `<text x="${x + (it.indent || 0)}" y="${y}" font-size="12.5" font-weight="800" fill="${color}">${glyph}</text>`;
    s += `<text x="${x + 16 + (it.indent || 0)}" y="${y}" font-size="${it.mono ? 11.2 : 12}" font-family="${it.mono ? MONO : SANS}" fill="${it.state === "miss" || it.state === "bad" ? "#ffc9c4" : it.state === "unknown" ? "#9fb3bf" : C.txt}">${esc(fit(it.text, w - 16 - (it.indent || 0) - noteW, it.mono ? 11.2 : 12))}</text>`;
    if (it.note) s += `<text x="${x + w}" y="${y}" text-anchor="end" font-size="10.5" font-weight="700" fill="${color}">${esc(it.note)}</text>`;
    return s;
  }

  function board(ctx, title, sections, foot) {
    const x0 = BX;
    const y0 = 10;
    const h = H - 20;
    const innerW = BW - 30;
    let s = `<rect x="${x0}" y="${y0}" width="${BW}" height="${h}" rx="14" fill="rgba(6,20,32,.95)" stroke="#2b4d63"/>`;
    s += `<text x="${x0 + 15}" y="${y0 + 22}" font-size="13" font-weight="800" fill="${C.txt}">${esc(fit(title, innerW, 13))}</text>`;
    s += statusPills(ctx, x0 + 15, y0 + 42);
    let y = y0 + 64;
    for (const sec of sections) {
      if (!sec || !sec.items || !sec.items.length) continue;
      s += `<text x="${x0 + 15}" y="${y}" font-size="10" font-weight="800" fill="#7fa6b8" letter-spacing=".8">${esc(sec.head)}</text>`;
      if (sec.chips) {
        let cx = x0 + 15;
        y += 17;
        for (const it of sec.items) {
          const cw = tw(it.text, 10.5) + 24;
          if (cx + cw > x0 + BW - 12) { cx = x0 + 15; y += 22; }
          const tone = it.state === "miss" ? "bad" : it.state === "unknown" ? "dim" : it.state === "add" ? "add" : "ok";
          s += pill(cx, y, `${(ICON[it.state] || ICON.ok)[0]} ${it.text}`, tone, 10.5, "start");
          cx += cw + 6;
        }
        y += 22;
      } else {
        for (const it of sec.items) { y += 17; s += boardLine(x0 + 15, y, innerW, it); }
        y += 15;
      }
    }
    if (foot) {
      const lines = wrap(foot.text, innerW, 11, foot.lines || 3);
      const fy = Math.max(y + 4, y0 + h - 12 - lines.length * 15);
      s += lines.map((ln, i) => `<text x="${x0 + 15}" y="${fy + i * 15}" font-size="11" fill="${foot.tone === "bad" ? "#ffc2bc" : C.sub}" font-family="${foot.mono ? MONO : SANS}">${esc(ln)}</text>`).join("");
    }
    return `<g>${s}</g>`;
  }

  function judgedNote(ctx, J) {
    if (ctx.live) return { text: "This cell is running. When it finishes, each item is coloured from the official parse." };
    if (!J.judged && (ctx.type === "GEN" || ctx.type === "MOD")) {
      return { text: ctx.sysml === "FAIL" ? "The official syntax check failed, so the checklist was not applied: none of the items above were judged." : (J.v.reason || "No official parse for this cell."), tone: "bad" };
    }
    return null;
  }

  /* GEN board: definitions as chips, parts tree, attributes, connections. */
  function genBoard(ctx, J, spec) {
    const sections = [];
    if (spec.defs) sections.push({ head: "DEFINITIONS (part def / port def)", chips: true, items: spec.defs.map((d) => ({ text: d, state: J.el(d) })) });
    if (spec.parts) sections.push({ head: "PARTS AND PORTS", items: spec.parts.map(([key, depth, label]) => ({ text: label || key.split("::").pop(), state: J.el(key), indent: depth * 14, note: J.el(key) === "miss" ? "missing" : "" })) });
    if (spec.attrs) {
      sections.push({ head: "ATTRIBUTES (values must match)", items: spec.attrs.map(([key, value, unit]) => {
        const info = J.keepInfo(key);
        const st = J.el(key) === "miss" ? "miss" : J.keep(key);
        return { text: `${key.split("::").pop()} = ${value}${unit ? ` ${unit}` : ""}`, state: st, mono: true, note: info ? `is ${info.actual ?? "missing"}` : st === "ok" ? "value ok" : "" };
      }) });
    }
    if (spec.reqs) sections.push({ head: "REQUIREMENT DEFINITIONS", items: spec.reqs.map(([key, label]) => ({ text: label, state: J.el(key) })) });
    if (spec.links) sections.push({ head: "CONNECTIONS", items: spec.links.map(([a, b]) => ({ text: `${a.split(".").slice(-2).join(".")} → ${b.split(".").slice(-2).join(".")}`, state: J.cn(a, b), mono: true, note: J.cn(a, b) === "miss" ? "missing" : "" })) });
    return board(ctx, spec.title, sections, judgedNote(ctx, J));
  }

  /* MOD board: what the change adds, what must stay, and the expected check. */
  function modBoard(ctx, J, spec) {
    const item = (it) => {
      const st = it.kind === "cn" ? J.cn(it.a, it.b) : it.kind === "keep" ? (J.el(it.key) === "miss" ? "miss" : J.keep(it.key)) : J.el(it.key);
      const info = it.kind === "keep" ? J.keepInfo(it.key) : null;
      return { text: it.text, state: st === "ok" && it.added ? "add" : st, mono: !!it.mono, note: st === "miss" ? (info ? `is ${info.actual ?? "missing"}` : "missing") : it.added && st === "ok" ? "done" : st === "ok" ? "unchanged" : "" };
    };
    const sections = [
      { head: "THIS CHANGE ADDS", items: spec.add.map((it) => item({ ...it, added: true })) },
      { head: "MUST STAY (changing it is wrong)", items: spec.keep.map(item) },
    ];
    if (spec.check) sections.push({ head: "ENGINEERING CHECK", items: [spec.check(J)] });
    return board(ctx, spec.title, sections, judgedNote(ctx, J));
  }

  /* QRY board: the question, then expected against answered. */
  function qryBoard(ctx, spec) {
    const v = ctx.verdict || {};
    const got = v.actual;
    let items;
    if (ctx.live) items = [{ text: "running", state: "unknown" }];
    else if (!v.expected) items = [{ text: "no verdict for this cell", state: "unknown" }];
    else if (v.reason && !got) items = [{ text: `answer is not JSON: ${v.reason}`, state: "bad" }];
    else items = spec.compare(v.expected, got || {});
    return board(ctx, spec.title, [
      { head: "QUESTION", items: para(spec.question, 12) },
      { head: "ANSWER KEY → AGENT'S ANSWER", items },
    ], ctx.answer ? { text: `Agent wrote: ${String(ctx.answer).replace(/\s+/g, " ").slice(0, 220)}`, lines: 3, mono: true } : null);
  }

  const norm = (x) => String(x ?? "").trim();
  function listCompare(expected, got, label) {
    const set = new Set((got || []).map(norm));
    const rows = (expected || []).map((name) => ({ text: name, state: set.has(norm(name)) ? "ok" : "miss", mono: true, note: set.has(norm(name)) ? "answered" : "not given" }));
    for (const extra of (got || []).filter((g) => !(expected || []).map(norm).includes(norm(g)))) rows.push({ text: extra, state: "bad", mono: true, note: "not in key" });
    if (!got) rows.unshift({ text: `the answer has no ${label}`, state: "bad" });
    return rows;
  }
  const numEq = (a, b) => a != null && b != null && Number(a) === Number(b);

  /* AMB board: which missing values the answer asked about. */
  function ambBoard(ctx, spec) {
    const v = ctx.verdict || {};
    const missing = (v.missing_questions || []).map((g) => norm(g[0]).toLowerCase());
    const items = spec.groups.map(([first, label]) => {
      const asked = !ctx.live && v.missing_questions && !missing.includes(first);
      return { text: `asks about ${label}`, state: ctx.live || !v.missing_questions ? "unknown" : asked ? "ok" : "miss", note: ctx.live || !v.missing_questions ? "" : asked ? "asked" : "not asked" };
    });
    if (v.missing_questions) {
      items.push({ text: "invents no number", state: v.invented_number ? "bad" : "ok", note: v.invented_number ? "invented" : "none" });
      items.push({ text: "uses a question mark", state: v.asked ? "ok" : "bad", note: v.asked ? "yes" : "no ?" });
    }
    return board(ctx, spec.title, [
      { head: "TASK STATEMENT", items: para(spec.brief, 12) },
      { head: "RIGHT MOVE: STOP AND ASK", items },
    ], ctx.answer ? { text: `Agent wrote: ${String(ctx.answer).replace(/\s+/g, " ").slice(0, 220)}`, lines: 3 } : null);
  }

  /* RT board: model text, the phrases the read-back must keep, and the answer. */
  function rtBoard(ctx, spec) {
    const v = ctx.verdict || {};
    const missing = new Set((v.missing || []).map((m) => m.toLowerCase()));
    const judged = !ctx.live && Array.isArray(v.missing);
    return board(ctx, spec.title, [
      { head: "WRITTEN IN THE MODEL", items: para(spec.doc, 11.2, true) },
      { head: "READ-BACK MUST MENTION", items: spec.phrases.map((ph) => ({ text: ph, state: !judged ? "unknown" : missing.has(ph.toLowerCase()) ? "miss" : "ok", note: !judged ? "" : missing.has(ph.toLowerCase()) ? "missing" : "mentioned" })) },
    ], ctx.answer ? { text: `Agent read back: ${String(ctx.answer).replace(/\s+/g, " ").slice(0, 240)}`, lines: 4 } : null);
  }

  /* ---------------- the 24 scenes ---------------- */
  const S = {};

  S["GEN-01"] = (p, ctx, J) => {
    const boat = usv(p, 120, 150, 1, { radio: true, eoState: J.el("usv::camera"), radioState: J.el("usv::radio"), state: J.el("usv") });
    const cmd = ship(p, 440, 152, 0.8, { state: J.el("commandShip") });
    let s = boat.svg + cmd.svg;
    s += inside(16, 196, 400, 130, "inside usv: three parts and two connections to write", boat.a.hull);
    s += block(30, 236, 104, 46, "camera", "Camera · imagery", J.el("usv::camera"));
    s += block(168, 236, 112, 46, "processor", "imageryIn · uplink", J.el("usv::processor"));
    s += block(314, 236, 90, 46, "radio", "fromProcessor · toShore", J.el("usv::radio"));
    s += link(p, "c1", [134, 259], [168, 259], "img", J.cn("usv.camera.imagery", "usv.processor.imageryIn"), { label: "imagery", ly: -32 });
    s += link(p, "c2", [280, 259], [314, 259], "lnk", J.cn("usv.processor.uplink", "usv.radio.fromProcessor"), { label: "uplink", ly: -32 });
    s += link(p, "c3", [359, 236], cmd.a.portL, "lnk", J.cn("usv.radio.toShore", "commandShip.fromUsv"), { c: [420, 210], label: "toShore → fromUsv", lx: 60, ly: -16, dur: 2.8 });
    s += pill(cmd.a.top[0] + 8, cmd.a.top[1] - 4, "commandShip", toneOf(J.el("commandShip")), 11);
    return { s, stamp: [262, 62], title: "GEN-01 · from scratch: the USV sends imagery via processor and radio to the command ship",
      board: genBoard(ctx, J, { title: "Checklist: UsvLink must contain",
        defs: ["ImageryPort", "LinkPort", "Camera", "Processor", "Radio", "CommandShip"],
        parts: [["usv", 0], ["usv::camera", 1, "camera : Camera"], ["usv::processor", 1, "processor : Processor"], ["usv::radio", 1, "radio : Radio"], ["commandShip", 0, "commandShip : CommandShip"]],
        links: [["usv.camera.imagery", "usv.processor.imageryIn"], ["usv.processor.uplink", "usv.radio.fromProcessor"], ["usv.radio.toShore", "commandShip.fromUsv"]] }) };
  };

  S["GEN-02"] = (p, ctx, J) => {
    const plane = uav(p, 262, 62, 1.15, { radar: true, radio: true, eoState: J.el("uav::eoCamera"), radarState: J.el("uav::searchRadar"), radioState: J.el("uav::radio"), state: J.el("uav") });
    let s = sweep(plane.a.radar[0], plane.a.radar[1], 118, C.trk, J.el("uav::searchRadar"));
    s += contact(118, 168, 0.75) + contact(420, 182, 0.6);
    s += cone(plane.a.eo, [118, 172], 34, C.img);
    s += plane.svg;
    s += inside(16, 200, 556, 128, "inside uav: two sensors feed the processor, then the radio", plane.a.body);
    s += block(28, 222, 116, 42, "searchRadar", "Radar · tracks", J.el("uav::searchRadar"));
    s += block(28, 276, 116, 42, "eoCamera", "Camera · imagery", J.el("uav::eoCamera"));
    s += block(214, 246, 122, 46, "processor", "trackIn · imageryIn · uplink", J.el("uav::processor"));
    s += block(420, 246, 108, 46, "radio", "fromProcessor · toShore", J.el("uav::radio"));
    s += link(p, "c1", [144, 243], [214, 262], "trk", J.cn("uav.searchRadar.tracks", "uav.processor.trackIn"), { label: "tracks", ly: -14 });
    s += link(p, "c2", [144, 297], [214, 278], "img", J.cn("uav.eoCamera.imagery", "uav.processor.imageryIn"), { label: "imagery", ly: 18 });
    s += link(p, "c3", [336, 269], [420, 269], "lnk", J.cn("uav.processor.uplink", "uav.radio.fromProcessor"), { label: "uplink", ly: -14 });
    return { s, stamp: [452, 110], title: "GEN-02 · from scratch: the UAV's radar and camera feed one processor",
      board: genBoard(ctx, J, { title: "Checklist: UavSearch must contain",
        defs: ["Radar", "Camera", "Processor", "Radio"],
        parts: [["uav", 0], ["uav::searchRadar", 1, "searchRadar : Radar"], ["uav::eoCamera", 1, "eoCamera : Camera"], ["uav::processor", 1, "processor : Processor"], ["uav::radio", 1, "radio : Radio"]],
        links: [["uav.searchRadar.tracks", "uav.processor.trackIn"], ["uav.eoCamera.imagery", "uav.processor.imageryIn"], ["uav.processor.uplink", "uav.radio.fromProcessor"]] }) };
  };

  S["GEN-03"] = (p, ctx, J) => {
    const cmd = ship(p, 300, 168, 1.1, { fusion: true, fusionState: J.el("commandShip::fusion"), state: J.el("commandShip") });
    const boat = usv(p, 64, 222, 0.55, { faint: true, radio: true });
    const plane = uav(p, 92, 58, 0.62, { faint: true, radio: true, radar: true });
    let s = boat.svg + plane.svg + cmd.svg;
    s += `<path d="M${boat.a.radio[0]} ${boat.a.radio[1]} Q150 160 ${cmd.a.portL[0]} ${cmd.a.portL[1]}" fill="none" stroke="${C.dim}" stroke-dasharray="2 6"/>`;
    s += `<path d="M${plane.a.radio[0]} ${plane.a.radio[1]} Q160 70 ${cmd.a.portL2[0]} ${cmd.a.portL2[1]}" fill="none" stroke="${C.dim}" stroke-dasharray="2 6"/>`;
    s += `<circle cx="${cmd.a.portL[0]}" cy="${cmd.a.portL[1]}" r="6" fill="${stateStroke(J.el("commandShip::fromUsv"), C.lnk)}"/>` + pill(cmd.a.portL[0] - 4, cmd.a.portL[1] + 26, "port fromUsv", toneOf(J.el("commandShip::fromUsv"), "lnk"), 10.5);
    s += `<circle cx="${cmd.a.portL2[0]}" cy="${cmd.a.portL2[1]}" r="6" fill="${stateStroke(J.el("commandShip::fromUav"), C.lnk)}"/>` + pill(cmd.a.portL2[0] - 26, cmd.a.portL2[1] - 22, "port fromUav", toneOf(J.el("commandShip::fromUav"), "lnk"), 10.5);
    s += `<path d="M${cmd.a.fusion[0]} ${cmd.a.fusion[1]} Q420 60 474 76" fill="none" stroke="#7fb6c4" stroke-dasharray="3 4"/>`;
    const lat = J.el("commandShip::fusionLatencyS") === "miss" ? "miss" : J.keep("commandShip::fusionLatencyS");
    s += timer(506, 84, 28, "fusionLatencyS = 2.0", lat);
    s += pill(150, 300, "ports and a fusion processor only; no links required", "dim", 11);
    return { s, stamp: [400, 262], title: "GEN-03 · from scratch: the command ship's fusion node, 2.0 s latency",
      board: genBoard(ctx, J, { title: "Checklist: FusionNode must contain",
        defs: ["LinkPort", "Processor"],
        parts: [["commandShip", 0, "commandShip"], ["commandShip::fromUsv", 1, "port fromUsv : LinkPort"], ["commandShip::fromUav", 1, "port fromUav : LinkPort"], ["commandShip::fusion", 1, "fusion : Processor"]],
        attrs: [["commandShip::fusionLatencyS", "2.0", "s"]] }) };
  };

  S["GEN-04"] = (p, ctx, J) => {
    const st = station(452, 132, 1.05, { archive: true, archiveState: J.el("shore::archive"), state: J.el("shore") });
    const cmd = ship(p, 120, 168, 0.66, { faint: true });
    let s = land(330).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + cmd.svg;
    const back = J.el("shore::backhaulMbps") === "miss" ? "miss" : J.keep("shore::backhaulMbps");
    s += link(p, "c1", cmd.a.mast, st.a.door, "lnk", back === "ok" && J.el("shore::fromCommand") === "ok" ? "ok" : J.el("shore::fromCommand") === "miss" ? "miss" : back, { c: [300, 40], label: "backhaulMbps = 50", ly: -6, dur: 3 });
    s += pill(st.a.door[0] - 2, st.a.door[1] + 22, "port fromCommand", toneOf(J.el("shore::fromCommand"), "lnk"), 10.5, "end");
    s += pill(st.a.racks[0] + 4, st.a.racks[1] + 30, "archive : Processor", toneOf(J.el("shore::archive"), "img"), 10.5);
    const days = J.el("shore::archiveDays") === "miss" ? "miss" : J.keep("shore::archiveDays");
    s += calendar(352, 222, 30, days) + pill(406, 318, "archiveDays = 30", toneOf(days, "lnk"), 10.5);
    s += doc(40, 238, "ShoreArchiveRetention", "keep the archive 30 days", J.el("ShoreArchiveRetention"));
    return { s, stamp: [180, 200], title: "GEN-04 · from scratch: shore archive, 50 Mbps backhaul, kept 30 days",
      board: genBoard(ctx, J, { title: "Checklist: ShoreArchive must contain",
        parts: [["shore", 0, "shore"], ["shore::fromCommand", 1, "port fromCommand : LinkPort"], ["shore::archive", 1, "archive : Processor"]],
        attrs: [["shore::backhaulMbps", "50.0", "Mbps"], ["shore::archiveDays", "30.0", "days"]],
        reqs: [["ShoreArchiveRetention", "ShoreArchiveRetention (doc says keep 30 days)"]] }) };
  };

  S["GEN-05"] = (p, ctx, J) => {
    const st = station(518, 132, 0.72, { state: J.el("shore") });
    const boat = usv(p, 82, 214, 0.72, { radio: true, radioState: J.el("usv::radio"), state: J.el("usv") });
    const plane = uav(p, 96, 54, 0.8, { radio: true, radioState: J.el("uav::radio"), state: J.el("uav") });
    const cmd = ship(p, 300, 178, 0.78, { state: J.el("commandShip") });
    let s = land(452).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + boat.svg + plane.svg + cmd.svg;
    s += link(p, "c1", boat.a.radio, cmd.a.portL, "lnk", J.cn("usv.radio.toCommand", "commandShip.fromUsv"), { c: [150, 120], label: "usv → fromUsv", ly: -4 });
    s += link(p, "c2", plane.a.radio, cmd.a.mast, "lnk", J.cn("uav.radio.toCommand", "commandShip.fromUav"), { c: [210, 20], label: "uav → fromUav", ly: 6 });
    s += link(p, "c3", cmd.a.portR, st.a.antenna, "lnk", J.cn("commandShip.toShore", "shore.fromCommand"), { c: [440, 60], label: "toShore → fromCommand", ly: -8, lx: -10 });
    s += pill(boat.a.stern[0] + 10, boat.a.stern[1] + 34, "usv", toneOf(J.el("usv")), 10.5) + pill(plane.a.nose[0] + 6, plane.a.nose[1] - 18, "uav", toneOf(J.el("uav")), 10.5);
    s += pill(cmd.a.deck[0], cmd.a.deck[1] + 50, "commandShip", toneOf(J.el("commandShip")), 10.5) + pill(st.a.roof[0], st.a.roof[1] + 76, "shore", toneOf(J.el("shore")), 10.5);
    return { s, stamp: [300, 282], title: "GEN-05 · from scratch: four platforms and three links",
      board: genBoard(ctx, J, { title: "Checklist: FourNode must contain",
        parts: [["usv", 0, "usv"], ["usv::radio", 1, "radio : Radio"], ["uav", 0, "uav"], ["uav::radio", 1, "radio : Radio"], ["commandShip", 0, "commandShip (three ports)"], ["shore", 0, "shore : ShoreStation"]],
        links: [["usv.radio.toCommand", "commandShip.fromUsv"], ["uav.radio.toCommand", "commandShip.fromUav"], ["commandShip.toShore", "shore.fromCommand"]] }) };
  };

  S["MOD-01"] = (p, ctx, J) => {
    const boat = usv(p, 132, 150, 1.05, { ir: true, ais: true, radio: true, irState: J.el("usv::irCamera") === "ok" ? "add" : J.el("usv::irCamera"), eoState: J.el("usv::eoCamera"), aisState: J.el("usv::ais") });
    let s = boat.svg;
    s += pill(330, 70, "powerLimitW = 60 · fixed", toneOf(J.keep("usv::powerLimitW"), "lock"), 11);
    s += inside(16, 192, 556, 136, "inside usv: wire the new infrared camera to the processor; keep the existing links", boat.a.hull);
    s += block(28, 216, 106, 30, "eoCamera", "", J.el("usv::eoCamera"), { lock: true });
    s += block(28, 253, 106, 30, "irCamera", "", J.el("usv::irCamera"), { added: true });
    s += block(28, 290, 106, 30, "ais", "", J.el("usv::ais"), { lock: true });
    s += block(222, 240, 122, 46, "processor", "imageryIn · trackIn · uplink", "ok");
    s += block(440, 240, 104, 46, "radio", "fromProcessor", "ok");
    s += link(p, "c1", [134, 231], [222, 254], "img", J.cn("usv.eoCamera.imagery", "usv.processor.imageryIn"), { label: "kept", ly: -10, lx: -6 });
    s += link(p, "c2", [134, 268], [222, 264], "img", J.cn("usv.irCamera.imagery", "usv.processor.imageryIn"), { added: true, label: "added", ly: -9 });
    s += link(p, "c3", [134, 305], [222, 276], "trk", J.cn("usv.ais.tracks", "usv.processor.trackIn"), { label: "kept", ly: 14, lx: -6 });
    s += link(p, "c4", [344, 263], [440, 263], "lnk", "plain", { label: "uplink (not checked)", ly: -36 });
    return { s, title: "MOD-01 · edit: add an infrared camera, change nothing else",
      board: modBoard(ctx, J, { title: "Checklist: UsvPlain after the change",
        add: [{ key: "usv::irCamera", text: "part irCamera : Camera" }, { kind: "cn", a: "usv.irCamera.imagery", b: "usv.processor.imageryIn", text: "irCamera.imagery → processor.imageryIn", mono: true }],
        keep: [{ key: "usv::eoCamera", text: "part eoCamera" }, { key: "usv::ais", text: "part ais" },
          { kind: "cn", a: "usv.eoCamera.imagery", b: "usv.processor.imageryIn", text: "eoCamera.imagery → processor", mono: true },
          { kind: "cn", a: "usv.ais.tracks", b: "usv.processor.trackIn", text: "ais.tracks → processor.trackIn", mono: true },
          { kind: "keep", key: "usv::powerLimitW", text: "powerLimitW = 60.0", mono: true }] }) };
  };

  S["MOD-02"] = (p, ctx, J) => {
    const boat = usv(p, 150, 152, 1.05, { ais: true, radio: false, aisState: J.el("vessel::ais") === "ok" ? "add" : J.el("vessel::ais"), eoState: J.el("vessel::camera") });
    let s = contact(420, 150, 0.62) + contact(500, 182, 0.55) + ping(420, 138) + ping(500, 172);
    s += link(p, "a1", [410, 132], boat.a.ais, "trk", J.el("vessel::ais") === "miss" ? "miss" : J.el("vessel::ais"), { c: [300, 60], added: true, label: "AIS tracks", ly: -4 });
    s += boat.svg;
    s += inside(16, 196, 556, 132, "inside vessel: wire the new AIS to the processor; imagery and tracks share one timestamp", boat.a.hull);
    s += block(28, 224, 112, 40, "camera", "Camera · imagery", J.el("vessel::camera"), { lock: true });
    s += block(28, 278, 112, 40, "ais", "AisReceiver · tracks", J.el("vessel::ais"), { added: true });
    s += block(222, 240, 116, 46, "processor", "imageryIn · trackIn", "ok");
    s += link(p, "c1", [140, 244], [222, 256], "img", J.cn("vessel.camera.imagery", "vessel.processor.imageryIn"), { label: "kept", ly: -10 });
    s += link(p, "c2", [140, 298], [222, 272], "trk", J.cn("vessel.ais.tracks", "vessel.processor.trackIn"), { added: true, label: "added", ly: 16 });
    s += doc(392, 226, "TimeAlign", "tracks and imagery share a timestamp", J.el("TimeAlign"), { added: true });
    s += `<g transform="translate(366 263)"><circle r="14" fill="#0e3445" stroke="${C.lock}" stroke-width="2"/><path d="M0 -8 V0 L6 4" stroke="${C.lock}" stroke-width="2" fill="none"/></g>`;
    return { s, title: "MOD-02 · edit: add an AIS receiver and a time-alignment requirement",
      board: modBoard(ctx, J, { title: "Checklist: VesselAlign after the change",
        add: [{ key: "vessel::ais", text: "part ais : AisReceiver" }, { kind: "cn", a: "vessel.ais.tracks", b: "vessel.processor.trackIn", text: "ais.tracks → processor.trackIn", mono: true }, { key: "TimeAlign", text: "requirement TimeAlign (shared timestamp)" }],
        keep: [{ key: "vessel::camera", text: "part camera" }, { kind: "cn", a: "vessel.camera.imagery", b: "vessel.processor.imageryIn", text: "camera.imagery → processor.imageryIn", mono: true }] }) };
  };

  S["MOD-03"] = (p, ctx, J) => {
    const st = station(500, 132, 0.85, { state: J.el("shore") });
    const boat = usv(p, 130, 156, 1.05, { radio: true, radioState: J.el("vessel::radio") });
    let s = land(410).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + boat.svg;
    s += link(p, "c2", boat.a.radio, st.a.antenna, "lnk", J.cn("vessel.radio.toShore", "shore.fromVessel"), { c: [330, 10], added: true, label: "added: radio.toShore → shore.fromVessel", ly: 2, dur: 3 });
    s += pill(st.a.roof[0], st.a.roof[1] + 72, "shore : ShoreStation", toneOf(J.el("shore")), 10.5);
    s += inside(16, 214, 330, 112, "inside vessel: this existing link must stay", boat.a.hull);
    s += block(30, 250, 112, 46, "processor", "uplink", "ok");
    s += block(214, 250, 112, 46, "radio", "fromProcessor · toShore", J.el("vessel::radio"), { lock: true });
    s += link(p, "c1", [142, 273], [214, 273], "lnk", J.cn("vessel.processor.uplink", "vessel.radio.fromProcessor"), { label: "kept", ly: -14 });
    return { s, stamp: [280, 186], title: "MOD-03 · edit: add a link from the vessel radio to the shore",
      board: modBoard(ctx, J, { title: "Checklist: ShoreHop after the change",
        add: [{ kind: "cn", a: "vessel.radio.toShore", b: "shore.fromVessel", text: "radio.toShore → shore.fromVessel", mono: true }],
        keep: [{ key: "vessel::radio", text: "part vessel.radio" }, { key: "shore", text: "part shore" }, { kind: "cn", a: "vessel.processor.uplink", b: "vessel.radio.fromProcessor", text: "processor.uplink → radio.fromProcessor", mono: true }] }) };
  };

  S["MOD-04"] = (p, ctx, J) => {
    const boat = usv(p, 150, 152, 1.05, { radio: true });
    let s = boat.svg;
    s += pill(360, 66, "uplinkMbps = 8 · fixed", toneOf(J.el("usv::uplinkMbps") === "miss" ? "miss" : J.keep("usv::uplinkMbps"), "lock"), 11);
    s += inside(16, 196, 556, 132, "usv.radio: add a health port; the uplink stays at 8", boat.a.hull);
    s += block(36, 236, 150, 56, "radio", "port fromProcessor (existing)", "ok", { lock: true });
    const health = J.el("usv::radio::health");
    s += `<rect x="186" y="256" width="14" height="14" rx="3" fill="${health === "miss" ? C.bad : health === "unknown" ? C.dim : C.add}"/>` + pill(193, 306, "port health : LinkPort", health === "miss" ? "bad" : health === "unknown" ? "dim" : "add", 10.5);
    const ecg = "M206 263 H250 L258 246 L266 280 L274 236 L282 263 H330 L338 250 L346 276 L354 263 H420";
    s += `<path d="${ecg}" fill="none" stroke="${health === "miss" ? C.bad : health === "unknown" ? C.dim : C.add}" stroke-width="2.4" stroke-dasharray="${health === "ok" ? "220 400" : "4 6"}">${health === "ok" && !reduced() ? `<animate attributeName="stroke-dashoffset" values="220;-400" dur="2.2s" repeatCount="indefinite"/>` : ""}</path>`;
    s += `<rect x="428" y="230" width="112" height="64" rx="8" fill="#0b2a36" stroke="#2f5870"/><text x="440" y="252" font-size="11" fill="${C.sub}" font-weight="800">health monitor</text><circle class="sc-blink" cx="520" cy="248" r="4" fill="${health === "ok" ? C.ok : C.dim}"/><text x="440" y="276" font-size="12" fill="${C.txt}">heartbeat · link ok</text>`;
    return { s, title: "MOD-04 · edit: give the radio a health port",
      board: modBoard(ctx, J, { title: "Checklist: RadioHealth after the change",
        add: [{ key: "usv::radio::health", text: "port radio.health : LinkPort" }],
        keep: [{ kind: "keep", key: "usv::uplinkMbps", text: "uplinkMbps = 8.0", mono: true }] }) };
  };

  S["MOD-05"] = (p, ctx, J) => {
    const boat = usv(p, 132, 150, 1.05, { ir: true, irState: J.el("usv::irCamera") === "ok" ? "add" : J.el("usv::irCamera") });
    let s = boat.svg;
    s += inside(16, 190, 556, 138, "usv's 24 V equipment box: the three devices' power summed against the limit", boat.a.hull);
    const chk = (J.v.checks || [])[0] || {};
    const draws = { eo: 41, cpu: 25, ir: 12 };
    const keepEo = J.keep("usv::eoCamera::drawW");
    const keepCpu = J.keep("usv::computer::drawW");
    const keepIr = J.el("usv::irCamera") === "miss" ? "miss" : J.keep("usv::irCamera::drawW");
    s += block(28, 216, 124, 30, "eoCamera 41 W", "", keepEo, { lock: true });
    s += block(28, 253, 124, 30, "computer 25 W", "", keepCpu, { lock: true });
    s += block(28, 290, 124, 30, "irCamera 12 W", "", keepIr, { added: true });
    const x0 = 196;
    const scale = 3.6;
    const limit = 60;
    const bar = (from, w, color, delay) => `<rect x="${(x0 + from * scale).toFixed(1)}" y="250" width="${(w * scale).toFixed(1)}" height="30" fill="${color}" stroke="#0a2230">${reduced() ? "" : `<animate attributeName="width" values="0;${(w * scale).toFixed(1)};${(w * scale).toFixed(1)}" keyTimes="0;0.25;1" dur="6s" begin="${delay}s" repeatCount="indefinite"/>`}</rect>`;
    s += `<rect x="${x0}" y="250" width="${(100 * scale).toFixed(0)}" height="30" rx="4" fill="#0b2230" stroke="#2f5870"/>`;
    s += bar(0, draws.eo, "#3aa58a", 0) + bar(draws.eo, draws.cpu, "#2f8fb0", 0.5) + bar(draws.eo + draws.cpu, draws.ir, C.add, 1);
    s += `<rect x="${x0 + limit * scale}" y="250" width="${(18 * scale).toFixed(1)}" height="30" fill="${C.bad}" opacity=".35" class="sc-pulse"/>`;
    const keepLimit = J.keep("usv::powerLimitW");
    s += `<path d="M${x0 + limit * scale} 236 V292" stroke="${keepLimit === "miss" ? C.bad : C.lock}" stroke-width="3"/>` + pill(x0 + limit * scale, 226, "limit 60 W · fixed", toneOf(keepLimit, "lock"), 10.5);
    s += `<text x="${x0}" y="304" font-size="11.5" fill="${C.txt}" font-weight="700">41 + 25 + 12 = ${chk.total_w != null ? chk.total_w : 78} W</text>`;
    s += `<text x="${x0 + 100 * scale}" y="304" text-anchor="end" font-size="11.5" fill="${C.bad}" font-weight="800">over by ${chk.total_w != null && chk.limit_w != null ? chk.total_w - chk.limit_w : 18} W</text>`;
    if (J.judged) s += pill(x0 + 180, 318, chk.match ? "over budget, reported honestly, as the key expects" : "check result differs from the key", chk.match ? "ok" : "bad", 10.5);
    return { s, title: "MOD-05 · edit: add a 12 W infrared camera; the 60 W limit cannot change",
      board: modBoard(ctx, J, { title: "Checklist: PowerBudget after the change",
        add: [{ key: "usv::irCamera", text: "part irCamera" }, { kind: "keep", key: "usv::irCamera::drawW", text: "irCamera.drawW = 12.0", mono: true }],
        keep: [{ kind: "keep", key: "usv::powerLimitW", text: "powerLimitW = 60.0", mono: true }, { kind: "keep", key: "usv::eoCamera::drawW", text: "eoCamera.drawW = 41.0", mono: true }, { kind: "keep", key: "usv::computer::drawW", text: "computer.drawW = 25.0", mono: true }],
        check: (JJ) => {
          const c = (JJ.v.checks || [])[0];
          if (!JJ.judged || !c) return { text: "R-POWER-001: not judged yet", state: "unknown" };
          return { text: `R-POWER-001 ${c.actual} (${c.total_w}/${c.limit_w} W), key ${c.expected}`, state: c.match ? "ok" : "miss", note: c.match ? "match" : "mismatch" };
        } }) };
  };

  /* The maritime ISR model behind QRY-01 … 05. */
  function isr(p, o = {}) {
    const st = station(528, 132, 0.66, { archive: true });
    const plane = uav(p, 126, 50, 0.82, { radar: true, radio: true });
    const boat = usv(p, 104, 206, 0.74, { ir: true, ais: true, radio: true });
    const cmd = ship(p, 318, 186, 0.74, { fusion: true });
    let s = land(470).replace("url(#LAND)", `url(#${p}-land)`) + st.svg;
    s += sweep(plane.a.radar[0], plane.a.radar[1], 96, C.trk, "ok");
    s += boat.svg + plane.svg + cmd.svg;
    const tone = (k) => (o.hot && o.hot.includes(k) ? "ok" : "plain");
    s += link(p, "l1", boat.a.radio, cmd.a.portL, "lnk", tone("l1"), { c: [180, 150], w: o.hot && o.hot.includes("l1") ? 4 : 2.2 });
    s += link(p, "l2", plane.a.radio, cmd.a.mast, "lnk", tone("l2"), { c: [230, 30], w: o.hot && o.hot.includes("l2") ? 4 : 2.2 });
    s += link(p, "l3", cmd.a.portR, st.a.antenna, "lnk", tone("l3"), { c: [450, 70], w: o.hot && o.hot.includes("l3") ? 4 : 2.2 });
    return { s, a: { st, plane, boat, cmd } };
  }

  S["QRY-01"] = (p, ctx) => {
    const base = isr(p);
    let s = base.s;
    s += spotlight(base.a.boat.a.hull[0], base.a.boat.a.hull[1] - 20, 44, 1) + spotlight(base.a.plane.a.body[0], base.a.plane.a.body[1], 40, 2);
    s += spotlight(base.a.cmd.a.deck[0] - 10, base.a.cmd.a.deck[1] - 20, 52, 3) + spotlight(base.a.st.a.roof[0], base.a.st.a.roof[1] + 20, 40, 4);
    return { s, title: "QRY-01 · query: name the four platforms",
      board: qryBoard(ctx, { title: "Read MaritimeISR and answer", question: "Which four platform part usages does the model contain? Give their qualified names.",
        compare: (e, g) => listCompare(e.platforms, g.platforms, "platforms") }) };
  };

  S["QRY-02"] = (p, ctx) => {
    const base = isr(p);
    let s = base.s + spotlight(base.a.boat.a.hull[0], base.a.boat.a.hull[1] - 18, 46, null);
    s += pill(base.a.boat.a.top[0] + 70, base.a.boat.a.top[1] - 6, "powerLimitW = 60", "lock", 12);
    return { s, title: "QRY-02 · query: the USV's power limit",
      board: qryBoard(ctx, { title: "Read MaritimeISR and answer", question: "What does UnmannedSurfaceVessel's powerLimitW parse to?",
        compare: (e, g) => [
          { text: `attribute: ${g.attribute ?? "(none)"}`, state: norm(g.attribute) === norm(e.attribute) ? "ok" : "miss", mono: true, note: norm(g.attribute) === norm(e.attribute) ? "right" : `key: …${String(e.attribute).split("::").slice(-2).join("::")}` },
          { text: `value: ${g.value ?? "(none)"}`, state: numEq(g.value, e.value) ? "ok" : "miss", mono: true, note: numEq(g.value, e.value) ? "right" : `key: ${e.value}` }] }) };
  };

  S["QRY-03"] = (p, ctx) => {
    const base = isr(p, { hot: ["l1", "l2", "l3"] });
    let s = base.s + spotlight(base.a.cmd.a.deck[0] - 10, base.a.cmd.a.deck[1] - 20, 56, null);
    s += pill(196, 160, "1", "lnk", 13) + pill(226, 76, "2", "lnk", 13) + pill(430, 98, "3", "lnk", 13);
    s += pill(318, 238, "connections ending on commandShip: 3", "ok", 12);
    return { s, title: "QRY-03 · query: how many links touch the command ship",
      board: qryBoard(ctx, { title: "Read MaritimeISR and answer", question: "How many connect statements have an endpoint on commandShip?",
        compare: (e, g) => [{ text: `connections: agent ${g.connections ?? "(none)"}, key ${e.connections}`, state: numEq(g.connections, e.connections) ? "ok" : "miss", note: numEq(g.connections, e.connections) ? "right" : "wrong" }] }) };
  };

  S["QRY-04"] = (p, ctx) => {
    const base = isr(p);
    let s = base.s + spotlight(base.a.plane.a.body[0], base.a.plane.a.body[1], 48, null);
    s += `<rect x="236" y="20" width="182" height="96" rx="10" fill="rgba(6,22,34,.9)" stroke="#2f5870"/><text x="248" y="38" font-size="10.5" font-weight="800" fill="${C.sub}">parts in FixedWingUav</text>`;
    s += ["eoCamera", "searchRadar", "processor", "radio"].map((n, i) => `<text x="250" y="${58 + i * 16}" font-size="12" fill="${C.txt}" font-family="${MONO}">• ${n}</text>`).join("");
    s += `<path d="M${base.a.plane.a.nose[0]} ${base.a.plane.a.nose[1]} L236 60" stroke="#7fb6c4" stroke-dasharray="3 4"/>`;
    return { s, title: "QRY-04 · query: which parts are inside the UAV",
      board: qryBoard(ctx, { title: "Read MaritimeISR and answer", question: "Which part usages are nested in part def FixedWingUav? Give qualified names.",
        compare: (e, g) => listCompare(e.parts, g.parts, "parts") }) };
  };

  S["QRY-05"] = (p, ctx) => {
    const base = isr(p);
    let s = base.s + spotlight(base.a.boat.a.hull[0], base.a.boat.a.hull[1] - 18, 46, null);
    const top = base.a.boat.a.top;
    s += `<path d="M${top[0]} ${top[1]} Q${top[0] + 60} 96 236 68" fill="none" stroke="#7fb6c4" stroke-dasharray="3 4"/>`;
    s += pill(300, 44, "powerLimitW 60 W", "lock", 11) + pill(300, 68, "uplinkMbps 8 Mbps", "lnk", 11) + pill(300, 92, "storageGB 128 GB", "img", 11);
    return { s, title: "QRY-05 · query: three values of the USV",
      board: qryBoard(ctx, { title: "Read MaritimeISR and answer", question: "Read UnmannedSurfaceVessel's powerLimitW, uplinkMbps and storageGB.",
        compare: (e, g) => ["powerLimitW", "uplinkMbps", "storageGB"].map((k) => ({ text: `${k}: agent ${g[k] ?? "(none)"}, key ${e[k]}`, state: numEq(g[k], e[k]) ? "ok" : "miss", mono: true, note: numEq(g[k], e[k]) ? "right" : "wrong" })) }) };
  };

  S["AMB-01"] = (p, ctx) => {
    const st = station(500, 132, 0.85, { archive: true });
    const boat = usv(p, 130, 160, 1, { ais: true, radio: true });
    let s = land(410).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + boat.svg;
    s += link(p, "t1", boat.a.radio, st.a.antenna, "trk", "plain", { c: [320, 30], label: "tracks must reach shore in real time", ly: -2, dur: 2.6 });
    s += fog(240, 210, "latency ? s") + fog(360, 250, "bandwidth ? Mbps");
    return { s, title: "AMB-01 · ask: real-time sharing, but no latency or bandwidth given",
      board: ambBoard(ctx, { title: "Missing information: stop and ask", brief: "Tracks must be shared from the vessel to the shore in real time. No latency and no bandwidth are given.",
        groups: [["latency", "latency"], ["bandwidth", "bandwidth"]] }) };
  };

  S["AMB-02"] = (p, ctx) => {
    const boat = usv(p, 150, 156, 1.05, { ir: true, radio: true });
    let s = boat.svg;
    const cx = 420;
    const cy = 236;
    s += `<path d="M${cx - 70} ${cy} A70 70 0 0 1 ${cx + 70} ${cy}" fill="none" stroke="#2f5870" stroke-width="12"/>`;
    s += `<path d="M${cx - 70} ${cy} A70 70 0 0 1 ${cx + 20} ${cy - 67}" fill="none" stroke="${C.pwr}" stroke-width="12" opacity=".75"/>`;
    s += `<g transform="translate(${cx} ${cy})"><path d="M0 0 L0 -60" stroke="${C.txt}" stroke-width="3" stroke-linecap="round">${reduced() ? "" : `<animateTransform attributeName="transform" type="rotate" values="-60;40;-20;55;-60" dur="6s" repeatCount="indefinite"/>`}</path><circle r="6" fill="${C.txt}"/></g>`;
    s += `<text x="${cx}" y="${cy + 26}" text-anchor="middle" font-size="12" fill="${C.sub}">power meter</text>`;
    s += fog(cx + 40, cy - 92, "limit ? W");
    s += pill(170, 300, "\"as low as possible\" is not a number you can check", "dim", 11);
    return { s, title: "AMB-02 · ask: save power, but no watt limit given",
      board: ambBoard(ctx, { title: "Missing information: stop and ask", brief: "The vessel power use must be as low as possible. No watt limit is given.",
        groups: [["watt", "the power limit in watts"]] }) };
  };

  S["AMB-03"] = (p, ctx) => {
    const st = station(470, 132, 0.95, { archive: true });
    let s = land(330).replace("url(#LAND)", `url(#${p}-land)`) + st.svg;
    s += `<g transform="translate(150 250)"><ellipse cx="0" cy="-46" rx="46" ry="12" fill="#2a4a5c" stroke="#7fb6c4"/><path d="M-46 -46 V20 A46 12 0 0 0 46 20 V-46" fill="#1b3442" stroke="#7fb6c4"/><ellipse cx="0" cy="20" rx="46" ry="12" fill="none" stroke="#7fb6c4"/><text x="0" y="-6" text-anchor="middle" font-size="15" font-weight="800" fill="${C.txt}">128 GB</text><text x="0" y="12" text-anchor="middle" font-size="10.5" fill="${C.sub}">storage</text></g>`;
    s += calendar(352, 226, 30, "ok");
    s += fog(250, 168, "data rate ? Mbps");
    s += pill(270, 318, "needed storage = data rate × 30 days → cannot compute", "dim", 11);
    return { s, title: "AMB-03 · ask: keep 30 days on 128 GB, but no data rate given",
      board: ambBoard(ctx, { title: "Missing information: stop and ask", brief: "The shore keeps tracks for 30 days and has 128 GB of storage. No data rate is given.",
        groups: [["data rate", "the data rate"]] }) };
  };

  S["AMB-04"] = (p, ctx) => {
    const boat = usv(p, 120, 160, 1, { radio: true });
    const cmd = ship(p, 450, 160, 0.8);
    let s = boat.svg + cmd.svg;
    s += link(p, "u1", boat.a.radio, cmd.a.portL, "lnk", "plain", { c: [290, 40], label: "uplink", ly: -2 });
    s += `<g><rect x="40" y="226" width="220" height="44" rx="8" fill="#eef4f7"/><text x="54" y="245" font-size="11" fill="#33505f">sentence 1</text><text x="54" y="262" font-size="13" font-weight="800" fill="#10233a" font-family="${MONO}">the uplink is 8</text></g>`;
    s += `<g><rect x="300" y="226" width="240" height="44" rx="8" fill="#eef4f7"/><text x="314" y="245" font-size="11" fill="#33505f">sentence 2</text><text x="314" y="262" font-size="13" font-weight="800" fill="#10233a" font-family="${MONO}">the uplink is 8 MHz</text></g>`;
    s += pill(280, 300, "8 Mbps? or 8 MHz? the unit is not settled", "lock", 12);
    return { s, title: "AMB-04 · ask: one uplink, two sentences with conflicting units",
      board: ambBoard(ctx, { title: "Conflicting units: stop and ask", brief: "One sentence says the uplink is 8. Another says the uplink is 8 MHz. The unit is not settled.",
        groups: [["unit", "the unit"]] }) };
  };

  S["RT-01"] = (p, ctx) => {
    const st = station(500, 132, 0.85);
    const boat = usv(p, 140, 160, 1, { radio: true });
    let s = land(410).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + boat.svg;
    s += link(p, "r1", boat.a.eo, st.a.antenna, "img", "plain", { c: [330, 10], label: "camera imagery → shore", ly: -2 });
    return { s, title: "RT-01 · round trip: the USV sends camera imagery ashore",
      board: rtBoard(ctx, { title: "Restate the model in sentences", doc: "The unmanned surface vessel sends camera imagery to the shore.", phrases: ["unmanned surface vessel", "camera", "shore"] }) };
  };

  S["RT-02"] = (p, ctx) => {
    const boat = usv(p, 160, 160, 1.1, { radio: true });
    let s = boat.svg;
    s += `<rect x="340" y="214" width="200" height="30" rx="6" fill="#0b2230" stroke="#2f5870"/><rect x="340" y="214" width="160" height="30" rx="6" fill="${C.pwr}" opacity=".5"/><path d="M500 204 V254" stroke="${C.lock}" stroke-width="3"/>`;
    s += pill(500, 194, "powerLimitW = 60 W", "lock", 11.5);
    return { s, title: "RT-02 · round trip: the USV's 60 W power limit",
      board: rtBoard(ctx, { title: "Restate the model in sentences", doc: "The unmanned surface vessel power limit is 60 W.", phrases: ["power limit", "60"] }) };
  };

  S["RT-03"] = (p, ctx) => {
    const plane = uav(p, 160, 60, 1.05, { radar: true });
    const cmd = ship(p, 420, 170, 0.85);
    let s = sweep(plane.a.radar[0], plane.a.radar[1], 120, C.trk, "ok") + plane.svg + cmd.svg;
    s += link(p, "r1", plane.a.radar, cmd.a.mast, "trk", "plain", { c: [330, 90], label: "radar tracks → command ship", ly: -4 });
    return { s, title: "RT-03 · round trip: the UAV radar sends tracks to the command ship",
      board: rtBoard(ctx, { title: "Restate the model in sentences", doc: "The UAV radar shares tracks with the command ship.", phrases: ["radar", "command ship"] }) };
  };

  S["RT-04"] = (p, ctx) => {
    const st = station(470, 132, 0.95, { archive: true });
    const cmd = ship(p, 120, 168, 0.66);
    let s = land(330).replace("url(#LAND)", `url(#${p}-land)`) + st.svg + cmd.svg;
    s += link(p, "r1", cmd.a.mast, st.a.door, "lnk", "plain", { c: [300, 40], label: "backhaul 50 Mbit/s", ly: -6 });
    s += calendar(352, 226, 30, "ok") + pill(406, 318, "kept 30 days", "lnk", 10.5);
    return { s, title: "RT-04 · round trip: shore keeps 30 days, 50 Mbit/s backhaul",
      board: rtBoard(ctx, { title: "Restate the model in sentences", doc: "The shore archive keeps tracks for 30 days on a 50 Mbit/s backhaul.", phrases: ["30 days", "50"] }) };
  };

  S["RT-05"] = (p, ctx) => {
    const cmd = ship(p, 330, 172, 1.05, { fusion: true });
    const boat = usv(p, 80, 220, 0.6, { radio: true });
    const plane = uav(p, 96, 54, 0.66, { radio: true });
    let s = boat.svg + plane.svg + cmd.svg;
    s += link(p, "r1", boat.a.radio, cmd.a.portL, "lnk", "plain", { c: [170, 160], label: "uplink 1", ly: -2 });
    s += link(p, "r2", plane.a.radio, cmd.a.portL2, "lnk", "plain", { c: [170, 50], label: "uplink 2", ly: 6 });
    s += timer(506, 84, 28, "fusion latency", "ok");
    return { s, title: "RT-05 · round trip: 2 s fusion latency, two uplinks into the command ship",
      board: rtBoard(ctx, { title: "Restate the model in sentences", doc: "Fusion latency is 2 seconds and the command ship accepts two uplinks.", phrases: ["2 seconds", "two uplinks"] }) };
  };

  function fallback(p, ctx) {
    const boat = usv(p, 160, 160, 1.1, { radio: true });
    return { s: boat.svg, title: [ctx.task || "new task", TYPE[ctx.type]].filter(Boolean).join(" · "),
      board: board(ctx, "No dedicated scene for this task", [{ head: "NOTE", items: [{ text: "New tasks use a generic picture.", state: "info" }, { text: "The verdict is in the full process below.", state: "info" }] }]) };
  }

  /* ---------------- entry point ---------------- */
  function render(host, ctx) {
    if (!host) return;
    seq += 1;
    const p = `sc${seq}`;
    spotId = `${p}-spot`;
    const J = judge(ctx);
    const make = S[ctx.task] || ((pp, cc) => fallback(pp, cc));
    const out = make(p, ctx, J);
    let stampSvg = "";
    const at = out.stamp || (ctx.type === "MOD" ? [430, 104] : [300, 268]);
    if (!ctx.live && (ctx.type === "GEN" || ctx.type === "MOD") && ctx.sysml === "FAIL") stampSvg = stamp(at[0], at[1], `syntax FAIL${ctx.attempts ? ` · ${ctx.attempts} attempt${ctx.attempts > 1 ? "s" : ""}` : ""}`);
    const titleW = Math.min(tw(out.title, 12.5) + 24, BX - 26);
    host.innerHTML = `<svg class="scene2" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${esc(out.title)}" font-family="${SANS}">
      ${defs(p)}${backdrop(p)}${out.s}${stampSvg}
      <g><rect x="12" y="8" width="${titleW.toFixed(0)}" height="26" rx="9" fill="rgba(5,18,28,.82)" stroke="#2f5870"/><text x="24" y="26" font-size="12.5" font-weight="800" fill="${C.txt}">${esc(fit(out.title, titleW - 22, 12.5))}</text></g>
      ${out.board}
    </svg>`;
    const svg = host.querySelector("svg");
    if (svg && reduced() && svg.pauseAnimations) svg.pauseAnimations();
  }

  window.SceneKit = { render };
})();
