# Researching company context and engineer experience

The calling agent can use its existing file, Git and connected-source tools to
prepare better planning inputs. Layline itself does not fetch repositories,
integrate with a Git hosting service, or maintain an engineer-profile database.
Proactively check for relevant sources accessible for this task before asking the
user where to look. Unavailable sources need not block planning from the user's account.

## Discover repository access first

Start with the current workspace and known company checkout directories. Inspect
Git remotes and READMEs to identify likely company repositories. Discover available
repository connectors and their read/search capabilities; prefer these when they
cover the task. Otherwise, an already authenticated hosting CLI can check a known
repository or list repositories in the identified company organization. Keep
discovery scoped to that company rather than every repository the account can see.

Verify access by actually reading repository metadata and a small source such as
its README or recent commits. A local checkout may work even when remote access
fails; record the revision and coverage you used. A remote URL or authenticated
account alone does not establish access to that repository. Distinguish a denied
read, a missing tool, and an empty search result from the company having no repos.
Use existing access; do not ask the user to paste credentials into the conversation.

When relevant repos are readable, proceed to inspect them and draft team profiles
without requiring the user to enumerate sources first. Briefly report what you
found and use it to ask focused follow-ups. If several companies are plausible,
ask which team is in scope. If access is unavailable or incomplete, explain what
you checked and ask for the missing repository location or team details, then
continue with available evidence. Keep the access findings in the intake notes.

## Understand the company and the work

Read company or product overviews, repository READMEs, architecture notes,
roadmaps, project briefs and current priorities. Establish the product and its
customers, business goals, planning horizon, success measures, and operational
constraints. Separate current plans from historical or aspirational documents.
Record source dates and ask the user to resolve conflicting priorities.

Connect each proposed project to an outcome and company goal. Use this context
to propose comparable value anchors, then agree on one value-per-week scale with
the user. Do not turn a strategic slogan into an invented numeric estimate.
Record deadlines, joint staffing and other unsupported requirements in intake
notes and explain their effect on interpreting the plan.

## Read repositories for evidence of experience

Start with a bounded recent period, such as the last six months, and inspect
representative older work when needed. State the period and repositories covered.
Read source structure, ownership files such as CODEOWNERS, and representative
changes alongside contributor history. For a local checkout, these read-only
commands are useful starting points; substitute the real path and time window:

```bash
git -C /path/to/repo log --since="6 months ago" --format='%h %aI | author: %aN <%aE> | committer: %cN <%cE> | %s' --name-only
git -C /path/to/repo show --stat COMMIT
git -C /path/to/repo show COMMIT -- path/to/relevant/file
```

Review authors, committers and co-authors separately: merging a change does not
necessarily mean writing it. Account for aliases and mailmaps, bots, squash
merges, shared accounts, contractors and former employees. Confirm ambiguous
identity matches before merging profiles. Use pull-request reviews and issue
discussions when available to capture design, debugging, mentoring and review
work that commits alone miss. Git history is incomplete evidence of someone's work.

Summarize systems, languages and domains a person has worked on, with concrete
examples. Do not rank engineers by commit counts, lines changed or activity gaps,
or derive speed multipliers, availability or employment status from those signals.
Ownership files are useful leads but may be stale; expertise does not establish
a hard project commitment. A merged change alone does not establish that a
planning project shipped or how much person-effort it consumed.

## Keep richer profiles in the intake record

For each draft profile, retain the person's name and confirmed aliases, observed
areas of work, examples, source paths or URLs and commit IDs, source dates and
research window, inferred candidate skills, confidence and its basis, and open
questions. Label direct observations, agent inferences and user confirmations
separately. Record relevant experience outside the inspected repositories too.

For example: “Dana authored billing API changes in two cited commits last quarter;
backend and billing familiarity are candidate skills. Current ownership and
availability are unconfirmed.” That supports a focused question rather than an
assumed allocation or a performance rating.

Show the user a concise company summary and draft profiles, then confirm or
correct the facts that affect the plan. Map confirmed skill labels to
`person.defined.skills`, using speed 1 unless the user supplies another multiplier.
Ask for availability after support, on-call and other duties. Keep company context,
profile narrative and provenance in the companion intake JSON; do not invent
extra planner fields or event types. Consult `layline docs show inputs` for the
supported schema and attribution rules. Repository evidence must not be recorded
as a human estimate, approval, commitment or observed-work event by inference.
