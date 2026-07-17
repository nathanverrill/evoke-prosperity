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
    discussionPrompt: "Alright Agents — compare your intel. Where do the stories line up? Where do they clash? That friction is where the truth hides. And be honest with me: what's one assumption you walked in with that just fell apart?",
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
    discussionPrompt: "Time to find out who you are as a crew, Agents. Share your Origin Story or Avatar. What values keep surfacing? What fires your team up? And what does each of you bring to the table?",
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
    discussionPrompt: "Look at everything you dreamed up, Agents. Which ideas connect? What themes keep showing up? Sometimes the magic is smashing two ideas together — which combinations are worth a closer look?",
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
    discussionPrompt: "Everyone pictured 2035 a little differently — that's a good thing, Agents. Compare your visions and find the common thread. That shared future? That's your North Star.",
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
    discussionPrompt: "Let's talk priorities, Agents. Of everything you'd need, what's truly essential to get started — and what can wait? Sort it out together.",
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
    discussionPrompt: "Time to poke holes in your own plan, Agents — better you than an investor, trust me. What feels unrealistic? What costs are you forgetting? Where could you start smaller or share resources?",
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
    discussionPrompt: "Take a breath and look at what you built, Agents. What's working? What still feels half-baked? And what one change would make it noticeably stronger?",
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
    discussionPrompt: "Pull up your 2035 vision, Agents. Does your prototype actually reflect that future? Be straight with each other — what's missing?",
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
    discussionPrompt: "Now see it through your testers' eyes, Agents. What surprised you? What did people get instantly? Where did they get stuck? This feedback is gold — don't defend it, just listen.",
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
    discussionPrompt: "Before you go any further, Agents, make sure you're all building the same thing. Lay it all out — challenge, vision, budget, prototype, what you learned. Surface the disagreements now, not later.",
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
    discussionPrompt: "Here's the big call, Agents: you've got 100 Venture Points. How many will you offer up to attract backers — and why? Keep more and you hold control but do the work yourselves; offer more and you gain support but share the wheel. Decide together.",
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
    discussionPrompt: "This is it, Agents — the Evokation. Anticipate the tough questions before they land, and decide how you'll answer as a team. Cool heads, clear voices. You've got this.",
    teamProduct: {
      items: [
        "Your team's live Evokation presentation: the challenge you identified, your innovation and prototype, your pitch, your Venture Points offer / investment case, and your vision for the future"
      ]
    }
  }
];
