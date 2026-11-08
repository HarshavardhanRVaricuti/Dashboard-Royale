// Casino dressing for the public page: lights, chips, cards, and the slot in the hero.
// Decorative only — no dashboard data is read or changed here.

(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const CELL = 64;
  const SYMBOLS = [["7", "s7"], ["β", "sb"], ["♠", ""], ["♥", "sr"], ["♦", "sr"], ["♣", ""], ["<span>BAR</span>", "bar"]];
  const pick = () => Math.floor(Math.random() * SYMBOLS.length);
  const cell = i => `<div class="${SYMBOLS[i][1]}">${SYMBOLS[i][0]}</div>`;

  const ticker = document.getElementById("ticker");
  if (ticker) {
    const line = " ★ THE GILDED ACE ★ JACKPOT ★ β BETA DANCERS ★ 7 7 7 ★ LUCK · LOCATION · OR A LEAK? ★ M-1158 38.5% VS 31.5% ★ DON'T REPLACE THE BOTTOM 10 ★ ";
    ticker.innerHTML = `<span>${line}</span><span>${line}</span>`;
  }

  const lights = document.getElementById("lights");
  if (!still && lights) {
    const ranks = ["A", "K", "Q", "J", "10", "9"];
    const suits = [["♠", ""], ["♥", "red"], ["♦", "red"], ["♣", ""]];
    for (let i = 0; i < 22; i++) {
      const el = document.createElement("div");
      const kind = i % 5;
      if (kind === 0) {
        const [s, cls] = suits[i % 4];
        el.className = "float pcard" + (cls ? " " + cls : "");
        el.textContent = ranks[i % ranks.length] + s;
      } else if (kind === 1) {
        el.className = "float chip";
      } else {
        el.className = "float";
        el.textContent = "♠♥♦♣"[i % 4];
        if (i % 2) el.style.color = "rgba(var(--alert-rgb), .16)";
        el.style.fontSize = `${22 + Math.random() * 22}px`;
      }
      el.style.left = `${(i * 4.6 + Math.random() * 3) % 98}vw`;
      el.style.animationDuration = `${18 + Math.random() * 20}s`;
      el.style.animationDelay = `${-Math.random() * 36}s`;
      lights.appendChild(el);
    }
  }

  const slot = document.getElementById("slot");
  if (!slot) return;
  const strips = [...slot.querySelectorAll(".strip")];
  const lever = document.getElementById("lever");
  let spinning = false, first = true;

  function land(targets) {
    strips.forEach((s, r) => { s.style.transition = "none"; s.style.transform = "none"; s.innerHTML = cell(targets[r]); });
  }

  function coins() {
    if (still) return;
    for (let i = 0; i < 14; i++) {
      const c = document.createElement("div");
      c.className = "coin";
      const ang = (i / 14) * Math.PI * 2, dist = 40 + Math.random() * 70;
      c.style.setProperty("--x", Math.cos(ang) * dist + "px");
      c.style.setProperty("--y", Math.sin(ang) * dist - 20 + "px");
      c.style.left = "50%";
      c.style.top = "36%";
      slot.appendChild(c);
      setTimeout(() => c.remove(), 950);
    }
  }

  function spin() {
    if (spinning) return;
    spinning = true;
    slot.classList.remove("win");
    lever.classList.add("pull");
    setTimeout(() => lever.classList.remove("pull"), 350);

    const beta = SYMBOLS.findIndex(s => s[1] === "sb"), seven = 0;
    const jackpot = first || Math.random() < 0.28;
    const sym = jackpot ? (first || Math.random() < 0.5 ? beta : seven) : null;
    const targets = jackpot ? [sym, sym, sym] : [pick(), pick(), pick()];
    if (!jackpot && targets[0] === targets[1] && targets[1] === targets[2]) targets[2] = (targets[2] + 1) % SYMBOLS.length;
    first = false;

    if (still) { land(targets); finish(targets); return; }
    strips.forEach((s, r) => {
      const n = 18 + r * 6, list = Array.from({ length: n }, pick);
      list.push(targets[r]);
      s.style.transition = "none";
      s.style.transform = "translateY(0)";
      s.innerHTML = list.map(cell).join("");
      s.offsetHeight;
      s.style.transition = `transform ${1.3 + r * 0.45}s cubic-bezier(.12,.75,.25,1)`;
      s.style.transform = `translateY(${-(list.length - 1) * CELL}px)`;
    });
    setTimeout(() => { land(targets); finish(targets); }, (1.3 + 2 * 0.45) * 1000 + 80);
  }

  function finish(t) {
    spinning = false;
    if (t[0] === t[1] && t[1] === t[2]) { slot.classList.add("win"); coins(); }
  }

  lever.addEventListener("click", spin);
  land([1, 1, 1]);
  if (!still) {
    setTimeout(spin, 700);
    setInterval(() => { if (!document.hidden) spin(); }, 9000);
  }

  const flips = [...document.querySelectorAll("button.flip")];
  const fitFlip = btn => {
    const inner = btn.querySelector(".flip-inner");
    const face = btn.classList.contains("on") ? btn.querySelector(".flip-back") : btn.querySelector(".flip-front");
    const h = face.scrollHeight;
    if (h) inner.style.height = h + "px";
  };
  const fitFlips = () => flips.forEach(fitFlip);
  const faces = btn => {
    const on = btn.classList.contains("on");
    btn.querySelector(".flip-front").setAttribute("aria-hidden", on);
    btn.querySelector(".flip-back").setAttribute("aria-hidden", !on);
  };
  flips.forEach(btn => {
    faces(btn);
    fitFlip(btn);
    btn.addEventListener("click", () => {
      btn.classList.toggle("on");
      btn.setAttribute("aria-expanded", btn.classList.contains("on"));
      faces(btn);
      requestAnimationFrame(() => fitFlip(btn));
    });
  });
  document.getElementById("tabs")?.addEventListener("click", () => requestAnimationFrame(fitFlips));
  window.addEventListener("resize", fitFlips);
})();
