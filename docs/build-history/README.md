# Build history — archived working docs

Working documents from the July 2026 build sprints (Brightspace integration, Minecraft bridge, LTI, ops). **Superseded by [`/BUILD_PLAN.md`](../../BUILD_PLAN.md) and [`/UI_SPEC.md`](../../UI_SPEC.md) at the repo root** — treat everything in this folder as history, not as current spec. Same rule as `docs/legacy/`: useful for context, never cite as the current plan.

## What's here

| Group | Files | What they were |
|---|---|---|
| Original specs | `PHASE_1_SPEC.md`, `BRIGHTSPACE_INTEGRATION_SPEC.md` | The executable specs the July sprint built against. (`BUILD_PROMPT.md`, the original MVP spec, was deleted — its award/collect/RCON rules and acceptance scenario live on in `BUILD_PLAN.md`.) |
| Planning / rollout | `CODING_ROADMAP.md`, `ROLLOUT_PLAN.md`, `ROLLOUT_INDEX.md`, `ROLLOUT_VISUAL.md`, `EXECUTIVE_SUMMARY.md`, `IMMEDIATE_NEXT_STEPS.md` | Sprint planning and stakeholder material. |
| Task/progress logs | `TASK_*_COMPLETE.md`, `TASK_*_SUMMARY.md`, `TASK_*_PLAN.md`, `TASK_*_PROGRESS.md`, `WEEK_*_SUMMARY.md`, `PROGRESS.md`, `PROGRESS_UPDATE.md`, `BUILD_SUMMARY.md`, `COMPLETION_SUMMARY.md`, `PROJECT_COMPLETION_SUMMARY.md` | Per-task completion records from the sprint. Good for "why does this code exist," not for "what should I build." |
| Setup / how-to guides | `SETUP.md`, `DOCKER_SETUP.md`, `QUICKSTART.md`, `QUICKREF.md`, `START_FRESH.md`, `RUN_WEBSITE.md`, `PLAY_AND_TEST_GUIDE.md`, `TESTING_GUIDE.md`, `OPERATIONS.md` | Point-in-time setup instructions. Some predate the compose project rename to `evoke` and the custom Minecraft container — verify commands against the current compose files before trusting them. |
| Minecraft docs | `MINECRAFT_INTEGRATION.md`, `MINECRAFT_LOCAL_SETUP.md`, `MINECRAFT_SETUP_COMPLETE.md` | Written for the `itzg/minecraft-server` image and a local-Java setup, both replaced by the custom container spec in `BUILD_PLAN.md`. |

