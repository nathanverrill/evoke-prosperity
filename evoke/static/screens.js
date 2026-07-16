/* screens.js — one render function per route in UI_SPEC.md's information
   architecture. Each function fetches what it needs and calls Evoke.mount().
   Honesty note: a few UI_SPEC affordances ("my team" lookup) don't have a
   backend behind them yet -- those are called out inline rather than faked,
   per CONCEPTS.md's "don't assume UI features exist server-side" warning. */

const ARC_ORDER = ["Explore", "Imagine", "Act", "Communicate"];

function missionState(mission, profile) {
  // Gating is manual admin release (GAPS.md's resolved "mission ordering"
  // item), not order-of-completion -- mission.released comes from the
  // missions.released_at column via GET /api/missions. Locked = visible
  // but silhouetted, same convention as the novel's chapter rail, never
  // hidden outright.
  if (!mission.released) return "locked";
  const completed = (profile && profile.missions_completed) || [];
  return completed.includes(mission.id) ? "complete" : "available";
}

// Backend timestamps are naive UTC (datetime.now() in a UTC container, no
// timezone suffix) -- JS would parse them as *local* time, shifting
// everything by the viewer's UTC offset (surfaced as "-1d ago" on the Ops
// Deck). Append Z unless the string already carries zone info.
function parseUtc(isoTimestamp) {
  if (!isoTimestamp) return null;
  const hasZone = /Z$|[+-]\d\d:?\d\d$/.test(isoTimestamp);
  return new Date(hasZone ? isoTimestamp : isoTimestamp + "Z");
}

