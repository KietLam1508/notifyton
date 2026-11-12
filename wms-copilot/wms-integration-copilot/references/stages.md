# Stage playbooks (S1–S9)

Read only the section for the stage you are running.

## Contents
- [S1 Intake](#s1-intake)
- [S2 Evaluate](#s2-evaluate)
- [S3 Validate partner logic](#s3-validate-partner-logic)
- [S4 Business use-case fit](#s4-business-use-case-fit)
- [S5 API mapping](#s5-api-mapping)
- [S6 Dev & testing handoff](#s6-dev--testing-handoff)
- [S7 UAT](#s7-uat)
- [S8 Launch](#s8-launch)
- [S9 Adoption](#s9-adoption)

Stage statuses used in the tracker: `Not started` · `In progress` · `Waiting on partner` ·
`Waiting on gate` · `Done` · `Stale` · `Skipped`

---

## S1 Intake

**Goal:** turn whatever the partner sent into a clean starting point.

**Collect** (ask only for what's missing; missing items don't block S2, log them as open):
- Partner name, country, partner contact
- API document (file, link, Postman collection, OpenAPI file) and its version/date
- Staging access: UI login and API credentials (yes / no / requested)
- Brands or ventures asking for this WMS, and target go-live if known
- Jira epic (can be created later)

**Steps:**
1. Read the full API document.
2. Build the **endpoint inventory** below. List every endpoint, including ones that seem
   irrelevant. Later stages decide relevance.
3. Note anything the document doesn't cover at all (e.g. no webhook section, no error
   codes, no rate limits). These become the first partner questions.
4. Create the tracker from `tracker-template.md`. Fill the header, set S1 to `Done`.

**Output: endpoint inventory**

```markdown
## Endpoint inventory – [Partner] API [version]

| # | Flow group | Endpoint name | Method | Path | Direction | Doc quality | Note |
|---|---|---|---|---|---|---|---|
| 1 | Product | Create product | POST | `/api/products` | PowerSell → Partner | Good / Partial / Missing samples | |
```

- **Flow group**: Config · Product · Inbound · Outbound · Return · Webhook · Other
- **Direction**: `PowerSell → Partner` (we call them) or `Partner → PowerSell` (webhook/callback)
- **Doc quality**: Good (purpose + sample request/response + errors) · Partial · Missing samples

**Next:** go straight into S2.

---

## S2 Evaluate

**Goal:** go / no-go on investing further in this partner.

**Steps:**
1. Run the `wms-api-evaluation` skill on the spec. Follow that skill fully, including its
   rule to flag every "varies" row for confirmation.
2. When proposing scores for "varies" rows, use `use-case-library.md` to judge whether the
   capability matters to PowerSell's actual setup.
3. Add the 8 due-diligence questions to the tracker's Partner Q&A log (category
   `Due diligence`, not blocking unless the user says so).
4. Link the scorecard in the tracker's Artifacts table.

**Gate G1 – Go / no-go.** Approver: WMS partner PIC.
Present the score, band, top 3 gaps, and the "varies" rows still needing confirmation.
The gate can't be decided while "varies" rows are unconfirmed, because they can move the
total across a band boundary.

- Proceed → S3
- Proceed with caveats → S3, caveats go to Risks & gaps
- Disqualified → stop, overall status `Disqualified`

---

## S3 Validate partner logic

**Goal:** understand how the partner's system actually behaves, not just what the
document says. Most integration bugs come from gaps between the two.

**Steps:**
1. Run the `wms-partner-logic-validation` skill. Follow it fully. Pass it the API
   document, the S1 endpoint inventory, the S2 scorecard and G1 conditions, the Q&A log,
   staging credentials, and the reference pack (`data-model.md`, `status-model.md`,
   `use-case-library.md`).
2. It produces the `[Partner] – System Logic Notes` page: G2 readiness, system logic
   notes, 42 logic check results with draft status mappings, smoke test plan and results,
   doc vs reality log, and a draft partner question message.
3. Copy its new partner questions into the tracker's Q&A log and every 🔴 check into
   Risks & gaps. Link the page in Artifacts.
4. Smoke tests are run by the user or QC unless this environment can reach staging.
   Never record a test as passed without its actual response.

**Gate G2 – Logic understood.** Approver: WMS partner PIC.
Use the skill's 5-condition readiness table. Ready when all blocking questions are
answered, the smoke tests passed for every must-have flow, and every must-have partner
status maps to one PowerSell status or is a listed gap. Open non-blocking questions are
presented as known risks.

---

## S4 Business use-case fit

**Goal:** agree, in business language, what PowerSell can and can't do with this
partner, and what goes into phase 1.

**Steps:**
1. Run the `wms-use-case-fit` skill. Follow it fully. Pass it the use-case library, the
   S2 scorecard, the S3 logic notes and check results, the Q&A log, Risks & gaps, and
   the brands requesting this WMS.
2. It first settles every "Varies" priority from the brands' real setup. The WMS partner
   PIC confirms these before any use case is rated. Record them in the Decision log.
3. It produces the `[Partner] – Use-Case Fit` page: business summary, G3 decision table,
   brand context, coverage matrix for all 18 use cases with evidence, workaround costing
   in hours per week, and the scope handoff list for S5.
4. If it reports "Changed since evaluation" rows that could move the S2 band, mark the
   scorecard `Stale` and follow "Going backwards" in `SKILL.md`.
5. Add every workaround and gap to Risks & gaps with an owner. Link the page in Artifacts.

**Gate G3 – Scope agreed.** Approvers: business stakeholders and the PowerSell module
owners for the affected modules (the module column in `use-case-library.md` shows which).
The gate passes only when every row of the skill's G3 decision table has a decision:
the Phase 1 scope, plus acceptance of each must-have workaround or descoping.

---

## S5 API mapping

**Goal:** the developer-ready mapping document.

**Steps:**
1. Run the `wms-api-mapping` skill. Pass it:
   - The S4 "Scope handoff to S5" list: only Phase 1 flows from G3, with the rest under
     "Out of scope"
   - The S3 logic check mapping notes (unit conversions, key choices, status mapping
     drafts) for those flows
   - PowerSell fields from `data-model.md` for the "PowerSell params" column
   - PowerSell statuses from `status-model.md` for status mapping tables
   - Answers from the Q&A log, and the S3 "Doc vs reality" findings
   - Staging credentials and Jira epic, if available
2. Collect every `[TBD]` left in the document. Each one becomes a Q&A log row (for the
   partner) or an open question (for PowerSell internally).
3. Publishing to Confluence: draft first, publish on OK, link in the tracker.

**Gate G4 – Mapping approved.** Approver: dev lead.
Ready when no `[TBD]` remains in Phase 1 flows, or each remaining one is accepted as a
known risk.

---

## S6 Dev & testing handoff

**Goal:** give dev and QC everything they need, so they don't have to re-read the spec.

**Steps:**
1. **Jira stories**: one story per Phase 1 flow group (Config, Product, Inbound,
   Outbound, Return, Webhook), under the epic. Each story: short title, link to the
   matching mapping section, acceptance criteria, related use-case IDs. Show the full
   list first; create in Jira only on OK.
2. **QC test cases** (table below). Minimum coverage:
   - Happy path for every Phase 1 endpoint
   - Missing each mandatory field → clear error
   - Every row of every status mapping table
   - Cancel at each allowed and not-allowed stage
   - Same request sent twice (duplicate protection)
   - Webhooks: retry, arriving out of order, arriving for an unknown order
   - Every workaround agreed at G3
3. **Test collection**: if the Postman connector is available, offer to extend the S3
   collection with the test cases (draft first).
4. Track progress in the tracker from what the user reports (stories done, test pass
   rate, open defects). Don't guess progress.

**Output: QC test cases**

```markdown
| TC | Flow | Endpoint | Scenario | Type | Steps | Expected result | Use case |
|---|---|---|---|---|---|---|---|
| TC-001 | Outbound | Create outbound | Valid B2C order | Happy path | | | UC-09 |
```

Type: Happy path · Negative · Edge · Status mapping · Webhook · Workaround

**Done when:** QC reports all Phase 1 test cases passed and no open critical or major
defects. No formal gate, but confirm with the user before moving to S7.

---

## S7 UAT

**Goal:** business users confirm the integration works for their real daily work.

**Steps:**
1. Write one UAT scenario per Phase 1 use case, in plain language, using the "Supported
   means" column of `use-case-library.md` as the expected result. Include agreed
   workarounds as their own scenarios.
2. Suggest testers by role (ops, warehouse coordinator, brand team).
3. Log failures as defects: draft the Jira bug with steps and evidence, create on OK.
4. Keep a sign-off block at the end.

**Output: UAT script**

```markdown
## [Partner] – UAT script

| # | Use case | What to do | What you should see | Tester | Result (Pass / Fail) | Evidence / note |
|---|---|---|---|---|---|---|
| 1 | UC-09 Send customer orders for fulfillment | | | | | |

### Sign-off
| Role | Name | Decision | Date | Conditions |
|---|---|---|---|---|
```

**Gate G5 – UAT sign-off.** Approvers: business users listed in the sign-off block.

---

## S8 Launch

**Goal:** go live safely, with everyone informed.

**Go-live checklist** (copy into the tracker and tick items as the user confirms them):

```markdown
| # | Item | Owner | Status |
|---|---|---|---|
| 1 | Production API credentials received and stored securely | | |
| 2 | Production base URL confirmed | | |
| 3 | Production webhook URL registered with the partner | | |
| 4 | Production rate limits confirmed (enough for campaign peaks) | | |
| 5 | Brand / warehouse setup configured in PowerSell | | |
| 6 | Product master synced to the WMS | | |
| 7 | Opening stock reconciled between WMS and PowerSell | | |
| 8 | Pilot brand and first live order agreed | | |
| 9 | Rollback plan: how to stop sending orders and fall back | | |
| 10 | Monitoring and alert owner in place | | |
| 11 | Support contacts and escalation path on both sides | | |
| 12 | Launch comms sent (internal ops, brand, partner) | | |
```

**Launch comms:** draft short messages for internal ops, the brand(s) and the partner:
what changes, from when, who to contact, and any agreed workarounds. Plain language.
Draft only.

**Gate G6 – Go-live.** Approvers: WMS partner PIC and Ops.
Ready when every checklist item is done or explicitly accepted as a risk.

---

## S9 Adoption

**Goal:** make sure the integration is used and stays healthy after launch.

**Metrics to track:**

| Metric | Why it matters |
|---|---|
| Brands live vs planned | Adoption itself |
| Orders sent to the WMS per day | Real usage |
| Failed or rejected requests (%) | Integration health |
| Stock mismatches between WMS and PowerSell | Overselling risk |
| Time from order sent to WMS confirmation | Fulfilment speed |
| Support tickets related to this WMS | Hidden manual effort |
| Partner response time on issues | Partner reliability |

**Steps:**
1. Ask the user where each metric can come from (PowerSell data, partner reports,
   support tool). Mark unknown sources `[TBD]`.
2. Offer to set up a recurring check (e.g. weekly) that updates the WMS integration
   dashboard and posts a short summary to the Slack channel.
3. Raise anything trending the wrong way as a risk in the tracker.

**Done when:** about 30 days after launch with stable metrics. Set overall status to
`Live`, close the tracker's open items, and hand ongoing monitoring to BAU support.
