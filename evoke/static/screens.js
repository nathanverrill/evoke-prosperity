/* screens.js — one render function per route in UI_SPEC.md's information
   architecture. Each function fetches what it needs and calls Evoke.mount().
   Honesty note: a few UI_SPEC affordances (mission lock/gating state,
   evidence-submission reflection text, "my team" lookup) don't have a
   backend behind them yet -- those are called out inline rather than faked,
   per CONCEPTS.md's "don't assume UI features exist server-side" warning. */

const ARC_ORDER = ["Explore", "Imagine", "Act", "Communicate"];

function missionState(mission, profile) {
  const completed = (profile && profile.missions_completed) || [];
  return completed.includes(mission.id) ? "complete" : "available";
  // No arc/sequence gating exists server-side yet (every mission is
  // "available" until completed) -- this reflects that honestly rather
  // than fabricating a lock mechanic the backend doesn't enforce.
}

function timeAgo(isoTimestamp) {
  const seconds = Math.floor((Date.now() - new Date(isoTimestamp)) / 1000);
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

Evoke.screens.hub = async function hub() {
  const { api, state, mount } = Evoke;
  const [missionsRes, notifRes, activityRes, checkinRes] = await Promise.all([
    api.missions(state.userId),
    api.notifications(state.userId).catch(() => ({ notifications: [] })),
    api.activity(20).catch(() => ({ activity: [] })),
    api.checkin(state.userId).catch(() => null),
  ]);
  const missions = missionsRes.missions || [];
  const profile = state.profile;
  const completedCount = (profile && profile.missions_completed_count) || 0;
  const nextMission = missions.find(m => missionState(m, profile) === "available");
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

  mount(`
    <div class="hub-layout">
      <div class="stack">
        <section class="card">
          <div class="card__eyebrow">Now</div>
          ${nextMission
            ? `<h2 class="card__title">${Evoke.escapeHtml(nextMission.title)}</h2>
               <p>Week ${nextMission.week} · ${nextMission.arc}</p>
               <a class="btn btn-primary" href="#/mission/${nextMission.id}">Open Mission Brief →</a>`
            : `<p class="empty-state">All missions complete. New chapters coming soon.</p>`}
          <p style="margin-top:var(--space-3)">${completedCount}/12 missions complete · ${pendingAwards.length} pending award${pendingAwards.length === 1 ? "" : "s"}</p>
          ${checkinLine ? `<p class="empty-state" style="margin-top:var(--space-2)">${checkinLine}</p>` : ""}
        </section>

        <section>
          <h2 class="section-title">Mission Board</h2>
          <div class="mission-board">
            ${ARC_ORDER.map(arc => `
              <div class="arc-column">
                <div class="arc-column__title">${arc}</div>
                ${byArc[arc].map(m => `
                  <a class="mission-card" data-state="${missionState(m, profile)}" href="#/mission/${m.id}">
                    <span class="mission-card__arc" data-arc="${m.arc}">${m.arc}</span>
                    <div class="mission-card__title">${Evoke.escapeHtml(m.title)}</div>
                    <div class="mission-card__meta">Week ${m.week} · ${missionState(m, profile)}</div>
                  </a>
                `).join("") || `<p class="empty-state">—</p>`}
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
      </aside>
    </div>
  `);
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
    if (!fileInput.files[0]) return;
    const formData = new FormData();
    formData.append("user_id", state.userId);
    formData.append("mission_id", missionId);
    formData.append("file", fileInput.files[0]);
    statusEl.textContent = "Submitting...";
    try {
      await api.submitEvidence(formData);
      statusEl.textContent = "Submitted! Redirecting to your debrief...";
      setTimeout(() => { location.hash = `#/mission/${missionId}/debrief`; }, 1200);
    } catch (err) {
      statusEl.textContent = "Submission failed: " + err.message;
    }
  });
};

Evoke.screens.missionDebrief = async function missionDebrief(missionId) {
  const { api, state, mount } = Evoke;
  const [missionsRes, timeline, awardsRes] = await Promise.all([
    api.missions(state.userId),
    api.timeline(state.userId, missionId).catch(() => ({ insights: [] })),
    api.awards(state.userId),
  ]);
  const mission = (missionsRes.missions || []).find(m => m.id === missionId);
  const missionAwards = (awardsRes.awards || []).filter(a => a.mission_id === missionId);

  mount(`
    <div class="stack">
      <h1>${mission ? Evoke.escapeHtml(mission.title) : "Debrief"}</h1>

      <div class="card">
        <div class="card__eyebrow">Insights</div>
        ${(timeline.insights || []).length
          ? timeline.insights.map(i => `<p><strong>${Evoke.escapeHtml(i.source)}:</strong> ${Evoke.escapeHtml(i.text)}</p>`).join("")
          : `<p class="empty-state">No insights yet — check back shortly.</p>`}
      </div>

      <div class="stack-sm" id="awards-list">
        ${missionAwards.length ? missionAwards.map(a => `
          <div class="award ${a.collected_at ? "" : "is-pending"}" data-tier="${a.tier}">
            <div>
              <span class="award__tier">${a.tier}</span>
              <span>${a.source.replace("_", " ")}</span>
            </div>
            ${a.collected_at
              ? `<span class="empty-state">Collected</span>`
              : `<button data-award-id="${a.id}" class="btn btn-primary collect-btn">Collect</button>`}
          </div>
        `).join("") : `<p class="empty-state">No awards yet for this mission.</p>`}
      </div>

      <a class="btn" href="#/">← Back to Operations Hub</a>
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
};

Evoke.screens.playerProfile = async function playerProfile(userId) {
  const { api, state, mount } = Evoke;
  const id = userId || state.userId;
  const profile = await api.playerProfile(id);
  const badgeKeys = ["Empathetic Changemaker", "Systems Thinker", "Creative Visionary", "Deep Collaborator"];

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
            return `
              <div class="badge-tile ${b && b.earned ? "is-earned" : "is-dimmed"}">
                <div class="badge-tile__name">${key}</div>
                <div class="badge-tile__progress">${b ? `${b.progress} mission${b.progress === 1 ? "" : "s"}` : "not started"}</div>
              </div>
            `;
          }).join("")}
        </div>
      </section>

      <section class="card">
        <div class="card__eyebrow">Missions</div>
        <p>${profile.missions_completed_count} / 12 complete</p>
      </section>

      <section class="card">
        <div class="card__eyebrow">Quests</div>
        <p>${profile.quests_completed_count} completed</p>
        ${(profile.quests_completed || []).length
          ? `<ul>${profile.quests_completed.map(q => `<li>${Evoke.escapeHtml(q.quest_id)} — ${new Date(q.completed_at).toLocaleDateString()}</li>`).join("")}</ul>`
          : `<p class="empty-state">No quests logged yet.</p>`}
      </section>

      <section>
        <h2 class="section-title">Award Cabinet</h2>
        <div class="stack-sm">
          ${(profile.awards || []).length ? profile.awards.map(a => `
            <div class="award" data-tier="${a.tier}">
              <span class="award__tier">${a.tier}</span>
              <span>${a.source.replace("_", " ")}</span>
              <span class="empty-state">${a.collected_at ? "collected" : "pending"}</span>
            </div>
          `).join("") : `<p class="empty-state">No awards yet.</p>`}
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
