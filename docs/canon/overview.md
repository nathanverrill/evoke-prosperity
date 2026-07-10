# EVOKE Prosperity Platform

## Product Design & Experience Specification

---

# 1. Vision

EVOKE Prosperity is a mission-based learning platform that combines:

- Storytelling
- Project-Based Learning
- Entrepreneurship
- Community engagement
- AI coaching
- Team collaboration
- Optional Minecraft exploration
- Instructor feedback

The goal is **not** to complete assignments.

The goal is to help learners become **problem solvers**.

The application should feel somewhere between:

- Duolingo
- GitHub
- Strava
- Notion
- RPG quest log
- NASA Mission Control

Students are continuously progressing through an evolving mission rather than taking isolated classes.

---

# 2. Core Design Principles

## Learning feels like an adventure

Never call something:

- Homework
- Assignment
- Submission

Instead use:

- Mission
- Quest
- Investigation
- Discovery
- Prototype
- Expedition
- Operation

---

## Progress is visible

Everything contributes toward progress.

Even failures.

Students should always feel like they are moving forward.

---

## Multiple paths to success

A learner may earn progress through

- research
- interviews
- building
- experimentation
- collaboration
- reflection
- mentoring

There should never be only one correct path.

---

## AI is optional

The platform functions without AI.

If AI exists:

- AI Coach
- AI feedback
- AI hints

If not:

- instructor feedback
- peer feedback
- stub messages

Nothing depends on AI.

---

# 3. User Journey

```
Login

↓

Home

↓

Current Mission

↓

Story

↓

Real-world Investigation

↓

Evidence Submission

↓

Platform Processing

↓

AI / Instructor Feedback

↓

Reflection

↓

XP

↓

Badge

↓

Next Mission
```

---

# 4. Home Dashboard

The dashboard answers three questions immediately.

## What should I do next?

Current mission

Current quest

Outstanding feedback

---

## How am I progressing?

XP

Level

Current streak

Badges earned

Mission completion

---

## Why does this matter?

Latest story page

Community impact

Team accomplishments

Leaderboard (optional)

---

# 5. Profile

Every learner has a persistent profile.

---

## Identity

Avatar

Preferred name

Organization

School

Class

Current level

XP

Rank

---

## Progress

Current mission

Completed missions

Completed quests

Story progress

Achievements

---

## Skills

Instead of grades, visualize growth.

Examples

Empathy

Research

Communication

Entrepreneurship

Leadership

Creativity

Systems Thinking

Financial Literacy

Innovation

Each skill grows over time.

---

## Portfolio

Every submission becomes part of a permanent portfolio.

Includes

Evidence

Instructor feedback

AI feedback

Photos

Videos

Documents

Minecraft screenshots

Reflection

Certificates

---

# 6. XP System

Everything awards XP.

Examples

Login

+5 XP

Daily streak

+10 XP

Mission completed

+100 XP

Optional quest

+40 XP

Help teammate

+20 XP

Instructor recognition

+50 XP

Community contribution

+75 XP

Reflection journal

+15 XP

Perfect attendance

+25 XP

---

XP is never removed.

No penalties.

---

# 7. Levels

Simple exponential progression.

Example

```
Level 1

0 XP

Level 2

100 XP

Level 3

250 XP

Level 4

450 XP

...

Level 20

Master Problem Solver
```

Levels unlock

Avatar items

Story chapters

Minecraft rewards

Special quests

Recognition

---

# 8. Badges

Badges celebrate accomplishments.

Categories

---

## Story

Explorer

Survivor

Innovator

Builder

Entrepreneur

---

## Learning

Research Expert

Interview Master

Prototype Builder

Critical Thinker

Evidence Collector

---

## Teamwork

Reliable Teammate

Mentor

Leadership

Problem Solver

Consensus Builder

---

## Community

Volunteer

Community Impact

Local Hero

Changemaker

---

## Creativity

Inventor

Designer

Artist

Engineer

---

## Hidden

Secret discoveries

Minecraft secrets

Lore discoveries

Rare events

---

# 9. Streaks

Daily engagement matters.

Examples

Login streak

Reflection streak

Learning streak

Mission streak

Reading streak

Community streak

---

Streaks should never punish learners.

Missing a day simply pauses progress.

No shame messaging.

---

# 10. Missions

A mission contains

Story

Objectives

Resources

Evidence

Reflection

Feedback

Rewards

---

Mission states

Locked

Available

Active

Submitted

Processing

Needs Revision

Completed

Mastered

---

# 11. Quests

Smaller optional activities.

Examples

Interview someone

Visit local business

Watch documentary

Read article

Minecraft challenge

Prototype idea

Community observation

Photograph evidence

Volunteer

