lightspace api lms July 2026

It sounds like you are referring to the Brightspace LMS by D2L. "Lightspace" is a very common misnomer, and D2L's official API documentation for this month is explicitly titled "Brightspace API Reference — Developer Platform (July 2026)".

If you are working with the Brightspace API for the July 2026 release cycle, here is a breakdown of the architectural standards and the latest platform updates.

Brightspace API Architecture
The Brightspace developer platform is built on modern web service standards, allowing for tightly integrated applications and independent operations:

REST and JSON: All routes use RESTful API conventions over HTTP/HTTPS, utilizing standard JSON data structures.

Authentication: The platform relies heavily on the industry-standard OAuth 2.0 Authorization Code Grant workflow. This ensures that every API call is made within the precise permissions context of the logged-in user. Legacy ID-Key authentication is still supported for older integrations but is being actively phased out.

Versioning: API endpoints are highly versioned (e.g., Learning Environment version 1.96 or Learning Platform version 1.62). Critical note for 2026: Any API contracts introduced before Learning Suite 20.24 are officially obsolete and unsupported as of this year.

July 2026 Release Highlights
The continuous delivery cycle for July 2026 introduces several administrative and workflow enhancements to the API:

User and Enrollment Management
Enrollment History: A new action has been added to retrieve a specific user's complete enrollment history log entries.

Password Provisioning: The user creation JSON structure now includes a PasswordData property, allowing administrators to set an initial password when creating a user via the API.

Batch Operations: New actions support the creation of multiple new users and the updating of enrollments in batch requests.

Course Administration
Sub-Organization Logs: Sub-organization administrators can now use the CourseCopyLogs API to securely view course copy history within their specific organizational unit.

Grade Schemes: New actions allow developers to programmatically create and delete grade schemes.

Intelligent Agents
Precision Scheduling: Properties have been added to the schedule data JSON block, enabling developers to define a precise time of day for scheduled Intelligent Agent runs.

