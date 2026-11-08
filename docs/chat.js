// Floor desk. Answers are built from the tables already loaded by app.js.
// No network call, no key, and the typed text is never treated as an instruction.

(() => {
  const MAX = 280;
  const log = [];
  let last = 0, ready = false;

  const period = () => `${dstr(S.s)} to ${dstr(S.e)} · ${scoped() ? scopeName() : "all zones and banks"}`;

  function totals() {
    let hw = 0, th = 0, ci = 0, n = 0;
    if (scoped()) scopedDays().forEach(a => { hw += a.hw; th += a.th; ci += a.ci; n++; });
    else TB.property_day.gaming_date.forEach((g, i) => {
      const d = dnum(g);
      if (d < S.s || d > S.e) return;
      hw += TB.property_day.house_win_usd[i];
      th += TB.property_day.theo_usd[i];
      ci += TB.property_day.coin_in_usd[i];
      n++;
    });
    return { hw, th, ci, n };
  }

  function faults() {
    const F = TB.faults;
    let n = 0, w = 0;
    for (let i = 0; i < F.d.length; i++) {
      if (F.d[i] < S.s || F.d[i] > S.e) continue;
      if (S.zone !== "all" && F.zone_name[i] !== S.zone) continue;
      if (S.bank !== "all" && F.bank[i] !== S.bank) continue;
      n++; w += F.wait[i];
    }
    return { n, wait: n ? w / n : null };
  }

  function machine(id) {
    const row = machineAgg(S.s, S.e).find(r => r.id.toUpperCase() === id);
    if (!row) {
      const known = MD.machines.id.some(x => x.toUpperCase() === id);
      return known
        ? `${id} is a real machine, but it has no play in ${period()}. Widen the dates or clear the zone and bank.`
        : `No machine ${id} is on this floor. Ids look like M-1158.`;
    }
    return {
      text: `${row.id} · ${row.theme} · ${row.zone} (${row.bank}) · ${row.manufacturer}\n` +
        `${row.days} days on the floor. House win ${usd(row.hw)}, theo ${usd(row.th)}, luck z ${fix(row.luck_z)}.\n` +
        `Hit rate ${pct(row.hit)} vs published ${pct(row.pub_hit)} (hit z ${fix(row.hit_z, 1)}). Theo per available hour $${fix(row.theo_hr)}.\n` +
        `Read: ${row.diagnosis[1]}.`,
      src: "g_machine_day, recomputed for " + period(),
    };
  }

  function bottom() {
    const list = machineAgg(S.s, S.e).sort((a, b) => a.manager_rank - b.manager_rank).slice(0, 10);
    const lines = list.map(r => `${r.manager_rank}. ${r.id} · ${r.zone} · ${r.days}d · ${r.diagnosis[1]}`);
    const leaks = list.filter(r => r.diagnosis[0] === "leak").map(r => r.id);
    return {
      text: `Manager's bottom 10 by raw house win.\n${lines.join("\n")}\n` +
        (leaks.length ? `Worth inspecting: ${leaks.join(", ")}. The rest are location, exposure, or ordinary luck.` : "None of these fail the hit-rate test."),
      src: "g_machine_day · " + period(),
    };
  }

  function plan() {
    const B = TB.budget;
    const spent = B.cost_usd.reduce((a, b) => a + b, 0);
    const lines = B.name.map((name, i) => `${name}: $${int(B.cost_usd[i])}. ${B.expected_effect[i]}`);
    return {
      text: `Spend $${int(spent)} of $100,000 and keep $${int(100000 - spent)}.\n${lines.join("\n")}`,
      src: "g_budget_plan · the plan is floor-wide and does not follow the zone filter",
    };
  }

  function model() {
    const S2 = TB.forecast_scores;
    const lines = S2.split.map((s, i) => `${s} · ${S2.model[i]}: MAE ${usd(S2.mae_usd[i])} (${pct(S2.mape[i])})`);
    return {
      text: `Daily floor coin-in. Trained Jan–Apr, scored on May–Jun, both forecasts frozen before the test.\n${lines.join("\n")}\n` +
        "The weekday model is what changes the decision: staff and the promotion weekend go on Fri–Sun, and the frozen forecast is the yardstick for the promotion.",
      src: "g_forecast_scores · floor-wide, filters do not apply",
    };
  }

  function reply(raw) {
    const q = String(raw).replace(/[\u0000-\u001F]/g, " ").replace(/\s+/g, " ").trim().slice(0, MAX);
    if (!q) return { text: "Ask about a machine, the bottom 10, the $100k plan, or the model." };
    if (/(ignore (all |any |the |previous |your )?instructions|system prompt|you are now|jailbreak|developer mode|<\s*script|api[_ ]?key|reveal (the |your )?prompt)/i.test(q))
      return { text: "I only answer questions about this floor, from the tables already loaded. I don't take new instructions, and nothing you type leaves this page." };
    if (/@|\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b|player id|guest name|social security|\bssn\b|password|credit card/i.test(q))
      return { text: "I don't look up individual guests, and this page has no names, emails, or account numbers. Player figures are aggregates of carded play." };

    const id = q.match(/\bM-\d{3,5}\b/i);
    if (id) return machine(id[0].toUpperCase());
    const low = q.toLowerCase();
    if (/bottom|weakest|replace|worst/.test(low)) return bottom();
    if (/\$?100|budget|plan|spend|keep|wayfinding|promotion|inspect/.test(low)) return plan();
    if (/model|forecast|mae|holdout|baseline|error/.test(low)) return model();
    if (/house win|hold\b|coin-?in|how much|revenue|theo\b/.test(low)) {
      const t = totals();
      return {
        text: `House win ${usd(t.hw)} against theo ${usd(t.th)} (luck ${usd(t.hw - t.th)}). Observed hold ${pct(t.hw / t.ci, 2)} vs theo hold ${pct(t.th / t.ci, 2)}, over ${t.n} days and coin-in ${usd(t.ci)}.`,
        src: "g_machine_day and g_property_day · " + period(),
      };
    }
    if (/back forty|walkway|location|access/.test(low))
      return { text: "Every theme earns 41–55% less in Back Forty than the same theme at the Main Entrance. While the entrance walkway was closed (Mar 3–Apr 6) Back Forty theo fell about 30%, then recovered. Swapping the machine in slot L-38-5 moved theo per hour only from $6.00 to $6.39.", src: "g_machine_day, floor_walkways · full period" };
    if (/downtime|fault|ridgeline|technician|wait/.test(low)) {
      const f = faults();
      return { text: `In this selection: ${int(f.n)} fault tickets, average wait ${f.wait == null ? "–" : fix(f.wait) + " h"}.\nFloor-wide over six months there are about 5,000 down hours, worth at most about $90k theo. Ridgeline faults 2.4–3.6× as often as the other makers. That is too small to spend the budget on extra technicians.`,       src: "g_fault_tickets · " + period() };
    }
    if (/comp|points|beer|reinvest/.test(low))
      return { text: "On May 1 every comp's points price roughly halved (a beer went from about 114 to 53 points) while the menu price stayed put. Comp cost rose from 1.11% of tracked theo in January to 1.32% in June, with no visible lift in play.", src: "g_comp_redemptions" };
    if (/player|decile|carded|tier|guest/.test(low))
      return { text: "Carded play is about 66% of coin-in. Players wagered $164M, got back $148M, and lost a net $15.6M. 16% finished ahead, and the top 10% account for 64% of tracked house win. The Players page can narrow that by tier, region, and age. I won't look up one person.", src: "g_player_period · full period" };
    if (/filter|zone|bank/.test(low))
      return { text: `You're on ${period()}. Zone and bank change Decision, Machines, Demand, and Downtime. Players, comps, and the model stay floor-wide, and the page says so when a filter is on.` };
    return { text: "I can answer about a machine (try M-1158), the bottom 10, house win, the $100k plan, the forecast, Back Forty, downtime, comps, or players. I only use the tables on this page." };
  }

  function add(who, msg) {
    const el = document.createElement("div");
    el.className = "bubble " + who;
    el.textContent = msg.text || msg;
    if (msg.src) {
      const s = document.createElement("div");
      s.className = "src";
      s.textContent = msg.src;
      el.appendChild(s);
    }
    document.getElementById("chat-log").appendChild(el);
    el.scrollIntoView({ block: "end" });
    log.push(who);
    while (document.getElementById("chat-log").children.length > 30)
      document.getElementById("chat-log").firstChild.remove();
  }

  function ask(text) {
    const now = Date.now();
    if (now - last < 400) return;
    last = now;
    add("me", text.slice(0, MAX));
    add("bot", reply(text));
  }

  window.startChat = () => {
    if (ready) return;
    ready = true;
    const box = document.getElementById("chat");
    const open = document.getElementById("chat-open");
    const setOpen = on => { box.hidden = !on; open.setAttribute("aria-expanded", on); };
    open.addEventListener("click", () => setOpen(box.hidden));
    document.getElementById("chat-x").addEventListener("click", () => setOpen(false));
    document.getElementById("chat-form").addEventListener("submit", e => {
      e.preventDefault();
      const input = document.getElementById("chat-q");
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      ask(text);
    });
    document.getElementById("chat-chips").addEventListener("click", e => {
      const b = e.target.closest("button");
      if (b) ask(b.textContent);
    });
    add("bot", { text: "Ask me about the floor. Try a machine id, the bottom 10, the plan, or the model.", src: "Answers stay on this page" });
  };
})();
