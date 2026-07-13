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

function timeAgo(isoTimestamp) {
  const seconds = Math.floor((Date.now() - new Date(isoTimestamp)) / 1000);
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
  const [missionsRes, notifRes, activityRes, checkinRes, mcLink, mcConnect] = await Promise.all([
    api.missions(state.userId),
    api.notifications(state.userId).catch(() => ({ notifications: [] })),
    api.activity(20).catch(() => ({ activity: [] })),
    api.checkin(state.userId).catch(() => null),
    api.minecraftLink(state.userId).catch(() => ({ linked: false })),
    api.minecraftConnectInfo().catch(() => null),
  ]);
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

  mount(`
    <div class="hub-layout">
      <div class="stack">
        ${showGuide ? `
          <section class="card" id="hub-guide">
            <div class="card__eyebrow">Orientation</div>
            <p><strong>Now</strong> — your next open mission. <strong>Mission Board</strong> — everything in this campaign; locked cards open when your instructor releases them. <strong>Feed</strong> — what the rest of your cohort is up to. <strong>Basin Simulation</strong> — the optional Minecraft world, in the sidebar.</p>
            <button class="btn" id="hub-guide-dismiss">Got it</button>
          </section>
        ` : ""}
        <section class="card">
          <div class="card__eyebrow">Now</div>
          ${nextMission
            ? `<h2 class="card__title">${Evoke.escapeHtml(nextMission.title)}</h2>
               <p>Week ${nextMission.week} · ${nextMission.arc}</p>
               <a class="btn btn-primary" href="#/mission/${nextMission.id}">Open Mission Brief →</a>`
            : allDone
              ? `<p class="empty-state">All released missions complete. New chapters coming soon.</p>`
              : `<p class="empty-state">Waiting on your instructor to release the next mission.</p>`}
          <p style="margin-top:var(--space-3)">${completedCount}/12 missions complete · ${pendingAwards.length} pending award${pendingAwards.length === 1 ? "" : "s"}</p>
          ${checkinLine ? `<p class="empty-state" style="margin-top:var(--space-2)">${checkinLine}</p>` : ""}
        </section>

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
  `);

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
};

Evoke.screens.novel = async function novel() {
  const { mount, state, api } = Evoke;
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
          <span class="empty-state">Panel ${panelIndex + 1} / ${chapter.panels.length}</span>
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
  const [missionsRes, timeline] = await Promise.all([
    api.missions(state.userId),
    api.timeline(state.userId, missionId).catch(() => null),
  ]);
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

      ${mission.quest ? `
        <div class="quest-card">
          <div class="quest-card__eyebrow">Optional — Basin Simulation</div>
          <strong>${Evoke.escapeHtml(mission.quest.title)}</strong>
          <p>${Evoke.escapeHtml(mission.quest.description || "")}</p>
        </div>
      ` : ""}

      <div class="card">
        <div class="card__eyebrow">Submit Evidence</div>
        <form class="evidence-form" id="evidence-form">
          <input type="file" name="file" required>
          <label for="evidence-reflection">Field Note ${mission.superpower ? `— what did this mission teach you about being a ${Evoke.escapeHtml(mission.superpower)}?` : ""}</label>
          <textarea id="evidence-reflection" name="reflection" rows="3" placeholder="Optional — B1llbot reads these."></textarea>
          <button type="submit" class="btn btn-primary">Submit Mission Evidence</button>
        </form>
        <p id="evidence-status"></p>
      </div>
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
      await api.submitEvidence(formData);
      statusEl.textContent = "Submitted!";
      setTimeout(() => { location.hash = `#/mission/${missionId}/debrief?fresh=1`; }, 800);
    } catch (err) {
      statusEl.textContent = "Submission failed: " + err.message;
    }
  });
};

