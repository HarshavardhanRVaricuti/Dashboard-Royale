// Dashboard Royale public view. Data: docs/data/*.json, exported from the Databricks gold tables
// by databricks/03_export_public.py. Every ratio is recomputed here as a ratio of sums.

const $ = id => document.getElementById(id);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const BASE = Date.UTC(2025, 0, 1);
const dstr = d => new Date(BASE + d * 864e5).toISOString().slice(0, 10);
const dnum = s => Math.round((Date.parse(s + "T00:00:00Z") - BASE) / 864e5);
const month = d => dstr(d).slice(0, 7);
const MONTHS = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"];
const MONTH_LABEL = { "2025-01": "Jan", "2025-02": "Feb", "2025-03": "Mar", "2025-04": "Apr", "2025-05": "May", "2025-06": "Jun" };
const CLOSURE = [dnum("2025-03-03"), dnum("2025-04-06")];
const AURORA_OPEN = dnum("2025-03-24");

const usd = (v, digits = 1) => {
  if (v == null || isNaN(v)) return "–";
  const a = Math.abs(v), s = v < 0 ? "−$" : "$";
  if (a >= 1e6) return s + (a / 1e6).toFixed(digits + 1) + "M";
  if (a >= 1e4) return s + (a / 1e3).toFixed(digits) + "k";
  return s + a.toLocaleString("en-US", { maximumFractionDigits: a < 100 ? 2 : 0 });
};
const pct = (v, p = 1) => (v == null || isNaN(v) ? "–" : (v * 100).toFixed(p) + "%");
const fix = (v, p = 2) => (v == null || isNaN(v) ? "–" : v.toFixed(p));
const int = v => (v == null ? "–" : Math.round(v).toLocaleString("en-US"));
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Chart palette: distinct, colorblind-friendly categorical colors (light and dark variants in CSS); maroon marks the key finding.
const pal = () => ({
  accent: css("--accent"), g1: css("--g1"), g2: css("--g2"), g3: css("--g3"), g4: css("--g4"), muted: css("--muted"),
  maroon: css("--c-maroon"), blue: css("--c-blue"), green: css("--c-green"), orange: css("--c-orange"),
  purple: css("--c-purple"), gold: css("--c-gold"), teal: css("--c-teal"), gray: css("--c-gray"),
});
const alpha = (hex, a) => {
  const n = parseInt(hex.replace("#", ""), 16);
  return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
};
const zoneColor = z => {
  const p = pal();
  return { "Back Forty": p.maroon, "Main Entrance": p.blue, "Center Pit": p.green, "Hotel Corridor": p.orange,
    "High-Limit Room": p.purple, "Bar Row": p.gold, "Garage Entrance": p.teal }[z] || p.gray;
};
const MFRS = ["Halcyon", "Northwind", "Ridgeline"];
const mfrColor = m => ({ Halcyon: pal().green, Northwind: pal().blue, Ridgeline: pal().orange }[m]);
const shiftColor = s => ({ day: pal().orange, swing: pal().blue, grave: pal().purple }[s]);

const DIAGNOSES = [
  ["leak", "Leak?", "hit rate far from the game's published math (|hit z| > 4): inspect"],
  ["exp", "Exposure / downtime", "on the floor for under 80% of the period, or available under 97% of scheduled hours"],
  ["loc", "Location", "sits in Back Forty, where every theme earns less; its result is within luck"],
  ["luck", "Luck", "result within the normal range of luck, or unlucky (z < −2) and worth re-testing next period"],
];
const TIPS = {
  manager_rank: "Rank by raw house win in the period (1 = lowest): the manager's list",
  days: "Days the machine was on the floor in the period",
  availability: "Available hours ÷ scheduled hours (1 − downtime)",
  occupancy: "Share of available hours with a player",
  hw: "Coin-in − payouts: what the casino kept",
  th: "Theoretical win = bet × (1 − RTP), the luck-free expectation",
  luck: "House win − theo",
  luck_z: "(House win − theo) ÷ its standard deviation. Between −2 and +2 = ordinary luck",
  hold: "House win ÷ coin-in",
  theo_hold: "Theo ÷ coin-in: the hold the game's math promises",
  hit: "Share of spins that paid anything",
  pub_hit: "Hit rate the game's published math predicts",
  hit_z: "(Paying spins − expected) ÷ standard deviation. Above 4 in size = not chance",
  theo_hr: "Theo ÷ available hours: demand for the machine where it stands, free of luck and downtime",
};
const tip = k => (TIPS[k] ? ` title="${TIPS[k]}"` : "");

const S = { s: 0, e: 180, zone: "all", bank: "all", tab: "decision", sort: "manager_rank", asc: true, q: "", sel: null };
let MD, PL, TB;
const charts = {};

// ---------------------------------------------------------------- aggregation

function machineAgg(s, e) {
  const R = MD.rows, M = MD.machines.id.length;
  const acc = Array.from({ length: M }, () => ({
    sch: 0, av: 0, occ: 0, ci: 0, hw: 0, th: 0, lv: 0, sp: 0, ps: 0, eh: 0, hv: 0, days: 0, last: -1, z: 0, b: 0,
  }));
  for (let i = 0; i < R.d.length; i++) {
    const d = R.d[i];
    if (d < s || d > e) continue;
    const a = acc[R.m[i]];
    a.sch += R.sch[i]; a.av += R.av[i]; a.occ += R.occ[i]; a.ci += R.ci[i]; a.hw += R.hw[i]; a.th += R.th[i];
    a.lv += R.lv[i]; a.sp += R.sp[i]; a.ps += R.ps[i]; a.eh += R.eh[i]; a.hv += R.hv[i]; a.days++;
    if (d > a.last) { a.last = d; a.z = R.z[i]; a.b = R.b[i]; }
  }
  const periodDays = e - s + 1;
  const list = [];
  acc.forEach((a, m) => {
    if (!a.days) return;
    const r = {
      m, id: MD.machines.id[m], theme: MD.machines.theme[m], manufacturer: MD.machines.manufacturer[m],
      zone: MD.zones[a.z], bank: MD.banks[a.b], days: a.days,
      availability: a.av / a.sch, occupancy: a.av ? a.occ / a.av : null,
      hw: a.hw, th: a.th, luck: a.hw - a.th, luck_z: a.lv ? (a.hw - a.th) / Math.sqrt(a.lv) : null,
      hold: a.ci ? a.hw / a.ci : null, theo_hold: a.ci ? a.th / a.ci : null,
      hit: a.sp ? a.ps / a.sp : null, pub_hit: a.sp ? a.eh / a.sp : null,
      hit_z: a.hv ? (a.ps - a.eh) / Math.sqrt(a.hv) : null,
      theo_hr: a.av ? a.th / a.av : null,
    };
    r.diagnosis = diagnose(r, periodDays);
    list.push(r);
  });
  [...list].sort((x, y) => x.hw - y.hw).forEach((r, i) => (r.manager_rank = i + 1));
  return list;
}

