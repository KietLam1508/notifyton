---
name: wms-partner-logic-validation
description: >
  Validate how a WMS (Warehouse Management System) partner's system really behaves before
  PowerSell maps or builds anything: writes the partner system logic notes, runs 42 logic
  checks against PowerSell's data and status model, plans and records staging smoke tests,
  logs "doc vs reality" differences, writes partner questions, and prepares the G2 "Logic
  understood" gate. This is stage S3 of the wms-integration-copilot flow. Use it whenever
  the user wants to validate, test, sanity-check or understand a WMS partner's logic or
  lifecycle, e.g. "validate [partner] logic", "run S3 for [partner]", "smoke test [partner]
  staging", "what questions should we ask [partner]", "compare [partner] statuses with
  ours", "here are the staging responses from [partner]", or "is [partner] ready for G2".
  Runs after the wms-api-evaluation scorecard passes G1, and before wms-use-case-fit (S4).
---

# WMS Partner Logic Validation (S3)

The API document says what the partner *intends*. Staging shows what the partner
*does*. Most integration bugs at PowerSell came from gaps between the two, or from a
partner concept that has no matching PowerSell concept (a status with no equivalent, a
quantity counted differently, a reference stored in the wrong field). This skill finds
those gaps while they are still cheap to fix: before mapping, dev and UAT.

Outputs (all Confluence-ready Markdown):
1. **System logic notes**: how the partner models things and moves them through statuses
2. **Logic check results**: 42 fixed checks against PowerSell's expectations
3. **Smoke test plan and results** for staging
4. **Doc vs reality log**
5. **Partner questions**, with a draft message to the partner
6. **G2 readiness summary**

---

## Inputs

Collect what's available. Missing items don't block starting. They become open items.

| Input | Where it comes from | Needed for |
|---|---|---|
| Partner API document (current version) | Tracker → Artifacts, or user | Everything |
| Endpoint inventory (S1) | Tracker | Smoke test plan |
| Evaluation scorecard (S2) and G1 conditions | Tracker | Focus areas, known gaps |
| Partner Q&A log | Tracker | Avoid re-asking; answers feed checks |
| Staging UI + API credentials | Tracker / user | Smoke tests |
| Actual staging responses | User or QC pastes them, or a Postman run export | Doc vs reality |
| PowerSell reference pack | See below | Logic checks |

**PowerSell reference pack.** The source of truth for PowerSell's fields, statuses and
cross-partner rules lives in the copilot skill:
`../wms-integration-copilot/references/powersell-reference/` (`data-model.md`,
`status-model.md`, `use-case-library.md`). If called from the copilot, use what it has
loaded. If running alone and that folder can't be found, ask the user to share those
files. Never fill a PowerSell field or status from memory.

---

## Workflow

### Step 1 — Orient

