# S3 output templates

All outputs go on one Confluence page titled `[Partner] – System Logic Notes`, in this
order: G2 readiness (top), then sections 1–5. Keep section names unchanged so later runs
can find and update them.

## Contents
- [Page header and G2 readiness](#page-header-and-g2-readiness)
- [§ 1 System logic notes](#-1-system-logic-notes)
- [§ 2 Logic check results](#-2-logic-check-results)
- [§ 3 Smoke test plan and results](#-3-smoke-test-plan-and-results)
- [§ 4 Doc vs reality log](#-4-doc-vs-reality-log)
- [§ 5 Partner question message (draft)](#-5-partner-question-message-draft)

---

## Page header and G2 readiness

```markdown
# [Partner] – System Logic Notes

| | |
|---|---|
| **API doc version** | |
| **Staging tested on** | [date, or "Not yet"] |
| **Last updated** | |
| **Tracker** | [link] |

## G2 readiness – Logic understood

**Status:** [Ready / Not ready] — [one sentence: what's blocking, and who owes it]

| # | Condition | Met? | Note |
|---|---|---|---|
| 1 | No ❓ logic check in must-have flows | ✅ / ❌ | [count open] |
| 2 | All blocking partner questions answered | ✅ / ❌ | [Q-IDs still open] |
| 3 | Smoke tests passed for product, inbound, outbound, cancel outbound, return | ✅ / ❌ | |
| 4 | Every must-have partner status maps to one PowerSell status, or is a listed gap | ✅ / ❌ | |
| 5 | Every 🔴 gap is in Risks & gaps with an owner | ✅ / ❌ | |

**Logic checks:** ✅ [n] · ✅ (doc) [n] · 🟡 [n] · 🔴 [n] · ❓ [n] · ➖ [n]
```

---

## § 1 System logic notes

```markdown
## 1. System logic notes

### 1.1 How the partner models things
| Topic | Partner behaviour | Source |
|---|---|---|
| Warehouse / client / brand structure | | Doc § / Q-ID / Test |
| Product (SKU) identity: who creates the ID, is our SKU code kept? | | |
| Order identity: one order = one shipment? split shipments? | | |
| Inbound identity: ASN, PO, GRN | | |
| Return identity: link to original order? | | |

### 1.2 Lifecycles
| Object | Partner statuses in order | Final statuses | Can cancel until |
|---|---|---|---|
| Inbound | | | |
| Outbound | | | |
| Return | | | |
| Delivery (if offered) | | | |

### 1.3 How updates reach PowerSell
| Update | Webhook? | Polling endpoint? | Real-time or batch? | Payload: full or changed fields |
|---|---|---|---|---|
| Inbound received | | | | |
| Stock change | | | | |
| Outbound status | | | | |
| Return received | | | | |

### 1.4 Technical rules
| Topic | Behaviour |
|---|---|
| Authentication and token expiry | |
| Rate limit (per shop or per partner?) | |
| Pagination | |
| Duplicate protection | |
| Timezone / date format | |
| Units (weight, dimensions, currency, shelf life) | |
| Error format and codes | |
| Webhook retry, signature, ordering | |
```

---

## § 2 Logic check results

One row per check, all 42, in order. "Mapping note" carries into the S5 mapping document.

```markdown
## 2. Logic check results

| ID | Check | Result | Partner behaviour | Evidence | Mapping note / action |
|---|---|---|---|---|---|
| L-01 | Product key | 🟡 | Uses barcode as key | Doc p.12; TC-S03 | Send `product.barcode`; SKU without barcode can't be created → Risk R-02 |
| L-23 | Cancelled at each outbound stage | ❓ | Doc lists `cancelled` only | Doc p.30 | Q-07 |
```

### Status mapping drafts (from L-20, L-22, L-25)

```markdown
### 2.1 Draft status mapping – [Inbound / Outbound / Return]

| Partner status | Partner meaning | PowerSell status (display) | PowerSell status (backend) | Confidence | Note / Q-ID |
|---|---|---|---|---|---|
| `picking` | Picking started | Sent successfully | Picking | Doc only | |
| `cancelled` | ? | — | — | Gap | Q-07 |
```

Confidence: `Tested` (seen in staging) · `Doc only` · `Gap` (no match, question raised).
The display column applies to outbound only.

---

## § 3 Smoke test plan and results

```markdown
## 3. Smoke tests

**Environment:** [staging base URL] · **Run by:** [name / QC] · **Run on:** [date]

| TC | Step | Request (endpoint + key inputs) | What to check | Proves | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-S01 | Auth | `POST /auth/token` | Token returned; expiry stated | L-37 | Not run | |
| TC-S05 | Create outbound | `POST /orders` with a masked address | Accepted; partner ref returned | L-04, L-14 | Not run | |
| TC-S06 | Create outbound again (same order number) | Same body as TC-S05 | Rejected as duplicate, or same ref returned | L-39 | Not run | |
```

Result: `Pass` · `Fail` · `Blocked` (can't run, e.g. no credentials) · `Not run`.
Evidence: response snippet, HTTP code, or screenshot reference. Leave blank until
the actual result is seen.

---

## § 4 Doc vs reality log

```markdown
## 4. Doc vs reality

| # | Endpoint | Document says | Staging actually does | Impact | Check | Q-ID |
|---|---|---|---|---|---|---|
| D-01 | Get order | `status` is a string | Returns an integer code | Status mapping needs a code table | L-22 | Q-09 |
```

Impact: describe the consequence for PowerSell in one line (what breaks, for whom).

---

## § 5 Partner question message (draft)

Plain language, no PowerSell-internal field names. Blocking questions first.

```markdown
Subject: [Partner] x PowerSell integration – questions on API behaviour ([date])

Hi [partner contact],

Thank you for the staging access. We have reviewed the API document [version] and run
first tests. To continue, we need your help with the questions below. Questions marked
**(priority)** block our next step. Could you reply by [date]?

**Orders**
- Q-07 (priority): When an order is cancelled after packing, which status do you send?
- Q-09: In "Get order", `status` comes back as a number (e.g. `3`), but the document shows
  text. Could you share the full list of codes and their meaning?

**Inbound**
- Q-11: …

Thank you,
[name]
```
