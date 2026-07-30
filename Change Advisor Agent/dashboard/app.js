(function () {
  const { records, teams } = window.DASHBOARD_DATA;
  const $ = (s) => document.querySelector(s);

  const state = { range: 30, team: "all", sortKey: "date", sortDir: -1, search: "" };

  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const COLORS = () => ({
    accent: css("--accent"), green: css("--green"), red: css("--red"),
    amber: css("--amber"), muted: css("--muted"), border: css("--border"), text: css("--text"),
  });

  function filtered() {
    return records.filter((r) =>
      r._daysAgo < state.range && (state.team === "all" || r.team === state.team)
    );
  }

  // ---- KPI cards ----
  function renderKpis(rows, prevRows) {
    const total = rows.length;
    const success = rows.filter((r) => r.outcome === "success").length;
    const rolled = rows.filter((r) => r.outcome === "rolled").length;
    const highRisk = rows.filter((r) => r.risk === "high").length;
    const rate = total ? Math.round((success / total) * 100) : 0;
    const prevRate = prevRows.length
      ? Math.round((prevRows.filter((r) => r.outcome === "success").length / prevRows.length) * 100)
      : rate;

    const cards = [
      { label: "Total changes", value: total, delta: total - prevRows.length, fmt: (n) => (n > 0 ? "+" : "") + n },
      { label: "Success rate", value: rate + "%", delta: rate - prevRate, fmt: (n) => (n > 0 ? "+" : "") + n + " pts" },
      { label: "Rollbacks", value: rolled, delta: -(rolled), invert: true, fmt: () => rolled + " this period" },
      { label: "High-risk", value: highRisk, delta: 0, fmt: () => Math.round((highRisk / (total || 1)) * 100) + "% of changes" },
    ];
    $("#kpis").innerHTML = cards.map((c) => {
      const up = c.delta > 0;
      const good = c.invert ? !up : up;
      const cls = c.delta === 0 ? "" : good ? "up" : "down";
      return `<div class="kpi">
        <div class="label">${c.label}</div>
        <div class="value">${c.value}</div>
        <div class="delta ${cls}">${c.fmt(c.delta)}</div>
      </div>`;
    }).join("");
  }

  // ---- Canvas helpers (HiDPI) ----
  function ctxOf(id, cssHeight) {
    const cv = document.getElementById(id);
    const dpr = window.devicePixelRatio || 1;
    const w = cv.clientWidth || cv.parentElement.clientWidth;
    cv.width = w * dpr; cv.height = cssHeight * dpr;
    cv.style.height = cssHeight + "px";
    const ctx = cv.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, cssHeight);
    return { ctx, w, h: cssHeight };
  }

  // ---- Line/area: change volume per day ----
  function renderVolume(rows) {
    const c = COLORS();
    const byDay = {};
    for (const r of rows) byDay[r.date] = (byDay[r.date] || 0) + 1;
    const days = [];
    const base = new Date(window.DASHBOARD_DATA.today);
    for (let i = state.range - 1; i >= 0; i--) {
      const d = new Date(base); d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      days.push({ key, v: byDay[key] || 0 });
    }
    const { ctx, w, h } = ctxOf("volumeChart", 240);
    const pad = { l: 30, r: 12, t: 12, b: 22 };
    const max = Math.max(4, ...days.map((d) => d.v));
    const px = (i) => pad.l + (i / (days.length - 1)) * (w - pad.l - pad.r);
    const py = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);

    ctx.strokeStyle = c.border; ctx.fillStyle = c.muted; ctx.font = "11px sans-serif";
    for (let g = 0; g <= 4; g++) {
      const v = (max / 4) * g, y = py(v);
      ctx.globalAlpha = 0.5; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(w - pad.r, y); ctx.stroke(); ctx.globalAlpha = 1;
      ctx.fillText(Math.round(v), 4, y + 3);
    }
    const grad = ctx.createLinearGradient(0, pad.t, 0, h - pad.b);
    grad.addColorStop(0, c.accent + "66"); grad.addColorStop(1, c.accent + "00");
    ctx.beginPath(); ctx.moveTo(px(0), py(days[0].v));
    days.forEach((d, i) => ctx.lineTo(px(i), py(d.v)));
    ctx.lineTo(px(days.length - 1), h - pad.b); ctx.lineTo(px(0), h - pad.b); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();

    ctx.beginPath(); ctx.lineWidth = 2; ctx.strokeStyle = c.accent;
    days.forEach((d, i) => (i ? ctx.lineTo(px(i), py(d.v)) : ctx.moveTo(px(i), py(d.v))));
    ctx.stroke();

    ctx.fillStyle = c.muted;
    const step = Math.ceil(days.length / 6);
    days.forEach((d, i) => { if (i % step === 0) ctx.fillText(d.key.slice(5), px(i) - 12, h - 6); });
    $("#volumeHint").textContent = `${rows.length} changes · peak ${max}/day`;
  }

  // ---- Donut: outcome mix ----
  function renderOutcome(rows) {
    const c = COLORS();
    const groups = { success: 0, partial: 0, rolled: 0 };
    rows.forEach((r) => (groups[r.outcome] = (groups[r.outcome] || 0) + 1));
    const map = [
      ["Success", groups.success, c.green],
      ["Partial", groups.partial, c.amber],
      ["Rolled back", groups.rolled, c.red],
    ];
    const total = map.reduce((s, m) => s + m[1], 0) || 1;
    const { ctx, w, h } = ctxOf("outcomeChart", 240);
    const cx = w / 2, cy = h / 2, R = Math.min(w, h) / 2 - 12, r0 = R * 0.6;
    let a0 = -Math.PI / 2;
    map.forEach(([, val, col]) => {
      const a1 = a0 + (val / total) * Math.PI * 2;
      ctx.beginPath(); ctx.moveTo(cx, cy); ctx.arc(cx, cy, R, a0, a1); ctx.closePath();
      ctx.fillStyle = col; ctx.fill(); a0 = a1;
    });
    ctx.beginPath(); ctx.fillStyle = css("--panel"); ctx.arc(cx, cy, r0, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = c.text; ctx.textAlign = "center"; ctx.font = "700 24px sans-serif";
    ctx.fillText(Math.round((groups.success / total) * 100) + "%", cx, cy + 2);
    ctx.fillStyle = c.muted; ctx.font = "11px sans-serif"; ctx.fillText("success", cx, cy + 18);
    ctx.textAlign = "left";
    $("#outcomeLegend").innerHTML = map.map(([name, val, col]) =>
      `<span><i class="dot" style="background:${col}"></i>${name} · ${val}</span>`).join("");
  }

  // ---- Bars: risk by team ----
  function renderRisk(rows) {
    const c = COLORS();
    const data = teams.map((t) => {
      const tr = rows.filter((r) => r.team === t);
      return { team: t, low: tr.filter((r) => r.risk === "low").length,
        medium: tr.filter((r) => r.risk === "medium").length, high: tr.filter((r) => r.risk === "high").length };
    });
    const { ctx, w, h } = ctxOf("riskChart", 240);
    const pad = { l: 28, r: 8, t: 10, b: 24 };
    const max = Math.max(4, ...data.map((d) => d.low + d.medium + d.high));
    const bw = (w - pad.l - pad.r) / data.length * 0.6;
    const gap = (w - pad.l - pad.r) / data.length;
    const py = (v) => h - pad.b - (v / max) * (h - pad.t - pad.b);
    ctx.font = "11px sans-serif";
    data.forEach((d, i) => {
      const x = pad.l + i * gap + (gap - bw) / 2;
      let y = h - pad.b;
      [["low", c.green], ["medium", c.amber], ["high", c.red]].forEach(([k, col]) => {
        const seg = (d[k] / max) * (h - pad.t - pad.b);
        ctx.fillStyle = col; ctx.fillRect(x, y - seg, bw, seg); y -= seg;
      });
      ctx.fillStyle = c.muted; ctx.textAlign = "center";
      ctx.fillText(d.team, x + bw / 2, h - 8);
    });
    ctx.textAlign = "left"; ctx.fillStyle = c.muted;
    for (let g = 0; g <= 4; g++) { const v = (max / 4) * g; ctx.fillText(Math.round(v), 2, py(v) + 3); }
  }

  // ---- Table ----
  function renderTable(rows) {
    let r = rows.slice();
    if (state.search) {
      const q = state.search.toLowerCase();
      r = r.filter((x) => x.service.includes(q) || x.author.includes(q) || x.team.toLowerCase().includes(q));
    }
    const order = { low: 0, medium: 1, high: 2, success: 0, partial: 1, rolled: 2 };
    r.sort((a, b) => {
      let av = a[state.sortKey], bv = b[state.sortKey];
      if (state.sortKey === "risk" || state.sortKey === "outcome") { av = order[av]; bv = order[bv]; }
      return (av < bv ? -1 : av > bv ? 1 : 0) * state.sortDir;
    });
    const oc = { success: "success", partial: "partial", rolled: "rolled" };
    $("#dataTable tbody").innerHTML = r.slice(0, 80).map((x) => `<tr>
      <td>${x.date}</td><td>${x.service}</td><td>${x.author}</td><td>${x.team}</td>
      <td><span class="badge ${x.risk}">${x.risk}</span></td>
      <td><span class="badge ${oc[x.outcome]}">${x.outcome}</span></td>
    </tr>`).join("");
  }

  function renderAll() {
    const rows = filtered();
    const prev = records.filter((r) => r._daysAgo >= state.range && r._daysAgo < state.range * 2 &&
      (state.team === "all" || r.team === state.team));
    renderKpis(rows, prev);
    renderVolume(rows);
    renderOutcome(rows);
    renderRisk(rows);
    renderTable(rows);
  }

  // ---- Wiring ----
  const teamSel = $("#teamSelect");
  teams.forEach((t) => { const o = document.createElement("option"); o.value = t; o.textContent = t; teamSel.appendChild(o); });
  $("#rangeSelect").addEventListener("change", (e) => { state.range = +e.target.value; renderAll(); });
  teamSel.addEventListener("change", (e) => { state.team = e.target.value; renderAll(); });
  $("#search").addEventListener("input", (e) => { state.search = e.target.value.trim().toLowerCase(); renderAll(); });

  document.querySelectorAll("th[data-sort]").forEach((th) => th.addEventListener("click", () => {
    const k = th.dataset.sort;
    state.sortDir = state.sortKey === k ? -state.sortDir : 1;
    state.sortKey = k;
    document.querySelectorAll("th[data-sort]").forEach((t) => (t.textContent = t.textContent.replace(/ [▾▴]$/, "")));
    th.textContent += state.sortDir > 0 ? " ▴" : " ▾";
    renderAll();
  }));

  const titles = {
    overview: ["Overview", "Change activity across all services"],
    changes: ["Changes", "Volume and recent change records"],
    risk: ["Risk", "Risk distribution by team"],
    table: ["Records", "Full change log"],
  };
  document.querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    const [t, s] = titles[b.dataset.view];
    $("#viewTitle").textContent = t; $("#viewSubtitle").textContent = s;
  }));

  $("#themeToggle").addEventListener("click", () => {
    const root = document.documentElement;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    renderAll();
  });

  window.addEventListener("resize", () => renderAll());
  renderAll();
})();
