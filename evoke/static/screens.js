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
    <div class="stack celebration-screen">
      <div class="card celebration-card">
        <span class="chip chip--green" style="margin-bottom:var(--space-3)"><span class="dot"></span>System Online · ID: EVOKE</span>
        <div class="card__eyebrow">Case File — Basin Region</div>
        <h1>Welcome to Keel</h1>
        <p>The water's scarce here. The power's unstable. But the people get by on something the mountain above them ran out of a long time ago: each other.</p>
        <p>You're the newest Agent assigned to this case, ${Evoke.escapeHtml(state.displayName || "Agent")}. B1llbot's expecting you — he's the one in the corner who won't stop talking about pipes.</p>
        <button class="btn btn-primary" id="welcome-continue">Review the Records →</button>
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
  const [missionsRes, notifRes, activityRes, checkinRes, mcLink, mcConnect, world, mcStatus, companion, reflections, progressMap] = await Promise.all([
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
      <div class="fieldkit-qr"><img src="/api/companion/qr.svg?user_id=${state.userId}" alt="QR code to the Companion Field Kit"></div>
      <p class="empty-state">${companion.scannable
        ? "Scan to open your Field Kit — it registers your phone as you automatically (no login). Daily field reports, Basin linking, quests, and B1llbot from the field."
        : "Open this site from your machine's LAN IP (not localhost) and this QR becomes scannable from your phone."}</p>
    </div>
  ` : "";

  mount(`
    <div class="stack">
    ${worldStrip}
    <div class="hub-layout">
      <div class="stack">
        ${showGuide ? `
          <section class="card" id="hub-guide">
            <div class="card__eyebrow">Orientation</div>
            <p><strong>Now</strong> — your next action, always first. <strong>Campaign Map</strong> — the whole experience and what done means. <strong>Story</strong> — the graphic novel. <strong>Cohort</strong> — everyone's work and the live feed. <strong>Field Ops</strong> — the optional Basin Simulation (Minecraft) and Training sims. <strong>Dossier</strong> — who you are.</p>
            <button class="btn" id="hub-guide-dismiss">Got it</button>
          </section>
        ` : ""}
        <section class="hub-hero" data-arc="${nextMission ? nextMission.arc : ""}">
          <div class="hub-hero__ghost" aria-hidden="true">${nextMission ? String(nextMission.week).padStart(2, "0") : (allDone ? "✓" : "—")}</div>
          <div class="hub-hero__body">
            <div class="card__eyebrow">${nextMission ? `Week ${nextMission.week} · ${nextMission.arc}` : "Now"}</div>
            ${nextMission
              ? `<h2 class="hub-hero__title">${Evoke.escapeHtml(nextMission.title)}</h2>
                 <p class="hub-hero__sub">${completedCount}/12 missions complete · ${pendingAwards.length} pending award${pendingAwards.length === 1 ? "" : "s"}</p>
                 <a class="btn btn-primary btn-hero" href="#/mission/${nextMission.id}">Open Mission Brief →</a>`
              : allDone
                ? `<h2 class="hub-hero__title">All released missions complete</h2>
                   <p class="hub-hero__sub">New chapters coming soon.</p>`
                : `<h2 class="hub-hero__title">Standing by</h2>
                   <p class="hub-hero__sub">Waiting on your instructor to release the next mission.</p>`}
            ${checkinLine ? `<p class="empty-state" style="margin-top:var(--space-2)">${checkinLine}</p>` : ""}
          </div>
        </section>

        ${fieldReportCard}
        ${myMapStrip}

        <section>
          <h2 class="section-title">Mission Board</h2>
          <div class="mission-board">
            ${ARC_ORDER.map(arc => `
              <div class="arc-column">
                <div class="arc-column__title">${arc}</div>
                ${byArc[arc].map(m => {
                  const st = missionState(m, profile);
                  const locked = st === "locked";
                  const dest = st === "complete" ? `#/mission/${m.id}/vault` : `#/mission/${m.id}`;
                  return `
                  <a class="mission-card" data-state="${st}" ${locked ? "" : `href="${dest}"`}>
                    <span class="mission-card__arc" data-arc="${m.arc}">${m.arc}</span>
                    <div class="mission-card__title">${locked ? "🔒 " : ""}${Evoke.escapeHtml(m.title)}</div>
                    <div class="mission-card__meta">Week ${m.week} · ${locked ? "not yet released" : st}</div>
                  </a>
                `;
                }).join("") || `<p class="empty-state">—</p>`}
              </div>
            `).join("")}
          </div>
        </section>

        <section class="card">
          <div class="card__eyebrow">Feed — what's happening across the cohort</div>
          ${activity.length
            ? activity.map(a => `
                <div class="feed-item" data-tier="${a.tier || ""}">
                  ${a.tier ? `<span class="award__tier">${a.tier}</span> ` : ""}
                  ${Evoke.escapeHtml(a.message)}
                  <span class="empty-state"> · ${timeAgo(a.timestamp)}</span>
                </div>
              `).join("")
            : `<p class="empty-state">Nothing yet — the first submission of the campaign will show up here.</p>`}
        </section>
      </div>

      <aside class="stack">
        <div class="card">
          <div class="card__eyebrow">Agent</div>
          <p>${Evoke.escapeHtml(state.displayName || "Agent")}</p>
          <p>Level ${profile ? profile.level : 1} · ${profile ? profile.xp : 0} XP</p>
          <a class="btn" href="#/profile">View Profile</a>
        </div>
        ${presenceCard}
        ${fieldKitCard}
        <div class="card">
          <div class="card__eyebrow">Team</div>
          <p class="empty-state">No "my team" lookup exists yet — open a team profile directly at #/team/&lt;id&gt;.</p>
        </div>
        <div class="card" id="mc-connect-card">
          <div class="card__eyebrow">Basin Simulation — optional</div>
          ${mcLink && mcLink.linked
            ? `<p>Linked as <strong>${Evoke.escapeHtml(mcLink.username)}</strong></p>`
            : `<p class="empty-state">Not linked yet — you can still connect and explore.</p>`}
          ${mcConnect ? `
            <p style="margin-top:var(--space-2)">Java: <code id="mc-java-addr">${Evoke.escapeHtml(mcConnect.java_address)}</code>
              <button class="btn" data-copy="${Evoke.escapeHtml(mcConnect.java_address)}" style="margin-left:var(--space-2)">Copy</button></p>
            <p>Bedrock: <code id="mc-bedrock-addr">${Evoke.escapeHtml(mcConnect.bedrock_address)}</code>
              <button class="btn" data-copy="${Evoke.escapeHtml(mcConnect.bedrock_address)}" style="margin-left:var(--space-2)">Copy</button></p>
            <p class="empty-state" style="margin-top:var(--space-2)">Add as a server (Java) or a Bedrock friend server, using the address above.</p>
          ` : `<p class="empty-state">Server address unavailable right now.</p>`}
        </div>
      </aside>
    </div>
    </div>
  `);

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
  let manifest;
  try {
    manifest = await fetch("content/chapters.json").then(r => r.json());
  } catch (e) {
    mount(`<div class="card"><p class="empty-state">No graphic novel content configured yet.</p></div>`);
    return;
  }

  // Mission IDs are generated UUIDs from the LMS sync, not something a
  // static manifest can hardcode -- resolve each chapter's CTA target by
  // position instead (2 missions/week/chapter, missions already returned in
  // week/sequence order by /api/missions).
  const missionsRes = await api.missions(state.userId).catch(() => ({ missions: [] }));
  const missions = missionsRes.missions || [];

  const completedCount = (state.profile && state.profile.missions_completed_count) || 0;
  // 2 missions/week cadence -> chapter N unlocks once 2*(N-1) missions are done.
  const chapters = manifest.chapters.map((c, i) => ({
    ...c, locked: completedCount < i * 2, ctaMission: missions[i * 2],
  }));

  let currentIndex = chapters.map(c => !c.locked).lastIndexOf(true);
  if (currentIndex === -1) currentIndex = 0;
  let panelIndex = 0;

  function renderChapter() {
    const chapter = chapters[currentIndex];
    const panel = chapter.panels[panelIndex];
    const isLast = panelIndex === chapter.panels.length - 1;
    Evoke.mount(`
      <div class="stack">
        <div class="chapter-rail">
          ${chapters.map((c, i) => `
            <a class="chapter-chip ${i === currentIndex ? "is-current" : ""}"
               data-state="${c.locked ? "locked" : "unlocked"}"
               data-chapter-index="${i}" href="#">${c.locked ? "🔒 " : ""}${Evoke.escapeHtml(c.title)}</a>
          `).join("")}
        </div>
        <div class="novel-panel">
          <div>
            <div style="font-size:var(--text-lg)">[ ${Evoke.escapeHtml(panel.image_slot || "panel art")} ]</div>
            <p>${Evoke.escapeHtml(panel.caption)}</p>
          </div>
        </div>
        <div class="row-between">
          <button id="novel-prev" ${panelIndex === 0 ? "disabled" : ""}>← Back</button>
          <span class="empty-state">Panel ${panelIndex + 1} / ${chapter.panels.length} ${Evoke.signal ? Evoke.signal.nodeHtml("novel") : ""}</span>
          ${isLast
            ? (chapter.ctaMission
                ? `<a class="btn btn-primary" href="#/mission/${chapter.ctaMission.id}">Open Mission Brief →</a>`
                : `<a class="btn btn-primary" href="#/">Back to Operations Hub →</a>`)
            : `<button id="novel-next">Next →</button>`}
        </div>
      </div>
    `);
    document.getElementById("novel-prev")?.addEventListener("click", () => { panelIndex--; renderChapter(); });
    document.getElementById("novel-next")?.addEventListener("click", () => { panelIndex++; renderChapter(); });
    Evoke.signal?.bindNodes();
    document.querySelectorAll("[data-chapter-index]").forEach(el => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        const i = Number(el.dataset.chapterIndex);
        if (chapters[i].locked) return;
        currentIndex = i; panelIndex = 0; renderChapter();
      });
    });
  }
  renderChapter();
};

