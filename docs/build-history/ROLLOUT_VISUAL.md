# EVOKE Prosperity - Visual Rollout Timeline & Feature Matrix

## Timeline Overview (6 Month Path to Production)

```
QUARTER 1 (Weeks 1-12)
├─ Phase 1: XP/Levels/Badges ████████████ (5 weeks)
├─ Phase 2: Timeline/Portfolio ████████████ (5 weeks)  [starts week 6]
├─ Phase 3: Teams ████████ (3 weeks)  [parallel with Phase 2]
└─ Phase 4: Instructor ████████ (3 weeks)  [parallel with Phase 2-3]

QUARTER 2 (Weeks 13-24)
├─ Phase 5: Story Integration ████████ (3 weeks)
├─ Phase 6: Real LMS ███████████ (5 weeks)  [starts week 8]
├─ Phase 7: Streaks ████████ (2 weeks)
├─ Phase 8: Search ████████ (2 weeks)
└─ Phase 9: Polished UI ██████████████ (6 weeks)  [starts week 18]

QUARTER 3 (Weeks 25-30)
├─ Phase 10: Scaling/Ops ████████ (4 weeks)
└─ Phase 11: Content Authoring █████████ (3 weeks)  [overlaps]

PHASE 12: Community (Optional, after Phase 1)
```

---

## Cumulative Feature Completeness

```
Week 5:   ████░░░░░░░░░░░░░░░░ 20% (XP basics)
Week 10:  ████████░░░░░░░░░░░░ 40% (Timeline + Teams started)
Week 15:  ████████████░░░░░░░░ 60% (Story, real LMS)
Week 21:  ████████████████░░░░ 80% (Polished UI starts)
Week 30:  ██████████████████░░ 90% (Scaling + ops)
Week 32:  ████████████████████ 100% (Production ready)
```

---

## Feature Dependency Matrix

```
                    Phase 1   Phase 2   Phase 3   Phase 4   Phase 5   Phase 6   Phase 7   Phase 8   Phase 9   Phase 10  Phase 11
                    XP/L/B    Timeline  Teams     Instr.    Story     LMS       Streaks   Search    Polish    Scaling   Content
            ┌────────────────────────────────────────────────────────────────────────────────────────────────────────────
MVP         │   ✓         ✓         ✓         ✓         ─         Sim       ─         ─         Wireframe ─         ─
Phase 1     │   ✓→✓       →         →         ─         ─         ─         ↓         ─         ─         ─         ─
Phase 2     │   ←         ✓→✓       ─         ↓         ─         ─         ─         ↓         ─         ─         ─
Phase 3     │   ←         ←         ✓→✓       ─         ─         ─         ─         ─         ─         ─         ─
Phase 4     │   ←         ←         ─         ✓→✓       ─         ←Sim      ─         ─         ─         ─         ─
Phase 5     │   ←         ─         ─         ─         ✓→✓       ─         ─         ─         ─         ─         ─
Phase 6     │   ─         ─         ─         ←         ─         Sim→✓     ─         ─         ─         ─         ─
Phase 7     │   ←         ─         ─         ─         ─         ─         ✓→✓       ─         ─         ─         ─
Phase 8     │   ─         ←         ─         ─         ─         ─         ─         ✓→✓       ─         ─         ─
Phase 9     │   ←         ←         ←         ←         ←         ←         ←         ←         ✓→✓       ─         ─
Phase 10    │   ─         ─         ─         ─         ─         ←         ─         ─         ←         ✓→✓       ─
Phase 11    │   ─         ─         ─         ─         ─         ←         ─         ─         ←         ←         ✓→✓

Legend:    ✓ = complete    → = builds on    ← = feeds into    ↓ = enables    ─ = independent
```

---

## Work Breakdown Structure (Person-Weeks)

