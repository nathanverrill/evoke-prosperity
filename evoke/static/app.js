/* app.js — shared shell: API helpers, router, top bar, B1llbot drawer.
   Screen-specific rendering lives in screens.js. Hash-based routing in
   vanilla JS, per UI_SPEC.md ("no build pipeline"). */

const Evoke = (() => {
  const state = {
    userId: localStorage.getItem("evoke_user_id") || null,
    displayName: localStorage.getItem("evoke_display_name") || null,
    profile: null,
  };

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
    companionInfo: () => apiGet("/api/companion/info"),
    teamWheel: (teamId) => apiGet(`/api/team/${teamId}/wheel`),
    adminCohort: (userId) => apiGet(`/api/admin/cohort?user_id=${userId}`),
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
        // of it for the exact same event.
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
      if (d.user_id !== state.userId) toast(escapeHtml(d.message || ""));
    } else if (msg.type === "XPGranted" && d.user_id === state.userId) {
      renderTopbar();
    } else if (msg.type === "AwardGranted" && d.user_id === state.userId) {
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
        <a href="#/profile" class="notif-bell ${unreadCount ? "has-unread" : ""}">🔔 ${unreadCount}</a>
      </div>
    `;
    renderRail();
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

  async function boot() {
    await ensureLoggedIn();
    // Fire-and-forget: the backend dedupes to one grant per calendar day, so
    // calling this on every boot is safe and simplest (no client-side
    // "have I already checked in" tracking to keep in sync with the server).
    api.checkin(state.userId).then(r => { state.checkinResult = r; }).catch(() => {});
    renderBillbotDrawer();
    connectLive();
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

  return { state, api, mount, boot, escapeHtml, toast, screens: {} };
})();
