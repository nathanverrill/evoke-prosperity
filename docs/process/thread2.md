Yes, and I actually think that's the ideal approach for EVOKE.

I'd separate Minecraft users from EVOKE users during development.

Development (you + a few testers)

Run a Fabric server on your Mac, a spare PC, or a small cloud VM.

Your Mac

Docker
├── EVOKE API
├── PostgreSQL
├── OpenWebUI
├── AI Gateway
└── MinIO

Fabric Server
└── EVOKE World

Minecraft Clients
├── You
├── Tester 1
├── Tester 2
└── Tester 3

You don't need Brightspace at all.

Instead, create a simple development authentication system.

/login

↓

Google Login
or

Local Username/Password

↓

EVOKE User

Each user gets an internal ID:

user_123

Your Minecraft plugin only needs to know:

Minecraft UUID

↓

EVOKE User ID

↓

Mission Progress
How do you link a Minecraft account?

Minecraft already gives every player a unique UUID.

Example:

Minecraft UUID

↓

3c8c2d77-a32d-4ef8...

When they join for the first time:

Unknown UUID

↓

Prompt player

↓

Visit

localhost:3000/link

↓

Login

↓

Done

Now your database has

minecraft_uuid

↓

evoke_user_id

↓

student profile

From then on:

Player joins

↓

UUID lookup

↓

Load missions

↓

Load rewards

↓

Load NPC permissions

No usernames.

No passwords inside Minecraft.

Dev Users

Your database might look like:

User Role Brightspace
Nathan Admin No
Alice Tester No
Bob Tester No
Charlie Tester No

Everything works.

No LMS required.

QA

Later you simply add another authentication provider.

Instead of

Local Login

you also support

Brightspace LTI

or

Google

Nothing else changes.

Your user model becomes

Identity

↓

EVOKE User

↓

Minecraft UUID

↓

Mission Progress

The identity provider is almost irrelevant.

Production

Eventually

Student

↓

Brightspace

↓

LTI Launch

↓

EVOKE

↓

EVOKE User

↓

Minecraft UUID

The first time they click "Open Minecraft":

Click

↓

Generate one-time link code

↓

ABCDE7

↓

Minecraft

/link ABCDE7

↓

UUID associated

↓

Done forever

Exactly like Discord account linking.

Multiple Minecraft Servers

This architecture also means you can have multiple worlds.

Development

localhost

↓

QA

qa.evoke.ai

↓

Production

play.evoke.ai

↓

Summer Camp

camp.evoke.ai

Each server reports

Server ID

Player UUID

↓

EVOKE API

The backend knows where the player is.

Small Playtests

This is actually one of the biggest advantages.

You could absolutely host a server for 5–20 testers.

Harwich Playtest

↓

Whitelist

↓

5 students

↓

Real EVOKE backend

↓

Real AI

↓

Real missions

You'd gather analytics before ever touching Brightspace.

Offline Development

You can even fake everything.

Fake Login

↓

Fake Missions

↓

Fake AI

↓

Fake Brightspace

↓

Minecraft

So if you're on an airplane...

...the entire game still works.

My recommendation

I would define four authentication adapters from day one:

interface IdentityProvider {
login();
getUser();
linkMinecraftAccount();
}

Implement them in this order:

LocalIdentityProvider (email/password or magic link) – for development and playtesting.
GoogleIdentityProvider – for external testers who aren't in a Brightspace course.
BrightspaceLTIProvider – for classroom deployments.
MockIdentityProvider – automatically logs you in as a test user for rapid local development.

Because the rest of EVOKE only ever interacts with an EVOKE User, you can switch between these identity providers without changing the mission engine, AI, rewards, or Minecraft integration.

One more idea that fits your vision well: add an Organization layer to the data model.

Organization
├── Local Playtest
├── University of South Carolina Demo
├── Colorado Middle School Pilot
└── Future Customer

         ↓

Courses

         ↓

Students

         ↓

Mission Progress

That lets you run a private playtest server today with a handful of users, then onboard multiple schools later without changing the core architecture. Each organization can have its own worlds, missions, branding, and LMS integration while sharing the same EVOKE platform.

