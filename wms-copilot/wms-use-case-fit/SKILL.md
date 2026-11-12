---
name: wms-use-case-fit
description: >
  Check a WMS (Warehouse Management System) partner against every PowerSell business use
  case and agree what goes into Phase 1. Settles "Varies" priorities from the brands' real
  setup, rates support per use case with evidence, costs each manual workaround in hours
  per week, proposes Phase 1 / Later / Out of scope, and prepares the G3 "Scope agreed"
  decision for business stakeholders and module owners. This is stage S4 of the
  wms-integration-copilot flow. Use it whenever the user wants to know what PowerSell can
  or can't do with a WMS partner, e.g. "run S4 for [partner]", "use-case matrix for
  [partner]", "what can brands do with [partner]", "what's in phase 1 for [partner]",
  "which workarounds do we need for [partner]", "prepare the scope sign-off", or "explain
  [partner] gaps to business". Runs after G2 (wms-partner-logic-validation) and before
  wms-api-mapping (S5).
---

# WMS Use-Case Fit (S4)

S2 asked "is this partner's API good enough?" S3 asked "how does it really behave?"
S4 asks the question business cares about: **"What will brands, ops and CS be able to
do, what will cost them manual work, and what won't work at all?"** The answer becomes
the Phase 1 scope that dev builds and UAT tests. If S4 is too generous, dev builds
flows the partner can't support. If it is too strict, PowerSell drops a good partner.

Outputs (Confluence-ready Markdown, one page `[Partner] – Use-Case Fit`):
1. **Brand context**: the brands' real setup, which settles every "Varies" priority
2. **Use-case coverage matrix**: all 18 use cases, rated with evidence
3. **Workaround costing**: who does the extra work, how often, hours per week
4. **Business summary**: plain language, for people who won't read the matrix
5. **G3 decision package**: scope plus approval of each must-have workaround, by approver
6. **Scope handoff to S5**: which flows and endpoints go into the mapping document

---

## Inputs

| Input | Where it comes from |
|---|---|
| Use-case library (18 use cases, priority, module, "supported means") | `../wms-integration-copilot/references/powersell-reference/use-case-library.md` |
| Evaluation scorecard (S2), including confirmed "varies" scores | Tracker → Artifacts |
| System logic notes and logic check results (S3) | Tracker → Artifacts |
| Partner Q&A log, Risks & gaps | Tracker |
| Brands requesting this WMS, target go-live | Tracker header, or user |

If called from the copilot, use what it has loaded. If running alone and the use-case
library can't be found, ask the user to share it. Don't rebuild it from memory.

If G2 hasn't passed, warn the user: ratings will rest on the document only and must be
re-checked after G2. Mark every rating `(doc)`.

---

## Workflow

### Step 1 — Capture the brand context

"Varies" priorities depend on how the brands will actually use this WMS. Ask only what
the tracker and Q&A log don't already answer. Use the questions in
`references/brand-context.md`: brands and channels, number of warehouses, who delivers,
COD share, instant/same-day share, daily volumes.

Then **propose** a resolved priority for every "Varies" use case using the rules in
`references/brand-context.md`, each with a one-line reason. Show them as a draft and ask
the user (the WMS partner PIC) to confirm or override, as the evaluation skill does for
"varies" scores. Don't rate any use case until the priorities are confirmed: a Varies
use case resolved to Must can change the gate outcome.

If daily volumes are unknown, say so and use `[TBD]` in the workaround costing. Don't
invent volumes.

### Step 2 — Gather evidence per use case

For each of the 18 use cases, collect evidence using `references/uc-evidence-map.md`. It
lists which scorecard rows, logic checks and typical endpoints prove each one:
- S2 scorecard rows: Yes/No and score
- S3 logic checks: result (✅ / ✅ (doc) / 🟡 / 🔴 / ❓)
- S3 smoke tests: Pass / Fail / Not run
- Q&A answers and Risks & gaps rows

Cross-cutting checks (L-37 auth, L-38 rate limit, L-40 errors, L-42 staging parity) apply
to every use case. A 🔴 on one of these is reported once, at the top of the matrix, not
repeated 18 times.

### Step 3 — Rate partner support

Rate each use case against its **"Supported means"** sentence in the library. That
sentence is the bar, not the partner's marketing description.

| Rating | Rule |
|---|---|
| ✅ Supported | Meets "Supported means" fully. Needs a documented endpoint/webhook, no 🔴 or ❓ on its logic checks, and (for Must) a passed smoke test |
| 🟡 Partial | Works, with a stated limit (e.g. stock pushed every 30 min, not per event) |
| 🔁 Workaround | Not supported via API, but a manual or alternative way exists. Must say who does it, how and how often |
| ❌ Gap | Not supported, no workaround |
| ➖ Not needed | Priority resolved to Not needed in Step 1, with the reason |