```
Phase 1: XP/Levels/Badges              = 5 weeks (1 senior + AI)
├─ XP System                             2 weeks
├─ Levels                                1 week
├─ Superpower Progress                   1 week
└─ Achievement Badges                    2 weeks

Phase 2: Timeline & Portfolio           = 5 weeks
├─ Timeline View                         2 weeks
├─ Profile Page                          2 weeks
├─ Portfolio/Vault                       2 weeks
└─ Reflections                           1 week

Phase 3: Team Collaboration             = 3 weeks
├─ Team Management                       1.5 weeks
├─ Team Submissions                      1 week
├─ Team Timeline/Badges                  1 week
└─ Peer Recognition                      0.5 weeks

Phase 4: Instructor Experience          = 4 weeks
├─ Dashboard                             2 weeks
├─ Feedback Interface                    2 weeks
├─ Student Monitoring                    1 week
└─ Announcements                         0.5 weeks

Phase 5: Story Integration              = 3 weeks
├─ Story Pages/Comic                     2 weeks
├─ NPC Dialogue                          1 week
└─ Minecraft Lore Unlocks                1 week

Phase 6: Real LMS Integration           = 5 weeks
├─ Brightspace LTI 1.3                   3 weeks
├─ Brightspace Submissions               2 weeks
├─ Brightspace Badge Sync                1.5 weeks
└─ Brightspace Grade Sync                1 week

Phase 7: Streaks & Engagement           = 2 weeks
├─ Daily Login Streak                    1.5 weeks
└─ Weekly Challenges                     1 week

Phase 8: Search                         = 2 weeks
├─ Full-Text Search                      2 weeks
└─ Smart Recommendations                 1.5 weeks

Phase 9: Polished UI                    = 6 weeks
├─ Component Library                     2 weeks (+ 1 FE eng)
├─ Page Implementations                  2 weeks (+ 1 FE eng)
├─ API Integration                       1 week (+ 1 FE eng)
└─ Testing & Polish                      1 week

Phase 10: Scaling & Ops                 = 4 weeks
├─ Multi-Org Deployment                  1 week
├─ Monitoring & Observability            2 weeks
├─ Backups & Recovery                    1 week
└─ Performance Optimization              2 weeks

Phase 11: Content Authoring             = 3 weeks
├─ Curriculum Tools                      3 weeks
├─ Resource Library                      2 weeks
└─ LMS-Agnostic Content Packs            6 weeks per campaign

Phase 12: Community & Gamification      = 3 weeks (optional)
├─ Leaderboards                          1.5 weeks
├─ Community Projects                    2 weeks
└─ Mentor Network                        2 weeks

TOTAL CRITICAL PATH: 24 weeks (6 months)
TOTAL WITH OPTIONAL: 30 weeks (7.5 months)
```

---

## Feature Matrix by Learner Persona

### Student / Learner Path
```
Week 1    │ Submit mission evidence
Week 5    │ + See XP and level progress
Week 10   │ + View full timeline of work
Week 15   │ + Read story pages that unlock
Week 21   │ + Use polished mobile-friendly UI
Week 30   │ + Build permanent portfolio
```

### Teacher / Instructor Path
```
Week 1    │ Simulate grading (brightspace-sim)
Week 10   │ View class dashboard and student progress
Week 15   │ Provide rich feedback with rubric
Week 20   │ Sync to real Brightspace gradebook
Week 21   │ Use polished instructor dashboard
Week 30   │ Monitor engagement metrics
```

### School Administrator Path
```
Week 1    │ Run entire stack on one server
Week 5    │ View XP/progress reports
Week 20   │ Connect real Brightspace instance
Week 25   │ Multi-organization configuration
Week 30   │ Monitoring/alerting dashboard
```

### Game Designer Path (Minecraft)
```
Week 1    │ Award items/effects via RCON
Week 5    │ Tier-based reward delivery
Week 15   │ Unlock lore pages in-game
Week 21   │ Use polished Minecraft UI integration
Week 30   │ Analytics on Minecraft engagement
```

---

## Launch Criteria by Phase

### Phase 1 (XP/Levels) - Ready for Beta
- ✓ XP calculated correctly
- ✓ Levels unlock on XP threshold
- ✓ Badges awarded automatically
- ✓ Dashboard shows progress
- ✓ No XP removed (tested)

### Phase 2 (Timeline) - Ready for Pilot
- ✓ All learner activity in timeline
- ✓ Portfolio shows all work
- ✓ Profile page complete
- ✓ Reflections optional but functional
- ✓ OpenSearch indices real-time

### Phase 4 (Instructor) - Ready for Teachers
- ✓ Teacher can see all students
- ✓ Feedback collection working
- ✓ Grades sync option ready
- ✓ Engagement flags working
- ✓ Instructor training docs complete

### Phase 6 (Real LMS) - Ready for Production
- ✓ Brightspace connection stable
- ✓ User provisioning via LTI
- ✓ Submissions to Dropbox
- ✓ Badges appear in Brightspace
- ✓ Tested with real school tenant

### Phase 9 (Polished UI) - Ready for Launch
- ✓ UI matches design mockup
- ✓ Mobile responsive
- ✓ All accessibility standards
- ✓ Performance <500ms P99
- ✓ User testing feedback incorporated

### Phase 10 (Scaling) - Ready for 1000+ Users
- ✓ Multiple orgs run independently
- ✓ Automated monitoring active
- ✓ Disaster recovery tested
- ✓ Uptime SLA tracking
- ✓ Capacity planning done