how many test users could i run on that server? if I use an ec2 or google cloud server to host it, what would the cost be? are there any licensing issues?

This is one of the nice things about Minecraft: the server software itself is surprisingly lightweight, especially compared to the AI services you're building around it.

How many players?

For EVOKE, you're not building a 500-player PvP server. You're building an educational exploration world where players are spread out, talking to NPCs, reading the story, and occasionally collaborating.

That means your requirements are much lower.

Concurrent Players Recommended Server
5–10 2 vCPU, 4 GB RAM
10–20 2–4 vCPU, 8 GB RAM
20–50 4 vCPU, 8–16 GB RAM
50–100 8 vCPU, 16–32 GB RAM

For your current EVOKE vision, I'd expect:

Local development: 1–5 players
Internal QA: 5–15 players
Classroom pilot: 15–30 players
Large classroom or camp: 30–50 players

A single well-configured server can comfortably handle that.

AWS EC2 pricing

A few reasonable options (rough order-of-magnitude monthly costs if left running 24/7):

Instance Specs Approx. Monthly
t3.medium 2 vCPU / 4 GB ~$30
t3.large 2 vCPU / 8 GB ~$60
c7i.large 2 vCPU / 4 GB (faster CPU) ~$50–70
c7i.xlarge 4 vCPU / 8 GB ~$90–120

Minecraft tends to benefit more from fast single-core CPU performance than from lots of cores.

For a 20-player EVOKE pilot, I'd probably choose a compute-optimized instance (such as the C-series on AWS) over a memory-heavy one.

Google Cloud

Very similar pricing.

A 2–4 vCPU VM with 8 GB RAM generally lands around:

~$30–70/month depending on machine type and region.

Google's networking and sustained-use discounts can make it attractive if you're already using Google Cloud.

Storage

Minecraft worlds are tiny compared to most applications.

Even a large EVOKE world is likely:

World: 1–5 GB
Mods: <500 MB
Backups: 10–20 GB

Storage cost is essentially negligible.

The expensive part isn't Minecraft

Your biggest cost will likely be:

AI inference (if using paid APIs)
Vector databases (if applicable)
Large language model hosting
Image generation (if you add it)

Minecraft itself is one of the cheaper components.

Licensing

This is where things often confuse people.

Minecraft server software

You can run the official dedicated server software or compatible server software (such as Fabric) without paying a separate server license.

Players

Every player connecting to a Java Edition server must have their own legitimate Java Edition account (today, a Microsoft account that owns Minecraft Java Edition).

So if you have:

20 students

then

20 legitimate Minecraft licenses.

You don't buy a "server license."

Can a school do this?

Yes.

The school doesn't need to buy a server license.

Students simply need licensed Minecraft Java accounts if you're using Java Edition.

Minecraft Education Edition?

I actually would not use Minecraft Education Edition for EVOKE.

Reasons:

Java Edition has a much richer modding ecosystem.
Fabric and Paper have extensive plugin support.
Your custom NPC integration is much easier.
You're already building on Fabric.

Education Edition is great for classroom activities, but it's far more restrictive for the kind of custom transmedia experience you're envisioning.

Suggested deployment strategy

I'd structure it like this:

Development
───────────
Mac Mini / Desktop
5 players

↓

Internal QA
───────────
Small EC2 or Google Cloud VM
10–20 players

↓

Pilot School
────────────
Larger VM
20–40 players

↓

Production
──────────
Dedicated VM(s)
Multiple schools

Because your EVOKE backend is separate from Minecraft, you can even have multiple Minecraft servers (e.g., one per school or cohort) all talking to the same EVOKE platform. The backend distinguishes them by a server_id, allowing shared accounts and progress while keeping worlds isolated if you choose.

One additional consideration: if you ever expect multiple classrooms in different worlds at the same time, it can be cleaner to spin up a separate Minecraft server per cohort rather than trying to put everyone into one huge world. Since each server only costs on the order of tens of dollars per month, the operational simplicity often outweighs the cost, and it gives each class its own resettable environment while still using the same EVOKE backend, AI services, and Brightspace integration.

EVOKE Prosperity Deployment Model