function timeAgo(isoTimestamp) {
  const seconds = Math.max(0, Math.floor((Date.now() - parseUtc(isoTimestamp)) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

Evoke.screens.welcome = async function welcome() {
  const { state, mount } = Evoke;
  mount(`
    <div class="celebration-screen" style="min-height:72vh;display:flex;align-items:center;justify-content:center;text-align:center;">
      <div class="glass brackets celebration-card" style="max-width:620px;width:100%;padding:clamp(28px,4vw,44px);">
        <span class="chip chip--green" style="margin-bottom:16px;"><span class="dot"></span>System Online · ID: EVOKE</span>
        <div class="hud" style="font-size:12px;margin-bottom:8px;">Case File — Basin Region</div>
        <h1 class="glow-h anim" style="font-size:clamp(40px,7vw,72px);margin:0 0 18px;">Welcome to Keel</h1>
        <p style="color:var(--teal-100);line-height:1.6;margin:0 0 14px;">The water's scarce here. The power's unstable. But the people get by on something the mountain above them ran out of a long time ago: each other.</p>
        <p style="color:var(--teal-100);line-height:1.6;margin:0 0 24px;">You're the newest Agent assigned to this case, ${Evoke.escapeHtml(state.displayName || "Agent")}. B1llbot's expecting you — he's the one in the corner who won't stop talking about pipes.</p>
        <button class="btn" id="welcome-continue" style="min-width:280px;">Review the Records ▶</button>
      </div>
    </div>
  `);
  document.getElementById("welcome-continue").addEventListener("click", () => {
    localStorage.setItem(`evoke_onboarded_${state.userId}`, "1");
    location.hash = "#/";
  });
};

Evoke.screens.hub = async function hub() {
  const { api, state, mount } = Evoke;
  const [missionsRes, notifRes, activityRes, checkinRes, mcLink, mcConnect, world, mcStatus, companion, reflections, progressMap, dailyObjectives, achievementsRes] = await Promise.all([
    api.missions(state.userId),
    api.notifications(state.userId).catch(() => ({ notifications: [] })),
    api.activity(20).catch(() => ({ activity: [] })),
    api.checkin(state.userId).catch(() => null),
    api.minecraftLink(state.userId).catch(() => ({ linked: false })),
    api.minecraftConnectInfo().catch(() => null),
    api.worldState().catch(() => null),
    api.minecraftStatus().catch(() => null),
    api.companionInfo().catch(() => null),
    api.reflections(state.userId).catch(() => ({ filed_today: false, journal: [] })),
    api.progressMap(state.userId).catch(() => null),
    api.dailyObjectives(state.userId).catch(() => ({ objectives: [] })),
    api.achievements(state.userId).catch(() => ({ qualities: {}, powers: {} })),
  ]);
  Evoke.kit?.visit("intake");
  const missions = missionsRes.missions || [];
  const profile = state.profile;
  const completedCount = (profile && profile.missions_completed_count) || 0;
  const nextMission = missions.find(m => missionState(m, profile) === "available");
  const allDone = missions.length > 0 && missions.every(m => missionState(m, profile) === "complete");
  const pendingAwards = (notifRes.notifications || []).filter(n => !n.read);
  const activity = activityRes.activity || [];

  const byArc = {};
  ARC_ORDER.forEach(a => byArc[a] = []);
  missions.forEach(m => { if (byArc[m.arc]) byArc[m.arc].push(m); });

  const checkinLine = checkinRes
    ? (checkinRes.status === "checked_in"
        ? `✓ Checked in today (+${checkinRes.xp_granted} XP${checkinRes.minecraft_reward ? " · a reward is waiting in the Basin" : ""})`
        : "✓ Already checked in today")
    : "";

  // Second onboarding artifact from the mockup comparison (GAPS.md: "No
  // onboarding") -- a one-time orientation banner, separate from #/welcome:
  // that's a one-shot narrative beat, this is a standing "what am I looking
  // at" reference dismissed independently.
  const guideKey = `evoke_hub_guide_dismissed_${state.userId}`;
  const showGuide = !localStorage.getItem(guideKey);

  // Order of importance (BUILD_PLAN_2 §1): the learner's own next action
  // leads; the cohort world-state compresses to a one-line strip linking
  // to the Campaign Map, where the full pipeline lives now.
  const worldStrip = world ? `
    <a class="world-strip" href="#/map" title="Open the Campaign Map">
      <span class="card__eyebrow">Keel Restoration</span>
      <span class="world-strip__stage">Stage ${world.stage}: ${Evoke.escapeHtml(world.current.title)}</span>
      <span class="world-meter__track world-strip__track"><span class="world-meter__fill" style="width:${Math.round((world.stage / world.total_stages) * 100)}%"></span></span>
      <span class="empty-state">Campaign Map →</span>
    </a>
  ` : "";

  // Daily Field Report (Words of Wisdom) -- the check-in as a reflection.
  const fieldReportCard = reflections.filed_today
    ? `<section class="card" id="field-report">
         <div class="card__eyebrow">Field Report — filed today ✓</div>
         ${reflections.journal[0] && reflections.journal[0].wisdom ? `<p class="wisdom-line">“${Evoke.escapeHtml(reflections.journal[0].wisdom)}” <span class="empty-state">— B1llbot</span></p>` : `<p class="empty-state">See your Wisdom Journal on the Dossier.</p>`}
       </section>`
    : `<section class="card" id="field-report">
         <div class="card__eyebrow">Daily Field Report — what did you do today?</div>
         <form id="reflection-form" class="row">
           <input type="text" id="reflection-text" placeholder="One line. What you did, or what you're thinking about." style="flex:1" maxlength="600">
           <button type="submit" class="btn btn-primary">File It</button>
         </form>
         <p id="reflection-status" class="empty-state" style="margin-top:var(--space-2)">B1llbot answers every report with a word of wisdom — they collect in your journal.</p>
       </section>`;

  // Compact personal progress strip: my stages at a glance -> Campaign Map.
  const myMapStrip = progressMap ? `
    <a class="map-strip" href="#/map">
      ${progressMap.stages.map(s => `
        <span class="map-strip__node ${s.complete ? "is-complete" : (s.completed ? "is-partial" : "")}" title="Stage ${s.stage}: ${s.completed}/${s.total}${s.grade ? " · " + s.grade : ""}">${s.stage}</span>
      `).join("")}
      <span class="empty-state">My campaign: ${progressMap.stages_complete}/${progressMap.stages_total} stages done — what does done mean? →</span>
    </a>
  ` : "";

  // Today's Objectives -- console-player feedback: live games always greet
  // you with a short rotating checklist ("what do I do in the next 10
  // minutes"), which is also the classroom's 45-minute-period question.
  // Every mechanic behind these three already existed (Field Report,
  // Training Sims, peer feedback); this just surfaces the daily state as a
  // checklist instead of leaving each one buried on its own screen.
  const objectives = dailyObjectives.objectives || [];
  const objectivesCard = objectives.length ? `
    <section class="card" id="daily-objectives">
      <div class="card__eyebrow">Today's Objectives</div>
      <ul class="objectives-list">
        ${objectives.map(o => `
          <li class="objectives-list__item ${o.done ? "is-done" : ""}">
            <span class="objectives-list__check">${o.done ? "✓" : "○"}</span>
            ${o.done
              ? `<span class="objectives-list__label">${Evoke.escapeHtml(o.label)}</span>`
              : `<a class="objectives-list__label" data-objective-key="${o.key}" href="${o.href}">${Evoke.escapeHtml(o.label)}</a>`}
            <span class="objectives-list__xp">${Evoke.escapeHtml(o.xp_label)}</span>
          </li>
        `).join("")}
      </ul>
    </section>
  ` : "";

  const presenceCard = (() => {
    const online = mcStatus && mcStatus.server_online;
    const players = (mcStatus && mcStatus.online_players) || [];
    const linked = (mcStatus && mcStatus.linked_players) || {};
    return `
      <div class="card" id="presence-card">
        <div class="card__eyebrow"><span class="presence-dot ${online ? "is-online" : ""}"></span> In the Basin right now</div>
        ${online
          ? (players.length
              ? players.map(p => {
                  const l = linked[p];
                  return `<p>${l ? `<strong>${Evoke.escapeHtml(l.display_name)}</strong> <span class="empty-state">as ${Evoke.escapeHtml(p)}</span>` : Evoke.escapeHtml(p)}</p>`;
                }).join("")
              : `<p class="empty-state">The Basin is quiet — nobody online.</p>`)
          : `<p class="empty-state">Basin Simulation status unknown right now.</p>`}
      </div>
    `;
  })();

  const fieldKitCard = companion ? `
    <div class="card" id="fieldkit-card">
      <div class="card__eyebrow">Field Kit — your phone</div>
      <div class="fieldkit-qr"><img id="fieldkit-qr-img" src="/api/companion/qr.svg?user_id=${state.userId}" alt="QR code to the Companion Field Kit"></div>
      <p class="empty-state" id="fieldkit-qr-status">${companion.scannable
        ? "Scan to open your Field Kit — it registers your phone as you automatically (no login). Daily field reports, Basin linking, quests, and B1llbot from the field."
        : "Checking whether this device's local network address can make the QR scannable…"}</p>
    </div>
  ` : "";

  const lvl = profile ? profile.level : 1;
  const curXp = profile ? profile.xp : 0;
  const nextXp = profile ? profile.next_level_xp : null;
  const xpPct = nextXp ? Math.min(100, Math.round((curXp / nextXp) * 100)) : 100;
  const xpLine = pendingAwards.length
    ? `${pendingAwards.length} award${pendingAwards.length === 1 ? "" : "s"} waiting — collect them on your Dossier.`
    : (nextMission ? `Next up: ${Evoke.escapeHtml(nextMission.title)}. Submit evidence to start earning XP.` : "Standing by for your next mission.");

  // Weeks 1-6 (2 missions each) -> the showcase's alternating week-card timeline.
  const weekCards = [1, 2, 3, 4, 5, 6].map(w => {
    const wm = missions.filter(m => m.week === w);
    const states = wm.map(m => missionState(m, profile));
    const allComplete = wm.length > 0 && states.every(s => s === "complete");
    const released = states.some(s => s !== "locked");
    let status = "locked";
    if (allComplete) status = "done";
    else if (released) status = "available";
    return { week: w, status, mission: wm[0] };
  });

  // 4 Superpower rings from the achievements/qualities projection.
  const SUPERPOWERS = ["Empathetic Changemaker", "Systems Thinker", "Creative Visionary", "Deep Collaborator"];
  const qualities = achievementsRes.qualities || {};
  const spTiles = SUPERPOWERS.map(name => {
    const q = qualities[name] || {};
    const pct = q.earned ? 100 : (q.pct != null ? q.pct : (q.progress != null ? q.progress : 0));
    return { name, earned: !!q.earned, pct };
  });
  const spEarned = spTiles.filter(t => t.earned).length;

  const greetTitle = allDone ? "All missions complete!" : (nextMission ? "Ready for your next mission?" : "Standing by");
  const greetSub = allDone ? "Outstanding work, Agent." : (nextMission ? "Let's get started!" : "Waiting on your instructor to release the next mission.");

  const weekCardHtml = (c, i) => {
    const right = i % 2 === 1;
    const locked = c.status === "locked";
    const done = c.status === "done";
    const numColor = locked ? "var(--text-locked)" : (done ? "var(--green-400)" : "var(--cyan-300)");
    const icon = done ? "check_circle" : (locked ? "lock" : "rocket_launch");
    const label = done ? "Complete" : (locked ? "Locked" : "▶ Begin");
    const labelColor = locked ? "var(--text-locked)" : (done ? "var(--green-400)" : "var(--cyan-300)");
    const bg = (locked || done) ? "background:rgba(15,23,43,0.4);box-shadow:inset 0 0 0 1px rgba(145,209,209,0.15);" : "background:var(--surface-glass);box-shadow:var(--elev-glass);";
    const link = (!locked && c.mission) ? `onclick="location.hash='#/mission/${c.mission.id}'"` : "";
    return `
      <div style="display:flex;justify-content:${right ? "flex-end" : "flex-start"};margin-bottom:28px;">
        <button class="tl-card" ${locked ? 'disabled aria-disabled="true"' : link} style="text-align:${right ? "right" : "left"};color:var(--text-heading);cursor:${locked ? "not-allowed" : "pointer"};${bg}" aria-label="Week ${c.week}, ${label.replace("▶ ", "")}">
          <span class="ms tl-ic ${done ? "complete" : (locked ? "locked" : "current")}" aria-hidden="true" style="${right ? "left" : "right"}:20px;">${icon}</span>
          <span class="hud" style="position:relative;z-index:1;font-size:11px;color:var(--text-faint);display:block;${right ? "text-align:right;" : ""}">Week</span>
          <span aria-hidden="true" style="position:relative;z-index:1;display:block;font-family:var(--font-display);font-weight:800;font-size:50px;line-height:1;color:${numColor};${!locked && !done ? "text-shadow:0 0 24px rgba(0,150,136,0.22);" : ""}">${c.week}</span>
          <span style="position:absolute;z-index:1;bottom:14px;left:22px;right:20px;display:flex;align-items:center;justify-content:space-between;gap:8px;">
            <span style="font-family:var(--font-mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:${labelColor};">${label}</span>
            <span style="display:flex;align-items:center;gap:6px;"><span aria-hidden="true" style="width:8px;height:8px;border-radius:50%;background:rgba(145,209,209,0.22);"></span><span aria-hidden="true" style="width:8px;height:8px;border-radius:50%;background:rgba(145,209,209,0.22);"></span></span>
          </span>
        </button>
      </div>`;
  };

  mount(`
    <div class="home-body">
      <div class="home-fx" aria-hidden="true"></div>
      <main class="home-main" id="main" tabindex="-1">
        <div class="home-hero anim">
          <div class="hero-bg" style="background-image:url('img/home-hero-bg.jpg')"></div>
          <div class="hero-tint"></div>
          <img class="hero-char" src="img/home-hero-char.png" alt="" aria-hidden="true">
          <div class="hero-text">
            <p class="hud" style="font-size:13px;margin:0 0 6px;">Hello, ${Evoke.escapeHtml((state.displayName || "Agent").split(" ")[0])}</p>
            <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(26px,4vw,44px);text-transform:uppercase;color:var(--text-heading);margin:0;line-height:1.05;">${greetTitle}</h1>
            <p style="font-size:16px;color:var(--teal-050);margin:8px 0 0;">${greetSub}</p>
          </div>
        </div>
        <div id="timeline" aria-label="Mission timeline">
          ${weekCards.map(weekCardHtml).join("")}
        </div>
      </main>

      <aside class="home-aside">
        <div class="glass billbot-card" style="padding:18px 20px;">
          <img src="img/billbot-avatar.png" alt="B1llbot">
          <div>
            <p class="hud" style="font-size:12px;margin:0 0 5px;color:var(--cyan-300);font-weight:700;letter-spacing:.14em;">B1llbot</p>
            <p id="home-xp-line" style="font-size:14px;margin:0;color:var(--text-muted);line-height:1.45;">${xpLine}</p>
          </div>
        </div>

        <div class="glass" style="padding:24px;">
          <h2 class="hud" style="font-size:12px;margin:0 0 14px;">XP Progress</h2>
          <div class="track" role="progressbar" aria-valuenow="${curXp}" aria-valuemin="0" aria-valuemax="${nextXp || curXp}"><div class="fill-xp" style="width:${xpPct}%"></div><div class="knob" style="left:${xpPct}%"></div></div>
          <div style="display:flex;justify-content:space-between;margin-top:12px;font-family:var(--font-mono);font-size:12px;">
            <span style="color:var(--text-label);">${curXp} XP</span>
            <span style="color:var(--text-faint);">${nextXp ? `${nextXp} XP to Lv.${lvl + 1}` : "MAX"}</span>
          </div>
        </div>

        <div class="glass" style="padding:24px;">
          <h2 class="hud" style="font-size:12px;margin:0 0 14px;">Weekly Streak</h2>
          <div class="days" id="streak" role="img" aria-label="Weekly streak">
            ${["M", "T", "W", "TH", "F", "S", "SU"].map(d => `<div class="day">${d}</div>`).join("")}
          </div>
        </div>

        <div class="glass" style="padding:24px;">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
            <h2 class="hud" style="font-size:12px;margin:0;">Superpowers</h2>
            <span class="hud" style="font-size:11px;color:var(--text-muted);">${spEarned} of 4</span>
          </div>
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px 2px;justify-items:center;" id="badges">
            ${spTiles.map(t => `
              <div class="sp-tile ${t.earned ? "" : "locked"}" role="img" aria-label="${Evoke.escapeHtml(t.name)}, ${t.earned ? "earned" : "locked"}">
                <div class="sp-ring">
                  <svg viewBox="0 0 64 64" aria-hidden="true"><circle class="bg" cx="32" cy="32" r="28"></circle><circle class="fg" cx="32" cy="32" r="28" stroke-dasharray="175.9" stroke-dashoffset="${(175.9 * (1 - t.pct / 100)).toFixed(1)}"></circle></svg>
                  <span class="ic"><span class="ms" aria-hidden="true">${t.earned ? "check" : "lock"}</span></span>
                </div>
                <div class="lbl">${Evoke.escapeHtml(t.name)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      </aside>

      <div class="buddy buddy-pop" id="buddy" aria-live="polite">
        <button class="buddy-face" id="buddy-face" aria-label="Talk to B1llbot"><img src="img/billbot-avatar.png" alt=""></button>
        <div class="buddy-bubble">
          <button class="buddy-close" id="buddy-close" aria-label="Hide B1llbot's tip"><span class="ms" aria-hidden="true" style="font-size:14px;">close</span></button>
          <div class="buddy-name">B1llbot</div>
          <p id="buddy-text">Welcome back, Agent! Pick a week and let's get to work.</p>
        </div>
      </div>
    </div>
  `);

  document.getElementById("buddy-face")?.addEventListener("click", () => { location.hash = "#/billbot"; });
  document.getElementById("buddy-close")?.addEventListener("click", () => { document.getElementById("buddy")?.classList.add("hidden-bubble"); });

  document.getElementById("reflection-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const textEl = document.getElementById("reflection-text");
    const statusEl = document.getElementById("reflection-status");
    const text = textEl.value.trim();
    if (!text) return;
    statusEl.textContent = "Filing… B1llbot is thinking (can take ~20s).";
    try {
      const res = await api.postReflection(state.userId, text);
      document.getElementById("field-report").innerHTML = `
        <div class="card__eyebrow">Field Report — filed ✓</div>
        <p class="wisdom-line">“${Evoke.escapeHtml(res.wisdom)}” <span class="empty-state">— B1llbot</span></p>
      `;
    } catch (err) {
      statusEl.textContent = "Couldn't file that just now — try again in a moment.";
    }
  });

  document.querySelectorAll("#mc-connect-card [data-copy]").forEach(btn => {
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(btn.dataset.copy).then(() => {
        const original = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = original; }, 1500);
      }).catch(() => { alert(btn.dataset.copy); });
    });
  });

  document.getElementById("hub-guide-dismiss")?.addEventListener("click", () => {
    localStorage.setItem(guideKey, "1");
    document.getElementById("hub-guide").remove();
  });

  // If the server's own guess isn't scannable (we're on localhost), see if
  // the browser can do better -- it can discover its own LAN IP via WebRTC
  // even when the address bar says "localhost" (see app.js's
  // detectLocalIP). Best-effort: silently keeps the original guidance if
  // the browser can't or won't expose an IP.
  if (companion && !companion.scannable) {
    Evoke.detectLocalIP().then(async (ip) => {
      if (!ip) return;
      try {
        const better = await api.companionInfo(ip);
        if (!better.scannable) return;
        const img = document.getElementById("fieldkit-qr-img");
        const status = document.getElementById("fieldkit-qr-status");
        if (img) img.src = `/api/companion/qr.svg?user_id=${state.userId}&hint_host=${encodeURIComponent(ip)}`;
        if (status) status.textContent = "Scan to open your Field Kit — it registers your phone as you automatically (no login). Daily field reports, Basin linking, quests, and B1llbot from the field.";
      } catch (e) { /* keep the original localhost guidance */ }
    });
  }

  // The Field Report objective is already on this same page -- scroll to
  // it instead of a real navigation (its href is "#/" as a harmless
  // fallback for no-JS, but following it as a hash change would re-run the
  // router and clobber the page mid-scroll).
  document.querySelector('[data-objective-key="field_report"]')?.addEventListener("click", (e) => {
    e.preventDefault();
    document.getElementById("field-report")?.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  // Live refresh: the Hub is an ops center, so it re-renders itself when
  // something it displays changes (feed entries, world stage, presence).
  // Throttled -- bursts of events (one submission fires several) collapse
  // into one refresh; the checkin call inside is dedupe-safe server-side.
  let refreshQueued = false;
  state.onLive = (msg) => {
    if (!["ActivityPosted", "WorldStateAdvanced", "MinecraftPresence", "MissionCompleted", "AwardGranted"].includes(msg.type)) return;
    if (refreshQueued) return;
    refreshQueued = true;
    setTimeout(() => {
      refreshQueued = false;
      if ((location.hash || "#/") === "#/") Evoke.screens.hub();
    }, 1500);
  };
};

Evoke.screens.novel = async function novel() {
  const { mount, state, api } = Evoke;
  Evoke.kit?.visit("sand");
  let chapters;
  try {
    chapters = await fetch("content/novel-pages.json").then(r => r.json());
  } catch (e) {
    mount(`<div class="glass" style="padding:clamp(28px,4vw,40px);text-align:center;"><p class="empty-state" style="margin:0;">No graphic novel content configured yet.</p></div>`);
    return;
  }
  await api.missions(state.userId).catch(() => ({ missions: [] }));
  const completedCount = (state.profile && state.profile.missions_completed_count) || 0;
  // Chapter N unlocks once 2*(N-1) missions are done (2 missions/chapter).
  chapters.forEach((c, i) => { c.locked = completedCount < i * 2; });

  let ci = chapters.map(c => !c.locked).lastIndexOf(true);
  if (ci < 0) ci = 0;
  let si = 0; // spread index within the chapter
  const spreadsIn = i => Math.ceil(chapters[i].pages.length / 2);

  function render() {
    const ch = chapters[ci];
    const pages = ch.pages, spreads = spreadsIn(ci);
    const li = si * 2, ri = si * 2 + 1;
    const left = pages[li], right = pages[ri];
    const atFirst = ci === 0 && si === 0;
    const nextCh = chapters[ci + 1];
    const canNext = si < spreads - 1 || (nextCh && !nextCh.locked);
    Evoke.mount(`
      <main style="max-width:1200px;margin:0 auto;width:100%;display:flex;flex-direction:column;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
          <h1 class="hud" style="font-size:13px;margin:0;">${Evoke.escapeHtml(ch.chapter)}</h1>
          <span class="hud" style="font-size:11px;color:var(--text-faint);display:flex;align-items:center;gap:6px;"><span class="ms" aria-hidden="true" style="font-size:16px;">zoom_in</span>Tap the page to enlarge</span>
        </div>
        <div class="nv-book anim ${right ? "" : "single"}">
          <button class="nv-page" data-page="${li}" type="button" aria-label="Enlarge page ${li + 1}"><img src="${left}" alt="Comic page ${li + 1}"></button>
          <button class="nv-page ${right ? "" : "empty"}" ${right ? `data-page="${ri}"` : "disabled"} type="button" aria-label="Enlarge page ${ri + 1}">${right ? `<img src="${right}" alt="Comic page ${ri + 1}">` : ""}</button>
          <span class="nv-spine" aria-hidden="true"></span>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;margin-top:24px;">
          <button class="btn sec" id="nv-back" ${atFirst ? "disabled" : ""}>◀ Back</button>
          <div style="display:flex;align-items:center;gap:14px;">
            <span class="hud" style="font-size:12px;color:var(--text-faint);">Spread ${si + 1} of ${spreads}</span>
            <div style="display:flex;gap:7px;" aria-hidden="true">${Array.from({ length: spreads }).map((_, k) => `<span style="width:8px;height:8px;border-radius:50%;background:${k === si ? "var(--cyan-300)" : "rgba(145,209,209,0.25)"};${k === si ? "box-shadow:0 0 8px var(--cyan-300);" : ""}"></span>`).join("")}</div>
          </div>
          <button class="btn" id="nv-next" ${canNext ? "" : "disabled"}>Next ▶</button>
        </div>
      </main>
    `);
    document.getElementById("nv-back")?.addEventListener("click", () => {
      if (si > 0) si--; else if (ci > 0) { ci--; si = spreadsIn(ci) - 1; }
      render();
    });
    document.getElementById("nv-next")?.addEventListener("click", () => {
      if (si < spreads - 1) si++; else if (nextCh && !nextCh.locked) { ci++; si = 0; }
      render();
    });
    document.querySelectorAll(".nv-page[data-page]").forEach(btn => btn.addEventListener("click", () => openZoom(Number(btn.dataset.page))));
  }

  // Full-screen zoom reader — the original design lets students click a page
  // to enlarge it; prev/next and Esc/arrows page through the chapter.
  function openZoom(startIdx) {
    const pages = chapters[ci].pages;
    let zi = startIdx;
    const overlay = document.createElement("div");
    overlay.style.cssText = "position:fixed;inset:0;z-index:200;background:rgba(4,16,34,0.93);display:flex;align-items:center;justify-content:center;padding:24px;";
    const iconBtn = (cls, icon, disabled, pos) => `<button class="${cls}" ${disabled ? "disabled" : ""} style="position:absolute;${pos};width:50px;height:50px;border-radius:50%;border:none;cursor:pointer;background:rgba(0,150,136,0.15);color:var(--cyan-100);box-shadow:inset 0 0 0 1px var(--border-ui);display:flex;align-items:center;justify-content:center;${disabled ? "opacity:0.4;cursor:default;" : ""}"><span class="ms">${icon}</span></button>`;
    const draw = () => {
      overlay.innerHTML = `
        ${iconBtn("z-close", "close", false, "top:20px;right:24px")}
        ${iconBtn("z-prev", "chevron_left", zi === 0, "left:24px;top:50%;transform:translateY(-50%)")}
        <img src="${pages[zi]}" alt="Comic page ${zi + 1}" style="max-width:min(92vw,920px);max-height:88vh;object-fit:contain;border-radius:8px;box-shadow:0 30px 80px -20px rgba(0,0,0,0.8);">
        ${iconBtn("z-next", "chevron_right", zi === pages.length - 1, "right:24px;top:50%;transform:translateY(-50%)")}
        <span class="hud" style="position:absolute;bottom:22px;left:50%;transform:translateX(-50%);font-size:12px;color:var(--text-faint);">Page ${zi + 1} of ${pages.length}</span>`;
      overlay.querySelector(".z-close").onclick = close;
      overlay.querySelector(".z-prev").onclick = e => { e.stopPropagation(); if (zi > 0) { zi--; draw(); } };
      overlay.querySelector(".z-next").onclick = e => { e.stopPropagation(); if (zi < pages.length - 1) { zi++; draw(); } };
    };
    const onKey = e => { if (e.key === "Escape") close(); else if (e.key === "ArrowLeft" && zi > 0) { zi--; draw(); } else if (e.key === "ArrowRight" && zi < pages.length - 1) { zi++; draw(); } };
    function close() { overlay.remove(); document.removeEventListener("keydown", onKey); }
    overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
    document.addEventListener("keydown", onKey);
    draw();
    document.body.appendChild(overlay);
  }

  render();
};

// Light structure for the "Evoke Mission (direct to students)" narrative
// text (Prosperity Campaign Missions docx): "Step N: <title>" as the first
// line of a paragraph block renders bold; "- " lines within a block become
// a real bullet list. Not full markdown -- just enough to make the actual
// mission content (previously never shown at all, only a one-line summary)
// readable instead of a wall of escaped text.
function formatMissionNarrative(text) {
  return text.split(/\n\n+/).map(block => {
    const lines = block.split("\n");
    let html = "";
    let bullets = [];
    const flush = () => {
      if (bullets.length) {
        html += `<ul>${bullets.map(b => `<li>${Evoke.escapeHtml(b)}</li>`).join("")}</ul>`;
        bullets = [];
      }
    };
    lines.forEach((line, i) => {
      if (/^-\s+/.test(line)) {
        bullets.push(line.replace(/^-\s+/, ""));
        return;
      }
      flush();
      if (!line.trim()) return;
      const isStepHeader = i === 0 && /^Step \d+/.test(line);
      html += isStepHeader
        ? `<p><strong>${Evoke.escapeHtml(line)}</strong></p>`
        : `<p>${Evoke.escapeHtml(line)}</p>`;
    });
    flush();
    return html;
  }).join("");
}

Evoke.screens.missionBrief = async function missionBrief(missionId) {
  const { api, state, mount } = Evoke;
  const [missionsRes, timeline, mcLink, aarProfile, aarAchievements, mySubmission] = await Promise.all([
    api.missions(state.userId),
    api.timeline(state.userId, missionId).catch(() => null),
    api.minecraftLink(state.userId).catch(() => ({ linked: false })),
    api.playerProfile(state.userId).catch(() => null),
    api.achievements(state.userId).catch(() => null),
    api.submission(state.userId, missionId).catch(() => ({ submitted: false })),
  ]);
  // Snapshot XP/level/achievements *before* any submission on this page, so
  // a fresh completion can render an itemized after-action report (count up
  // XP, flag a level-up, reveal newly-unlocked Powers/badges) instead of a
  // single static card. Consumed by missionDebrief's fresh branch below;
  // cleared there once used so a stale snapshot can't attach to a later,
  // unrelated mission.
  if (aarProfile && aarAchievements) {
    state.aarBefore = { missionId, xp: aarProfile.xp, level: aarProfile.level, nextLevelXp: aarProfile.next_level_xp, achievements: aarAchievements };
  }
  const mission = (missionsRes.missions || []).find(m => m.id === missionId);
  if (!mission) { mount(`<div class="card"><p>Mission not found.</p></div>`); return; }

  if (!mission.released) {
    mount(`
      <div style="display:flex;flex-direction:column;gap:24px;max-width:1040px;margin:0 auto;">
        <div style="display:flex;justify-content:center;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">lock</span>${Evoke.escapeHtml(mission.arc)} · Week ${mission.week}</span></div>
        <div class="glass brackets" style="padding:clamp(24px,3.5vw,36px);text-align:center;">
          <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(26px,5vw,44px);text-transform:uppercase;color:var(--text-locked);margin:0 0 12px;line-height:1;">🔒 ${Evoke.escapeHtml(mission.title)}</h1>
          <p class="empty-state" style="margin:0;">This mission hasn't been released yet. Check back once your instructor opens it.</p>
        </div>
        <a class="btn sec" href="#/">◀ Back to Operations Hub</a>
      </div>
    `);
    return;
  }

  mount(`
    <div style="display:flex;flex-direction:column;gap:24px;max-width:1040px;margin:0 auto;">
      <div style="display:flex;justify-content:center;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">assignment</span>${Evoke.escapeHtml(mission.arc)} · Week ${mission.week}</span></div>

      <div class="glass brackets" style="padding:clamp(24px,3.5vw,36px);">
        <div class="hud" style="font-size:13px;margin-bottom:8px;">Builds toward: ${Evoke.escapeHtml(mission.superpower || "—")}</div>
        <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(28px,5vw,48px);text-transform:uppercase;color:var(--cyan-500);text-shadow:0 0 24px rgba(0,150,136,0.3);margin:0 0 18px;line-height:1;">${Evoke.escapeHtml(mission.title)}</h1>
        <div>
          <div class="hud" style="font-size:10px;margin-bottom:5px;">Objective</div>
          <div style="font-family:var(--font-body);font-size:15px;color:var(--teal-050);line-height:1.5;">${Evoke.escapeHtml(mission.brief || "No brief text yet.").replace(/\n/g, "<br>")}</div>
        </div>
      </div>

      ${timeline ? `
        <div class="panel" style="padding:22px clamp(18px,3vw,26px);">
          <h2 class="hud" style="font-size:12px;margin:0 0 16px;color:var(--cyan-300);">Timeline</h2>
          <div class="timeline-strip">
            ${(timeline.timeline || []).map(step => `
              <div class="timeline-step is-${step.status}">
                <div class="timeline-step__label">${Evoke.escapeHtml(step.label)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}

      ${mission.pbl_description ? `
        <div class="panel" style="padding:clamp(22px,3.5vw,32px);">
          <h2 class="hud" style="font-size:12px;margin:0 0 16px;color:var(--cyan-300);">Your Briefing</h2>
          <div class="mission-narrative">${formatMissionNarrative(mission.pbl_description)}</div>
        </div>
      ` : ""}

      ${mission.evidence_requirements ? `
        <div>
          <h2 class="hud" style="font-size:12px;margin:0 0 16px;color:var(--cyan-300);">Field Objectives — what your team must submit</h2>
          <div class="panel" style="padding:8px clamp(18px,3vw,26px) 18px;">
            <ul class="evidence-checklist">
              ${mission.evidence_requirements.split("\n").filter(l => l.trim().startsWith("-")).map(l =>
                `<li>${Evoke.escapeHtml(l.replace(/^-\s*/, "").trim())}</li>`
              ).join("")}
            </ul>
          </div>
        </div>
      ` : ""}

      ${mission.quest && mcLink.linked ? `
        <div class="panel" style="padding:clamp(20px,3vw,26px);">
          <div class="hud" style="font-size:11px;margin-bottom:8px;color:var(--cyan-300);">Optional — Basin Simulation</div>
          <strong style="color:var(--text-heading);">${Evoke.escapeHtml(mission.quest.title)}</strong>
          <p style="margin:6px 0 0;color:var(--teal-100);">${Evoke.escapeHtml(mission.quest.description || "")}</p>
        </div>
      ` : (mission.quest ? `
        <div class="panel" style="padding:clamp(20px,3vw,26px);">
          <div class="hud" style="font-size:11px;margin-bottom:8px;color:var(--cyan-300);">Basin telemetry offline</div>
          <p class="empty-state" style="margin:0;">This mission has an optional Basin Simulation quest — connect Minecraft from your Field Kit to reveal it. <a href="#/faq" style="color:var(--cyan-300);">How? →</a></p>
        </div>
      ` : "")}

      <div class="panel" style="position:relative;overflow:hidden;padding:clamp(24px,3.5vw,38px);display:flex;gap:28px;align-items:stretch;flex-wrap:wrap;">
        <div style="flex:1;min-width:280px;">
          <div style="display:flex;align-items:center;gap:18px;margin-bottom:14px;">
            <span style="width:60px;height:60px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;background:radial-gradient(circle at 50% 35%,rgba(0,212,146,0.4),rgba(0,150,136,0.08));box-shadow:inset 0 0 0 1.5px var(--border-ui);">
              <span class="ms" aria-hidden="true" style="font-size:30px;color:var(--green-400);">military_tech</span>
            </span>
            <div>
              <h2 style="font-family:var(--font-display);font-weight:800;font-size:clamp(24px,3.4vw,34px);text-transform:uppercase;color:var(--text-heading);margin:0;line-height:1;">Mission Accepted</h2>
              <p class="hud" style="font-size:13px;margin:7px 0 0;color:var(--green-400);">You have your assignment.</p>
            </div>
          </div>
          <p style="font-family:var(--font-body);font-size:16px;line-height:1.6;color:var(--teal-100);margin:0 0 18px;max-width:520px;">Investigate the challenge in the real world, gather your evidence, and submit it here when you're ready.</p>
          <div style="display:flex;gap:12px;align-items:flex-start;padding:16px 18px;border-radius:12px;background:rgba(0,150,136,0.06);box-shadow:inset 0 0 0 1px var(--border-ui);max-width:520px;">
            <span class="ms" aria-hidden="true" style="font-size:22px;color:var(--cyan-300);flex:none;">event</span>
            <span style="font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--teal-050);"><strong style="color:var(--cyan-100);font-weight:700;">Head to the field.</strong> Do the work, then bring back your team's evidence and your own reflection below.</span>
          </div>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px;">
            <span class="chip orange"><span class="ms" aria-hidden="true" style="font-size:16px;">bolt</span>+100 XP</span>
            <span class="chip teal"><span class="ms" aria-hidden="true" style="font-size:16px;">military_tech</span>${Evoke.escapeHtml(mission.superpower || "Superpower")}</span>
          </div>
        </div>
        <div style="flex:0 0 clamp(220px,24vw,290px);display:flex;flex-direction:column;gap:12px;padding-left:clamp(0px,2vw,20px);border-left:1px solid var(--border-faint);">
          <div style="display:flex;align-items:center;gap:10px;"><span class="hud" style="font-size:12px;color:var(--cyan-300);">Transmission from Alex</span><span class="tx-pulse" aria-hidden="true"></span></div>
          <p style="font-family:var(--font-body);font-size:14px;line-height:1.6;color:var(--teal-100);margin:0;">The reports only tell part of the story. To understand what happened in Keel, you'll need to talk to the people who lived it.</p>
          <p style="font-family:var(--font-body);font-size:14px;line-height:1.6;color:var(--cyan-200);margin:0;font-style:italic;">Some truths only become visible when you're standing inside the system.</p>
        </div>
      </div>

      ${(() => {
        // Team-evidence + individual-reflection model: the file is one
        // shared artifact any team member can submit; the reflection is
        // always personal, and is what actually closes YOUR OWN completion
        // gate (see main.py's _complete_mission_for_user). Revise-and-
        // resubmit is a visible, welcomed path on both sides (GAPS.md #3)
        // -- a prior submission changes the framing, never blocks.
        const teamHasSubmitted = timeline && (timeline.timeline || []).some(s => s.id === "submitted" && s.status === "completed");
        const iHaveReflected = !!mySubmission.submitted;
        return `
      <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
        <span class="ev-label">${teamHasSubmitted ? "Team Evidence — submitted ✓" : "Team Evidence"}</span>
        <p style="margin:0 0 16px;color:var(--teal-100);font-size:14px;line-height:1.5;">One shared file for your whole team — any member can submit or improve it.${teamHasSubmitted ? " Your team has already submitted; a stronger resubmission can upgrade everyone's award tier — nothing earned is taken back." : ""}</p>
        <form class="evidence-form" id="evidence-form">
          <label class="ev-drop" for="ev-file" id="ev-drop">
            <span class="ms" aria-hidden="true">cloud_upload</span>
            <span class="ev-drop-title">Drop your evidence file here</span>
            <span class="ev-drop-sub" id="ev-filename">or <span class="ev-browse">browse your files</span></span>
          </label>
          <input type="file" name="file" id="ev-file" required style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;">
          <button type="submit" class="btn ev-submit">${teamHasSubmitted ? "Resubmit Team Evidence" : "Submit Team Evidence"}</button>
        </form>
        <p id="evidence-status" class="empty-state" style="margin-top:12px;"></p>
      </div>

      <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
        <span class="ev-label">${iHaveReflected ? "Your Reflection — submitted ✓" : "Your Reflection"}</span>
        <p style="margin:0 0 14px;color:var(--teal-100);font-size:14px;line-height:1.5;">${mission.superpower ? `What did this mission teach you about being a ${Evoke.escapeHtml(mission.superpower)}?` : "Your own take on this mission."} Required to receive your own award and XP — separate from your team's evidence.</p>
        <form id="reflection-form">
          <textarea class="ev-textarea" id="my-reflection" rows="3" placeholder="Your own reflection...">${mySubmission.reflection ? Evoke.escapeHtml(mySubmission.reflection) : ""}</textarea>
          <button type="submit" class="btn ev-submit">${iHaveReflected ? "Update Your Reflection" : "Submit Your Reflection"}</button>
        </form>
        <p id="reflection-status" class="empty-state" style="margin-top:8px;"></p>
      </div>`;
      })()}

      <div style="display:flex;align-items:center;justify-content:flex-start;gap:14px;flex-wrap:wrap;">
        <a class="btn sec" href="#/">◀ Back to Operations Hub</a>
      </div>
    </div>
  `);

  const teamHasSubmitted = timeline && (timeline.timeline || []).some(s => s.id === "submitted" && s.status === "completed");
  const iHaveReflected = !!mySubmission.submitted;

  document.getElementById("evidence-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("evidence-status");
    const fileInput = e.target.querySelector("input[type=file]");
    if (!fileInput.files[0]) return;
    const formData = new FormData();
    formData.append("user_id", state.userId);
    formData.append("mission_id", missionId);
    formData.append("file", fileInput.files[0]);
    statusEl.textContent = "Submitting...";
    try {
      const res = await api.submitEvidence(formData);
      if (res.resubmission) {
        // No fresh-completion celebration for a resubmission -- toast the
        // upgrade path and land on the normal debrief instead.
        Evoke.toast("Team evidence resubmitted — the AI Coach is re-reviewing. Improvements can upgrade everyone's award tier.");
        statusEl.textContent = "Resubmitted!";
        setTimeout(() => { location.hash = `#/mission/${missionId}/debrief`; }, 800);
      } else {
        statusEl.textContent = "Submitted!";
        // This only closes YOUR OWN gate if you'd already reflected before
        // the team's evidence landed -- otherwise nothing completed for
        // you yet, so no fresh-AAR celebration.
        const fresh = iHaveReflected ? "?fresh=1" : "";
        setTimeout(() => { location.hash = `#/mission/${missionId}/debrief${fresh}`; }, 800);
      }
    } catch (err) {
      statusEl.textContent = "Submission failed: " + err.message;
    }
  });

  // Reflect the chosen file in the styled drop-zone (the real <input> is
  // visually hidden behind the .ev-drop label).
  document.getElementById("ev-file")?.addEventListener("change", (e) => {
    const f = e.target.files[0];
    const nameEl = document.getElementById("ev-filename");
    if (nameEl) nameEl.innerHTML = f ? Evoke.escapeHtml(f.name) : `or <span class="ev-browse">browse your files</span>`;
    document.getElementById("ev-drop")?.classList.toggle("drag", !!f);
  });

  document.getElementById("reflection-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("reflection-status");
    const textEl = document.getElementById("my-reflection");
    if (!textEl.value.trim()) return;
    statusEl.textContent = "Saving...";
    try {
      await api.submitReflection(state.userId, missionId, textEl.value.trim());
      statusEl.textContent = "Saved!";
      // Only closes YOUR gate if the team's evidence already existed --
      // otherwise this is just recording your reflection ahead of time.
      const fresh = teamHasSubmitted ? "?fresh=1" : "";
      setTimeout(() => { location.hash = `#/mission/${missionId}/debrief${fresh}`; }, 800);
    } catch (err) {
      statusEl.textContent = "Couldn't save: " + err.message;
    }
  });
};

// After-action report: the fresh-completion celebration, sequenced as an
// itemized reveal (mission complete -> award -> XP count-up -> level-up ->
// new Power/badge unlocks) rather than one static card. Console games do
// this on every match end; console-player feedback flagged the old static
// card as the single biggest "feels like a document" gap in the loop.
// The XP grant on submission is a fixed, known amount (main.py's
// mission_completed XPGranted is always +100), so the count-up and bar
// animate immediately off the "before" snapshot missionBrief captured --
// no waiting on the event pipeline for that part. Level-up and Power/badge
// unlocks depend on the async worker actually processing the events this
// submission published, so those beats wait on one settle fetch instead.
// Live canvas confetti for celebratory moments. Self-contained, brand-colored,
// fades out and removes its own canvas; a no-op under prefers-reduced-motion.
Evoke.confetti = function confetti(opts = {}) {
  try {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const duration = opts.duration || 2800;
    const colors = opts.colors || ["#00a596", "#26c0b0", "#ff6b35", "#00d492", "#89e0d3", "#e8a33a"];
    const canvas = document.createElement("canvas");
    canvas.setAttribute("aria-hidden", "true");
    canvas.style.cssText = "position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:200;";
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = () => window.innerWidth, h = () => window.innerHeight;
    const resize = () => { canvas.width = w() * dpr; canvas.height = h() * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
    resize();
    window.addEventListener("resize", resize);
    const N = opts.count || 170;
    const parts = Array.from({ length: N }, () => ({
      x: Math.random() * w(),
      y: (Math.random() * h() * 0.75) - h() * 0.7, // spread from just above the fold into view — visible from frame 1
      w: 6 + Math.random() * 6, h: 8 + Math.random() * 8,
      vx: (Math.random() - 0.5) * 1.6, vy: 2.4 + Math.random() * 3.6,
      rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.3,
      color: colors[(Math.random() * colors.length) | 0], sway: Math.random() * Math.PI * 2,
    }));
    const start = performance.now();
    const frame = (now) => {
      const elapsed = now - start;
      ctx.clearRect(0, 0, w(), h());
      const fade = elapsed > duration - 700 ? Math.max(0, (duration - elapsed) / 700) : 1;
      for (const p of parts) {
        p.sway += 0.05; p.x += p.vx + Math.sin(p.sway) * 0.9; p.y += p.vy; p.rot += p.vr;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.globalAlpha = fade; ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      }
      if (elapsed < duration) requestAnimationFrame(frame);
      else { window.removeEventListener("resize", resize); canvas.remove(); }
    };
    requestAnimationFrame(frame);
  } catch (e) { /* confetti is decorative -- never let it break a screen */ }
};

async function renderMissionAAR(mission, freshAward, missionId, targetUserIdParam) {
  const { api, state, mount, escapeHtml } = Evoke;
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const reveal = (id) => document.getElementById(id)?.classList.add("is-visible");

  const before = state.aarBefore && state.aarBefore.missionId === missionId ? state.aarBefore : null;
  state.aarBefore = null; // one-shot -- don't let it attach to a later mission

  // No "before" snapshot (e.g. this URL was opened directly/reloaded) --
  // fall back to the original single static card rather than guessing.
  if (!before) {
    mount(`
      <div class="celebration-screen" style="min-height:68vh;display:flex;align-items:center;justify-content:center;text-align:center;">
        <div class="glass celebration-card" data-tier="${freshAward ? freshAward.tier : "common"}" style="max-width:640px;width:100%;padding:clamp(28px,4vw,44px);">
          <h1 class="glow-h anim" style="font-size:clamp(38px,7vw,72px);margin:0 0 10px;">Mission Complete!</h1>
          <p class="hud" style="font-size:14px;margin:0 0 8px;">${escapeHtml(mission.title)}</p>
          <p style="color:var(--teal-100);margin:0 0 18px;">Logged. Every drop counts — even the small ones.</p>
          ${freshAward ? `<div style="margin-bottom:6px;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">auto_awesome</span>Rewards Unlocked</span></div><p class="celebration-tier" style="margin:14px 0 0;">Award: <span class="award" data-tier="${freshAward.tier}" style="display:inline-flex"><span class="award__tier">${freshAward.tier}</span></span></p>` : ""}
          <button class="btn aar-beat is-visible" id="celebration-continue" style="margin-top:28px;min-width:280px;">See Full Debrief ▶</button>
        </div>
      </div>
    `);
    Evoke.confetti();
    document.getElementById("celebration-continue").addEventListener("click", () => {
      history.replaceState(null, "", location.pathname + `#/mission/${missionId}/debrief`);
      Evoke.screens.missionDebrief(missionId, targetUserIdParam);
    });
    return;
  }

  // Kicked off now, awaited later -- gives the worker the full length of
  // the earlier beats to actually process the XP/badge events.
  const settleFetch = Promise.all([
    api.playerProfile(state.userId).catch(() => null),
    api.achievements(state.userId).catch(() => null),
  ]);

  const guessXp = before.xp + 100;
  const guessPct = before.nextLevelXp ? Math.min(100, Math.round((guessXp / before.nextLevelXp) * 100)) : 100;
  const beforePct = before.nextLevelXp ? Math.min(100, Math.round((before.xp / before.nextLevelXp) * 100)) : 100;

  mount(`
    <div class="celebration-screen" style="min-height:70vh;display:flex;align-items:center;justify-content:center;text-align:center;">
      <div class="glass celebration-card" data-tier="${freshAward ? freshAward.tier : "common"}" id="aar-card" style="max-width:660px;width:100%;padding:clamp(28px,4vw,44px);">
        <div class="aar-beat is-visible">
          <h1 class="glow-h anim" style="font-size:clamp(38px,7vw,72px);margin:0 0 10px;">Mission Complete!</h1>
          <p class="hud" style="font-size:14px;margin:0 0 8px;">${escapeHtml(mission.title)}</p>
          <p style="color:var(--teal-100);margin:0 0 4px;">Logged. Every drop counts — even the small ones.</p>
          <div style="margin-top:16px;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">auto_awesome</span>Rewards Unlocked</span></div>
        </div>

        <div class="aar-beat" id="aar-beat-award">
          ${freshAward ? `<p class="celebration-tier">Award: <span class="award" data-tier="${freshAward.tier}" style="display:inline-flex"><span class="award__tier">${freshAward.tier}</span></span></p>` : ""}
        </div>

        <div class="aar-beat" id="aar-beat-xp">
          <div class="dossier-xp">
            <div class="row-between">
              <span class="card__eyebrow">+100 XP</span>
              <span class="mono-rank" id="aar-xp-value">${before.xp}${before.nextLevelXp ? ` / ${before.nextLevelXp}` : " · MAX"}</span>
            </div>
            <div class="world-meter__track"><div class="world-meter__fill is-xp" id="aar-xp-fill" style="width:${beforePct}%"></div></div>
          </div>
        </div>

        <div class="aar-beat" id="aar-beat-levelup"></div>
        <div class="aar-beat" id="aar-beat-unlocks"></div>

        <button class="btn btn-primary aar-beat" id="celebration-continue">See Full Debrief →</button>
      </div>
    </div>
  `);

  Evoke.confetti();

  // The authoritative LevelUpped broadcast is a *second* Kafka round-trip
  // (workers.py re-publishes it onto the same stream once XPGranted crosses
  // a threshold, rather than emitting it inline), so it reliably arrives
  // after this screen's own settle fetch below has already resolved --
  // clearing the suppression right after that fetch was measured to still
  // let the global overlay slip in a few seconds later, stacking a second
  // "you leveled up" moment on top of this one's own inline beat. A fixed
  // grace window is simpler and safer than trying to key off the event
  // actually arriving.
  state.suppressLevelUpOverlay = true;
  setTimeout(() => { state.suppressLevelUpOverlay = false; }, 8000);

  await sleep(500);
  reveal("aar-beat-award");

  await sleep(600);
  reveal("aar-beat-xp");
  requestAnimationFrame(() => {
    const fill = document.getElementById("aar-xp-fill");
    if (fill) fill.style.width = guessPct + "%";
  });
  const xpValueEl = document.getElementById("aar-xp-value");
  const xpStart = performance.now();
  const xpDuration = 900;
  function tickXp(now) {
    const t = Math.min(1, (now - xpStart) / xpDuration);
    const shown = Math.round(before.xp + t * 100);
    if (xpValueEl) xpValueEl.textContent = `${shown}${before.nextLevelXp ? ` / ${before.nextLevelXp}` : " · MAX"}`;
    if (t < 1) requestAnimationFrame(tickXp);
  }
  requestAnimationFrame(tickXp);

  await sleep(1000);
  const [afterProfile, afterAchievements] = await settleFetch;

  if (afterProfile && afterProfile.level > before.level) {
    const beat = document.getElementById("aar-beat-levelup");
    if (beat) {
      beat.innerHTML = `
        <div class="celebration-tier">
          <div class="card__eyebrow">Rank Advancement</div>
          <p>Level ${afterProfile.level} — you are now a <strong>${escapeHtml(afterProfile.rank_title)}</strong></p>
        </div>
      `;
      // Authoritative XP/level landed -- true up the bar/number from the
      // optimistic +100 guess in case the two disagree.
      const fill = document.getElementById("aar-xp-fill");
      const pct = afterProfile.next_level_xp ? Math.min(100, Math.round((afterProfile.xp / afterProfile.next_level_xp) * 100)) : 100;
      if (fill) fill.style.width = pct + "%";
      if (xpValueEl) xpValueEl.textContent = `${afterProfile.xp}${afterProfile.next_level_xp ? ` / ${afterProfile.next_level_xp}` : " · MAX"}`;
    }
    reveal("aar-beat-levelup");
    Evoke.confetti({ count: 130, duration: 2400 });
  }

  if (afterAchievements && before.achievements) {
    const newPowers = Object.entries(afterAchievements.powers || {})
      .filter(([key, after]) => after.earned && !(before.achievements.powers[key] && before.achievements.powers[key].earned))
      .map(([key]) => key);
    const newBadges = Object.entries(afterAchievements.qualities || {})
      .filter(([key, after]) => after.earned && !(before.achievements.qualities[key] && before.achievements.qualities[key].earned))
      .map(([key]) => key);

    if (newPowers.length || newBadges.length) {
      const unlocksEl = document.getElementById("aar-beat-unlocks");
      if (unlocksEl) {
        unlocksEl.innerHTML = `
          <div class="card__eyebrow">New Unlocks</div>
          ${newBadges.map((q) => `<p class="celebration-tier">🏅 <strong>${escapeHtml(q)}</strong> badge complete</p>`).join("")}
          ${newPowers.map((p) => `<p>⚡ New Power: <strong>${escapeHtml(p)}</strong></p>`).join("")}
        `;
      }
      await sleep(500);
      reveal("aar-beat-unlocks");
      await sleep(500);
    }
  }

  reveal("celebration-continue");

  document.getElementById("celebration-continue").addEventListener("click", () => {
    history.replaceState(null, "", location.pathname + `#/mission/${missionId}/debrief`);
    Evoke.screens.missionDebrief(missionId, targetUserIdParam);
  });
}

Evoke.screens.missionDebrief = async function missionDebrief(missionId, targetUserIdParam) {
  const { api, state, mount } = Evoke;
  Evoke.kit?.visit("pipes");
  const targetUserId = targetUserIdParam || state.userId;
  const isOwn = targetUserId === state.userId;

  const [missionsRes, timeline, awardsRes, targetProfile] = await Promise.all([
    api.missions(state.userId),
    api.timeline(targetUserId, missionId).catch(() => ({ insights: [] })),
    api.awards(targetUserId),
    isOwn ? Promise.resolve(null) : api.playerProfile(targetUserId).catch(() => null),
  ]);
  const mission = (missionsRes.missions || []).find(m => m.id === missionId);
  const missionAwards = (awardsRes.awards || []).filter(a => a.mission_id === missionId);

  // Full-screen celebration moment (GAPS.md: "No celebration moments" --
  // found missing by comparing against ui/Final Prosperity Showcase.html,
  // which designed a full-screen reward reveal the real app never built).
  // missionBrief's submit handler routes here with ?fresh=1 right after a
  // successful submission; "Continue" clears the flag via history.replaceState
  // (not a hash change, so it doesn't re-trigger the router) and re-renders
  // the normal debrief in place.
  const isFresh = location.hash.includes("fresh=1");
  const freshAward = missionAwards.find(a => !a.collected_at);
  if (isOwn && isFresh && mission) {
    await renderMissionAAR(mission, freshAward, missionId, targetUserIdParam);
    return;
  }

  mount(`
    <div style="display:flex;flex-direction:column;gap:24px;max-width:920px;margin:0 auto;">
      <div style="text-align:center;">
        <span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">military_tech</span>Debrief</span>
        <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(28px,5vw,48px);text-transform:uppercase;color:var(--cyan-500);text-shadow:0 0 24px rgba(0,150,136,0.3);margin:12px 0 0;line-height:1;">${mission ? Evoke.escapeHtml(mission.title) : "Debrief"}</h1>
        ${!isOwn ? `<p class="empty-state" style="margin-top:8px;">Viewing ${Evoke.escapeHtml(targetProfile ? targetProfile.display_name : "a classmate")}'s work</p>` : ""}
      </div>

      <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
        <span class="ev-label">Insights</span>
        ${(timeline.insights || []).length
          ? timeline.insights.map(i => `<p style="margin:0 0 10px;line-height:1.55;"><strong style="color:var(--cyan-100);">${Evoke.escapeHtml(i.category || "Insight")} from ${Evoke.escapeHtml(i.source)}:</strong> ${Evoke.escapeHtml(i.text)}</p>`).join("")
          : `<p class="empty-state" style="margin:0;">No insights yet — check back shortly.</p>`}
      </div>

      ${!isOwn ? `
        <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
          <span class="ev-label">Leave Feedback</span>
          <form id="peer-insight-form">
            <textarea class="ev-textarea" id="peer-insight-text" placeholder="What stood out about this?" rows="3" required></textarea>
            <button type="submit" class="btn ev-submit">Post Feedback</button>
          </form>
          <p id="peer-insight-status" class="empty-state" style="margin-top:8px;"></p>
        </div>
      ` : ""}

      <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
        <span class="ev-label">Rewards</span>
        <div class="stack-sm" id="awards-list" style="margin-top:12px;">
          ${missionAwards.length ? missionAwards.map(a => `
            <div class="award ${a.collected_at ? "" : "is-pending"}" data-tier="${a.tier}">
              <div>
                <span class="award__tier">${a.tier}</span>
                <span>${a.source.replace("_", " ")}</span>
              </div>
              ${a.collected_at
                ? `<span class="empty-state">Collected</span>`
                : (isOwn ? `<button data-award-id="${a.id}" class="btn collect-btn">Collect</button>` : `<span class="empty-state">Not yet collected</span>`)}
            </div>
          `).join("") : `<p class="empty-state" style="margin:0;">No awards yet for this mission.</p>`}
        </div>
      </div>

      <div style="display:flex;gap:14px;flex-wrap:wrap;">
        <a class="btn sec" href="${isOwn ? "#/" : "#/gallery"}">◀ Back to ${isOwn ? "Operations Hub" : "Gallery"}</a>
        ${isOwn ? `<a class="btn" href="#/mission/${missionId}/vault">Open in the Vault ▶</a>` : ""}
      </div>
    </div>
  `);

  document.querySelectorAll(".collect-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Collecting...";
      try {
        await api.collectAward(btn.dataset.awardId, state.userId);
        btn.closest(".award").classList.remove("is-pending");
        btn.replaceWith(Object.assign(document.createElement("span"), { className: "empty-state", textContent: "Collected — delivered to your agent in the Basin" }));
      } catch (e) {
        btn.disabled = false;
        btn.textContent = "Collect";
      }
    });
  });

  document.getElementById("peer-insight-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const textEl = document.getElementById("peer-insight-text");
    const statusEl = document.getElementById("peer-insight-status");
    const text = textEl.value.trim();
    if (!text) return;
    statusEl.textContent = "Posting...";
    try {
      await api.postPeerInsight(targetUserId, missionId, state.userId, text);
      statusEl.textContent = "Posted! It'll show up in their Insights above shortly.";
      textEl.value = "";
    } catch (err) {
      statusEl.textContent = "Couldn't post that just now.";
    }
  });
};

Evoke.screens.gallery = async function gallery() {
  const { api, mount } = Evoke;
  Evoke.kit?.visit("charcoal");
  // "Peers seeing each other's work" -- GAPS.md's #2 flagged social-layer
  // gap, the other half beyond the activity feed: the feed says something
  // happened, the gallery is where you can actually go look and react.
  const galleryRes = await api.gallery().catch(() => ({ gallery: [] }));
  const items = galleryRes.gallery || [];

  mount(`
    <div style="display:flex;flex-direction:column;gap:24px;">
      <div>
        <h1 class="glow-h" style="font-size:clamp(30px,5vw,52px);margin:0 0 8px;">Gallery</h1>
        <p class="empty-state" style="margin:0;">Completed mission work from across the cohort. Open one to leave feedback.</p>
      </div>
      <div class="grid-2">
        ${items.length ? items.map(it => `
          <a class="glass mission-card" data-state="available" href="#/mission/${it.mission_id}/debrief/${it.user_id}" style="padding:20px 22px;">
            <span class="ev-label">${Evoke.escapeHtml(it.mission_title)}</span>
            <div class="mission-card__title" style="margin-top:8px;">${Evoke.escapeHtml(it.display_name)}</div>
            <div class="mission-card__meta">${Evoke.escapeHtml(it.superpower || "")} · ${new Date(it.submitted_at).toLocaleDateString()}</div>
          </a>
        `).join("") : `<p class="empty-state">No submissions yet — this fills up as the cohort starts turning in missions.</p>`}
      </div>
    </div>
  `);
};

/* The Agent Dossier — the profile as a video-game loadout/dossier screen:
   identity block with clearance chips and an XP charge bar, the 4
   Superpowers as loadout slots with pip progress, the 16 Powers as a skill
   matrix, awards as commendations, quests as the field-ops log. Same data,
   same trophy-case principle as before (every slot visible, earned or
   not); only the presentation changed. */
Evoke.screens.playerProfile = async function playerProfile(userId) {
  const { api, state, mount } = Evoke;
  const id = userId || state.userId;
  const [profile, achievementsRes, missionsRes, questsRes, mcStatus, gearRes, kitRes, reflectionsRes, arenaRes, gauntletRes] = await Promise.all([
    api.playerProfile(id),
    api.achievements(id).catch(() => ({ qualities: {}, powers: {} })),
    api.missions(id).catch(() => ({ missions: [] })),
    api.mcQuests().catch(() => ({ quests: [] })),
    api.minecraftStatus().catch(() => null),
    api.gear(id).catch(() => ({ gear: [], equipped: [], sigil: null, has_avatar: false })),
    api.kitProgress(id).catch(() => ({ found: [], total: 10, complete: false, pieces: {} })),
    api.reflections(id).catch(() => ({ journal: [], total: 0 })),
    api.mcArena(id).catch(() => ({ best_wave: 0 })),
    api.mcGauntlet(id).catch(() => ({ best_wave: 0 })),
  ]);
  Evoke.kit?.visit("valve");
  const badgeKeys = ["Empathetic Changemaker", "Systems Thinker", "Creative Visionary", "Deep Collaborator"];
  const powers = achievementsRes.powers || {};

  // Trophy case principle: show every mission/quest that exists, not just
  // what's already earned -- a learner should be able to see the whole
  // shelf, including the empty slots, so the not-yet-earned ones read as
  // "still to do" rather than invisible.
  const allMissions = missionsRes.missions || [];
  const allQuests = questsRes.quests || [];
  const questCompletions = {};
  (profile.quests_completed || []).forEach(q => { questCompletions[q.quest_id] = q.completed_at; });

  const TIER_RANK = { common: 1, epic: 2, legendary: 3 };
  const bestAwardByMission = {};
  (profile.awards || []).forEach(a => {
    const current = bestAwardByMission[a.mission_id];
    if (!current || TIER_RANK[a.tier] > TIER_RANK[current.tier]) bestAwardByMission[a.mission_id] = a;
  });

  const name = profile.display_name || "Agent";
  const monogram = name.split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
  const inBasin = !!(mcStatus && mcStatus.server_online && profile.minecraft_username
    && (mcStatus.online_players || []).includes(profile.minecraft_username));
  const isOwn = id === state.userId;

  // Identity visual, in priority order: uploaded photo > chosen Agent
  // Sigil (curated glyph + hue) > monogram fallback.
  const sigil = gearRes.sigil;
  const avatarHtml = gearRes.has_avatar
    ? `<img class="dossier-monogram dossier-avatar" src="/api/avatar/${id}?t=${Date.now()}" alt="${Evoke.escapeHtml(name)}'s avatar">`
    : (sigil
        ? `<div class="dossier-monogram dossier-sigil" style="--sigil-hue:${sigil.hue}" aria-hidden="true">${Evoke.escapeHtml(sigil.glyph)}</div>`
        : `<div class="dossier-monogram" aria-hidden="true">${Evoke.escapeHtml(monogram)}</div>`);

  const equippedItems = (gearRes.gear || []).filter(g => (gearRes.equipped || []).includes(g.key));

  // "New gear unlocked" nudge: diff unlocked keys against what this browser
  // saw last time (cosmetic-only, so localStorage is an honest enough memory).
  if (isOwn) {
    const seenKey = `evoke_gear_seen_${id}`;
    const seen = new Set(JSON.parse(localStorage.getItem(seenKey) || "[]"));
    const nowUnlocked = (gearRes.gear || []).filter(g => g.unlocked).map(g => g.key);
    nowUnlocked.filter(k => !seen.has(k)).forEach(k => {
      const g = (gearRes.gear || []).find(x => x.key === k);
      if (seen.size) Evoke.toast(`◈ FIELD GEAR UNLOCKED — <strong>${Evoke.escapeHtml(g.name)}</strong><br>${Evoke.escapeHtml(g.flavor)}`, { ttl: 9000 });
    });
    localStorage.setItem(seenKey, JSON.stringify(nowUnlocked));
  }

  // XP charge bar: progress through the current level's band.
  const nextXp = profile.next_level_xp;
  const xpPct = nextXp ? Math.min(100, Math.round((profile.xp / nextXp) * 100)) : 100;

  const completedIds = new Set(profile.missions_completed || []);

  // Service Record (console-UX gap #8): lifetime stats in one glanceable
  // strip -- every number here already existed somewhere else on this
  // screen, just never summarized together the way a combat record does.
  const RARITY_RANK = { standard: 1, epic: 2, legendary: 3 };
  const rarestGear = (gearRes.gear || [])
    .filter(g => g.unlocked)
    .sort((a, b) => (RARITY_RANK[b.rarity] || 0) - (RARITY_RANK[a.rarity] || 0))[0];
  const statTiles = [
    { icon: "flag", n: `${profile.missions_completed_count}/12`, l: "Missions" },
    { icon: "explore", n: String(profile.quests_completed_count), l: "Quests" },
    { icon: "sports_esports", n: gearRes.best_sim_score != null ? String(gearRes.best_sim_score) : "—", l: "Best Sim Score" },
    { icon: "auto_stories", n: String(reflectionsRes.total || 0), l: "Wisdom Entries" },
    { icon: "inventory_2", n: `${gearRes.unlocked_count}/${gearRes.total}`, l: "Gear Recovered" },
    { icon: "workspace_premium", n: rarestGear ? rarestGear.icon : "—", l: rarestGear ? `Rarest: ${Evoke.escapeHtml(rarestGear.name)}` : "Rarest Gear" },
    { icon: "swords", n: arenaRes.best_wave > 0 ? `Wave ${arenaRes.best_wave}` : "—", l: "Arena Best" },
    { icon: "swords", n: gauntletRes.best_wave > 0 ? `Wave ${gauntletRes.best_wave}` : "—", l: "Gauntlet Best" },
  ];

  mount(`
    <div class="stack dossier">
      <h1 class="glow-h" style="font-size:clamp(30px,5vw,56px);margin-bottom:28px;">Profile</h1>
      <div class="pf-grid">
        <div class="glass brackets" style="padding:30px 30px 34px;text-align:center;position:relative;">
          <div class="pf-avatar-wrap">
            <button id="pf-avatar-btn" class="pf-avatar" type="button" aria-label="Change your avatar" ${isOwn ? "" : "disabled"}>
              <span class="mtile" style="width:104px;height:104px;border-radius:50%;overflow:hidden;display:flex;align-items:center;justify-content:center;">${avatarHtml}</span>
              ${isOwn ? `<span class="pf-avatar-edit" aria-hidden="true"><span class="ms" style="font-size:15px;">edit</span></span>` : ""}
            </button>
          </div>
          <div class="pf-name-row">
            <h2 style="font-family:var(--font-display);font-weight:800;font-size:24px;color:var(--text-heading);margin:0;">${Evoke.escapeHtml(name)}</h2>
          </div>
          <div class="hud" style="font-size:12px;margin:7px 0 18px;">${Evoke.escapeHtml(profile.rank_title || "Recruit")} · Keel Network</div>
          <div class="pf-ring" style="--pct:${xpPct};">
            <div class="pf-ring-in"><div class="pf-ring-lvl">${profile.level}</div><div class="pf-ring-cap">LEVEL</div></div>
          </div>
          <div style="font-family:var(--font-mono);font-size:12px;color:var(--text-faint);margin-top:14px;">${profile.xp} / ${nextXp || profile.xp} XP to Level ${profile.level + 1}</div>
          <div style="font-family:var(--font-mono);font-size:11px;color:var(--text-faint);margin-top:6px;">${inBasin ? "In the Basin now" : (profile.minecraft_username ? "Callsign " + Evoke.escapeHtml(profile.minecraft_username) : "Basin not linked")}</div>
          ${isOwn ? `
          <div style="margin-top:16px;"><button class="btn sec" id="identity-edit" style="width:100%;">Customize Identity</button></div>
          <div id="identity-editor" class="identity-editor" hidden style="margin-top:16px;text-align:left;">
            <div class="hud" style="font-size:11px;margin-bottom:10px;color:var(--cyan-300);">Agent Sigil — pick a mark and a color</div>
            <div class="row" id="sigil-glyphs">
              ${["⬡","◈","✦","☄","⚙","♜","⟁","◭","⬢","❖"].map(g => `<button class="sigil-pick ${sigil && sigil.glyph === g ? "is-current" : ""}" data-glyph="${g}">${g}</button>`).join("")}
            </div>
            <div class="row" style="margin-top:12px;">
              <input type="range" id="sigil-hue" min="0" max="360" value="${sigil ? sigil.hue : 190}" style="flex:1">
              <span class="dossier-monogram dossier-sigil sigil-preview" id="sigil-preview" style="--sigil-hue:${sigil ? sigil.hue : 190}; width:44px;height:44px;font-size:var(--text-lg)">${sigil ? Evoke.escapeHtml(sigil.glyph) : "⬡"}</span>
            </div>
            <div class="row" style="margin-top:14px;">
              <label class="btn sec" style="cursor:pointer">Upload Photo<input type="file" id="avatar-file" accept="image/*" hidden></label>
              ${gearRes.has_avatar ? `<button class="btn sec" id="avatar-remove">Remove Photo</button>` : ""}
            </div>
            <p id="identity-status" class="empty-state" style="margin-top:10px;"></p>
          </div>
          ` : ""}
        </div>
        <div style="display:flex;flex-direction:column;gap:24px;">
          <div class="glass" style="padding:24px 26px;">
            <h2 class="hud" style="font-size:12px;margin:0 0 16px;">Agent Stats</h2>
            <div class="pf-stats">
              <div class="pf-stat" style="--accent:var(--green-400);"><span class="ms" aria-hidden="true">rocket_launch</span><div class="n">${profile.missions_completed_count || 0}</div><div class="l">Missions</div></div>
              <div class="pf-stat" style="--accent:var(--cyan-300);"><span class="ms" aria-hidden="true">military_tech</span><div class="n">${profile.level}</div><div class="l">Level</div></div>
              <div class="pf-stat" style="--accent:var(--orange-500);"><span class="ms" aria-hidden="true">bolt</span><div class="n">${profile.xp}</div><div class="l">Total XP</div></div>
            </div>
          </div>
          <div class="glass" style="padding:24px 26px;">
            <h2 class="hud" style="font-size:12px;margin:0 0 8px;">Settings</h2>
            <div style="display:flex;flex-direction:column;gap:4px;" id="pf-settings">
              <div class="pf-set-row"><span class="ms" aria-hidden="true" style="font-size:22px;color:var(--cyan-300);">contrast</span><div style="flex:1;"><div style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--text-heading);">High Contrast</div><div class="pf-set-val" style="font-family:var(--font-body);font-size:13px;color:var(--text-faint);">Standard contrast</div></div><button class="pf-toggle" type="button" role="switch" aria-checked="false" data-setting="hc" aria-label="High Contrast"></button></div>
              <div class="pf-set-row"><span class="ms" aria-hidden="true" style="font-size:22px;color:var(--cyan-300);">animation</span><div style="flex:1;"><div style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--text-heading);">Reduce Motion</div><div class="pf-set-val" style="font-family:var(--font-body);font-size:13px;color:var(--text-faint);">Animations on</div></div><button class="pf-toggle" type="button" role="switch" aria-checked="false" data-setting="reduce-motion" aria-label="Reduce Motion"></button></div>
              <div class="pf-set-row"><span class="ms" aria-hidden="true" style="font-size:22px;color:var(--cyan-300);">notifications</span><div style="flex:1;"><div style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--text-heading);">Mission Reminders</div><div class="pf-set-val" style="font-family:var(--font-body);font-size:13px;color:var(--text-faint);">Reminders off</div></div><button class="pf-toggle" type="button" role="switch" aria-checked="false" data-setting="reminders" aria-label="Mission Reminders"></button></div>
            </div>
          </div>
        </div>
      </div>

    </div>
  `);

  if (!isOwn) return;

  // --- identity editor ---
  document.getElementById("identity-edit")?.addEventListener("click", () => {
    const ed = document.getElementById("identity-editor");
    ed.hidden = !ed.hidden;
  });
  const statusEl = () => document.getElementById("identity-status");
  let pendingGlyph = sigil ? sigil.glyph : "⬡";
  document.querySelectorAll(".sigil-pick").forEach(btn => btn.addEventListener("click", async () => {
    pendingGlyph = btn.dataset.glyph;
    const hue = Number(document.getElementById("sigil-hue").value);
    const preview = document.getElementById("sigil-preview");
    preview.textContent = pendingGlyph;
    preview.style.setProperty("--sigil-hue", hue);
    await api.setSigil(id, pendingGlyph, hue).catch(() => {});
    statusEl().textContent = "Sigil saved.";
    document.querySelectorAll(".sigil-pick").forEach(b => b.classList.toggle("is-current", b === btn));
  }));
  document.getElementById("sigil-hue")?.addEventListener("change", async (e) => {
    const hue = Number(e.target.value);
    document.getElementById("sigil-preview").style.setProperty("--sigil-hue", hue);
    await api.setSigil(id, pendingGlyph, hue).catch(() => {});
    statusEl().textContent = "Sigil saved.";
  });
  document.getElementById("avatar-file")?.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    statusEl().textContent = "Uploading…";
    try {
      await api.uploadAvatar(id, file);
      statusEl().textContent = "Photo set.";
      Evoke.screens.playerProfile(userId);
    } catch (err) {
      statusEl().textContent = "Upload failed — images only, 2MB max.";
    }
  });
  document.getElementById("avatar-remove")?.addEventListener("click", async () => {
    await api.deleteAvatar(id).catch(() => {});
    Evoke.screens.playerProfile(userId);
  });

  // --- gear equip toggles (max 3, server-validated) ---
  document.querySelectorAll(".gear-equip-btn").forEach(btn => btn.addEventListener("click", async () => {
    const key = btn.dataset.gearKey;
    let next = [...(gearRes.equipped || [])];
    if (next.includes(key)) next = next.filter(k => k !== key);
    else {
      if (next.length >= 3) { Evoke.toast("Three gear slots — unequip something first."); return; }
      next.push(key);
    }
    try {
      await api.equipGear(id, next);
      Evoke.screens.playerProfile(userId);
    } catch (e) {
      Evoke.toast("Couldn't equip that just now.");
    }
  }));
};

Evoke.screens.teamProfile = async function teamProfile(teamId) {
  const { api, mount } = Evoke;
  Evoke.kit?.visit("spout");
  const [team, wheelRes, mcStatus] = await Promise.all([
    api.teamProfile(teamId),
    api.teamWheel(teamId).catch(() => ({ wheels: [], roster_size: 0 })),
    api.minecraftStatus().catch(() => null),
  ]);
  const onlinePlayers = new Set((mcStatus && mcStatus.online_players) || []);

  // Squad panel (console-UX gap #7): "friends online, join them" -- the
  // team page was a flat name list with no presence signal anywhere.
  // Presence is scoped to the Basin (Minecraft) since that's the only
  // real-time presence this app tracks; there's no "browsing the web app
  // right now" signal to show alongside it.
  mount(`
    <div class="stack">
      <div class="card">
        <h1 class="glow-h" style="font-size:clamp(28px,5vw,48px);margin:0;">${Evoke.escapeHtml(team.team_name || "Team")}</h1>
        <div class="squad-panel">
          ${(team.members || []).map(m => {
            const online = m.minecraft_username && onlinePlayers.has(m.minecraft_username);
            const sigilStyle = m.sigil ? `--sigil-hue:${m.sigil.hue}` : "";
            return `
            <div class="squad-member">
              <span class="dossier-monogram ${m.sigil ? "dossier-sigil" : ""}" style="width:48px;height:48px;font-size:var(--text-lg);${sigilStyle}">
                ${m.sigil ? Evoke.escapeHtml(m.sigil.glyph) : Evoke.escapeHtml((m.display_name || "?")[0])}
              </span>
              <div class="squad-member__info">
                <strong>${Evoke.escapeHtml(m.display_name)}</strong>
                ${m.role_label ? `<span class="empty-state">${Evoke.escapeHtml(m.role_label)}</span>` : ""}
                <span class="squad-member__presence">
                  <span class="presence-dot ${online ? "is-online" : ""}"></span>
                  ${online ? "In the Basin now" : (m.minecraft_username ? "Offline" : "Not linked")}
                </span>
              </div>
            </div>
          `;
          }).join("") || `<p class="empty-state">No members yet.</p>`}
        </div>
      </div>

      <section class="card">
        <div class="card__eyebrow">Team Mission Progress</div>
        <p>${team.missions_completed_count} / 12 complete (team-wide)</p>
      </section>

      <section class="card">
        <div class="card__eyebrow">Team Wheels — nobody left behind</div>
        <p class="empty-state">One wheel per released mission; a wedge fills when that member submits it. The wheel completing is a team celebration, never a gate — a wedge stays open as long as it needs to.</p>
        <div class="stack-sm">
          ${(wheelRes.wheels || []).length ? wheelRes.wheels.map(w => `
            <div class="wheel-row ${w.complete ? "is-complete" : ""}">
              <span class="wheel-row__title">${w.complete ? "◎ " : ""}${Evoke.escapeHtml(w.title)}</span>
              <span class="wheel-row__wedges">
                ${w.wedges.map(wd => `<span class="wheel-wedge ${wd.filled ? "is-filled" : ""}" title="${Evoke.escapeHtml(wd.display_name)}${wd.filled ? " — submitted" : " — not yet"}"></span>`).join("")}
              </span>
              <span class="empty-state">${w.complete ? "complete — every member" : `${w.wedges.filter(x => x.filled).length}/${w.wedges.length}`}</span>
            </div>
          `).join("") : `<p class="empty-state">No released missions yet.</p>`}
        </div>
      </section>

      <section class="card">
        <div class="card__eyebrow">Combined Badge Wall</div>
        ${Object.keys(team.member_badges || {}).length
          ? Object.entries(team.member_badges).map(([uid, badges]) => `
              <p>${uid.slice(0, 8)}: ${Object.keys(badges).join(", ")}</p>
            `).join("")
          : `<p class="empty-state">No badges earned yet.</p>`}
      </section>

      <section class="card">
        <div class="card__eyebrow">Quest Log</div>
        <p>${team.quests_completed_count} completed by the team</p>
      </section>

      <section class="card">
        <div class="card__eyebrow">Venture Points / Venture Spectrum</div>
        <p class="empty-state">Unlocks in the Act arc (weeks 4–6).</p>
      </section>
    </div>
  `);
};

// Deliberately not linked from the learner-facing top nav (app.js's
// renderTopbar) -- reachable at #/admin directly, same pattern as
// brightspace-sim's /teacher-review. No role check exists yet (see
// GAPS.md's "Auth is dev-grade" gap) so this is a direct-URL utility
// today, not a promoted destination.
Evoke.screens.admin = async function admin() {
  const { api, mount } = Evoke;
  const [missionsRes, cohortRes, world, mcStatus, rosterRes, teamsRes] = await Promise.all([
    api.adminMissions(Evoke.state.userId).catch(() => ({ missions: [] })),
    api.adminCohort(Evoke.state.userId).catch(() => ({ cohort: [] })),
    api.worldState().catch(() => null),
    api.minecraftStatus().catch(() => null),
    api.adminRoster().catch(() => ({ roster: [] })),
    api.adminTeams().catch(() => ({ teams: [] })),
  ]);
  const missions = missionsRes.missions || [];
  const cohort = cohortRes.cohort || [];
  const roster = rosterRes.roster || [];
  const teams = teamsRes.teams || [];
  const daysAgo = (iso) => iso ? Math.max(0, Math.floor((Date.now() - parseUtc(iso)) / 86400000)) : null;

  mount(`
    <div class="stack">
      <div class="row-between">
        <h1 class="glow-h" style="font-size:clamp(28px,5vw,48px);margin:0;">Instructor Ops Deck</h1>
        <span class="row">
          ${world ? `<span class="chip">KEEL STAGE ${world.stage}/${world.total_stages}</span>` : ""}
          <span class="chip ${mcStatus && mcStatus.server_online ? "chip--green" : ""}">${mcStatus && mcStatus.server_online ? `<span class="dot"></span>BASIN ONLINE · ${(mcStatus.online_players || []).length} IN-WORLD` : "BASIN STATUS UNKNOWN"}</span>
        </span>
      </div>

      <section class="card">
        <div class="card__eyebrow">Cohort — who needs you</div>
        ${cohort.length ? `
          <table class="cohort-table">
            <thead><tr><th>Agent</th><th>Rank</th><th>Missions</th><th>Last submission</th><th>Waiting on you</th></tr></thead>
            <tbody>
              ${cohort.map(c => {
                const days = daysAgo(c.last_submission);
                const stuck = days === null || days >= 7;
                return `
                <tr class="${stuck ? "is-stuck" : ""}">
                  <td><a href="#/profile/${c.user_id}">${Evoke.escapeHtml(c.display_name)}</a></td>
                  <td>Lv ${c.level} · ${Evoke.escapeHtml(c.rank_title)}</td>
                  <td>${c.missions_completed}/12</td>
                  <td>${days === null ? `<span class="empty-state">never</span>` : (days === 0 ? "today" : `${days}d ago`)}${stuck ? " ⚠" : ""}</td>
                  <td>${c.pending_teacher_reviews ? `<strong>${c.pending_teacher_reviews} review${c.pending_teacher_reviews === 1 ? "" : "s"}</strong>` : `<span class="empty-state">—</span>`}</td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
          <p class="empty-state" style="margin-top:var(--space-2)">⚠ = no submission in 7+ days. Reviews happen in the Brightspace sim's teacher screen; awards land here automatically.</p>
        ` : `<p class="empty-state">No learners in this org yet.</p>`}
      </section>

      <h2 class="section-title">Teams</h2>
      <p class="empty-state">EVOKE Teams contain EVOKE Players — every Player is 1:1 with an LMS student. Import from the roster below, then assign here. A learner belongs to exactly one team; assigning moves them.</p>
      <section class="card">
        <form id="create-team-form" class="row" style="margin-bottom:var(--space-3)">
          <input type="text" id="new-team-name" placeholder="New team name" required style="flex:1">
          <button type="submit" class="btn btn-primary">Create Team</button>
        </form>
        ${teams.length ? `
          <div class="stack-sm">
            ${teams.map(t => `
              <div class="card" data-team-id="${t.team_id}">
                <strong>${Evoke.escapeHtml(t.name)}</strong>
                <p class="empty-state">${t.members.length} member${t.members.length === 1 ? "" : "s"}</p>
                ${t.members.length ? `
                  <ul class="stack-sm">
                    ${t.members.map(m => `
                      <li class="row-between">
                        <span>${Evoke.escapeHtml(m.display_name)}</span>
                        <button class="btn" data-remove-member="${m.user_id}" data-team-id="${t.team_id}">Remove</button>
                      </li>
                    `).join("")}
                  </ul>
                ` : `<p class="empty-state">No members yet.</p>`}
              </div>
            `).join("")}
          </div>
        ` : `<p class="empty-state">No teams yet — create one above.</p>`}
      </section>

      <section class="card">
        <div class="card__eyebrow">LMS Roster</div>
        ${roster.length ? `
          <table class="cohort-table">
            <thead><tr><th>Student</th><th>Email</th><th>EVOKE Player</th><th>Team</th></tr></thead>
            <tbody>
              ${roster.map(r => `
                <tr>
                  <td>${Evoke.escapeHtml(r.display_name)}</td>
                  <td>${Evoke.escapeHtml(r.email)}</td>
                  <td>${r.imported ? `<span class="chip chip--green">Imported</span>` : `<button class="btn" data-import-bsid="${r.brightspace_user_id}">Import</button>`}</td>
                  <td>${r.imported ? `
                    <select data-assign-user="${r.user_id}" data-current-team="${r.team ? r.team.team_id : ""}">
                      <option value="">Unassigned</option>
                      ${teams.map(t => `<option value="${t.team_id}" ${r.team && r.team.team_id === t.team_id ? "selected" : ""}>${Evoke.escapeHtml(t.name)}</option>`).join("")}
                    </select>
                  ` : `<span class="empty-state">Import first</span>`}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<p class="empty-state">No roster data — is brightspace-sim reachable?</p>`}
      </section>

      <h2 class="section-title">Mission Release</h2>
      <p class="empty-state">Missions are gated by manual release, not automatic order. Week 1's first mission releases on its own; everything else waits here.</p>
      <div class="stack-sm">
        ${missions.map(m => `
          <div class="card" data-mission-row="${m.id}">
            <div class="card__eyebrow">Week ${m.week} · ${m.arc}</div>
            <strong>${Evoke.escapeHtml(m.title)}</strong>
            <p class="empty-state">${m.released ? `Released ${new Date(m.released_at).toLocaleString()}` : "Not released"}</p>
            <div class="row">
              <button class="btn ${m.released ? "" : "btn-primary"}" data-action="${m.released ? "unrelease" : "release"}" data-mission-id="${m.id}">
                ${m.released ? "Unrelease" : "Release"}
              </button>
              <label class="empty-state">Stage
                <select data-stage-for="${m.id}">
                  ${Array.from({length: 8}, (_, i) => i + 1).map(n => `<option value="${n}" ${((m.stage || m.week) === n) ? "selected" : ""}>${n}</option>`).join("")}
                </select>
              </label>
            </div>
          </div>
        `).join("") || `<p class="empty-state">No missions synced yet.</p>`}
      </div>
    </div>
  `);

  document.querySelectorAll("[data-stage-for]").forEach(sel => {
    sel.addEventListener("change", async () => {
      try {
        await api.setStage(sel.dataset.stageFor, Number(sel.value));
        Evoke.toast(`Stage updated — the Campaign Map regroups instantly.`);
      } catch (e) { alert("Couldn't set stage: " + e.message); }
    });
  });

  document.querySelectorAll("[data-action]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const missionId = btn.dataset.missionId;
      btn.disabled = true;
      try {
        if (btn.dataset.action === "release") await api.adminRelease(missionId);
        else await api.adminUnrelease(missionId);
        await Evoke.screens.admin();
      } catch (err) {
        btn.disabled = false;
        alert("Failed: " + err.message);
      }
    });
  });

  document.getElementById("create-team-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const nameInput = document.getElementById("new-team-name");
    try {
      await api.adminCreateTeam(nameInput.value);
      await Evoke.screens.admin();
    } catch (err) { alert("Couldn't create team: " + err.message); }
  });

  document.querySelectorAll("[data-import-bsid]").forEach(btn => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      try {
        await api.adminImportStudent(btn.dataset.importBsid);
        await Evoke.screens.admin();
      } catch (err) {
        btn.disabled = false;
        alert("Import failed: " + err.message);
      }
    });
  });

  document.querySelectorAll("[data-assign-user]").forEach(sel => {
    sel.addEventListener("change", async () => {
      const userId = sel.dataset.assignUser;
      const currentTeam = sel.dataset.currentTeam;
      try {
        if (sel.value) await api.adminAddTeamMember(sel.value, userId);
        else if (currentTeam) await api.adminRemoveTeamMember(currentTeam, userId);
        await Evoke.screens.admin();
      } catch (err) { alert("Couldn't update team assignment: " + err.message); }
    });
  });

  document.querySelectorAll("[data-remove-member]").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        await api.adminRemoveTeamMember(btn.dataset.teamId, btn.dataset.removeMember);
        await Evoke.screens.admin();
      } catch (err) { alert("Couldn't remove member: " + err.message); }
    });
  });
};

// Full-screen B1llbot chat mode (GAPS.md gap surfaced by comparing against
// ui/Final Prosperity Showcase.html, which designed an immersive
// full-screen "holo-comms" chat screen -- the real app previously only had
// the persistent bottom drawer, which stays minimized/small by design).
// Independent message log from the drawer's -- this is a different,
// more deliberate conversation mode, not a resize of the same widget.
Evoke.screens.billbot = async function billbot() {
  const { api, state, mount } = Evoke;
  mount(`
    <div class="bb-room">
      <div class="bb-inner">
        <div class="bb-name">
          <h1>B1LLBOT</h1>
          <div class="tag">Online · ready to help</div>
        </div>
        <div class="bb-split">
          <div class="bb-holo-col">
            <span class="bay-tag bay-tag-tl">REC ●</span>
            <span class="bay-tag bay-tag-tr">SIG 98%</span>
            <span class="bay-tag bay-tag-bl">ID · BB-01</span>
            <div class="holo">
              <div class="badge-live"><span class="dot"></span>Live Transmission</div>
              <div class="reticle"></div>
              <div class="cone"></div>
              <img class="figure" src="img/billbot-avatar.png" alt="B1llbot">
              <div class="dais"></div>
            </div>
          </div>
          <div class="bb-chat-col">
            <div class="chat-hdr">// TRANSMISSION LOG<span class="hdots"><i></i><i></i><i></i></span></div>
            <div class="chat-log" id="billbot-fs-log">
              <div class="bubble bot">You made it. What's on your mind?</div>
            </div>
            <div class="suggest" id="billbot-suggest">
              ${["What should I do first?", "What's a Field Report?", "Tell me about Keel"].map(q => `<button type="button" data-q="${Evoke.escapeHtml(q)}">${Evoke.escapeHtml(q)}</button>`).join("")}
            </div>
            <form id="billbot-fs-form" class="chat-input">
              <input type="text" id="billbot-fs-input" placeholder="Ask B1llbot..." autocomplete="off">
              <button type="submit" class="send" aria-label="Send"><span class="ms" aria-hidden="true">send</span></button>
            </form>
          </div>
        </div>
      </div>
    </div>
  `);

  const log = document.getElementById("billbot-fs-log");
  const input = document.getElementById("billbot-fs-input");
  async function send(msg) {
    if (!msg) return;
    if (/alchemy/i.test(msg)) Evoke.signal?.collect("billbot");
    log.insertAdjacentHTML("beforeend", `<div class="bubble me">${Evoke.escapeHtml(msg)}</div>`);
    input.value = "";
    // A local model response takes 10-20s once warm, longer on a cold start.
    log.insertAdjacentHTML("beforeend", `<div class="bubble bot typing" id="billbot-fs-thinking"><span></span><span></span><span></span></div>`);
    log.scrollTop = log.scrollHeight;
    try {
      const reply = await api.billbotChat(state.userId, msg);
      document.getElementById("billbot-fs-thinking")?.remove();
      log.insertAdjacentHTML("beforeend", `<div class="bubble bot">${Evoke.escapeHtml(reply.reply)}</div>`);
    } catch (err) {
      document.getElementById("billbot-fs-thinking")?.remove();
      log.insertAdjacentHTML("beforeend", `<div class="bubble bot">Having trouble hearing you right now.</div>`);
    }
    log.scrollTop = log.scrollHeight;
  }
  document.getElementById("billbot-fs-form").addEventListener("submit", (e) => { e.preventDefault(); send(input.value.trim()); });
  document.querySelectorAll("#billbot-suggest button").forEach(b => b.addEventListener("click", () => send(b.dataset.q)));
};

// Mission Vault -- a revisit-anytime retrospective, distinct from the
// debrief (which is the live/right-after-submission view). Gap surfaced by
// comparing against ui/Final Prosperity Showcase.html, which designed a
// per-mission retrospective ("The Mission" / "What You Explored" / etc.)
// the real app had no equivalent of. Own missions only -- a retrospective
// on someone else's private reflection text isn't the Gallery's peer-view
// model, it's just not built.
Evoke.screens.vault = async function vault(missionId) {
  const { api, state, mount } = Evoke;
  Evoke.kit?.visit("gauge");
  const [missionsRes, timeline, submission, awardsRes] = await Promise.all([
    api.missions(state.userId),
    api.timeline(state.userId, missionId).catch(() => ({ insights: [] })),
    api.submission(state.userId, missionId).catch(() => ({ submitted: false })),
    api.awards(state.userId).catch(() => ({ awards: [] })),
  ]);
  const mission = (missionsRes.missions || []).find(m => m.id === missionId);
  if (!mission) { mount(`<div class="card"><p>Mission not found.</p></div>`); return; }

  const missionAwards = (awardsRes.awards || []).filter(a => a.mission_id === missionId);

  if (!submission.submitted) {
    mount(`
      <div style="display:flex;flex-direction:column;gap:24px;max-width:920px;margin:0 auto;">
        <div style="display:flex;justify-content:center;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">inventory_2</span>The Vault</span></div>
        <div class="glass brackets" style="padding:clamp(24px,3.5vw,36px);text-align:center;">
          <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(26px,5vw,44px);text-transform:uppercase;color:var(--cyan-500);text-shadow:0 0 24px rgba(0,150,136,0.3);margin:0 0 12px;line-height:1;">${Evoke.escapeHtml(mission.title)}</h1>
          <p class="empty-state" style="margin:0;">Nothing here yet — this fills in once you've submitted evidence for this mission.</p>
        </div>
        <a class="btn sec" href="#/mission/${missionId}">◀ Back to Mission Brief</a>
      </div>
    `);
    return;
  }

  mount(`
    <div style="display:flex;flex-direction:column;gap:24px;max-width:920px;margin:0 auto;">
      <div style="display:flex;justify-content:center;"><span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">inventory_2</span>${Evoke.escapeHtml(mission.arc)} · Week ${mission.week}</span></div>
      <div class="glass brackets" style="padding:clamp(24px,3.5vw,36px);text-align:center;">
        <div class="hud" style="font-size:13px;margin-bottom:8px;">The Vault</div>
        <h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(28px,5vw,48px);text-transform:uppercase;color:var(--cyan-500);text-shadow:0 0 24px rgba(0,150,136,0.3);margin:0;line-height:1;">${Evoke.escapeHtml(mission.title)}</h1>
      </div>

      <div class="panel" style="padding:clamp(22px,3.5vw,32px);">
        <h2 class="hud" style="font-size:12px;margin:0 0 12px;color:var(--cyan-300);">The Mission</h2>
        <p style="margin:0;color:var(--teal-050);line-height:1.55;">${Evoke.escapeHtml(mission.brief || "No brief text yet.").replace(/\n/g, "<br>")}</p>
      </div>

      <div class="panel" style="padding:clamp(22px,3.5vw,32px);">
        <h2 class="hud" style="font-size:12px;margin:0 0 12px;color:var(--cyan-300);">What You Explored</h2>
        ${submission.reflection
          ? `<p style="margin:0;color:var(--teal-050);line-height:1.55;">${Evoke.escapeHtml(submission.reflection)}</p>`
          : `<p class="empty-state" style="margin:0;">No field note recorded for this one.</p>`}
        <p class="empty-state" style="margin-top:12px;">Submitted ${new Date(submission.submitted_at).toLocaleDateString()}</p>
      </div>

      <div class="panel" style="padding:clamp(22px,3.5vw,32px);">
        <h2 class="hud" style="font-size:12px;margin:0 0 12px;color:var(--cyan-300);">What Came Back</h2>
        ${(timeline.insights || []).length
          ? timeline.insights.map(i => `<p style="margin:0 0 10px;line-height:1.55;"><strong style="color:var(--cyan-100);">${Evoke.escapeHtml(i.category || "Insight")} from ${Evoke.escapeHtml(i.source)}:</strong> ${Evoke.escapeHtml(i.text)}</p>`).join("")
          : `<p class="empty-state" style="margin:0;">No insights recorded.</p>`}
      </div>

      <div class="panel" style="padding:clamp(22px,3.5vw,32px);">
        <h2 class="hud" style="font-size:12px;margin:0 0 12px;color:var(--cyan-300);">What You Earned ${Evoke.signal ? Evoke.signal.nodeHtml("vault") : ""}</h2>
        ${missionAwards.length
          ? missionAwards.map(a => `<span class="award" data-tier="${a.tier}" style="display:inline-flex"><span class="award__tier">${a.tier}</span></span>`).join(" ")
          : `<p class="empty-state" style="margin:0;">No awards yet for this mission.</p>`}
      </div>

      <div style="display:flex;gap:14px;flex-wrap:wrap;">
        <a class="btn sec" href="#/">◀ Back to Operations Hub</a>
        <a class="btn" href="#/mission/${missionId}">Strengthen &amp; Resubmit ▶</a>
      </div>
    </div>
  `);
  Evoke.signal?.bindNodes();
};

/* The Campaign Map — the concise "what done means" infographic
   (BUILD_PLAN_2 §2-3): the whole experience as the Basin's pipeline. One
   node per instructor-configured stage: a completion ring (100% = every
   mission in the stage submitted) + a quality grade (★ submitted /
   ★★ AI-strengthened / ★★★ teacher-honored — the MIN across the stage,
   so upgrading your weakest mission visibly raises the grade). Basin
   quests appear only once Minecraft is linked. */
Evoke.screens.campaignMap = async function campaignMap() {
  const { api, state, mount } = Evoke;
  const [map, world, gearRes] = await Promise.all([
    api.progressMap(state.userId),
    api.worldState().catch(() => null),
    api.gear(state.userId).catch(() => null),
  ]);
  Evoke.kit?.visit("basin");
  const TIER_NAME = { 1: "common", 2: "epic", 3: "legendary" };

  // Forward visibility (console-UX gap #3): a season pass always shows the
  // next reward before you earn it. The rank half is deterministic (the XP
  // curve is fixed); the gear half is gear.js's pick_next_unlock -- the
  // lowest-level locked, non-secret item in the catalog.
  const profile = state.profile;
  const nextUnlock = gearRes && gearRes.next_unlock;
  const nextRankLine = profile && profile.next_level_xp
    ? `<p>🎖 Next Rank: <strong>${Evoke.escapeHtml(profile.next_rank_title)}</strong> at ${profile.next_level_xp} XP <span class="empty-state">(${profile.next_level_xp - profile.xp} to go)</span></p>`
    : "";
  const nextGearLine = nextUnlock
    ? `<p>${nextUnlock.icon} Next Unlock: <strong>${Evoke.escapeHtml(nextUnlock.name)}</strong> <span class="empty-state">— ${Evoke.escapeHtml(nextUnlock.hint)}</span></p>`
    : "";
  const nextUnlockCard = (nextRankLine || nextGearLine) ? `
    <div class="glass" id="next-unlock-card" style="padding:22px 24px;">
      <span class="ev-label">Coming Up</span>
      ${nextRankLine}
      ${nextGearLine}
    </div>
  ` : "";

  mount(`
    <div style="display:flex;flex-direction:column;gap:24px;">
      <div class="row-between">
        <h1 class="glow-h" style="font-size:clamp(30px,5vw,52px);margin:0;">Campaign Map</h1>
        <span class="chip">${map.stages_complete}/${map.stages_total} STAGES DONE</span>
      </div>

      <div class="glass" style="padding:clamp(22px,3.5vw,30px);">
        <span class="ev-label">What done means</span>
        <p><strong>Submitted</strong> = the mission counts (<span class="award__tier" style="background:var(--tier-common);color:var(--color-text)">common</span>). <strong>AI-strengthened</strong> = <span class="award__tier" style="background:var(--tier-epic)">epic</span>. <strong>Teacher-honored</strong> = <span class="award__tier" style="background:var(--tier-legendary)">legendary</span>.</p>
        <p>A stage is <strong>DONE</strong> when its ring closes — 100% of its missions submitted. Its <strong>GRADE</strong> (★ to ★★★) is your weakest mission's tier: strengthen and resubmit any mission to raise it. Quests and Training sims never gate anything — they're how agents get sharper.</p>
      </div>

      ${nextUnlockCard}

      <div class="pipeline">
        ${map.stages.map((s, i) => `
          <div class="pipeline__segment ${s.complete ? "is-complete" : ""}">
            <div class="stage-node ${s.complete ? "is-complete" : (s.completed ? "is-partial" : "")}">
              <svg viewBox="0 0 44 44" class="stage-ring" aria-hidden="true">
                <circle cx="22" cy="22" r="19" class="stage-ring__bg"/>
                <circle cx="22" cy="22" r="19" class="stage-ring__fill"
                        stroke-dasharray="${(s.pct / 100) * 119.4} 119.4" transform="rotate(-90 22 22)"/>
              </svg>
              <span class="stage-node__num">${s.stage}</span>
            </div>
            <div class="stage-node__label">
              <strong>Stage ${s.stage}</strong> · ${s.completed}/${s.total}
              ${s.grade ? `<span class="stage-grade">${s.grade}</span>` : ""}
            </div>
            <div class="stage-node__missions">
              ${s.missions.map(m => `
                <a class="stage-mission ${m.submitted ? "is-done" : (m.released ? "" : "is-locked")}"
                   ${m.released || m.submitted ? `href="#/mission/${m.id}${m.submitted ? "/vault" : ""}"` : ""}
                   title="${Evoke.escapeHtml(m.title)}${m.best_tier_rank ? " · best: " + TIER_NAME[m.best_tier_rank] : ""}">
                  ${m.released || m.submitted ? "" : "🔒 "}${Evoke.escapeHtml(m.title)}
                  ${m.best_tier_rank ? `<span class="award__tier" data-t="${TIER_NAME[m.best_tier_rank]}" style="background:var(--tier-${TIER_NAME[m.best_tier_rank]})${m.best_tier_rank === 1 ? ";color:var(--color-text)" : ""}">${TIER_NAME[m.best_tier_rank]}</span>` : ""}
                  ${m.quest ? `<span class="stage-quest ${m.quest.done ? "is-done" : ""}" title="Basin quest: ${Evoke.escapeHtml(m.quest.title)}">⛏️${m.quest.done ? " ✔" : ""}</span>` : ""}
                </a>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </div>

      ${!map.minecraft_linked ? `
        <div class="panel" style="padding:clamp(20px,3vw,26px);">
          <div class="hud" style="font-size:11px;margin-bottom:8px;color:var(--cyan-300);">Basin telemetry offline</div>
          <p class="empty-state" style="margin:0;">Each stage also has an optional Basin Simulation quest — connect your Minecraft account from your Field Kit (scan the QR on Now) to reveal them here. <a href="#/faq" style="color:var(--cyan-300);">How do I connect? →</a></p>
        </div>
      ` : ""}

      ${world ? `
        <section class="glass world-meter" style="padding:clamp(22px,3.5vw,30px);">
          <span class="ev-label">And the whole cohort together — Keel Restoration</span>
          <div class="row-between" style="margin-top:8px;">
            <h2 style="font-family:var(--font-display);font-weight:700;color:var(--text-heading);margin:0;">Stage ${world.stage}: ${Evoke.escapeHtml(world.current.title)}</h2>
            <span class="empty-state">${world.completions} mission logs banked</span>
          </div>
          <p class="world-meter__narrative">${Evoke.escapeHtml(world.current.narrative)}</p>
          <div class="world-meter__track">
            <div class="world-meter__fill" style="width:${Math.round((world.stage / world.total_stages) * 100)}%"></div>
            ${world.stages.slice(1).map((s, i) => `
              <span class="world-meter__tick ${world.stage > i ? "is-reached" : ""}"
                    style="left:${((i + 1) / world.total_stages) * 100}%"
                    title="Stage ${i + 1}: ${Evoke.escapeHtml(s.title)}"></span>
            `).join("")}
          </div>
        </section>
      ` : ""}
    </div>
  `);
};

// Story — the showcase's "Agent Transmission" narrative device, rebuilt from
// its literal markup.
Evoke.screens.story = async function story() {
  const { api, state, mount } = Evoke;
  const missionsRes = await api.missions(state.userId).catch(() => ({ missions: [] }));
  const nextMission = (missionsRes.missions || []).find(m => missionState(m, state.profile) === "available");
  const acceptHref = nextMission ? `#/mission/${nextMission.id}` : "#/ops";
  mount(`
    <main style="max-width:1000px;margin:0 auto;width:100%;display:flex;flex-direction:column;justify-content:center;min-height:82vh;padding:32px clamp(20px,6vw,80px) 40px;">
      <h1 class="sr-only">Agent Transmission</h1>
      <div class="tx-device anim">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 16px 12px 14px;border-bottom:1px solid var(--border-ui);gap:12px;flex-wrap:wrap;position:relative;z-index:5;">
          <button class="tx-back" id="tx-back" type="button" aria-label="Go back to the previous screen"><span class="ms" aria-hidden="true">arrow_back</span>Back</button>
          <span style="display:flex;align-items:center;gap:10px;min-width:0;"><span class="ms" aria-hidden="true" style="font-size:20px;color:var(--cyan-300);">sensors</span><span class="hud" style="font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">AGENT // FIELD LOG</span></span>
        </div>
        <div style="display:flex;gap:0;align-items:stretch;flex-wrap:wrap;height:min(58vh,500px);">
          <div style="flex:0 0 clamp(190px,26vw,320px);position:relative;background:radial-gradient(110% 90% at 45% 0%,rgba(0,150,136,0.22),rgba(4,16,34,0.45));display:flex;align-items:flex-end;justify-content:center;overflow:hidden;">
            <img src="img/home-hero-char.png" alt="The Agent, transmitting from the field." style="height:100%;max-width:100%;width:auto;object-fit:contain;object-position:bottom center;filter:drop-shadow(0 0 30px rgba(0,150,136,0.3));">
            <div class="tx-portrait-fade" aria-hidden="true"></div>
          </div>
          <div class="anim" style="flex:1;min-width:280px;padding:clamp(22px,4vw,34px);height:100%;overflow:auto;">
            <p style="font-family:var(--font-display);font-weight:700;font-size:clamp(20px,3vw,24px);color:var(--cyan-200);margin:0 0 22px;">Your Mission</p>
            <p style="font-family:var(--font-body);font-size:16px;line-height:1.7;color:var(--teal-050);margin:0 0 18px;">If you want to understand this challenge—really understand it—you have to step into it. Not as yourself. As them.</p>
            <p style="font-family:var(--font-body);font-size:16px;line-height:1.7;color:var(--teal-050);margin:0 0 18px;">And stay curious: ask good questions before jumping to conclusions.</p>
            <p style="font-family:var(--font-display);font-weight:700;font-size:clamp(22px,3vw,28px);line-height:1.35;color:var(--cyan-500);text-shadow:0 0 20px rgba(0,150,136,0.4);margin:10px 0 0;">Listen. Not for data. For truth.</p>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-top:1px solid var(--border-ui);gap:14px;flex-wrap:wrap;">
          <span style="display:flex;align-items:center;gap:8px;font-family:var(--font-mono);font-size:13px;letter-spacing:.08em;color:var(--green-400);"><span class="tx-pulse" style="background:var(--green-400);box-shadow:0 0 10px var(--green-400);" aria-hidden="true"></span>Transmission Stable</span>
          <button class="btn" id="tx-next" type="button">Accept the Mission ▶<span class="key" aria-hidden="true"></span></button>
        </div>
      </div>
    </main>
  `);
  document.getElementById("tx-back")?.addEventListener("click", () => history.back());
  document.getElementById("tx-next")?.addEventListener("click", () => { location.hash = acceptHref; });
};

// The Vault — the showcase's archive grid of completed missions (each card
// opens the per-mission recap). Rebuilt from the showcase's literal markup.
Evoke.screens.vaultGrid = async function vaultGrid() {
  const { api, state, mount } = Evoke;
  const [missionsRes] = await Promise.all([api.missions(state.userId)]);
  Evoke.kit?.visit("cap");
  const profile = state.profile || {};
  const missions = missionsRes.missions || [];
  const lvl = profile.level || 1, xp = profile.xp || 0, nextXp = profile.next_level_xp;
  const xpPct = nextXp ? Math.min(100, Math.round(xp / nextXp * 100)) : 100;
  const completed = missions.filter(m => missionState(m, profile) === "complete");

  mount(`
    <main style="max-width:1280px;margin:0 auto;width:100%;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:8px;">
        <h1 class="glow-h" style="font-size:clamp(34px,6vw,64px);margin-left:-4px;">The Vault</h1>
        <div class="agent-hdr">
          <div style="text-align:right;">
            <div class="hud" style="font-size:12px;color:var(--cyan-300);margin-bottom:6px;">Agent Level ${lvl}</div>
            <div style="display:flex;align-items:center;gap:10px;"><span style="width:120px;height:7px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;display:inline-block;"><span style="display:block;height:100%;width:${xpPct}%;background:linear-gradient(90deg,var(--cyan-500),var(--green-400));"></span></span><span class="hud" style="font-size:11px;color:var(--text-faint);">${xp} / ${nextXp || xp} XP</span></div>
          </div>
          <span class="mtile" style="width:48px;height:48px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;"><span class="ms fill" aria-hidden="true" style="font-size:26px;">person</span></span>
        </div>
      </div>
      <p style="font-family:var(--font-body);font-size:17px;color:var(--text-faint);margin:0 0 36px;max-width:620px;">Every assignment you've completed, archived for review. Revisit a mission to study your choices and the badge you earned.</p>
      <div style="height:190px;border-radius:14px;overflow:hidden;margin:6px 0 30px;box-shadow:var(--elev-glass),inset 0 0 0 1px var(--border-ui);"><img src="img/home-hero-bg.jpg" alt="Progress through purpose." style="display:block;width:100%;height:100%;object-fit:cover;object-position:center;"></div>
      <div class="vault-grid" id="vault">
        ${completed.length ? completed.map(m => `
          <a class="glass vault-card" href="#/mission/${m.id}/vault" style="text-decoration:none;">
            <div class="vault-photo" style="background-image:url('img/home-hero-bg.jpg');"></div>
            <div style="padding:18px 20px;">
              <div class="hud" style="font-size:11px;color:var(--cyan-300);margin-bottom:6px;">Week ${m.week} · ${Evoke.escapeHtml(m.arc)}</div>
              <div style="font-family:var(--font-display);font-weight:700;font-size:17px;color:var(--text-heading);line-height:1.15;">${Evoke.escapeHtml(m.title)}</div>
            </div>
          </a>
        `).join("") : `<div class="glass" style="padding:34px;text-align:center;grid-column:1/-1;"><span class="ms" aria-hidden="true" style="font-size:36px;color:var(--text-faint);">inventory_2</span><p style="font-family:var(--font-body);font-size:15px;color:var(--text-faint);margin:12px 0 0;">No missions archived yet. Complete a mission and it will appear here for review.</p></div>`}
      </div>
    </main>
  `);
};

// Operations Hub — the showcase's mission dashboard, rebuilt from its literal
// markup and wired to live mission/profile/achievement data.
Evoke.screens.ops = async function ops() {
  const { api, state, mount } = Evoke;
  const [missionsRes, achievementsRes] = await Promise.all([
    api.missions(state.userId),
    api.achievements(state.userId).catch(() => ({ qualities: {} })),
  ]);
  Evoke.kit?.visit("spout");
  const missions = missionsRes.missions || [];
  const profile = state.profile || {};
  const lvl = profile.level || 1, xp = profile.xp || 0, nextXp = profile.next_level_xp;
  const xpPct = nextXp ? Math.min(100, Math.round((xp / nextXp) * 100)) : 100;
  const nextMission = missions.find(m => missionState(m, profile) === "available");
  const allDone = missions.length > 0 && missions.every(m => missionState(m, profile) === "complete");
  const curWeek = nextMission ? nextMission.week : (allDone ? 6 : 1);
  const upcoming = missions.filter(m => missionState(m, profile) !== "complete");
  const nextNext = upcoming[1];
  const briefHref = nextMission ? `#/mission/${nextMission.id}` : "#/";

  const weekStates = [1, 2, 3, 4, 5, 6].map(w => {
    const wm = missions.filter(m => m.week === w);
    const st = wm.map(m => missionState(m, profile));
    if (wm.length && st.every(s => s === "complete")) return "done";
    if (w === curWeek) return "cur";
    return "";
  });
  const chapters = weekStates.map((s, i) => `<span class="chap-node ${s}" role="img" aria-label="Week ${i + 1}">${i + 1}</span>`).join('<span class="chap-line"></span>');

  const SUPERPOWERS = ["Empathetic Changemaker", "Systems Thinker", "Creative Visionary", "Deep Collaborator"];
  const qualities = achievementsRes.qualities || {};
  const spRows = SUPERPOWERS.map(name => {
    const q = qualities[name] || {};
    const earned = !!q.earned;
    const pct = earned ? 100 : (q.pct != null ? q.pct : (q.progress != null ? q.progress : 0));
    const pips = Math.max(0, Math.min(3, Math.round(pct / 100 * 3)));
    return `<div style="display:flex;align-items:center;gap:12px;padding:10px 13px;border-radius:11px;box-shadow:inset 0 0 0 1px var(--border-ui);${earned ? "" : "opacity:0.5;"}"><span class="ms" aria-hidden="true" style="font-size:22px;flex:none;color:${earned ? "var(--cyan-300)" : "var(--text-faint)"};">${earned ? "military_tech" : "lock"}</span><div style="flex:1;min-width:0;"><div style="font-family:var(--font-display);font-weight:700;font-size:13px;color:var(--teal-050);line-height:1.15;">${Evoke.escapeHtml(name)}</div><div style="display:flex;gap:4px;margin-top:6px;">${[0, 1, 2].map(i => `<span style="width:13px;height:5px;border-radius:3px;display:inline-block;background:${i < pips ? "linear-gradient(90deg,var(--cyan-300),var(--cyan-500))" : "rgba(145,209,209,0.16)"};"></span>`).join("")}</div></div><span class="hud" style="font-size:10px;flex:none;color:var(--text-faint);">${earned ? "Earned" : "Locked"}</span></div>`;
  }).join("");

  const CHECKLIST = [
    { ic: "directions_walk", t: "Walk in Their World" },
    { ic: "join_inner", t: "Find the Friction" },
    { ic: "account_tree", t: "Name the Challenge" },
    { ic: "cloud_upload", t: "Submit your findings" },
  ];

  mount(`
    <main style="max-width:1280px;margin:0 auto;width:100%;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:24px;">
        <div>
          <h1 class="glow-h" style="font-size:clamp(34px,6vw,64px);margin:0 0 8px -8px;">Operations Hub</h1>
          <p style="font-family:var(--font-body);font-size:17px;color:var(--text-faint);margin:0;max-width:620px;">Your home base for missions, progress, and the Prosperity story.</p>
        </div>
        <div class="agent-hdr">
          <div style="text-align:right;">
            <div class="hud" style="font-size:12px;color:var(--cyan-300);margin-bottom:6px;">Agent Level ${lvl}</div>
            <div style="display:flex;align-items:center;gap:10px;"><span style="width:120px;height:7px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;display:inline-block;"><span style="display:block;height:100%;width:${xpPct}%;background:linear-gradient(90deg,var(--cyan-500),var(--green-400));"></span></span><span class="hud" style="font-size:11px;color:var(--text-faint);">${xp} / ${nextXp || xp} XP</span></div>
          </div>
          <span class="mtile" style="width:48px;height:48px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;"><span class="ms fill" aria-hidden="true" style="font-size:26px;">person</span></span>
        </div>
      </div>

      <div class="ops-top">
        <div class="ops-banner">
          <div class="bg" style="background-image:url('img/home-hero-bg.jpg');"></div>
          <div class="tint"></div>
          <div>
            <div class="hud" style="font-size:12px;color:var(--cyan-300);margin-bottom:10px;">Active Mission</div>
            <h2 style="font-family:var(--font-display);font-weight:800;font-size:clamp(24px,3.4vw,34px);color:var(--text-heading);margin:0 0 12px;line-height:1.05;">${nextMission ? Evoke.escapeHtml(nextMission.title) : (allDone ? "All missions complete" : "Standing by")}</h2>
            <p style="font-family:var(--font-body);font-size:15px;line-height:1.55;color:var(--teal-050);margin:0;max-width:460px;">${nextMission ? Evoke.escapeHtml(nextMission.brief || "") : "New missions coming soon."}</p>
          </div>
          <div style="margin-top:22px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:16px;"><span style="width:9px;height:9px;border-radius:50%;background:${nextMission ? "var(--cyan-300)" : "var(--text-faint)"};"></span><span class="hud" style="font-size:12px;color:var(--text-faint);">Status: ${nextMission ? "In Progress" : (allDone ? "Complete" : "Not Started")}</span></div>
            ${nextMission ? `<button id="ops-brief" class="btn sec" type="button" style="padding:8px 16px;font-size:13px;"><span class="ms" aria-hidden="true" style="font-size:16px;vertical-align:middle;">menu_book</span>&nbsp;Re-read the brief</button>` : ""}
          </div>
        </div>
        <div class="glass" style="padding:clamp(18px,2.5vw,24px);">
          <h3 class="hud" style="font-size:12px;color:var(--cyan-300);margin:0 0 14px;">Story Progress</h3>
          <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:18px;">
            <span class="ch-thumb" style="width:96px;height:72px;display:flex;align-items:center;justify-content:center;" aria-hidden="true"><span class="ms" style="font-size:34px;">auto_stories</span><span class="num">${String(curWeek).padStart(2, "0")}</span></span>
            <div><div style="font-family:var(--font-display);font-weight:700;font-size:18px;color:var(--text-heading);">Chapter ${curWeek}: In Progress</div><div style="font-family:var(--font-body);font-size:14px;color:var(--teal-100);margin-bottom:6px;">${nextMission ? Evoke.escapeHtml(nextMission.title) : "—"}</div></div>
          </div>
          <div style="display:flex;align-items:center;justify-content:center;gap:0;margin-bottom:18px;">${chapters}</div>
          <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;"><div><div style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--cyan-300);margin-bottom:4px;">${nextNext ? Evoke.escapeHtml(nextNext.title) : "Campaign complete"}</div><div style="font-family:var(--font-body);font-size:13px;color:var(--text-faint);">Submit your findings to unlock the next chapter.</div></div><span class="ms" aria-hidden="true" style="color:var(--text-faint);">lock</span></div>
        </div>
      </div>

      <div class="ops-bottom">
        <div class="glass" style="padding:clamp(18px,2.5vw,24px);">
          <h3 class="hud" style="font-size:12px;color:var(--cyan-300);margin:0 0 14px;">Investigation Overview</h3>
          <div class="ops-ov-list">${CHECKLIST.map(c => `<div class="ops-chk"><span class="ic-tile" aria-hidden="true"><span class="ms">${c.ic}</span></span><span style="flex:1;font-family:var(--font-body);font-size:15px;color:var(--teal-050);line-height:1.35;">${c.t}</span></div>`).join("")}</div>
        </div>
        <div class="glass" style="padding:clamp(18px,2.5vw,24px);display:flex;flex-direction:column;">
          <h3 class="hud" style="font-size:12px;color:var(--cyan-300);margin:0 0 14px;">Go to Minecraft <span style="color:var(--text-faint);">· Optional</span></h3>
          <div class="ops-photo" style="border-radius:12px;box-shadow:inset 0 0 0 1px var(--border-ui);flex:1;min-height:150px;margin-bottom:14px;background:#0e2236;position:relative;overflow:hidden;">
            <img src="img/billbot-minecraft.png" alt="B1llbot in the Prosperity Minecraft world" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center top;">
          </div>
          <p style="font-family:var(--font-body);font-size:13px;line-height:1.5;color:var(--teal-100);margin:0 0 14px;">Optional practice space — explore the Prosperity Simulation of Keel. Your real-world fieldwork is what completes the mission.</p>
          <button id="ops-mc" class="btn sec" type="button" style="margin-top:auto;width:100%;">Go to Minecraft to talk with B1llbot&nbsp;<span class="ms" aria-hidden="true" style="font-size:16px;vertical-align:middle;">open_in_new</span></button>
        </div>
        <div class="glass" style="padding:clamp(18px,2.5vw,24px);">
          <h3 class="hud" style="font-size:12px;color:var(--cyan-300);margin:0 0 14px;">Superpowers</h3>
          <div style="display:flex;flex-direction:column;gap:10px;flex:1;justify-content:space-evenly;">${spRows}</div>
        </div>
      </div>

      <div class="glass" style="display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;padding:clamp(20px,3vw,30px);margin-top:22px;">
        <div style="display:flex;gap:18px;align-items:flex-start;flex:1;min-width:260px;">
          <span style="width:52px;height:52px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;background:rgba(0,150,136,0.12);color:var(--cyan-300);"><span class="ms" aria-hidden="true" style="font-size:26px;">assignment_turned_in</span></span>
          <div><div style="font-family:var(--font-display);font-weight:700;font-size:19px;text-transform:uppercase;color:var(--text-heading);margin-bottom:4px;">Ready to Report Back?</div><p style="font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--teal-100);margin:0;max-width:520px;">When you've completed your assignment and gathered your evidence, return to submit your findings, share your reflections, and unlock the next chapter.</p></div>
        </div>
        <button id="ops-submit" class="btn" type="button" style="min-width:240px;">Submit My Findings&nbsp;&nbsp;<span class="ms" aria-hidden="true" style="font-size:18px;vertical-align:middle;">arrow_forward</span></button>
      </div>

      <div class="glass" style="display:flex;align-items:center;gap:16px;padding:16px clamp(18px,2.5vw,24px);margin-top:18px;flex-wrap:wrap;">
        <span style="width:44px;height:44px;border-radius:50%;overflow:hidden;flex:none;box-shadow:0 0 0 1px var(--border-ui);background:#11243a;"><img src="img/billbot-avatar.png" alt="Alex" style="width:100%;height:100%;object-fit:contain;"></span>
        <span class="hud" style="font-size:12px;color:var(--cyan-300);flex:none;">Alex says:</span>
        <span style="font-family:var(--font-body);font-style:italic;font-size:14px;color:var(--teal-050);flex:1;min-width:200px;">“Listen. The reports only tell part of the story — the people who lived it know the rest.”</span>
      </div>
    </main>
  `);

  const go = (id, href) => document.getElementById(id)?.addEventListener("click", () => { location.hash = href; });
  go("ops-brief", briefHref);
  go("ops-submit", briefHref);
  go("ops-mc", "#/faq");
};

// Progress — the showcase's dedicated growth screen (Badge Collection, level
// ring, statistics), rebuilt from the showcase's literal markup.
Evoke.screens.progress = async function progress() {
  const { api, state, mount } = Evoke;
  const [profile, achievementsRes, reflectionsRes] = await Promise.all([
    api.playerProfile(state.userId),
    api.achievements(state.userId).catch(() => ({ qualities: {}, powers: {} })),
    api.reflections(state.userId).catch(() => ({ total: 0 })),
  ]);
  Evoke.kit?.visit("gauge");
  const lvl = profile.level, xp = profile.xp, nextXp = profile.next_level_xp;
  const xpPct = nextXp ? Math.min(100, Math.round((xp / nextXp) * 100)) : 100;
  const ringOffset = (326.726 * (1 - xpPct / 100)).toFixed(2);
  const SUPERPOWERS = ["Empathetic Changemaker", "Systems Thinker", "Creative Visionary", "Deep Collaborator"];
  const qualities = achievementsRes.qualities || {};
  const badges = SUPERPOWERS.map(name => {
    const q = qualities[name] || {};
    const earned = !!q.earned;
    const pctv = earned ? 100 : (q.pct != null ? q.pct : (q.progress != null ? q.progress : 0));
    return { name, earned, pips: Math.max(0, Math.min(3, Math.round((pctv / 100) * 3))) };
  });
  const spEarned = badges.filter(b => b.earned).length;
  const truths = reflectionsRes.total || 0;

  mount(`
    <main style="max-width:1280px;margin:0 auto;width:100%;">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;margin-bottom:30px;">
        <div>
          <h1 class="glow-h" style="font-size:clamp(26px,4.5vw,46px);margin:0 0 4px -4px;">Progress</h1>
          <p style="font-family:var(--font-body);font-size:14px;color:var(--text-faint);margin:0;">Track your growth, your badges, and your rank as you rise through the ranks, Agent.</p>
        </div>
        <div class="agent-hdr">
          <div style="text-align:right;">
            <div class="hud" style="font-size:12px;color:var(--cyan-300);margin-bottom:6px;">Agent Level ${lvl}</div>
            <div style="display:flex;align-items:center;gap:10px;"><span style="width:120px;height:7px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;display:inline-block;"><span style="display:block;height:100%;width:${xpPct}%;background:linear-gradient(90deg,var(--cyan-500),var(--green-400));"></span></span><span class="hud" style="font-size:11px;color:var(--text-faint);">${xp} / ${nextXp || xp} XP</span></div>
          </div>
          <span class="mtile" style="width:52px;height:52px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;"><span class="ms fill" aria-hidden="true" style="font-size:28px;">person</span></span>
        </div>
      </div>

      <div class="glass" style="padding:clamp(20px,2.4vw,28px);margin-bottom:26px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:12px;gap:14px;flex-wrap:wrap;">
          <div>
            <div class="hud" style="font-size:10px;color:var(--cyan-300);letter-spacing:.16em;margin-bottom:5px;">Achievements</div>
            <h2 style="font-family:var(--font-display);font-weight:800;font-size:clamp(16px,2.1vw,21px);color:var(--text-heading);margin:0;text-transform:uppercase;">Badge Collection</h2>
          </div>
          <span class="hud" style="font-size:12px;color:var(--text-muted);">${spEarned} of 4 superpowers</span>
        </div>
        <div id="pg-badges-all">
          ${badges.map(b => `
            <div class="pg-badge ${b.earned ? "" : "locked"}">
              <span class="pg-badge-ic"><span class="ms" aria-hidden="true">${b.earned ? "military_tech" : "lock"}</span></span>
              <div class="pg-badge-txt">
                <span class="pg-badge-name">${Evoke.escapeHtml(b.name)}</span>
                <span class="pg-badge-lvl">${b.earned ? "Earned" : "Locked · 3 missions"}</span>
                <span class="pg-pips" aria-hidden="true">${[0, 1, 2].map(i => `<span class="pip ${i < b.pips ? "on" : ""}"></span>`).join("")}</span>
              </div>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="glass" style="padding:clamp(20px,2.4vw,28px);margin-bottom:26px;position:relative;overflow:hidden;">
        <img src="img/home-hero-bg.jpg" alt="" aria-hidden="true" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:75% 40%;z-index:0;opacity:0.5;">
        <div aria-hidden="true" style="position:absolute;inset:0;z-index:0;background:linear-gradient(90deg,rgba(13,21,40,0.94) 0%,rgba(13,21,40,0.82) 45%,rgba(13,21,40,0.55) 100%);"></div>
        <div class="pg-hero-grid" style="position:relative;z-index:1;">
          <div class="pg-ring" style="width:112px;height:112px;flex:none;">
            <svg viewBox="0 0 120 120" aria-hidden="true"><circle class="ring-bg" cx="60" cy="60" r="52"></circle><circle class="ring-fg" cx="60" cy="60" r="52" style="stroke-dasharray:326.726;stroke-dashoffset:${ringOffset};"></circle></svg>
            <div class="pg-ring-mid"><div class="pg-ring-pct" style="font-size:25px;">${xpPct}%</div><div class="pg-ring-lbl">to Lv.${lvl + 1}</div></div>
          </div>
          <div style="flex:1;min-width:250px;">
            <div class="hud" style="font-size:11px;color:var(--cyan-300);margin-bottom:6px;letter-spacing:.14em;">Current Rank</div>
            <div style="font-family:var(--font-display);font-weight:800;font-size:clamp(18px,2.2vw,24px);color:var(--text-heading);line-height:1.05;">Level ${lvl} · ${Evoke.escapeHtml(profile.rank_title || "Recruit")}</div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin:12px 0 7px;gap:12px;flex-wrap:wrap;">
              <span class="hud" style="font-size:11px;color:var(--text-muted);">XP to Next Level</span>
              <span class="hud" style="font-size:11px;color:var(--text-muted);">${nextXp ? `${nextXp} XP · Lv.${lvl + 1}` : "MAX"}</span>
            </div>
            <div class="track" role="progressbar" aria-valuenow="${xp}" aria-valuemin="0" aria-valuemax="${nextXp || xp}"><div class="fill-xp" style="width:${xpPct}%;"></div><div class="knob" style="left:${xpPct}%;"></div></div>
            <div style="margin-top:10px;font-family:var(--font-mono);font-size:12px;"><span style="color:var(--text-label);">${xp} XP</span></div>
          </div>
        </div>
      </div>

      <div class="glass" style="padding:clamp(20px,2.4vw,28px);">
        <h2 class="hud" style="font-size:13px;margin:0 0 16px;">Your Statistics</h2>
        <div id="pg-stats">
          ${[
            { ic: "rocket_launch", n: profile.missions_completed_count || 0, l: "Missions Complete" },
            { ic: "military_tech", n: spEarned, l: "Badges Earned" },
            { ic: "workspace_premium", n: lvl, l: "Agent Level" },
            { ic: "format_quote", n: truths, l: "Truths Recorded" },
          ].map(s => `<div class="pg-stat"><div class="pg-stat-ic"><span class="ms fill" aria-hidden="true">${s.ic}</span></div><div class="pg-stat-txt"><div class="pg-stat-num">${s.n}</div><div class="pg-stat-lbl">${s.l}</div></div></div>`).join("")}
        </div>
      </div>
    </main>
  `);
};

/* FAQ — the connect-to-Basin instructions live inline in the Field Kit
   flow AND here, per Nathan's spec. */
Evoke.screens.faq = async function faq() {
  const { api, mount } = Evoke;
  const info = await api.minecraftConnectInfo().catch(() => null);
  mount(`
    <div class="stack">
      <h1 class="glow-h" style="font-size:clamp(30px,5vw,52px);margin:0 0 8px;">FAQ</h1>

      <div class="card">
        <div class="card__eyebrow">How do I connect to the Basin Simulation (Minecraft)?</div>
        <ol class="faq-steps">
          <li><strong>Open your Field Kit</strong> on your phone — scan the QR code on the Now page. It registers you automatically.</li>
          <li>Tap <strong>Connect to Basin Simulation</strong>. You'll get the server address and a 4-digit link code.</li>
          <li>In Minecraft (Java or Bedrock), add a multiplayer server:${info ? `<br>Java: <code>${Evoke.escapeHtml(info.java_address)}</code> · Bedrock: <code>${Evoke.escapeHtml(info.bedrock_address)}</code>` : ""}</li>
          <li>Join the world and find B1llbot's secret kiosk near the starter villagers, close to spawn — he'll whisper hello the first time. Right there, type in chat: <code>/trigger evoke_link set YOUR-CODE</code></li>
          <li>Your Field Kit pops a confirmation — tap <strong>Confirm</strong>. Done: rewards, quests, and XP now flow between the Basin and your account.</li>
        </ol>
      </div>

      <div class="card">
        <div class="card__eyebrow">Do I have to play Minecraft?</div>
        <p>No. The Basin Simulation is optional and never graded — every mission is completable entirely on the web. The Basin is extra ways to explore the same world.</p>
      </div>

      <div class="card">
        <div class="card__eyebrow">What does "done" mean?</div>
        <p>See the <a href="#/map">Campaign Map</a> — a stage is done at 100% of its missions submitted; its grade (★–★★★) reflects your award tiers, and you can always strengthen and resubmit.</p>
      </div>

      <div class="card">
        <div class="card__eyebrow">What's a Field Report?</div>
        <p>Once a day, tell B1llbot what you did or what you're thinking — one line is enough. He answers with a word of wisdom; both collect in the Wisdom Journal on your Dossier. Ten reports unlocks the Transformation Power.</p>
      </div>
    </div>
  `);
};
