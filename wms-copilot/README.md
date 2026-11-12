# WMS Integration Copilot – update (2026-11-12)

## What changed

| Item | Change |
|---|---|
| `wms-partner-logic-validation` (new) | Stage S3: system logic notes, 42 logic checks against PowerSell's model, smoke test plan, doc vs reality log, partner questions, G2 readiness |
| `wms-use-case-fit` (new) | Stage S4: brand context settles "Varies" priorities, rates all 18 use cases with evidence, costs workarounds in hours/week, G3 decision table, scope handoff to S5 |
| `wms-integration-copilot` (updated) | S3 and S4 now call the two new skills; S5 receives the S4 scope list and S3 mapping notes; reference pack README has steps for applying dev answers; new S3 regression checks |
| `dev-questions/PowerSell-WMS-reference-open-questions.md` (new) | One question list for dev and module owners: 12 field and 10 status conflicts, 7 partners with unmapped statuses, 17 page fixes, use-case library confirmations |

`wms-api-evaluation` and `wms-api-mapping` are unchanged.

## Install

Upload the three files in `packages/` in claude.ai → Settings → Capabilities → Skills.
Replace the existing `wms-integration-copilot`. The two new skills sit next to it.