Rules:
- Every rating cites evidence (scorecard row, check ID, test ID, Q-ID). No evidence = ❓
  open, and the use case can't be ✅.
- If the only evidence is the document, write `✅ (doc)` or `🟡 (doc)`. That's acceptable
  for Should use cases; for **Must** use cases flag it as a G3 risk.
- A ❓ logic check behind a Must use case is unresolved: rate the use case `❓ Pending`
  and list the blocking Q-ID. Don't round it up to ✅.

### Step 4 — Cost every workaround

For each 🔁 (and each 🟡 that needs manual effort), fill the costing table in
`references/output-templates.md` § 3:
- **Who** does it (role: ops, warehouse coordinator, brand team, CS, partner)
- **What** they do, in one sentence
- **Trigger and frequency**: per order, per inbound, daily, weekly
- **Effort**: minutes per occurrence × occurrences per week = hours per week. Show the
  arithmetic, and mark any assumed number `(assumption)`.
- **Scales with volume?** Yes / No. A workaround that grows with order volume is flagged
  **not viable long-term**: campaign days multiply it.
- **Risk if missed**: what goes wrong when someone forgets (oversell, late shipment,
  wrong stock)

### Step 5 — Propose scope

| Situation | Proposed scope |
|---|---|
| Must, ✅ or 🟡 | Phase 1 |
| Must, 🔁 | Phase 1 with the workaround, **needs explicit approval at G3** |
| Must, ❌ | **Blocks G3.** Options to present: partner builds it (ask for date), accept descoping with a named owner, or Hold / Reject the partner |
| Should, ✅ or 🟡 | Phase 1, unless it adds major dev effort (then Later; say why) |
| Should, 🔁 or ❌ | Later, or Out of scope |
| Not needed | Out of scope (reason) |

Only propose. The approvers decide at G3.

### Step 6 — Consistency check against S2

Compare each rating with the S2 scorecard rows it maps to. If S4 now says ❌ or 🔁 for a
row S2 scored as a working Yes (or the reverse), list it under "Changed since evaluation".
If the S2 total could move across a band boundary (60 or 75), say so clearly: the
copilot will mark the scorecard `Stale` and G1 may need to be decided again.

### Step 7 — Write the business summary

For readers who won't open the matrix: ops leads, brand managers, CS. Plain language, no
endpoint names, no field names. Structure in `references/output-templates.md` § 4:
- **What works automatically** (one line each)
- **What needs manual work**: who, how often, hours per week
- **What won't work**, and what that means for brands
- **Who is affected**: by team

### Step 8 — Prepare G3

G3 "Scope agreed". Approvers: business stakeholders **plus** the module owner of every
PowerSell module touched by a Phase 1 or workaround use case. Take the modules from the
library's "PowerSell module" column. If a module owner isn't known, list the module and
ask the user who owns it. If a module is marked `[confirm]` or `[TBD]` in the library,
say that the module assignment is unconfirmed.

Present using the copilot's gate template, plus the decision table in
`references/output-templates.md` § 5: one row per decision (the Phase 1 scope, and each
must-have workaround or descoping), each with its approver. G3 passes only when **every
row** has a decision. Recommendation logic:
- No Must ❌, all Must 🔁 costed → **Approve with conditions** (the workarounds are the
  conditions), or **Approve** if there are no workarounds
- Any Must ❌ without partner commitment → **Hold**
- Must ❌ on UC-09 (send orders) or UC-02 (register products), or several Must ❌ → flag
  that the partner may not be viable, and suggest re-deciding G1

Never mark G3 passed yourself. Record each approver's decision as the user reports it.

### Step 9 — Hand off to S5

List exactly what goes into the mapping document (template § 6): Phase 1 flow groups,
the endpoints and webhooks each needs, and every 🟡 mapping note from S3 that applies.
Everything else goes under "Out of scope", with its reason. The copilot passes this list
to `wms-api-mapping`.

### Step 10 — Update the tracker

S4 status, new Risks & gaps rows (every workaround and every gap, with owner), new Q&A
rows, the use-case fit page in Artifacts, Activity log.

---

## Output style

- The business summary and G3 package come **first** on the page. The matrix follows.
- Business-facing parts: plain language, short sentences, hours and people, not
  endpoints. Example: "Ops will need to type in returned quantities by hand, about 2
  hours a week at today's volume", not "UC-16 🔁, no GET /returns/{id}".
- Matrix and S5 handoff: precise, with evidence IDs.
- Confluence-compatible Markdown only. No HTML.
- Chat reply: 3–5 lines (count per rating, must-have gaps, decisions needed, from whom).

---

## Regression check

After changing this skill, re-run it on OnFlow (see `partner-examples.md` in the
reference pack): Must use cases UC-05, UC-07, UC-09, UC-11 should come out ✅ or 🟡.