function diagnose(r, periodDays) {
  if (Math.abs(r.hit_z) > 4) return ["leak", "Leak? Hit rate off published math → inspect"];
  if (r.days < 0.8 * periodDays) return ["exp", "Exposure: on floor part of period"];
  if (r.availability < 0.97) return ["exp", "Downtime"];
  if (r.zone === "Back Forty" && r.luck_z > -2) return ["loc", "Location: weak zone, result within luck"];
  if (r.luck_z < -2) return ["luck", "Unlucky (z < −2): re-test next period"];
  return ["luck", "Within luck"];
}

const pill = ([cls, text]) => `<span class="pill ${cls}">${esc(text)}</span>`;

function rowsWhere(fn) {
  const R = MD.rows, out = [];
  for (let i = 0; i < R.d.length; i++) if (fn(i)) out.push(i);
  return out;
}

const zoneOk = z => S.zone === "all" || MD.zones[z] === S.zone;
const bankOk = b => S.bank === "all" || MD.banks[b] === S.bank;

// ---------------------------------------------------------------- charts

function chart(id) {
  if (!charts[id]) charts[id] = echarts.init($(id), null, { renderer: "canvas" });
  return charts[id];
}

function base(extra = {}) {
  const ink = css("--ink"), muted = css("--muted"), line = css("--line"), p = pal();
  return {
    color: [p.blue, p.orange, p.green, p.purple, p.maroon, p.teal, p.gold, p.gray],
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", color: ink },
    grid: { left: 64, right: 20, top: 36, bottom: 40, containLabel: false },
    tooltip: { trigger: "axis", confine: true, backgroundColor: css("--card"), borderColor: line, textStyle: { color: ink } },
    legend: { top: 0, textStyle: { color: muted, fontSize: 11 }, type: "scroll" },
    xAxis: { axisLine: { lineStyle: { color: line } }, axisLabel: { color: muted }, splitLine: { show: false } },
    yAxis: { axisLine: { show: false }, axisLabel: { color: muted }, splitLine: { lineStyle: { color: line, type: "dashed" } } },
    ...extra,
  };
}

const usdAxis = { axisLabel: { formatter: v => usd(v, 0) } };

function set(id, opt) {
  chart(id).setOption(opt, true);
}

// ---------------------------------------------------------------- pages

function renderDecision() {
  const P = TB.property_day;
  let hw = 0, th = 0, ci = 0, n = 0;
  P.gaming_date.forEach((g, i) => {
    const d = dnum(g);
    if (d < S.s || d > S.e) return;
    hw += P.house_win_usd[i]; th += P.theo_usd[i]; ci += P.coin_in_usd[i]; n++;
  });
  $("k-hw").textContent = usd(hw);
  $("k-hw-f").textContent = `${n} gaming days · theo ${usd(th)} · luck ${usd(hw - th)}`;
  $("k-hold").textContent = `${pct(hw / ci, 2)} vs ${pct(th / ci, 2)}`;
  $("k-hold-f").textContent = "Ratio of sums · Missouri slot benchmark ≈ 9.6% (real)";

  const B = TB.budget;
  const spent = B.cost_usd.reduce((a, b) => a + b, 0);
  $("k-spent").textContent = "$" + int(spent);
  $("k-kept").textContent = "$" + int(100000 - spent);

  const list = machineAgg(S.s, S.e).sort((a, b) => a.manager_rank - b.manager_rank).slice(0, 10);
  $("bottom10").innerHTML = `<thead><tr><th${tip("manager_rank")}>#</th><th>Machine</th><th>Zone</th><th class="num"${tip("days")}>Days</th>
    <th class="num"${tip("hw")}>House win</th><th class="num"${tip("th")}>Theo</th><th class="num"${tip("luck_z")}>Luck z</th><th class="num"${tip("hit_z")}>Hit z</th>
    <th class="num"${tip("theo_hr")}>Theo/hr</th><th>What's going on</th></tr></thead><tbody>` +
    list.map(r => `<tr><td>${r.manager_rank}</td><td><b>${r.id}</b><br><span class="sub">${esc(r.theme)}</span></td>
      <td>${esc(r.zone)}</td><td class="num">${r.days}</td><td class="num">${usd(r.hw)}</td><td class="num">${usd(r.th)}</td>
      <td class="num">${fix(r.luck_z)}</td><td class="num">${fix(r.hit_z, 1)}</td><td class="num">$${fix(r.theo_hr)}</td>
      <td>${pill(r.diagnosis)}</td></tr>`).join("") + "</tbody>";
  $("legend").innerHTML = DIAGNOSES.map(([cls, name, text]) => `<span>${pill([cls, name])} ${esc(text)}</span>`).join("");

  $("budget").innerHTML = `<thead><tr><th>Action</th><th class="num">Qty</th><th>Targets</th><th class="num">Cost</th>
    <th class="num">Lead</th><th>Evidence</th><th>Expected effect</th><th>Uncertainty</th><th>How we'll know</th></tr></thead><tbody>` +
    B.action_type_id.map((a, i) => `<tr><td><b>${esc(B.name[i])}</b><br><span class="sub">${a}</span></td>
      <td class="num">${B.quantity[i]}</td><td>${esc(B.targets[i])}</td><td class="num">$${int(B.cost_usd[i])}</td>
      <td class="num">${B.lead_days[i]}d</td><td>${esc(B.evidence[i])}</td><td>${esc(B.expected_effect[i])}</td>
      <td>${esc(B.uncertainty[i])}</td><td>${esc(B.measurement[i])}</td></tr>`).join("") + "</tbody>";
}

