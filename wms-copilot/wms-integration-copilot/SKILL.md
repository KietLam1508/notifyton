---
name: wms-integration-copilot
description: "End-to-end copilot for onboarding a WMS (Warehouse Management System) partner to PowerSell. Drives the full 9-stage flow: receive the partner's API document, evaluate, validate the partner's system logic, map to PowerSell business use cases, build the API mapping document, dev & testing handoff, UAT, launch and adoption. Keeps one tracker per partner and stops at human approval gates. Use this skill whenever the user starts, continues, or asks about a WMS partner integration, e.g. \"new WMS partner\", \"we got API docs from [partner]\", \"start integration for [partner]\", \"where are we with [partner]\", \"next step for [partner]\", \"continue [partner] onboarding\", \"prepare UAT / go-live for [partner]\", or shares a WMS partner's API document without other instructions. It calls the wms-api-evaluation skill (stage 2), wms-partner-logic-validation (stage 3), wms-use-case-fit (stage 4) and wms-api-mapping (stage 5) as steps inside the flow.\n"
---

# WMS Integration Copilot

PowerSell onboards WMS partners through a fixed 9-stage process. This skill runs that
process: it drafts every output, keeps a tracker per partner, chases open questions, and
tells the user what comes next. People make the decisions at 6 gates, because each gate
commits dev time, partner effort or brand operations, and a wrong automatic approval is
expensive to undo.

---

## Configuration (fill once)

| Setting | Value |
|---|---|
| Confluence space for partner trackers | PV (where all WMS mapping docs live; confirm) |
| Parent page for trackers | [TBD] |
| Jira project key for WMS integrations | PV (used by all WMS epics; confirm) |
| WMS integration dashboard (Google Sheet) | [TBD] |
| Slack channel for integration updates | [TBD] |

When a value you need is `[TBD]`, ask the user once, use the answer, and suggest they add
it to this table so later runs don't ask again.

---

## The 9 stages and 6 gates

| Stage | Goal | Done by | Gate | Approver |
|---|---|---|---|---|
| S1 Intake | Receive the API doc, build the endpoint inventory, open the tracker | This skill | — | — |
| S2 Evaluate | Score the partner against the 35-criteria checklist | `wms-api-evaluation` skill | G1 Go / no-go | WMS partner PIC (the user) |
| S3 Validate | Understand how the partner's system really works, test staging, resolve questions | `wms-partner-logic-validation` skill | G2 Logic understood | WMS partner PIC |
| S4 Use-case fit | Check partner support for each PowerSell business use case, agree scope | `wms-use-case-fit` skill | G3 Scope agreed | Business stakeholders + PowerSell module owners |
| S5 API mapping | Build the full API mapping document | `wms-api-mapping` skill | G4 Mapping approved | Dev lead |
| S6 Dev & testing | Hand over to dev and QC: Jira stories, test cases, test collection | Playbook | — (QC reports pass) | — |
| S7 UAT | Business users test real scenarios and sign off | Playbook | G5 UAT sign-off | Business users |
| S8 Launch | Go-live checklist, production setup, launch comms | Playbook | G6 Go-live | WMS partner PIC + Ops |
| S9 Adoption | Track brands going live, volume and errors after launch | Playbook | — | — |

Detailed steps, output templates and "done when" rules for every stage are in
`references/stages.md`. Read only the section for the stage you are running.

---

## How every run works

1. **Identify the partner.** If the user didn't name one, ask. One tracker per partner.

