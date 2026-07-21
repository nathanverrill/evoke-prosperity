(function () {
  "use strict";

  function getJSON(p) {
    return fetch(p, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { var e = new Error(p + " " + r.status); e.status = r.status; throw e; }
      return r.json();
    });
  }
  function postJSON(p, b) {
    return fetch(p, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}),
    }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (d) {
        throw new Error(d.detail || (p + " " + r.status));
      });
      return r.json();
    });
  }
  function putJSON(p, b) {
    return fetch(p, {
      method: "PUT", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(b || {}),
    }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (d) {
        throw new Error(d.detail || (p + " " + r.status));
      });
      return r.json();
    });
  }
  function postForm(p, fields) {
    var body = new URLSearchParams();
    Object.keys(fields).forEach(function (k) { body.append(k, fields[k]); });
    return fetch(p, { method: "POST", credentials: "same-origin", body: body }).then(function (r) {
      if (!r.ok) return r.json().catch(function () { return {}; }).then(function (d) {
        throw new Error(d.detail || (p + " " + r.status));
      });
      return r.json();
    });
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var POWERS = [
    "Imagination", "Ideation", "Vision", "Courage", "Communication", "Teamwork",
    "Networking", "Generosity of Spirit", "Problem Solving", "Analysis",
    "Aggregation", "Critical Reflection", "Leadership", "Empathy",
    "Transformation", "Curiosity",
  ];
  var ARCS = ["Explore", "Imagine", "Act", "Communicate"];

  var loginScreen = document.getElementById("login-screen");
  var dashboard = document.getElementById("dashboard");

  function showLogin(message) {
    loginScreen.style.display = "block";
    dashboard.style.display = "none";
    document.getElementById("login-error").textContent = message || "";
  }

  function showDashboard() {
    loginScreen.style.display = "none";
    dashboard.style.display = "block";
    loadMissions();
    loadDevUsersIfDevMode();
  }

  document.getElementById("login-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var username = document.getElementById("login-username").value.trim();
    var password = document.getElementById("login-password").value;
    postForm("/api/admin/login", { username: username, password: password })
      .then(function () { showDashboard(); })
      .catch(function (err) { showLogin(err.message || "Invalid admin credentials"); });
  });

  document.getElementById("logout-btn").addEventListener("click", function () {
    postJSON("/api/session/logout").catch(function () {}).then(function () { showLogin(); });
  });

  // ---------- Brightspace Mission Sync ----------
  // An Evoke mission is created first (its own form below) with its Evoke
  // curriculum fields; a Brightspace assignment is linked to an *existing*
  // mission afterward, one at a time -- never the other way around. Pulling
  // never writes anything; only the per-row "Link" action does, and only
  // to the one mission chosen in that row's select.
  var pulledAssignments = [];
  var latestMissions = [];

  document.getElementById("connect-brightspace-btn").addEventListener("click", function () {
    // Full navigation, not fetch -- this is an OAuth authorize redirect.
    // Doesn't touch this admin's login/session, only caches a token for
    // the pull below (see admin_brightspace_connect in main.py).
    window.location.href = "/api/admin/brightspace/connect";
  });

  document.getElementById("pull-assignments-btn").addEventListener("click", function () {
    var btn = this;
    var errEl = document.getElementById("pull-error");
    errEl.textContent = "";
    btn.disabled = true;
    getJSON("/api/admin/brightspace/assignments")
      .then(function (d) {
        pulledAssignments = d.assignments || [];
        renderAssignments();
      })
      .catch(function (err) { errEl.textContent = "Pull failed: " + err.message; })
      .then(function () { btn.disabled = false; });
  });

  function renderAssignments() {
    var wrap = document.getElementById("assignments-wrap");
    if (!pulledAssignments.length) {
      wrap.innerHTML = '<p class="empty-state">No assignments returned.</p>';
      return;
    }
    // Every mission created before real assignments existed still carries
    // its old sim ref (mission-01 etc.) -- those are exactly the ones that
    // need re-linking to a real ID, not excluded from the picker. Only the
    // label distinguishes "not yet linked" from "currently linked to X".
    var missionOptions = '<option value="">Link to mission…</option>' +
      latestMissions.map(function (m) {
        var label = m.lms_assignment_ref ? m.title + " (currently: " + m.lms_assignment_ref + ")" : m.title;
        return '<option value="' + m.id + '">' + escapeHtml(label) + '</option>';
      }).join("");

    wrap.innerHTML =
      '<table><thead><tr><th>Name</th><th>Brightspace ID</th><th>Status</th><th></th></tr></thead><tbody>' +
      pulledAssignments.map(function (a, i) {
        var blocked = a.errors && a.errors.length;
        var statusChip = a.already_mapped
          ? '<span class="chip chip--green">Linked</span>'
          : blocked
            ? '<span class="chip chip--err">' + escapeHtml(a.errors.join("; ")) + '</span>'
            : '<span class="chip">New</span>';
        var linkable = !a.already_mapped && !blocked;
        var linkCell = !linkable ? '' :
          latestMissions.length
            ? '<select data-link-idx="' + i + '">' + missionOptions + '</select> <button data-link-btn="' + i + '">Link</button>'
            : '<span class="empty-state">Create a mission first</span>';
        return '<tr>' +
          '<td>' + escapeHtml(a.name) + '</td>' +
          '<td>' + escapeHtml(a.id) + '</td>' +
          '<td>' + statusChip + '</td>' +
          '<td>' + linkCell + '</td>' +
        '</tr>';
      }).join("") +
      '</tbody></table>';

    wrap.querySelectorAll("[data-link-btn]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var idx = Number(btn.dataset.linkBtn);
        var sel = wrap.querySelector('[data-link-idx="' + idx + '"]');
        var missionId = sel.value;
        if (!missionId) { alert("Pick a mission to link to first."); return; }
        var mission = latestMissions.find(function (m) { return m.id === missionId; });
        if (mission && mission.lms_assignment_ref) {
          var ok = confirm('"' + mission.title + '" is currently linked to ' + mission.lms_assignment_ref + '. Re-link it to "' + pulledAssignments[idx].name + '" instead?');
          if (!ok) return;
        }
        linkAssignment(missionId, pulledAssignments[idx], btn);
      });
    });
  }

  function linkAssignment(missionId, assignment, btn) {
    btn.disabled = true;
    postJSON("/api/admin/missions/" + missionId + "/link-brightspace", {
      brightspace_assignment_id: assignment.id,
      grade_item_id: assignment.grade_item_id,
    })
      .then(function () {
        return loadMissions().then(function () {
          document.getElementById("pull-assignments-btn").click();
        });
      })
      .catch(function (err) { alert("Link failed: " + err.message); btn.disabled = false; });
  }

  // ---------- Brightspace Roster ----------
  document.getElementById("pull-roster-btn").addEventListener("click", function () {
    var btn = this;
    var errEl = document.getElementById("roster-error");
    var wrap = document.getElementById("roster-wrap");
    errEl.textContent = "";
    btn.disabled = true;
    getJSON("/api/admin/brightspace/roster")
      .then(function (d) {
        var roster = d.roster || [];
        if (!roster.length) {
          wrap.innerHTML = '<p class="empty-state">No students returned.</p>';
          return;
        }
        wrap.innerHTML =
          '<table><thead><tr><th>Name</th><th>Brightspace ID</th><th>Logged into Evoke?</th></tr></thead><tbody>' +
          roster.map(function (r) {
            return '<tr>' +
              '<td>' + escapeHtml(r.display_name) + '</td>' +
              '<td>' + escapeHtml(r.brightspace_user_id) + '</td>' +
              '<td>' + (r.logged_into_evoke ? '<span class="chip chip--green">Yes</span>' : '<span class="chip">Not yet</span>') + '</td>' +
            '</tr>';
          }).join("") +
          '</tbody></table>';
      })
      .catch(function (err) {
        errEl.textContent = "Roster pull failed: " + err.message +
          (err.status === 502 ? " — connected account may not be instructor/TA-level" : "");
      })
      .then(function () { btn.disabled = false; });
  });

  // ---------- Dev Users ----------
  // Only shown when no real login is configured (AUTH_PROVIDER unset) --
  // these two accounts are a local-dev stand-in for a Brightspace-connected
  // team, meaningless once a real tenant is wired up, so the card stays
  // hidden rather than confusing an instructor who has real students.
  function loadDevUsersIfDevMode() {
    getJSON("/api/auth/config")
      .then(function (cfg) {
        if (cfg.login_required) return;
        document.getElementById("dev-users-card").style.display = "block";
        loadDevUsers();
      })
      .catch(function () {});
  }

  function loadDevUsers() {
    return getJSON("/api/admin/dev-users").then(function (d) {
      renderDevUsers(d.dev_users || []);
    });
  }

  function renderDevUsers(users) {
    var wrap = document.getElementById("dev-users-wrap");
    wrap.innerHTML =
      '<table><thead><tr><th>Account</th><th>Team</th><th>XP / Level</th><th>Missions</th><th>Submissions</th><th></th></tr></thead><tbody>' +
      users.map(function (u) {
        if (!u.exists) {
          return '<tr><td>' + escapeHtml(u.email) + '</td><td colspan="4" class="empty-state">Not seeded yet -- run seed.py</td><td></td></tr>';
        }
        return '<tr>' +
          '<td>' + escapeHtml(u.display_name) + ' <span class="empty-state">(' + escapeHtml(u.email) + ')</span></td>' +
          '<td>' + escapeHtml(u.team_name || "—") + '</td>' +
          '<td>' + u.xp + ' XP · Lv ' + u.level + '</td>' +
          '<td>' + u.missions_completed + '</td>' +
          '<td>' + u.submissions + '</td>' +
          '<td><button data-reset-dev-user="' + escapeHtml(u.email) + '">Reset</button></td>' +
        '</tr>';
      }).join("") +
      '</tbody></table>';

    wrap.querySelectorAll("[data-reset-dev-user]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var email = btn.dataset.resetDevUser;
        if (!confirm('Reset ' + email + '\'s progress? Evidence, reflections, XP, badges, and chat history all clear. Team assignment stays.')) return;
        btn.disabled = true;
        postJSON("/api/admin/dev-users/" + encodeURIComponent(email) + "/reset")
          .then(loadDevUsers)
          .catch(function (err) { alert("Reset failed: " + err.message); btn.disabled = false; });
      });
    });
  }

  document.getElementById("reset-all-dev-users-btn").addEventListener("click", function () {
    if (!confirm("Reset both dev accounts' progress? Team assignment stays.")) return;
    var btn = this;
    btn.disabled = true;
    postJSON("/api/admin/dev-users/reset-all")
      .then(loadDevUsers)
      .catch(function (err) { alert("Reset failed: " + err.message); })
      .then(function () { btn.disabled = false; });
  });

  // ---------- Create Mission ----------
  document.getElementById("create-mission-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var input = document.getElementById("new-mission-title");
    var title = input.value.trim();
    if (!title) return;
    postJSON("/api/admin/missions", { title: title })
      .then(function () { input.value = ""; return loadMissions(); })
      .catch(function (err) { alert("Couldn't create mission: " + err.message); });
  });

  // ---------- Missions: release / stage / curriculum edit ----------
  function loadMissions() {
    return getJSON("/api/admin/missions")
      .then(function (d) {
        latestMissions = d.missions || [];
        renderMissions(latestMissions);
      })
      .catch(function (err) {
        if (err.status === 401 || err.status === 403) { showLogin(); return; }
        document.getElementById("missions-wrap").innerHTML =
          '<p class="empty-state">Couldn\'t load missions: ' + escapeHtml(err.message) + '</p>';
      });
  }

  function renderMissions(missions) {
    var wrap = document.getElementById("missions-wrap");
    if (!missions.length) {
      wrap.innerHTML = '<p class="empty-state">No missions yet — create one above.</p>';
      return;
    }
    wrap.innerHTML = missions.map(function (m) {
      return '<div class="mission-row" data-mission-id="' + m.id + '">' +
        '<div class="row-between">' +
          '<div><strong>' + escapeHtml(m.title) + '</strong> ' +
            '<span class="empty-state">Week ' + (m.week == null ? "—" : m.week) + ' · ' + escapeHtml(m.arc || "no arc") + '</span></div>' +
          '<span class="row">' +
            '<span class="chip ' + (m.lms_assignment_ref ? "chip--green" : "") + '">' + (m.lms_assignment_ref ? ("Linked: " + escapeHtml(m.lms_assignment_ref)) : "Not linked to Brightspace") + '</span>' +
            '<span class="chip ' + (m.released ? "chip--green" : "") + '">' + (m.released ? "Released" : "Not released") + '</span>' +
          '</span>' +
        '</div>' +
        '<div class="row" style="margin-top:8px">' +
          '<button data-action="' + (m.released ? "unrelease" : "release") + '" data-mission-id="' + m.id + '">' + (m.released ? "Unrelease" : "Release") + '</button>' +
          '<label class="empty-state">Stage ' +
            '<select data-stage-for="' + m.id + '">' +
              Array.from({ length: 8 }, function (_, i) { return i + 1; }).map(function (n) {
                return '<option value="' + n + '"' + ((m.stage || m.week) === n ? " selected" : "") + '>' + n + '</option>';
              }).join("") +
            '</select></label>' +
          '<button data-toggle-edit="' + m.id + '">Edit curriculum fields</button>' +
          (m.lms_assignment_ref ? '<button data-sync-grades="' + m.id + '">Sync grades</button>' : '') +
        '</div>' +
        '<form class="mission-edit-form" data-edit-form="' + m.id + '">' +
          '<label>Arc <select name="arc">' +
            '<option value="">—</option>' +
            ARCS.map(function (a) { return '<option value="' + a + '">' + a + '</option>'; }).join("") +
          '</select></label>' +
          '<label>PFL Domain <input name="pfl_domain" type="text"></label>' +
          '<label>Superpower <input name="superpower" list="powers-list" type="text"></label>' +
          '<label>Primary Skill <input name="primary_skill" list="powers-list" type="text"></label>' +
          '<label>Secondary Skill <input name="secondary_skill" list="powers-list" type="text"></label>' +
          '<label>Week <input name="week" type="number" min="1"></label>' +
          '<label class="wide">Mission Brief (short) <textarea name="mission_brief_md"></textarea></label>' +
          '<label class="wide">Your Mission (full narrative) <textarea name="pbl_description"></textarea></label>' +
          '<label class="wide">Evidence checklist <textarea name="evidence_requirements_md"></textarea></label>' +
          '<div class="wide row"><button type="submit" class="primary">Save</button></div>' +
        '</form>' +
      '</div>';
    }).join("") +
    '<datalist id="powers-list">' + POWERS.map(function (p) { return '<option value="' + p + '">'; }).join("") + '</datalist>';

    wrap.querySelectorAll("[data-action]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var missionId = btn.dataset.missionId;
        var action = btn.dataset.action;
        btn.disabled = true;
        postJSON("/api/admin/missions/" + missionId + "/" + action)
          .then(loadMissions)
          .catch(function (err) { alert("Failed: " + err.message); btn.disabled = false; });
      });
    });
    wrap.querySelectorAll("[data-stage-for]").forEach(function (sel) {
      sel.addEventListener("change", function () {
        postForm("/api/admin/missions/" + sel.dataset.stageFor + "/stage", { stage: sel.value })
          .catch(function (err) { alert("Couldn't set stage: " + err.message); });
      });
    });
    wrap.querySelectorAll("[data-toggle-edit]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var form = wrap.querySelector('[data-edit-form="' + btn.dataset.toggleEdit + '"]');
        if (form) form.classList.toggle("open");
      });
    });
    wrap.querySelectorAll("[data-sync-grades]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var missionId = btn.dataset.syncGrades;
        btn.disabled = true;
        var original = btn.textContent;
        btn.textContent = "Syncing…";
        postJSON("/api/admin/missions/" + missionId + "/sync-grades")
          .then(function (d) {
            alert("Synced " + d.synced.length + " grade(s)" + (d.skipped_no_match.length ? "; " + d.skipped_no_match.length + " skipped (no matching student/submission)" : ""));
          })
          .catch(function (err) { alert("Grade sync failed: " + err.message); })
          .then(function () { btn.disabled = false; btn.textContent = original; });
      });
    });
    wrap.querySelectorAll("[data-edit-form]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        var missionId = form.dataset.editForm;
        var fd = new FormData(form);
        var body = {};
        ["arc", "pfl_domain", "superpower", "primary_skill", "secondary_skill",
          "mission_brief_md", "pbl_description", "evidence_requirements_md"].forEach(function (k) {
          var v = (fd.get(k) || "").toString().trim();
          if (v) body[k] = v;
        });
        var week = (fd.get("week") || "").toString().trim();
        if (week) body.week = Number(week);
        var submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        putJSON("/api/admin/missions/" + missionId, body)
          .then(loadMissions)
          .catch(function (err) { alert("Save failed: " + err.message); submitBtn.disabled = false; });
      });
    });
  }

  // ---------- Boot ----------
  getJSON("/api/admin/missions").then(showDashboard).catch(function () { showLogin(); });
})();