Evoke.screens.missionDebrief = async function missionDebrief(missionId, targetUserIdParam) {
  const { api, state, mount } = Evoke;
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
    mount(`
      <div class="stack celebration-screen">
        <div class="card celebration-card" data-tier="${freshAward ? freshAward.tier : "common"}">
          <div class="card__eyebrow">Mission Complete</div>
          <h1>${Evoke.escapeHtml(mission.title)}</h1>
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

Evoke.screens.playerProfile = async function playerProfile(userId) {
  const { api, state, mount } = Evoke;
  const id = userId || state.userId;
  const [profile, achievementsRes, missionsRes, questsRes] = await Promise.all([
    api.playerProfile(id),
    api.achievements(id).catch(() => ({ qualities: {}, powers: {} })),
    api.missions(id).catch(() => ({ missions: [] })),
    api.mcQuests().catch(() => ({ quests: [] })),
  ]);
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

  mount(`
    <div class="stack">
      <div class="card">
        <h1>${Evoke.escapeHtml(profile.display_name || "Agent")}</h1>
        <p>Level ${profile.level} · ${profile.xp} XP</p>
        <p>${profile.minecraft_username ? `Minecraft: ${Evoke.escapeHtml(profile.minecraft_username)}` : `<span class="empty-state">No Minecraft account linked</span>`}</p>
      </div>

      <section>
        <h2 class="section-title">Superpowers</h2>
        <div class="badge-wall">
          ${badgeKeys.map(key => {
            const b = (profile.badges || {})[key];
            const powersEarned = b ? b.progress : 0;
            return `
              <div class="badge-tile ${b && b.earned ? "is-earned" : "is-dimmed"}">
                <div class="badge-tile__name">${key}</div>
                <div class="badge-tile__progress">${powersEarned} of 4 Powers</div>
              </div>
            `;
          }).join("")}
        </div>
      </section>

      <section>
        <h2 class="section-title">Achievements</h2>
        <p class="empty-state">The 16 Powers behind the 4 Superpowers (World Bank EVOKE framework). Hover a tile for what it means.</p>
        ${badgeKeys.map(quality => `
          <div class="stack-sm">
            <div class="card__eyebrow">${quality}</div>
            <div class="badge-wall">
              ${Object.entries(powers).filter(([, p]) => p.quality === quality).map(([powerKey, p]) => `
                <div class="badge-tile ${p.earned ? "is-earned" : "is-dimmed"}" title="${Evoke.escapeHtml(p.definition)}">
                  <div class="badge-tile__name">${Evoke.escapeHtml(powerKey)}</div>
                  <div class="badge-tile__progress">${p.earned ? (p.tag_type === "behavioral" ? "earned" : `earned · ${p.tag_type}`) : "locked"}</div>
                </div>
              `).join("")}
            </div>
          </div>
        `).join("")}
      </section>

      <section class="card">
        <div class="card__eyebrow">Missions</div>
        <p>${profile.missions_completed_count} / 12 complete</p>
      </section>

      <section>
        <h2 class="section-title">Quests</h2>
        <p class="empty-state">${profile.quests_completed_count} of ${allQuests.length} completed — every quest in the Basin Simulation, whether you've done it yet or not.</p>
        <div class="badge-wall">
          ${allQuests.length ? allQuests.map(q => {
            const completedAt = questCompletions[q.id];
            return `
              <div class="badge-tile ${completedAt ? "is-earned" : "is-dimmed"}" title="${Evoke.escapeHtml(q.description || "")}">
                <div class="badge-tile__name">${Evoke.escapeHtml(q.title)}</div>
                <div class="badge-tile__progress">${completedAt ? `done ${new Date(completedAt).toLocaleDateString()}` : (q.kind === "side_quest" ? "side quest — not done" : "not done")}</div>
              </div>
            `;
          }).join("") : `<p class="empty-state">No quests configured for this campaign yet.</p>`}
        </div>
      </section>

      <section>
        <h2 class="section-title">Award Cabinet</h2>
        <p class="empty-state">Every mission's trophy slot — your best tier so far, or empty until you submit.</p>
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
    </div>
  `);
};

Evoke.screens.teamProfile = async function teamProfile(teamId) {
  const { api, mount } = Evoke;
  const team = await api.teamProfile(teamId);

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
  const missionsRes = await api.adminMissions(Evoke.state.userId).catch(() => ({ missions: [] }));
  const missions = missionsRes.missions || [];

  mount(`
    <div class="stack">
      <h1>Mission Release — Admin</h1>
      <p class="empty-state">Missions are gated by manual release, not automatic order. Week 1's first mission releases on its own; everything else waits here.</p>
      <div class="stack-sm">
        ${missions.map(m => `
          <div class="card" data-mission-row="${m.id}">
            <div class="card__eyebrow">Week ${m.week} · ${m.arc}</div>
            <strong>${Evoke.escapeHtml(m.title)}</strong>
            <p class="empty-state">${m.released ? `Released ${new Date(m.released_at).toLocaleString()}` : "Not released"}</p>
            <button class="btn ${m.released ? "" : "btn-primary"}" data-action="${m.released ? "unrelease" : "release"}" data-mission-id="${m.id}">
              ${m.released ? "Unrelease" : "Release"}
            </button>
          </div>
        `).join("") || `<p class="empty-state">No missions synced yet.</p>`}
      </div>
    </div>
  `);

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
        <div class="card__eyebrow">What You Earned</div>
        ${missionAwards.length
          ? missionAwards.map(a => `<span class="award" data-tier="${a.tier}" style="display:inline-flex"><span class="award__tier">${a.tier}</span></span>`).join(" ")
          : `<p class="empty-state">No awards yet for this mission.</p>`}
      </div>

      <a class="btn" href="#/">← Back to Operations Hub</a>
    </div>
  `);
};