---

## Risk & Mitigation

| Phase | Risk | Mitigation | Owner |
|-------|------|-----------|-------|
| 1 | XP calculation bugs | Automated testing, sample data | Backend |
| 2 | OpenSearch schema changes | Plan mapping updates | Infra |
| 3 | Team XP sharing conflicts | Clear business rules, test all paths | Product |
| 4 | Instructor adoption slow | Early feedback, training plan | Product |
| 5 | Story content not ready | Plan parallel with phase 2 | Content |
| 6 | Brightspace API changes | Vendor communication, versioning | Backend |
| 7 | Streak calculations off | Edge case testing (timezone, DST) | Backend |
| 8 | Search performance | Load testing, index tuning | Infra |
| 9 | UI doesn't match mockup | Design system spec first | Frontend |
| 10 | Deployment complexity | Runbook-driven, test disaster recovery | Ops |
| 11 | Content authoring UX poor | User research with curriculum team | Product |
| 12 | Leaderboard toxic | Privacy controls, opt-out easy | Product |

---

## Budget Estimate (Person-Months)

```
Senior Engineer (current):   12 months   = $150k/year → $150k for full path
AI Assistant (Claude):       12 months   = Embedded cost (already budgeted)

Optional Additions:
Frontend Engineer (month 21+):  4 months = $50k + benefits
QA Engineer (month 15+):        6 months = $40k + benefits
Content Creator (month 25+):    2 months = $30k (contract)
Narrative Designer (month 5):   2 months = $25k (contract)

TOTAL: $150k base + $245k optional = $395k for full production release
```

---

## Parallel Work Tracks

### Track A: Core Platform (Weeks 1-12)
- Phase 1: XP/Levels/Badges
- Phase 2: Timeline/Portfolio
- Phase 3: Teams
- Phase 4: Instructor Dashboard

### Track B: Narrative & Content (Weeks 1-20)
- Phase 5: Story Integration
- Phase 11 (early): Curriculum Authoring tools
- Narrative Designer starts week 1 (writing story pages)
- QA validates content week 10+

### Track C: Enterprise Integration (Weeks 8-20)
- Phase 6: Real LMS Integration (research week 1, build week 8)
- Brightspace sandbox access + LTI testing

### Track D: Polish & Scale (Weeks 18-30)
- Phase 9: Polished UI (Frontend Engineer joins)
- Phase 10: Scaling & Ops
- Performance optimization starts week 24

### Track E: Community Features (Weeks 25+)
- Phase 12: Leaderboards, community projects
- Lower priority; can slip if needed

---

## Success Metrics by Phase

### Phase 1
- [ ] 100% of missions show XP earned
- [ ] Level progression deterministic
- [ ] 5 achievement badges unlock per user
- [ ] XP preserved across app restarts

### Phase 2
- [ ] 100% of submissions in portfolio
- [ ] Timeline shows 20+ event types
- [ ] Profile viewable by self and teachers
- [ ] Portfolio exportable as PDF

### Phase 3
- [ ] Teams can have 2-4 members
- [ ] Team submissions split XP correctly
- [ ] Team badges award to all members

### Phase 4
- [ ] Teacher sees <3s to load class list (50 students)
- [ ] Feedback submission <2s
- [ ] Engagement report generated weekly

### Phase 5
- [ ] Story pages unlock based on level
- [ ] B1llbot responds in character
- [ ] Minecraft lore items appear in Inventory

### Phase 6
- [ ] LTI launch succeeds 99%+ of time
- [ ] Submissions appear in Dropbox within 1s
- [ ] Badges sync to Brightspace within 5 minutes
- [ ] Grades visible in gradebook

### Phase 7
- [ ] Streaks persist across sessions
- [ ] Missing a day pauses, doesn't punish
- [ ] +10 XP awarded for active streak

### Phase 8
- [ ] Keyword search returns results <500ms
- [ ] Semantic search works for 80%+ queries
- [ ] Recommendations appear on dashboard

### Phase 9
- [ ] Mobile viewport works 100% on features
- [ ] WCAG 2.1 AA compliance
- [ ] Lighthouse score >90
- [ ] User satisfaction >4/5

### Phase 10
- [ ] 99.9% uptime maintained
- [ ] P99 latency <500ms
- [ ] Disaster recovery test succeeds monthly
- [ ] Alerts fire within 5 minutes of incident

### Phase 11
- [ ] Non-technical staff can create mission
- [ ] New campaign deployed <1 hour
- [ ] Resource library has 50+ items