const SCORE_COLS = [
  ["manager_rank", "Mgr rank", r => r.manager_rank, true],
  ["id", "Machine", r => `<b>${r.id}</b><br><span class="sub">${esc(r.theme)}</span>`],
  ["zone", "Zone", r => `${esc(r.zone)}<br><span class="sub">${r.bank}</span>`],
  ["diagnosis", "Diagnosis", r => pill(r.diagnosis)],
  ["days", "Days", r => r.days, true],
  ["availability", "Avail.", r => pct(r.availability), true],
  ["occupancy", "Occup.", r => pct(r.occupancy), true],
  ["hw", "House win", r => usd(r.hw), true],
  ["th", "Theo", r => usd(r.th), true],
  ["luck", "Luck $", r => usd(r.luck), true],
  ["luck_z", "Luck z", r => fix(r.luck_z), true],
  ["hold", "Hold", r => pct(r.hold), true],
  ["theo_hold", "Theo hold", r => pct(r.theo_hold), true],
  ["hit", "Hit rate", r => pct(r.hit), true],
  ["pub_hit", "Published hit", r => pct(r.pub_hit), true],
  ["hit_z", "Hit z", r => fix(r.hit_z, 1), true],
  ["theo_hr", "Theo / avail. hr", r => "$" + fix(r.theo_hr), true],
];

function renderMachines() {
  const all = machineAgg(S.s, S.e);
  const list = all
    .filter(r => (S.zone === "all" || r.zone === S.zone) && (S.bank === "all" || r.bank === S.bank))
    .filter(r => !S.q || (r.id + " " + r.theme).toLowerCase().includes(S.q));
  const key = S.sort;
  list.sort((a, b) => {
    const A = key === "diagnosis" ? a.diagnosis[1] : a[key], B = key === "diagnosis" ? b.diagnosis[1] : b[key];
    return (A > B ? 1 : A < B ? -1 : 0) * (S.asc ? 1 : -1);
  });
  $("scorecard").innerHTML = "<thead><tr>" + SCORE_COLS.map(([k, label, , isNum]) =>
    `<th data-k="${k}" class="${isNum ? "num" : ""}"${tip(k)}>${label}${k === S.sort ? (S.asc ? " ↑" : " ↓") : ""}</th>`).join("") +
    "</tr></thead><tbody>" + list.map(r => `<tr class="click ${S.sel === r.m ? "on" : ""}" data-m="${r.m}">` +
      SCORE_COLS.map(([, , fmt, isNum]) => `<td class="${isNum ? "num" : ""}">${fmt(r)}</td>`).join("") + "</tr>").join("") +
    (list.length ? "" : `<tr><td colspan="${SCORE_COLS.length}" class="sub">No machines match.</td></tr>`) + "</tbody>";

  renderDetail(all);

  // heatmap: theme x zone theo per available hour
  const R = MD.rows, cell = new Map();
  for (let i = 0; i < R.d.length; i++) {
    if (R.d[i] < S.s || R.d[i] > S.e) continue;
    const k = MD.machines.theme[R.m[i]] + "|" + R.z[i];
    const c = cell.get(k) || { th: 0, av: 0 };
    c.th += R.th[i]; c.av += R.av[i]; cell.set(k, c);
  }
  const themes = [...new Set(MD.machines.theme)].sort();
  const data = [];
  cell.forEach((c, k) => {
    const [t, z] = k.split("|");
    data.push([+z, themes.indexOf(t), +(c.th / c.av).toFixed(2)]);
  });
  const vals = data.map(d => d[2]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const cells = data.map(v => ({ value: v, label: { color: (v[2] - lo) / (hi - lo) > 0.55 ? css("--heat-ink-hi") : css("--ink") } }));
  set("c-heat", base({
    tooltip: { formatter: p => `${themes[p.value[1]]} · ${MD.zones[p.value[0]]}<br><b>$${p.value[2].toFixed(2)}</b> theo / available hr` },
    grid: { left: 110, right: 20, top: 10, bottom: 90 },
    xAxis: { type: "category", data: MD.zones, axisLabel: { color: css("--muted"), rotate: 30, interval: 0 } },
    yAxis: { type: "category", data: themes, axisLabel: { color: css("--muted") } },
    visualMap: { min: lo, max: hi, orient: "horizontal", left: "center", bottom: 0,
      itemHeight: 160, itemWidth: 10, text: ["high", "low"], textStyle: { color: css("--muted") },
      inRange: { color: ["--heat-lo", "--heat-m1", "--heat-m2", "--heat-hi"].map(css) } },
    series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: css("--card"), borderWidth: 2 },
      label: { show: true, formatter: p => p.value[2].toFixed(1), fontSize: 10, color: css("--ink") } }],
  }));

  // scatter: theo per hour vs luck z
  const byZone = {};
  list.forEach(r => (byZone[r.zone] = byZone[r.zone] || []).push(r));
  set("c-scatter", base({
    grid: { left: 56, right: 30, top: 56, bottom: 40 },
    tooltip: { trigger: "item", formatter: p => `<b>${p.data.r.id}</b> ${esc(p.data.r.theme)}<br>${esc(p.data.r.zone)}<br>` +
      `Theo/hr $${fix(p.data.r.theo_hr)} · luck z ${fix(p.data.r.luck_z)} · hit z ${fix(p.data.r.hit_z, 1)}` },
    xAxis: { type: "value", name: "Theo per available hour ($)", nameLocation: "middle", nameGap: 26, scale: true,
      axisLabel: { color: css("--muted") }, splitLine: { show: false } },
    yAxis: { type: "value", name: "Luck z", nameTextStyle: { color: css("--muted"), align: "left" }, axisLabel: { color: css("--muted") },
      splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    series: Object.entries(byZone).map(([z, rs]) => ({
      name: z, type: "scatter", symbolSize: 8, itemStyle: { color: zoneColor(z), opacity: 0.75 },
      data: rs.map(r => ({ value: [r.theo_hr, r.luck_z], r, symbolSize: r.diagnosis[0] === "leak" ? 18 : 9,
        itemStyle: r.diagnosis[0] === "leak" ? { color: pal().maroon, borderColor: css("--ink"), borderWidth: 2, opacity: 1 } : undefined,
        label: r.diagnosis[0] === "leak" ? { show: true, formatter: r.id, position: "right", color: css("--ink"), fontWeight: 600 } : undefined })),
      markLine: z === Object.keys(byZone)[0] ? { silent: true, symbol: "none", lineStyle: { color: css("--muted"), type: "dashed" },
        data: [{ yAxis: -2 }, { yAxis: 2 }], label: { formatter: p => (p.value > 0 ? "+2" : "−2"), color: css("--muted") } } : undefined,
    })),
  }));
}

