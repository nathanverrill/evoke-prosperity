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
    teamProfile: (teamId) => apiGet(`/api/profile/team/${teamId}`),
    timeline: (userId, missionId) => apiGet(`/api/timeline/${userId}/${missionId}`),
    mcQuests: (campaignId) => apiGet(`/api/mc-quests${campaignId ? "?campaign_id=" + campaignId : ""}`),
    submitQuest: (questId, formData) => apiPostForm(`/api/mc-quests/${questId}/submit`, formData),
    billbotChat: (userId, message) => apiPostJSON(`/api/billbot/chat?user_id=${userId}&message=${encodeURIComponent(message)}`, {}),
    devLogin: () => fetch("/api/dev-login", { method: "POST" }).then(r => r.json()),
    checkin: (userId) => fetch(`/api/checkin?user_id=${userId}`, { method: "POST" }).then(r => r.json()),
    activity: (limit) => apiGet(`/api/activity${limit ? "?limit=" + limit : ""}`),
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

  // ---------- Top bar ----------
  async function renderTopbar() {
    const el = document.getElementById("topbar");
    let xp = 0, level = 1;
    try {
      state.profile = await api.playerProfile(state.userId);
      xp = state.profile.xp;
      level = state.profile.level;
    } catch (e) { /* profile not ready yet -- empty state is fine */ }

    let unreadCount = 0;
    try {
      const n = await api.notifications(state.userId);
      unreadCount = (n.notifications || []).filter(x => !x.read).length;
    } catch (e) { /* ignore */ }

    const route = location.hash || "#/";
    const navLink = (href, label) =>
      `<a href="${href}" class="${route === href ? "is-active" : ""}">${label}</a>`;

    el.innerHTML = `
      <div class="topbar__left">
        <a href="#/" class="topbar__brand">EVOKE Prosperity</a>
        <nav class="topbar__nav">
          ${navLink("#/", "Operations Hub")}
          ${navLink("#/novel", "Novel")}
          ${navLink("#/profile", "Profile")}
        </nav>
      </div>
      <div class="topbar__right">
        <span class="xp-meter">${state.displayName || "Agent"} · Lv ${level} · ${xp} XP</span>
        <span class="streak-pill" title="Streak tracking not built yet">🔥 —</span>
        <a href="#/profile" class="notif-bell ${unreadCount ? "has-unread" : ""}">🔔 ${unreadCount}</a>
      </div>
    `;
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
      const log = document.getElementById("billbot-log");
      log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="user">${escapeHtml(msg)}</div>`);
      input.value = "";
      log.scrollTop = log.scrollHeight;
      try {
        const reply = await api.billbotChat(state.userId, msg);
        log.insertAdjacentHTML("beforeend", `<div class="billbot-msg" data-from="billbot">${escapeHtml(reply.reply)}</div>`);
      } catch (err) {
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
    { pattern: /^#\/$/, screen: "hub" },
    { pattern: /^#\/novel$/, screen: "novel" },
    { pattern: /^#\/mission\/([^/]+)$/, screen: "missionBrief" },
    { pattern: /^#\/mission\/([^/]+)\/debrief$/, screen: "missionDebrief" },
    { pattern: /^#\/profile$/, screen: "playerProfile" },
    { pattern: /^#\/profile\/([^/]+)$/, screen: "playerProfile" },
    { pattern: /^#\/team\/([^/]+)$/, screen: "teamProfile" },
  ];

  async function router() {
    const hash = location.hash || "#/";
    const screenEl = document.getElementById("screen");
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
    await renderTopbar();
    window.addEventListener("hashchange", router);
    await router();
  }

  return { state, api, mount, boot, escapeHtml, screens: {} };
})();
