# Skills

Each directory in [Job/](../Job/README.md) is optional. The catalog [INDEX](../catalog/INDEX.md) is the menu. An address you do not publish is a role you have not deployed.

Load order for a matched role:

1. [shared/core/SKILL.md](../shared/core/SKILL.md)
2. `Job/<role>/SKILL.md`

Frontmatter `name` must equal the directory name. `description` is a single line. Required sections are Mission, Scope, Required context, Intake and triage, Workflow, Drafting rules, Escalation, Reply policy, Rubric, and Done criteria.

The core skill wins on safety when a role file conflicts with it. Neither file can enable the kill switch, remove a role from `human_only_roles`, or mark a draft as approved.

Unknown recipients use the Hello skill only as an internal routing report when the operator keeps that unknown policy. They are not automatically answered with the Hello template.

Adding a role means a new directory, a catalog row, a route, and a human review of the default policy. The new role stays human-only unless an owner edits the policy in a separate change. The agent does not open that change.
