/* controller.js — drives the pixel-exact UI (v2.html, taken verbatim from the
   design team's Prosperity Showcase-44.html) with the REAL EVOKE backend.

   The screen-rendering logic below is the designer's own code, unchanged, so
   every screen, flow, spacing, and animation is identical to the design file.
   Only the *data source* is rewired: instead of the demo's leaked-key LLM and
   pure-localStorage state, we log in for real, seed mission progress from the
   backend, and route B1llBot chat through /api/billbot/chat. */
(function(){
  "use strict";
  var CONTENT = window.EVOKE_CONTENT;
  if(!CONTENT){ console.error('EVOKE content missing (content.js failed to load)'); return; }

  // ----- backend bridge -----
  var STATE = { userId:null, displayName:null, profile:null, missionIds:[] };
  function getJSON(p){ return fetch(p).then(function(r){ if(!r.ok) throw new Error(p+' '+r.status); return r.json(); }); }
  function postJSON(p,b){ return fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}).then(function(r){ return r.json(); }); }

  // B1llBot: the design calls llmComplete() when LLM.endpoint+apiKey are set,
  // else falls back to canned keyword replies. Point it at the real endpoint.
  var LLM = { endpoint:'/api/billbot/chat', apiKey:'backend' };
  function llmComplete(q, history){
    if(!STATE.userId) return Promise.resolve(null);
    return fetch('/api/billbot/chat?user_id='+encodeURIComponent(STATE.userId)+'&message='+encodeURIComponent(q), {method:'POST'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        var reply = d && (d.reply||d.message||d.response||d.text) || null;
        // When the backend's upstream model is unreachable it still returns 200
        // with an error-shaped string. Treat those as a miss so the design's
        // polished keyword fallback answers instead of showing a raw error.
        if(reply && /^(error:|i'?m having trouble|hmm, lost my train)/i.test(reply.trim())) return null;
        return reply;
      })
      .catch(function(){ return null; });
  }
  // Vault recap: design uses window.claude.complete if present, else a graceful
  // local fallback. No backend recap endpoint yet -> leave undefined (fallback).

  // Persist real evidence when the learner completes a mission. Best-effort:
  // never blocks the identical local flow if the backend rejects (no team, no
  // file, unreleased mission, etc.).
  window.evokeBackendSubmit = function(designMissionNo){
    try{
      var mid = STATE.missionIds[designMissionNo-1];
      if(!mid || !STATE.userId) return;
      var stmt = '';
      var os = document.getElementById('ev-statement'); if(os) stmt = os.value || '';
      // Reflection (no file required) — the design's statement maps to a reflection.
      var fd = new FormData();
      fd.append('user_id', STATE.userId); fd.append('mission_id', mid);
      fd.append('reflection', stmt || 'Submitted via EVOKE.');
      fetch('/api/submit-reflection', {method:'POST', body:fd}).catch(function(){});
    }catch(e){}
  };

  // Seed the design's per-mission localStorage flags from real backend
  // completion so all render logic reflects the learner's true progress.
  // Backend /api/missions is ordered by (week, sequence) — the SAME order as
  // the design's sequential missions 1..12 — so index i maps to design N=i+1.
  function seedFromBackend(){
    return postJSON('/api/dev-login').then(function(d){
      STATE.userId = d.user_id; STATE.displayName = d.display_name;
      try{ localStorage.setItem('evoke_user_id', STATE.userId); }catch(e){}
      return Promise.all([
        getJSON('/api/missions?user_id='+STATE.userId).catch(function(){ return {missions:[]}; }),
        getJSON('/api/profile/player/'+STATE.userId).catch(function(){ return null; })
      ]);
    }).then(function(res){
      var missions = (res[0] && res[0].missions) || [];
      STATE.profile = res[1];
      STATE.missionIds = missions.map(function(m){ return m.id; });
      var done = {};
      if(STATE.profile && STATE.profile.missions_completed){
        STATE.profile.missions_completed.forEach(function(id){ done[String(id)] = true; });
      }
      try{
        // clear then seed, so a returning learner sees their real state
        for(var n=1;n<=12;n++){ localStorage.removeItem('evoke-m'+n+'-submitted'); localStorage.removeItem('evoke-m'+n+'-started'); }
        var firstIncomplete = 0;
        missions.forEach(function(m, i){
          var no = i+1;
          if(done[String(m.id)]){ localStorage.setItem('evoke-m'+no+'-submitted','1'); }
          else if(!firstIncomplete){ firstIncomplete = no; }
        });
        if(firstIncomplete) localStorage.setItem('evoke-m'+firstIncomplete+'-started','1');
        // real agent name in Profile (only if the learner hasn't set their own)
        if(STATE.displayName && !localStorage.getItem('evoke-agent-name')){
          localStorage.setItem('evoke-agent-name', STATE.displayName);
        }
      }catch(e){}
      // real Minecraft server address — only override the design default when
      // the backend gives a genuine public host (ignore dev's localhost).
      getJSON('/api/minecraft/connect-info').then(function(ci){
        var host = ci && (ci.server || ci.host || ci.address);
        if(host && !/^(localhost|127\.|0\.0\.0\.0)/.test(host)){ var el2=document.getElementById('mc-server'); if(el2) el2.textContent = host; }
      }).catch(function(){});
    }).catch(function(e){ console.warn('backend seed failed; using local demo state', e); });
  }

  // ----- the designer's screen logic, verbatim, booted after seeding -----
  seedFromBackend().then(function(){

  var SCREENS = [["home","Learn"],["ops","Ops Hub"],["progress","Progress"],["vault","Vault"],["billbot","B1llBot"],["profile","Profile"],["welcome","Intro"],["novel","Novel"],["story","Transmission"],["assignment","Assignment"],["evidence","Evidence"],["minecraft","Minecraft"],["companion","Companion"],["reward","Complete"]];

  /* ---- helpers ---- */
  function el(html){var d=document.createElement('div');d.innerHTML=html.trim();return d.firstChild;}
  function brandLockup(){return '<img class="wordmark-img" src="img/evoke-wordmark.png" alt="'+CONTENT.brand+'">';}
  /* ---- unified XP model (spans all 12 missions across 6 weeks) ----
     500 XP per mission, 1000 XP per level → a level every 2 missions (one per week).
     12 missions = 6000 XP = Level 7 at the finish line. */
  var XP_PER_MISSION=500, XP_PER_LEVEL=1000, TOTAL_MISSIONS=12, MAX_LEVEL=7;
  function countCompleted(){ var c=0; for(var i=1;i<=TOTAL_MISSIONS;i++){ if(missionState(i)==='complete') c++; } return c; }
  function evokeXP(){
    var missions=countCompleted();
    var total=missions*XP_PER_MISSION;
    var level=Math.min(MAX_LEVEL, Math.floor(total/XP_PER_LEVEL)+1);
    var into=total-(level-1)*XP_PER_LEVEL;          // XP earned within the current level
    var maxed=missions>=TOTAL_MISSIONS;
    return { sub:missionState(1)==='complete', xp:into, max:XP_PER_LEVEL, level:level,
             toNext:maxed?0:(XP_PER_LEVEL-into), missions:missions, total:total, maxed:maxed };
  }
  /* ---- mission lifecycle: notstarted -> inprogress -> complete ---- */
  function missionState(id){
    var started=false, submitted=false;
    try{ started=localStorage.getItem('evoke-m'+id+'-started')==='1'; submitted=localStorage.getItem('evoke-m'+id+'-submitted')==='1'; }catch(e){}
    return submitted ? 'complete' : (started ? 'inprogress' : 'notstarted');
  }
  function markStarted(id){ try{ localStorage.setItem('evoke-m'+id+'-started','1'); }catch(e){} if(window.renderOps) window.renderOps(id); }
  window.missionState=missionState; window.markStarted=markStarted;
  /* ---- developer mode: browse any week now; students stay sequence-locked ---- */
  function devOn(){ try{ return localStorage.getItem('evoke-dev')==='1'; }catch(e){ return false; } }
  function devSel(){ try{ var v=parseInt(localStorage.getItem('evoke-dev-mission'),10); return (v>=1&&v<=12)?v:1; }catch(e){ return 1; } }
  window.devOn=devOn; window.devSel=devSel;
  /* which mission is the student currently on? Sequential: mission N unlocks once N-1 is complete.
     In developer mode, the selected mission is shown directly. */
  function curMission(){ if(devOn()) return devSel(); for(var i=1;i<=12;i++){ if(missionState(i)!=='complete') return i; } return 12; }
  /* resolve per-mission content (novel / transmission / assignment) for the current mission */
  function MD(key){ var m=curMission(); return CONTENT[key+'_m'+m] || CONTENT[key]; }
  window.curMission=curMission;
  function syncAllXP(){
    var X=evokeXP(), pct=Math.round(X.xp/X.max*100);
    function set(id,fn){var n=document.getElementById(id); if(n) fn(n);}
    set('home-xp-line',function(n){ n.textContent = X.maxed ? 'All missions complete \u2014 Level '+X.level+' reached. Outstanding work, Agent.' : (X.xp>0 ? (X.toNext+' XP to Level '+(X.level+1)+' \u2014 keep it up, Agent.') : 'Submit your first mission to start earning XP.'); });
    set('home-xp-track',function(n){ n.querySelector('.fill-xp').style.width=pct+'%'; n.querySelector('.knob').style.left=pct+'%'; n.setAttribute('aria-valuenow',X.xp); n.setAttribute('aria-label',X.xp+' of '+X.max+' XP to Level '+(X.level+1)); });
    set('home-xp-now',function(n){ n.textContent=X.xp+' XP'; });
    set('home-xp-goal',function(n){ n.textContent = X.maxed ? 'Level '+X.level+' \u00b7 Max' : (X.toNext+' XP to Lv.'+(X.level+1)); });
    document.querySelectorAll('.agent-hdr-level').forEach(function(n){ n.textContent='Agent Level '+X.level; });
    document.querySelectorAll('.agent-hdr-fill').forEach(function(n){ n.style.width=pct+'%'; });
    document.querySelectorAll('.agent-hdr-xp').forEach(function(n){ n.textContent=X.xp+' / '+X.max+' XP'; });
    set('pg-track',function(n){ n.querySelector('.fill-xp').style.width=pct+'%'; n.querySelector('.knob').style.left=pct+'%'; n.setAttribute('aria-valuenow',X.xp); });
    set('pg-xp',function(n){ n.textContent=X.xp+' XP'; });
    set('pg-missions',function(n){ n.textContent=String(X.missions); });
    set('pf-xpline',function(n){ n.textContent = X.maxed ? ('Level '+X.level+' \u00b7 Max rank reached') : (X.xp+' / '+X.max+' XP to Level '+(X.level+1)); });
  }
  window.syncAllXP=syncAllXP;

  /* ---- brand lockups (top bars + nav) — logo returns Home ---- */
  document.querySelectorAll('.brand-static').forEach(function(n){
    n.innerHTML = brandLockup();
    n.setAttribute('data-go','home');
    n.setAttribute('role','link');
    n.setAttribute('tabindex','0');
    n.setAttribute('aria-label','Go to Home');
    n.style.cursor='pointer';
  });

  // in-content "Back" buttons (next to forward CTAs / headers) use history
  document.querySelectorAll('.back-step').forEach(function(b){ b.addEventListener('click', goBack); });
  // The Minecraft screen's Back returns to its hub (Ops), not deep history.
  document.querySelectorAll('.screen[data-screen="minecraft"] .back-step').forEach(function(b){
    var clone = b.cloneNode(true); b.parentNode.replaceChild(clone, b); // drop the generic goBack handler
    clone.addEventListener('click', function(){ go('ops'); });
  });

  /* ---- nav rail ---- */
  var nav = document.getElementById('primary-nav');
  nav.appendChild(el('<div class="brand-lockup lockup">'+brandLockup()+'</div>'));
  CONTENT.nav.forEach(function(it){
    var b = el('<button class="nav" data-go="'+it.id+'"><span class="ms '+(it.fill?'fill':'')+'" aria-hidden="true" style="font-size:28px;">'+it.icon+'</span><span class="lbl">'+it.label+'</span></button>');
    nav.appendChild(b);
  });

  /* ---- greeting ---- */
  document.getElementById('greet-kicker').textContent = CONTENT.greeting.kicker;
  document.getElementById('greet-title').textContent  = CONTENT.greeting.title;
  document.getElementById('greet-sub').textContent     = CONTENT.greeting.sub;

  /* ---- streak: real days the student opened the app (this week) ---- */
  function localISO(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }
  function evokeStreak(){
    var labels=['M','T','W','TH','F','S','SU'];
    var today=new Date();
    var visits={}; try{ visits=JSON.parse(localStorage.getItem('evoke-visits')||'{}'); }catch(e){}
    visits[localISO(today)]=1;
    try{ localStorage.setItem('evoke-visits',JSON.stringify(visits)); }catch(e){}
    var dow=(today.getDay()+6)%7; // 0 = Monday
    var monday=new Date(today); monday.setDate(today.getDate()-dow);
    var days=[], count=0;
    for(var i=0;i<7;i++){ var d=new Date(monday); d.setDate(monday.getDate()+i); var on=visits[localISO(d)]?1:0; if(on)count++; days.push([labels[i],on]); }
    return { days:days, count:count };
  }
  function renderStreaks(){
    var s=evokeStreak();
    ['streak','pg-streak'].forEach(function(id){ var n=document.getElementById(id); if(!n) return; n.innerHTML=''; s.days.forEach(function(d){ n.appendChild(el('<div class="day '+(d[1]?'on':'')+'">'+d[0]+'</div>')); }); });
    var sc=document.getElementById('pg-streak-count'); if(sc) sc.textContent=String(s.count);
  }
  window.renderStreaks=renderStreaks; renderStreaks();

  /* ---- POWER BADGES: the app's 16 Powers grouped under the 4 Superpowers ----
     A Power is earned by completing a mission tagged with its skill (mirrors the
     backend's mission-tag -> Power mapping in skills_framework). Themed Material
     Symbols icons; earned = green glow, locked = dim + lock. */
  var POWER_META = {
    "Creativity":["Creative Visionary","palette"],
    "Imagination":["Creative Visionary","lightbulb"],
    "Vision":["Creative Visionary","visibility"],
    "Problem Solving":["Systems Thinker","extension"],
    "Research & Analysis":["Systems Thinker","analytics"],
    "Critical Reflection":["Systems Thinker","psychology"],
    "Teamwork":["Deep Collaborator","groups"],
    "Communication":["Deep Collaborator","forum"],
    "Relationship Management":["Deep Collaborator","handshake"],
    "Empathy":["Empathetic Changemaker","favorite"],
    "Leadership":["Empathetic Changemaker","flag"],
    "Courage":["Empathetic Changemaker","bolt"]
  };
  var QUALITY_META = { "Creative Visionary":"auto_awesome", "Systems Thinker":"account_tree", "Deep Collaborator":"diversity_3", "Empathetic Changemaker":"volunteer_activism" };
  var QUALITY_ORDER = ["Creative Visionary","Systems Thinker","Deep Collaborator","Empathetic Changemaker"];
  var POWER_ALIAS = {};
  var TOTAL_POWERS = Object.keys(POWER_META).length;
  function earnedPowerSet(){
    var set={}, ms=window.EVOKE_SUBMISSION_MISSIONS||[];
    ms.forEach(function(m){
      if(missionState(m.n)!=='complete') return;
      (m.skills||[]).forEach(function(sk){ var p=POWER_ALIAS[sk]||sk; if(POWER_META[p]) set[p]=true; });
    });
    return set;
  }
  function powerGroups(){
    var earned=earnedPowerSet(), g={};
    QUALITY_ORDER.forEach(function(q){ g[q]={quality:q,icon:QUALITY_META[q],powers:[]}; });
    Object.keys(POWER_META).forEach(function(p){ var q=POWER_META[p][0]; g[q].powers.push({name:p,icon:POWER_META[p][1],earned:!!earned[p]}); });
    return QUALITY_ORDER.map(function(q){return g[q];});
  }
  function totalPowersEarned(){ return Object.keys(earnedPowerSet()).length; }
  function powerTile(p, s){
    s=s||54; var on=p.earned;
    var box = on
      ? 'background:radial-gradient(circle at 50% 35%,rgba(0,212,146,0.28),rgba(0,150,137,0.10));box-shadow:inset 0 0 0 1.5px var(--green-400),0 0 18px -4px rgba(0,212,146,0.55);color:var(--green-400);'
      : 'box-shadow:inset 0 0 0 1px var(--border-ui);color:var(--text-faint);';
    return '<div style="display:flex;flex-direction:column;align-items:center;gap:7px;text-align:center;min-width:0;opacity:'+(on?'1':'0.72')+';">'
      +'<span style="width:min(100%,'+s+'px);aspect-ratio:1;border-radius:14px;display:flex;align-items:center;justify-content:center;'+box+'"><span class="ms'+(on?' fill':'')+'" aria-hidden="true" style="font-size:'+Math.round(s*0.46)+'px;">'+(on?p.icon:'lock')+'</span></span>'
      +'<span style="font-family:var(--font-display);font-weight:600;font-size:10.5px;line-height:1.15;overflow-wrap:anywhere;hyphens:auto;color:'+(on?'var(--teal-050)':'var(--text-faint)')+';">'+p.name+'</span></div>';
  }
  window.powerGroups=powerGroups; window.totalPowersEarned=totalPowersEarned;

  /* ---- badges: the 4 Superpower rings on Home, each filled by its 4 Powers ---- */
  var badges = document.getElementById('badges');
  function renderHomeBadges(){
    if(!badges) return;
    var C=175.9;
    badges.innerHTML = powerGroups().map(function(g){
      var lvl=g.powers.filter(function(p){return p.earned;}).length, on=lvl>0;
      var off=(C*(1 - lvl/g.powers.length)).toFixed(1);
      return '<div class="sp-tile'+(on?'':' locked')+'" role="img" aria-label="'+g.quality+', '+lvl+' of '+g.powers.length+' powers">'
        +'<div class="sp-ring"><svg viewBox="0 0 64 64" aria-hidden="true"><circle class="bg" cx="32" cy="32" r="28"></circle>'
        +'<circle class="fg" cx="32" cy="32" r="28" stroke-dasharray="'+C.toFixed(1)+'" stroke-dashoffset="'+off+'"></circle></svg>'
        +'<span class="ic"><span class="ms" aria-hidden="true">'+(on?g.icon:'lock')+'</span></span>'+(on?'<span class="lv">'+lvl+'</span>':'')
        +'</div><div class="lbl">'+g.quality+'</div></div>';
    }).join('');
    var hdr = document.getElementById('badges-week'); if(hdr) hdr.textContent=totalPowersEarned()+' of '+TOTAL_POWERS+' powers';
  }
  window.renderHomeBadges=renderHomeBadges; renderHomeBadges();

  /* ---- timeline: 6 WEEKS, locked linear order ---- */
  var tl = document.getElementById('timeline');
  function renderTimeline(){
    tl.innerHTML='';
    var done = evokeXP().missions;
    CONTENT.weeks.forEach(function(wk,wi){
      var firstIdx=wi*2, secondIdx=wi*2+1;
      var status = done>=secondIdx+1 ? 'complete' : (done>=firstIdx ? 'current' : 'locked');
      if(devOn() && status==='locked') status='current';
      var left = wi%2===0, isLocked = status==='locked';
      var msCount = wk.missions.length;
      var doneInWeek = Math.max(0, Math.min(done - firstIdx, msCount));
      var mode = status==='complete' ? 'Complete' : isLocked ? 'Locked' : (doneInWeek===0 ? 'Begin' : 'Continue');
      var label = mode;
      var col = status==='complete'?'var(--orange-500)':status==='current'?'var(--cyan-300)':'var(--text-locked)';
      var dots='';
      for(var di=0; di<msCount; di++){ dots += '<span aria-hidden="true" style="width:8px;height:8px;border-radius:50%;background:'+(!isLocked && di<doneInWeek?col:'rgba(145,209,209,0.22)')+';box-shadow:'+(!isLocked && di<doneInWeek?'0 0 6px '+col:'none')+';"></span>'; }
      var row = el('<div style="display:flex;justify-content:'+(left?'flex-start':'flex-end')+';margin-bottom:28px;"></div>');
      var card = el('<button class="tl-card" '+(isLocked?'disabled aria-disabled="true"':'')+' style="text-align:'+(left?'left':'right')+';color:var(--text-heading);cursor:'+(isLocked?'not-allowed':'pointer')+';opacity:1;background:'+(isLocked?'rgba(15,23,43,0.4)':'var(--surface-glass)')+';box-shadow:'+(isLocked?'inset 0 0 0 1px rgba(145,209,209,0.15)':'var(--elev-glass)')+';" aria-label="Week '+wk.week+', '+label+'"></button>');
      card.innerHTML =
        '<span class="ms tl-ic '+status+'" aria-hidden="true" style="'+(left?'right':'left')+':20px;">'+(isLocked?'lock':(wk.missions[0]&&wk.missions[0].icon||'rocket_launch'))+'</span>'+
        '<span class="hud" style="position:relative;z-index:1;font-size:11px;color:var(--text-faint);'+(left?'':'display:block;text-align:right;')+'">Week</span>'+
        '<span aria-hidden="true" style="position:relative;z-index:1;display:block;font-family:var(--font-display);font-weight:800;font-size:50px;line-height:1;color:'+col+';'+(isLocked?'':'text-shadow:0 0 24px rgba(0,150,136,0.22);')+'">'+wk.week+'</span>'+
        '<span style="position:absolute;z-index:1;bottom:14px;left:22px;right:20px;display:flex;align-items:center;justify-content:space-between;gap:8px;">'+
          '<span style="font-family:var(--font-mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:'+col+';">'+(mode==='Begin'?'\u25b6 Begin':mode==='Continue'?'\u25b6 Continue \u00b7 '+doneInWeek+'/'+msCount:mode==='Complete'?'\u2713 Complete':mode)+'</span>'+
          '<span style="display:flex;align-items:center;gap:6px;">'+dots+'</span>'+
        '</span>';
      if(!isLocked) card.addEventListener('click', function(){ currentWeek=wi; novelForce=wi*2+1; renderMissions(wi); go(wi===0 ? 'welcome' : 'novel'); });
      row.appendChild(card); tl.appendChild(row);
    });
  }
  renderTimeline();

  /* ---- Mission Control: the selected week's 2 missions (sequence-locked) ---- */
  var currentWeek = Math.min(Math.floor(evokeXP().missions/2), CONTENT.weeks.length-1);
  var mc = document.getElementById('missions');
  function renderMissions(weekIdx){
    var wk = CONTENT.weeks[weekIdx], done = evokeXP().missions;
    var sub = document.getElementById('mc-subtitle');
    if(sub) sub.textContent = '/// Week '+wk.week+' \u00b7 choose your assignment ///';
    mc.innerHTML='';
    wk.missions.forEach(function(m,mi){
      var idx = weekIdx*2+mi;
      var status = idx<done ? 'complete' : (idx===done ? 'current' : 'locked');
      if(devOn() && status==='locked') status='current';
      var sLabel = status==='complete'?'Completed':status==='current'?'Available now':'Locked';
      var sCol   = status==='complete'?'var(--green-400)':status==='current'?'var(--cyan-300)':'var(--text-locked)';
      var bLabel = status==='complete'?'Review \u25b6':status==='current'?'Begin Mission \u25b6':'Locked';
      var actionHTML = status==='complete'
        ? '<div role="status" aria-label="Completed: '+m.title+'" style="width:100%;height:56px;margin-top:14px;display:flex;align-items:center;justify-content:center;gap:8px;border-radius:var(--radius-lg);box-shadow:inset 0 0 0 1px rgba(0,212,146,0.4);background:rgba(0,212,146,0.08);color:var(--green-400);font-family:var(--font-display);font-weight:700;font-size:15px;"><span class="ms" aria-hidden="true" style="font-size:20px;">check_circle</span>Completed</div>'
        : '<button class="btn '+(status==='current'?'':'sec')+'" '+(status==='locked'?'disabled aria-disabled="true"':'')+' style="width:100%;height:56px;margin-top:14px;position:relative;'+(status==='locked'?'cursor:not-allowed;':'')+'" aria-label="'+sLabel+': '+m.title+'">'+bLabel+(status==='current'?'<span class="key" aria-hidden="true"></span>':'')+'</button>';
      var card = el('<div class="glass mcard brackets" style="position:relative;"></div>');
      card.innerHTML =
        '<span class="ghostnum" aria-hidden="true">'+(mi+1)+'</span>'+
        '<div style="display:flex;justify-content:space-between;align-items:flex-start;position:relative;">'+
          '<div class="mtile"><span class="ms" aria-hidden="true" style="font-size:30px;">'+(status==='locked'?'lock':m.icon)+'</span></div>'+
          '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">'+
            '<span style="font-family:var(--font-mono);font-size:13px;color:var(--cyan-300);padding:4px 10px;border-radius:8px;background:rgba(0,150,136,0.10);box-shadow:inset 0 0 0 1px var(--border-ui);">W'+wk.week+' \u00b7 M'+(mi+1)+'</span>'+
            '<span class="hud" style="font-size:11px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,0.04);color:'+sCol+';">'+sLabel+'</span>'+
          '</div></div>'+
        '<h2 style="font-family:var(--font-display);font-weight:700;font-size:clamp(22px,4vw,28px);text-transform:uppercase;color:var(--text-heading);margin:16px 0 5px;position:relative;">'+m.title+'</h2>'+
        '<div style="font-family:var(--font-display);font-weight:500;font-size:15px;color:var(--cyan-300);margin-bottom:10px;position:relative;">'+m.sub+'</div>'+
        '<p style="font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--teal-100);margin:0 0 14px;position:relative;">'+m.desc+'</p>'+
        '<div style="display:flex;align-items:center;justify-content:space-between;height:56px;margin-top:auto;padding:0 18px;border-radius:12px;box-shadow:inset 0 0 0 1px var(--border-ui);position:relative;gap:12px;">'+
          '<span style="display:flex;align-items:center;gap:10px;color:var(--text-muted);font-family:var(--font-body);font-size:15px;"><span class="ms" aria-hidden="true" style="font-size:20px;">military_tech</span>Badge</span>'+
          '<span style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--teal-050);text-align:right;">'+m.badge+'</span>'+
        '</div>'+
        actionHTML;
      var btn = card.querySelector('button.btn');
      if(status==='current') btn.addEventListener('click',function(){ if(devOn()){ try{localStorage.setItem('evoke-dev-mission',String(idx+1));}catch(e){} } go('story'); });
      mc.appendChild(card);
    });
  }
  renderMissions(currentWeek);

  /* ---- rewards ---- */
  var rw = document.getElementById('rewards');
  CONTENT.rewards.forEach(function(r){
    rw.appendChild(el(
      '<div class="glass" style="width:300px;max-width:100%;padding:32px;text-align:center;position:relative;overflow:hidden;">'+
        '<span aria-hidden="true" style="position:absolute;top:-30px;right:-30px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(217,164,65,0.45),transparent 70%);"></span>'+
        '<div style="width:84px;height:84px;margin:0 auto 20px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-shadow:inset 0 0 0 2px var(--cyan-300),var(--glow-md);"><span class="ms" aria-hidden="true" style="font-size:38px;color:var(--cyan-100);">'+r.icon+'</span></div>'+
        '<div style="font-family:var(--font-display);font-weight:700;font-size:18px;color:var(--teal-050);margin-bottom:6px;">'+r.name+'</div>'+
        '<div class="hud" style="font-size:12px;">'+r.sub+'</div>'+
      '</div>'));
  });

  /* ---- vault ---- */
  var vault = document.getElementById('vault');
  function renderVault(){
    vault.innerHTML='';
    var any=false;
    CONTENT.vault.forEach(function(v){
      if(missionState(v.mission)!=='complete') return;
      any=true;
      var _wp=(v.n||'').split('·'); var wm=_wp.length===2?('WEEK '+_wp[0].replace(/\D/g,'')+' · MISSION '+_wp[1].replace(/\D/g,'')):(v.n||'');
      var card = el('<button class="glass vault-card" style="text-align:left;border:none;cursor:pointer;color:inherit;position:relative;" aria-label="Review '+wm+', '+v.title+', badge '+v.badge+'"></button>');
      card.innerHTML =
        
        '<div style="padding:22px 24px;">'+
        '<div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;">'+
          '<div class="mtile" style="width:48px;height:48px;flex:none;"><span class="ms" aria-hidden="true" style="font-size:24px;">'+v.icon+'</span></div>'+
          '<div><div class="hud" style="font-size:10.5px;color:var(--cyan-300);letter-spacing:.14em;margin-bottom:5px;">'+wm+'</div><div style="font-family:var(--font-display);font-weight:700;font-size:19px;color:var(--text-heading);text-transform:uppercase;line-height:1.1;">'+v.title+'</div>'+
          '<div class="hud" style="font-size:11px;color:var(--green-400);margin-top:4px;">'+v.date+'</div></div>'+
          '<span class="ms" aria-hidden="true" style="margin-left:auto;font-size:22px;color:var(--cyan-300);">chevron_right</span>'+
        '</div>'+
        '<p style="font-family:var(--font-body);font-size:15px;line-height:1.6;color:var(--teal-100);margin:0 0 18px;">'+v.desc+'</p>'+
        '<span class="chip teal"><span class="ms" aria-hidden="true" style="font-size:16px;">military_tech</span>'+v.badge+'</span>'+
        '</div>';
      card.addEventListener('click', function(){ openRecap(v); });
      vault.appendChild(card);
    });
    if(!any){ vault.innerHTML='<div class="glass" style="padding:34px;text-align:center;grid-column:1/-1;"><span class="ms" aria-hidden="true" style="font-size:36px;color:var(--text-faint);">inventory_2</span><p style="font-family:var(--font-body);font-size:15px;color:var(--text-faint);margin:12px 0 0;">No missions archived yet. Complete a mission and it will appear here for review.</p></div>'; }
  }
  renderVault();

  /* ---- Vault recap popup: an AI-generated summary of the whole mission.
         "Re-read Story" still opens the full comic, returning to the Vault. ---- */
  var recapEl=document.getElementById('recap'), recapV=null, recapCache={};

  function recapSeg(s,i,total){
    var icons=['flag','travel_explore','lightbulb'];
    var ic=s.icon||icons[i]||'chevron_right';
    var pts=(s.bullets && s.bullets.length) ? s.bullets : (s.t.match(/[^.!?]+[.!?]+/g) || [s.t]);
    var lis=pts.map(function(b){
      return '<li style="display:flex;gap:11px;align-items:flex-start;font-family:var(--font-body);font-size:14.5px;line-height:1.55;color:var(--teal-050);">'+
        '<span aria-hidden="true" style="flex:none;margin-top:8px;width:6px;height:6px;border-radius:50%;background:var(--cyan-300);box-shadow:0 0 6px rgba(0,150,136,0.7);"></span>'+
        '<span>'+b.trim()+'</span></li>';
    }).join('');
    var div=(i<total-1)?'padding-bottom:16px;border-bottom:1px solid rgba(0,150,136,0.13);':'';
    return '<div style="margin-bottom:16px;'+div+'">'+
      '<div style="display:flex;align-items:center;gap:9px;margin-bottom:10px;white-space:nowrap;">'+
        '<span class="ms" aria-hidden="true" style="font-size:18px;color:var(--cyan-300);flex:none;filter:drop-shadow(0 0 7px rgba(0,150,136,0.5));">'+ic+'</span>'+
        '<span class="hud" style="font-size:10.5px;letter-spacing:.14em;color:var(--cyan-200);white-space:nowrap;">'+s.h+'</span>'+
      '</div>'+
      '<ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:9px;">'+lis+'</ul>'+
    '</div>';
  }
  function recapFallback(v){
    return v.desc || ("You completed "+v.title+" and earned the "+v.badge+" badge, Agent. Re-read the story any time to see how far you've come.");
  }
  function buildRecapPrompt(v){
    var T = CONTENT['transmission_m'+v.mission] || CONTENT.transmission;
    var A = CONTENT['assignment_m'+v.mission] || CONTENT.assignment;
    var story = T ? [T.lead].concat([].concat.apply([], T.stanzas||[])).concat(T.emphasis||[]).join(' ') : '';
    var goal = (A && A.objectiveLine) || '';
    return "You are B1llBot, the friendly in-game AI mentor in EVOKE's Prosperity program — a narrative learning game set in the drought-stricken world of Keel, where an agent named Alex fights to reclaim water and justice. A young student (addressed as 'Agent') has just finished a mission. Write a warm, encouraging recap of the WHOLE mission in 4 to 6 sentences. Use second person ('you'), a confident and friendly sci-fi command-deck tone, plain language a middle-schooler understands, and absolutely no emoji. Summarize what the mission was about, what the Agent explored, and what they learned.\n\nMission title: "+v.title+"\nLearning goal: "+goal+"\nBadge earned: "+v.badge+"\nStory context (Alex's field transmission): "+story+"\n\nReturn only the recap paragraph, with no preamble or heading.";
  }
  async function loadRecapSummary(v){
    var box=document.getElementById('recap-summary');
    if(v.segments && v.segments.length){ box.innerHTML=v.segments.map(function(s,i){return recapSeg(s,i);}).join(''); return; }
    var saved=recapCache[v.mission];
    if(!saved && v.summary){ saved=v.summary; }
    if(!saved){ try{ saved=localStorage.getItem('evoke-recap-'+v.mission)||null; }catch(e){} }
    if(saved){ recapCache[v.mission]=saved; box.textContent=saved; return; }
    box.innerHTML='<span class="recap-loading" aria-hidden="true"><i></i><i></i><i></i></span> <span style="color:var(--text-muted);font-family:var(--font-mono);font-size:12px;letter-spacing:.12em;">GENERATING SUMMARY…</span>';
    var text='';
    try{
      if(window.claude && typeof window.claude.complete==='function'){
        text=(await window.claude.complete(buildRecapPrompt(v))||'').trim();
      }
    }catch(e){ text=''; }
    if(!text) text=recapFallback(v);
    recapCache[v.mission]=text;
    try{ localStorage.setItem('evoke-recap-'+v.mission, text); }catch(e){}
    if(recapV && recapV.mission===v.mission && recapEl.classList.contains('open')) box.textContent=text;
  }
  function openRecap(v){
    recapV=v;
    document.getElementById('recap-tag').textContent=(v.n?v.n+' · ':'')+'Mission Recap';
    document.getElementById('recap-title').textContent=v.title;
    document.getElementById('recap-date').textContent=v.date;
    document.getElementById('recap-badge').textContent=v.badge;
    document.getElementById('recap-icon').textContent=v.icon||'auto_stories';
    recapEl.classList.add('open');
    document.getElementById('recap-close').focus();
    loadRecapSummary(v);
  }
  function closeRecap(){ recapEl.classList.remove('open'); recapV=null; }
  document.getElementById('recap-x').addEventListener('click',closeRecap);
  document.getElementById('recap-close').addEventListener('click',closeRecap);
  document.getElementById('recap-reread').addEventListener('click',function(){ if(!recapV) return; var m=recapV.mission; closeRecap(); novelForce=m; novelReturn='vault'; go('novel'); });
  recapEl.addEventListener('click',function(e){ if(e.target===recapEl) closeRecap(); });
  document.addEventListener('keydown',function(e){ if(e.key==='Escape' && recapEl.classList.contains('open')) closeRecap(); });

  /* ---- confetti (decorative) ---- */
  var cf = document.getElementById('confetti');
  var cols=["#2b9d90","#a5ede9","#ffa759","#00d492"];
  for(var i=0;i<28;i++){
    cf.appendChild(el('<span style="position:absolute;left:'+(Math.random()*100)+'%;top:'+(Math.random()*100)+'%;width:'+(6+Math.random()*10)+'px;height:3px;background:'+cols[i%4]+';opacity:0.6;transform:rotate('+(Math.random()*180)+'deg);border-radius:2px;box-shadow:0 0 8px '+cols[i%4]+';"></span>'));
  }

  /* ---- graphic novel (multi-page comic reader, mission-aware) ---- */
  var renderNovel; var novelForce=null; var novelReturn=null;
  (function(){
    var spreadIdx=0, pages=[], spreads=[], single=false, n=null, zoomIdx=0, sessionReturn=null;
    var book=document.getElementById('novel-book');
    var lBtn=document.getElementById('nv-left'), rBtn=document.getElementById('nv-right');
    var lImg=document.getElementById('nv-left-img'), rImg=document.getElementById('nv-right-img');
    var zimg=document.getElementById('novel-zoom-img');
    var zoom=document.getElementById('novel-zoom');
    var counter=document.getElementById('novel-counter');
    var dots=document.getElementById('novel-dots');
    var cont=document.getElementById('novel-continue');
    var backBtn=document.getElementById('novel-back');
    function buildSpreads(){
      spreads=[];
      if(pages.length<=1){ single=true; spreads=[[0,null]]; }
      else { single=false; for(var i=0;i<pages.length;i+=2){ spreads.push([i, i+1<pages.length?i+1:null]); } }
    }
    function showSpread(si){
      if(si<0)si=0; if(si>spreads.length-1)si=spreads.length-1; spreadIdx=si;
      book.classList.toggle('single', single);
      var sp=spreads[spreadIdx];
      var lp=pages[sp[0]];
      lImg.src=lp.img; lImg.alt=lp.alt||"";
      if(sp[1]!=null){ var rp=pages[sp[1]]; rImg.src=rp.img; rImg.alt=rp.alt||""; rBtn.classList.remove('empty'); rBtn.style.display=''; }
      else if(single){ rBtn.style.display='none'; }
      else { rImg.removeAttribute('src'); rImg.alt=''; rBtn.classList.add('empty'); rBtn.style.display=''; }
      var multi=spreads.length>1;
      counter.textContent = multi ? ('Spread '+(spreadIdx+1)+' of '+spreads.length) : '';
      dots.innerHTML='';
      if(multi){ for(var d=0;d<spreads.length;d++){ dots.appendChild(el('<span style="width:8px;height:8px;border-radius:50%;background:'+(d===spreadIdx?'var(--cyan-300)':'rgba(145,209,209,0.25)')+';box-shadow:'+(d===spreadIdx?'0 0 8px var(--cyan-300)':'none')+';"></span>')); } }
      var last = spreadIdx===spreads.length-1;
      cont.innerHTML = last ? ((sessionReturn?'Back to Vault':'Continue to Mission Control')+' \u25b6<span class="key" aria-hidden="true"></span>') : 'Next \u25b6';
      backBtn.textContent = spreadIdx===0 ? '\u25c0 Back' : '\u25c0 Prev';
      book.classList.remove('anim'); void book.offsetWidth; book.classList.add('anim');
    }
    function showEmptyNovel(){
      single=true; spreads=[[0,null]]; spreadIdx=0;
      book.style.display='none';
      var ph=document.getElementById('novel-empty');
      if(!ph){
        ph=el('<div id="novel-empty" class="glass" style="max-width:560px;margin:0 auto;padding:48px 36px;text-align:center;"><span class="ms" aria-hidden="true" style="font-size:44px;color:var(--cyan-300);filter:drop-shadow(0 0 12px rgba(0,150,136,0.5));">auto_stories</span><div class="hud" style="font-size:11px;letter-spacing:.16em;color:var(--cyan-300);margin:16px 0 8px;">Transmission Pending</div><p style="font-family:var(--font-body);font-size:15px;line-height:1.6;color:var(--teal-100);margin:0;">The graphic novel for this mission is still being drawn, Agent. Continue on to your briefing \u2014 the story panels will arrive soon.</p></div>');
        book.parentNode.insertBefore(ph, book.nextSibling);
      }
      ph.style.display='';
      counter.textContent=''; dots.innerHTML='';
      cont.innerHTML=(sessionReturn?'Back to Vault':'Continue to Mission Control')+' \u25b6<span class="key" aria-hidden="true"></span>';
      backBtn.textContent='\u25c0 Back';
    }
    renderNovel=function(){
      var target = novelForce || ((typeof curMission==='function') ? curMission() : 1);
      novelForce=null;
      n = (target===1) ? CONTENT.novel : (CONTENT['novel_m'+target] || null);
      sessionReturn = novelReturn; novelReturn=null;
      pages=(n&&n.pages)||[];
      document.getElementById('novel-chapter').textContent=(n&&n.chapter)||('Mission '+target+' \u00b7 Chapter coming soon');
      buildSpreads();
      var ph=document.getElementById('novel-empty');
      if(pages.length){ if(ph) ph.style.display='none'; book.style.display=''; showSpread(0); }
      else { showEmptyNovel(); }
    };
    cont.addEventListener('click',function(){ if(spreadIdx<spreads.length-1) showSpread(spreadIdx+1); else if(sessionReturn){ var t=sessionReturn; sessionReturn=null; go(t); } else go('missions'); });
    backBtn.addEventListener('click',function(){ if(spreadIdx>0) showSpread(spreadIdx-1); else go(currentWeek===0 ? 'welcome' : 'home'); });
    function openZoom(pIdx){
      zoomIdx = pIdx;
      var p=pages[zoomIdx];
      zimg.src=p.img; zimg.alt=p.alt||"";
      document.getElementById('nvz-counter').textContent = 'Page '+(zoomIdx+1)+' of '+pages.length;
      var pv=document.getElementById('nvz-prev'), nx=document.getElementById('nvz-next');
      pv.style.visibility = zoomIdx>0 ? 'visible':'hidden';
      nx.style.visibility = zoomIdx<pages.length-1 ? 'visible':'hidden';
      zoom.style.display='block'; document.getElementById('novel-zoom-close').focus();
    }
    function zoomStep(d){ var i=zoomIdx+d; if(i>=0 && i<pages.length) openZoom(i); }
    function closeZoom(){ zoom.style.display='none'; }
    lBtn.addEventListener('click',function(){ if(lImg.getAttribute('src')) openZoom(spreads[spreadIdx][0]); });
    rBtn.addEventListener('click',function(){ if(rImg.getAttribute('src') && !rBtn.classList.contains('empty')) openZoom(spreads[spreadIdx][1]); });
    document.getElementById('nvz-prev').addEventListener('click',function(){ zoomStep(-1); });
    document.getElementById('nvz-next').addEventListener('click',function(){ zoomStep(1); });
    document.getElementById('novel-zoom-close').addEventListener('click',closeZoom);
    zoom.addEventListener('click',function(e){ if(e.target===zoom) closeZoom(); });
    document.addEventListener('keydown',function(e){
      if(zoom.style.display==='block'){
        if(e.key==='Escape'){ closeZoom(); return; }
        if(e.key==='ArrowRight'){ zoomStep(1); return; }
        if(e.key==='ArrowLeft'){ zoomStep(-1); return; }
        return;
      }
      var act=document.querySelector('.screen.active');
      if(act && act.dataset.screen==='novel'){
        if(e.key==='ArrowRight' && spreadIdx<spreads.length-1) showSpread(spreadIdx+1);
        if(e.key==='ArrowLeft' && spreadIdx>0) showSpread(spreadIdx-1);
      }
    });
    renderNovel();
  })();

  /* ---- agent transmission (monologue, mission-aware) ---- */
  var renderTransmission;
  (function(){
    renderTransmission=function(){
      var t=MD('transmission');
      document.getElementById('tx-speaker').textContent=t.speaker;
      var html='<p style="font-family:var(--font-display);font-weight:700;font-size:clamp(20px,3vw,24px);color:var(--cyan-200);margin:0 0 22px;">'+t.lead+'</p>';
      t.stanzas.forEach(function(st){
        html+='<p style="font-family:var(--font-body);font-size:16px;line-height:1.7;color:var(--teal-050);margin:0 0 18px;white-space:pre-line;">'+st.join('\n')+'</p>';
      });
      html+='<p style="font-family:var(--font-display);font-weight:700;font-size:clamp(22px,3vw,28px);line-height:1.35;color:var(--cyan-500);text-shadow:0 0 20px rgba(0,150,136,0.4);margin:10px 0 0;white-space:pre-line;">'+t.emphasis.join('\n')+'</p>';
      document.getElementById('tx-body').innerHTML=html;
      var b=document.getElementById('tx-body'); if(b) b.scrollTop=0;
    };
    renderTransmission();
  })();
  document.getElementById('tx-next').addEventListener('click',function(){ if(window.markStarted) window.markStarted(curMission()); go('assignment'); });

  /* ---- mission assignment (dashboard, mission-aware) ---- */
  var renderAssignment;
  renderAssignment=function(){
    var a=MD('assignment');
    document.getElementById('as-brief').innerHTML='';
    document.getElementById('as-objectives').innerHTML='';
    document.getElementById('as-sub').textContent=a.sub;
    document.getElementById('as-title').textContent=a.title;
    document.getElementById('as-objline').textContent=a.objectiveLine;
    document.getElementById('as-xp').textContent='+'+a.xp+' XP';
    document.getElementById('as-badge').textContent=a.badge;
    var br=document.getElementById('as-brief');
    a.brief.forEach(function(p){
      br.appendChild(el('<p style="font-family:var(--font-body);font-size:clamp(15px,2vw,17px);line-height:1.6;color:var(--teal-100);margin:0;">'+p+'</p>'));
    });
    var ob=document.getElementById('as-objectives');
    a.objectives.forEach(function(o,oi){
      var last = oi===a.objectives.length-1;
      var bodyHtml = (o.body||[]).map(function(b){
        if(b.p) return '<p style="font-family:var(--font-body);font-size:14px;line-height:1.55;color:var(--teal-100);margin:0 0 10px;">'+b.p+'</p>';
        if(b.list) return '<ul style="margin:0 0 12px;padding-left:20px;display:flex;flex-direction:column;gap:6px;">'+b.list.map(function(li){return '<li style="font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--teal-100);">'+li+'</li>';}).join('')+'</ul>';
        return '';
      }).join('');
      ob.appendChild(el('<div style="display:flex;gap:18px;align-items:flex-start;padding:20px 4px;'+(last?'':'border-bottom:1px solid var(--border-faint);')+'">'+
        '<div style="width:44px;height:44px;flex:none;border-radius:10px;display:flex;align-items:center;justify-content:center;background:transparent;box-shadow:inset 0 0 0 1.5px var(--border-ui);color:var(--cyan-300);"><span class="ms" aria-hidden="true" style="font-size:24px;">'+o.icon+'</span></div>'+
        '<div style="flex:1;"><div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:4px;">Field Objective '+o.code+'</div>'+
        '<div style="font-family:var(--font-display);font-weight:700;font-size:18px;color:var(--text-heading);margin-bottom:10px;">'+o.t+'</div>'+
        bodyHtml+'</div></div>'));
    });
    var ev=document.getElementById('ev-cache');
    ev.innerHTML='<div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;"><span class="ms" aria-hidden="true" style="font-size:24px;color:var(--cyan-300);">cloud_upload</span><h2 class="hud" style="font-size:12px;margin:0;color:var(--cyan-300);">'+a.evidence.title+'</h2></div>'+
      '<p style="font-family:var(--font-body);font-size:15px;color:var(--teal-050);margin:0 0 18px;">'+a.evidence.intro+'</p>'+
      '<div class="ev-reqs">'+a.evidence.reqs.map(function(it){return '<div style="display:flex;gap:12px;align-items:flex-start;"><span class="ms" aria-hidden="true" style="font-size:20px;color:var(--cyan-300);flex:none;">task_alt</span><span style="font-family:var(--font-body);font-size:14px;line-height:1.55;color:var(--teal-100);">'+it+'</span></div>';}).join('')+'</div>'+
      '<div class="ev-divider"></div>'+
      '<label class="ev-label" for="ev-statement">'+(a.evidence.fieldLabel||'Your Challenge Statement')+'</label>'+
      '<textarea id="ev-statement" class="ev-textarea" placeholder="'+(a.evidence.fieldPlaceholder||'As a team, describe the community issue you\'ll address through your Evokation \u2014 and the financial realities shaping it.')+'"></textarea>'+
      '<span class="ev-label">Attach your fieldwork</span>'+
      '<div id="ev-drop" class="ev-drop" role="button" tabindex="0" aria-label="Upload files. Drag and drop here, or activate to browse your device.">'+
        '<span class="ms" aria-hidden="true">cloud_upload</span>'+
        '<div class="ev-drop-title">Drag &amp; drop files here</div>'+
        '<div class="ev-drop-sub">or <span class="ev-browse">browse from your device</span></div>'+
        '<div class="ev-drop-hint">Notes, interviews, photos, sketches, recordings, maps &middot; PDF, DOCX, JPG, PNG, MP3</div>'+
      '</div>'+
      '<input id="ev-file" type="file" multiple class="sr-only" aria-hidden="true" tabindex="-1">'+
      '<ul id="ev-files" class="ev-files" aria-label="Attached files"></ul>';

    /* evidence cache \u2014 file upload mockup */
    (function(){
      var drop=document.getElementById('ev-drop'),
          input=document.getElementById('ev-file'),
          list=document.getElementById('ev-files');
      function fmtSize(b){ if(b>=1048576) return (b/1048576).toFixed(1)+' MB'; if(b>=1024) return Math.round(b/1024)+' KB'; return b+' B'; }
      function iconFor(name){ var e=(name.split('.').pop()||'').toLowerCase();
        if(['jpg','jpeg','png','gif','webp','heic'].indexOf(e)>=0) return 'image';
        if(['mp3','wav','m4a','aac'].indexOf(e)>=0) return 'graphic_eq';
        if(['mp4','mov','webm'].indexOf(e)>=0) return 'movie';
        if(['pdf'].indexOf(e)>=0) return 'picture_as_pdf';
        return 'description'; }
      function addFile(name,size){
        var row=el('<li class="ev-filerow"><span class="fi"><span class="ms" aria-hidden="true">'+iconFor(name)+'</span></span>'+
          '<span class="fmeta"><span class="fname">'+name+'</span><span class="fsize">'+fmtSize(size)+' \u00b7 Uploaded</span></span>'+
          '<span class="fdone" title="Uploaded"><span class="ms" aria-hidden="true">check_circle</span></span>'+
          '<button type="button" class="ev-fileremove" aria-label="Remove '+name+'"><span class="ms" aria-hidden="true">close</span></button></li>');
        row.querySelector('.ev-fileremove').addEventListener('click',function(){ row.remove(); });
        list.appendChild(row);
      }
      function handle(files){ Array.prototype.forEach.call(files,function(f){ addFile(f.name, f.size||0); }); }
      drop.addEventListener('click',function(){ input.click(); });
      drop.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); input.click(); } });
      input.addEventListener('change',function(){ if(input.files&&input.files.length) handle(input.files); input.value=''; });
      ['dragenter','dragover'].forEach(function(ev){ drop.addEventListener(ev,function(e){ e.preventDefault(); drop.classList.add('drag'); }); });
      ['dragleave','drop'].forEach(function(ev){ drop.addEventListener(ev,function(e){ e.preventDefault(); drop.classList.remove('drag'); }); });
      drop.addEventListener('drop',function(e){ if(e.dataTransfer&&e.dataTransfer.files&&e.dataTransfer.files.length) handle(e.dataTransfer.files); });
    })();
  };
  renderAssignment();
  document.getElementById('as-ops').addEventListener('click',function(){ go('ops'); });
  document.getElementById('ev-submit').addEventListener('click',function(){ if(curMission()===2){ var os=document.getElementById('ev-statement'); if(os&&os.value.trim()){ try{localStorage.setItem('evoke-origin',os.value.trim());}catch(e){} } } if(window.evokeBackendSubmit) window.evokeBackendSubmit(curMission()); if(window.opsMarkSubmitted) window.opsMarkSubmitted(curMission()); go('reward'); });

  /* ---- operations hub ---- */
  (function(){
    var A1 = CONTENT.assignment, A2 = CONTENT.assignment_m2;
    var current = 1;
    function opsFor(a, chapterNum, nextChapter, badgeD, alex){
      return {
        title:a.title, desc:a.objectiveLine, chapterNum:chapterNum, chapterSub:a.title,
        next:nextChapter, nextSub:"Submit your findings to unlock the next chapter.",
        checklist:a.objectives.map(function(o){ return [o.icon, o.t]; }).concat([["cloud_upload","Submit your findings"]]),
        chapterTotal:12, badgeT:a.badge, badgeD:badgeD, alex:alex
      };
    }
    function opsTitleOf(n){ try{ var wi=Math.floor((n-1)/2), mi=(n-1)%2; return CONTENT.weeks[wi].missions[mi].title; }catch(e){ return 'Coming soon'; } }
    var OPS = {};
    (function(){
      for(var n=1;n<=12;n++){
        var a = (n===1) ? CONTENT.assignment : CONTENT['assignment_m'+n];
        if(!a) continue;
        var nextLabel = n<12 ? ('Mission '+(n+1)+': '+opsTitleOf(n+1)) : 'The campaign is complete — outstanding work, Agent.';
        var ALEX_QUOTES = {
          1:"You listened before you judged, Agent. That's where real change starts.",
          2:"You found your 'why.' Hold onto it — it'll carry the whole team.",
          3:"The wild ideas scared you and you chased them anyway. That's the work.",
          4:"You saw a future worth building. Now other people can see it too.",
          5:"Turning a dream into real numbers is brave. You did the honest math.",
          6:"You found the resources others missed. Resourceful, Agent — I'm impressed.",
          7:"You stopped imagining and started building. That takes real nerve.",
          8:"You made the hard calls about what stays and what waits. That's leadership.",
          9:"You put unfinished work in front of real people and listened. Courage.",
          10:"You aligned the team around one shared bet. Not easy — well done.",
          11:"You made people believe. That's how good ideas find their backers.",
          12:"You stood up, told the truth, and owned it together. Proud of you, Agent."
        };
        var alexLine = ALEX_QUOTES[n] || "Keep going, Agent. You're closer than you think.";
        OPS[n] = opsFor(a, n, nextLabel, 'Grew your '+a.badge+' superpower.', alexLine);
      }
    })();
    var MC_CONTENT = {
      week1: {
        chip:"Week 1 \u00b7 Simulation",
        banner:'This is a <strong style="color:var(--cyan-100);">simulation</strong> of Keel as it once was \u2014 a thriving world before the collapse. Explore it freely. Your real mission still happens in the real world.',
        heroTitle:"Explore Keel",
        goal:'I can explore the <strong style="color:var(--cyan-100);font-weight:700;">simulation of Keel before the collapse</strong> and imagine the prosperous world I\'ll work to rebuild.',
        steps:[
          {t:"Leave EVOKE &amp; open Minecraft", d:"Step away from this site and launch Minecraft to load the simulation of Keel \u2014 the world as it was before the collapse."},
          {t:"Explore the world freely", d:"Roam the whole map: wander the streets, discover hidden places, and try the parkour. There's no wrong way to explore."},
          {t:"See what prosperity looks like", d:"Take in the thriving world \u2014 the water, the people, the life. This is the future you'll work to bring back."},
          {t:"Return &amp; reflect", d:"Come back to EVOKE and record what you saw and what excited you most about this world."}
        ],
        reflectQ:"What did Keel look like before the collapse \u2014 and what excited you most about exploring it?",
        placeholder:"In the simulation, I explored\u2026",
        obj:[
          "Open Minecraft and load the simulation of Keel.",
          "Explore the world freely, as it was before the fall.",
          "Discover hidden places \u2014 try the parkour.",
          "Capture what excites you in your Notebook."
        ],
        modalIntro:'This step is <strong style="color:var(--cyan-100);">optional</strong> \u2014 your mission is completed with real-world fieldwork. If you\'d like to explore the simulation of Keel before the collapse, follow the steps below.',
        modalSteps:[
          'Open Minecraft on your computer, click <strong style="color:var(--cyan-100);">Multiplayer \u203a Add Server</strong>, paste the address you copied above, and click <strong style="color:var(--cyan-100);">Join Server</strong>.',
          "Resize your Minecraft window to fill one side of your screen.",
          'Tap <strong style="color:var(--cyan-100);">Enter Companion Mode</strong> below and snap EVOKE to the other side \u2014 B1llBot and your Explorer\'s Notebook stay with you while you play.',
          'In Keel, use <strong style="color:var(--cyan-100);">W A S D</strong> and your <strong style="color:var(--cyan-100);">mouse</strong> to explore freely. This is the world before the collapse \u2014 roam it, find the parkour, and see what prosperity looks like.'
        ]
      },
      later: {
        chip:"Simulation \u00b7 Rebuild Prosperity",
        banner:'The simulation is over \u2014 this is Keel <strong style="color:var(--cyan-100);">now</strong>, after the collapse. Follow the mini-games to rebuild prosperity and turn that vision into reality. Your real mission still happens in the real world.',
        heroTitle:"Rebuild Keel",
        goal:'I can follow the mini-games to <strong style="color:var(--cyan-100);font-weight:700;">build prosperity from the ground up</strong> \u2014 turning the dystopian Keel back into the thriving world from the simulation.',
        steps:[
          {t:"Leave EVOKE &amp; open Minecraft", d:"Step away from this site and launch Minecraft to enter Keel as it is now \u2014 after the collapse."},
          {t:"Start at the bottom", d:"You begin with almost nothing in the dystopian world. This is where the real work starts."},
          {t:"Follow the mini-games", d:"Work through the in-game challenges to earn, save, and rebuild prosperity step by step."},
          {t:"Return &amp; reflect", d:"Come back to EVOKE and record the progress you made this week."}
        ],
        reflectQ:"How did you start to rebuild prosperity in Keel this week?",
        placeholder:"This week in Keel, I\u2026",
        obj:[
          "Open Minecraft and enter Keel after the collapse.",
          "Follow the mini-games to start rebuilding.",
          "Earn, save, and build prosperity step by step.",
          "Capture your progress in your Notebook."
        ],
        modalIntro:'This step is <strong style="color:var(--cyan-100);">optional</strong> \u2014 your mission is completed with real-world fieldwork. If you\'d like to keep rebuilding Keel in the simulation, follow the steps below.',
        modalSteps:[
          'Open Minecraft on your computer, click <strong style="color:var(--cyan-100);">Multiplayer \u203a Add Server</strong>, paste the address you copied above, and click <strong style="color:var(--cyan-100);">Join Server</strong>.',
          "Resize your Minecraft window to fill one side of your screen.",
          'Tap <strong style="color:var(--cyan-100);">Enter Companion Mode</strong> below and snap EVOKE to the other side \u2014 B1llBot and your Explorer\'s Notebook stay with you while you play.',
          'In Keel, use <strong style="color:var(--cyan-100);">W A S D</strong> and your <strong style="color:var(--cyan-100);">mouse</strong>. Follow the mini-game markers to rebuild prosperity \u2014 earn, save, and build the world back toward the simulation you explored in Week 1.'
        ]
      }
    };
    function renderMinecraftWeek(){
      var c = (typeof curMission==='function' && curMission()>2) ? MC_CONTENT.later : MC_CONTENT.week1;
      function setHTML(id,h){ var n=document.getElementById(id); if(n) n.innerHTML=h; }
      function setText(id,t){ var n=document.getElementById(id); if(n) n.textContent=t; }
      setText('mc-chip-text', c.chip);
      setHTML('mc-banner-text', c.banner);
      setText('mc-hero-title', c.heroTitle);
      setHTML('mc-goal', c.goal);
      setHTML('mc-reflect-q', '<strong style="color:var(--cyan-100);font-weight:700;">'+c.reflectQ+'</strong>');
      var rt=document.getElementById('mc-reflect'); if(rt) rt.setAttribute('placeholder', c.placeholder);
      setHTML('mc-modal-intro', c.modalIntro);
      var qs=document.getElementById('mc-quest-steps');
      if(qs){ qs.innerHTML=''; c.steps.forEach(function(s,i){ qs.appendChild(el('<div class="mc-step"><span class="num" aria-hidden="true">'+(i+1)+'</span><div><div class="t">'+s.t+'</div><div class="d">'+s.d+'</div></div></div>')); }); }
      var ob=document.getElementById('comp-obj');
      if(ob){ var icons=['looks_one','looks_two','looks_3','looks_4']; ob.innerHTML=''; c.obj.forEach(function(t,i){ ob.appendChild(el('<li><span class="ms" aria-hidden="true">'+icons[i]+'</span>'+t+'</li>')); }); }
      var mt2=document.getElementById('comp-mt');
      if(mt2 && typeof curMission==='function'){ try{ var gm=curMission(), wi=Math.floor((gm-1)/2), mi=(gm-1)%2; mt2.textContent=CONTENT.weeks[wi].missions[mi].title; }catch(e){} }
      var ms=document.getElementById('mc-modal-steps');
      if(ms){ ms.innerHTML=''; c.modalSteps.forEach(function(t,i){ ms.appendChild(el('<div class="ops-step"><span class="n" aria-hidden="true">'+(i+1)+'</span><span style="flex:1;font-family:var(--font-body);font-size:14px;line-height:1.55;color:var(--teal-050);padding-top:2px;">'+t+'</span></div>')); }); }
    }
    window.renderMinecraftWeek = renderMinecraftWeek;
    function renderOps(id){
      var m=OPS[id]; if(!m) return; current=id;
      var X=evokeXP();
      var state=missionState(id); // notstarted | inprogress | complete
      document.getElementById('ops-title').textContent=m.title;
      document.getElementById('ops-desc').textContent=m.desc;
      var stCfg = state==='complete' ? ['Status: Complete','var(--green-400)']
                : state==='inprogress' ? ['Status: In Progress','var(--cyan-300)']
                : ['Status: Not Started','var(--text-faint)'];
      var sd=document.getElementById('ops-status-dot'), sl=document.getElementById('ops-status');
      sl.textContent=stCfg[0]; sl.style.color=stCfg[1];
      sd.style.background=stCfg[1]; sd.style.boxShadow= state==='notstarted' ? 'none' : '0 0 8px '+stCfg[1];
      var thisDone = state==='complete';
      var wkChapter = Math.ceil(m.chapterNum/2);   // chapters are per-week (1..6), 2 missions each
      document.getElementById('ops-chapter').textContent= thisDone ? ('Chapter '+wkChapter+' \u00b7 Complete') : ('Chapter '+wkChapter+': In Progress');
      var cn=document.getElementById('ops-chapter-num'); if(cn) cn.textContent=('0'+wkChapter).slice(-2);
      document.getElementById('ops-chapter-sub').textContent=m.chapterSub;
      document.getElementById('ops-next').textContent=m.next;
      document.getElementById('ops-next-sub').textContent=m.nextSub;
      // rewards reflect TOTAL progress — in sync with home/progress/profile
      document.getElementById('ops-xp').textContent = X.xp;
      document.getElementById('ops-badges').textContent = X.missions;
      // Superpowers tracker — 4 superpowers that level up across the journey
      (function(){
        var sp=document.getElementById('ops-superpowers'); if(!sp) return;
        sp.innerHTML = powerGroups().map(function(g){
          var e=g.powers.filter(function(p){return p.earned;}).length, on=e>0;
          var mini=g.powers.map(function(p){
            var pon=p.earned;
            return '<span title="'+p.name+'" style="width:26px;height:26px;flex:none;border-radius:8px;display:flex;align-items:center;justify-content:center;'+(pon?'color:var(--green-400);box-shadow:inset 0 0 0 1px rgba(0,212,146,0.5);background:rgba(0,212,146,0.08);':'color:var(--text-faint);box-shadow:inset 0 0 0 1px var(--border-ui);')+'"><span class="ms'+(pon?' fill':'')+'" aria-hidden="true" style="font-size:15px;">'+(pon?p.icon:'lock')+'</span></span>';
          }).join('');
          return '<div style="display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:11px;box-shadow:inset 0 0 0 1px var(--border-ui);opacity:'+(on?'1':'0.6')+';">'
            +'<span class="ms" aria-hidden="true" style="font-size:20px;flex:none;color:'+(on?'var(--cyan-300)':'var(--text-faint)')+';">'+g.icon+'</span>'
            +'<div style="flex:1;min-width:0;"><div style="font-family:var(--font-display);font-weight:700;font-size:12.5px;color:var(--teal-050);line-height:1.15;margin-bottom:6px;">'+g.quality+'</div><div style="display:flex;gap:5px;flex-wrap:wrap;">'+mini+'</div></div>'
            +'<span class="hud" style="font-size:10px;flex:none;color:'+(on?'var(--cyan-300)':'var(--text-faint)')+';">'+e+'/'+g.powers.length+'</span></div>';
        }).join('');
      })();
      document.getElementById('ops-alex').textContent='\u201c'+m.alex+'\u201d';
      var cl=document.getElementById('ops-checklist'); cl.innerHTML='';
      m.checklist.forEach(function(c){ cl.appendChild(el('<div class="ops-chk"><span class="ic-tile" aria-hidden="true"><span class="ms">'+c[0]+'</span></span><span style="flex:1;font-family:var(--font-body);font-size:15px;color:var(--teal-050);line-height:1.35;">'+c[1]+'</span></div>')); });
      var doneChapters = X.missions; // completed chapters across the journey
      var ch=document.getElementById('ops-chapters');
      if(ch){
        ch.innerHTML='';
        var doneWeeks=Math.floor(X.missions/2);              // fully-completed weeks
        var curWeek=Math.ceil((typeof curMission==='function'?curMission():1)/2); // 1..6
        for(var i=1;i<=6;i++){
          var isCur=(i===curWeek && doneWeeks<6), cls=i<=doneWeeks?'done':(isCur?'cur':'');
          var node=el('<span class="chap-node '+cls+'" role="img" aria-label="Week '+i+(i<=doneWeeks?', complete':(isCur?', current chapter':', locked'))+'">'+(i<=doneWeeks?'\u2713':i)+'</span>');
          ch.appendChild(node); if(i<6) ch.appendChild(el('<span class="chap-line"></span>'));
        }
      }
    }
    renderOps(curMission()); window.renderOps=renderOps;
    window.opsMarkSubmitted=function(id){ try{localStorage.setItem('evoke-m'+id+'-submitted','1');}catch(e){} renderOps(current); if(window.syncAllXP) window.syncAllXP(); };
    document.getElementById('ops-brief').addEventListener('click',function(){ go('assignment'); });
    document.getElementById('ops-submit').addEventListener('click',function(){ go('submission'); });
    // Operations Hub onboarding guide — auto-opens once, reopenable via the ? button
    (function(){
      var guide=document.getElementById('ops-guide');
      function openGuide(){ if(guide){ guide.classList.add('open'); var ok=document.getElementById('ops-guide-ok'); if(ok) ok.focus(); } }
      function closeGuide(){ if(guide){ guide.classList.remove('open'); try{ localStorage.setItem('evoke-ops-guide-seen','1'); }catch(e){} } }
      window.openOpsGuide=openGuide;
      var helpBtn=document.getElementById('ops-help'); if(helpBtn) helpBtn.addEventListener('click',openGuide);
      var x=document.getElementById('ops-guide-x'); if(x) x.addEventListener('click',closeGuide);
      var ok=document.getElementById('ops-guide-ok'); if(ok) ok.addEventListener('click',closeGuide);
      if(guide){ guide.addEventListener('click',function(e){ if(e.target===guide) closeGuide(); }); }
      document.addEventListener('keydown',function(e){ if(e.key==='Escape' && guide && guide.classList.contains('open')) closeGuide(); });
    })();
    var modal=document.getElementById('mc-modal'), steps=document.getElementById('mc-modal-steps');
    renderMinecraftWeek();
    function openM(){ modal.classList.add('open'); document.getElementById('mc-modal-ok').focus(); }
    function closeM(){ modal.classList.remove('open'); go('ops'); }
    document.getElementById('ops-mc').addEventListener('click',openM);
    document.getElementById('mc-modal-ok').addEventListener('click',closeM);
    var mcc=document.getElementById('mc-modal-companion'); if(mcc) mcc.addEventListener('click',function(){ closeM(); if(window.openCompanionWindow) window.openCompanionWindow(); });
    document.getElementById('mc-modal-x').addEventListener('click',closeM);
    (function(){
      var copyBtn=document.getElementById('mc-copy');
      if(copyBtn) copyBtn.addEventListener('click',function(){
        var addr=document.getElementById('mc-server').textContent.trim();
        var done=function(){ var o=copyBtn.innerHTML; copyBtn.innerHTML='<span class="ms" aria-hidden="true" style="font-size:15px;vertical-align:middle;">check</span> Copied'; setTimeout(function(){ copyBtn.innerHTML=o; },1600); };
        if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(addr).then(done,done); }
        else { try{ var t=document.createElement('textarea'); t.value=addr; document.body.appendChild(t); t.select(); document.execCommand('copy'); document.body.removeChild(t); }catch(e){} done(); }
      });
    })();
    modal.addEventListener('click',function(e){ if(e.target===modal) closeM(); });
    document.addEventListener('keydown',function(e){ if(e.key==='Escape' && modal.classList.contains('open')) closeM(); });
  })();

  /* ---- optional minecraft ---- */
  /* ---- minecraft quest (reflection gate) ---- */
  (function(){
    var ref=document.getElementById('mc-reflect');
    var btn=document.getElementById('mc-done');
    var hint=document.getElementById('mc-reflect-hint');
    function check(){
      var ok = ref.value.trim().length>=40;
      btn.disabled=!ok; btn.setAttribute('aria-disabled', ok?'false':'true');
      if(hint){
        hint.innerHTML = ok
          ? '<span class="ms" aria-hidden="true" style="font-size:16px;color:var(--green-400);">check_circle</span>Reflection logged \u2014 you can complete your mission.'
          : '<span class="ms" aria-hidden="true" style="font-size:16px;">lock</span>Write a sentence or two to unlock the next step.';
        hint.style.color = ok ? 'var(--green-400)' : 'var(--text-faint)';
      }
    }
    ref.addEventListener('input', check);
    check();
    btn.addEventListener('click', function(){ if(!btn.disabled) go('reward'); });
  })();

  /* ---- progress dashboard ---- */
  function renderProgress(){
    var X=evokeXP(), pct=Math.round(X.xp/X.max*100);
    document.getElementById('pg-level').textContent='Level '+X.level+' · Recruit';
    var track=document.getElementById('pg-track');
    track.querySelector('.fill-xp').style.width=pct+'%'; track.querySelector('.knob').style.left=pct+'%';
    track.setAttribute('aria-valuenow',X.xp); track.setAttribute('aria-valuemin','0'); track.setAttribute('aria-valuemax',X.max);
    document.getElementById('pg-xp').textContent=X.xp+' XP';
    document.getElementById('pg-xpmax').textContent=X.max+' XP · Lv.'+(X.level+1);
    var ringFg=document.getElementById('pg-ring-fg'); if(ringFg){ var C=2*Math.PI*52; ringFg.style.strokeDasharray=C; ringFg.style.strokeDashoffset=C*(1-pct/100); }
    var rp=document.getElementById('pg-ring-pct'); if(rp) rp.textContent=pct+'%';
    var rl=document.querySelector('#pg-ring-pct ~ .pg-ring-lbl, .pg-ring-lbl'); if(rl) rl.textContent = X.maxed ? 'Max' : ('to Lv.'+(X.level+1));
    var rdot=document.getElementById('pg-ring-dot'); if(rdot){ if(pct>0){ rdot.style.display='block'; var W=rdot.parentNode.clientWidth||188; var C=W/2, R=W*52/120, th=2*Math.PI*(pct/100); rdot.style.left=(C+R*Math.sin(th)).toFixed(1)+'px'; rdot.style.top=(C-R*Math.cos(th)).toFixed(1)+'px'; } else { rdot.style.display='none'; } }
    // badges earned across the whole journey
    var earned=0;
    CONTENT.weeks.forEach(function(wk,wi){ wk.missions.forEach(function(m,mi){ if(missionState(wi*2+mi+1)==='complete') earned++; }); });
    // stats
    var statVals={ 'pg-missions':String(X.missions), 'pg-badges-stat':String(earned) };
    var st=document.getElementById('pg-stats'); st.innerHTML='';
    CONTENT.progress.stats.forEach(function(s){
      var val = statVals[s.id] != null ? statVals[s.id] : s.value;
      st.appendChild(el('<div class="pg-stat"><div class="pg-stat-ic"><span class="ms fill" aria-hidden="true">'+s.icon+'</span></div><div class="pg-stat-txt"><div class="pg-stat-num"'+(s.id?' id="'+s.id+'"':'')+'>'+val+'</div><div class="pg-stat-lbl">'+s.label+'</div></div></div>'));
    });
    // The 16 Powers grouped under their 4 Superpowers (the app's badge collection).
    var ba=document.getElementById('pg-badges-all');
    ba.style.display='grid'; ba.style.gridTemplateColumns='repeat(4,minmax(0,1fr))'; ba.style.gap='14px';
    ba.innerHTML = powerGroups().map(function(g){
      var e=g.powers.filter(function(p){return p.earned;}).length;
      var tiles=g.powers.map(function(p){ return powerTile(p,52); }).join('');
      return '<div class="glass" style="padding:18px 16px;">'
        +'<div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;"><span class="mtile" style="width:38px;height:38px;flex:none;border-radius:11px;display:flex;align-items:center;justify-content:center;"><span class="ms fill" aria-hidden="true" style="font-size:20px;">'+g.icon+'</span></span>'
        +'<div style="min-width:0;"><div style="font-family:var(--font-display);font-weight:800;font-size:13.5px;color:var(--text-heading);text-transform:uppercase;line-height:1.1;">'+g.quality+'</div><div class="hud" style="font-size:10px;color:var(--cyan-300);margin-top:2px;">'+e+' of '+g.powers.length+' powers</div></div></div>'
        +'<div style="display:grid;grid-template-columns:repeat('+g.powers.length+',1fr);gap:8px;">'+tiles+'</div></div>';
    }).join('');
    document.getElementById('pg-badge-count').textContent=totalPowersEarned()+' of '+TOTAL_POWERS+' powers';
    if(window.renderStreaks) window.renderStreaks();
  }
  window.renderProgress=renderProgress; renderProgress();

  /* ---- agent profile ---- */
  (function(){
    var p=CONTENT.profile;
    var PF_AVATARS=['person','smart_toy','rocket_launch','bolt','shield','military_tech','psychology','water_drop'];
    var PF_RANKS=['Recruit','Field Agent','Changemaker','Senior Changemaker'];
    function pfGet(k,d){ try{ var v=localStorage.getItem(k); return v==null?d:v; }catch(e){ return d; } }
    function pfSet(k,v){ try{ localStorage.setItem(k,v); }catch(e){} }
    function renderProfile2(){
      var X=evokeXP();
      document.getElementById('pf-name').textContent=pfGet('evoke-agent-name', p.codename);
      var avPhoto=pfGet('evoke-avatar-photo',''), avIc=document.getElementById('pf-avatar-ic'), avImg=document.getElementById('pf-avatar-img');
      if(avPhoto){ avImg.src=avPhoto; avImg.style.display='block'; avIc.style.display='none'; }
      else{ avImg.style.display='none'; avImg.removeAttribute('src'); avIc.style.display=''; avIc.textContent=pfGet('evoke-avatar','person'); }
      document.getElementById('pf-rank').textContent=PF_RANKS[Math.min(X.missions,PF_RANKS.length-1)]+' · Keel Network';
      var pct=Math.round(X.xp/X.max*100);
      var ring=document.getElementById('pf-ring'); if(ring) ring.style.setProperty('--pct',pct);
      document.getElementById('pf-ring-lvl').textContent=X.level;
      document.getElementById('pf-xpline').textContent=X.xp+' / '+X.max+' XP to Level '+(X.level+1);
      document.getElementById('pf-joined').textContent=p.joined;
      var st=document.getElementById('pf-stats'); st.innerHTML='';
      [['rocket_launch',String(X.missions),'Missions','var(--green-400)'],['calendar_today',String(Math.min(Math.floor(X.missions/2)+1,6)),'Current Week','var(--cyan-300)'],['bolt',String(X.xp),'Total XP','var(--orange-500)']].forEach(function(s){
        st.appendChild(el('<div class="pf-stat" style="--accent:'+s[3]+';"><span class="ms" aria-hidden="true">'+s[0]+'</span><div class="n">'+s[1]+'</div><div class="l">'+s[2]+'</div></div>'));
      });
    }
    window.renderProfile2=renderProfile2; renderProfile2();
    document.getElementById('pf-name-edit').addEventListener('click',function(){
      var v=prompt('Enter your agent name:',document.getElementById('pf-name').textContent);
      if(v&&v.trim()){ pfSet('evoke-agent-name',v.trim().slice(0,24)); renderProfile2(); }
    });
    var pfPicker=document.getElementById('pf-avatar-picker');
    var pfFile=document.getElementById('pf-avatar-file');
    function buildPicker(){
      pfPicker.innerHTML='';
      var hasPhoto=!!pfGet('evoke-avatar-photo','');
      // Upload-a-photo action
      var up=el('<button type="button" role="menuitem" class="pf-pick-photo" aria-label="Upload a photo"><span class="ms" aria-hidden="true">add_a_photo</span></button>');
      up.addEventListener('click',function(e){ e.stopPropagation(); pfFile.click(); });
      pfPicker.appendChild(up);
      // Remove-photo action (only when a photo is set) — returns to icon avatars
      if(hasPhoto){
        var rm=el('<button type="button" role="menuitem" class="pf-pick-rm" aria-label="Remove photo, use an icon"><span class="ms" aria-hidden="true">do_not_disturb_on</span></button>');
        rm.addEventListener('click',function(e){ e.stopPropagation(); try{ localStorage.removeItem('evoke-avatar-photo'); }catch(_){ } pfPicker.hidden=true; renderProfile2(); });
        pfPicker.appendChild(rm);
      }
      // Built-in icon avatars
      PF_AVATARS.forEach(function(ic){
        var sel=(!hasPhoto && pfGet('evoke-avatar','person')===ic)?' class="sel"':'';
        var b=el('<button type="button" role="menuitem"'+sel+' aria-label="Avatar '+ic+'"><span class="ms" aria-hidden="true">'+ic+'</span></button>');
        b.addEventListener('click',function(e){ e.stopPropagation(); try{ localStorage.removeItem('evoke-avatar-photo'); }catch(_){ } pfSet('evoke-avatar',ic); pfPicker.hidden=true; renderProfile2(); });
        pfPicker.appendChild(b);
      });
    }
    // Read a chosen photo, downscale to a 256px square (so it fits localStorage), store + show it.
    pfFile.addEventListener('change',function(){
      var f=pfFile.files&&pfFile.files[0]; if(!f) return;
      var rd=new FileReader();
      rd.onload=function(){
        var img=new Image();
        img.onload=function(){
          var S=256, c=document.createElement('canvas'); c.width=S; c.height=S;
          var ctx=c.getContext('2d');
          var sc=Math.max(S/img.width,S/img.height), dw=img.width*sc, dh=img.height*sc;
          ctx.drawImage(img,(S-dw)/2,(S-dh)/2,dw,dh);
          var data; try{ data=c.toDataURL('image/jpeg',0.82); }catch(_){ data=rd.result; }
          pfSet('evoke-avatar-photo',data); pfPicker.hidden=true; renderProfile2();
        };
        img.onerror=function(){ pfSet('evoke-avatar-photo',rd.result); pfPicker.hidden=true; renderProfile2(); };
        img.src=rd.result;
      };
      rd.readAsDataURL(f);
      pfFile.value='';
    });
    document.getElementById('pf-avatar-btn').addEventListener('click',function(e){ e.stopPropagation(); pfPicker.hidden=!pfPicker.hidden;
      if(!pfPicker.hidden) buildPicker();
    });
    document.addEventListener('click',function(){ pfPicker.hidden=true; });
    // ── Functional settings: persisted toggles that actually do something ──
    function setBool(k,v){ try{ localStorage.setItem(k, v?'1':'0'); }catch(e){} }
    function getBool(k,d){ try{ var v=localStorage.getItem(k); return v==null?d:(v==='1'); }catch(e){ return d; } }
    var SETTINGS=[
      { key:'evoke-set-hc', icon:'contrast', label:'High Contrast',
        on:'Boosted contrast for readability', off:'Standard contrast', def:false,
        apply:function(v){ document.body.classList.toggle('hc',v); } },
      { key:'evoke-set-motion', icon:'animation', label:'Reduce Motion',
        on:'Animations minimized', off:'Animations on', def:false,
        apply:function(v){ document.body.classList.toggle('reduce-motion',v); } },
      { key:'evoke-set-notif', icon:'notifications', label:'Mission Reminders',
        on:'Browser reminders enabled', off:'Reminders off', def:false,
        apply:function(v,interactive){
          if(v && interactive && 'Notification' in window){
            var fire=function(){ try{ new Notification('EVOKE Mission Control',{body:"Mission reminders enabled, Agent. We'll help you keep your streak alive."}); }catch(e){} };
            if(Notification.permission==='granted') fire();
            else if(Notification.permission!=='denied') Notification.requestPermission().then(function(p){ if(p==='granted') fire(); });
          }
        } }
    ];
    // Apply saved settings immediately on load (global effects, not just on this screen)
    SETTINGS.forEach(function(s){ s.apply(getBool(s.key,s.def),false); });

    var ps=document.getElementById('pf-settings');
    function renderSettings(){
      ps.innerHTML='';
      SETTINGS.forEach(function(s){
        var on=getBool(s.key,s.def);
        var row=el('<div class="pf-set-row">'+
          '<span class="ms" aria-hidden="true" style="font-size:22px;color:var(--cyan-300);">'+s.icon+'</span>'+
          '<div style="flex:1;"><div style="font-family:var(--font-display);font-weight:700;font-size:15px;color:var(--text-heading);">'+s.label+'</div>'+
          '<div class="pf-set-val" style="font-family:var(--font-body);font-size:13px;color:var(--text-faint);">'+(on?s.on:s.off)+'</div></div>'+
          '<button class="pf-toggle" type="button" role="switch" aria-checked="'+(on?'true':'false')+'" aria-label="'+s.label+'"></button></div>');
        row.querySelector('.pf-toggle').addEventListener('click',function(){
          var nv=!getBool(s.key,s.def); setBool(s.key,nv); s.apply(nv,true);
          renderSettings();
        });
        ps.appendChild(row);
      });
    }
    renderSettings();
  })();

  /* ---- B1llBot chat (holo-comms) ---- */
  var bb = CONTENT.billbot;
  var log = document.getElementById('chat-log');
  var log = document.getElementById('chat-log');
  function setHolo(){}
  function typeOn(b, text){
    var i=0; b.innerHTML='<span class="cur"></span>';
    var cur=b.querySelector('.cur');
    (function tick(){
      if(i<text.length){ cur.insertAdjacentText('beforebegin', text.charAt(i)); i++; log.scrollTop=log.scrollHeight; setTimeout(tick, 16); }
      else { if(cur) cur.remove(); }
    })();
  }
  function addBubble(text, who, typed){
    var b = el('<div class="bubble '+who+'"></div>');
    log.appendChild(b);
    if(typed){ typeOn(b, text); } else { b.textContent = text; }
    log.scrollTop = log.scrollHeight; return b;
  }
  var bbHistory = [];
  function keywordReply(q){
    var low = q.toLowerCase(), hit = null;
    bb.replies.forEach(function(r){ if(!hit && r.match.some(function(m){return low.indexOf(m)>-1;})) hit = r.text; });
    return hit || bb.fallback;
  }
  function botReply(q){
    var typing = el('<div class="bubble bot typing"><span></span><span></span><span></span></div>');
    log.appendChild(typing); log.scrollTop = log.scrollHeight;
    if(!LLM.endpoint || !LLM.apiKey){
      setTimeout(function(){ if(typing.parentNode) log.removeChild(typing); addBubble(keywordReply(q),'bot',true); }, 900);
      return;
    }
    llmComplete(q, bbHistory).then(function(reply){
      if(typing.parentNode) log.removeChild(typing);
      if(reply == null) reply = keywordReply(q);
      bbHistory.push({role:"user",content:q},{role:"assistant",content:reply});
      if(bbHistory.length > 20) bbHistory = bbHistory.slice(-20);
      addBubble(reply,'bot',true);
    }).catch(function(){
      if(typing.parentNode) log.removeChild(typing);
      addBubble(keywordReply(q),'bot',true);
    });
  }
  function sendMsg(q){ if(!q.trim())return; addBubble(q,'me'); botReply(q); }
  addBubble(bb.greeting,'bot');
  var sg = document.getElementById('chat-suggest');
  bb.suggestions.forEach(function(s){
    var b = el('<button type="button">'+s+'</button>');
    b.addEventListener('click', function(){ sendMsg(s); });
    sg.appendChild(b);
  });
  document.getElementById('chat-form').addEventListener('submit', function(e){
    e.preventDefault();
    var f = document.getElementById('chat-field');
    sendMsg(f.value); f.value='';
  });

  /* ---- companion mode ---- */
  (function(){
    var clog=document.getElementById('comp-log');
    if(!clog) return;
    function cType(b,text){ var i=0; b.innerHTML='<span class="cur"></span>'; var cur=b.querySelector('.cur');
      (function tick(){ if(i<text.length){ cur.insertAdjacentText('beforebegin',text.charAt(i)); i++; clog.scrollTop=clog.scrollHeight; setTimeout(tick,16); } else { if(cur) cur.remove(); } })(); }
    function cAdd(text,who,typed){ var b=el('<div class="bubble '+who+'"></div>'); clog.appendChild(b); if(typed){ cType(b,text); } else { b.textContent=text; } clog.scrollTop=clog.scrollHeight; return b; }
    var compHistory=[];
    function cKeyword(q){ var low=q.toLowerCase(),hit=null; bb.replies.forEach(function(r){ if(!hit && r.match.some(function(m){return low.indexOf(m)>-1;})) hit=r.text; }); return hit||bb.fallback; }
    function cReply(q){
      var t=el('<div class="bubble bot typing"><span></span><span></span><span></span></div>'); clog.appendChild(t); clog.scrollTop=clog.scrollHeight;
      if(!LLM.endpoint || !LLM.apiKey){ setTimeout(function(){ if(t.parentNode) clog.removeChild(t); cAdd(cKeyword(q),'bot',true); },900); return; }
      llmComplete(q, compHistory).then(function(reply){
        if(t.parentNode) clog.removeChild(t);
        if(reply==null) reply=cKeyword(q);
        compHistory.push({role:"user",content:q},{role:"assistant",content:reply});
        if(compHistory.length>20) compHistory=compHistory.slice(-20);
        cAdd(reply,'bot',true);
      }).catch(function(){ if(t.parentNode) clog.removeChild(t); cAdd(cKeyword(q),'bot',true); });
    }
    function cSend(q){ if(!q.trim())return; cAdd(q,'me'); cReply(q); }
    cAdd(bb.greeting,'bot');
    var csg=document.getElementById('comp-suggest');
    bb.suggestions.forEach(function(s){ var b=el('<button type="button">'+s+'</button>'); b.addEventListener('click',function(){ cSend(s); }); csg.appendChild(b); });
    document.getElementById('comp-form').addEventListener('submit',function(e){ e.preventDefault(); var f=document.getElementById('comp-field'); cSend(f.value); f.value=''; });
    // tabs
    document.querySelectorAll('.comp-tab').forEach(function(t){ t.addEventListener('click',function(){
      var which=t.dataset.ctab;
      document.querySelectorAll('.comp-tab').forEach(function(x){ var on=x===t; x.classList.toggle('on',on); x.setAttribute('aria-selected',on?'true':'false'); });
      document.querySelectorAll('.comp-pane').forEach(function(p){ p.hidden = p.dataset.cpane!==which; });
    }); });
    // notebook autosave
    function bindNote(id,key){ var t=document.getElementById(id); if(!t)return; try{ t.value=localStorage.getItem(key)||''; }catch(e){}
      var saved=document.getElementById(id+'-saved'), tmo;
      t.addEventListener('input',function(){ try{ localStorage.setItem(key,t.value); }catch(e){} if(saved){ saved.classList.add('show'); clearTimeout(tmo); tmo=setTimeout(function(){ saved.classList.remove('show'); },1200); } });
    }
    bindNote('comp-earned','evoke-note-earned');
    bindNote('comp-noticed','evoke-note-noticed');
    // screenshot drop
    var drop=document.getElementById('comp-shot'), file=document.getElementById('comp-shot-input');
    if(drop&&file){
      function show(f){ if(!f||!/^image\//.test(f.type))return; var r=new FileReader(); r.onload=function(){ drop.innerHTML='<img src="'+r.result+'" alt="Your captured screenshot">'; }; r.readAsDataURL(f); }
      drop.addEventListener('click',function(){ file.click(); });
      drop.addEventListener('keydown',function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); file.click(); } });
      file.addEventListener('change',function(){ show(file.files[0]); });
      drop.addEventListener('dragover',function(e){ e.preventDefault(); drop.style.boxShadow='inset 0 0 0 2px var(--cyan-300)'; });
      drop.addEventListener('dragleave',function(){ drop.style.boxShadow=''; });
      drop.addEventListener('drop',function(e){ e.preventDefault(); drop.style.boxShadow=''; show(e.dataTransfer.files[0]); });
    }
    // current-quest title sync (works across all 12 missions)
    var mt=document.getElementById('comp-mt');
    if(mt && typeof curMission==='function'){ try{ var gm=curMission(), wi=Math.floor((gm-1)/2), mi=(gm-1)%2; mt.textContent = CONTENT.weeks[wi].missions[mi].title; }catch(e){} }
    // window enter/exit toggle
    var COMPACT_W=480, prevWin=null, compWin=null;
    // Dock the CURRENT window: narrow, full-height, snapped to the LEFT edge.
    function dockLeft(){
      try{ prevWin={w:window.outerWidth,h:window.outerHeight,x:window.screenX,y:window.screenY};
        var sw=window.screen.availWidth, sh=window.screen.availHeight, w=Math.min(COMPACT_W,sw);
        window.resizeTo(w,sh); window.moveTo(0,0);
      }catch(e){}
    }
    // Companion mode is ONE single-tab screen — no pop-out window and no
    // window resizing (both caused stale/leftover-screen bugs). Enter it from
    // anywhere; exit always returns to the Ops Hub. Snap this window beside
    // Minecraft yourself if you want them side by side.
    window.enterCompanion=function(){ go('companion'); };
    window.openCompanionWindow=function(){ go('companion'); };
    window.exitCompanion=function(){
      // Close any lingering old pop-out window; otherwise just return to Ops.
      if(/companion-window/.test(location.hash)){ try{ window.close(); }catch(e){} return; }
      go('ops');
    };
    document.getElementById('comp-exit').addEventListener('click',window.exitCompanion);
    var ec=document.getElementById('mc-companion'); if(ec) ec.addEventListener('click',window.openCompanionWindow);
    var fk=document.getElementById('ops-fieldkit-open'); if(fk) fk.addEventListener('click',window.openCompanionWindow);
  })();

  /* ---- routing ---- */
  var flow=document.getElementById('flow');
  SCREENS.forEach(function(s){
    var b=el('<button data-go="'+s[0]+'">'+s[1]+'</button>');
    flow.appendChild(b);
  });
  var navHist = [];
  function go(name, fromBack){
    var activeEl = document.querySelector('.screen.active');
    var cur = activeEl ? activeEl.dataset.screen : null;
    if(!fromBack && cur && cur!==name) navHist.push(cur);
    document.querySelectorAll('.screen').forEach(function(s){s.classList.toggle('active',s.dataset.screen===name);});
    if(name==='novel') renderNovel();
    if(name==='home' && typeof renderTimeline==='function') renderTimeline();
    if(name==='home' && window.renderHomeBadges) window.renderHomeBadges();
    if(name==='progress' && window.renderProgress) window.renderProgress();
    if(name==='vault' && typeof renderVault==='function') renderVault();
    if(name==='story') renderTransmission();
    if(name==='assignment') renderAssignment();
    if(name==='missions') renderMissions(currentWeek);
    if(name==='ops' && window.renderOps) window.renderOps(curMission());
    if(name==='submission' && window.renderSubmission) window.renderSubmission();
    if(name==='team' && window.renderTeam) window.renderTeam();
    if(name==='ops' && window.openOpsGuide){ var seen; try{ seen=localStorage.getItem('evoke-ops-guide-seen')==='1'; }catch(e){ seen=false; } if(!seen) setTimeout(window.openOpsGuide, 350); }
    if((name==='minecraft' || name==='companion') && window.renderMinecraftWeek) window.renderMinecraftWeek();
    if(name==='profile' && window.renderProfile2) window.renderProfile2();
    if(window.syncAllXP) window.syncAllXP();
    document.querySelectorAll('#flow button').forEach(function(b){b.classList.toggle('on',b.dataset.go===name);});
    document.querySelectorAll('#primary-nav .nav').forEach(function(b){
      var on = b.dataset.go===name; b.classList.toggle('on',on);
      if(on){b.setAttribute('aria-current','page');} else {b.removeAttribute('aria-current');}
    });
    document.body.classList.toggle('in-companion', name==='companion');
    // Never leave the nav hidden on a normal screen: the `companion-window`
    // chrome-hiding class is only for the genuine popped-out phone window
    // (hash #companion-window). If it ever sticks on the main app, strip it so
    // the rail returns everywhere.
    if(name!=='companion' && !/companion-window/.test(location.hash)){ document.body.classList.remove('companion-window'); }
    if(name==='home') navHist.length=0; // Home is the hub / reset point
    updateBackBtn(name);
    updateBuddy(name);
    window.scrollTo(0,0);
  }
  function goBack(){ if(navHist.length){ go(navHist.pop(), true); } }
  function updateBackBtn(name){
    var show = navHist.length>0 && name!=='home';
    document.querySelectorAll('.back-btn').forEach(function(b){ b.style.display = show ? 'inline-flex' : 'none'; });
  }

  /* ---- B1llBot companion dialogue ---- */
  var BUDDY_LINES = {
    home:"Welcome back, Agent! Pick a week and let's get to work.",
    ops:"This is your Operations Hub \u2014 your whole mission, all in one place.",
    welcome:"This is Keel. Big things ahead \u2014 you ready?",
    novel:"Read the story close. It's how you'll really get Keel.",
    missions:"Choose your assignment. I've got your back.",
    story:"Heads up \u2014 this transmission matters. Listen for the truth.",
    assignment:"Mission accepted! Your real mission is the fieldwork \u2014 the Minecraft quest is an optional bonus.",
    evidence:"Drop your evidence here when you're ready, Agent.",
    minecraft:"Earn and save money in Keel, then come back and reflect to finish.",
    reward:"YES! You did it, Agent. So proud of you.",
    vault:"Everything you've finished lives here. Nice work so far!",
    progress:"Every mission you finish earns XP. Let's climb to Level 2!",
    profile:"Looking sharp, Agent."
  };
  var buddyEl = document.getElementById('buddy');
  var buddyTextEl = document.getElementById('buddy-text');
  function updateBuddy(name){
    var line = BUDDY_LINES[name];
    if(!line || name==='billbot'){ buddyEl.style.display='none'; return; }
    buddyEl.style.display='flex';
    buddyEl.classList.remove('hidden-bubble');
    buddyTextEl.textContent = line;
    buddyEl.classList.remove('buddy-pop'); void buddyEl.offsetWidth; buddyEl.classList.add('buddy-pop');
  }
  document.getElementById('buddy-close').addEventListener('click', function(e){ e.stopPropagation(); buddyEl.classList.add('hidden-bubble'); });
  document.getElementById('buddy-face').addEventListener('click', function(){ go('billbot'); });
  // delegate all [data-go] clicks (nav, buttons, flow)
  document.addEventListener('click', function(e){
    var t = e.target.closest('[data-go]'); if(t){ go(t.dataset.go); }
  });
  // keyboard activation for non-button [data-go] elements (e.g. the logo)
  document.addEventListener('keydown', function(e){
    if((e.key==='Enter'||e.key===' ') && e.target.matches && e.target.matches('[data-go][tabindex]')){ e.preventDefault(); go(e.target.getAttribute('data-go')); }
  });
  // Demo screen switcher: hidden for testers; add ?screens to the URL to reveal it.
  if (location.search.indexOf('screens') > -1) document.body.classList.add('show-screens');
  // Deep-link to any screen with ?screen=vault (used by the tracing frames + testing).
  var _sp = new URLSearchParams(location.search);
  // Booted as the popped-out companion window? Go straight to companion mode,
  // hide the demo chrome, and dock this window to the left edge.
  if(/companion-window/.test(location.hash)){
    document.body.classList.add('companion-window');
    var _ce=document.getElementById('comp-exit'); if(_ce) _ce.innerHTML='<span class="ms" aria-hidden="true" style="font-size:17px;">close</span>Close Window';
    try{ var _sh=window.screen.availHeight, _w=Math.min(480,window.screen.availWidth), _sx=window.screen.availLeft||0, _sy=window.screen.availTop||0; window.moveTo(_sx,_sy); window.resizeTo(_w,_sh); }catch(e){}
    go('companion');
  } else {
    go(_sp.get('screen') || 'home');
  }
  /* ================= DEVELOPER PANEL (browse any week) =================
     Lets a developer jump to any mission and unlock the timeline. Turning it
     off restores the locked, sequential experience students see. */
  (function(){
    if(/companion-window/.test(location.hash)) return; // not in the popped-out companion
    function devRefresh(){
      try{ renderTimeline(); }catch(e){}
      try{ renderMissions(typeof currentWeek!=='undefined'?currentWeek:0); }catch(e){}
      try{ if(window.renderHomeBadges) renderHomeBadges(); }catch(e){}
      try{ if(window.renderProgress) renderProgress(); }catch(e){}
      try{ if(window.renderVault) renderVault(); }catch(e){}
      try{ if(window.syncAllXP) syncAllXP(); }catch(e){}
    }
    var fab=el('<button id="dev-fab" aria-label="Open developer panel" style="position:fixed;left:14px;bottom:14px;z-index:120;display:flex;align-items:center;gap:7px;padding:9px 13px;border:none;border-radius:999px;cursor:pointer;font-family:var(--font-mono);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#0b1220;background:linear-gradient(135deg,#ffb877,#ff9a4d);box-shadow:0 6px 20px -6px rgba(0,0,0,0.6);"><span class="ms" aria-hidden="true" style="font-size:16px;">build</span>Dev</button>');
    var panel=el('<div id="dev-panel" role="dialog" aria-label="Developer panel" style="position:fixed;left:14px;bottom:62px;z-index:121;width:300px;max-width:calc(100vw - 28px);display:none;padding:18px;border-radius:16px;background:rgba(13,21,40,0.97);box-shadow:0 24px 60px -12px rgba(0,0,0,0.7),inset 0 0 0 1px rgba(255,167,89,0.4);backdrop-filter:blur(12px);"></div>');
    panel.innerHTML =
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'+
        '<span style="font-family:var(--font-display);font-weight:800;font-size:15px;color:#ffb877;">Developer</span>'+
        '<button id="dev-close" aria-label="Close" style="border:none;background:none;cursor:pointer;color:var(--text-muted);"><span class="ms" style="font-size:20px;">close</span></button>'+
      '</div>'+
      '<p style="font-family:var(--font-body);font-size:12.5px;line-height:1.5;color:var(--text-faint);margin:0 0 14px;">Browse any week now. Turn this off and students get the locked, sequential flow.</p>'+
      '<label style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;border-radius:10px;background:rgba(255,255,255,0.04);box-shadow:inset 0 0 0 1px var(--border-ui);cursor:pointer;margin-bottom:14px;">'+
        '<span style="font-family:var(--font-display);font-weight:600;font-size:13px;color:var(--teal-050);">Unlock all weeks</span>'+
        '<input type="checkbox" id="dev-toggle" style="width:18px;height:18px;accent-color:#ff9a4d;cursor:pointer;">'+
      '</label>'+
      '<div class="hud" style="font-size:10px;letter-spacing:.14em;color:var(--cyan-300);margin-bottom:8px;">Jump to mission</div>'+
      '<div id="dev-grid" style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px;margin-bottom:14px;"></div>'+
      '<button id="dev-reset" style="width:100%;padding:9px;border:none;border-radius:10px;cursor:pointer;font-family:var(--font-display);font-weight:700;font-size:12px;color:var(--text-muted);background:rgba(255,255,255,0.05);box-shadow:inset 0 0 0 1px var(--border-ui);">Reset all progress</button>';
    document.body.appendChild(fab); document.body.appendChild(panel);

    var grid=panel.querySelector('#dev-grid');
    CONTENT.weeks.forEach(function(wk,wi){ wk.missions.forEach(function(m,mi){
      var n=wi*2+mi+1;
      var b=el('<button data-m="'+n+'" style="text-align:left;padding:8px 9px;border:none;border-radius:8px;cursor:pointer;background:rgba(0,150,136,0.06);box-shadow:inset 0 0 0 1px var(--border-ui);color:var(--teal-050);"><span style="display:block;font-family:var(--font-mono);font-size:9px;color:var(--cyan-300);">W'+wk.week+' \u00b7 M'+(mi+1)+'</span><span style="display:block;font-family:var(--font-display);font-weight:600;font-size:11px;line-height:1.2;margin-top:2px;">'+m.title+'</span></button>');
      b.addEventListener('click',function(){
        try{ localStorage.setItem('evoke-dev','1'); localStorage.setItem('evoke-dev-mission',String(n)); }catch(e){}
        syncDevUI(); devRefresh(); go('story');
      });
      grid.appendChild(b);
    }); });

    function syncDevUI(){
      panel.querySelector('#dev-toggle').checked=devOn();
      var sel=devSel();
      grid.querySelectorAll('button').forEach(function(b){
        var on=devOn() && parseInt(b.getAttribute('data-m'),10)===sel;
        b.style.boxShadow=on?'inset 0 0 0 1.5px #ff9a4d':'inset 0 0 0 1px var(--border-ui)';
        b.style.background=on?'rgba(255,167,89,0.14)':'rgba(0,150,136,0.06)';
      });
      grid.style.opacity=devOn()?'1':'0.5'; grid.style.pointerEvents=devOn()?'auto':'none';
    }
    function openPanel(o){ panel.style.display=o?'block':'none'; if(o) syncDevUI(); }
    fab.addEventListener('click',function(){ openPanel(panel.style.display!=='block'); });
    panel.querySelector('#dev-close').addEventListener('click',function(){ openPanel(false); });
    panel.querySelector('#dev-toggle').addEventListener('change',function(){
      try{ if(this.checked){ localStorage.setItem('evoke-dev','1'); } else { localStorage.removeItem('evoke-dev'); } }catch(e){}
      syncDevUI(); devRefresh();
    });
    panel.querySelector('#dev-reset').addEventListener('click',function(){
      if(!confirm('Reset all mission progress?')) return;
      try{ for(var i=1;i<=12;i++){ localStorage.removeItem('evoke-m'+i+'-submitted'); localStorage.removeItem('evoke-m'+i+'-started'); } }catch(e){}
      syncDevUI(); devRefresh(); go('home');
    });
    syncDevUI();
  })();

  syncAllXP();

  // ----- Phone Field Kit QR + Minecraft account pairing (real backend) -----
  (function(){
    var qrBox = document.getElementById('mc-fieldkit-qr');
    if(qrBox && STATE.userId){
      var img = new Image();
      img.alt = 'QR code to open your Field Kit on your phone';
      img.style.width='100%'; img.style.height='100%'; img.style.objectFit='contain';
      img.onload = function(){ qrBox.innerHTML=''; qrBox.appendChild(img); };
      img.src = '/api/companion/qr.svg?user_id=' + encodeURIComponent(STATE.userId);
    }
    var input = document.getElementById('mc-username');
    var btn = document.getElementById('mc-link-btn');
    var status = document.getElementById('mc-link-status');
    function showLinked(username){
      if(!status) return;
      status.innerHTML = '<span class="ms" aria-hidden="true" style="font-size:16px;color:var(--green-400);vertical-align:middle;">check_circle</span> Linked as <strong style="color:var(--cyan-100);">' + username + '</strong>';
      status.style.color = 'var(--green-400)';
    }
    if(STATE.userId){
      fetch('/api/minecraft/link/' + STATE.userId).then(function(r){ return r.ok ? r.json() : null; }).then(function(d){
        if(d && d.linked){ if(input) input.value = d.username; showLinked(d.username); }
      }).catch(function(){});
    }
    if(btn && input){
      btn.addEventListener('click', function(){
        var u = input.value.trim();
        if(!u || !STATE.userId) return;
        btn.disabled = true;
        fetch('/api/minecraft/link?user_id=' + encodeURIComponent(STATE.userId) + '&minecraft_username=' + encodeURIComponent(u), {method:'POST'})
          .then(function(r){ return r.ok ? r.json() : null; })
          .then(function(d){
            btn.disabled = false;
            if(d && d.status === 'linked'){ showLinked(d.username); }
            else if(status){ status.textContent = 'Could not link — please try again.'; status.style.color = 'var(--text-faint)'; }
          })
          .catch(function(){ btn.disabled = false; if(status){ status.textContent = 'Could not link — check your connection.'; status.style.color = 'var(--text-faint)'; } });
      });
    }
  })();

  // ===== Mission Submission screen (individual task + team discussion + team product) =====
  (function(){
    var MISSIONS = window.EVOKE_SUBMISSION_MISSIONS || [];
    var subMain = document.getElementById('sub-main');
    if(!subMain) return;
    var e2 = function(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];}); };
    var missionNo = function(){ try{ return (typeof curMission==='function') ? curMission() : 1; }catch(e){ return 1; } };
    var missionData = function(no){ return MISSIONS.find(function(m){return m.n===no;}) || MISSIONS[0]; };
    var backendId = function(no){ return STATE.missionIds && STATE.missionIds[no-1]; };

    function statusChip(text, tone){
      var c = tone==='done'?['green','check_circle']: tone==='todo'?['orange','pending']:['','schedule'];
      return '<span class="chip '+c[0]+'" style="margin-left:auto;"><span class="ms" aria-hidden="true" style="font-size:14px;">'+c[1]+'</span>'+text+'</span>';
    }
    function reqList(items){
      return '<div class="ev-reqs" style="margin-bottom:18px;">'+items.map(function(it){
        return '<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:10px;"><span class="ms" aria-hidden="true" style="font-size:20px;color:var(--cyan-300);flex:none;">task_alt</span><span style="font-family:var(--font-body);font-size:14px;line-height:1.55;color:var(--teal-050);">'+e2(it)+'</span></div>';
      }).join('')+'</div>';
    }
    function stepPill(num,label,state){
      var cfg = state==='done'?['rgba(0,212,146,0.4)','rgba(0,212,146,0.07)','var(--green-400)','rgba(0,212,146,0.16)','check','Done']
              : state==='todo'?['rgba(0,150,136,0.4)','rgba(0,150,136,0.06)','var(--cyan-300)','rgba(0,150,136,0.16)','upload_file','To do']
              : ['var(--border-ui)','transparent','var(--text-faint)','rgba(145,209,209,0.1)','forum','Optional'];
      return '<div style="flex:1;min-width:170px;display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:14px;box-shadow:inset 0 0 0 1px '+cfg[0]+';background:'+cfg[1]+';">'
        +'<span style="width:34px;height:34px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;background:'+cfg[3]+';color:'+cfg[2]+';"><span class="ms" aria-hidden="true" style="font-size:20px;">'+cfg[4]+'</span></span>'
        +'<div><div class="hud" style="font-size:9px;color:'+cfg[2]+';">'+cfg[5]+'</div><div style="font-family:var(--font-display);font-weight:700;font-size:14px;color:var(--text-heading);">'+label+'</div></div></div>';
    }
    function rosterChip(mem){
      var st = mem.team_product; // matching | divergent | missing
      var box = st==='matching'?['rgba(0,212,146,0.4)','rgba(0,212,146,0.07)','check_circle','var(--green-400)']
              : st==='divergent'?['rgba(217,164,65,0.5)','rgba(217,164,65,0.08)','error','#e0a83f']
              : ['var(--border-ui)','rgba(15,23,43,0.3)','radio_button_unchecked','var(--text-faint)'];
      var ring = mem.is_you?'box-shadow:inset 0 0 0 1.5px var(--cyan-500);':'box-shadow:inset 0 0 0 1px '+box[0]+';';
      var nm = mem.is_you?'<span style="font-family:var(--font-body);font-size:13px;color:var(--cyan-100);font-weight:700;">You</span>':'<span style="font-family:var(--font-body);font-size:13px;color:var(--teal-050);">'+e2(mem.display_name)+'</span>';
      return '<span style="display:inline-flex;align-items:center;gap:8px;padding:8px 14px 8px 8px;border-radius:999px;'+ring+'background:'+box[1]+';"><span class="mtile" style="width:26px;height:26px;border-radius:50%;font-family:var(--font-display);font-weight:700;font-size:11px;display:flex;align-items:center;justify-content:center;color:var(--cyan-100);">'+e2(mem.initials)+'</span>'+nm+'<span class="ms" aria-hidden="true" style="font-size:16px;color:'+box[3]+';">'+box[2]+'</span></span>';
    }

    var currentState = null, currentMsgs = [];

    function render(){
      var no = missionNo();
      var m = missionData(no);
      var hasInd = !!m.individual;
      var st = currentState || {};
      var you = st.you || {};
      var members = st.members || [];
      var banner = (st.banner && st.banner.show) ? ('<div class="glass brackets" style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;padding:18px 22px;margin-bottom:26px;box-shadow:inset 0 0 0 1px rgba(0,150,136,0.35),0 0 34px -12px rgba(0,150,136,0.5);">'
        +'<span style="width:56px;height:60px;flex:none;"><img src="img/ui/3.png" alt="" style="width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 5px 14px rgba(0,150,136,0.45));"></span>'
        +'<div style="flex:1;min-width:240px;"><div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:5px;">B1llBot · Team Nudge</div>'
        +'<div style="font-family:var(--font-body);font-size:15px;line-height:1.5;color:var(--teal-050);">Your team’s rolling, Agent — <strong style="color:var(--cyan-100);">'+st.banner.submitted+' of '+st.banner.total+'</strong> have turned in the Evokation and you’re the last piece. Drop yours in and finish it together. 🚀</div></div></div>') : '';

      var indStatus = you.individual_task ? 'done' : 'todo';
      var prodStatus = (you.team_product && you.team_product!=='missing') ? 'done' : 'todo';

      var head = banner
        + '<div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;">'
        + '<span class="chip"><span class="ms" aria-hidden="true" style="font-size:16px;">groups</span>'+e2(m.phase)+' · Week '+m.week+' · Mission '+m.n+'</span>'
        + '<span class="chip teal"><span class="ms" aria-hidden="true" style="font-size:15px;">military_tech</span>'+e2(m.superpower)+'</span></div>'
        + '<h1 style="font-family:var(--font-display);font-weight:700;font-size:clamp(28px,5vw,46px);text-transform:uppercase;color:var(--cyan-500);text-shadow:0 0 24px rgba(0,150,136,0.3);text-align:center;margin:0 0 8px;">'+e2(m.title)+'</h1>'
        + '<p style="text-align:center;color:var(--teal-100);font-family:var(--font-body);font-size:15px;line-height:1.55;margin:0 auto 26px;max-width:640px;">'+(hasInd?'Complete your steps below. Your individual work feeds the team’s shared Evokation — everyone contributes.':'A team deliverable — talk it through, then everyone turns in your team’s shared product.')+'</p>';

      var stepper = '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px;">'
        + (hasInd?stepPill(1,'Individual Task',indStatus):'')
        + stepPill(hasInd?2:1,'Team Discussion', you.discussed?'done':'optional')
        + stepPill(hasInd?3:2,'Team Product', prodStatus) + '</div>';

      var indHtml = '';
      if(hasInd){
        indHtml = '<div class="glass" style="padding:clamp(22px,3.5vw,30px);margin-bottom:22px;">'
          + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;flex-wrap:wrap;"><span class="ms" aria-hidden="true" style="font-size:24px;color:var(--cyan-300);">person</span><h2 class="hud" style="font-size:12px;margin:0;color:var(--cyan-300);">Step 1 · Your Individual Task</h2>'+statusChip(you.individual_task?'Submitted':'To do', you.individual_task?'done':'todo')+'</div>'
          + '<p style="font-family:var(--font-body);font-size:14px;color:var(--teal-100);margin:0 0 14px;">Your own contribution — the piece only you are accountable for. Turn in:</p>'
          + reqList(m.individual.items)
          + '<div class="ev-drop" id="sub-ind-drop" role="button" tabindex="0" style="margin-bottom:16px;"><span class="ms" aria-hidden="true">cloud_upload</span><div class="ev-drop-title">Drop your individual work</div><div class="ev-drop-sub">or <span class="ev-browse">browse from your device</span></div></div>'
          + '<input type="file" id="sub-ind-file" class="sr-only" aria-hidden="true">'
          + '<label class="ev-label">Your reflection</label><textarea id="sub-reflect" class="ev-textarea" placeholder="What did you learn or notice…" style="min-height:90px;">'+e2(you.reflection_text||'')+'</textarea>'
          + '<div style="text-align:right;margin-top:12px;"><button class="btn sec" id="sub-reflect-save" type="button">Save reflection</button></div></div>';
      }

      var msgsHtml = (currentMsgs||[]).map(function(mm){
        return '<div style="display:flex;gap:12px;align-items:flex-start;"><span class="mtile" style="width:36px;height:36px;flex:none;border-radius:50%;font-family:var(--font-display);font-weight:700;font-size:14px;display:flex;align-items:center;justify-content:center;color:var(--cyan-100);">'+e2(mm.initials)+'</span><div style="flex:1;"><div style="font-family:var(--font-display);font-weight:700;font-size:13px;color:var(--cyan-200);margin-bottom:3px;">'+e2(mm.display_name)+(mm.is_you?' <span class="hud" style="font-weight:400;color:var(--text-faint);font-size:10px;">you</span>':'')+'</div><div style="font-family:var(--font-body);font-size:14px;line-height:1.5;color:var(--teal-050);padding:10px 14px;border-radius:0 12px 12px 12px;box-shadow:inset 0 0 0 1px var(--border-ui);">'+e2(mm.message)+'</div></div></div>';
      }).join('') || '<p class="hud" style="font-size:12px;color:var(--text-faint);margin:0 0 14px;">No messages yet — start the conversation below.</p>';
      var discHtml = '<div class="glass" style="padding:clamp(22px,3.5vw,30px);margin-bottom:22px;">'
        + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;flex-wrap:wrap;"><span class="ms" aria-hidden="true" style="font-size:24px;color:var(--cyan-300);">forum</span><h2 class="hud" style="font-size:12px;margin:0;color:var(--cyan-300);">Step '+(hasInd?2:1)+' · Team Discussion</h2><span class="hud" style="margin-left:auto;font-size:11px;color:var(--text-faint);">'+(currentMsgs.length)+' message'+(currentMsgs.length===1?'':'s')+'</span></div>'
        + '<div style="margin:0 0 16px;padding:13px 15px;border-radius:12px;background:rgba(0,150,136,0.06);box-shadow:inset 0 0 0 1px var(--border-ui);">'
          + '<div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:5px;">B1llBot</div>'
          + '<div style="font-family:var(--font-body);font-size:14px;line-height:1.55;color:var(--teal-050);">'+e2(m.discussionPrompt)+'</div></div>'
        + '<div style="display:flex;flex-direction:column;gap:12px;margin-bottom:16px;">'+msgsHtml+'</div>'
        + '<form id="sub-disc-form" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;"><input id="sub-disc-input" type="text" placeholder="Add to the discussion…" style="flex:1 1 160px;min-width:0;padding:12px 14px;border-radius:12px;border:none;background:rgba(0,150,136,0.06);box-shadow:inset 0 0 0 1px var(--border-ui);color:var(--text-heading);font-family:var(--font-body);font-size:14px;"><button class="btn sec" type="submit" style="flex:none;width:auto;min-width:96px;">Post</button></form></div>';

      var chips = members.map(rosterChip).join('');
      var diverge = members.filter(function(x){return x.team_product==='divergent';});
      var divNote = diverge.length ? '<div style="display:flex;align-items:center;gap:8px;margin-top:14px;font-family:var(--font-mono);font-size:11px;color:var(--text-faint);"><span class="ms" aria-hidden="true" style="font-size:15px;color:#e0a83f;">info</span>'+e2(diverge.map(function(x){return x.display_name;}).join(', '))+' turned in a different file than the rest of the team — your facilitator will take a look. It won’t block anyone.</div>' : '';
      var teamHtml = '<div class="glass brackets" style="padding:clamp(22px,3.5vw,30px);margin-bottom:22px;box-shadow:inset 0 0 0 1px rgba(0,150,136,0.32),var(--elev-glass);">'
        + '<div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;flex-wrap:wrap;"><span class="ms" aria-hidden="true" style="font-size:24px;color:var(--cyan-300);">groups</span><h2 class="hud" style="font-size:12px;margin:0;color:var(--cyan-300);">Step '+(hasInd?3:2)+' · Team Product</h2>'+statusChip(prodStatus==='done'?'Submitted':'Your turn', prodStatus)+'</div>'
        + '<p style="font-family:var(--font-body);font-size:14px;color:var(--teal-100);margin:0 0 14px;">Your team’s shared deliverable. Everyone turns in the <strong style="color:var(--cyan-100);">same file</strong> — that’s how we know the whole team signed off. Include:</p>'
        + reqList(m.teamProduct.items)
        + '<div class="ev-drop" id="sub-team-drop" role="button" tabindex="0" style="margin-bottom:18px;"><span class="ms" aria-hidden="true">cloud_upload</span><div class="ev-drop-title">Drag &amp; drop your team’s Evokation</div><div class="ev-drop-sub">or <span class="ev-browse">browse from your device</span></div><div class="ev-drop-hint">Should match your teammates’ file</div></div>'
        + '<input type="file" id="sub-team-file" class="sr-only" aria-hidden="true">'
        + '<div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:10px;">Team Roster · who’s turned it in</div>'
        + '<div style="display:flex;flex-wrap:wrap;gap:10px;">'+chips+'</div>'+divNote+'</div>';

      var footer = '<div style="display:flex;align-items:center;justify-content:flex-end;gap:14px;flex-wrap:wrap;"><button class="btn" id="sub-complete" type="button">Back to Operations Hub ▶<span class="key" aria-hidden="true"></span></button></div>';

      subMain.innerHTML = head + stepper + indHtml + discHtml + teamHtml + footer;
      wire(no);
    }

    function wire(no){
      var mid = backendId(no);
      // uploads
      function hookUpload(dropId, fileId, kind){
        var drop = document.getElementById(dropId), file = document.getElementById(fileId);
        if(!drop || !file) return;
        drop.addEventListener('click', function(){ file.click(); });
        drop.addEventListener('keydown', function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); file.click(); } });
        file.addEventListener('change', function(){
          if(!file.files || !file.files[0] || !mid || !STATE.userId) return;
          var fd = new FormData();
          fd.append('user_id', STATE.userId); fd.append('mission_id', mid); fd.append('kind', kind); fd.append('file', file.files[0]);
          drop.querySelector('.ev-drop-title').textContent = 'Uploading…';
          fetch('/api/submit-evidence', {method:'POST', body:fd}).then(function(r){return r.json();})
            .then(function(){ refresh(no); }).catch(function(){ drop.querySelector('.ev-drop-title').textContent = 'Upload failed — try again'; });
        });
      }
      hookUpload('sub-ind-drop','sub-ind-file','individual_task');
      hookUpload('sub-team-drop','sub-team-file','team_product');
      // discussion
      var df = document.getElementById('sub-disc-form');
      if(df) df.addEventListener('submit', function(e){
        e.preventDefault();
        var inp = document.getElementById('sub-disc-input'); var msg = (inp.value||'').trim();
        if(!msg || !mid) return; inp.value='';
        fetch('/api/team-discussion', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({user_id:STATE.userId, mission_id:mid, message:msg})})
          .then(function(){ refresh(no); }).catch(function(){});
      });
      // reflection
      var rs = document.getElementById('sub-reflect-save');
      if(rs) rs.addEventListener('click', function(){
        var ta = document.getElementById('sub-reflect'); var val = (ta.value||'').trim();
        if(!val || !mid) return; rs.disabled = true; rs.textContent = 'Saving…';
        var fd = new FormData(); fd.append('user_id', STATE.userId); fd.append('mission_id', mid); fd.append('reflection', val);
        fetch('/api/submit-reflection', {method:'POST', body:fd}).then(function(){ rs.textContent='Saved ✓'; setTimeout(function(){ refresh(no); }, 600); }).catch(function(){ rs.disabled=false; rs.textContent='Save reflection'; });
      });
      var comp = document.getElementById('sub-complete');
      if(comp) comp.addEventListener('click', function(){ go('ops'); });
    }

    function refresh(no){
      var mid = backendId(no);
      if(!mid || !STATE.userId){ currentState=null; currentMsgs=[]; render(); return; }
      Promise.all([
        fetch('/api/submission-state/'+STATE.userId+'/'+mid).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}),
        fetch('/api/team-discussion/'+STATE.userId+'/'+mid).then(function(r){return r.ok?r.json():null;}).catch(function(){return null;})
      ]).then(function(res){
        currentState = res[0] || {};
        currentMsgs = (res[1] && res[1].messages) || [];
        render();
      });
    }

    window.renderSubmission = function(){ refresh(missionNo()); };
  })();

  // ===== Team page (B1llBot holo-comms layout: identity+squad bay | team chat) =====
  (function(){
    var infoCol = document.getElementById('team-info');
    var log = document.getElementById('team-chat-log');
    if(!infoCol || !log) return;
    var e3 = function(s){ return String(s==null?'':s).replace(/[&<>"]/g,function(c){return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'})[c];}); };
    var teamData=null, msgs=[];
    function avatar(initials, you, s){
      s=s||42;
      return '<span class="mtile" style="width:'+s+'px;height:'+s+'px;flex:none;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:var(--font-display);font-weight:800;font-size:'+Math.round(s*0.36)+'px;color:var(--cyan-100);'+(you?'box-shadow:inset 0 0 0 1.5px var(--cyan-500),var(--glow-md);':'')+'">'+e3(initials)+'</span>';
    }
    var BAY = infoCol.innerHTML; // keep the REC/SQUAD/CH bay tags
    function render(){
      var t=teamData||{}, members=t.members||[], MT=12;
      var identity = '<div style="margin-bottom:20px;">'
        +'<div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:6px;letter-spacing:.14em;">// TEAM</div>'
        +'<h1 style="font-family:var(--font-display);font-weight:800;font-size:clamp(20px,2.4vw,28px);color:var(--text-heading);margin:0;text-transform:uppercase;letter-spacing:.02em;line-height:1.05;">'+e3(t.name||'Your Team')+'</h1>'
        +(t.motto?'<div style="font-family:var(--font-body);font-style:italic;font-size:13px;color:var(--teal-100);margin-top:8px;">“'+e3(t.motto)+'”</div>':'')
        +'<div class="bb-status" style="margin-top:12px;justify-content:flex-start;"><span class="dot" aria-hidden="true"></span>'+members.length+' member'+(members.length===1?'':'s')+' · online</div></div>';
      var squad = '<div class="hud" style="font-size:10px;color:var(--cyan-300);margin-bottom:8px;letter-spacing:.14em;">Squad</div>'
        + members.map(function(m){
            var pct=Math.round((m.missions_completed||0)/MT*100);
            return '<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-top:1px solid var(--border-faint);">'
              +avatar(m.initials, m.is_you, 40)
              +'<div style="flex:1;min-width:0;"><div style="font-family:var(--font-display);font-weight:700;font-size:14px;color:var(--text-heading);">'+e3(m.display_name)+(m.is_you?' <span class="hud" style="font-weight:400;font-size:9px;color:var(--cyan-300);">you</span>':'')+'</div>'
              +'<div class="hud" style="font-size:9px;color:var(--text-faint);margin:5px 0;">Lv '+(m.level||1)+' · '+(m.missions_completed||0)+'/'+MT+' missions</div>'
              +'<span style="display:block;width:100%;height:5px;border-radius:999px;background:rgba(255,255,255,0.08);overflow:hidden;"><span style="display:block;height:100%;width:'+pct+'%;background:linear-gradient(90deg,var(--cyan-500),var(--green-400));"></span></span></div></div>';
          }).join('');
      infoCol.innerHTML = BAY + '<div style="width:100%;margin-top:20px;">' + identity + squad + '</div>';

      log.innerHTML = (msgs||[]).length ? msgs.map(function(mm){
        if(mm.is_you) return '<div class="bubble me">'+e3(mm.message)+'</div>';
        return '<div class="bubble bot"><span style="display:block;font-family:var(--font-display);font-weight:700;font-size:11px;letter-spacing:.02em;color:var(--cyan-200);margin-bottom:4px;">'+e3(mm.display_name)+'</span>'+e3(mm.message)+'</div>';
      }).join('') : '<div class="bubble bot" style="opacity:0.75;">No messages yet — say hi to your team. 👋</div>';
      log.scrollTop = log.scrollHeight;
    }
    function refresh(){
      if(!STATE.userId){ teamData=null; msgs=[]; render(); return; }
      Promise.all([
        getJSON('/api/team/'+STATE.userId).catch(function(){return null;}),
        getJSON('/api/team-messages/'+STATE.userId).catch(function(){return {messages:[]};})
      ]).then(function(r){ teamData=r[0]||{}; msgs=(r[1]&&r[1].messages)||[]; render(); });
    }
    var form=document.getElementById('team-chat-form');
    if(form) form.addEventListener('submit', function(e){
      e.preventDefault();
      var inp=document.getElementById('team-chat-field'); var m=(inp.value||'').trim();
      if(!m || !STATE.userId) return; inp.value='';
      postJSON('/api/team-message',{user_id:STATE.userId,message:m}).then(function(){ refresh(); }).catch(function(){});
    });
    window.renderTeam=function(){ refresh(); };
  })();

  });
})();
