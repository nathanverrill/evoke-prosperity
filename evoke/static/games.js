/* games.js — Training Sims (browser minigames) + the Alchemy Signal hunt.
   Same rules as Minecraft quests (GAME_DESIGN.md/thread5 canon): optional,
   self-directed, never gates or grades a mission. XP flows through the real
   event pipeline via POST /api/minigames/{key}/score, capped server-side at
   one daily grant per game so grinding a sim can't out-earn missions.

   Both sims are the curriculum wearing a game costume, not decoration:
   Flow Control is GAME_DESIGN §12's arc-1 concept (scarcity/budgeting/
   emergency fund) as pressure-management; Signal Decrypt drills the §12
   vocabulary as intercepted Broker transmissions. */

(() => {
  const { api, state } = Evoke;

  // ---------- shared ----------
  async function postScore(gameKey, score) {
    const fd = new FormData();
    fd.append("score", String(score));
    try {
      const res = await fetch(`/api/minigames/${gameKey}/score?user_id=${state.userId}`, { method: "POST", body: fd }).then(r => r.json());
      if (res.xp_granted) Evoke.toast(`+${res.xp_granted} XP — training logged${res.personal_best ? " · new personal best" : ""}`);
      else if (res.personal_best) Evoke.toast("New personal best · daily training XP already earned");
      return res;
    } catch (e) { return null; }
  }

  async function leaderboardHtml(gameKey) {
    try {
      const lb = await fetch(`/api/minigames/${gameKey}/leaderboard?user_id=${state.userId}`).then(r => r.json());
      const rows = lb.leaderboard || [];
      return `
        <div class="card">
          <div class="card__eyebrow">Top Agents</div>
          ${rows.length ? rows.map((r, i) => `
            <div class="feed-item"><span class="mono-rank">${String(i + 1).padStart(2, "0")}</span> ${Evoke.escapeHtml(r.display_name)} <span class="empty-state">· ${r.best}</span></div>
          `).join("") : `<p class="empty-state">No runs logged yet. Be first.</p>`}
          ${lb.personal_best !== null ? `<p class="empty-state" style="margin-top:var(--space-2)">Your best: ${lb.personal_best}</p>` : ""}
        </div>
      `;
    } catch (e) { return ""; }
  }

  // ---------- Alchemy Signal (scavenger hunt) ----------
  // 5 fragments hidden across the app; server-tracked so the unlock can't
  // be re-farmed. Copy on the unlock screen is deliberately minimal --
  // GAME_DESIGN.md §13.5 leaves Alchemy's signal beats to the narrative
  // team, so nothing here invents backstory.
  const signal = {
    progress: null,
    async load() {
      try { this.progress = await fetch(`/api/minigames/signal/${state.userId}`).then(r => r.json()); }
      catch (e) { this.progress = { found: [], total: 5, unlocked: false }; }
      return this.progress;
    },
    async collect(fragment) {
      const before = this.progress || await this.load();
      if (before.found.includes(fragment)) return;
      const fd = new FormData();
      fd.append("fragment", fragment);
      try {
        const res = await fetch(`/api/minigames/signal/fragment?user_id=${state.userId}`, { method: "POST", body: fd }).then(r => r.json());
        this.progress = { found: res.found, total: res.total, unlocked: res.unlocked || (this.progress && this.progress.unlocked) };
        if (res.unlocked) {
          Evoke.toast(`<strong>⬡ SIGNAL LOCKED — ALL ${res.total} FRAGMENTS.</strong><br>Something is transmitting. <a href="#/alchemy">Open the channel →</a>`, { kind: "world", ttl: 12000 });
        } else {
          Evoke.toast(`⬡ Signal fragment acquired — ${res.found.length}/${res.total}`);
        }
      } catch (e) { /* silent -- easter eggs never error loudly */ }
    },
    // Call on screens that hide a node. Renders a faint interactive glyph.
    nodeHtml(fragment) {
      return `<span class="signal-node" data-fragment="${fragment}" title="…a stray signal?">⬡</span>`;
    },
    bindNodes(rootEl) {
      (rootEl || document).querySelectorAll(".signal-node").forEach(el => {
        el.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          el.classList.add("is-found");
          signal.collect(el.dataset.fragment);
        }, { once: true });
      });
    },
  };
  Evoke.signal = signal;

  // Konami code -> fragment. Global, once per page load.
  const KONAMI = ["ArrowUp","ArrowUp","ArrowDown","ArrowDown","ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"];
  let konamiIdx = 0;
  document.addEventListener("keydown", (e) => {
    konamiIdx = (e.key === KONAMI[konamiIdx]) ? konamiIdx + 1 : (e.key === KONAMI[0] ? 1 : 0);
    if (konamiIdx === KONAMI.length) {
      konamiIdx = 0;
      signal.collect("konami");
    }
  });

  // ---------- Arcade ----------
  Evoke.screens.arcade = async function arcade() {
    const [flowLb, decryptLb, sig] = await Promise.all([
      leaderboardHtml("flow-control"),
      leaderboardHtml("signal-decrypt"),
      signal.load(),
    ]);
    Evoke.mount(`
      <div class="stack">
        <div class="row-between">
          <h1>Training</h1>
          <span class="chip chip--green"><span class="dot"></span>Sim Deck Online</span>
        </div>
        <p class="empty-state">Field simulations. Optional, never graded — but the Basin remembers your scores. Daily training earns XP once per sim.</p>
        <div class="grid-2">
          <div class="stack-sm">
            <a class="card mission-card game-card" data-state="available" href="#/game/flow">
              <div class="card__eyebrow">SIM 01 · Scarcity & Budgeting</div>
              <div class="mission-card__title">FLOW CONTROL</div>
              <p>Keel's reclaimed water is limited. Route it. Survive six cycles. Learn why the cistern matters <em>before</em> the pipe bursts.</p>
              <span class="btn btn-primary">Initialize →</span>
            </a>
            ${flowLb}
          </div>
          <div class="stack-sm">
            <a class="card mission-card game-card" data-state="available" href="#/game/decrypt">
              <div class="card__eyebrow">SIM 02 · The Language of Money</div>
              <div class="mission-card__title">SIGNAL DECRYPT</div>
              <p>Intercepted Broker transmissions, one encrypted term each. Three traces and the channel burns. Know the words they don't want you to know.</p>
              <span class="btn btn-primary">Initialize →</span>
            </a>
            ${decryptLb}
          </div>
        </div>
        <div class="card">
          <div class="card__eyebrow">⬡ Anomalous Signal</div>
          <p class="empty-state">${sig.unlocked
            ? `Channel open. <a href="#/alchemy">Listen again →</a>`
            : `${sig.found.length} of ${sig.total} fragments triangulated. They're scattered where only the curious look. That's the whole hint.`}</p>
        </div>
      </div>
    `);
  };

  // ---------- SIM 01: FLOW CONTROL ----------
  // Turn-based allocation: each cycle brings a variable amount of reclaimed
  // flow; route it across HOME (needs), MARKET (wants/trade), CISTERN
  // (savings/emergency fund), NETWORK (community/giving). Shocks hit; the
  // cistern absorbs them; the network deflects Broker pressure. Six cycles.
  const FLOW_EVENTS = [
    { key: "burst", name: "PIPE BURST", lesson: "Emergency funds exist for exactly this.", apply(s, log) {
        let dmg = 15;
        const spend = Math.min(s.cistern, 5);
        if (spend > 0) { dmg -= spend * 3; s.cistern -= spend; log(`Cistern released ${spend} units — absorbed ${spend * 3} damage.`); }
        dmg = Math.max(0, dmg);
        s.home -= dmg;
        log(`HOME integrity -${dmg}.${spend ? "" : " No reserve to soften it."}`);
      } },
    { key: "toll", name: "BROKER TOLL", lesson: "Monopolies price what you can't route around. Networks route around.", apply(s, log) {
        if (s.network >= 3) { log("Neighbors rerouted supply lines around the toll. MARKET untouched."); }
        else { s.market -= 12; log("MARKET integrity -12. Nobody owed Keel a favor today."); }
      } },
    { key: "drought", name: "DROUGHT CYCLE", lesson: "Income varies. Plans that only work on good months aren't plans.", apply(s, log) {
        s.incomeDelta = -4; log("Next cycle's reclaimed flow -4.");
      } },
    { key: "surge", name: "MOUNTAIN THAW", lesson: "Windfalls test discipline more than droughts do.", apply(s, log) {
        s.incomeDelta = +4; log("Next cycle's reclaimed flow +4. Spend it like it'll happen again — and it won't.");
      } },
    { key: "festival", name: "KEEL FESTIVAL", lesson: "Community is an asset class.", apply(s, log) {
        if (s.network >= 2) { s.market += 8; log("The festival ran on shared water. MARKET +8 — goodwill pays dividends."); }
        else { log("A quiet festival. Nothing lost, nothing gained."); }
      } },
  ];

  Evoke.screens.gameFlow = async function gameFlow() {
    const TOTAL_CYCLES = 6;
    const s = { cycle: 1, home: 70, market: 60, cistern: 0, network: 0, incomeDelta: 0, over: false, lessons: [] };
    let events = [...FLOW_EVENTS].sort(() => Math.random() - 0.5);
    let alloc, income, logLines;

    function newCycle() {
      income = Math.max(4, 10 + s.incomeDelta + Math.floor(Math.random() * 3) - 1);
      s.incomeDelta = 0;
      alloc = { home: 0, market: 0, cistern: 0, network: 0 };
      logLines = [];
    }

    const gauge = (label, val, max, cls) => `
      <div class="flow-gauge">
        <div class="row-between"><span class="card__eyebrow">${label}</span><span class="mono-rank">${val}</span></div>
        <div class="world-meter__track flow-gauge__track"><div class="world-meter__fill ${cls || ""}" style="width:${Math.max(0, Math.min(100, (val / max) * 100))}%"></div></div>
      </div>`;

    function render() {
      const spent = alloc.home + alloc.market + alloc.cistern + alloc.network;
      const left = income - spent;
      const stepper = (key, label, hint) => `
        <div class="flow-stepper">
          <div><strong>${label}</strong> <span class="empty-state">${hint}</span></div>
          <div class="row">
            <button data-step="${key}:-1" ${alloc[key] <= 0 ? "disabled" : ""}>−</button>
            <span class="mono-rank">${alloc[key]}</span>
            <button data-step="${key}:1" ${left <= 0 ? "disabled" : ""}>+</button>
          </div>
        </div>`;

      Evoke.mount(`
        <div class="stack game-screen">
          <div class="row-between">
            <h1>Flow Control</h1>
            <span class="chip">CYCLE ${s.cycle} / ${TOTAL_CYCLES}</span>
          </div>
          <div class="grid-2">
            <div class="card">
              <div class="card__eyebrow">Keel Systems</div>
              ${gauge("HOME — needs", s.home, 100)}
              ${gauge("MARKET — trade", s.market, 100)}
              ${gauge("CISTERN — reserve", s.cistern, 12, "is-water")}
              ${gauge("NETWORK — goodwill", s.network, 12, "is-water")}
              <p class="empty-state" style="margin-top:var(--space-2)">HOME decays 6/cycle, MARKET 4/cycle. Each unit routed restores 2. The cistern holds what you bank; the network remembers what you give.</p>
            </div>
            <div class="card">
              <div class="card__eyebrow">Reclaimed Flow — ${income} units · <strong>${left} unrouted</strong></div>
              ${stepper("home", "HOME", "keep the lights on")}
              ${stepper("market", "MARKET", "stalls, trade, repairs")}
              ${stepper("cistern", "CISTERN", "bank it for shocks")}
              ${stepper("network", "NETWORK", "share it forward")}
              <button class="btn btn-primary" id="flow-commit" style="margin-top:var(--space-3)">COMMIT CYCLE ${left > 0 ? `(${left} will drain to runoff)` : ""}</button>
            </div>
          </div>
          <div class="card">
            <div class="card__eyebrow">System Log</div>
            <div id="flow-log">${logLines.map(l => `<div class="feed-item mono-log">${l}</div>`).join("") || `<p class="empty-state">Awaiting first commit…</p>`}</div>
          </div>
        </div>
      `);

      document.querySelectorAll("[data-step]").forEach(btn => btn.addEventListener("click", () => {
        const [key, d] = btn.dataset.step.split(":");
        alloc[key] += Number(d);
        render();
      }));
      document.getElementById("flow-commit").addEventListener("click", commit);
    }

    function commit() {
      const log = (m) => logLines.push(Evoke.escapeHtml(m));
      s.home = Math.min(100, s.home - 6 + alloc.home * 2);
      s.market = Math.min(100, s.market - 4 + alloc.market * 2);
      s.cistern = Math.min(12, s.cistern + alloc.cistern);
      s.network = Math.min(12, s.network + alloc.network);
      log(`Cycle ${s.cycle} committed: HOME+${alloc.home * 2 - 6 >= 0 ? "" : ""}${alloc.home * 2}−6, MARKET+${alloc.market * 2}−4, banked ${alloc.cistern}, shared ${alloc.network}.`);

      if (s.cycle >= 2) {
        const ev = events.pop() || FLOW_EVENTS[Math.floor(Math.random() * FLOW_EVENTS.length)];
        log(`⚠ EVENT: ${ev.name}`);
        ev.apply(s, log);
        s.lessons.push(ev.lesson);
      }
      s.home = Math.max(0, s.home); s.market = Math.max(0, s.market);

      if (s.home <= 0 || s.market <= 0 || s.cycle >= TOTAL_CYCLES) return finish();
      s.cycle++;
      const oldLog = logLines;
      newCycle();
      logLines = oldLog;
      render();
    }

    async function finish() {
      const survived = s.home > 0 && s.market > 0;
      const score = Math.max(0, s.home + s.market + s.cistern * 2 + s.network * 3 + (survived ? 20 : 0));
      const res = await postScore("flow-control", score);
      Evoke.mount(`
        <div class="stack celebration-screen">
          <div class="card celebration-card" data-tier="${survived ? "epic" : "common"}">
            <div class="card__eyebrow">${survived ? "Simulation Complete" : "Keel Went Dark"}</div>
            <h1>Score ${score}</h1>
            <p>HOME ${s.home} · MARKET ${s.market} · reserve ${s.cistern} · goodwill ${s.network}</p>
            ${s.lessons.length ? `<div style="text-align:left;margin-top:var(--space-3)">${[...new Set(s.lessons)].map(l => `<p class="empty-state">— ${Evoke.escapeHtml(l)}</p>`).join("")}</div>` : ""}
            ${res && res.xp_granted ? `<p class="celebration-tier">+${res.xp_granted} XP</p>` : ""}
            <div class="row" style="justify-content:center">
              <button class="btn btn-primary" id="flow-again">Run It Again</button>
              <a class="btn" href="#/arcade">Back to Training</a>
            </div>
          </div>
        </div>
      `);
      document.getElementById("flow-again").addEventListener("click", () => Evoke.screens.gameFlow());
    }

    newCycle();
    render();
  };

  // ---------- SIM 02: SIGNAL DECRYPT ----------
  // GAME_DESIGN §12's vocabulary as intercepted transmissions. Definition
  // shown as intel; the term is the cipher. Wrong submissions raise TRACE;
  // three traces burn the channel.
  const VOCAB = [
    { term: "SCARCITY", intel: "Never enough for every want. The mountain's first law — every decision a tradeoff.", arc: 1 },
    { term: "BUDGET", intel: "A plan that spends tomorrow's water on purpose instead of by accident.", arc: 1 },
    { term: "TRADEOFF", intel: "What you gave up to get what you chose. There is always one.", arc: 1 },
    { term: "DIVERSIFY", intel: "Depending on one supplier is easy. Until they leave. Spread the risk.", arc: 2 },
    { term: "RESILIENCE", intel: "How hard a system can be hit and still deliver water in the morning.", arc: 2 },
    { term: "RISK", intel: "The chance the plan meets a day the plan didn't plan for.", arc: 2 },
    { term: "INCENTIVE", intel: "What the system pays people to do — watch it, and you can predict them.", arc: 3 },
    { term: "MONOPOLY", intel: "One seller, no exits. If profit comes from scarcity, scarcity grows.", arc: 3 },
    { term: "OWNERSHIP", intel: "Whose name is on the pipe decides whose rules the water follows.", arc: 3 },
    { term: "ASSET", intel: "Builds value long after it's built. Produces more than it consumes.", arc: 4 },
    { term: "LIABILITY", intel: "Consumes resources for as long as you hold it. Know which one you're buying.", arc: 4 },
    { term: "INVESTING", intel: "Paying present water for future flow. Patience with a spreadsheet.", arc: 4 },
    { term: "SAVING", intel: "Water in the cistern. Boring right up until the day it's everything.", arc: 4 },
    { term: "CAPITAL", intel: "The stored work you can put to work. Tools, funds, trust — all of it counts.", arc: 5 },
    { term: "DIVIDEND", intel: "What an asset hands back to its owners, cycle after cycle, for showing up early.", arc: 5 },
    { term: "NETWORK", intel: "One filter helps one family. Ten help a village. This helps generations.", arc: 5 },
  ];
  const DECOYS = "XZQJKVWY";

  Evoke.screens.gameDecrypt = async function gameDecrypt() {
    const deck = [...VOCAB].sort(() => Math.random() - 0.5).slice(0, 8);
    const s = { round: 0, score: 0, streak: 0, traces: 0, done: [] };
    let entry = [];

    function bank(term) {
      const letters = term.split("");
      const decoys = [...DECOYS].sort(() => Math.random() - 0.5).slice(0, 4);
      return [...letters, ...decoys].sort(() => Math.random() - 0.5);
    }
    let letterBank;

    function render() {
      const item = deck[s.round];
      Evoke.mount(`
        <div class="stack game-screen">
          <div class="row-between">
            <h1>Signal Decrypt</h1>
            <span class="chip ${s.traces >= 2 ? "" : "chip--green"}">TRACE ${s.traces}/3 · SCORE ${s.score}${s.streak > 1 ? ` · ×${s.streak}` : ""}</span>
          </div>
          <div class="card decrypt-card">
            <div class="card__eyebrow">Intercepted Broker transmission · ${s.round + 1}/${deck.length} · Arc ${item.arc}</div>
            <p class="mono-log" style="margin:var(--space-3) 0">INTEL: “${Evoke.escapeHtml(item.intel)}”</p>
            <div class="decrypt-blanks">${item.term.split("").map((ch, i) => `<span class="decrypt-blank">${entry[i] || "·"}</span>`).join("")}</div>
            <div class="decrypt-bank">
              ${letterBank.map((ch, i) => `<button class="decrypt-key" data-key="${ch}" data-i="${i}">${ch}</button>`).join("")}
              <button class="decrypt-key decrypt-key--wide" id="decrypt-back">⌫</button>
              <button class="decrypt-key decrypt-key--wide" id="decrypt-send" ${entry.length !== item.term.length ? "disabled" : ""}>TRANSMIT</button>
            </div>
            <p id="decrypt-status" class="empty-state" style="margin-top:var(--space-2)"></p>
          </div>
          <a class="btn" href="#/arcade">Abort Run</a>
        </div>
      `);
      document.querySelectorAll(".decrypt-key[data-key]").forEach(btn => btn.addEventListener("click", () => {
        if (entry.length < item.term.length) { entry.push(btn.dataset.key); render(); }
      }));
      document.getElementById("decrypt-back").addEventListener("click", () => { entry.pop(); render(); });
      document.getElementById("decrypt-send").addEventListener("click", () => {
        if (entry.join("") === item.term) {
          s.streak++;
          s.score += 100 * s.streak;
          s.done.push(item.term);
          s.round++;
          entry = [];
          if (s.round >= deck.length) return finish(true);
          letterBank = bank(deck[s.round].term);
          Evoke.toast(`DECRYPTED: ${item.term} · +${100 * s.streak}`);
          render();
        } else {
          s.traces++;
          s.streak = 0;
          entry = [];
          if (s.traces >= 3) return finish(false);
          letterBank = bank(item.term);
          render();
          document.getElementById("decrypt-status").textContent = "✗ Wrong key — trace strengthened. The intel is the answer, read it again.";
        }
      });
    }

    async function finish(clean) {
      const res = await postScore("signal-decrypt", s.score);
      Evoke.mount(`
        <div class="stack celebration-screen">
          <div class="card celebration-card" data-tier="${clean ? "epic" : "common"}">
            <div class="card__eyebrow">${clean ? "Channel Fully Decrypted" : "Trace Locked — Channel Burned"}</div>
            <h1>Score ${s.score}</h1>
            <p>${s.done.length} term${s.done.length === 1 ? "" : "s"} decrypted${s.done.length ? ": " + s.done.join(", ") : ""}</p>
            ${res && res.xp_granted ? `<p class="celebration-tier">+${res.xp_granted} XP</p>` : ""}
            <div class="row" style="justify-content:center">
              <button class="btn btn-primary" id="decrypt-again">New Intercept</button>
              <a class="btn" href="#/arcade">Back to Training</a>
            </div>
          </div>
        </div>
      `);
      document.getElementById("decrypt-again").addEventListener("click", () => Evoke.screens.gameDecrypt());
    }

    letterBank = bank(deck[0].term);
    render();
  };

  // ---------- The Alchemy channel (secret screen) ----------
  Evoke.screens.alchemy = async function alchemy() {
    const sig = await signal.load();
    if (!sig.unlocked) {
      Evoke.mount(`
        <div class="stack celebration-screen">
          <div class="card celebration-card crt">
            <div class="card__eyebrow">⬡ Anomalous Signal</div>
            <h1>NO LOCK</h1>
            <p class="mono-log">${sig.found.length} / ${sig.total} fragments triangulated.</p>
            <p class="empty-state">Five sources. Scattered where only the curious look. Keep your eyes open, Agent.</p>
            <a class="btn" href="#/">← Operations Hub</a>
          </div>
        </div>
      `);
      return;
    }
    Evoke.mount(`
      <div class="stack celebration-screen">
        <div class="card celebration-card crt" data-tier="legendary">
          <div class="card__eyebrow">⬡ Channel Open · Origin Unresolved</div>
          <h1 class="crt-flicker">SIGNAL LOCKED</h1>
          <div class="mono-log" style="text-align:left;margin:var(--space-4) 0">
            <p>&gt; FIVE SOURCES. ONE LISTENER.</p>
            <p>&gt; MOST PEOPLE STOP LOOKING. BUILDERS DON'T.</p>
            <p>&gt; THE WATER RISES BECAUSE SOMEBODY ROUTES IT.</p>
            <p>&gt; KEEP BUILDING.</p>
            <p>&gt; — A</p>
          </div>
          <p class="empty-state">Transmission ends. The channel stays open — you earned that.</p>
          <a class="btn btn-primary" href="#/">← Operations Hub</a>
        </div>
      </div>
    `);
  };
})();