Evoke.screens.missionBrief = async function missionBrief(missionId) {
  const { api, state, mount } = Evoke;
  const [missionsRes, timeline, mcLink, aarProfile, aarAchievements] = await Promise.all([
    api.missions(state.userId),
    api.timeline(state.userId, missionId).catch(() => null),
    api.minecraftLink(state.userId).catch(() => ({ linked: false })),
    api.playerProfile(state.userId).catch(() => null),
    api.achievements(state.userId).catch(() => null),
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
      <div class="stack">
        <div>
          <span class="mission-card__arc" data-arc="${mission.arc}">${mission.arc} · Week ${mission.week}</span>
          <h1>🔒 ${Evoke.escapeHtml(mission.title)}</h1>
        </div>
        <div class="card">
          <p class="empty-state">This mission hasn't been released yet. Check back once your instructor opens it.</p>
        </div>
        <a class="btn" href="#/">← Back to Operations Hub</a>
      </div>
    `);
    return;
  }

  mount(`
    <div class="stack">
      <div>
        <span class="mission-card__arc" data-arc="${mission.arc}">${mission.arc} · Week ${mission.week}</span>
        <h1>${Evoke.escapeHtml(mission.title)}</h1>
        <p>Builds toward: <strong>${Evoke.escapeHtml(mission.superpower || "—")}</strong></p>
      </div>

      ${timeline ? `
        <div class="card">
          <div class="card__eyebrow">Timeline</div>
          <div class="timeline-strip">
            ${(timeline.timeline || []).map(step => `
              <div class="timeline-step is-${step.status}">
                <div class="timeline-step__label">${Evoke.escapeHtml(step.label)}</div>
              </div>
            `).join("")}
          </div>
        </div>
      ` : ""}

      <div class="card">
        <div class="card__eyebrow">Mission Brief</div>
        <p>${Evoke.escapeHtml(mission.brief || "No brief text yet.").replace(/\n/g, "<br>")}</p>
      </div>

      ${mission.quest && mcLink.linked ? `
        <div class="quest-card">
          <div class="quest-card__eyebrow">Optional — Basin Simulation</div>
          <strong>${Evoke.escapeHtml(mission.quest.title)}</strong>
          <p>${Evoke.escapeHtml(mission.quest.description || "")}</p>
        </div>
      ` : (mission.quest ? `
        <div class="quest-card">
          <div class="quest-card__eyebrow">Basin telemetry offline</div>
          <p class="empty-state">This mission has an optional Basin Simulation quest — connect Minecraft from your Field Kit to reveal it. <a href="#/faq">How? →</a></p>
        </div>
      ` : "")}

      ${(() => {
        // Revise-and-resubmit is a visible, welcomed path (GAPS.md #3), not
        // a loophole: a prior submission changes the framing, never blocks.
        const alreadySubmitted = timeline && (timeline.timeline || []).some(s => s.id === "submitted" && s.status === "completed");
        return `
      <div class="card">
        <div class="card__eyebrow">${alreadySubmitted ? "Resubmit — strengthen your work" : "Submit Evidence"}</div>
        ${alreadySubmitted ? `<p class="empty-state">You've already completed this mission. A stronger resubmission can upgrade your award tier — your first take is never punished, and nothing you earned gets taken back.</p>` : ""}
        <form class="evidence-form" id="evidence-form">
          <input type="file" name="file" required>
          <label for="evidence-reflection">Field Note ${mission.superpower ? `— what did this mission teach you about being a ${Evoke.escapeHtml(mission.superpower)}?` : ""}</label>
          <textarea id="evidence-reflection" name="reflection" rows="3" placeholder="Optional — B1llbot reads these."></textarea>
          <button type="submit" class="btn btn-primary">${alreadySubmitted ? "Resubmit Evidence" : "Submit Mission Evidence"}</button>
        </form>
        <p id="evidence-status"></p>
      </div>`;
      })()}
    </div>
  `);

  document.getElementById("evidence-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const statusEl = document.getElementById("evidence-status");
    const fileInput = e.target.querySelector("input[type=file]");
    const reflectionInput = document.getElementById("evidence-reflection");
    if (!fileInput.files[0]) return;
    const formData = new FormData();
    formData.append("user_id", state.userId);
    formData.append("mission_id", missionId);
    formData.append("file", fileInput.files[0]);
    if (reflectionInput.value.trim()) formData.append("reflection", reflectionInput.value.trim());
    statusEl.textContent = "Submitting...";
    try {
      const res = await api.submitEvidence(formData);
      if (res.resubmission) {
        // No fresh-completion celebration for a resubmission -- toast the
        // upgrade path and land on the normal debrief instead.
        Evoke.toast("Resubmitted — the AI Coach is re-reviewing. Improvements can upgrade your award tier.");
        statusEl.textContent = "Resubmitted!";
        setTimeout(() => { location.hash = `#/mission/${missionId}/debrief`; }, 800);
      } else {
        statusEl.textContent = "Submitted!";
        setTimeout(() => { location.hash = `#/mission/${missionId}/debrief?fresh=1`; }, 800);
      }
    } catch (err) {
      statusEl.textContent = "Submission failed: " + err.message;
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
      <div class="stack celebration-screen">
        <div class="card celebration-card" data-tier="${freshAward ? freshAward.tier : "common"}">
          <div class="card__eyebrow">Mission Complete</div>
          <h1>${escapeHtml(mission.title)}</h1>
          <p>Logged. Every drop counts — even the small ones.</p>
          ${freshAward ? `<p class="celebration-tier">Award: <span class="award" data-tier="${freshAward.tier}" style="display:inline-flex"><span class="award__tier">${freshAward.tier}</span></span></p>` : ""}
          <button class="btn btn-primary" id="celebration-continue">See Full Debrief →</button>
        </div>
      </div>
    `);
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
    <div class="stack celebration-screen">
      <div class="card celebration-card" data-tier="${freshAward ? freshAward.tier : "common"}" id="aar-card">
        <div class="aar-beat is-visible">
          <div class="card__eyebrow">Mission Complete</div>
          <h1>${escapeHtml(mission.title)}</h1>
          <p>Logged. Every drop counts — even the small ones.</p>
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
    <div class="stack">
      <h1>${mission ? Evoke.escapeHtml(mission.title) : "Debrief"}</h1>
      ${!isOwn ? `<p class="empty-state">Viewing ${Evoke.escapeHtml(targetProfile ? targetProfile.display_name : "a classmate")}'s work</p>` : ""}

      <div class="card">
        <div class="card__eyebrow">Insights</div>
        ${(timeline.insights || []).length
          ? timeline.insights.map(i => `<p><strong>${Evoke.escapeHtml(i.category || "Insight")} from ${Evoke.escapeHtml(i.source)}:</strong> ${Evoke.escapeHtml(i.text)}</p>`).join("")
          : `<p class="empty-state">No insights yet — check back shortly.</p>`}
      </div>

      ${!isOwn ? `
        <div class="card">
          <div class="card__eyebrow">Leave Feedback</div>
          <form id="peer-insight-form" class="stack-sm">
            <textarea id="peer-insight-text" placeholder="What stood out about this?" rows="3" required></textarea>
            <button type="submit" class="btn btn-primary">Post Feedback</button>
          </form>
          <p id="peer-insight-status" class="empty-state"></p>
        </div>
      ` : ""}

      <div class="stack-sm" id="awards-list">
        ${missionAwards.length ? missionAwards.map(a => `
          <div class="award ${a.collected_at ? "" : "is-pending"}" data-tier="${a.tier}">
            <div>
              <span class="award__tier">${a.tier}</span>
              <span>${a.source.replace("_", " ")}</span>
            </div>
            ${a.collected_at
              ? `<span class="empty-state">Collected</span>`
              : (isOwn ? `<button data-award-id="${a.id}" class="btn btn-primary collect-btn">Collect</button>` : `<span class="empty-state">Not yet collected</span>`)}
          </div>
        `).join("") : `<p class="empty-state">No awards yet for this mission.</p>`}
      </div>

      <div class="row">
        <a class="btn" href="${isOwn ? "#/" : "#/gallery"}">← Back to ${isOwn ? "Operations Hub" : "Gallery"}</a>
        ${isOwn ? `<a class="btn" href="#/mission/${missionId}/vault">Open in the Vault</a>` : ""}
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
    <div class="stack">
      <h1>Gallery</h1>
      <p class="empty-state">Completed mission work from across the cohort. Open one to leave feedback.</p>
      <div class="grid-2">
        ${items.length ? items.map(it => `
          <a class="card mission-card" data-state="available" href="#/mission/${it.mission_id}/debrief/${it.user_id}">
            <div class="card__eyebrow">${Evoke.escapeHtml(it.mission_title)}</div>
            <div class="mission-card__title">${Evoke.escapeHtml(it.display_name)}</div>
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
  const [profile, achievementsRes, missionsRes, questsRes, mcStatus, gearRes, kitRes, reflectionsRes] = await Promise.all([
    api.playerProfile(id),
    api.achievements(id).catch(() => ({ qualities: {}, powers: {} })),
    api.missions(id).catch(() => ({ missions: [] })),
    api.mcQuests().catch(() => ({ quests: [] })),
    api.minecraftStatus().catch(() => null),
    api.gear(id).catch(() => ({ gear: [], equipped: [], sigil: null, has_avatar: false })),
    api.kitProgress(id).catch(() => ({ found: [], total: 10, complete: false, pieces: {} })),
    api.reflections(id).catch(() => ({ journal: [], total: 0 })),
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

  mount(`
    <div class="stack dossier">
      <div class="card dossier-header">
        <div class="dossier-header__id">
          ${avatarHtml}
          <div>
            <div class="card__eyebrow">Agent Dossier · Basin Field Division</div>
            <h1>${Evoke.escapeHtml(name)}</h1>
            <div class="row" style="margin-top:var(--space-2)">
              <span class="chip">LV ${profile.level} · ${Evoke.escapeHtml(profile.rank_title || "")}</span>
              <span class="chip">CLEARANCE ${String(profile.level).padStart(2, "0")}</span>
              <span class="chip ${inBasin ? "chip--green" : ""}">${inBasin ? `<span class="dot"></span>IN THE BASIN` : (profile.minecraft_username ? `CALLSIGN ${Evoke.escapeHtml(profile.minecraft_username.toUpperCase())}` : "CALLSIGN UNASSIGNED")}</span>
            </div>
            ${equippedItems.length ? `
              <div class="row" style="margin-top:var(--space-2)">
                ${equippedItems.map(g => `<span class="gear-chip" data-rarity="${g.rarity}" title="${Evoke.escapeHtml(g.flavor)}">${g.icon} ${Evoke.escapeHtml(g.name)}</span>`).join("")}
              </div>
            ` : ""}
          </div>
          ${isOwn ? `<button class="btn dossier-edit-btn" id="identity-edit">Customize Identity</button>` : ""}
        </div>
        ${isOwn ? `
        <div id="identity-editor" class="identity-editor" hidden>
          <div class="card__eyebrow" style="margin-bottom:var(--space-2)">Agent Sigil — pick a mark and a color</div>
          <div class="row" id="sigil-glyphs">
            ${["⬡","◈","✦","☄","⚙","♜","⟁","◭","⬢","❖"].map(g => `<button class="sigil-pick ${sigil && sigil.glyph === g ? "is-current" : ""}" data-glyph="${g}">${g}</button>`).join("")}
          </div>
          <div class="row" style="margin-top:var(--space-2)">
            <input type="range" id="sigil-hue" min="0" max="360" value="${sigil ? sigil.hue : 190}" style="flex:1">
            <span class="dossier-monogram dossier-sigil sigil-preview" id="sigil-preview" style="--sigil-hue:${sigil ? sigil.hue : 190}; width:44px;height:44px;font-size:var(--text-lg)">${sigil ? Evoke.escapeHtml(sigil.glyph) : "⬡"}</span>
          </div>
          <div class="row" style="margin-top:var(--space-3)">
            <label class="btn" style="cursor:pointer">Upload Photo<input type="file" id="avatar-file" accept="image/*" hidden></label>
            ${gearRes.has_avatar ? `<button class="btn" id="avatar-remove">Remove Photo</button>` : ""}
            <span class="empty-state">Photo is optional — the Sigil always works.</span>
          </div>
          <p id="identity-status" class="empty-state" style="margin-top:var(--space-2)"></p>
        </div>
        ` : ""}
        <div class="dossier-xp">
          <div class="row-between">
            <span class="card__eyebrow">XP Charge</span>
            <span class="mono-rank">${profile.xp}${nextXp ? ` / ${nextXp}` : " · MAX"}</span>
          </div>
          <div class="world-meter__track"><div class="world-meter__fill is-xp" style="width:${xpPct}%"></div></div>
          ${nextXp ? `<p class="empty-state" style="margin-top:var(--space-1)">${nextXp - profile.xp} XP to next rank</p>` : ""}
        </div>
      </div>

      <section>
        <h2 class="section-title">Field Gear</h2>
        <p class="empty-state">${gearRes.unlocked_count} of ${gearRes.total} recovered. Unlocked by what you actually do — Powers, rank, sims, the Basin${isOwn ? ". Equip up to 3 to display on your dossier" : ""}.</p>
        <div class="gear-grid">
          ${(gearRes.gear || []).map(g => `
            <div class="gear-item ${g.unlocked ? "is-unlocked" : "is-locked"}" data-rarity="${g.rarity}">
              <div class="gear-item__icon">${g.unlocked || !g.secret ? g.icon : "?"}</div>
              <div class="gear-item__name">${g.unlocked || !g.secret ? Evoke.escapeHtml(g.name) : "UNKNOWN ITEM"}</div>
              <div class="gear-item__slot">${Evoke.escapeHtml(g.slot)} · ${Evoke.escapeHtml(g.rarity)}</div>
              <p class="gear-item__text">${g.unlocked ? Evoke.escapeHtml(g.flavor) : Evoke.escapeHtml(g.hint || "Signal too weak to identify.")}</p>
              ${isOwn && g.unlocked ? `
                <button class="btn gear-equip-btn ${(gearRes.equipped || []).includes(g.key) ? "btn-primary" : ""}" data-gear-key="${g.key}">
                  ${(gearRes.equipped || []).includes(g.key) ? "Equipped" : "Equip"}
                </button>` : ""}
            </div>
          `).join("")}
        </div>
      </section>

      <section>
        <h2 class="section-title">Loadout — Superpowers</h2>
        <div class="badge-wall dossier-loadout">
          ${badgeKeys.map(key => {
            const b = (profile.badges || {})[key];
            const earnedCount = b ? b.progress : 0;
            return `
              <div class="badge-tile loadout-slot ${b && b.earned ? "is-earned" : "is-dimmed"}">
                <div class="loadout-slot__frame">${b && b.earned ? "◈" : "◇"}</div>
                <div class="badge-tile__name">${key}</div>
                <div class="loadout-pips">${[0, 1, 2, 3].map(i => `<span class="loadout-pip ${i < earnedCount ? "is-lit" : ""}"></span>`).join("")}</div>
                <div class="badge-tile__progress">${b && b.earned ? "EQUIPPED" : `${earnedCount}/4 Powers`}</div>
              </div>
            `;
          }).join("")}
        </div>
      </section>

      <section>
        <h2 class="section-title">Skill Matrix — 16 Powers</h2>
        <p class="empty-state">World Bank EVOKE framework. Hover a node for its definition.</p>
        ${badgeKeys.map(quality => `
          <div class="stack-sm" style="margin-bottom:var(--space-3)">
            <div class="card__eyebrow">${quality}</div>
            <div class="skill-matrix">
              ${Object.entries(powers).filter(([, p]) => p.quality === quality).map(([powerKey, p]) => `
                <div class="skill-node ${p.earned ? "is-earned" : ""}" title="${Evoke.escapeHtml(p.definition)}">
                  <span class="skill-node__dot"></span>${Evoke.escapeHtml(powerKey)}
                  ${p.earned ? `<span class="skill-node__how">${p.tag_type === "behavioral" ? "field-observed" : p.tag_type}</span>` : ""}
                </div>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </section>

      <section>
        <h2 class="section-title">Mission Record</h2>
        <div class="card">
          <div class="row-between">
            <span class="card__eyebrow">Campaign Progress</span>
            <span class="mono-rank">${profile.missions_completed_count} / 12</span>
          </div>
          <div class="mission-pips">
            ${allMissions.map(m => `<span class="mission-pip ${completedIds.has(m.id) ? "is-done" : (m.released ? "" : "is-locked")}" title="${Evoke.escapeHtml(m.title)}"></span>`).join("")}
          </div>
        </div>
      </section>

      <section>
        <h2 class="section-title">Commendations</h2>
        <p class="empty-state">Every mission's slot — your best tier so far, or empty until you submit.</p>
        <div class="stack-sm">
          ${allMissions.length ? allMissions.map(m => {
            const best = bestAwardByMission[m.id];
            return best ? `
              <div class="award" data-tier="${best.tier}">
                <span class="award__tier">${best.tier}</span>
                <span>${Evoke.escapeHtml(m.title)}</span>
                <span class="empty-state">${best.collected_at ? "collected" : "pending"}</span>
              </div>
            ` : `
              <div class="award is-empty">
                <span class="empty-state">Not yet submitted</span>
                <span>${Evoke.escapeHtml(m.title)}</span>
              </div>
            `;
          }).join("") : `<p class="empty-state">No missions synced yet.</p>`}
        </div>
      </section>

      <section>
        <h2 class="section-title">The Aqueduct</h2>
        ${kitRes.complete ? `
          <div class="card aqueduct is-assembled">
            <div class="card__eyebrow">Assembled — all ${kitRes.total} components</div>
            <div class="aqueduct__art" aria-hidden="true">
              <span class="aqueduct__pipe"></span><span class="aqueduct__flow"></span>
              <span class="aqueduct__glyphs">⚙ ▤ ≋ ▥ ◫ ◉ ⌸ ═ ⌵ ◍</span>
            </div>
            <p class="empty-state">Water moves because somebody built the thing that moves it. You found every component in the field.</p>
          </div>
        ` : `
          <div class="card">
            <div class="card__eyebrow">Aqueduct Kit — ${kitRes.found.length}/${kitRes.total} components</div>
            <div class="row">
              ${Object.entries(kitRes.pieces || {}).map(([k, name]) => `
                <span class="kit-piece ${kitRes.found.includes(k) ? "is-found" : ""}" title="${Evoke.escapeHtml(name)}">${kitRes.found.includes(k) ? "⚙" : "·"}</span>
              `).join("")}
            </div>
            <p class="empty-state" style="margin-top:var(--space-2)">Components are scattered across every screen of this app — recovered just by showing up. Keep exploring.</p>
          </div>
        `}
      </section>

      <section>
        <h2 class="section-title">Wisdom Journal</h2>
        <p class="empty-state">${reflectionsRes.total || 0} field report${(reflectionsRes.total || 0) === 1 ? "" : "s"} filed — ten unlocks the Transformation Power. Your daily reflections and B1llbot's answers.</p>
        <div class="stack-sm">
          ${(reflectionsRes.journal || []).slice(0, 14).map(j => `
            <div class="card journal-entry">
              <div class="card__eyebrow">${j.date}</div>
              <p>${Evoke.escapeHtml(j.text)}</p>
              ${j.wisdom ? `<p class="wisdom-line">"${Evoke.escapeHtml(j.wisdom)}" <span class="empty-state">— B1llbot</span></p>` : ""}
            </div>
          `).join("") || `<p class="empty-state">No reports yet — file your first from Now or your Field Kit.</p>`}
        </div>
      </section>

      ${profile.minecraft_username ? `
      <section>
        <h2 class="section-title">Field Ops Log — Basin Simulation</h2>
        <p class="empty-state">${profile.quests_completed_count} of ${allQuests.length} logged. Self-reported or world-observed, never graded, never required.</p>
        <div class="badge-wall">
          ${allQuests.length ? allQuests.map(q => {
            const completedAt = questCompletions[q.id];
            return `
              <div class="badge-tile ${completedAt ? "is-earned" : "is-dimmed"}" title="${Evoke.escapeHtml(q.description || "")}">
                <div class="badge-tile__name">${Evoke.escapeHtml(q.title)}</div>
                <div class="badge-tile__progress">${completedAt ? `LOGGED ${new Date(completedAt).toLocaleDateString()}` : (q.kind === "side_quest" ? "SIDE OP" : "OPEN")}</div>
              </div>
            `;
          }).join("") : `<p class="empty-state">No quests configured for this campaign yet.</p>`}
        </div>
      </section>
      ` : `
      <section class="card">
        <div class="card__eyebrow">Basin telemetry offline</div>
        <p class="empty-state">Connect your Minecraft account from your Field Kit to reveal the Field Ops Log. <a href="#/faq">How? →</a></p>
      </section>
      `}
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
  const [team, wheelRes] = await Promise.all([
    api.teamProfile(teamId),
    api.teamWheel(teamId).catch(() => ({ wheels: [], roster_size: 0 })),
  ]);

  mount(`
    <div class="stack">
      <div class="card">
        <h1>${Evoke.escapeHtml(team.team_name || "Team")}</h1>
        <div class="row">
          ${(team.members || []).map(m => `<span class="badge-tile">${Evoke.escapeHtml(m.display_name)}${m.role_label ? " — " + Evoke.escapeHtml(m.role_label) : ""}</span>`).join("") || `<p class="empty-state">No members yet.</p>`}
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
  const [missionsRes, cohortRes, world, mcStatus] = await Promise.all([
    api.adminMissions(Evoke.state.userId).catch(() => ({ missions: [] })),
    api.adminCohort(Evoke.state.userId).catch(() => ({ cohort: [] })),
    api.worldState().catch(() => null),
    api.minecraftStatus().catch(() => null),
  ]);
  const missions = missionsRes.missions || [];
  const cohort = cohortRes.cohort || [];
  const daysAgo = (iso) => iso ? Math.max(0, Math.floor((Date.now() - parseUtc(iso)) / 86400000)) : null;

  mount(`
    <div class="stack">
      <div class="row-between">
        <h1>Instructor Ops Deck</h1>
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
    <div class="billbot-fullscreen">
      <div class="card__eyebrow">Live Transmission</div>
      <h1>B1llbot</h1>
      <div class="billbot-fullscreen__log" id="billbot-fs-log">
        <div class="billbot-msg" data-from="billbot">You made it. What's on your mind?</div>
      </div>
      <form id="billbot-fs-form" class="row">
        <input type="text" id="billbot-fs-input" placeholder="Ask B1llbot..." style="flex:1" autocomplete="off">
        <button type="submit" class="btn btn-primary">Send</button>
      </form>
    </div>
  `);

  document.getElementById("billbot-fs-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("billbot-fs-input");
    const msg = input.value.trim();
    if (!msg) return;
    if (/alchemy/i.test(msg)) Evoke.signal?.collect("billbot");
    const log = document.getElementById("billbot-fs-log");
    log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="user">${Evoke.escapeHtml(msg)}</div>`);
    input.value = "";
    // A local model response takes 10-20s once warm, longer on a cold
    // start -- without this, the screen looks hung for that whole stretch.
    log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot" id="billbot-fs-thinking">…</div>`);
    log.scrollTop = log.scrollHeight;
    try {
      const reply = await api.billbotChat(state.userId, msg);
      document.getElementById("billbot-fs-thinking")?.remove();
      log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot">${Evoke.escapeHtml(reply.reply)}</div>`);
    } catch (err) {
      document.getElementById("billbot-fs-thinking")?.remove();
      log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot">Having trouble hearing you right now.</div>`);
    }
    log.scrollTop = log.scrollHeight;
  });
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
      <div class="stack">
        <h1>${Evoke.escapeHtml(mission.title)} — Vault</h1>
        <div class="card"><p class="empty-state">Nothing here yet — this fills in once you've submitted evidence for this mission.</p></div>
        <a class="btn" href="#/mission/${missionId}">← Back to Mission Brief</a>
      </div>
    `);
    return;
  }

  mount(`
    <div class="stack">
      <div>
        <span class="mission-card__arc" data-arc="${mission.arc}">${mission.arc} · Week ${mission.week}</span>
        <h1>${Evoke.escapeHtml(mission.title)} — Vault</h1>
      </div>

      <div class="card">
        <div class="card__eyebrow">The Mission</div>
        <p>${Evoke.escapeHtml(mission.brief || "No brief text yet.").replace(/\n/g, "<br>")}</p>
      </div>

      <div class="card">
        <div class="card__eyebrow">What You Explored</div>
        ${submission.reflection
          ? `<p>${Evoke.escapeHtml(submission.reflection)}</p>`
          : `<p class="empty-state">No field note recorded for this one.</p>`}
        <p class="empty-state" style="margin-top:var(--space-2)">Submitted ${new Date(submission.submitted_at).toLocaleDateString()}</p>
      </div>

      <div class="card">
        <div class="card__eyebrow">What Came Back</div>
        ${(timeline.insights || []).length
          ? timeline.insights.map(i => `<p><strong>${Evoke.escapeHtml(i.category || "Insight")} from ${Evoke.escapeHtml(i.source)}:</strong> ${Evoke.escapeHtml(i.text)}</p>`).join("")
          : `<p class="empty-state">No insights recorded.</p>`}
      </div>

      <div class="card">
        <div class="card__eyebrow">What You Earned ${Evoke.signal ? Evoke.signal.nodeHtml("vault") : ""}</div>
        ${missionAwards.length
          ? missionAwards.map(a => `<span class="award" data-tier="${a.tier}" style="display:inline-flex"><span class="award__tier">${a.tier}</span></span>`).join(" ")
          : `<p class="empty-state">No awards yet for this mission.</p>`}
      </div>

      <div class="row">
        <a class="btn" href="#/">← Back to Operations Hub</a>
        <a class="btn btn-primary" href="#/mission/${missionId}">Strengthen &amp; Resubmit →</a>
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
  const [map, world] = await Promise.all([
    api.progressMap(state.userId),
    api.worldState().catch(() => null),
  ]);
  Evoke.kit?.visit("basin");
  const TIER_NAME = { 1: "common", 2: "epic", 3: "legendary" };

  mount(`
    <div class="stack">
      <div class="row-between">
        <h1>Campaign Map</h1>
        <span class="chip">${map.stages_complete}/${map.stages_total} STAGES DONE</span>
      </div>

      <div class="card">
        <div class="card__eyebrow">What done means</div>
        <p><strong>Submitted</strong> = the mission counts (<span class="award__tier" style="background:var(--tier-common);color:var(--color-text)">common</span>). <strong>AI-strengthened</strong> = <span class="award__tier" style="background:var(--tier-epic)">epic</span>. <strong>Teacher-honored</strong> = <span class="award__tier" style="background:var(--tier-legendary)">legendary</span>.</p>
        <p>A stage is <strong>DONE</strong> when its ring closes — 100% of its missions submitted. Its <strong>GRADE</strong> (★ to ★★★) is your weakest mission's tier: strengthen and resubmit any mission to raise it. Quests and Training sims never gate anything — they're how agents get sharper.</p>
      </div>

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
        <div class="card">
          <div class="card__eyebrow">Basin telemetry offline</div>
          <p class="empty-state">Each stage also has an optional Basin Simulation quest — connect your Minecraft account from your Field Kit (scan the QR on Now) to reveal them here. <a href="#/faq">How do I connect? →</a></p>
        </div>
      ` : ""}

      ${world ? `
        <section class="card world-meter">
          <div class="card__eyebrow">And the whole cohort together — Keel Restoration</div>
          <div class="row-between">
            <h2 class="card__title">Stage ${world.stage}: ${Evoke.escapeHtml(world.current.title)}</h2>
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

/* FAQ — the connect-to-Basin instructions live inline in the Field Kit
   flow AND here, per Nathan's spec. */
Evoke.screens.faq = async function faq() {
  const { api, mount } = Evoke;
  const info = await api.minecraftConnectInfo().catch(() => null);
  mount(`
    <div class="stack">
      <h1>FAQ</h1>

      <div class="card">
        <div class="card__eyebrow">How do I connect to the Basin Simulation (Minecraft)?</div>
        <ol class="faq-steps">
          <li><strong>Open your Field Kit</strong> on your phone — scan the QR code on the Now page. It registers you automatically.</li>
          <li>Tap <strong>Connect to Basin Simulation</strong>. You'll get the server address and a 4-digit link code.</li>
          <li>In Minecraft (Java or Bedrock), add a multiplayer server:${info ? `<br>Java: <code>${Evoke.escapeHtml(info.java_address)}</code> · Bedrock: <code>${Evoke.escapeHtml(info.bedrock_address)}</code>` : ""}</li>
          <li>Join the world, then type in chat: <code>/trigger evoke_link set YOUR-CODE</code></li>
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
