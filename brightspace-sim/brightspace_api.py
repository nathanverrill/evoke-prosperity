"""
Brightspace LMS Simulator - Based on D2L Brightspace API (July 2026)

This simulator implements the key Brightspace API endpoints needed for EVOKE Prosperity:
- OAuth 2.0 authentication (login/token endpoints)
- User/Identity endpoints (whoami, get user info)
- Award Service (BAS) for badge management
- Group management (create groups, add users)
- Dropbox submission endpoints
"""

from datetime import datetime, timedelta
import json
import uuid
from typing import Dict, List, Optional, Tuple


class BrightspaceSimulator:
    """In-memory Brightspace LMS simulator for development/testing"""

    def __init__(self):
        # Org unit (course) for Evoke Prosperity
        self.org_unit_id = "1"
        self.org_unit_name = "Evoke Prosperity"

        # Users: dict of user_id -> user_data
        self.users: Dict[str, dict] = {
            "6001": {
                "UserId": 6001,
                "Username": "learner@evoke.local",
                "FirstName": "Demo",
                "LastName": "Learner",
                "Email": "learner@evoke.local",
                "IsActive": True,
                "Role": "learner"
            },
            "6002": {
                "UserId": 6002,
                "Username": "teacher@evoke.local",
                "FirstName": "Demo",
                "LastName": "Teacher",
                "Email": "teacher@evoke.local",
                "IsActive": True,
                "Role": "instructor"
            },
        }
        # A realistic class roster for testing the admin roster-import/team-
        # assignment flow (GAPS.md: "no roster import for non-LTI pilots") --
        # 6001/6002 above are the original two demo accounts; these are a
        # separate, larger cohort a real classlist call would actually return.
        _roster = [
            ("Amara", "Okafor"), ("Liam", "Chen"), ("Sofia", "Reyes"), ("Noah", "Patel"),
            ("Zoe", "Nakamura"), ("Ethan", "Osei"), ("Maya", "Kowalski"), ("Diego", "Alvarez"),
            ("Priya", "Sharma"), ("Jackson", "Whitehorse"), ("Layla", "Haddad"), ("Mateo", "Silva"),
            ("Nina", "Petrov"), ("Caleb", "Johnson"), ("Aaliyah", "Brooks"), ("Kenji", "Tanaka"),
            ("Fatima", "Al-Rashid"), ("Owen", "Murphy"), ("Ines", "Dubois"), ("Tyler", "Running Bear"),
            ("Grace", "Kim"), ("Marcus", "Thompson"), ("Elena", "Volkov"), ("Amir", "Hassan"),
        ]
        for i, (first, last) in enumerate(_roster):
            uid = str(6100 + i)
            self.users[uid] = {
                "UserId": int(uid),
                "Username": f"{first.lower().replace(' ', '')}.{last.lower().replace(' ', '').replace('-', '')}@evoke.local",
                "FirstName": first,
                "LastName": last,
                "Email": f"{first.lower().replace(' ', '')}.{last.lower().replace(' ', '').replace('-', '')}@evoke.local",
                "IsActive": True,
                "Role": "learner",
            }

        # Refresh tokens: token -> user_id
        self.refresh_tokens: Dict[str, str] = {}

        # Access tokens: token -> (user_id, expires_at)
        self.access_tokens: Dict[str, Tuple[str, float]] = {}

        # Awards (badges) defined in this org
        self.awards: Dict[str, dict] = {
            "1001": {"AwardId": 1001, "Name": "Common Tier", "Description": "Basic achievement"},
            "1002": {"AwardId": 1002, "Name": "Epic Tier", "Description": "Intermediate achievement"},
            "1003": {"AwardId": 1003, "Name": "Legendary Tier", "Description": "Master achievement"},
        }

        # Issued awards: dict of user_id -> list of award_ids
        self.issued_awards: Dict[str, List[dict]] = {}

        # Group categories: dict of category_id -> category_data
        self.group_categories: Dict[str, dict] = {}

        # Groups: dict of group_id -> group_data
        self.groups: Dict[str, dict] = {}

        # Group enrollments: dict of group_id -> list of user_ids
        self.group_enrollments: Dict[str, List[str]] = {}

        # Dropbox submissions: dict of assignment_id -> list of submission_data
        self.dropbox_submissions: Dict[str, List[dict]] = {}

        # Assignments (dropboxes): dict of assignment_id -> assignment_data.
        # Self-seeds the real 12 Prosperity missions as Brightspace-shaped
        # assignments, per BUILD_PLAN.md's "missions come from the sim"
        # directive -- EVOKE's mission metadata (arc, superpower, PFL domain,
        # brief) rides in CustomFields exactly where a real Brightspace
        # assignment's custom fields would carry it, not in an EVOKE-only
        # table. Source: "Prosperity Campaign Missions -- 07.14.26.docx"
        # (~/evoke-prosperity-files/), the full mission content -- "brief" is
        # a short summary shown on the Hub/Campaign Map; "narrative" and
        # "evidence" carry the actual "Evoke Mission (direct to students)"
        # text (the "Your Mission" framing + Step 1/2/3) and the "Evidence:"
        # checklist, both previously never synced anywhere -- the app only
        # ever showed the one-line brief. lms_assignment_ref-style IDs
        # ("mission-01".."mission-12") are the stable key EVOKE's missions
        # table syncs against.
        self.assignments: Dict[str, dict] = {
            ref: {
                "AssignmentId": ref,
                "Name": name,
                "OrgUnitId": "1",
                "CustomFields": {
                    "Week": week,
                    "Sequence": seq,
                    "Arc": arc,
                    "Superpower": superpower,
                    "PrimarySkill": primary_skill,
                    "SecondarySkill": secondary_skill,
                    "PflDomain": pfl_domain,
                    "Description": brief,
                    "MissionNarrative": narrative.strip(),
                    "EvidenceRequirements": evidence.strip(),
                },
            }
            for ref, week, seq, name, arc, superpower, primary_skill, secondary_skill, pfl_domain, brief, narrative, evidence in [
                ("mission-01", 1, 1, "Follow the Flow", "Explore", "Empathetic Changemaker", "Empathy", "Research & Analysis", "Philanthropy",
                 "Interview at least two stakeholders connected to a real water-access, property-ownership, or financial-exclusion challenge, then name the challenge as a team.",
                 """If you want to understand this challenge—really understand it—you have to step into it. Not as yourself. As them. And stay curious: ask good questions before jumping to conclusions.

Step 1: Walk in Their World
Choose at least two stakeholders connected to the issue your team is exploring. They could include:
- someone directly affected by the issue (peer, family member, community member)
- someone trying to help solve the issue (school counselor, nonprofit or community leader)
- someone connected to the larger system (water utility staff, local officials, fire department personnel, or others relevant to your challenge)
Then talk with them. Listen closely (not just for answers—for emotion, perspective, and patterns). Ask questions like:
- What does this challenge feel like in your life?
- What worries or frustrates you most about it?
- What matters most to you in this situation?
- Where does money or access to resources play a role?
- How are they currently addressing these issues, if at all?
- Where are they falling short?
Listen for understanding. Pay attention to what's not being said. Ask clarifying questions if something feels incomplete or surprising.

Step 2: Find the Friction
Now compare what you've learned as a team:
- Where do their experiences align?
- Where do they clash?
This is where the truth hides. And here's the hard part: what's one assumption you had… that no longer holds up? Say it out loud. Write it down. Own it. That's how real understanding begins.

Step 3: Name the Challenge
Now name the challenge. As a team, create a clear, compelling Challenge Statement that identifies the community issue you want to address through your Evokation (final project) and the financial realities shaping it. Think about:
- the issue that kept surfacing across the people you spoke with
- how the issue affects individuals or the community
- the systems or barriers making the challenge harder to solve
- where money, access, or resources play a role
- what evidence led you to this conclusion""",
                 """- Notes or reflections from at least two stakeholder perspectives, including one assumption you challenged
- A Challenge Statement that identifies the community issue and the financial realities shaping it"""),

                ("mission-02", 1, 2, "Your Prosperity Origin Story", "Explore", "Systems Thinker", "Critical Reflection", "Communication", "Goal Setting",
                 "Connect the challenge you named to your own lived experience and write your Prosperity Origin Story or design your EVOKE Avatar.",
                 """Last time, you named the challenge. Now… bring it closer. Close enough that it stops being "an issue"… and starts being your story. Reflection is not just looking backward. It is understanding what your experiences might mean for the future you want to create.

Step 1: Trace the Connection
Take the challenge you defined in Mission 1. Now ask yourself:
- Where does this show up in my life?
- Have I seen it? Felt it? Been affected by it—even indirectly?
- Who do I know that lives this reality?
- What assumptions or beliefs have shaped the way I see this challenge?
This isn't about being perfect. It's about being honest.

Step 2: Look Forward (This is where power begins)
Where could this path take you?
- What kind of future do you want to build?
- What kind of role do you see yourself in? Problem solver? Entrepreneur? Advocate? Designer? Leader?
This is goal setting. This is about direction. About deciding: if this challenge matters to me… what am I going to do about it?

Step 3: Make It Yours
Now bring it all together. Choose one:
- Write your Prosperity Origin Story: a short personal story about why this challenge matters to you and the future you want to help create. In your story include your first action as the hero of your story.
OR
- Design your EVOKE Avatar: another way of telling your Prosperity Origin Story that reflects what you want to become in the future
This isn't pretend. It's practice. A chance to reflect on who you are becoming—and what role you want to play in the future.""",
                 """- Either your Prosperity Origin Story OR your EVOKE Avatar
- A future direction that relates to the challenge (career, project, hobby, or personal interest)"""),

                ("mission-03", 2, 3, "Dream Beyond the Obvious", "Imagine", "Creative Visionary", "Imagination", "Teamwork", "Philanthropy",
                 "Brainstorm a wide range of imaginative solutions with your team and narrow to 2-3 promising directions on a Dream Map.",
                 """You've felt the challenge. You've made it personal. Now it's time to do something most people never do: imagine beyond what exists.

Step 1: Brainstorm your Dream Map
Your first idea? It's probably safe. Expected. Obvious. Leave it behind. With your team:
- Generate as many ideas as possible.
- Wild ideas. Practical ideas. Impossible ideas.
- Don't judge. Don't filter. Don't stop early.
Capture everything in one shared space—paper, poster board, sticky notes, mind map app, a shared document, digital whiteboard, or whatever helps your team think visually. Because the best ideas? They rarely arrive first.

Step 2: Find the Patterns
Now step back. Look at everything your team created. Ask:
- What ideas seem connected?
- What themes keep showing up?
- Which ideas make each other stronger?
- Are there surprising combinations worth exploring?
Sometimes the most powerful ideas emerge when separate ideas collide.

Step 3: Choose What Pulls You
Now begin to narrow. Look at the ideas your team generated and identify the ones that feel most worth pursuing. Choose ideas that feel bold, surprising, or capable of creating meaningful change. You do not need to choose one final solution yet. But your team should identify 2–3 promising directions worth imagining further in Mission 4.""",
                 """- A collaborative Dream Map showing your team's brainstorming and emerging idea clusters
- 2–3 promising solution directions your team wants to explore further"""),

                ("mission-04", 2, 4, "2035: If We Get This Right", "Imagine", "Creative Visionary", "Vision", "Leadership", "Goal Setting",
                 "Choose one promising idea, imagine it working in 2037, and write a North Star Statement plus a short creative expression of that future.",
                 """You've imagined possibilities. Now choose one. And do something even harder: imagine what happens if you get it right. Real leaders do more than solve today's problem. They imagine a future worth building—and help others see it too.

Step 1: Travel to 2037
Choose one promising solution from your Dream Map. Now imagine it's the year 2037. Your idea? It didn't just survive. It worked. People live differently. The system shifted. Something changed for the better. Take time to picture that future.
- Who is experiencing change?
- What feels different?
- What problem has become smaller—or disappeared?
- What does success actually look like?
- How will your idea be sustained?

Step 2: Find Your North Star
Big visions do not begin with slogans. They begin with clarity. As a team, decide what matters most about the future you want to create. Write down:
- the change you most want to see
- who benefits from that change
- what success would mean in real life
This is your north star—the future your team wants to move toward and help others believe in.

Step 3: Show the World
Create a short creative expression of your team's 2035 vision that reflects the future you want to create and the success you are aiming for. Keep it short: 1–2 lines max. You can express it as:
- a future news headline
- a short message from someone living in that future
- a graphic novel panel
- another short creative expression of your vision""",
                 """- A 1–2 sentence North Star Statement that defines the change your team wants to create and what success would look like
- A short creative expression of your 2035 vision that brings that future to life"""),

                ("mission-05", 3, 5, "What Would It Take—for Real?", "Imagine", "Systems Thinker", "Research & Analysis", "Problem Solving", "Budgeting",
                 "Research what your idea actually needs (people, time, partnerships, tools, money) and build a simple starter budget.",
                 """You've imagined your solution. You've pictured the future it could help create. Now ask the practical question: what would it actually take to get started?

Step 1: Identify What You Need
Every idea—no matter how powerful—needs resources. Break it down:
- People – Who needs to be involved?
- Time – How long might it take to get started?
- Partnerships – Who could support or unlock progress?
- Space & Tools – What physical or digital resources might be needed?
- Money – What costs might need to be covered?
Don't just guess. Use evidence to test your assumptions. Research:
- simple project budget template
- startup or community project checklists
- real prices for people, tools, materials, or services your idea might need
- look up publicly available 990s to understand how existing organizations budget
You're gathering and analyzing information to make smarter estimates and build your starter budget.

Step 2: Sort What Matters Most
You probably can't do everything at once. So, sort what you identified:
- Essential: What do we need to get started?
- Can wait: What would be helpful later, but isn't needed right now?
This is budgeting. It's deciding what's essential to get started.

Step 3: Build a Starter Budget
Find an appropriate project budget template online to estimate the costs of getting your idea started. Include:
- the key expenditures your team prioritized
- rough estimated cost for each item
You do NOT need exact numbers. This is your team's first draft—not the final version.""",
                 """- A simple starter budget showing your prioritized expenditures, rough cost estimates, and brief notes on how you estimated those costs
- A short research snapshot (links, notes, screenshots, or sources) showing how your team gathered information to make smarter estimates"""),

                ("mission-06", 3, 6, "What If We Actually Did This?", "Imagine", "Creative Visionary", "Creativity", "Critical Reflection", "Budgeting",
                 "Stress-test your starter budget, brainstorm possible income sources, and produce an updated, more realistic budget.",
                 """You've imagined the future. You've estimated what it might take to get started. Now think creatively and challenge yourself to imagine: what if we actually do this? Creativity is not just about dreaming up big ideas. It's also about solving real problems when resources are limited. That's how ideas move from possibility to reality.

Step 1: Stress Test the Plan
Take a fresh look at your starter budget. Ask:
- What seems unrealistic?
- What costs might be missing?
- Where could we start smaller, phase the launch, or simplify?
- What resources could be donated, borrowed, shared, or provided by a partner?
Use BillBot, another team, a mentor—or all three—to test your thinking.

Step 2: Build the Other Side of the Budget
Budgets are not just about costs. They are also about resources and income. As a team, brainstorm:
- What sources of income or revenue could help this idea launch?
- What could help it continue over time?
- Could your customers or the people who benefit from it pay for part of it?
- Could sponsorship, fundraising, partnerships, subscriptions, or another model help?
Push past the first idea.

Step 3: Update Your Budget
Use what you learned to improve your starter budget. Update:
- projected expenditures
- sources of income or revenue
- assumptions that changed
- what now feels realistic
This is your stronger next version.""",
                 """- An updated budget showing revised expenditures, changed assumptions, and what now feels most realistic
- A short list of possible sources of income or revenue that could help your solution launch, continue, or grow"""),

                ("mission-07", 4, 7, "Bring It to Life", "Act", "Systems Thinker", "Problem Solving", "Imagination", "Goal Setting",
                 "Choose the first piece of your idea to build and create a first concrete prototype -- physical, visual, digital, or in Minecraft.",
                 """You've imagined a better world. You've created a budget to make it happen. Now, consider: can you bring it to life? Not perfectly. Not completely. But enough to make it real. Complex problems rarely get solved all at once. Strong problem solvers experiment and figure out what to tackle first. This is where you stop imagining—and start building.

Step 1: Choose What to Prototype
Your full idea may be too big to build all at once. So focus. Ask: what problem are we trying to solve first? What is the first version of this that we can create?
- the core idea
- the key interaction
- the simplest way to show how it works
- the most important part of the solution
Start small. A strong first prototype can be simple.

Step 2: Build a Concrete Prototype
Now make it real. Your prototype does not need to be polished. It needs to be clear enough for others to understand. Your prototype can take many forms:
- a physical model
- a visual design or storyboard
- a digital mockup, wireframe, or simulation
- a Minecraft build
Use what you have. Focus on showing the most important part of your idea.

Step 3: Pause and Prepare to Improve
Your first prototype is not the final version. Step back. Look at what you've built. Ask:
- What's working?
- What still feels unfinished?
- What would make this stronger?
You'll keep building in the next mission.""",
                 """- The first version of a concrete prototype showing how your solution could work
- 1-2 sentence explanation of what your team chose to prototype first—and why"""),

                ("mission-08", 4, 8, "Strengthen the Vision", "Act", "Empathetic Changemaker", "Leadership", "Vision", "Budgeting",
                 "Reconnect your first prototype to your original vision and budget, then revise it into a stronger version ready for testing.",
                 """You built the first version. Now ask a new question: does this prototype reflect the future we imagined? A first version proves you can start. Leadership means making thoughtful, responsible choices about what moves forward now—and what can wait.

Step 1: Reconnect to Your Vision
Go back to your 2035 vision. Ask:
- What future were we trying to create?
- What mattered most in that vision?
- Does our prototype reflect that?
- What feels like it is missing?
Strong leaders encourage different perspectives and help their teams to keep the bigger picture in view.

Step 2: Build the Next Version
Now iterate. Use this time to revise, strengthen, simplify, or expand your prototype so it more clearly reflects your vision. As you decide what changes to make, think about alternatives, tradeoffs, and consequences:
- What should stay?
- What should change?
- What matters most right now?
- What can wait?
This is not about perfection. It is about making the next version stronger.

Step 3: Move Forward Together
Take a moment as a team. Look at what you built. Recognize the work each person contributed. Make sure everyone understands what this version is meant to show. Then celebrate the progress. You're ready to put it in the world.""",
                 """- A revised prototype ready for testing that clearly communicates your solution
- A brief explanation of one important choice or tradeoff your team made (what you changed, kept, simplified, or set aside—and why)"""),

                ("mission-09", 5, 9, "Put It in the World", "Act", "Empathetic Changemaker", "Courage", "Empathy", "Investing",
                 "Test your prototype with people beyond your team, gather honest feedback, and decide what matters most to change.",
                 """You built something. Now put it in the world. This is where courage matters. Because real builders do something difficult: they let other people react to unfinished work. And they listen. Even when the feedback is uncomfortable.

Step 1: Test Your Prototype
Put your prototype in front of people beyond your immediate team—classmates, other groups, family members, mentors, teachers, or community members. Ask for honest reactions. Ask open questions like:
- What do you think this does?
- What stands out to you?
- What feels confusing?
- What would make this more useful?
- Would something like this matter to you? Why or why not?
- Does this do more than current solutions provide?
Listen carefully. Do not explain too quickly. Do not defend your idea. Be curious instead.

Step 2: Look Through Their Eyes
As a team, compare what you heard. Ask:
- What surprised us?
- What did people understand right away?
- Where did they struggle?
- What concerns or questions came up?
- What did we learn about the people we hope to serve?
Empathy means seeing your idea through someone else's experience.

Step 3: Decide What Feedback Matters Most
You will hear many opinions. Not all feedback points in the same direction. So decide:
- What feedback feels most important?
- What changes would make the biggest difference?
- What should we improve before moving forward?
This is not about pleasing everyone. It is about learning what matters. And having the courage to change course if needed.""",
                 """- Documented feedback from your prototype testing (notes, quotes, or observations)
- A short team decision about the most important change or insight that will shape what happens next"""),

                ("mission-10", 5, 10, "Worth Backing", "Act", "Deep Collaborator", "Teamwork", "Relationship Management", "Investing",
                 "Align as a team, define 2-3 measurable signs of success, and place your venture on the Low/Medium/High risk spectrum.",
                 """You've imagined, built, tested, and improved your solution. Now decide whether it is truly worth backing. Strong teams do more than build ideas. They make hard decisions—together. They listen, challenge one another respectfully, and align around a shared direction.

Step 1: Get Aligned
You've each experienced this journey a little differently. That's normal. Before you move forward, make sure your team is truly building the same thing. Lay out what you've created:
- your challenge
- your vision
- your budget
- your prototype
- what you learned from testing
Listen to one another. Make space for quieter voices. Surface disagreements early. If your team sees different versions of the project, fix that now.

Step 2: Define Success
Go back to Mission 4. You imagined a future worth building. Now decide how you will recognize progress. Choose 2–3 measurable signs that would show your solution is working. Examples:
- number of users or participants
- revenue or cash flow
- lower costs
- stronger adoption or engagement
- fewer barriers or community uptake

Step 3: The Venture Spectrum: Make Your Case
Every investment involves opportunity—and risk. The classic rule of investing says: the higher the risk, the higher the opportunity for reward. Consider a risk tolerance spectrum:
- LOW RISK: Easier to launch. Fewer resources required. Smaller or steadier impact.
- MEDIUM RISK: Significant resources required to execute. 50/50 chance of success. Possible impact is impressive and widespread.
- HIGH RISK: Massive resources required to execute. Smaller likelihood of success. Possible impact could change the world.
As a team, decide: where does your solution belong? Your goal is not unanimous agreement without discussion—it is shared commitment after honest conversation. Ask Bi11Bot for help thinking through tradeoffs: opportunity, uncertainty, resources required, possible impact, individual risk tolerance. Complete this sentence: Our solution is worth backing because ____________________.""",
                 """- 2–3 measurable indicators of success
- Show where your venture fits (Low Risk, Medium Risk, High Risk) and a one-sentence investment case"""),

                ("mission-11", 6, 11, "Craft Your Pitch", "Communicate", "Deep Collaborator", "Communication", "Creativity", "Investing",
                 "Decide how many of your 100 Venture Points to offer for outside support, then build and design your pitch.",
                 """Your team decided your solution is worth backing. Now prove it to others. A strong idea is not enough. People need to understand it. Believe in it. Want to support it. Strong communicators do more than speak. They make ideas clear, memorable, and meaningful for other people.

Step 1: The Venture Points Challenge
Every venture needs support. Your team has 100 Venture Points representing the total value of the venture. The amount of points each person has corresponds to their power in the venture — if you have 60 Venture Points and are voting on a decision, you get 60 votes. Keeping your points means you maintain control of your venture, but do all the work yourselves. Offering your points means you bring in additional resources (time, money, expertise) to support your venture, but you share the control. Now decide: how many Venture Points are you willing to offer to attract support? This is not exact finance — it is strategic thinking. For example:
- Keep 90 / Offer 10 → high confidence, low outside dependence: you maintain control over decisions, but lose outside support.
- Keep 60 / Offer 40 → moderate dependence, shared support: you maintain majority control over decisions, but increase outside support to grow the venture.
- Keep 30 / Offer 70 → higher need, bigger outside investment: you offer up majority control because you believe so strongly in your vision, but need significant support to execute your plans.
Your choice should match your venture's risk profile — LOW RISK ventures may offer fewer points, MEDIUM RISK a moderate share, HIGH RISK more (the need is higher, but so is the potential upside). Complete this sentence: We are offering ____ Venture Points because ____________________. This becomes part of your pitch.

Step 2: Build Your Pitch
Now craft your message. Your job is to make someone believe your solution is worth backing — that means communicating clearly, not just talking. Your pitch should clearly answer:
- What problem are you solving?
- What is your solution and how does your prototype bring it to life?
- Why is it worth backing?
- How much will it cost to develop and launch, and what do those costs consist of?
- What impact or return could it create?
- What support are you asking for?
Keep it concise. Make it memorable.

Step 3: Design the Experience
Communication is more than words — it is also about visuals, delivery, teamwork, and what your audience takes away. Decide:
- who will speak
- what each team member will do
- what you will show
- how you want your audience to remember your idea
Your pitch might include your prototype, props, visuals, a slide deck, a short video, or another creative presentation format. Practice. Strengthen. Have fun.""",
                 """- A completed pitch
- Your Venture Points offer"""),

                ("mission-12", 6, 12, "The Evokation", "Communicate", "Deep Collaborator", "Relationship Management", "Courage", "Investing",
                 "Deliver your team's live Evokation presentation -- challenge, innovation, pitch, Venture Points offer, and a respectful audience Q&A.",
                 """This is your moment. Not to prepare. Not to revise. To stand up and be heard.

Step 1: Deliver Your Evokation
Bring everything together and deliver your pitch. Speak clearly. Speak with purpose. Show your audience why your solution is worth backing. Make eye contact. Read the room. Help your audience feel included in the conversation.

Step 2: Engage the Audience
Strong relationships are built in real time. Listen carefully. Respond thoughtfully. Adapt to the questions and reactions in front of you. Respect different perspectives—even when they challenge your thinking. Look for common ground between your audience's concerns and your team's goals. This is where trust is built. This is where courage shows.""",
                 """Your team's live Evokation presentation, including a respectful audience Q&A exchange:
- the challenge you identified
- your innovation and prototype
- your pitch
- your Venture Points offer / investment case
- your vision for the future you are working toward"""),
            ]
        }

    # ========== OAUTH 2.0 ENDPOINTS ==========

    def login(self, username: str, password: str) -> Tuple[str, str, int]:
        """
        OAuth 2.0 Authorization Code Grant - simplified for dev

        Real flow: /d2l/auth/oauth2/authorize + /d2l/auth/oauth2/token
        Sim flow: Direct token grant

        Returns: (access_token, refresh_token, expires_in_seconds)
        """
        # Find user by username
        user = None
        for uid, u in self.users.items():
            if u["Username"] == username:
                user = u
                break

        if not user:
            return None, None, None

        # Generate tokens
        access_token = str(uuid.uuid4())
        refresh_token = str(uuid.uuid4())
        expires_in = 3600  # 1 hour

        # Store tokens
        self.access_tokens[access_token] = (str(user["UserId"]), datetime.now().timestamp() + expires_in)
        self.refresh_tokens[refresh_token] = str(user["UserId"])

        return access_token, refresh_token, expires_in

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, int]:
        """Refresh an expired access token"""
        if refresh_token not in self.refresh_tokens:
            return None, None

        user_id = self.refresh_tokens[refresh_token]
        access_token = str(uuid.uuid4())
        expires_in = 3600

        self.access_tokens[access_token] = (user_id, datetime.now().timestamp() + expires_in)
        return access_token, expires_in

    def _verify_token(self, access_token: str) -> Optional[str]:
        """Verify access token and return user_id, or None if invalid"""
        if access_token not in self.access_tokens:
            return None

        user_id, expires_at = self.access_tokens[access_token]
        if datetime.now().timestamp() > expires_at:
            del self.access_tokens[access_token]
            return None

        return user_id

    # ========== IDENTITY / USER ENDPOINTS ==========

    def whoami(self, access_token: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/users/whoami
        Returns the current user's ID and details
        """
        user_id = self._verify_token(access_token)
        if not user_id:
            return None

        return self.users.get(user_id)

    def get_user(self, access_token: str, user_id: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/users/{user_id}
        Returns user details
        """
        if not self._verify_token(access_token):
            return None

        return self.users.get(user_id)

    # ========== AWARD SERVICE (BAS) ENDPOINTS ==========

    def get_issued_awards(self, access_token: str, user_id: str) -> Optional[List[dict]]:
        """
        GET /d2l/api/bas/1.62/issued/users/{user_id}/
        Returns all badges earned by this user
        """
        if not self._verify_token(access_token):
            return None

        awarded = []
        if user_id in self.issued_awards:
            for award_data in self.issued_awards[user_id]:
                awarded.append({
                    "AwardId": award_data["AwardId"],
                    "AwardName": award_data["AwardName"],
                    "IssuedDate": award_data["IssuedDate"],
                    "Evidence": award_data.get("Evidence", ""),
                    "Criteria": award_data.get("Criteria", "")
                })

        return awarded

    def issue_award(self, access_token: str, user_id: str, award_id: str,
                   criteria: str = "", evidence: str = "") -> bool:
        """
        POST /d2l/api/bas/1.62/orgunits/{orgUnitId}/issued/
        Issues a badge to a user

        Payload:
        {
            "AwardId": 1002,
            "IssuedToUserId": 6001,
            "Criteria": "Completed Mission 1",
            "Evidence": "Submission ID: xyz"
        }
        """
        if not self._verify_token(access_token):
            return False

        if award_id not in self.awards:
            return False

        # Check if already issued (no duplicates)
        if user_id in self.issued_awards:
            for issued in self.issued_awards[user_id]:
                if issued["AwardId"] == award_id:
                    return False  # Already issued

        # Issue the award
        if user_id not in self.issued_awards:
            self.issued_awards[user_id] = []

        self.issued_awards[user_id].append({
            "AwardId": award_id,
            "AwardName": self.awards[award_id]["Name"],
            "IssuedDate": datetime.now().isoformat(),
            "Criteria": criteria,
            "Evidence": evidence
        })

        return True

    # ========== GROUP MANAGEMENT ENDPOINTS ==========

    def create_group_category(self, access_token: str, name: str,
                            description: str = "") -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/
        Creates a group category (e.g., "Evoke Prosperity Teams")

        Payload:
        {
            "Name": "Evoke Teams",
            "Description": "4-person venture teams",
            "EnrollmentStyle": 1  # Manual enrollment
        }
        """
        if not self._verify_token(access_token):
            return None

        category_id = str(uuid.uuid4())
        self.group_categories[category_id] = {
            "GroupCategoryId": category_id,
            "Name": name,
            "Description": description,
            "OrgUnitId": self.org_unit_id,
            "CreatedDate": datetime.now().isoformat()
        }

        return category_id

    def create_group(self, access_token: str, category_id: str,
                    name: str, code: str = "", description: str = "") -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{groupCategoryId}/groups/
        Creates a group (e.g., "Team Alpha")

        Payload:
        {
            "Name": "Team Alpha",
            "Code": "TEAM_A",
            "Description": "Venture team"
        }
        """
        if not self._verify_token(access_token):
            return None

        if category_id not in self.group_categories:
            return None

        group_id = str(uuid.uuid4())
        self.groups[group_id] = {
            "GroupId": group_id,
            "GroupCategoryId": category_id,
            "Name": name,
            "Code": code,
            "Description": description,
            "OrgUnitId": self.org_unit_id,
            "CreatedDate": datetime.now().isoformat()
        }
        self.group_enrollments[group_id] = []

        return group_id

    def enroll_user_in_group(self, access_token: str, group_id: str,
                            user_id: str) -> bool:
        """
        POST /d2l/api/lp/1.96/{orgUnitId}/groupcategories/{groupCategoryId}/groups/{groupId}/enrollments/
        Adds a user to a group

        Payload:
        {
            "UserId": 6001
        }
        """
        if not self._verify_token(access_token):
            return False

        if group_id not in self.groups:
            return False

        if user_id not in self.group_enrollments[group_id]:
            self.group_enrollments[group_id].append(user_id)

        return True

    def get_group(self, access_token: str, group_id: str) -> Optional[dict]:
        """
        GET /d2l/api/lp/1.96/groups/{groupId}/
        Returns group details with members
        """
        if not self._verify_token(access_token):
            return None

        if group_id not in self.groups:
            return None

        group = self.groups[group_id].copy()
        group["Members"] = [
            self.users.get(uid, {"UserId": uid})
            for uid in self.group_enrollments.get(group_id, [])
        ]

        return group

    # ========== DROPBOX (ASSIGNMENT) ENDPOINTS ==========

    def submit_to_dropbox(self, access_token: str, assignment_id: str,
                         user_id: str, file_name: str, file_content: bytes) -> Optional[str]:
        """
        POST /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
        Submits a file to an assignment dropbox

        Returns: submission_id
        """
        if not self._verify_token(access_token):
            return None

        if assignment_id not in self.assignments:
            return None

        submission_id = str(uuid.uuid4())
        submission = {
            "SubmissionId": submission_id,
            "UserId": user_id,
            "AssignmentId": assignment_id,
            "FileName": file_name,
            "FileSize": len(file_content),
            "SubmittedDate": datetime.now().isoformat(),
            "Status": "submitted"
        }

        if assignment_id not in self.dropbox_submissions:
            self.dropbox_submissions[assignment_id] = []

        self.dropbox_submissions[assignment_id].append(submission)

        return submission_id

    def get_submissions_for_assignment(self, access_token: str,
                                      assignment_id: str) -> Optional[List[dict]]:
        """
        GET /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions
        Returns all submissions for an assignment
        """
        if not self._verify_token(access_token):
            return None

        if assignment_id not in self.dropbox_submissions:
            return []

        return self.dropbox_submissions[assignment_id]

    # ========== GRADING ENDPOINTS ==========

    def grade_submission(self, access_token: str, assignment_id: str,
                        submission_id: str, grade: int,
                        feedback: str = "") -> Optional[dict]:
        """
        PUT /d2l/api/lp/1.96/dropbox/{assignmentId}/submissions/{submissionId}/grade
        Grades a submission (called by teacher). Returns the graded
        submission dict (so the caller can push a grading webhook back to
        EVOKE with the UserId) rather than a bare bool.
        """
        if not self._verify_token(access_token):
            return None

        if assignment_id not in self.dropbox_submissions:
            return None

        for submission in self.dropbox_submissions[assignment_id]:
            if submission["SubmissionId"] == submission_id:
                submission["Status"] = "graded"
                submission["Grade"] = grade
                submission["Feedback"] = feedback
                submission["GradedDate"] = datetime.now().isoformat()
                return submission

        return None

    # ========== UTILITY METHODS ==========

    def get_all_assignments(self) -> List[dict]:
        """Returns all assignments (missions) -- what EVOKE's startup sync
        pulls to build its missions table cache."""
        return list(self.assignments.values())

    def get_all_users(self) -> List[dict]:
        """Returns all users (for admin/testing)"""
        return list(self.users.values())

    def get_classlist(self, org_unit_id: str) -> List[dict]:
        """Real D2L shape for GET /d2l/api/le/(version)/(orgUnitId)/classlist/
        -- every learner enrolled in the org unit (course). Doesn't model
        per-course enrollment (this sim only has one org unit), so it's
        every learner-role user regardless of org_unit_id, matching how the
        rest of this simulator treats org_unit_id as a formality."""
        return [
            {
                "Identifier": str(u["UserId"]),
                "ProfileIdentifier": str(u["UserId"]),
                "DisplayName": f'{u["FirstName"]} {u["LastName"]}',
                "Username": u["Username"],
                "OrgDefinedId": str(u["UserId"]),
                "Email": u["Email"],
            }
            for u in self.users.values()
            if u["Role"] == "learner"
        ]

    def get_all_groups(self) -> List[dict]:
        """Returns all groups (for admin/testing)"""
        result = []
        for group_id, group_data in self.groups.items():
            group = group_data.copy()
            group["Members"] = [
                self.users.get(uid)
                for uid in self.group_enrollments.get(group_id, [])
            ]
            result.append(group)
        return result

    def reset(self):
        """Reset simulator to initial state (for testing)"""
        self.__init__()