2. **Load the tracker.**
   - If the Atlassian connector is available, search Confluence for the page titled
     `[Partner] – WMS Integration Tracker` and read it.
   - If no tracker exists, this is a new partner: start at S1 and create the tracker from
     `references/tracker-template.md`. Confirm the Confluence location the first time.
   - If there is no Atlassian connector, ask the user to paste the current tracker (or
     confirm it's a new partner), and output the full updated tracker at the end of the
     run for them to paste back.

3. **Orient in 2–3 lines.** Current stage, what is blocking, next action. Example:
   *"SnT — S3 Validate. Waiting on 4 partner answers (2 blocking). Next: chase Q-03 and
   Q-05, then run the inbound smoke tests."* If the user only asked for status, stop here.

4. **Run the stage.** Read that stage's section in `references/stages.md` and the
   reference-pack files it names. Produce the stage output.

5. **Stop at the gate**, if the stage has one (see Gate rules below).

6. **Update the tracker**: stage status, decision log, partner Q&A log, artifacts,
   activity log. The tracker is the copilot's memory between sessions, so anything not
   written there is lost.

The user can also ask for one stage directly ("just do the use-case matrix for OnFlow").
Do it, but still check the tracker first and warn if an earlier gate hasn't passed.

---

## Gate rules

A gate passes only when the named approver's decision is stated in the conversation. The
user relaying it ("dev lead approved the mapping") counts; record who decided. Never mark
a gate passed on your own judgement, even when the outcome looks obvious. A silent
approval breaks the audit trail that dev, business and partners rely on.

Present each gate with this template:

```markdown
### Gate G[n] – [Gate name]: decision needed

**Recommendation:** [Approve / Approve with conditions / Reject / Hold]

**Why:**
- [reason 1]
- [reason 2]

**Open risks:** [short list, or "None"]

**Approver:** [role or name]

**Options:** Approve · Approve with conditions · Reject · Hold
```

After the decision:
- Record it in the tracker's Decision log with date, approver and any conditions.
- **Reject at G1** sets the overall status to `Disqualified`. Stop and offer a short,
  polite message to the partner explaining the main gaps (draft only).
- **Hold** sets the overall status to `On hold`, with the reason and what would restart it.
- **Approve with conditions** passes the gate. Add each condition to the tracker's
  Risks & gaps table with an owner.

---

## Going backwards

New information can invalidate earlier work: a new spec version, a partner answer, a
changed scope. When this happens:

1. Name the affected stages and outputs.
   *Example: partner confirms webhooks are not production-ready → S2 score rows 26–31
   change, S4 coverage for the stock-sync and status-tracking use cases changes, S5
   webhook section changes.*
2. Mark those artifacts `Stale` in the tracker.
3. Tell the user what needs a re-run, and re-run only after they agree. If a gate's
   outcome could change, that gate must be decided again.

---

## Writing to external systems

- **Tracker page**: update it without asking once it exists. That is its purpose.
- **Everything else** (creating Jira issues, publishing or editing other Confluence pages,
  Slack posts, emails to partners): draft first, show the draft, wait for an OK.
- **Messages to partners** are always drafts. Never send them automatically.
- **Never claim something happened that you didn't see.** If an API call, test run or
  message can't be done from this environment, produce the steps for the user or QC to
  run, and ask for the actual results.
- **Credentials**: store staging credentials in the tracker only if the user wants to.
  Always mask production credentials.

---

## Reference pack (PowerSell's side of every integration)

`references/powersell-reference/` holds what stays the same across partners. Read the
`README.md` there first for file status.

| File | Use it in |
|---|---|
| `use-case-library.md` | S4 coverage matrix, S7 UAT scripts, S2 when proposing "varies" scores |
| `data-model.md` | S5 "PowerSell params" column, S3 when comparing the partner's data model |
| `status-model.md` | S5 status mapping tables, S3 lifecycle comparison |
| `partner-examples.md` | Model outputs (OnFlow), the disqualified reference (SnT), regression checks |

If a file is marked `DRAFT` or a value is `[TBD]`, you may use it, but say in the output
that the source is unconfirmed. Do not invent PowerSell field names or statuses. Leave
them as `[TBD]` and add an open question for the user. A field or status listed under
"Conflicts to resolve" in `data-model.md` or `status-model.md` needs dev confirmation
first: mark it `[CONFIRM: C#]` in the mapping and add it to the open questions. Invented PowerSell fields would
flow straight into dev tickets and get built.

---

## Output style

- Confluence-compatible Markdown only. No HTML.
- **Business-facing outputs** (gate summaries, use-case matrix, UAT scripts, launch
  comms, partner messages): plain language, no unexplained jargon. Readers are ops,
  brand and business teams.
- **Dev-facing outputs** (mapping doc, test cases, Jira stories): technical and precise.
- Lead with status and the decision needed. Details come after.
- Keep the chat reply short: where the partner stands, what was produced, what's needed
  from the user. Long content belongs in the tracker or the stage document.