EVOKE Prosperity is a standalone learning platform that integrates with existing Learning Management Systems (LMSs) such as Brightspace but is not dependent on them. Schools can adopt only the components they want, allowing the platform to scale from a single classroom to large institutional deployments.

Core Experience (Always Available)

Every EVOKE deployment includes:

Interactive graphic novel
Real-world missions and evidence submission
AI mentor characters
Student rewards and achievements
Instructor reporting
Optional LMS integration (e.g., Brightspace)
Optional Components

If a school uses Brightspace (or another supported LMS), then:

Students launch EVOKE from the LMS.
Mission completion, grades, badges, and course progress synchronize automatically.
Instructors continue managing courses and grades within the LMS.

If a school does not use an LMS, then:

EVOKE operates independently.
Teachers manage students and view progress directly within EVOKE.
Reports can be exported as needed.

If an organization wants Minecraft, then:

Minecraft becomes an optional side quest experience that complements—but never replaces—the core learning experience.
Students with Minecraft Java Edition can explore the world, interact with AI characters, and unlock optional rewards.
No required coursework depends on Minecraft participation.

If an organization does not use Minecraft, then:

Students experience the complete curriculum through the graphic novel, AI interactions, missions, and evidence submission with no loss of required functionality.
Internet Connectivity

If reliable Internet is available, then:

EVOKE can connect to cloud AI services and synchronize with the organization's LMS in real time.

If Internet connectivity is intermittent, then:

EVOKE continues operating locally.
Student work is stored securely and automatically synchronized with external systems once connectivity is restored.

If there is no Internet connection (for example, in remote schools or humanitarian deployments), then:

EVOKE can be deployed entirely on a local server within the school or community.
Students access EVOKE over the local network.
The graphic novel, missions, AI mentors (using local AI models), evidence submission, and optional local Minecraft server continue to function without Internet access.
If an LMS is not available, EVOKE provides its own student management and reporting capabilities.
A Flexible Platform

This modular approach allows every organization to choose the level of functionality that fits its environment:

Need only the curriculum? Use EVOKE by itself.
Already use Brightspace? Connect EVOKE and synchronize grades and badges.
Want an immersive experience? Enable optional Minecraft side quests.
Operating in low-connectivity or remote environments? Deploy EVOKE locally and continue teaching without relying on Internet access.

By keeping every component optional except the core learning experience, EVOKE can serve universities, K–12 schools, nonprofits, NGOs, and humanitarian programs using the same platform while adapting to each organization's technical capabilities and educational goals.

what about connecting with the minecraft app on a phone, ipad, or xbox?

This is where things get interesting, and it's an architectural decision you'll want to make early.

By default, no.

If you're running a Java Edition Fabric server, then only Minecraft Java Edition clients (Windows, macOS, Linux) can connect.

Device Native Java Support
Windows PC ✅
macOS ✅
Linux ✅
iPad ❌
iPhone ❌
Android ❌
Xbox ❌
PlayStation ❌
Nintendo Switch ❌

However, there is a very popular solution.

Option 1 (Recommended): Java server + Bedrock compatibility

Many communities run a Java server with two compatibility layers:

Geyser – allows Bedrock Edition clients to connect to a Java server.
Floodgate – allows Bedrock players to join without needing a linked Java account.

The architecture looks like this:

            Java Players
                 │
            Fabric Server
                 ▲
         Geyser + Floodgate
                 ▼
      Bedrock Players

(iPad, iPhone, Android,
Xbox, Windows Bedrock)

From the student's perspective:

PC users play Java Edition.
iPad users use Minecraft Bedrock.
Xbox users use Minecraft Bedrock.
Everyone joins the same EVOKE world.

This dramatically lowers the barrier to participation.

Will my Fabric mod still work?

Usually, yes.

Your Fabric NPC mod continues running on the server.

The Bedrock client is simply translated into Java protocol by Geyser.

Because your AI logic lives in the EVOKE backend—not in the client—you generally don't need separate logic for mobile or console players.

Are there limitations?

Yes, a few.

Some Java-only features don't translate perfectly:

Certain custom GUIs
Some advanced modded blocks or items
A few particle and rendering effects
Rare gameplay mechanics