---

## Communication Plan

### Weekly
- Standups (team sync on progress)
- Phase burndown chart

### Bi-weekly
- Stakeholder sync (product, instructors, narrative lead)
- Demo session (show working features)

### Monthly
- Retrospective (what went well, what to improve)
- Roadmap review (adjust based on learnings)

### Quarterly
- Board/leadership update (high-level progress, budget)
- User feedback session (learner + teacher interviews)

---

## Rollout & Launch Strategy

### Phase 1-2 Completion (Week 10)
**Beta Launch to Pilot Cohort**
- 50-100 learners
- One school / classroom
- Feedback: XP/levels feel right? Timeline useful? Portfolio compelling?

### Phase 4 Completion (Week 14)
**Teacher Onboarding**
- Instructor dashboard training
- Feedback workflow walk-through
- Early adopter teachers

### Phase 6 Completion (Week 18)
**Real LMS Integration**
- Switch from simulator to real Brightspace
- Grades flow to gradebook
- Learner accounts synced

### Phase 9 Completion (Week 26)
**Public Launch**
- Polished UI live
- Full feature set (XP, timeline, portfolio, teams, story, LMS)
- Marketing / outreach begins
- Second cohort of students

### Phase 10 Completion (Week 30)
**Production-Ready**
- Monitoring active
- Disaster recovery tested
- Ready to scale to 1000+ users
- Multiple schools deploying

---

## Key Milestones (Month by Month)

```
Month 1 (Week 5):     XP/Levels/Badges launch to team
Month 1.5 (Week 8):   Timeline/Portfolio working
Month 2 (Week 10):    Beta pilot with 50 students
Month 2.5 (Week 12):  Teams collaboration working
Month 3 (Week 14):    Instructor dashboard launch
Month 3.5 (Week 18):  Real Brightspace connection
Month 4 (Week 20):    Story integration complete
Month 4.5 (Week 22):  Search working
Month 5 (Week 26):    Polished UI launch (public beta)
Month 6 (Week 30):    Production-ready, scaling plan active
```

---

## What Happens if Behind Schedule?

**Drop/Defer Priority (in order):**
1. Phase 12 (Community features) - move to Phase 2
2. Phase 11 (Content authoring) - delay 2 weeks
3. Phase 8 (Search) - reduce to keyword-only
4. Phase 5 (Story) - ship with minimal story pages
5. Phase 9 polish - accept "good enough" UI to ship faster

**Never defer:**
- Phase 1-4 (core platform)
- Phase 6 (LMS integration - required for schools)
- Phase 10 (ops/monitoring - required for production)

---

## Version Numbering

```
0.1.0 (Week 5):     Alpha - XP/Levels
0.2.0 (Week 10):    Beta - Timeline/Portfolio
0.3.0 (Week 14):    Beta+ - Instructor Dashboard
0.4.0 (Week 18):    Release Candidate - Real LMS
0.5.0 (Week 22):    Release Candidate+ - Story/Search
1.0.0 (Week 26):    Production - Full Feature Set
1.1.0 (Week 30):    Production+ - Scaling & Ops
```

Each version should be tagged in git, with release notes documenting new features and known issues.

---

## Questions for Stakeholders

Before starting Phase 1, clarify:

1. **Narrative Priority?** Should Phase 5 (Story) start in parallel with Phase 1?
2. **LMS Preference?** Is it definitely Brightspace, or Moodle also needed?
3. **Pilot School?** Which school for first beta (Phase 1-2)?
4. **Teacher Feedback?** Have instructors reviewed Phase 4 feature set?
5. **Curriculum Ready?** Are all 12 missions finalized, or still iterating?
6. **Budget Approved?** Is $395k acceptable for full production path?
7. **Timeline Pressure?** Do we need to ship by specific date (fall 2024, spring 2025)?
8. **Mobile Essential?** Is native mobile app (Phase 9 optional) required day 1?
9. **Analytics?** Do we need to track engagement/completion metrics (Phase 10+)?
10. **Scale Target?** How many students in year 1? (impacts Phase 10 effort)

---

## Conclusion

This roadmap balances **speed-to-value** (ship Phase 1 in 5 weeks) with **sustainability** (proper ops/scaling by week 30). The critical path is ~24 weeks to production-ready, but early phases unlock value much sooner:

- **Week 10:** Platform feels like a real game (XP, levels, timeline)
- **Week 14:** Teachers can use it
- **Week 18:** LMS integration complete
- **Week 26:** Full feature set, public launch
- **Week 30:** Ready to scale

At each gate, gather user feedback and adjust priorities for next phase.
