/* app.js — shared shell: API helpers, router, top bar, B1llbot drawer.
   Screen-specific rendering lives in screens.js. Hash-based routing in
   vanilla JS, per UI_SPEC.md ("no build pipeline"). */

const Evoke = (() => {
  const state = {
    userId: localStorage.getItem("evoke_user_id") || null,
    displayName: localStorage.getItem("evoke_display_name") || null,
    profile: null,
  };

  // ---------- Sound layer (console-UX gap #9) ----------
  // Consoles are never silent -- hover blips, an XP tick, a level-up sting
  // are a disproportionately large "this is a game, not a website" signal.
  // Synthesized tones via Web Audio (oscillator + short gain envelope), not
  // sample files -- no asset pipeline to build, and a clean sine/square
  // blip reads as HUD/sci-fi, which fits this app's register better than a
  // sampled arcade sound would. The AudioContext is created lazily on the
  // first real user gesture (autoplay policies block it otherwise), and
  // every sound is gated on the mute flag, persisted per-browser.
  const soundMutedKey = "evoke_sound_muted";
  let audioCtx = null;
  function isMuted() { return localStorage.getItem(soundMutedKey) === "1"; }
  function setMuted(m) { localStorage.setItem(soundMutedKey, m ? "1" : "0"); }
  function ensureAudioCtx() {
    if (!audioCtx) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) return null;
      audioCtx = new Ctor();
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }
  document.addEventListener("pointerdown", ensureAudioCtx, { once: true });
  document.addEventListener("keydown", ensureAudioCtx, { once: true });

  function playTone(freq, startDelay, duration, type, peak) {
    if (isMuted()) return;
    const ctx = ensureAudioCtx();
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type || "sine";
    osc.frequency.value = freq;
    const t0 = ctx.currentTime + (startDelay || 0);
    gain.gain.setValueAtTime(0, t0);
    gain.gain.linearRampToValueAtTime(peak != null ? peak : 0.12, t0 + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t0);
    osc.stop(t0 + duration + 0.02);
  }

  const sfx = {
    hover: () => playTone(660, 0, 0.05, "sine", 0.045),
    select: () => playTone(880, 0, 0.08, "square", 0.06),
    xpTick: () => playTone(920, 0, 0.09, "sine", 0.09),
    award: () => { playTone(700, 0, 0.10, "sine", 0.09); playTone(1050, 0.06, 0.12, "sine", 0.08); },
    levelUp: () => { playTone(660, 0, 0.14, "square", 0.08); playTone(880, 0.10, 0.14, "square", 0.08); playTone(1320, 0.20, 0.26, "square", 0.09); },
  };

  // Delegated hover/select blips -- one pair of listeners for every link
  // and button, rather than wiring each screen's markup individually.
  let lastHovered = null;
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest("a, button");
    if (!el || el === lastHovered) return;
    lastHovered = el;
    sfx.hover();
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest("a, button") === lastHovered && !e.relatedTarget?.closest?.("a, button")) lastHovered = null;
  });
  document.addEventListener("click", (e) => {
    if (e.target.closest("a, button")) sfx.select();
  });

  // ---------- API ----------
  async function apiGet(path) {
    const res = await fetch(path);
    if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
    return res.json();
  }

  async function apiPostJSON(path, body) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
    return res.json();
  }

  async function apiPostForm(path, formData) {
    const res = await fetch(path, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`POST ${path} -> ${res.status}`);
    return res.json();
  }

  const api = {
    missions: (userId) => apiGet(`/api/missions?user_id=${userId}`),
    submitEvidence: (formData) => apiPostForm("/api/submit-evidence", formData),
    notifications: (userId) => apiGet(`/api/notifications/${userId}`),
    guideOverlay: (userId) => apiGet(`/api/guide-overlay/${userId}`),
    awards: (userId) => apiGet(`/api/awards/${userId}`),
    collectAward: (awardId, userId) => fetch(`/api/awards/${awardId}/collect?user_id=${userId}`, { method: "POST" }).then(r => r.json()),
    playerProfile: (userId) => apiGet(`/api/profile/player/${userId}`),
    achievements: (userId) => apiGet(`/api/achievements/${userId}`),
    teamProfile: (teamId) => apiGet(`/api/profile/team/${teamId}`),
    timeline: (userId, missionId) => apiGet(`/api/timeline/${userId}/${missionId}`),
    mcQuests: (campaignId) => apiGet(`/api/mc-quests${campaignId ? "?campaign_id=" + campaignId : ""}`),
    submitQuest: (questId, formData) => apiPostForm(`/api/mc-quests/${questId}/submit`, formData),
    billbotChat: (userId, message) => apiPostJSON(`/api/billbot/chat?user_id=${userId}&message=${encodeURIComponent(message)}`, {}),
    devLogin: () => fetch("/api/dev-login", { method: "POST" }).then(r => r.json()),
    checkin: (userId) => fetch(`/api/checkin?user_id=${userId}`, { method: "POST" }).then(r => r.json()),
    activity: (limit) => apiGet(`/api/activity${limit ? "?limit=" + limit : ""}`),
    gallery: (missionId) => apiGet(`/api/gallery${missionId ? "?mission_id=" + missionId : ""}`),
    postPeerInsight: (targetUserId, missionId, fromUserId, text) => {
      const formData = new FormData();
      formData.append("text", text);
      return fetch(`/api/timeline/${targetUserId}/${missionId}/peer-insight?from_user_id=${fromUserId}`, { method: "POST", body: formData }).then(r => r.json());
    },
    submission: (userId, missionId) => apiGet(`/api/submissions/${userId}/${missionId}`),
    minecraftConnectInfo: () => apiGet(`/api/minecraft/connect-info`),
    minecraftLink: (userId) => apiGet(`/api/minecraft/link/${userId}`),
    adminMissions: (userId) => apiGet(`/api/admin/missions?user_id=${userId}`),
    adminRelease: (missionId) => fetch(`/api/admin/missions/${missionId}/release`, { method: "POST" }).then(r => r.json()),
    adminUnrelease: (missionId) => fetch(`/api/admin/missions/${missionId}/unrelease`, { method: "POST" }).then(r => r.json()),
    worldState: () => apiGet("/api/world-state"),
    minecraftStatus: () => apiGet("/api/minecraft/status"),
    mcArena: (userId) => apiGet(`/api/mc-arena/${userId}`),
    mcGauntlet: (userId) => apiGet(`/api/mc-gauntlet/${userId}`),
    companionInfo: () => apiGet("/api/companion/info"),
    teamWheel: (teamId) => apiGet(`/api/team/${teamId}/wheel`),
    adminCohort: (userId) => apiGet(`/api/admin/cohort?user_id=${userId}`),
    adminRoster: () => apiGet("/api/admin/roster"),
    adminImportStudent: (brightspaceUserId) => fetch(`/api/admin/roster/${brightspaceUserId}/import`, { method: "POST" }).then(r => r.json()),
    adminTeams: () => apiGet("/api/admin/teams"),
    adminCreateTeam: (name) => {
      const fd = new FormData();
      fd.append("name", name);
      return apiPostForm("/api/admin/teams", fd);
    },
    adminAddTeamMember: (teamId, userId) => {
      const fd = new FormData();
      fd.append("user_id", userId);
      return apiPostForm(`/api/admin/teams/${teamId}/members`, fd);
    },
    adminRemoveTeamMember: (teamId, userId) => fetch(`/api/admin/teams/${teamId}/members/${userId}`, { method: "DELETE" }).then(r => r.json()),
    progressMap: (userId) => apiGet(`/api/progress-map/${userId}`),
    setStage: (missionId, stage) => {
      const fd = new FormData();
      fd.append("stage", String(stage));
      return apiPostForm(`/api/admin/missions/${missionId}/stage`, fd);
    },
    postReflection: (userId, text) => {
      const fd = new FormData();
      fd.append("text", text);
      return apiPostForm(`/api/reflection?user_id=${userId}`, fd);
    },
    reflections: (userId) => apiGet(`/api/reflections/${userId}`),
    dailyObjectives: (userId) => apiGet(`/api/daily-objectives/${userId}`),
    linkCode: (userId) => fetch(`/api/minecraft/link-code?user_id=${userId}`, { method: "POST" }).then(r => r.json()),
    linkRequest: (userId) => apiGet(`/api/minecraft/link-request/${userId}`),
    linkConfirm: (userId, accept) => {
      const fd = new FormData();
      fd.append("accept", accept ? "true" : "false");
      return apiPostForm(`/api/minecraft/link-confirm?user_id=${userId}`, fd);
    },
    kitPiece: (userId, piece) => {
      const fd = new FormData();
      fd.append("piece", piece);
      return apiPostForm(`/api/minigames/kit/piece?user_id=${userId}`, fd);
    },
    kitProgress: (userId) => apiGet(`/api/minigames/kit/${userId}`),
    gear: (userId) => apiGet(`/api/gear/${userId}`),
    equipGear: (userId, keys) => {
      const fd = new FormData();
      fd.append("keys", JSON.stringify(keys));
      return apiPostForm(`/api/gear/${userId}/equip`, fd);
    },
    setSigil: (userId, glyph, hue) => {
      const fd = new FormData();
      fd.append("glyph", glyph);
      fd.append("hue", String(hue));
      return apiPostForm(`/api/profile/${userId}/sigil`, fd);
    },
    uploadAvatar: (userId, file) => {
      const fd = new FormData();
      fd.append("file", file);
      return apiPostForm(`/api/avatar/${userId}`, fd);
    },
    deleteAvatar: (userId) => fetch(`/api/avatar/${userId}`, { method: "DELETE" }).then(r => r.json()),
  };

  // ---------- Auth (dev-login only; see CONCEPTS.md's known gaps) ----------
  async function ensureLoggedIn() {
    if (state.userId) return;
    const data = await api.devLogin();
    state.userId = data.user_id;
    state.displayName = data.display_name;
    localStorage.setItem("evoke_user_id", state.userId);
    localStorage.setItem("evoke_display_name", state.displayName);
  }

  // ---------- Live layer (WebSocket) ----------
  // One socket per page load, auto-reconnecting. Two consumer levels:
  // app-level reactions here (toasts, topbar refresh, level-up overlay),
  // plus a single screen-level handler slot (state.onLive) the current
  // screen may set to react in place (hub re-render on feed/world/presence
  // changes). Projections/APIs stay the source of truth -- this is a
  // freshness signal, not a data channel the UI depends on.
  function connectLive() {
    let ws;
    let retryMs = 1000;
    function open() {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => { retryMs = 1000; };
      ws.onmessage = (e) => {
        let msg;
        try { msg = JSON.parse(e.data); } catch { return; }
        handleLiveEvent(msg);
        if (typeof state.onLive === "function") {
          try { state.onLive(msg); } catch (err) { console.error(err); }
        }
      };
      ws.onclose = () => {
        setTimeout(open, retryMs);
        retryMs = Math.min(retryMs * 2, 15000);
      };
    }
    open();
  }

  function toast(html, opts = {}) {
    let box = document.getElementById("toast-box");
    if (!box) {
      box = document.createElement("div");
      box.id = "toast-box";
      box.className = "toast-box";
      document.body.appendChild(box);
    }
    const el = document.createElement("div");
    el.className = "toast";
    if (opts.kind) el.dataset.kind = opts.kind;
    el.innerHTML = html;
    box.appendChild(el);
    setTimeout(() => el.classList.add("is-leaving"), opts.ttl || 6000);
    setTimeout(() => el.remove(), (opts.ttl || 6000) + 400);
  }

  function showLevelUpOverlay(data) {
    document.getElementById("levelup-overlay")?.remove();
    const overlay = document.createElement("div");
    overlay.id = "levelup-overlay";
    overlay.className = "celebration-overlay";
    overlay.innerHTML = `
      <div class="card celebration-card" data-tier="legendary">
        <div class="card__eyebrow">Rank Advancement</div>
        <h1>Level ${data.level}</h1>
        <p class="celebration-tier">You are now a <strong>${escapeHtml(data.title)}</strong></p>
        <p>The Basin remembers who shows up.</p>
        <button class="btn btn-primary" id="levelup-continue">Carry On →</button>
      </div>
    `;
    document.body.appendChild(overlay);
    document.getElementById("levelup-continue").addEventListener("click", () => overlay.remove());
  }

  function handleLiveEvent(msg) {
    const d = msg.data || {};
    if (msg.type === "LevelUpped") {
      if (d.user_id === state.userId) {
        // The fresh-completion after-action report (screens.js's
        // renderMissionAAR) shows its own inline level-up beat when a
        // mission submission crosses a threshold -- this global overlay
        // would otherwise stack a second "you leveled up" moment on top
        // of it for the exact same event. The sting still plays either
        // way -- only the visual overlay is suppressed.
        sfx.levelUp();
        if (!state.suppressLevelUpOverlay) showLevelUpOverlay(d);
        renderTopbar();
      } else {
        toast(`⬆ ${escapeHtml(d.display_name || "An agent")} reached Level ${d.level} — ${escapeHtml(d.title || "")}`);
      }
    } else if (msg.type === "WorldStateAdvanced") {
      toast(
        `⚡ <strong>Keel Restoration — Stage ${d.stage}: ${escapeHtml(d.title || "")}</strong><br>${escapeHtml(d.narrative || "")}`,
        { kind: "world", ttl: 10000 }
      );
    } else if (msg.type === "ActivityPosted") {
      // Someone else's award/quest landing right now -- worth a nudge, but
      // not for my own actions (those already celebrate full-screen).
      // mission_released gets its own richer season-drop toast below
      // (same underlying release, two live-hub broadcasts -- this feed
      // copy would otherwise double up with it).
      if (d.user_id !== state.userId && d.kind !== "mission_released") toast(escapeHtml(d.message || ""));
    } else if (msg.type === "MissionReleased") {
      // Season drop (console-UX gap #10): mission release is already this
      // campaign's real content-drop mechanic, just never announced. Every
      // connected browser gets this, including the releasing instructor's.
      sfx.award();
      toast(
        `<span class="chip chip--green" style="margin-bottom:var(--space-2);display:inline-flex">NEW</span><br>` +
        `<strong>Week ${d.week}: ${escapeHtml(d.title || "")}</strong><br>` +
        `<a href="#/mission/${d.mission_id}">Open Mission Brief →</a>`,
        { kind: "release", ttl: 12000 }
      );
    } else if (msg.type === "ArenaWaveReached" && d.user_id === state.userId) {
      // No full-screen celebration for this one (unlike missions/levels) --
      // just a toast. Other players' runs already reach everyone through
      // the generic ActivityPosted branch above (arena_wave isn't excluded
      // there), so this only needs to cover the achiever's own case.
      sfx.award();
      toast(`⚔ Claude's Halyard Mob Arena — new best: <strong>Wave ${d.wave}</strong>`);
    } else if (msg.type === "GauntletWaveReached" && d.user_id === state.userId) {
      sfx.award();
      toast(`⚔ The Mob Gauntlet — new best: <strong>Wave ${d.wave}</strong>`);
    } else if (msg.type === "XPGranted" && d.user_id === state.userId) {
      sfx.xpTick();
      renderTopbar();
    } else if (msg.type === "AwardGranted" && d.user_id === state.userId) {
      sfx.award();
      renderTopbar();
    }
  }

  // ---------- Nav rail (the showcase's primary-nav pattern) ----------
  // A vertical rail: brand lockup on top, then big icon+label items in the
  // display font, cyan-highlighted when active. On narrow screens it
  // collapses to a fixed bottom tab bar (layout.css).
  const NAV_ITEMS = [
    { href: "#/", icon: "home", label: "Home", fill: true },
    { href: "#/map", icon: "hub", label: "Campaign Map" },
    { href: "#/novel", icon: "auto_stories", label: "Story" },
    { href: "#/gallery", icon: "groups", label: "Cohort" },
    { href: "#/arcade", icon: "sports_esports", label: "Field Ops" },
    { href: "#/billbot", icon: "smart_toy", label: "B1llbot" },
    { href: "#/profile", icon: "person", label: "Dossier", fill: true },
  ];

  function navIsActive(href) {
    const route = location.hash || "#/";
    if (href === "#/") return route === "#/" || route === "#/welcome";
    return route === href || route.startsWith(href + "/");
  }

  function renderRail() {
    const el = document.getElementById("nav-rail");
    if (!el) return;
    el.innerHTML = `
      <a href="#/" class="topbar__brand rail__brand" aria-label="EVOKE Prosperity — home">
        <span class="glyph" aria-hidden="true"></span>
        <span class="rail__brandwords"><span class="word">EVOKE</span><span class="word--sub">Prosperity</span></span>
      </a>
      ${NAV_ITEMS.map(it => `
        <a class="nav ${navIsActive(it.href) ? "on" : ""}" href="${it.href}">
          <span class="ms ${it.fill ? "ms--fill" : ""}" aria-hidden="true">${it.icon}</span>
          <span class="nav__lbl">${it.label}</span>
        </a>
      `).join("")}
    `;

    // Easter egg (Alchemy Signal fragment): triple-click the glyph.
    let glyphClicks = 0, glyphTimer = null;
    el.querySelector(".glyph")?.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      glyphClicks++;
      clearTimeout(glyphTimer);
      glyphTimer = setTimeout(() => { glyphClicks = 0; }, 2500);
      if (glyphClicks >= 3) {
        glyphClicks = 0;
        Evoke.signal?.collect("glyph");
      }
    });
  }

  // ---------- Top bar (slim status strip -- nav lives in the rail) ----------
  async function renderTopbar() {
    const el = document.getElementById("topbar");
    let xp = 0, level = 1, rank = "";
    try {
      state.profile = await api.playerProfile(state.userId);
      xp = state.profile.xp;
      level = state.profile.level;
      rank = state.profile.rank_title || "";
    } catch (e) { /* profile not ready yet -- empty state is fine */ }

    let unreadCount = 0;
    try {
      const n = await api.notifications(state.userId);
      unreadCount = (n.notifications || []).filter(x => !x.read).length;
    } catch (e) { /* ignore */ }

    el.innerHTML = `
      <div class="topbar__left">
        <span class="hud">Hello, Agent</span>
      </div>
      <div class="topbar__right">
        <span class="xp-meter">${state.displayName || "Agent"} · Lv ${level}${rank ? ` ${rank}` : ""} · ${xp} XP</span>
        <span class="streak-pill" title="Streak tracking not built yet">🔥 —</span>
        <button type="button" id="sound-toggle-btn" class="notif-bell" title="${isMuted() ? "Unmute" : "Mute"} sound" aria-pressed="${isMuted()}">${isMuted() ? "🔇" : "🔊"}</button>
        <button type="button" id="notif-bell-btn" class="notif-bell ${unreadCount ? "has-unread" : ""}">🔔 ${unreadCount}</button>
      </div>
    `;
    renderRail();
    document.getElementById("notif-bell-btn")?.addEventListener("click", toggleGuideOverlay);
    document.getElementById("sound-toggle-btn")?.addEventListener("click", () => {
      setMuted(!isMuted());
      renderTopbar();
    });
  }

  // ---------- Guide overlay (console-UX gap #6) ----------
  // Xbox-button-from-anywhere pattern: notifications, pending awards, and
  // recent wisdom in a panel that opens over whatever screen you're on,
  // instead of the bell navigating away to the Dossier.
  async function renderGuideOverlay() {
    const data = await api.guideOverlay(state.userId).catch(() => null);
    if (!data) return;
    let el = document.getElementById("guide-overlay");
    if (!el) {
      el = document.createElement("div");
      el.id = "guide-overlay";
      el.className = "guide-overlay";
      el.addEventListener("click", (e) => { if (e.target === el) closeGuideOverlay(); });
      document.body.appendChild(el);
    }
    el.innerHTML = `
      <div class="card guide-overlay__panel">
        <div class="row-between">
          <div class="card__eyebrow">Guide</div>
          <button type="button" class="btn" id="guide-overlay-close">✕</button>
        </div>

        <div class="guide-overlay__section">
          <div class="card__eyebrow">Pending Awards</div>
          ${data.pending_awards.length ? data.pending_awards.map(a => `
            <div class="award is-pending" data-tier="${a.tier}">
              <div>
                <span class="award__tier">${a.tier}</span>
                <span>${escapeHtml(a.mission_title)}</span>
              </div>
              <button type="button" class="btn btn-primary guide-overlay__collect" data-award-id="${a.id}">Collect</button>
            </div>
          `).join("") : `<p class="empty-state">Nothing waiting — you're all caught up.</p>`}
        </div>

        ${data.link_request.pending ? `
          <div class="guide-overlay__section">
            <div class="card__eyebrow">Basin Link Request</div>
            <p><strong>${escapeHtml(data.link_request.minecraft_username)}</strong> wants to link to your account.</p>
            <div class="row">
              <button type="button" class="btn btn-primary" id="guide-overlay-link-accept">Accept</button>
              <button type="button" class="btn" id="guide-overlay-link-reject">Reject</button>
            </div>
          </div>
        ` : ""}

        <div class="guide-overlay__section">
          <div class="card__eyebrow">Recent Wisdom</div>
          ${data.recent_wisdom ? `<p class="wisdom-line">“${escapeHtml(data.recent_wisdom)}” <span class="empty-state">— B1llbot</span></p>` : `<p class="empty-state">File a Field Report to start your journal.</p>`}
        </div>

        <a class="btn" href="#/profile" id="guide-overlay-dossier">Open full Dossier →</a>
      </div>
    `;

    document.getElementById("guide-overlay-close").addEventListener("click", closeGuideOverlay);
    document.getElementById("guide-overlay-dossier").addEventListener("click", closeGuideOverlay);
    el.querySelectorAll(".guide-overlay__collect").forEach(btn => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Collecting...";
        try {
          await api.collectAward(btn.dataset.awardId, state.userId);
          await renderGuideOverlay();
          await renderTopbar();
        } catch (e) {
          btn.disabled = false;
          btn.textContent = "Collect";
        }
      });
    });
    document.getElementById("guide-overlay-link-accept")?.addEventListener("click", () => resolveLinkRequest(true));
    document.getElementById("guide-overlay-link-reject")?.addEventListener("click", () => resolveLinkRequest(false));
  }

  async function resolveLinkRequest(accept) {
    const fd = new FormData();
    fd.append("accept", accept);
    try {
      await apiPostForm(`/api/minecraft/link-confirm?user_id=${state.userId}`, fd);
    } catch (e) { /* surfaced by the panel just not clearing below */ }
    await renderGuideOverlay();
  }

  function toggleGuideOverlay() {
    const el = document.getElementById("guide-overlay");
    if (el && el.classList.contains("is-open")) { closeGuideOverlay(); return; }
    renderGuideOverlay().then(() => {
      document.getElementById("guide-overlay")?.classList.add("is-open");
    });
  }

  function closeGuideOverlay() {
    document.getElementById("guide-overlay")?.classList.remove("is-open");
  }

  // ---------- B1llbot drawer ----------
  function renderBillbotDrawer() {
    const el = document.getElementById("billbot-drawer");
    el.innerHTML = `
      <div class="billbot-drawer__header" id="billbot-toggle">B1llbot <span id="billbot-caret">▲</span></div>
      <div class="billbot-drawer__body">
        <div class="billbot-drawer__log" id="billbot-log">
          <div class="billbot-msg" data-from="billbot">What do you notice today?</div>
        </div>
        <form id="billbot-form" class="row">
          <input type="text" id="billbot-input" placeholder="Ask B1llbot..." style="flex:1" autocomplete="off">
          <button type="submit">Send</button>
        </form>
      </div>
    `;
    document.getElementById("billbot-toggle").addEventListener("click", () => {
      el.classList.toggle("is-collapsed");
      document.getElementById("billbot-caret").textContent = el.classList.contains("is-collapsed") ? "▲" : "▼";
    });
    document.getElementById("billbot-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("billbot-input");
      const msg = input.value.trim();
      if (!msg) return;
      // Easter egg (Alchemy Signal fragment): asking B1llbot about the
      // name he won't explain.
      if (/alchemy/i.test(msg)) Evoke.signal?.collect("billbot");
      const log = document.getElementById("billbot-log");
      log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="user">${escapeHtml(msg)}</div>`);
      input.value = "";
      // A local model response takes 10-20s once warm, longer on a cold
      // start -- without this, the drawer looks hung for that whole stretch.
      log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot" id="billbot-thinking">…</div>`);
      log.scrollTop = log.scrollHeight;
      try {
        const reply = await api.billbotChat(state.userId, msg);
        document.getElementById("billbot-thinking")?.remove();
        log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot">${escapeHtml(reply.reply)}</div>`);
      } catch (err) {
        document.getElementById("billbot-thinking")?.remove();
        log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot">Having trouble hearing you right now.</div>`);
      }
      log.scrollTop = log.scrollHeight;
    });
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  // ---------- Router ----------
  const routes = [
    { pattern: /^#\/welcome$/, screen: "welcome" },
    { pattern: /^#\/$/, screen: "hub" },
    { pattern: /^#\/novel$/, screen: "novel" },
    { pattern: /^#\/gallery$/, screen: "gallery" },
    { pattern: /^#\/billbot$/, screen: "billbot" },
    { pattern: /^#\/mission\/([^/]+)$/, screen: "missionBrief" },
    { pattern: /^#\/mission\/([^/]+)\/debrief(?:\?.*)?$/, screen: "missionDebrief" },
    { pattern: /^#\/mission\/([^/]+)\/vault$/, screen: "vault" },
    { pattern: /^#\/mission\/([^/]+)\/debrief\/([^/]+)$/, screen: "missionDebrief" },
    { pattern: /^#\/profile$/, screen: "playerProfile" },
    { pattern: /^#\/profile\/([^/]+)$/, screen: "playerProfile" },
    { pattern: /^#\/team\/([^/]+)$/, screen: "teamProfile" },
    { pattern: /^#\/admin$/, screen: "admin" },
    { pattern: /^#\/map$/, screen: "campaignMap" },
    { pattern: /^#\/faq$/, screen: "faq" },
    { pattern: /^#\/arcade$/, screen: "arcade" },
    { pattern: /^#\/game\/flow$/, screen: "gameFlow" },
    { pattern: /^#\/game\/decrypt$/, screen: "gameDecrypt" },
    { pattern: /^#\/alchemy$/, screen: "alchemy" },
  ];

  async function router() {
    const hash = location.hash || "#/";
    const screenEl = document.getElementById("screen");
    state.onLive = null; // screens opt back in after render; stale handlers must not survive navigation
    for (const route of routes) {
      const match = hash.match(route.pattern);
      if (match) {
        screenEl.innerHTML = `<p class="empty-state">Loading...</p>`;
        try {
          await Evoke.screens[route.screen](...match.slice(1));
        } catch (e) {
          console.error(e);
          screenEl.innerHTML = `<div class="card"><p>Something didn't load. ${escapeHtml(e.message)}</p></div>`;
        }
        renderTopbar();
        return;
      }
    }
    screenEl.innerHTML = `<div class="card"><p>Unknown page.</p></div>`;
  }

  function mount(html) {
    document.getElementById("screen").innerHTML = html;
  }

  // ---------- Controller-grammar keyboard nav ----------
  // Console-player feedback: A=select/B=back/bumpers-switch-tabs has a web
  // translation this app never built -- Esc/Backspace for back, arrow-key
  // roving focus in the nav rail, and visible focus rings (the last one
  // doubles as the keyboard-accessibility gap GAPS.md already flags).
  // Hash navigation already pushes a real browser history entry per route
  // change, so "back" is just history.back() -- no custom nav stack needed
  // (the showcase mocked one; the real app's router makes that redundant).
  function isEditableTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  }

  function setupKeyboardNav() {
    document.addEventListener("keydown", (e) => {
      const overlayOpen = document.getElementById("guide-overlay")?.classList.contains("is-open");
      if (e.key === "Escape" && overlayOpen) {
        e.preventDefault();
        closeGuideOverlay();
        return;
      }
      if (e.key === "Escape" || (e.key === "Backspace" && !isEditableTarget(document.activeElement))) {
        e.preventDefault();
        history.back();
        return;
      }
      const rail = document.getElementById("nav-rail");
      const active = document.activeElement;
      if (!rail || !active || !rail.contains(active)) return;
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      const links = [...rail.querySelectorAll("a")];
      const idx = links.indexOf(active);
      if (idx === -1) return;
      e.preventDefault();
      const next = e.key === "ArrowDown" ? links[(idx + 1) % links.length] : links[(idx - 1 + links.length) % links.length];
      next.focus();
    });
  }

  async function boot() {
    await ensureLoggedIn();
    // Fire-and-forget: the backend dedupes to one grant per calendar day, so
    // calling this on every boot is safe and simplest (no client-side
    // "have I already checked in" tracking to keep in sync with the server).
    api.checkin(state.userId).then(r => { state.checkinResult = r; }).catch(() => {});
    renderBillbotDrawer();
    connectLive();
    setupKeyboardNav();
    await renderTopbar();
    window.addEventListener("hashchange", router);
    // First-run onboarding (GAPS.md: "No onboarding" -- found missing by
    // comparing against ui/Final Prosperity Showcase.html, which designed a
    // welcome screen the real app never built). Only hijacks a bare/root
    // landing, never a deep link -- someone arriving via a mission/gallery
    // link should land exactly there, not get detoured.
    const onboardKey = `evoke_onboarded_${state.userId}`;
    if (!localStorage.getItem(onboardKey) && (location.hash === "" || location.hash === "#/")) {
      location.hash = "#/welcome";
    }
    await router();
  }

  return { state, api, mount, boot, escapeHtml, toast, sfx, screens: {} };
})();