But for an exploration-focused educational experience with NPCs, quests, and chat, Geyser works very well.

What about consoles?

Consoles are the hardest part.

Xbox and Nintendo Switch are designed to connect to Microsoft's featured servers.
Joining a custom Bedrock server may require additional setup depending on the platform and network.
Mobile devices (iPad, iPhone, Android) and Windows Bedrock generally have a much smoother experience connecting to custom servers.

So while console support is possible for some users, I wouldn't market it as the primary experience.

My recommendation for EVOKE

I would define your support levels like this:

Tier 1 (Officially Supported)
Java Edition (Windows, macOS, Linux)

This is your development and testing platform.

Tier 2 (Supported via Geyser)
iPad
iPhone
Android tablets/phones
Windows Bedrock Edition

These are excellent options for classrooms and greatly expand accessibility.

Tier 3 (Best Effort)
Xbox
Nintendo Switch
PlayStation

Possible in some environments, but with more variability in setup and support.

Long-term strategy

Architecturally, I would think of Minecraft as another client of EVOKE:

             EVOKE Platform
                  │
    ┌─────────────┼─────────────┐
    │             │             │

Web App Java Minecraft Bedrock Minecraft
│ │ │
└─────────────┴─────────────┘
Same missions
Same AI
Same rewards

That means a student could:

Read the graphic novel on an iPad.
Explore the optional Minecraft world from the same iPad using Bedrock (if enabled).
Upload evidence from a Chromebook.
Have all of that progress synchronized in EVOKE.

That's a compelling story for schools because it reduces the requirement that every student have a gaming PC while keeping Minecraft as an optional enrichment experience.

and that's an important part of the brief, how we reach as many people as possible

I agree, and I'd elevate that from a technical detail to a core design principle.

Right now, the message is "Minecraft is optional." I think the stronger message is:

EVOKE meets learners where they are.

That applies to devices, connectivity, and institutional technology.

Here's how I'd frame it in the business brief.

Accessibility and Reach

EVOKE Prosperity is designed to maximize access by adapting to each organization's technology, infrastructure, and learning environment. Rather than requiring a specific platform, EVOKE provides multiple ways for students to participate.

If a school uses a Learning Management System (such as Brightspace), then EVOKE integrates with it for authentication, assignments, grades, and badges.

If a school does not use an LMS, then EVOKE operates as a complete standalone learning platform with its own student management and reporting tools.

If reliable Internet is available, then EVOKE can use cloud AI services and synchronize with external systems in real time.

If Internet connectivity is limited or unavailable, then EVOKE can be deployed entirely on a local server, allowing students to continue learning over a local network with synchronization occurring whenever connectivity becomes available—or not at all if external systems are unnecessary.

If students have access to Minecraft, then they can participate in optional immersive side quests that extend the story through exploration, AI characters, and collaborative activities. These experiences are designed as enrichment and are never required to complete the curriculum.

If students do not have access to Minecraft, then they receive the complete EVOKE learning experience through the graphic novel, AI mentors, real-world missions, and evidence submission without any loss of required educational content.

If students use different devices, then EVOKE is designed to support broad accessibility. The core web experience runs in a modern browser on laptops, Chromebooks, tablets, and desktop computers. Where appropriate, optional Minecraft experiences can also be made available across multiple device types, expanding access without making them a requirement.

By separating the core learning experience from optional technologies, EVOKE enables organizations to start with the capabilities they have today and expand over time. This flexible approach supports universities, K–12 schools, nonprofits, NGOs, and humanitarian programs, helping ensure that technology availability never becomes a barrier to participation.

I would add one final principle that becomes part of the product's identity:

No learner is excluded because of technology.

Every major feature should have a graceful fallback:

No LMS → EVOKE manages learners.
No Internet → EVOKE runs locally.
No cloud AI → Use local AI models.
No Minecraft → Complete the experience through the web.
No gaming PC → Use the browser experience, and where Minecraft is offered, support as many compatible devices as practical.

That simple philosophy is something business stakeholders, educators, and NGOs immediately understand, and it clearly communicates that EVOKE is designed for broad accessibility rather than a single technology stack.