State in 2–3 lines: partner, API doc version, G1 outcome and conditions, whether staging
access exists, and how many Q&A rows are already open. If G1 hasn't passed, warn the user
and ask whether to continue anyway (record the answer in the tracker's Activity log).

### Step 2 — Write the system logic notes (from the document)

Fill the template in `references/output-templates.md` § 1 using only the API document and
answers already in the Q&A log. Where the document is silent, write `Not documented` and
don't guess. Every `Not documented` cell becomes a candidate question in Step 6.

### Step 3 — Run the 42 logic checks

Open `references/logic-checks.md` and work through **every** check, in order. Each check
names what PowerSell expects (with the reference-pack section) and why it matters (the
partner where it broke before). Rate each check:

| Result | Meaning | Action |
|---|---|---|
| ✅ Match | Partner behaves the way PowerSell expects | None |
| 🟡 Differs, mappable | Different, but a transform or rule handles it (unit conversion, status grouping) | Write the rule in "Mapping note"; it carries into S5 |
| 🔴 Differs, gap | No clean way to handle it in mapping | Add to Risks & gaps; becomes an S4 input |
| ❓ Unknown | Document is silent or unclear | Partner question (Step 6) or smoke test (Step 4) |
| ➖ N/A | Partner doesn't offer the flow (e.g. no delivery service) | Say why |

Rules:
- Every check gets a result. No blanks, no silent skips.
- Base a result on the document **and** staging evidence when you have it. A ✅ from the
  document alone is written `✅ (doc)`. It is upgraded to `✅` only once a smoke test
  confirms it.
- **Status checks (L-20 to L-27):** list every partner status and map it to exactly one
  PowerSell status from `status-model.md`. A partner status that has no clean match is
  🔴 and needs a question. Never force it into the nearest PowerSell status: that's how
  BoostWare `cancelled` ended up mapped to "Sent successfully" (conflict S1).
- If a check touches a PowerSell field or status that is listed under "Conflicts to
  resolve" in the reference pack, write `[CONFIRM: C#/S#]` in the mapping note. Don't pick
  one side yourself.

### Step 4 — Plan the smoke tests

Build the plan from the template in `references/output-templates.md` § 3. Default order:

auth → get warehouse → create product → get product / stock → create inbound → get
inbound → cancel inbound → create outbound → get outbound → cancel outbound → create
return → get return → cancel return → trigger each webhook → negative tests.

For each step, name the logic checks it proves (e.g. "Create outbound twice with the same
order number → proves L-39 duplicate protection"). Skip steps for flows the partner
doesn't offer, and say so.

Always include these negative tests, because they are where partners differ most:
- Missing a mandatory field → is the error readable enough to show as `WMS error: …`?
- Same create request sent twice → duplicate protection
- Cancel after the allowed point → clear refusal, not silent success
- Product/SKU that doesn't exist at the WMS → error, not a silent drop
- Webhook for an order PowerSell doesn't know → what the partner does with our error reply

**Running the tests.**
- If the Postman connector is available, offer to create a collection for the plan.
  Show the list of requests first and create it only after the user says OK.
- This environment usually can't call the partner's staging directly. Hand the plan to
  the user or QC and ask them to paste the actual responses (or a Postman run export).
- **Never mark a test Pass without seeing its actual response.** If results haven't
  come back, the status stays `Not run`.

### Step 5 — Record results and doc vs reality

When responses come back:
1. Fill the Result column of the smoke test table (Pass / Fail / Blocked / Not run) with
   a one-line evidence note.
2. Compare each response to the document: missing fields, renamed fields, different
   types or formats, undocumented statuses, different error formats, different units.
   Each difference becomes a row in the Doc vs reality log (`references/output-templates.md`
   § 4) and usually a partner question.
3. Re-rate the affected logic checks (e.g. `✅ (doc)` → `✅`, or → 🔴).

### Step 6 — Write partner questions

Turn every ❓ check, every `Not documented` note and every doc-vs-reality difference into
a question. Before writing a new one, search the Q&A log: don't re-ask something already
answered, and don't duplicate an open question.

Each question:
- Is numbered with the next free tracker ID (`Q-01`, `Q-02`, …)
- Names the check or doc-vs-reality row it comes from
- Is concrete and answerable in one reply: "When an inbound is partially received and
  then closed, which status do you send: `completed` or `partial_closed`?", not "How do
  inbound statuses work?"
- Gets **Blocking = Y** if a Must use case or a mapping table can't be finished without
  it. Use `use-case-library.md` priorities to decide.

Then draft the message to the partner (template in `references/output-templates.md`
§ 5): grouped by topic, numbered with the Q&A IDs, blocking questions first, a polite
reply-by date. **Draft only.** Never send it.

### Step 7 — G2 readiness

G2 "Logic understood" is ready when **all** are true:

| # | Condition |
|---|---|
| 1 | No logic check is ❓ for a flow in the likely Phase 1 scope (Must use cases) |
| 2 | All Blocking partner questions are answered |
| 3 | Smoke tests passed for every must-have flow: product, inbound, outbound, cancel outbound, return |
| 4 | Every partner status in must-have flows maps to exactly one PowerSell status, or is listed as a gap |
| 5 | Every 🔴 gap is in the tracker's Risks & gaps with an owner |

Present the readiness table with ✅ / ❌ per condition, then the gate using the copilot's
gate template. Recommendation logic:
- All 5 conditions met → **Approve**
- Only non-blocking items open → **Approve with conditions** (list them)
- Blocking questions unanswered or must-have smoke tests not run → **Hold**, with what is
  missing and who owes it
- A 🔴 gap breaks a Must use case with no workaround in sight → **Hold**, and flag that
  S4 will probably need business to accept a workaround or descope

Never mark G2 passed yourself. The WMS partner PIC decides.

### Step 8 — Update the tracker

- S3 stage status (`In progress` / `Waiting on partner` / `Waiting on gate` / `Done`)
- New Q&A rows; answers received
- Risks & gaps rows for every 🔴
- Artifacts: link the logic notes page with its version and date
- Activity log: what ran, what's waiting, on whom

---

## Handling new information later

A partner answer or a new API document version can change earlier results. When it does:
re-rate only the affected checks, add a Doc vs reality row if the new behaviour contradicts
the document, and list what downstream work is now stale (S2 score rows, S4 use cases, S5
mapping sections). The copilot handles marking them `Stale`.

---

## Output style

- Lead with the readiness summary: where G2 stands and what's blocking. Details follow.
- The logic notes and logic checks are read by the PIC and dev: precise, field names in
  `code`.
- The partner message is read by the partner's team, often in a second language: short
  sentences, one question per line, no PowerSell-internal field names.
- Confluence-compatible Markdown only. No HTML.
- Chat reply: 3–5 lines (G2 status, number of checks per result, blocking questions,
  next action). Long content goes to the logic notes page.

---

## Regression check

After changing this skill, re-run it on a past partner (see `partner-examples.md` in the
reference pack) and confirm known facts still come out:
- **Flash**: L-01 product key is flagged 🟡 (barcode, not SKU code)
- **BoostWare**: L-23 flags `cancelled` (9000) as a status needing a decision, not mapped
  silently to "Sent successfully"
- **LEL**: L-22 lists the unmapped LEL statuses from `status-model.md` "Known mapping gaps"
