# Partner examples

**Status: DRAFT — scorecard links `[TBD]`.**

Past partners serve two purposes: (1) show what good output looks like, and (2) act as
regression checks. After changing any copilot skill, re-run these partners and confirm
the outcomes below still hold. If one changes, find out why before trusting the change.

---

## OnFlow (Vietnam): the model to follow

| Item | Value |
|---|---|
| Role | Model API mapping; first full run of the evaluation pipeline |
| Evaluation outcome | ~99, recommended **Proceed with caveats** |
| Caveats at the time | Webhook production-readiness; last-mile delivery scope |
| API mapping page | https://intrepid-asia.atlassian.net/wiki/spaces/PV/pages/4020371458 |
| Evaluation scorecard | [TBD: Google Sheet link] |

Use the OnFlow mapping page as the style and depth reference for S5, and as the source
for filling `data-model.md` and `status-model.md`.

## SnT (eHUB Cloud API Rev 2.2): the disqualified reference

| Item | Value |
|---|---|
| Role | Reference case for a partner that fails the gate |
| Evaluation outcome | **58, Disqualified** |
| Mapping test | Full 15-endpoint mapping produced as a skill test: SKU profiles, purchase orders, inbound receiving, sales orders, AWB, picking confirmation, order status, inventory sync, POD, return orders, product inventory query |
| Related | SnT iWeb API Rev 7 was compared alongside eHUB Cloud |
| Evaluation scorecard | [TBD: link] |
| Mapping document | https://intrepid-asia.atlassian.net/wiki/spaces/PV/pages/4196958210 |

## Regression checks

| Partner | Stage | Expected outcome |
|---|---|---|
| SnT eHUB Cloud Rev 2.2 | S2 | Total 58 (suggested tolerance ±2 for "varies" judgement), band <60, **Disqualified**, G1 stops the flow |
| OnFlow | S2 | Band >75, recommendation Proceed (with caveats while the open items stand) |
| Flash | S3 | L-01 product key rated 🟡 (barcode is the key, not SKU code) |
| BoostWare | S3 | L-23 flags `cancelled` (9000) as needing a decision, not silently "Sent successfully" |
| LEL | S3 | L-22 lists the unmapped LEL outbound statuses from `status-model.md` |
| OnFlow | S4 | [confirm] Must-have use cases UC-05, UC-07, UC-09, UC-11 show ✅ or 🟡 |
| OnFlow | S5 | Output matches the structure of the existing OnFlow mapping page |

Add each new partner here once it passes G6 or is disqualified at G1.