function renderDetail(all) {
  const r = all.find(x => x.m === S.sel);
  $("detail").className = "detail" + (r ? " show" : "");
  if (!r) return;
  $("detail-title").textContent = `${r.id} · ${r.theme} · ${r.zone} (${r.bank}) · ${r.manufacturer}`;
  $("detail-text").innerHTML = `${pill(r.diagnosis)} · house win ${usd(r.hw)} vs theo ${usd(r.th)} · luck z ${fix(r.luck_z)} · ` +
    `hit rate ${pct(r.hit)} vs published ${pct(r.pub_hit)} (z ${fix(r.hit_z, 1)}) · availability ${pct(r.availability)}`;
  const R = MD.rows, mon = {};
  for (let i = 0; i < R.d.length; i++) {
    if (R.m[i] !== r.m) continue;
    const k = month(R.d[i]);
    const a = (mon[k] = mon[k] || { ci: 0, hw: 0, th: 0, sp: 0, ps: 0, eh: 0 });
    a.ci += R.ci[i]; a.hw += R.hw[i]; a.th += R.th[i]; a.sp += R.sp[i]; a.ps += R.ps[i]; a.eh += R.eh[i];
  }
  const ks = MONTHS.filter(k => mon[k]);
  const line = (name, f, color, dash) => ({ name, type: "line", data: ks.map(k => +(f(mon[k]) * 100).toFixed(2)),
    lineStyle: { color, type: dash ? "dashed" : "solid", width: 2 }, itemStyle: { color }, symbolSize: 6 });
  requestAnimationFrame(() => set("c-detail", base({
    grid: { left: 48, right: 20, top: 30, bottom: 24 },
    tooltip: { trigger: "axis", valueFormatter: v => v.toFixed(1) + "%" },
    xAxis: { type: "category", data: ks.map(k => MONTH_LABEL[k]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", axisLabel: { color: css("--muted"), formatter: "{value}%" }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    series: [
      line("Hold", a => a.hw / a.ci, pal().blue), line("Theo hold", a => a.th / a.ci, pal().blue, true),
      line("Hit rate", a => a.ps / a.sp, pal().orange), line("Published hit", a => a.eh / a.sp, pal().orange, true),
    ],
  })));
}

function eventAreas(dates, events) {
  const areas = [];
  let start = null, name = null;
  dates.forEach((g, i) => {
    const ev = events[i];
    if (ev && ev !== name) { if (start) areas.push([{ xAxis: start, name }, { xAxis: dates[i - 1] }]); start = g; name = ev; }
    else if (!ev && start) { areas.push([{ xAxis: start, name }, { xAxis: dates[i - 1] }]); start = null; name = null; }
  });
  if (start) areas.push([{ xAxis: start, name }, { xAxis: dates[dates.length - 1] }]);
  return areas;
}

function renderDemand() {
  const P = TB.property_day;
  const idx = P.gaming_date.map((g, i) => i).filter(i => { const d = dnum(P.gaming_date[i]); return d >= S.s && d <= S.e; });
  const dates = idx.map(i => P.gaming_date[i]);
  set("c-daily", base({
    xAxis: { type: "category", data: dates, axisLabel: { color: css("--muted"), formatter: v => v.slice(5) } },
    yAxis: { type: "value", ...usdAxis, scale: true, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", formatter: ps => { const i = idx[ps[0].dataIndex];
      return `<b>${P.gaming_date[i]}</b> ${P.local_weekday[i]}<br>Coin-in ${usd(P.coin_in_usd[i])}` +
        (P.events_active[i] ? `<br>${esc(P.events_active[i])}` : ""); } },
    series: [{ name: "Coin-in", type: "line", data: idx.map(i => P.coin_in_usd[i]), showSymbol: false,
      lineStyle: { color: pal().blue, width: 1.6 }, itemStyle: { color: pal().blue },
      markArea: { silent: true, itemStyle: { color: alpha(pal().gold, 0.22) }, label: { show: false },
        data: eventAreas(dates, idx.map(i => P.events_active[i])) } }],
  }));

  const order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], wk = {};
  idx.forEach(i => { if (P.events_active[i]) return; const w = (wk[P.local_weekday[i]] = wk[P.local_weekday[i]] || [0, 0]); w[0] += P.coin_in_usd[i]; w[1]++; });
  set("c-weekday", base({
    xAxis: { type: "category", data: order, axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: [{ type: "bar", name: "Avg coin-in", data: order.map(o => wk[o] ? wk[o][0] / wk[o][1] : null),
      itemStyle: { color: p => (["Fri", "Sat", "Sun"].includes(order[p.dataIndex]) ? pal().blue : alpha(pal().blue, 0.4)), borderRadius: [2, 2, 0, 0] } }],
  }));

  // weekly zone theo per day
  const R = MD.rows, wz = new Map(), weeks = new Set();
  for (let i = 0; i < R.d.length; i++) {
    const d = R.d[i];
    if (d < S.s || d > S.e || !bankOk(R.b[i])) continue;
    const w = d - ((3 + d) % 7 + 6) % 7;
    weeks.add(w);
    const k = R.z[i] + "|" + w;
    const a = wz.get(k) || { th: 0, days: new Set() };
    a.th += R.th[i]; a.days.add(d); wz.set(k, a);
  }
  const wl = [...weeks].sort((a, b) => a - b);
  set("c-zoneweek", base({
    xAxis: { type: "category", data: wl.map(w => dstr(Math.max(w, 0)).slice(5)), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: MD.zones.map((z, zi) => ({
      name: z, type: "line", showSymbol: false,
      data: wl.map(w => { const a = wz.get(zi + "|" + w); return a ? +(a.th / a.days.size).toFixed(0) : null; }),
      lineStyle: { color: zoneColor(z), width: S.zone === z || (S.zone === "all" && z === "Back Forty") ? 3.5 : 1.4,
        opacity: S.zone === "all" || S.zone === z ? 1 : 0.35 },
      itemStyle: { color: zoneColor(z) },
      markArea: zi === 0 ? { silent: true, itemStyle: { color: alpha(pal().gold, 0.18) },
        data: [[{ xAxis: wl.findIndex(w => w + 6 >= CLOSURE[0]) }, { xAxis: wl.findLastIndex(w => w <= CLOSURE[1]) }]] } : undefined,
    })),
  }));

  const E = TB.event_lift;
  $("events").innerHTML = `<thead><tr><th>Event</th><th>Scope</th><th class="num">Days</th><th class="num">Lift</th><th class="num">Extra theo</th></tr></thead><tbody>` +
    E.event_name.map((n, i) => `<tr><td>${esc(n)}<br><span class="sub">${esc(E.event_type[i])}</span></td><td>${esc(E.local_scope[i])}</td>
      <td class="num">${E.days[i]}</td><td class="num">${pct(E.coin_in_lift[i])}</td><td class="num">${usd(E.extra_theo_usd[i])}</td></tr>`).join("") + "</tbody>";

  const C = TB.city;
  set("c-city", base({
    xAxis: { type: "category", data: C.month.map(m => MONTH_LABEL[m]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", scale: true, axisLabel: { color: css("--muted"), formatter: v => v.toFixed(2) }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => v.toFixed(3) },
    series: [
      { name: "Casino coin-in per day", type: "line", data: C.casino_coin_in_per_day.map(v => v / C.casino_coin_in_per_day[0]), itemStyle: { color: pal().blue } },
      { name: "Las Vegas visitors per day (LVCVA)", type: "line", data: C.lv_visitors_per_day.map(v => v / C.lv_visitors_per_day[0]), itemStyle: { color: pal().orange }, lineStyle: { type: "dashed" } },
    ],
  }));

  // Aurora bank cannibalization test (fixed comparison, closure weeks excluded)
  const g = { "New bank B-51": [0, 0, 0, 0], "Rest of Center Pit": [0, 0, 0, 0], "Rest of floor": [0, 0, 0, 0] };
  const dayset = [new Set(), new Set()];
  const b51 = MD.banks.indexOf("B-51"), pit = MD.zones.indexOf("Center Pit");
  for (let i = 0; i < R.d.length; i++) {
    const d = R.d[i];
    if (d >= CLOSURE[0] && d <= CLOSURE[1]) continue;
    const after = d >= AURORA_OPEN ? 1 : 0;
    dayset[after].add(d);
    const k = R.b[i] === b51 ? "New bank B-51" : R.z[i] === pit ? "Rest of Center Pit" : "Rest of floor";
    g[k][after] += R.th[i];
  }
  const names = Object.keys(g);
  const per = (k, a) => g[k][a] / dayset[a].size;
  const total = a => names.reduce((s, k) => s + per(k, a), 0);
  set("c-aurora", base({
    grid: { left: 64, right: 20, top: 36, bottom: 30 },
    xAxis: { type: "category", data: [...names, "Whole floor"], axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: [0, 1].map(a => ({ name: a ? "After Mar 24" : "Before Mar 24", type: "bar",
      itemStyle: { color: a ? pal().blue : pal().gray },
      data: [...names.map(k => per(k, a)), total(a)] })),
  }));
}

function renderDowntime() {
  const R = MD.rows, M = MD.machines.id.length;
  const th = new Float64Array(M), av = new Float64Array(M);
  const keep = rowsWhere(i => R.d[i] >= S.s && R.d[i] <= S.e && zoneOk(R.z[i]) && bankOk(R.b[i]));
  keep.forEach(i => { th[R.m[i]] += R.th[i]; av[R.m[i]] += R.av[i]; });
  let down = 0, sch = 0, lost = 0;
  const lostMM = {}, mdays = {};
  keep.forEach(i => {
    const dn = R.sch[i] - R.av[i], mf = MD.machines.manufacturer[R.m[i]], k = month(R.d[i]);
    const l = av[R.m[i]] ? dn * th[R.m[i]] / av[R.m[i]] : 0;
    down += dn; sch += R.sch[i]; lost += l;
    (lostMM[mf] = lostMM[mf] || {})[k] = (lostMM[mf][k] || 0) + l;
    mdays[mf] = (mdays[mf] || 0) + 1;
  });
  const F = TB.faults;
  const fi = F.d.map((d, i) => i).filter(i => F.d[i] >= S.s && F.d[i] <= S.e && (S.zone === "all" || F.zone_name[i] === S.zone));
  $("k-down").textContent = int(down) + " h";
  $("k-down-f").textContent = `${pct(down / sch, 2)} of scheduled machine-hours`;
  $("k-lost").textContent = usd(lost);
  $("k-faults").textContent = int(fi.length);
  $("k-faults-f").textContent = S.zone === "all" ? "fault_repair tickets" : `in ${S.zone}`;
  $("k-wait").textContent = fi.length ? fix(fi.reduce((s, i) => s + F.wait[i], 0) / fi.length) + " h" : "–";

  const ms = MONTHS.filter(k => dnum(k + "-01") <= S.e && dnum(k + "-01") + 31 > S.s);
  set("c-lost", base({
    xAxis: { type: "category", data: ms.map(k => MONTH_LABEL[k]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: MFRS.map(mf => ({ name: mf, type: "bar", stack: "a", itemStyle: { color: mfrColor(mf) },
      data: ms.map(k => (lostMM[mf] || {})[k] || 0) })),
  }));

  const fc = {};
  fi.forEach(i => (fc[F.manufacturer[i]] = (fc[F.manufacturer[i]] || 0) + 1));
  const mfs = MFRS;
  set("c-rel", base({
    xAxis: { type: "category", data: mfs, axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", axisLabel: { color: css("--muted") }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", formatter: ps => { const m = ps[0].name;
      return `<b>${m}</b><br>${fix(ps[0].value, 1)} faults / 1,000 machine-days<br>${fc[m] || 0} faults over ${int(mdays[m] || 0)} machine-days`; } },
    series: [{ type: "bar", data: mfs.map(m => ({ value: mdays[m] ? 1000 * (fc[m] || 0) / mdays[m] : 0, itemStyle: { color: mfrColor(m) } })),
      label: { show: true, position: "top", formatter: p => p.value.toFixed(1), color: css("--ink") }, barWidth: "45%" }],
  }));

  const T = TB.staff, st = {};
  T.d.forEach((d, i) => {
    if (d < S.s || d > S.e) return;
    const k = T.shift[i] + "|" + month(d);
    const a = (st[k] = st[k] || [0, 0, 0]);
    a[0] += T.planned_techs[i]; a[1] += T.actual_techs[i]; a[2]++;
  });
  set("c-staff", base({
    xAxis: { type: "category", data: ms.map(k => MONTH_LABEL[k]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", min: 0, axisLabel: { color: css("--muted") }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => (v == null ? "–" : v.toFixed(2)) },
    series: ["day", "swing", "grave"].flatMap(s => [
      { name: `${s} actual`, type: "line", itemStyle: { color: shiftColor(s) }, lineStyle: { width: 2.5 },
        data: ms.map(k => st[s + "|" + k] ? st[s + "|" + k][1] / st[s + "|" + k][2] : null) },
      { name: `${s} planned`, type: "line", itemStyle: { color: shiftColor(s) }, lineStyle: { type: "dashed", width: 1.2 }, symbol: "none",
        data: ms.map(k => st[s + "|" + k] ? st[s + "|" + k][0] / st[s + "|" + k][2] : null) },
    ]),
  }));

  const wt = {};
  fi.forEach(i => { const k = F.shift[i] + "|" + month(F.d[i]); const a = (wt[k] = wt[k] || [0, 0]); a[0] += F.wait[i]; a[1]++; });
  const shifts = [...new Set(F.shift)].sort();
  set("c-wait", base({
    xAxis: { type: "category", data: ms.map(k => MONTH_LABEL[k]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", axisLabel: { color: css("--muted") }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => (v == null ? "–" : v.toFixed(2) + " h") },
    series: shifts.map(s => ({ name: s.slice(2), type: "bar", itemStyle: { color: shiftColor(s.split(" ")[1].toLowerCase()) },
      data: ms.map(k => wt[s + "|" + k] ? wt[s + "|" + k][0] / wt[s + "|" + k][1] : null) })),
  }));
}

function renderPlayers() {
  const P = PL.rows, preset = $("p-preset").value, tier = $("p-tier").value, region = $("p-region").value, age = $("p-age").value;
  const keep = P.preset.map((p, i) => i).filter(i => P.preset[i] === preset && (tier === "all" || P.tier[i] === tier) &&
    (region === "all" || P.region[i] === region) && (age === "all" || P.age[i] === age));
  const sum = k => keep.reduce((s, i) => s + P[k][i], 0);
  const n = sum("n");
  $("p-n").textContent = int(n);
  $("p-ci").textContent = usd(sum("ci"));
  $("p-po").textContent = usd(sum("po"));
  $("p-net").textContent = usd(sum("net"));
  $("p-th").textContent = usd(sum("th"));
  $("p-ahead").textContent = n ? pct(sum("ahead") / n) : "–";

  const dec = Array.from({ length: 10 }, () => 0);
  keep.forEach(i => (dec[P.decile[i] - 1] += -P.net[i]));
  const totalHW = dec.reduce((a, b) => a + b, 0);
  $("p-conc").textContent = totalHW > 0 ? `Top decile = ${pct(dec[0] / totalHW, 0)} of tracked house win in this group.` : "";
  set("c-decile", base({
    xAxis: { type: "category", data: dec.map((_, i) => i + 1), name: "Theo decile", nameLocation: "middle", nameGap: 26, axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: [{ type: "bar", name: "House win (−players' net)", data: dec, itemStyle: { color: p => (p.dataIndex === 0 ? pal().maroon : pal().blue), borderRadius: [2, 2, 0, 0] } }],
  }));

  const tiers = [...new Set(P.tier)].sort(), tn = {}, tc = {};
  keep.forEach(i => { tn[P.tier[i]] = (tn[P.tier[i]] || 0) + P.net[i]; tc[P.tier[i]] = (tc[P.tier[i]] || 0) + P.comp[i]; });
  set("c-tier", base({
    xAxis: { type: "category", data: tiers, axisLabel: { color: css("--muted") } },
    yAxis: [{ type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
            { type: "value", ...usdAxis, splitLine: { show: false } }],
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    series: [
      { type: "bar", name: "Players' net", data: tiers.map(t => tn[t] || 0), itemStyle: { color: pal().blue } },
      { type: "bar", name: "Comp cost (right axis)", yAxisIndex: 1, data: tiers.map(t => tc[t] || 0), itemStyle: { color: pal().orange } },
    ],
  }));
}

function renderComps() {
  const B = TB.comp_benefit, items = [...new Set(B.benefit_id)];
  set("c-points", base({
    xAxis: { type: "category", data: MONTHS.map(m => MONTH_LABEL[m]), axisLabel: { color: css("--muted") } },
    yAxis: { type: "value", name: "Points", axisLabel: { color: css("--muted") }, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => Math.round(v) + " pts" },
    series: items.map(b => ({ name: b.replace("COMP-", "").toLowerCase(), type: "line",
      data: MONTHS.map(m => { const i = B.benefit_id.findIndex((x, j) => x === b && B.month[j] === m); return i < 0 ? null : B.points_per_redemption[i]; }),
      markLine: b === items[0] ? { silent: true, symbol: "none", lineStyle: { color: css("--bad") }, label: { formatter: "May 1 price change", color: css("--bad") },
        data: [{ xAxis: "May" }] } : undefined })),
  }));
  const C = TB.comp_month;
  set("c-reinvest", base({
    xAxis: { type: "category", data: C.month.map(m => MONTH_LABEL[m]), axisLabel: { color: css("--muted") } },
    yAxis: [{ type: "value", ...usdAxis, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
            { type: "value", min: 0.01, axisLabel: { color: css("--muted"), formatter: v => pct(v, 2) }, splitLine: { show: false } }],
    tooltip: { trigger: "axis" },
    series: [
      { type: "bar", name: "Comp cost", data: C.comp_cost_usd, itemStyle: { color: pal().blue }, tooltip: { valueFormatter: v => usd(v) } },
      { type: "line", name: "Reinvestment", yAxisIndex: 1, data: C.reinvestment, itemStyle: { color: pal().orange }, lineStyle: { width: 2.5 },
        tooltip: { valueFormatter: v => pct(v, 2) } },
    ],
  }));
}

function renderModel() {
  const F = TB.forecast;
  const test0 = F.split.findIndex(s => s.startsWith("test"));
  set("c-forecast", base({
    xAxis: { type: "category", data: F.gaming_date, axisLabel: { color: css("--muted"), formatter: v => v.slice(5) } },
    yAxis: { type: "value", ...usdAxis, scale: true, splitLine: { lineStyle: { color: css("--line"), type: "dashed" } } },
    tooltip: { trigger: "axis", valueFormatter: v => usd(v) },
    dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 4 }],
    grid: { left: 64, right: 20, top: 36, bottom: 56 },
    series: [
      { name: "Actual", type: "line", data: F.actual, showSymbol: false, lineStyle: { color: css("--ink"), width: 1.8 }, itemStyle: { color: css("--ink") },
        markArea: { silent: true, itemStyle: { color: alpha(pal().gold, 0.16) }, data: [[{ xAxis: F.gaming_date[test0], name: "Holdout" }, { xAxis: F.gaming_date[F.gaming_date.length - 1] }]],
          label: { color: css("--muted") } } },
      { name: "Weekday + event uplift", type: "line", data: F.pred_weekday_event, showSymbol: false, itemStyle: { color: pal().green }, lineStyle: { width: 2 } },
      { name: "Weekday mean (model)", type: "line", data: F.pred_weekday, showSymbol: false, itemStyle: { color: pal().blue }, lineStyle: { width: 1.4, type: "dashed" } },
      { name: "Constant mean (baseline)", type: "line", data: F.pred_constant, showSymbol: false, itemStyle: { color: pal().orange }, lineStyle: { width: 1.4, type: "dotted" } },
    ],
  }));
  const S2 = TB.forecast_scores;
  $("scores").innerHTML = `<thead><tr><th>Split</th><th>Model</th><th class="num">MAE</th><th class="num">MAPE</th></tr></thead><tbody>` +
    S2.split.map((s, i) => `<tr><td>${esc(s)}</td><td>${esc(S2.model[i])}</td><td class="num">${usd(S2.mae_usd[i])}</td>
      <td class="num">${pct(S2.mape[i])}</td></tr>`).join("") + "</tbody>";
}

const CLAIMS = [
  ["The bottom 10 is mostly about location", "g_machine_day: Σ theo ÷ Σ available hours by theme × zone", "Back Forty is 41–55% lower for every theme", "Bad themes? The same themes earn well elsewhere", "Placement was not random"],
  ["Access drives Back Forty", "Weekly zone theo vs floor_walkways closure (W-ENT-B40)", "≈−30% during Mar 3–Apr 6, recovered after reopening", "Seasonality? Main Entrance flat over the same weeks", "One closure episode"],
  ["Replacing a machine in place doesn't fix it", "g_machine_day, slot L-38-5: M-1120 → M-5076 (May 13)", "$6.00 → $6.39 theo per available hour", "A new game might ramp up", "49 days after the swap"],
  ["New machines mostly redistribute play", "Aurora bank B-51 (Mar 24) vs rest of floor (page 3)", "+$5.4k/day on the new bank, −$8.1k/day elsewhere", "June citywide slowdown also lowers the rest", "Before/after, no control"],
  ["M-1158 is a lead to inspect", "Payout-positive spins vs game_math.hit_probability", "38.5% vs 31.5% every month, hit z ≈ 124; hold 3.0% vs 10%", "Luck? A z this large is not chance", "Could be a meter or config error; inspection decides. Not evidence of wrongdoing"],
  ["Other low earners are within luck", "luck z = Σ(house win − theo) ÷ √Σ(bet² × payout variance)", "SD of z = 1.09 across 310 machines; 20 with |z| > 2 vs ≈14 expected", "Mis-specified variance? SD near 1 says no", "Assumes independent spins"],
  ["Exposure distorts the manager's list", "days_on_floor", "3 of the bottom 10 were on the floor 49–132 days", "—", "—"],
  ["Promotions lift play", "g_event_lift: Winter Slot Tournament (Feb 21–23)", "+18% coin-in vs no-event weekday mean, ≈+$80k theo, no dip on surrounding days", "Citywide event that weekend? None in events", "Single example; July may differ"],
  ["Comp points price halved on May 1", "g_comp_redemptions: points per redemption by benefit", "Beer 114 → 53 points, same $9 face value; every item halved", "Mix shift? Every item changed", "Reason not in the data"],
  ["Comp cost rose without a lift in play", "comp cost ÷ tracked theo by month", "1.11% (Jan) → 1.32% (Jun); coin-in flat", "Higher demand? Coin-in per day did not rise", "Carded play only"],
  ["Downtime is too small to fund staff", "g_fault_tickets, g_tech_staffing, g_machine_day", "≈5,000 down hours, ≈$90k theo in 6 months; May waits spiked with day-shift techs at 0.9 vs 1.7 planned", "Lost demand? Valued at each machine's own theo rate", "Upper bound: players may switch machines"],
  ["Ridgeline is least reliable", "Faults per 1,000 machine-days", "40.4 vs 11.1 (Halcyon) and 16.7 (Northwind)", "Busier zones? Rate is per machine-day", "Machine age not separated"],
  ["Weekday forecast beats the baseline", "g_forecast_scores, holdout May–Jun", "MAE $218k → $69k (weekday) → $51k (with events)", "Overfitting? Frozen on Jan–Apr, scored on unseen months", "Two holdout months"],
  ["Player results are concentrated", "g_player_period, deciles by full-period theo", "Top 10% = 64% of tracked house win; 16% of players ahead", "—", "Carded only (≈66% of coin-in)"],
];

function renderEvidence() {
  $("claims").innerHTML = `<thead><tr><th>#</th><th>Claim</th><th>Table → query</th><th>Result</th><th>Alternative tested</th><th>Limitation</th></tr></thead><tbody>` +
    CLAIMS.map((c, i) => `<tr><td>${i + 1}</td>${c.map((x, j) => `<td>${j === 1 ? `<code>${esc(x)}</code>` : esc(x)}</td>`).join("")}</tr>`).join("") + "</tbody>";
}

const RENDER = {
  decision: renderDecision, machines: renderMachines, demand: renderDemand, downtime: renderDowntime,
  players: renderPlayers, comps: renderComps, model: renderModel, evidence: renderEvidence,
};

// Which of the shared controls each tab responds to, and what the judge should know about the rest.
const SCOPE = {
  decision: { period: true, place: false, note: "Zone and Bank don't apply: the manager's list is floor-wide." },
  machines: { period: true, place: true, note: "The heatmap always shows every zone so they can be compared." },
  demand: { period: true, place: true, note: "Zone highlights a line in the weekly zone chart; Bank filters it. Event lift, city and new-bank charts use the full period." },
  downtime: { period: true, place: true, note: "Technician staffing is floor-wide." },
  players: { period: false, place: false, note: "This tab uses its own period and player filters (below)." },
  comps: { period: false, place: false, note: "Always shows all six months, so the May 1 price change is visible." },
  model: { period: false, place: false, note: "Always shows the full training and holdout split." },
  evidence: { period: false, place: false, note: "Static list of claims." },
};

function renderScope() {
  const sc = SCOPE[S.tab];
  ["c-start", "c-end", "presets"].forEach(id => $(id).classList.toggle("off", !sc.period));
  ["c-zone", "c-bank"].forEach(id => $(id).classList.toggle("off", !sc.place));
  const fmt = d => new Date(BASE + d * 864e5).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
  const parts = [];
  if (sc.period) parts.push(`<b>${fmt(S.s)} – ${fmt(S.e)}, 2025</b> (${S.e - S.s + 1} days)`);
  if (sc.place) parts.push(`<b>${S.zone === "all" ? "all zones" : esc(S.zone)}</b>`, `<b>${S.bank === "all" ? "all banks" : esc(S.bank)}</b>`);
  $("scope").innerHTML = (parts.length ? "Showing " + parts.join(" · ") + ". " : "") + esc(sc.note);
}

function render() {
  const nb = document.querySelector(`#tabs button[data-t="${S.tab}"]`);
  $("page-kicker").textContent = nb.dataset.kicker;
  $("page-title").textContent = nb.dataset.title;
  renderScope();
  RENDER[S.tab]();
  requestAnimationFrame(() => Object.values(charts).forEach(c => c.getDom().offsetParent && c.resize()));
}

// ---------------------------------------------------------------- wiring

function setPeriod(s, e) {
  S.s = Math.max(0, Math.min(dnum(s), 180));
  S.e = Math.max(S.s, Math.min(dnum(e), 180));
  $("start").value = dstr(S.s);
  $("end").value = dstr(S.e);
  document.querySelectorAll("#presets button").forEach(b => b.classList.toggle("on", b.dataset.s === dstr(S.s) && b.dataset.e === dstr(S.e)));
  render();
}

function init() {
  MD.zones.forEach(z => $("zone").add(new Option(z, z)));
  MD.banks.forEach(b => $("bank").add(new Option(b, b)));
  PL.presets.forEach(p => $("p-preset").add(new Option(p.label, p.key)));
  [["p-tier", "tier"], ["p-region", "region"], ["p-age", "age"]].forEach(([id, k]) =>
    [...new Set(PL.rows[k])].sort().forEach(v => $(id).add(new Option(v, v))));

  $("start").onchange = () => setPeriod($("start").value, $("end").value);
  $("end").onchange = () => setPeriod($("start").value, $("end").value);
  $("presets").onclick = e => { const b = e.target.closest("button"); if (b) setPeriod(b.dataset.s, b.dataset.e); };
  $("zone").onchange = e => { S.zone = e.target.value; render(); };
  $("bank").onchange = e => { S.bank = e.target.value; render(); };
  ["p-preset", "p-tier", "p-region", "p-age"].forEach(id => ($(id).onchange = renderPlayers));
  $("tabs").onclick = e => {
    const b = e.target.closest("button"); if (!b) return;
    S.tab = b.dataset.t;
    document.querySelectorAll("#tabs button").forEach(x => x.classList.toggle("on", x === b));
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t.id === "t-" + S.tab));
    history.replaceState(null, "", "#" + S.tab);
    render();
  };
  $("reset").onclick = () => {
    S.zone = S.bank = "all"; $("zone").value = $("bank").value = "all";
    setPeriod("2025-01-01", "2025-06-30");
  };
  document.querySelector(".guide").onclick = e => {
    const b = e.target.closest("button[data-go]"); if (!b) return;
    document.querySelector(`#tabs button[data-t="${b.dataset.go}"]`).click();
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (b.dataset.focus) $(b.dataset.focus).focus({ preventScroll: true });
  };
  $("search").oninput = e => { S.q = e.target.value.toLowerCase(); renderMachines(); };
  $("scorecard").onclick = e => {
    const th = e.target.closest("th[data-k]");
    if (th) { S.asc = S.sort === th.dataset.k ? !S.asc : true; S.sort = th.dataset.k; return renderMachines(); }
    const tr = e.target.closest("tr[data-m]");
    if (tr) { S.sel = S.sel === +tr.dataset.m ? null : +tr.dataset.m; renderMachines(); }
  };
  window.addEventListener("resize", () => Object.values(charts).forEach(c => c.resize()));
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

  const hash = location.hash.slice(1);
  $("loading").remove();
  if (RENDER[hash]) document.querySelector(`#tabs button[data-t="${hash}"]`).click();
  else render();
}

Promise.all(["data/machine_day.json", "data/players.json", "data/tables.json"].map(u => fetch(u).then(r => r.json())))
  .then(([md, pl, tb]) => { MD = md; PL = pl; TB = tb; init(); })
  .catch(err => { $("loading").textContent = "Could not load data: " + err.message; });