(Note: If you were actually searching for "Lightspace" in the context of Lightspace Technologies' AR headsets or the interactive projection floors from the 2000s, those are entirely separate technologies and do not function as Learning Management Systems.)

I'm building a game app that will use t -- thehe brightspace api as the backend. Evoke Prosperity the overall the transmedia experience includes a web app for EVOKE, an AI (powered with OpenWebUI that has a lore rag etc) for a chat bot, and other ai interactions, Minecraft, and a utility bridge application to connect brightspace id with minecraft id, and associate brightspace accomplishments / badges with things earned in Minecraft.

This sounds like an incredible transmedia architecture. Tying a narrative-driven Minecraft experience to an LMS via a lore-backed OpenWebUI chatbot is a fantastic way to handle game-based learning.

To build your utility bridge application, you will be relying heavily on the Brightspace Award Service (BAS) API and the Learning Platform (LP) API.

Here is the architectural blueprint for connecting Brightspace to Minecraft using the July 2026 API standards.

1. Identity Bridging: Brightspace ID ↔ Minecraft ID
   To link the two accounts, your bridge app will act as an OAuth 2.0 client. You cannot securely map a Brightspace ID just by asking the student for their username — you need them to authenticate.

The Handshake: Have the user log into your bridge app using Brightspace OAuth 2.0.

Get the Brightspace ID: Once authenticated, call the "WhoAmI" endpoint using their access token:
GET /d2l/api/lp/{version}/users/whoami
This returns their internal Brightspace UserId (e.g., 123456).

The Minecraft Link: Have the user authenticate via Microsoft/Xbox to retrieve their Minecraft UUID.

The Bridge Database: Store the mapping of Brightspace_UserId <--> Minecraft_UUID in your utility bridge's database.

Note: Your API app registration in Brightspace must include the users:_:_ and awards:_:_ scopes.

2. Brightspace to Minecraft: Reading Earned Badges
   If a student earns a specific badge in Brightspace (e.g., passing a quiz on sustainable agriculture), you can use the API to unlock a corresponding item, title, or permission in Minecraft.

To retrieve all badges a user has earned across Brightspace, make a call to the Award Service (BAS):

GET /d2l/api/bas/{version}/issued/users/{userId}/

What it returns: A JSON array of IssuedAward objects. You can filter this list by AwardType (Type 1 is a Badge, Type 2 is a Certificate). Look for specific AwardId numbers that correspond to your Evoke Prosperity milestones, and push those triggers to your Minecraft server via a plugin (like a custom Spigot/Paper plugin) or RCON.

3. Minecraft to Brightspace: Issuing Badges
   When a student accomplishes something in Minecraft (e.g., building a functional redstone water-filtration system), your Minecraft plugin pings your bridge app. The bridge app then tells Brightspace to issue a badge to the student's Brightspace profile.

To issue an award, you must target the specific Brightspace Course (OrgUnit) where the Evoke project lives:

POST /d2l/api/bas/{version}/orgunits/{orgUnitId}/issued/

Payload (JSON):

JSON
{
"AwardId": 8901,
"IssuedToUserId": 123456,
"Criteria": "Completed the Evoke Prosperity Water Filtration Challenge in Minecraft.",
"Evidence": "Minecraft Server Log: UUID 4f4b... successfully triggered the Redstone completion block at coordinates X, Y, Z."
}
By passing the in-game action into the Evidence field, the Brightspace badge becomes a permanent, verifiable record of their Minecraft achievement.

A Quick Note on Service Accounts vs. User Tokens
For the Minecraft-to-Brightspace route (issuing awards), the action is happening asynchronously in the game, meaning the user isn't actively logging into Brightspace at that exact moment. You will need to ensure your bridge app either stores and manages the user's OAuth Refresh Tokens, or uses a Brightspace service account (an API user with instructor-level award permissions) to issue the badges on the student's behalf.

create an architecture diagram

A detailed, dynamic system architecture diagram illustrating the complex transmedia ecosystem for the "Evoke Prosperity" game app, integrating Brightspace LMS, Minecraft, OpenWebUI AI, and the Utility Bridge application. The diagram is organized logically into three main layers: Frontend/User Layer, Application/Bridge Layer, and Platforms/Core Systems Layer, connected by directional arrows (data flow) on a modern, gridded background with a title: "EVOKE PROSPERITY TRANSMEDIA ECOSYSTEM ARCHITECTURE".

The top layer shows the USER / PLAYER interface: (Left) a Player using "Evoke Prosperity Web App" (Laptop/Mobile icon, displaying "Welcome Student", "Missions", "Badges") and "Evoke AI Chatbot" (Chat icon, "Lore RAG & Interactions"). (Right) a Player within the "Minecraft Game Client" (Minecraft Avatar, playing the game).

The middle layer (APPLICATION / BRIDGE) acts as the central hub:
Center: "UTILITY BRIDGE APPLICATION" (Box with components: OAuth 2.0 Auth Server, ID Mapper (Brightspace UserId <-> Minecraft UUID), Event Handler, Award Logic, Bridge Database (Mapped IDs, Logs)). Connects via "RCON/Plugin" to Minecraft Server, "REST API" to Brightspace, and the Bridge DB.
Left: "EVOKE PROSPERITY WEB APP" (App icon, Mission UI, Badge Display, Achievement Sync). Connects via "OAuth/API" to Brightspace and "Bridge API" to Bridge App.
Right: "MINECRAFT SERVER" (Box with components: Custom Plugin (Spigot/Paper), Game Logic, Survival World, Spigot/Paper API). Connects via "RCON/Plugin API" to Bridge App and "Minecraft Protocol" to Minecraft Clients.

The bottom layer (PLATFORMS / CORE SYSTEMS) contains the main backends:
Left: "BRIGHTSPACE LMS (D2L)" (Logo, Box with components: Course (Evoke Prosperity), User Data, Awards Service (BAS), Badges/Certificates, brightspace/api/bas). Brightspace API provides `UserId`, `IssuedAwards`, `CreateAward`.
Center: "BRIDGE DB" (Database icon, Brightspace ID Mapper, MC UUIDs, Achievement Logs, Event History).
Right: "OPENWEBUI (AI)" (Logo, Box with components: AI Chatbot (Transmedia Lore), Lore RAG (Knowledge Base), Vector DB, LLM (e.g., Llama/Mistral)). Lore RAG accesses transmedia knowledge.

Arrows illustrate data flows: OAuth Login flow (User -> Web App -> Brightspace), Achievement sync (Minecraft -> Plugin -> Bridge App -> Brightspace API -> Awards (BAS)), Badge issuance (Brightspace BAS -> API -> Bridge App -> RCON -> Minecraft (Spawn Item/Unlock Title)), Lore chat (User -> AI Chatbot -> OpenWebUI/RAG). The diagram uses clear icons, labeled boxes, thin lines, and legible text within a technical, illustrative style., AI generated, AI generated

make a simpler version. there also is a core EVOKE ID that Brightspace ID and Minecraft ID be associated with.

, AI generated

does the brightspace api have the concept of gropus? could we have a small team of 4 b4 a group modeled in brightspace or do we have to build that out

Yes, the Brightspace API absolutely has a native concept of groups. You do not need to build out your own custom grouping logic or database tables for this; you can model your 4-person teams directly within Brightspace and use the API to read, write, and manage them.  
Brightspace API - D2L

In Brightspace, the architecture for groups relies on a parent-child hierarchy: Group Categories and Groups.

Here is how you would model and build your teams using the Brightspace Learning Platform (LP) API.

1. The Data Model
   Before you assign a team of 4, you have to understand where they live in the Brightspace structure.

OrgUnitId: Every course or shell in Brightspace has a unique ID. Groups must be attached to an OrgUnit.

Group Category: This is the container for the teams (e.g., "Evoke Prosperity Build Teams"). It defines the rules for the groups inside it.

Group: The actual team (e.g., "Team Alpha").

Enrollment: The specific user IDs assigned to that group.

2. API Execution Steps
   To programmatically generate your small teams via the API, your bridge application will follow this sequence:

Step A: Create the Group Category
First, create the container for your teams within the Evoke course.

Endpoint: POST /d2l/api/lp/{version}/{orgUnitId}/groupcategories/

Payload Insight: You will specify rules here, such as EnrollmentStyle (e.g., manual enrollment so your app can dictate who goes where, rather than auto-enrollment).

Step B: Create the Specific Group
Next, create the actual 4-person team under that new category.

Endpoint: POST /d2l/api/lp/{version}/{orgUnitId}/groupcategories/{groupCategoryId}/groups/

Payload Insight: You pass a JSON block with the Name (e.g., "Team 1"), a Code, and a Description.

Step C: Enroll the Users
Finally, add your 4 players to the group. You will need their Brightspace UserIds (which your bridge app will have already mapped, as discussed earlier).

Endpoint: POST /d2l/api/lp/{version}/{orgUnitId}/groupcategories/{groupCategoryId}/groups/{groupId}/enrollments/

Payload Insight: Send { "UserId": <number:D2LID> } for each of the 4 members.

Why this is better than building it yourself:
By keeping the group model native to Brightspace, you instantly unlock the rest of the LMS ecosystem for those 4 users. If the team earns a Brightspace Award (badge), or if you want to restrict a specific Evoke discussion board, dropbox, or content module strictly to that team of 4, Brightspace natively handles all those permissions based on the Group ID.

Note: Make sure your OAuth 2.0 app registration in Brightspace includes the groups:_:_ scopes, otherwise your API calls to create and enroll will be rejected with a 403 Forbidden error.

Gemini is AI and can make mistakes.
