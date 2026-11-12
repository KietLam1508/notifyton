# PowerSell reference pack

PowerSell's side of every WMS integration: the business use cases it must support, its
own data fields and statuses, and past partners to learn from. Every stage of the copilot
reads from here, so partners are always judged and mapped against the same standard.

## File status

| File | What it holds | Status |
|---|---|---|
| `use-case-library.md` | 18 business use cases with priority, module and "supported means" | DRAFT: seeded from the 35-criteria checklist; priorities and modules need confirming |
| `data-model.md` | PowerSell fields used in WMS mappings, cross-partner rules, 13 field conflicts, source-doc errors | DRAFT: filled from all 21 docs; conflicts C1–C13 need dev answers |
| `status-model.md` | Statuses for ASN, PO, transfer order, WMS order (display + backend), return, item condition; known gaps | DRAFT: filled from all 21 docs; conflicts S1–S10 need dev answers |
| `partner-examples.md` | OnFlow, SnT and expected outcomes for regression checks | DRAFT |

Change a file's status to `CONFIRMED` once dev has answered its conflicts.

## Source documents (Confluence space PV)

Base URL: `https://intrepid-asia.atlassian.net/wiki/spaces/PV/pages/<id>`. All read on
2026-10-29.

### Partner mapping docs

| Partner | Page ID | Last updated | Format | Note |
|---|---|---|---|---|
| Onflow | 4020371458 | 2026-08 | Field paths | Model to follow |
| TNSL | 3293642767 | 2026-10 | Field paths | Return moved to child page "TNSL - Return" (3829006338, not read) |
| BoostWare (SG, MY) | 2978840604 | 2026-09 | Field paths | Same API family as ZTO |
| EASYSPAD | 3919216642 | 2026-09 | Field paths | Best Inc GLINK API, cloned from IM Logistics |
| IM Logistics | 3273490473 | 2026-09 | Field paths | GLINK; return child page 3828776973 |
| Lazada MCL (V2 - LEL) | 2835349505 | 2026-09 | Field paths | |
| SnT | 4196958210 | 2026-07 | Field paths | |
| Flash | 1287421953 | 2026-05 | Field paths | Product key is barcode |
| BetterLand | 2805202946 | 2025-12 | Field paths | Own OMS API (not GLINK); return child page "BetterLand - Return" (3829268490, not read) |
| N&H | 3828482524 | 2025-12 | Field paths | Return only; no main mapping doc found |
| TitipAja | 2274000909 | 2025-11 | Mostly UI labels | |
| Boxme V2 | 2616950859 | 2025-10 | UI labels + DB column | Richest backend order status list |
| ZTO | 2323251242 | 2024-10 | UI labels | |
| MyCloud | 2620883027 | 2024-01 | UI labels | Early draft, likely not live |

### Cross-WMS docs

| Document | Page ID | Last updated |
|---|---|---|
| [Return] - WMS Integration Document | 2408480882 | 2026-01 |
| [Offline orders] WMS Integration Document | 2794487827 | 2025-04 |
| [Shopify] WMS integration document | 3925966849 | 2026-02 |
| [Transfer Order] WMS integration documents | 2526216230 | 2023-08 |
| PowerSell_W Order Status & Definition | 23724121 | 2026-10 |
| WMS status management (legacy) | 1722023973 | 2022-07 |

Legacy pages (2021–2023, likely inactive, not used): API mapping with Boxme (v1),
Boxme (Limited), API Mapping with LEL (v1), Shipper, Swift (draft), Wareo, Roadbull.

## Maintenance rules

- **One source of truth.** If a new mapping uses a PowerSell field or status that isn't
  here, add it here first, then use it in the mapping.
- **Never invent.** A missing value stays `[TBD]` with an open question, so it can't leak
  into dev tickets as if it were real.
- **Conflicts block reuse.** A field or status listed under "Conflicts to resolve" can't be
  used in a new mapping until dev confirms it.
- **Log changes** below, because past mappings were built on older versions.

## Applying dev answers

Open conflicts (C1–C13, S1–S10), unmapped partner statuses and source-doc errors were
sent to dev as one question list: "PowerSell WMS reference – open questions for dev"
(Confluence: [link TBD]). When the user shares answers (the filled page, or answers
in chat):

1. **One answer at a time.** For each answered row, update the matching section of
   `data-model.md` or `status-model.md`: keep the confirmed field / status, remove the
   **See C#** / `[CONFIRM: …]` flag, and move the row from "Conflicts to resolve" to a
   "Resolved" table with the answer, who answered and the date.
2. **Don't apply the copilot proposal unless dev explicitly agreed with it.** An empty
   or "not sure" answer leaves the conflict open.
3. **Unmapped partner statuses** (status-model "Known mapping gaps"): add each confirmed
   mapping to the partner's row, or mark the partner `Not live – ignore`.
4. **Use-case library answers** from module owners: update priority / module, remove
   `[confirm]` / `[TBD]`.
5. **Find affected past mappings.** List the partner mapping pages that used the losing
   option of each conflict (the "Seen in" codes show which). Report them to the user as
   a fix list; don't edit those pages without an OK.
6. **Flip file status** to `CONFIRMED` when no conflicts remain in that file; otherwise
   write "DRAFT – [n] conflicts open".
7. Add a Change log row per file changed.

## Change log

| Date | File | Change | By |
|---|---|---|---|
| 2026-10-29 | All | Initial draft structure | Copilot |
| 2026-10-29 | data-model.md, status-model.md | Filled from 5 mapping docs and 3 cross-WMS docs; conflicts listed | Copilot |
| 2026-10-29 | data-model.md, status-model.md | Extended to all 21 docs: new fields, cross-partner rules, conflicts C11–C13 and S6–S10, mapping gaps, source-doc errors | Copilot |
| 2026-11-12 | README.md | Added "Applying dev answers"; open questions sent to dev as one list | Copilot |
