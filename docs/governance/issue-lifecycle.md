# GitHub issue lifecycle

GitHub Issues are the authoritative work queue for ICT Branch Toolkit. Issue bodies, human comments, linked pull requests, project fields, and native relationships form the complete task record. An AI-generated summary never replaces that record.

## Lifecycle

| State | Evidence | Meaning |
| --- | --- | --- |
| Triage | `status:triage` | Outcome, scope, priority, or relationships still need review. |
| Ready | Project Status = Ready and `status:ready` | Acceptance criteria, human gates, dependencies, and milestone are understood. |
| In progress | `status:in-progress`, `ai:in-progress`, or linked branch/task | Work has actually started. A queue acknowledgement alone is not active work. |
| Review | Draft/ready PR and `status:review` | Implementation exists and awaits CI plus human review. |
| Blocked | Native dependency and `status:blocked` | A named issue, decision, credential, or external gate prevents progress. |
| Done | Merged/accepted work and closed issue | Acceptance criteria are verified; documentation and relationships are current. |

Only a maintainer closes milestone work. Codex may create a branch and draft pull request but never merges, deploys, closes milestone work, changes secrets, changes DNS, or approves its own result.

## Comments as tasks

Every human comment is retained as task input.

- Trusted organization owners, members, and repository collaborators automatically receive a read-only Codex assessment unless the first line is `/codex ignore`.
- `/codex assess` explicitly requests the same read-only assessment.
- `/codex implement` authorizes a scoped implementation from `main`, a new `codex/issue-<number>-comment-<id>` branch, and a draft pull request.
- External comments receive an acknowledgement and `needs:maintainer-review`. They cannot trigger paid AI work or repository writes by themselves.
- A materially independent request becomes a new linked issue or sub-issue. A small in-scope correction stays with the current issue or pull request.

The acknowledgement says only that input was recorded. `ai:in-progress`, a workflow run, branch, cloud task, or draft pull request is required before anyone claims that implementation is active.

## Metadata model

Use native GitHub metadata before labels when the native field has the intended meaning.

| Capability | Use |
| --- | --- |
| Assignee | Human accountable for disposition and acceptance. Default maintainer: `KD7CAO`. |
| Issue type | `Bug`, `Feature`, or `Task`. Organization owners manage the available types. |
| Milestone | Release or phase outcome. Phase 1 uses `Phase 1 — Operational Planning Prototype`. |
| Parent/sub-issue | Break a deliverable into independently verifiable tasks. Phase 1 milestones are children of a single Phase 1 tracking issue. |
| Dependency | Use native `blocked by`/`blocking` relationships for execution order. Do not rely on prose alone. |
| Linked PR | Connect implementation evidence to the task. Draft PRs do not close issues automatically. |
| Labels | Automation state, technical domain, human gate, or data restriction. |
| Project fields | Portfolio status, priority, phase, effort, target dates, and AI state across issues and PRs. |

## Recommended organization project

Create an organization Project named **ICT Branch Toolkit Delivery** and enable automatic addition for this repository. Repository Actions tokens do not automatically receive organization Project access, so this is an organization-owner setup step.

Recommended fields:

| Field | Type | Values |
| --- | --- | --- |
| Status | Single select | Triage, Backlog, Ready, In progress, Review, Blocked, Done |
| Priority | Single select | P0 Critical, P1 High, P2 Normal, P3 Low |
| Phase | Single select | P1.0, P1.1, P1.2, P1.3, P1.4, P1.5, P1.6, Phase 2, Phase 3 |
| Effort | Single select | XS, S, M, L, XL |
| AI state | Single select | Not requested, Queued, Assessing, Implementing, Human gate, Review, Complete, Failed |
| Target start | Date | Planned start date |
| Target completion | Date | Planned completion date |
| Iteration | Iteration | Current planning cycle |

Recommended views:

1. **Triage** — open items grouped by Type, filtered to Status = Triage.
2. **Delivery board** — board grouped by Status, sorted by Priority.
3. **Phase roadmap** — roadmap grouped by Phase with target dates.
4. **Human gates** — filtered to `needs:human` or Status = Blocked.
5. **AI work** — filtered to `ai:queued`, `ai:in-progress`, `ai:review`, or `ai:failed`.

## One-time repository setup

After the foundation pull request is merged:

1. Add an Actions secret named `OPENAI_API_KEY`. The Codex GitHub Action uses OpenAI API billing; a ChatGPT subscription does not supply this secret.
2. In repository **Settings → Actions → General**, allow GitHub Actions to create and approve pull requests. The workflow creates draft PRs only and never approves them.
3. Run **Actions → Bootstrap issue management → Run workflow** once. The workflow creates lifecycle labels, the Phase 1 milestone and parent issue, assignees, sub-issue relationships, and sequential dependencies.
4. Create the organization Project and fields above, then configure its built-in auto-add workflow for `repo:Texas-Communications-Unit/ict-branch-toolkit is:issue,pr`.
5. Confirm organization issue types `Bug`, `Feature`, and `Task` are enabled. The issue forms apply those types automatically to new work.

## Failure behavior

- Missing `OPENAI_API_KEY`: intake continues, but the workflow states that AI execution is paused and never claims work occurred.
- Codex failure: the issue receives `ai:failed` and a workflow-run reference; no merge or deployment occurs.
- No code change: Codex posts its explanation and does not open an empty pull request.
- Pull-request creation disabled: the feature branch remains for recovery, and the failed workflow identifies the blocked step.
- Sensitive-looking path: publication stops before commit/push.
