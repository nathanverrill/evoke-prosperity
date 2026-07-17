/* submission-missions.js — the exact per-mission submission requirements,
   transcribed from "Prosperity Campaign Missions" (Mission Submission Redesign).
   Drives the adaptive submission screen: `individual` is null for missions that
   the doc defines as team-product-only (5–12); those still gate each learner via
   reflection + a Team Discussion post + ratifying the team file. */
window.EVOKE_SUBMISSION_MISSIONS = [
  {
    n: 1, phase: "Explore", week: 1, title: "Follow the Flow",
    superpower: "Empathetic Changemaker", skills: ["Empathy", "Research & Analysis"],
    individual: {
      items: [
        "B1llBot interview notes — one surprising insight, one assumption you challenged, and one question you'd now ask a real community member",
        "Notes from at least two stakeholder perspectives, including one assumption you challenged"
      ]
    },
    discussionPrompt: "Mind if I ask you something? Most folks think they're good listeners. Truth is, most of us are just waiting for our turn to talk. Before you wrap this up, what's one question you didn't ask that might've taught you something important? I'd ask that one next.",
    teamProduct: {
      items: [
        "A combined stakeholder list",
        "A Challenge Statement naming the community issue and the financial realities shaping it"
      ]
    }
  },
  {
    n: 2, phase: "Explore", week: 1, title: "Your Prosperity Origin Story",
    superpower: "Systems Thinker", skills: ["Critical Reflection", "Communication"],
    individual: {
      items: [
        "Either your Prosperity Origin Story OR your EVOKE Avatar",
        "A future direction that relates to the challenge (career, project, hobby, or personal interest)"
      ]
    },
    discussionPrompt: "Everybody's got a story. Mine certainly wasn't a straight line. Here's what I'd like to know... what part of your story has actually made you stronger? Don't tell me what happened to you. Tell me what you earned because of it.",
    teamProduct: {
      items: [
        "Team Name",
        "Team Logo",
        "Team Motto",
        "One paragraph explaining how each member's story shaped the team's identity"
      ]
    }
  },
  {
    n: 3, phase: "Imagine", week: 2, title: "Dream Beyond the Obvious",
    superpower: "Creative Visionary", skills: ["Imagination", "Teamwork"],
    individual: {
      items: [
        "Five original solution ideas",
        "Highlight the one idea you're most excited about"
      ]
    },
    discussionPrompt: "Careful now. Teams have a funny habit of falling in love with the first good idea that comes along. If you had to throw out your favorite idea today...which one would you work on tomorrow? That answer might be the better one.",
    teamProduct: {
      items: [
        "A collaborative Dream Map showing your brainstorming and emerging idea clusters",
        "2–3 promising solution directions your team wants to explore further"
      ]
    }
  },
  {
    n: 4, phase: "Imagine", week: 2, title: "2035: If We Get This Right",
    superpower: "Creative Visionary", skills: ["Vision", "Leadership"],
    individual: {
      items: [
        "A 1–2 sentence North Star Statement — the change your team wants to create and what success would look like"
      ]
    },
    discussionPrompt: "I like optimists. But the ones I trust are the ones with a plan. So let me ask you...what has to be true for this future to actually happen? If you're counting on somebody else to make it happen, you might want to think again.",
    teamProduct: {
      items: [
        "A short creative expression of your 2035 vision (a future headline, a message from the future, a graphic-novel panel, or another format)"
      ]
    }
  },
  {
    n: 5, phase: "Imagine", week: 3, title: "What Would It Take—for Real?",
    superpower: "Systems Thinker", skills: ["Research & Analysis", "Problem Solving"],
    individual: null,
    discussionPrompt: "Budgets have a way of humbling people. Which number in here do you really know...and which one's just a hopeful guess? Nothing wrong with guessing—just don't confuse it with knowing.",
    teamProduct: {
      items: [
        "A simple starter budget — prioritized expenditures, rough cost estimates, and brief notes on how you estimated them",
        "A short research snapshot (links, notes, screenshots, or sources) showing how you gathered information"
      ]
    }
  },
  {
    n: 6, phase: "Imagine", week: 3, title: "What If We Actually Did This?",
    superpower: "Creative Visionary", skills: ["Creativity", "Critical Reflection"],
    individual: null,
    discussionPrompt: "Here's something I've learned. Money's usually not the first thing you run out of. You run out of creativity first. So tell me...if nobody gave you another dollar, how would you keep moving?",
    teamProduct: {
      items: [
        "An updated budget — revised expenditures, changed assumptions, and what now feels most realistic",
        "A short list of possible income or revenue sources that could help your solution launch, continue, or grow"
      ]
    }
  },
  {
    n: 7, phase: "Act", week: 4, title: "Bring It to Life",
    superpower: "Systems Thinker", skills: ["Problem Solving", "Imagination"],
    individual: null,
    discussionPrompt: "You know what I like about prototypes? They don't argue with you. They just show you what's broken. If I picked this up without you standing beside me...where would I get stuck?",
    teamProduct: {
      items: [
        "The first version of a concrete prototype showing how your solution could work",
        "A 1–2 sentence explanation of what your team chose to prototype first — and why"
      ]
    }
  },
  {
    n: 8, phase: "Act", week: 4, title: "Strengthen the Vision",
    superpower: "Empathetic Changemaker", skills: ["Leadership", "Vision"],
    individual: null,
    discussionPrompt: "Can I tell you a secret? Some of my worst decisions came right after my biggest successes. We start believing every idea we've had is a good one. So tell me...what are you keeping because it's truly important...and what are you keeping just because you worked hard on it?",
    teamProduct: {
      items: [
        "A revised prototype ready for testing that clearly communicates your solution",
        "A brief explanation of one important choice or tradeoff (what you changed, kept, simplified, or set aside — and why)"
      ]
    }
  },
  {
    n: 9, phase: "Act", week: 5, title: "Put It in the World",
    superpower: "Empathetic Changemaker", skills: ["Courage", "Empathy"],
    individual: null,
    discussionPrompt: "Well...you asked for feedback. Now comes the hard part. Which comment made you a little uncomfortable? That's usually the one worth sitting with a bit longer.",
    teamProduct: {
      items: [
        "Documented feedback from your prototype testing (notes, quotes, or observations)",
        "A short team decision about the most important change or insight that will shape what happens next"
      ]
    }
  },
  {
    n: 10, phase: "Act", week: 5, title: "Worth Backing",
    superpower: "Deep Collaborator", skills: ["Teamwork", "Relationship Management"],
    individual: null,
    discussionPrompt: "Let me put on my investor hat for a minute. If I had one tough question that could keep me from backing your idea...what do you think it'd be? Don't dodge it. That's probably the question you ought to answer first.",
    teamProduct: {
      items: [
        "2–3 measurable indicators of success",
        "Where your venture fits (Low / Medium / High Risk) and a one-sentence investment case"
      ]
    }
  },
  {
    n: 11, phase: "Communicate", week: 6, title: "Craft Your Pitch",
    superpower: "Deep Collaborator", skills: ["Communication", "Creativity"],
    individual: null,
    discussionPrompt: "I've sat through more pitches than I can count. Most people try to tell me everything they know. Big mistake. What's the one thing you want me talking about after you leave the room?",
    teamProduct: {
      items: [
        "A completed pitch",
        "Your Venture Points offer"
      ]
    }
  },
  {
    n: 12, phase: "Communicate", week: 6, title: "The Evokation",
    superpower: "Deep Collaborator", skills: ["Relationship Management", "Courage"],
    individual: null,
    discussionPrompt: "I've enjoyed watching you build this. But here's something I've learned after a lot of years...this presentation isn't really the finish line. It's just proof that you're capable of more than you knew six weeks ago. So what's the first thing you're going to build after this?",
    teamProduct: {
      items: [
        "Your team's live Evokation presentation: the challenge you identified, your innovation and prototype, your pitch, your Venture Points offer / investment case, and your vision for the future"
      ]
    }
  }
];
