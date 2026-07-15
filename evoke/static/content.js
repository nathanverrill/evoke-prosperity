/* content.js — narrative content ported verbatim from the design file
   (Prosperity Showcase-44.html CONTENT); inline base64 images extracted to
   img/content/*. Designer-authored copy the UI renders. */
window.EVOKE_CONTENT = {
    brand: "EVOKE",
    nav: [
      { id:"home",    icon:"home",        label:"Learn",    fill:true },
      { id:"ops",     icon:"hub",         label:"Operations Hub" },
      { id:"progress",icon:"shield",      label:"Progress" },
      { id:"vault",   icon:"inventory_2", label:"Vault" },
      { id:"billbot", icon:"smart_toy",   label:"B1llbot" },
      { id:"profile", icon:"person",      label:"Profile",  fill:true }
    ],
    greeting: { kicker:"Hello, Agent", title:"Ready for your next mission?", sub:"Let's get started!" },
    streak: [ ["M",1],["T",1],["W",1],["TH",1],["F",0],["S",0],["SU",0] ],
    badges: [ {icon:"military_tech",label:"Changemaker",tone:"teal"}, {icon:"bolt",label:"First Steps",tone:"cyan"} ],

    // ---- CAMPAIGN STRUCTURE ----------------------------------------
    // 6 weeks, each with 2 missions. Missions MUST be played in a strict
    // linear order: W1·M1 → W1·M2 → W2·M1 → W2·M2 → ... → W6·M2.
    // `completedMissions` = how many the student has finished in that order.
    // The next one in sequence is "current" (playable); everything after is locked.
    // Real EVOKE curriculum — 6 weeks · 12 activities. Badge = the activity's Superpower.
    // Phases: Week 1 EXPLORE · Weeks 2–3 IMAGINE · Weeks 4–5 ACT · Week 6 COMMUNICATE.
    completedMissions: 0,
    weeks: [
      { week:1, missions:[
        { icon:"rocket_launch", title:"Follow the Flow", sub:"// Listen to Keel",     desc:"Investigate a real community challenge \u2014 water, housing, or money \u2014 and understand how different people live it before you try to solve it.", badge:"Empathetic Changemaker", badgeIcon:"military_tech" },
        { icon:"fingerprint",   title:"Your Prosperity Origin Story", sub:"// Make It Personal", desc:"Connect the challenge to your own life and values, then choose the future you want to help build.", badge:"Systems Thinker", badgeIcon:"hub" }
      ]},
      { week:2, missions:[
        { icon:"tips_and_updates", title:"Dream Beyond the Obvious", sub:"// Imagine Beyond", desc:"Brainstorm wild, unexpected ideas for your challenge \u2014 then spot the 2\u20133 directions worth imagining further.", badge:"Creative Visionary", badgeIcon:"lightbulb" },
        { icon:"auto_awesome",  title:"2035: If We Get This Right", sub:"// Picture 2035",   desc:"Choose one idea and picture the future it creates by 2035. Define your North Star and bring that vision to life.", badge:"Creative Visionary", badgeIcon:"lightbulb" }
      ]},
      { week:3, missions:[
        { icon:"calculate",     title:"What Would It Take \u2014 for Real?", sub:"// Count the Cost", desc:"Research what it really takes to start \u2014 people, time, tools, money \u2014 and build your first starter budget.", badge:"Systems Thinker", badgeIcon:"hub" },
        { icon:"savings",       title:"What If We Actually Did This?", sub:"// Make It Real", desc:"Stress-test your plan, find sources of income, and turn your budget into a stronger, more realistic version.", badge:"Creative Visionary", badgeIcon:"lightbulb" }
      ]},
      { week:4, missions:[
        { icon:"build",         title:"Bring It to Life",  sub:"// Build It",           desc:"Decide what to build first and create a real prototype that brings your solution to life.", badge:"Systems Thinker", badgeIcon:"hub" },
        { icon:"auto_fix_high", title:"Strengthen the Vision", sub:"// Strengthen It",   desc:"Reconnect your prototype to your 2035 vision and strengthen it into a version ready for testing.", badge:"Empathetic Changemaker", badgeIcon:"military_tech" }
      ]},
      { week:5, missions:[
        { icon:"reviews",       title:"Put It in the World", sub:"// Test It Live",      desc:"Put your prototype in front of real people, gather honest feedback, and decide what matters most.", badge:"Empathetic Changemaker", badgeIcon:"military_tech" },
        { icon:"verified",      title:"Worth Backing",     sub:"// Worth Backing",       desc:"Align as a team, define what success looks like, and make the case for why your venture is worth backing.", badge:"Deep Collaborator", badgeIcon:"diversity_3" }
      ]},
      { week:6, missions:[
        { icon:"campaign",      title:"Craft Your Pitch",  sub:"// Make the Case",      desc:"Turn your decisions into a clear, memorable pitch \u2014 and decide how many Venture Points to offer for support.", badge:"Deep Collaborator", badgeIcon:"diversity_3" },
        { icon:"co_present",    title:"The Evokation",     sub:"// The Evokation",       desc:"Deliver your live Evokation: the challenge, your solution, your pitch, and the future you\u2019re building toward.", badge:"Deep Collaborator", badgeIcon:"diversity_3" }
      ]}
    ],
    // Graphic-novel pages (Step 2 of the journey)
    novel: {
      chapter:"Chapter 1 \u00b7 The Thirst of Keel",
      pages:[
        { img:"img/content/c1.jpg" },
        { img:"img/content/c2.jpg" }
        ,{ img:"img/content/c3.jpg" }
        ,{ img:"img/content/c4.jpg" }
      ]
    },
        novel_m3: {
      chapter:"Chapter 2 \u00b7 The View From the Mountain",
      pages:[
        { img:"img/content/c5.jpg" },
        { img:"img/content/c6.jpg" },
        { img:"img/content/c7.jpg" },
        { img:"img/content/c8.jpg" }
      ]
    },
    novel_m5: {
      chapter:"Chapter 3 \u00b7 From the Ground Up",
      pages:[
        { img:"img/content/c9.jpg" },
        { img:"img/content/c10.jpg" }
      ]
    },
    novel_m7: {
      chapter:"Chapter 4 \u00b7 The Mountain Thrives",
      pages:[
        { img:"img/content/c10.jpg" },
        { img:"img/content/c11.jpg" }
      ]
    },
    novel_m9: {
      chapter:"Chapter 5 \u00b7 The Evoke Network",
      pages:[
        { img:"img/content/c11.jpg" },
        { img:"img/content/c12.jpg" }
      ]
    },
    novel_m11: {
      chapter:"Chapter 6 \u00b7 Global Solutions",
      pages:[
        { img:"img/content/c12.jpg" },
        { img:"img/content/c13.jpg" }
      ]
    },
    // Agent transmission (Step 3) — the full monologue
    transmission: {
      speaker:"AGENT // FIELD LOG",
      lead:"Your Mission",
      stanzas:[
        ["If you want to understand this challenge\u2014really understand it\u2014you have to step into it.","Not as yourself.","As them."],
        ["And stay curious: ask good questions before jumping to conclusions."]
      ],
      emphasis:["Listen.","Not for data.","For truth."]
    },
    transmission_m2: {
      speaker:"AGENT // FIELD LOG",
      lead:"Last time, you named the challenge.",
      stanzas:[
        ["Now\u2026 bring it closer.","Close enough that it stops being \u201Can issue\u201D\u2026","and starts being your story."],
        ["Reflection is not just looking backward.","It is understanding what your experiences might mean for the future you want to create."]
      ],
      emphasis:["Every changemaker has an origin.","This is where yours begins.","\u2014 Alex"]
    },
    // Mission assignment (Step 4)
    assignment: {
      n:"01", title:"Follow the Flow", sub:"// Mission Status",
      objectiveLine:"I can identify issues in my community that non-profits help solve.",
      guide:"B1llbot",
      source:"Alex \u2014 Keel Extraction Zone 7",
      brief:[
        "Your mission: if you want to understand this challenge \u2014 really understand it \u2014 you have to step into it. Not as yourself. As them.",
        "And stay curious: ask good questions before jumping to conclusions."
      ],
      objectives:[
        { code:"01", icon:"directions_walk", t:"Walk in Their World", body:[
          { p:"Choose at least two stakeholders connected to the issue your team is exploring. They could include:" },
          { list:[
            "Someone directly affected by the issue \u2014 a peer, family member, or community member",
            "Someone trying to help solve it \u2014 a school counselor, nonprofit, or community leader",
            "Someone connected to the larger system \u2014 water utility staff, local officials, fire department personnel, or others relevant to your challenge"
          ] },
          { p:"Then talk with them. Listen closely \u2014 not just for answers, but for emotion, perspective, and patterns. Ask questions like:" },
          { list:[
            "What does this challenge feel like in your life?",
            "What worries or frustrates you most about it?",
            "What matters most to you in this situation?",
            "Where does money or access to resources play a role?",
            "How are they currently addressing this, if at all \u2014 and where are they falling short?"
          ] },
          { p:"Listen for understanding. Pay attention to what's not being said, and ask clarifying questions if something feels incomplete or surprising." }
        ] },
        { code:"02", icon:"join_inner", t:"Find the Friction", body:[
          { p:"Now compare what you've learned as a team:" },
          { list:[
            "Where do their experiences align?",
            "Where do they clash?"
          ] },
          { p:"This is where the truth hides." },
          { p:"And here's the hard part: what's one assumption you had\u2026 that no longer holds up? Say it out loud. Write it down. Own it. That's how real understanding begins." }
        ] },
        { code:"03", icon:"account_tree", t:"Name the Challenge", body:[
          { p:"Now name the challenge. As a team, create a clear, compelling Challenge Statement that identifies the community issue you want to address through your Evokation, and the financial realities shaping it." },
          { p:"Think about:" },
          { list:[
            "The issue that kept surfacing across the people you spoke with",
            "How the issue affects individuals or the community",
            "The systems or barriers making the challenge harder to solve",
            "Where money, access, or resources play a role",
            "What evidence led you to this conclusion"
          ] }
        ] }
      ],
      evidence:{ title:"Evidence Cache", intro:"To complete this mission, your team must submit:", reqs:[
        "Notes or reflections from at least two stakeholder perspectives \u2014 including one assumption you challenged",
        "A Challenge Statement that identifies the community issue and the financial realities shaping it"
      ] },
      xp:450, badge:"Empathetic Changemaker"
    },
    assignment_m2: {
      n:"02", title:"Your Prosperity Origin Story", sub:"// Mission Status",
      objectiveLine:"I can set personal goals and take responsibility for them by reflecting on what I\u2019ve experienced.",
      guide:"B1llbot",
      source:"Alex \u2014 Halyard Ascent",
      brief:[
        "Last time, you named the challenge. Now\u2026 bring it closer. Close enough that it stops being \u201Can issue\u201D\u2026 and starts being your story.",
        "Reflection is not just looking backward. It is understanding what your experiences might mean for the future you want to create."
      ],
      objectives:[
        { code:"01", icon:"link", t:"Trace the Connection", body:[
          { p:"Take the challenge you defined in Mission 1. Now ask yourself:" },
          { list:[
            "Where does this show up in my life?",
            "Have I seen it? Felt it? Been affected by it \u2014 even indirectly?",
            "Who do I know that lives this reality?",
            "What assumptions or beliefs have shaped the way I see this challenge?"
          ] },
          { p:"This isn\u2019t about being perfect. It\u2019s about being honest." }
        ] },
        { code:"02", icon:"trending_up", t:"Look Forward", body:[
          { p:"This is where power begins. Where could this path take you? What kind of future do you want to build?" },
          { list:[
            "Problem solver?",
            "Entrepreneur?",
            "Advocate?",
            "Designer?",
            "Leader?"
          ] },
          { p:"This is goal setting. This is about direction \u2014 about deciding: if this challenge matters to me\u2026 what am I going to do about it?" }
        ] },
        { code:"03", icon:"fingerprint", t:"Make It Yours", body:[
          { p:"Now bring it all together. Choose one:" },
          { list:[
            "Write your Prosperity Origin Story \u2014 a short personal story about why this challenge matters to you and the future you want to help create",
            "OR",
            "Design your EVOKE Avatar \u2014 another way of telling your Prosperity Origin Story"
          ] },
          { p:"This isn\u2019t pretend. It\u2019s practice \u2014 a chance to reflect on who you are becoming, and what role you want to play in the future." }
        ] }
      ],
      evidence:{ title:"Evidence Cache", intro:"To complete this mission, you must submit:", reqs:[
        "Either your Prosperity Origin Story OR your EVOKE Avatar",
        "A future direction that relates to the challenge (career, project, hobby, or personal interest)"
      ], fieldLabel:"Your Prosperity Origin Story", fieldPlaceholder:"Tell the short personal story of why this challenge matters to you \u2014 and the future you want to help create." },
      xp:450, badge:"Systems Thinker"
    },
    

    transmission_m3: {"speaker":"AGENT // FIELD LOG","lead":"Recruit…","stanzas":[["You've felt the challenge.","You've made it personal."],["Now it's time to do something most people never do:","Imagine beyond what exists."],["Your first idea? It's probably safe. Expected. Obvious.","The best ideas rarely arrive first."]],"emphasis":["Brainstorm wild. Don't filter.","Then choose what pulls you."]},
    assignment_m3: {"n":"03","title":"Dream Beyond the Obvious","sub":"// Mission Status","objectiveLine":"I can imagine many possible solutions to a community issue before choosing a direction.","guide":"B1llbot","source":"Alex — The Dreaming Flats","brief":["You've felt the challenge. You've made it personal. Now do something most people never do:","Imagine beyond what exists."],"objectives":[{"code":"01","icon":"lightbulb","t":"Brainstorm Your Dream Map","body":[{"p":"Your first idea is probably safe. Leave it behind. With your team, generate as many ideas as possible — wild, practical, impossible."},{"p":"Don't judge. Don't filter. Don't stop early. Capture everything in one shared space: paper, sticky notes, a mind map, or a digital whiteboard."}]},{"code":"02","icon":"hub","t":"Find the Patterns","body":[{"p":"Step back and look at everything your team created. Ask:"},{"list":["What ideas seem connected?","What themes keep showing up?","Which ideas make each other stronger?","Are there surprising combinations worth exploring?"]},{"p":"Sometimes the most powerful ideas emerge when separate ideas collide."}]},{"code":"03","icon":"ads_click","t":"Choose What Pulls You","body":[{"p":"Now begin to narrow. Identify the ideas that feel boldest, most surprising, or most capable of meaningful change."},{"p":"You don't need one final solution yet — but your team should choose 2–3 promising directions worth imagining further."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["A collaborative Dream Map showing your team's brainstorming and emerging idea clusters","2–3 promising solution directions your team wants to explore further"]},"xp":450,"badge":"Creative Visionary"},
    transmission_m4: {"speaker":"AGENT // FIELD LOG","lead":"Visionary…","stanzas":[["You've imagined possibilities.","Now choose one."],["And do something even harder:","Imagine what happens if you get it right."],["Real leaders do more than solve today's problem.","They imagine a future worth building — and help others see it too."]],"emphasis":["Travel to 2035.","Find your North Star."]},
    assignment_m4: {"n":"04","title":"2035: If We Get This Right","sub":"// Mission Status","objectiveLine":"I can picture the future my idea could create and define what success looks like.","guide":"B1llbot","source":"Alex — Beacon Ridge, 2035","brief":["You've imagined possibilities. Now choose one — and do something even harder:","Imagine what happens if you get it right."],"objectives":[{"code":"01","icon":"rocket_launch","t":"Travel to 2035","body":[{"p":"Choose one promising solution from your Dream Map. Now imagine it's the year 2035 and your idea worked. Picture that future:"},{"list":["Who is experiencing change?","What feels different?","What problem has become smaller — or disappeared?","What does success actually look like?","How will your idea be sustained?"]}]},{"code":"02","icon":"explore","t":"Find Your North Star","body":[{"p":"Big visions begin with clarity, not slogans. As a team, decide what matters most about the future you want to create. Write down:"},{"list":["The change you most want to see","Who benefits from that change","What success would mean in real life"]},{"p":"This is your North Star — the future your team wants to move toward and help others believe in."}]},{"code":"03","icon":"auto_awesome","t":"Show the World","body":[{"p":"Create a short creative expression of your 2035 vision (1–2 lines max). It could be:"},{"list":["A future news headline","A short message from someone living in that future","A graphic-novel panel","Another short creative expression of your vision"]}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["A 1–2 sentence North Star Statement that defines the change your team wants to create and what success would look like","A short creative expression of your 2035 vision that brings that future to life"]},"xp":450,"badge":"Creative Visionary"},
    transmission_m5: {"speaker":"AGENT // FIELD LOG","lead":"Strategist…","stanzas":[["You've imagined your solution.","You've pictured the future it could help create."],["Now ask the practical question:","What would it actually take to get started?"],["Every idea — no matter how powerful — needs resources.","Don't just guess. Use evidence to test your assumptions."]],"emphasis":["Sort what matters most.","Build a starter budget."]},
    assignment_m5: {"n":"05","title":"What Would It Take — for Real?","sub":"// Mission Status","objectiveLine":"I can research real costs and build a starter budget that separates essentials from extras.","guide":"B1llbot","source":"Alex — The Ledger House","brief":["You've imagined your solution and pictured the future it could create.","Now ask the practical question: what would it actually take to get started?"],"objectives":[{"code":"01","icon":"checklist","t":"Identify What You Need","body":[{"p":"Every idea needs resources. Break it down:"},{"list":["People — who needs to be involved?","Time — how long might it take to get started?","Partnerships — who could support or unlock progress?","Space & Tools — what physical or digital resources are needed?","Money — what costs might need to be covered?"]},{"p":"Research real prices, simple budget templates, and publicly available 990s to make smarter estimates."}]},{"code":"02","icon":"low_priority","t":"Sort What Matters Most","body":[{"p":"You probably can't do everything at once. Sort what you identified:"},{"list":["Essential — what do we need to get started?","Can wait — what would help later, but isn't needed right now?"]},{"p":"This is budgeting: deciding what's essential to get started."}]},{"code":"03","icon":"request_quote","t":"Build a Starter Budget","body":[{"p":"Use a project budget template to estimate the costs of getting your idea started. Include:"},{"list":["The key expenditures your team prioritized","A rough estimated cost for each item"]},{"p":"You don't need exact numbers. This is your team's first draft — not the final version."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["A simple starter budget showing your prioritized expenditures, rough cost estimates, and brief notes on how you estimated those costs","A short research snapshot (links, notes, screenshots, or sources) showing how your team gathered information to make smarter estimates"]},"xp":450,"badge":"Systems Thinker"},
    transmission_m6: {"speaker":"AGENT // FIELD LOG","lead":"Problem-solver…","stanzas":[["You've imagined the future.","You've estimated what it might take to get started."],["Now think creatively and challenge yourself to imagine:","What if we actually do this?"],["Creativity is not just about dreaming up big ideas.","It's also about solving real problems when resources are limited."]],"emphasis":["Stress test the plan.","Build the other side of the budget."]},
    assignment_m6: {"n":"06","title":"What If We Actually Did This?","sub":"// Mission Status","objectiveLine":"I can find sources of income and turn my budget into a stronger, more realistic plan.","guide":"B1llbot","source":"Alex — The Workshop","brief":["You've imagined the future and estimated what it might take.","Now think creatively: what if we actually did this?"],"objectives":[{"code":"01","icon":"fact_check","t":"Stress Test the Plan","body":[{"p":"Take a fresh look at your starter budget and ask:"},{"list":["What seems unrealistic?","What costs might be missing?","Where could we start smaller, phase the launch, or simplify?","What could be donated, borrowed, shared, or provided by a partner?"]},{"p":"Use BillBot, another team, or a mentor to test your thinking."}]},{"code":"02","icon":"payments","t":"Build the Other Side of the Budget","body":[{"p":"Budgets aren't just about costs — they're also about income. As a team, brainstorm:"},{"list":["What sources of income or revenue could help this idea launch?","What could help it continue over time?","Could the people who benefit pay for part of it?","Could sponsorship, fundraising, partnerships, or subscriptions help?"]},{"p":"Push past the first idea."}]},{"code":"03","icon":"edit_note","t":"Update Your Budget","body":[{"p":"Use what you learned to improve your starter budget. Update:"},{"list":["Projected expenditures","Sources of income or revenue","Assumptions that changed","What now feels realistic"]},{"p":"This is your stronger next version."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["An updated budget showing revised expenditures, changed assumptions, and what now feels most realistic","A short list of possible sources of income or revenue that could help your solution launch, continue, or grow"]},"xp":450,"badge":"Creative Visionary"},
    transmission_m7: {"speaker":"AGENT // FIELD LOG","lead":"Builder…","stanzas":[["You've imagined a better world.","You've created a budget to make it happen."],["Now, consider: can you bring it to life?","Not perfectly. Not completely. But enough to make it real."],["Complex problems rarely get solved all at once.","This is where you stop imagining — and start building."]],"emphasis":["Choose what to prototype.","Start small. Make it real."]},
    assignment_m7: {"n":"07","title":"Bring It to Life","sub":"// Mission Status","objectiveLine":"I can break a big idea into a first build and create a real prototype.","guide":"B1llbot","source":"Alex — The Build Yard","brief":["You've imagined a better world and built a budget to make it happen.","Now — can you bring it to life? Enough to make it real."],"objectives":[{"code":"01","icon":"ads_click","t":"Choose What to Prototype","body":[{"p":"Your full idea may be too big to build all at once. Focus. Ask:"},{"list":["What problem are we trying to solve first?","What is the first version we can create?","What's the simplest way to show how it works?","What's the most important part of the solution?"]},{"p":"Start small. A strong first prototype can be simple."}]},{"code":"02","icon":"build","t":"Build a Concrete Prototype","body":[{"p":"Now make it real. It doesn't need to be polished — just clear enough for others to understand. Your prototype can be:"},{"list":["A physical model","A visual design or storyboard","A digital mockup, wireframe, or simulation","A Minecraft build"]},{"p":"Use what you have. Focus on showing the most important part of your idea."}]},{"code":"03","icon":"pause_circle","t":"Pause and Prepare to Improve","body":[{"p":"Your first prototype is not the final version. Step back and ask:"},{"list":["What's working?","What still feels unfinished?","What would make this stronger?"]},{"p":"You'll keep building in the next mission."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["The first version of a concrete prototype showing how your solution could work","A 1–2 sentence explanation of what your team chose to prototype first — and why"]},"xp":450,"badge":"Systems Thinker"},
    transmission_m8: {"speaker":"AGENT // FIELD LOG","lead":"Leader…","stanzas":[["You built the first version.","Now ask a new question:"],["Does this prototype reflect the future we imagined?"],["A first version proves you can start.","Leadership means choosing what moves forward now — and what can wait."]],"emphasis":["Reconnect to your vision.","Build the next version."]},
    assignment_m8: {"n":"08","title":"Strengthen the Vision","sub":"// Mission Status","objectiveLine":"I can make thoughtful tradeoffs to strengthen my prototype toward our vision.","guide":"B1llbot","source":"Alex — The Proving Ground","brief":["You built the first version. Now lead it forward.","Does this prototype reflect the future we imagined?"],"objectives":[{"code":"01","icon":"explore","t":"Reconnect to Your Vision","body":[{"p":"Go back to your 2035 vision and ask:"},{"list":["What future were we trying to create?","What mattered most in that vision?","Does our prototype reflect that?","What feels like it is missing?"]},{"p":"Strong leaders invite different perspectives and keep the bigger picture in view."}]},{"code":"02","icon":"auto_fix_high","t":"Build the Next Version","body":[{"p":"Now iterate — revise, strengthen, simplify, or expand your prototype so it more clearly reflects your vision. Weigh alternatives and tradeoffs:"},{"list":["What should stay?","What should change?","What matters most right now?","What can wait?"]},{"p":"This isn't about perfection. It's about making the next version stronger."}]},{"code":"03","icon":"groups","t":"Move Forward Together","body":[{"p":"Take a moment as a team. Look at what you built, recognize each person's contribution, and make sure everyone understands what this version is meant to show."},{"p":"Then celebrate the progress. You're ready to put it in the world."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["A revised prototype ready for testing that clearly communicates your solution","A brief explanation of one important choice or tradeoff your team made (what you changed, kept, simplified, or set aside — and why)"]},"xp":450,"badge":"Empathetic Changemaker"},
    transmission_m9: {"speaker":"AGENT // FIELD LOG","lead":"Changemaker…","stanzas":[["You built something.","Now put it in the world."],["This is where courage matters.","Real builders let other people react to unfinished work."],["And they listen.","Even when the feedback is uncomfortable."]],"emphasis":["Test your prototype.","Decide what feedback matters most."]},
    assignment_m9: {"n":"09","title":"Put It in the World","sub":"// Mission Status","objectiveLine":"I can test my prototype with real people and use honest feedback to decide what matters most.","guide":"B1llbot","source":"Alex — The Town Square","brief":["You built something real. Now have the courage to share it.","Put it in the world — and listen."],"objectives":[{"code":"01","icon":"reviews","t":"Test Your Prototype","body":[{"p":"Put your prototype in front of people beyond your team — classmates, mentors, family, or community members. Ask open questions:"},{"list":["What do you think this does?","What stands out to you?","What feels confusing?","What would make this more useful?","Would something like this matter to you — why or why not?"]},{"p":"Listen carefully. Don't explain too quickly. Don't defend — be curious."}]},{"code":"02","icon":"visibility","t":"Look Through Their Eyes","body":[{"p":"As a team, compare what you heard:"},{"list":["What surprised us?","What did people understand right away?","Where did they struggle?","What concerns or questions came up?","What did we learn about the people we hope to serve?"]},{"p":"Empathy means seeing your idea through someone else's experience."}]},{"code":"03","icon":"filter_alt","t":"Decide What Feedback Matters","body":[{"p":"Not all feedback points the same direction. Decide:"},{"list":["What feedback feels most important?","What changes would make the biggest difference?","What should we improve before moving forward?"]},{"p":"This isn't about pleasing everyone — it's about learning what matters, and having the courage to change course if needed."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["Documented feedback from your prototype testing (notes, quotes, or observations)","A short team decision about the most important change or insight that will shape what happens next"]},"xp":450,"badge":"Empathetic Changemaker"},
    transmission_m10: {"speaker":"AGENT // FIELD LOG","lead":"Operative…","stanzas":[["You've imagined, built, tested, and improved your solution.","Now decide whether it is truly worth backing."],["Strong teams do more than build ideas.","They make hard decisions — together."],["They listen, challenge one another respectfully,","and align around a shared direction."]],"emphasis":["Get aligned. Define success.","Make your case."]},
    assignment_m10: {"n":"10","title":"Worth Backing","sub":"// Mission Status","objectiveLine":"I can align my team, define success, and judge where our venture fits on the risk spectrum.","guide":"B1llbot","source":"Alex — The Roundtable","brief":["You've imagined, built, tested, and improved your solution.","Now decide — together — whether it's truly worth backing."],"objectives":[{"code":"01","icon":"groups","t":"Get Aligned","body":[{"p":"You've each experienced this journey a little differently. Before moving forward, make sure your team is building the same thing. Lay out:"},{"list":["Your challenge","Your vision","Your budget","Your prototype","What you learned from testing"]},{"p":"Make space for quieter voices and surface disagreements early. If your team sees different versions of the project, fix that now."}]},{"code":"02","icon":"flag","t":"Define Success","body":[{"p":"Go back to your 2035 vision and decide how you'll recognize progress. Choose 2–3 measurable signs your solution is working, such as:"},{"list":["Number of users or participants","Revenue or cash flow","Lower costs","Stronger adoption or engagement","Fewer barriers or greater community uptake"]}]},{"code":"03","icon":"speed","t":"The Venture Spectrum: Make Your Case","body":[{"p":"Every investment involves opportunity and risk — the higher the risk, the higher the possible reward. Decide where your solution belongs:"},{"list":["LOW RISK — easier to launch, fewer resources, steadier impact","MEDIUM RISK — significant resources, ~50/50 odds, impressive possible impact","HIGH RISK — massive resources, lower odds, world-changing possible impact"]},{"p":"Then complete the sentence: “Our solution is worth backing because ____.” Ask BillBot to help think through the tradeoffs."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["2–3 measurable indicators of success","Where your venture fits (Low, Medium, or High Risk) and a one-sentence investment case"]},"xp":450,"badge":"Deep Collaborator"},
    transmission_m11: {"speaker":"AGENT // FIELD LOG","lead":"Advocate…","stanzas":[["Your team decided your solution is worth backing.","Now prove it to others."],["A strong idea is not enough.","People need to understand it. Believe in it. Want to support it."],["You used creativity to build your solution.","Now use creativity to show it off."]],"emphasis":["Make the Venture Points call.","Build your pitch."]},
    assignment_m11: {"n":"11","title":"Craft Your Pitch","sub":"// Mission Status","objectiveLine":"I can turn our decisions into a clear pitch and decide how much of our venture to offer for support.","guide":"B1llbot","source":"Alex — The Pitch Deck","brief":["Your team decided your solution is worth backing. Now prove it to others.","A strong idea isn't enough — people need to understand it, believe it, and want to support it."],"objectives":[{"code":"01","icon":"toll","t":"The Venture Points Challenge","body":[{"p":"Your team has 100 Venture Points representing the value of your venture — your points are your voting power and control. Keeping points means more control but more work; offering points brings resources but shares control. Decide how many to offer to attract support."},{"list":["Keep 90 / Offer 10 — high confidence, low outside dependence","Keep 60 / Offer 40 — shared support, majority control","Keep 30 / Offer 70 — bigger investment, you give up majority control"]},{"p":"Match your choice to your risk profile, then complete: “We are offering ____ Venture Points because ____.”"}]},{"code":"02","icon":"campaign","t":"Build Your Pitch","body":[{"p":"Craft a clear, memorable message that makes someone believe your solution is worth backing. Answer:"},{"list":["What problem are you solving?","What is your solution, and how does your prototype bring it to life?","How much will it cost to develop and launch — and what do those costs consist of?","What impact or return could it create?","What support are you asking for?"]}]},{"code":"03","icon":"theater_comedy","t":"Design the Experience","body":[{"p":"Communication is more than words. Decide how your team will deliver the pitch:"},{"list":["Who will speak, and what each member will do","What you will show","How you want your audience to remember your idea"]},{"p":"Your pitch might include your prototype, props, visuals, a slide deck, or a short video. Practice, strengthen, and have fun."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must submit:","reqs":["A completed pitch","Your Venture Points offer"]},"xp":450,"badge":"Deep Collaborator"},
    transmission_m12: {"speaker":"AGENT // FIELD LOG","lead":"Agent…","stanzas":[["This is your moment.","Bring everything together."],["Share the challenge you took on,","the solution you built, and the choices that shaped your pitch."],["Strong relationship builders do more than present —","they listen, connect, and respond with respect."]],"emphasis":["Deliver your Evokation.","Stand up and be heard."]},
    assignment_m12: {"n":"12","title":"The Evokation","sub":"// Mission Status","objectiveLine":"I can deliver our Evokation and respond to an audience with clarity and courage.","guide":"B1llbot","source":"Alex — The Evokation Stage","brief":["This is your moment. Bring everything together.","Not to prepare. Not to revise. To stand up and be heard."],"objectives":[{"code":"01","icon":"co_present","t":"Deliver Your Evokation","body":[{"p":"Bring everything together and deliver your pitch. Speak clearly and with purpose. Show your audience why your solution is worth backing."},{"p":"Make eye contact. Read the room. Help your audience feel included in the conversation."}]},{"code":"02","icon":"forum","t":"Engage the Audience","body":[{"p":"Strong relationships are built in real time. Listen carefully, respond thoughtfully, and adapt to the questions in front of you."},{"p":"Respect different perspectives — even when they challenge your thinking — and look for common ground between your audience's concerns and your team's goals. This is where trust is built, and where courage shows."}]}],"evidence":{"title":"Evidence Cache","intro":"To complete this mission, your team must deliver:","reqs":["Your team's live Evokation presentation, including a respectful audience Q&A exchange","Your challenge, your innovation and prototype, your pitch, your Venture Points offer, and your vision for the future"]},"xp":450,"badge":"Deep Collaborator"},

    // Progress dashboard (nav)
    progress: {
      level:1, levelLabel:"Level 1 · Recruit", xp:0, xpMax:1000,
      stats:[
        { label:"Missions Complete", value:"0", sub:"of 12", icon:"rocket_launch", id:"pg-missions" },
        { label:"Badges Earned",     value:"0", sub:"of 12", icon:"military_tech", id:"pg-badges-stat" },
        { label:"Day Streak",        value:"0", sub:"this week", icon:"local_fire_department", id:"pg-streak-count" },
        { label:"Truths Recorded",   value:"3", sub:"in the field", icon:"format_quote" }
      ]
    },
    // Agent profile (nav)
    profile: {
      codename:"Agent Nova", role:"Field Recruit · Keel Network", joined:"Joined Week One",
      level:"Level 1", xpLine:"0 / 1000 XP to Level 2",
      badges:[
        { icon:"military_tech", label:"Empathetic Changemaker" },
        { icon:"bolt",          label:"First Steps" },
        { icon:"sensors",       label:"First Transmission" }
      ],
      settings:[
        { icon:"accessibility_new", label:"Accessibility",  value:"High contrast · On" },
        { icon:"notifications",     label:"Notifications",  value:"Mission reminders" },
        { icon:"volume_up",         label:"Sound & Music",  value:"On" }
      ]
    },
    rewards: [
      { name:"Empathetic Changemaker", sub:"Badge Unlocked",       icon:"military_tech" },
      { name:"First Transmission",     sub:"Achievement Unlocked", icon:"trophy" }
    ],
    vault: [
      { mission:1, n:"W1\u00b7M1", title:"Follow the Flow", segments:[{h:"The Mission",t:"You stepped into Keel to spot real problems in a community by listening to the people actually living through them."},{h:"What You Explored",t:"You walked Keel's struggling neighborhoods and saw that the biggest issues, like lack of water, unfair treatment, and broken systems, aren't fixed by technology or quick solutions alone. Through Alex's story, you saw how nonprofits bridge the gap between decision-makers and the communities they affect by doing the hard work of listening and connecting people."},{h:"What You Learned",t:"Real change starts with compassion and genuine understanding, not just efficiency. Before you try to fix anything, you have to truly listen to the people living inside the problem. That's the mindset of a changemaker, and why you earned the Empathetic Changemaker badge."}], summary:"Agent, you just completed a crucial mission called Follow the Flow, where you learned how to spot real problems in your community by listening to the people actually living through them. You explored Keel's struggling neighborhoods and discovered that the biggest issues, like lack of access to water, unfair treatment, and broken systems, aren't solved by technology or quick fixes alone, but by understanding what people really need. Through Alex's story, you saw how nonprofits step in to bridge the gap between decision-makers and the communities they affect, doing the hard work of listening and connecting people instead of just pushing solutions from above. You earned your Empathetic Changemaker badge because you recognized that real change starts with compassion and genuine understanding, not just efficiency or optimization. Remember this as you move forward: before you try to fix anything in the world, you have to truly listen to the people living inside those problems. You're building the mindset of a changemaker who leads with empathy.", badge:"Empathetic Changemaker", date:"Completed · Week 1", icon:"rocket_launch", img:"", desc:"You walked in their world, found the friction, and named the challenge \u2014 listening for the truth beneath the scarcity." },
      { mission:2, n:"W1\u00b7M2", title:"Your Prosperity Origin Story", segments:[{h:"The Mission",t:"This mission asked you to look inward and discover who you're becoming, not just in Keel but in your own life."},{h:"What You Explored",t:"You followed Alex's struggle against a system that controls people by controlling their identities, and you reflected on how the systems around you, at school, at home, and online, can quietly shape who you are. Then you created your Evoke identity and left a signal for the agents who come after you."},{h:"What You Learned",t:"Real change starts with understanding yourself: your values, what matters to you, and the direction you want to move toward. By choosing your own future instead of letting circumstances choose it for you, you showed the power to question, reflect, and decide, the heart of the Systems Thinker badge."}], summary:"You just completed a powerful mission that asked you to look inward and discover who you're becoming, not just in the game world of Keel but in your own life. You explored Alex's struggle against a system that controls people by controlling their identities, and you reflected on how the systems around you, at school, at home, online, might be shaping who you are without you even realizing it. You learned that real change starts with understanding yourself: your values, what matters to you personally, and the direction you want to move toward. By creating your Evoke identity and leaving your signal for other agents, you took responsibility for choosing your own future instead of letting circumstances choose it for you. This is what earning the Systems Thinker badge means: recognizing that you have the power to question, reflect, and decide who you're becoming. You're ready to move forward with purpose.", badge:"Systems Thinker", date:"Completed · Week 1", icon:"trending_up", img:"", desc:"You traced the challenge to your own life, looked forward, and chose your direction \u2014 beginning your Prosperity Origin Story." },
      {"mission":3,"n":"W2·M1","title":"Dream Beyond the Obvious","segments":[{"h":"The Mission","t":"You pushed past the first, safe idea and let your team imagine boldly — generating far more possibilities than you could ever use."},{"h":"What You Explored","t":"You built a Dream Map of wild, practical, and impossible ideas, then stepped back to find the patterns connecting them. You learned that powerful ideas often appear when separate thoughts collide, not when you settle for the obvious."},{"h":"What You Learned","t":"Real innovation starts with quantity and courage, not the first answer. By choosing 2–3 bold directions to explore further, you showed the imagination of a Creative Visionary."}],"summary":"Agent, in Dream Beyond the Obvious you trained yourself to think past the easy answer. You and your team flooded a Dream Map with ideas — wild, practical, and impossible — then looked for the themes and surprising combinations hiding inside them. You learned that the strongest ideas rarely arrive first, and that imagination is a discipline: you have to generate a lot before you narrow. By selecting 2–3 promising directions to carry forward, you proved you can dream big and still aim it at real change. That's the heart of the Creative Visionary superpower.","badge":"Creative Visionary","date":"Completed · Week 2","icon":"lightbulb","img":"","desc":"You flooded a Dream Map with bold ideas, found the patterns, and chose 2–3 directions worth imagining further."},
      {"mission":4,"n":"W2·M2","title":"2035: If We Get This Right","segments":[{"h":"The Mission","t":"You chose one idea and imagined the future it could build — then defined what success would actually look like."},{"h":"What You Explored","t":"You traveled to 2035 and pictured a world where your idea worked: who changed, what felt different, what problem shrank. From that, you wrote a North Star to guide your team and gave the vision a creative form others could see."},{"h":"What You Learned","t":"Leaders don't just solve today's problem — they make a future worth building feel real to others. Naming your North Star is how you turn a dream into direction, the mark of a Creative Visionary."}],"summary":"Agent, 2035: If We Get This Right asked you to do something most people never do — imagine success, not just struggle. You chose one idea and pictured the world it could create by 2035, then distilled that into a North Star: the change you most want to see, who benefits, and what success really means. Finally you expressed that future in a way others could feel, whether a headline, a message from the future, or a comic panel. You learned that vision is leadership — helping people believe in a future worth building. You're growing your Creative Visionary superpower.","badge":"Creative Visionary","date":"Completed · Week 2","icon":"auto_awesome","img":"","desc":"You imagined your idea's 2035 future, set a North Star, and brought that vision to life for others to see."},
      {"mission":5,"n":"W3·M1","title":"What Would It Take — for Real?","segments":[{"h":"The Mission","t":"You turned a big vision into something concrete by researching what it would actually take to get started."},{"h":"What You Explored","t":"You broke your idea into people, time, partnerships, tools, and money, then researched real prices and even public 990s. You sorted everything into essentials and ‘can-wait’ items and built a first starter budget."},{"h":"What You Learned","t":"Budgeting is decision-making: choosing what's essential to begin. By grounding your estimates in evidence instead of guesses, you thought like a Systems Thinker."}],"summary":"Agent, What Would It Take — for Real? moved you from dreaming to planning. You broke your solution into the resources it truly needs — people, time, partnerships, space, tools, and money — and researched real costs to test your assumptions instead of guessing. Then you sorted everything into what's essential to start versus what can wait, and built your first starter budget. You learned that a budget is really a series of smart decisions about what matters most right now. That evidence-based, big-picture thinking is the Systems Thinker superpower at work.","badge":"Systems Thinker","date":"Completed · Week 3","icon":"calculate","img":"","desc":"You researched real costs, separated essentials from extras, and built your first starter budget."},
      {"mission":6,"n":"W3·M2","title":"What If We Actually Did This?","segments":[{"h":"The Mission","t":"You stress-tested your plan and found creative ways to fund it — turning a rough budget into a realistic one."},{"h":"What You Explored","t":"You looked for missing costs, places to start smaller, and resources you could borrow, share, or get donated. Then you built the other side of the budget by brainstorming sources of income and revenue."},{"h":"What You Learned","t":"Creativity isn't only about big ideas — it's solving real problems with limited resources. Strengthening both sides of your budget showed the resourcefulness of a Creative Visionary."}],"summary":"Agent, What If We Actually Did This? challenged you to make your idea real within real constraints. You stress-tested your starter budget — hunting for missing costs, ways to phase or simplify the launch, and resources you could borrow, share, or have donated. Then you built the other side of the budget, brainstorming how the idea could earn income through customers, sponsorship, fundraising, partnerships, or subscriptions. You learned that creativity also means solving practical problems when money is tight. That resourceful problem-solving grows your Creative Visionary superpower.","badge":"Creative Visionary","date":"Completed · Week 3","icon":"savings","img":"","desc":"You stress-tested your plan, found sources of income, and turned your budget into a realistic next version."},
      {"mission":7,"n":"W4·M1","title":"Bring It to Life","segments":[{"h":"The Mission","t":"You stopped imagining and started building — turning your solution into a first, real prototype."},{"h":"What You Explored","t":"You decided what to build first, breaking a complex idea into the simplest version that shows how it works. Then you made it real — a model, storyboard, mockup, or Minecraft build — and paused to spot what was working and what wasn't."},{"h":"What You Learned","t":"Complex problems get solved in pieces, not all at once. Choosing a focused first build and making it tangible is the practical mindset of a Systems Thinker."}],"summary":"Agent, Bring It to Life was where your idea finally took physical form. You decided what to prototype first — the core, the key interaction, the simplest way to show how it works — and then built it. It didn't need to be polished, just clear enough for others to understand: a model, a storyboard, a digital mockup, or a Minecraft build. Afterward you paused to notice what worked and what still felt unfinished, ready to improve. You learned that big problems are solved one focused step at a time. That's the Systems Thinker superpower in action.","badge":"Systems Thinker","date":"Completed · Week 4","icon":"build","img":"","desc":"You chose what to build first and created a real, first-version prototype of your solution."},
      {"mission":8,"n":"W4·M2","title":"Strengthen the Vision","segments":[{"h":"The Mission","t":"You led your prototype forward — reconnecting it to your vision and making thoughtful choices about what to strengthen."},{"h":"What You Explored","t":"You revisited your 2035 vision, found what was missing, and built a stronger next version. Working within your budget, you weighed tradeoffs: what to keep, change, simplify, or set aside."},{"h":"What You Learned","t":"Leadership means making responsible choices about what moves forward now and what can wait. Strengthening your prototype with the bigger picture in mind reflects an Empathetic Changemaker."}],"summary":"Agent, Strengthen the Vision asked you to lead, not just build. You reconnected your prototype to the 2035 future you imagined, asked what was missing, and built a stronger next version. Along the way you made real decisions — weighing alternatives, tradeoffs, and consequences as you chose what to keep, change, simplify, or set aside within your budget. Then you brought your team together, recognized everyone's contribution, and prepared to share your work with the world. You learned that responsible, thoughtful choices are what leadership looks like. That grows your Empathetic Changemaker superpower.","badge":"Empathetic Changemaker","date":"Completed · Week 4","icon":"auto_fix_high","img":"","desc":"You reconnected your prototype to your vision and strengthened it into a version ready for testing."},
      {"mission":9,"n":"W5·M1","title":"Put It in the World","segments":[{"h":"The Mission","t":"You found the courage to put unfinished work in front of real people — and to listen."},{"h":"What You Explored","t":"You tested your prototype with people beyond your team, asking open questions and resisting the urge to defend it. You compared what you heard, saw your idea through others' eyes, and decided which feedback mattered most."},{"h":"What You Learned","t":"Real builders learn from honest reactions, even uncomfortable ones. Listening with empathy and being willing to change course shows the heart of an Empathetic Changemaker."}],"summary":"Agent, Put It in the World took real courage. You shared your prototype with people beyond your team — classmates, mentors, family, community members — and asked open questions instead of defending your idea. You listened for what made sense, what confused them, and what sparked interest, then compared notes as a team to see your idea through their eyes. Finally you decided which feedback mattered most and what to change before moving forward. You learned that honest feedback, even when it's uncomfortable, is how ideas get stronger. That empathy and courage define the Empathetic Changemaker superpower.","badge":"Empathetic Changemaker","date":"Completed · Week 5","icon":"reviews","img":"","desc":"You tested your prototype with real people, gathered honest feedback, and decided what mattered most."},
      {"mission":10,"n":"W5·M2","title":"Worth Backing","segments":[{"h":"The Mission","t":"You made three strategic decisions together that turned your solution into something others could realistically back."},{"h":"What You Explored","t":"You aligned as a team around one shared project, defined 2–3 measurable signs of success, and placed your venture on the risk spectrum — low, medium, or high — with a one-sentence investment case."},{"h":"What You Learned","t":"Strong teams make hard calls together, listening and aligning after honest conversation. Turning individual ideas into shared commitment is the work of a Deep Collaborator."}],"summary":"Agent, Worth Backing was about turning many voices into one shared decision. You aligned your team around the same challenge, vision, budget, prototype, and testing insights — making space for quieter voices and surfacing disagreements early. You defined 2–3 measurable signs that would show your solution is working, then placed your venture on the risk spectrum and made your case: ‘Our solution is worth backing because…’ You learned that strong teams reach shared commitment through honest conversation, not silence. That's the Deep Collaborator superpower.","badge":"Deep Collaborator","date":"Completed · Week 5","icon":"verified","img":"","desc":"You aligned your team, defined success, and made the case for where your venture fits and why it's worth backing."},
      {"mission":11,"n":"W6·M1","title":"Craft Your Pitch","segments":[{"h":"The Mission","t":"You turned your strategy into a clear, memorable pitch — and decided how much of your venture to offer for support."},{"h":"What You Explored","t":"Using your 100 Venture Points, you weighed control against the resources outside support could bring. Then you built a pitch that answers the problem, your solution, the costs, the impact, and the support you're seeking — and designed how your team would deliver it."},{"h":"What You Learned","t":"Communication is more than talking — it's making ideas clear, memorable, and worth supporting. Aligning your ask with your risk profile shows a Deep Collaborator who can rally others."}],"summary":"Agent, Craft Your Pitch turned everything you decided into a message others could believe in. You took on the Venture Points Challenge — deciding how many of your 100 points to offer, balancing control against the time, money, and expertise outside backers could bring, and matching that choice to your venture's risk. Then you built a clear, memorable pitch covering the problem, your solution and prototype, the costs, the impact, and the support you're asking for — and designed how your team would deliver it. You learned that great communication makes ideas clear, memorable, and worth backing. That grows your Deep Collaborator superpower.","badge":"Deep Collaborator","date":"Completed · Week 6","icon":"campaign","img":"","desc":"You set your Venture Points offer and built a clear, memorable pitch your team is ready to deliver."},
      {"mission":12,"n":"W6·M2","title":"The Evokation","segments":[{"h":"The Mission","t":"This was your moment — to stand up, deliver your Evokation, and respond to a live audience."},{"h":"What You Explored","t":"You brought together your challenge, innovation, prototype, pitch, and Venture Points offer and presented them with purpose. Then you engaged a real audience, listening and adapting through a respectful Q&A."},{"h":"What You Learned","t":"Relationship builders do more than present — they listen, connect, and respond with respect, especially when perspectives differ. Owning your decisions together in real time takes courage, the mark of a Deep Collaborator."}],"summary":"Agent, The Evokation was the culmination of everything — your moment to be heard. You brought together the challenge you took on, the solution and prototype you built, your pitch, your Venture Points offer, and your vision for the future, and you delivered it with clarity and purpose. Then you engaged your audience for real: listening carefully, responding thoughtfully, adapting to questions, and respecting perspectives different from your own. You learned that trust is built in how you connect and respond, not just in what you present — and that owning your decisions as a team takes courage. You've fully earned the Deep Collaborator superpower.","badge":"Deep Collaborator","date":"Completed · Week 6","icon":"co_present","img":"","desc":"You delivered your live Evokation — challenge, prototype, pitch, and vision — and engaged a real audience with courage."}
    ],
    billbot: {
      greeting: "Hey Agent! I'm B1llbot, your field assistant. Ask me about your missions, the world of Keel, or how to earn badges.",
      suggestions: [ "What's my next mission?", "How do I earn badges?", "Tell me about Keel" ],
      replies: [
        { match:["next mission","mission three","what now"], text:"Mission Three unlocks once you review Mission Two in the Vault. Want to head there?" },
        { match:["badge","earn","level"],                    text:"You earn badges by completing missions and making empathetic choices. You've unlocked Changemaker and First Steps — two more to reach Level 2!" },
        { match:["keel","world","story"],                    text:"Keel is a town gripped by drought. They blame the Oasis for hoarding water. Your job is to uncover the truth and bring prosperity back." },
        { match:["vault","past","completed","review"],       text:"The Vault holds every assignment you've finished. Check the Vault tab to revisit Missions One and Two." },
        { match:["minecraft","build world","play","launch"],  text:"Your mission continues in Minecraft \u2014 a required quest. Open Minecraft on your computer, walk Keel, complete in-game missions to earn and save money, then come back here and reflect on what you did." },
        { match:["xp","points"],                             text:"You're at 620 XP — just 380 to go before Level 2. Finishing a mission is the fastest way to climb." }
      ],
      fallback: "I'm still learning, Agent! Try asking about your missions, badges, the Vault, or the world of Keel."
    }
  };
