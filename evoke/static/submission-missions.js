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
        "B1llbot interview notes — one surprising insight, one assumption you challenged, and one question you'd now ask a real community member",
        "Notes from at least two stakeholder perspectives, including one assumption you challenged"
      ]
    },
    discussionPrompt: "Find the Friction — compare what each of you learned. Where do their experiences align? Where do they clash? What's one assumption you had that no longer holds up?",
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
    discussionPrompt: "Team Identity — share your Origin Story or Avatar. What common values emerged? What motivates your team? What strengths does each person bring?",
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
    discussionPrompt: "Find the Patterns — look at everything your team generated. What ideas connect? What themes keep showing up? Which combinations are worth exploring?",
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
    discussionPrompt: "Compare everyone's future visions and find the common themes worth building toward.",
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
    discussionPrompt: "Sort what matters most — which resources are essential to get started, and which can wait?",
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
    discussionPrompt: "Stress-test the plan — what seems unrealistic? What costs might be missing? Where could you start smaller or share resources?",
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
    discussionPrompt: "Pause and prepare to improve — what's working, what still feels unfinished, and what would make it stronger?",
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
    discussionPrompt: "Reconnect to your 2035 vision — does the prototype reflect the future you imagined? What feels like it's missing?",
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
    discussionPrompt: "Look through their eyes — what surprised us? What did people understand right away? Where did they struggle?",
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
    discussionPrompt: "Get aligned — lay out your challenge, vision, budget, prototype, and testing. Make sure you're all building the same thing.",
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
    discussionPrompt: "The Venture Points Challenge — how many of your 100 Venture Points will you offer to attract support, and why?",
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
    discussionPrompt: "Prepare to engage the audience — anticipate their questions and decide how you'll respond thoughtfully as a team.",
    teamProduct: {
      items: [
        "Your team's live Evokation presentation: the challenge you identified, your innovation and prototype, your pitch, your Venture Points offer / investment case, and your vision for the future"
      ]
    }
  }
];