---

Quests provide

XP

Badges

Lore

Unlockables

---

# 12. Side Quests

Completely optional.

Minecraft

Robotics

Programming

Photography

Business

Public speaking

Maker challenges

Science experiments

---

Side quests never block mission progress.

---

# 13. Teams

Students may work individually or collaboratively.

A team has

Name

Logo

Members

Shared XP

Projects

Achievements

Team timeline

---

# 14. Team Profile

Displays

Members

Current mission

XP

Badges

Team streak

Contribution graph

Recent accomplishments

Shared files

Instructor comments

---

# 15. Team Accomplishments

Examples

Completed first mission

Interviewed 20 stakeholders

Built prototype

Won community award

Perfect collaboration

Helped another team

Completed Minecraft expedition

Published solution

---

Displayed as timeline cards.

---

# 16. Team Roles

Optional

Leader

Researcher

Builder

Designer

Presenter

Recorder

Community Liaison

Developer

Roles are flexible.

---

# 17. Event-Based Architecture

Everything becomes an event.

Instead of

```
Update database
```

Think

```
Something happened.
```

Examples

EvidenceSubmitted

MissionStarted

MissionCompleted

BadgeAwarded

LevelUp

XPGranted

QuestCompleted

FeedbackGenerated

TeacherReviewed

TeamCreated

TeamJoined

ReflectionAdded

MinecraftRewardUnlocked

NotificationCreated

---

Workers independently react.

Example

```
EvidenceSubmitted

↓

PDF Worker

↓

Text Extraction Worker

↓

AI Worker

↓

Feedback Event

↓

Timeline Worker

↓

Notification Worker

↓

Portfolio Worker

↓

Search Worker

```

Each worker is independent.

No worker directly calls another.

---

# 18. Timeline

Every learner has a living timeline.

Example

Mission Started

↓

Evidence Uploaded

↓

AI Feedback

↓

Teacher Feedback

↓

Revision

↓

Badge Earned

↓

Mission Complete

↓

Level Up

↓

Unlocked Story Chapter

---

Timeline becomes the learner's journey.

---

# 19. Notifications

Types

Mission available

Feedback received

Badge earned

Level up

Team invitation

Instructor announcement

Quest unlocked

Minecraft reward available

---

Notifications are events.

Never business logic.

---

# 20. Rewards

Rewards should feel meaningful.

Examples

XP

Badges

Avatar items

Minecraft cosmetics

Story pages

Concept art

Lore

Certificates

Special missions

---

# 21. Minecraft Integration

Optional.

Minecraft never blocks learning.

Possible rewards

New area unlocked

Decoration pack

NPC interaction

Lore collectible

Treasure

Hidden story

Exploration badge

Screenshots can become evidence.

---

# 22. Instructor Experience

Instructor sees

Mission status

Student progress

Team progress

Pending reviews

Analytics

Engagement

Reflection quality

Submission history

---

Instructor actions create events.

Review submitted

↓

InsightPublished

↓

Timeline updated

↓

Notification sent

↓

Portfolio updated

---

# 23. AI Coach

Optional.

Provides

Encouragement

Reflection prompts

Questions

Suggestions

Celebration

Never grades.

Never replaces instructors.

Always identified as AI.

---

# 24. Portfolio

Permanent learner showcase.

Contains

Completed missions

Evidence

Badges

Skills

Reflections

Projects

Community work

Certificates

Team contributions

Growth timeline

Can eventually become exportable as a professional portfolio.

---

# 25. Search

Search across

Missions

Lore

Resources

Evidence

Reflections

Feedback

Badges

Teams

Community projects

Portfolio

Supports semantic and keyword search.

---

# 26. Future Extensions

Potential additions include:

- Seasonal challenges and global events
- Organization- or school-specific campaigns
- Cross-school collaborations
- Mentor and alumni network
- Community partner projects
- Volunteer hour tracking
- Hackathons and innovation sprints
- Entrepreneurship competitions
- Grant and scholarship opportunities
- AI-generated personalized learning paths
- Public impact dashboards
- Mobile companion application
- Offline-first deployments for low-connectivity environments
- Integration with LMS platforms (e.g., Brightspace, Moodle, Canvas)
- Open API for third-party mission packs and custom content

---

# 27. Guiding Philosophy

The platform should never feel like a traditional LMS.

Students are not completing assignments—they are embarking on missions, building evidence of their growth, collaborating with others, and creating real-world impact. Every interaction should reinforce progress, curiosity, and purpose.

By combining narrative, gamification, project-based learning, optional AI assistance, and an event-driven architecture, EVOKE Prosperity transforms a sequence of coursework into a persistent journey where learners grow as innovators, teammates, and community problem solvers.
