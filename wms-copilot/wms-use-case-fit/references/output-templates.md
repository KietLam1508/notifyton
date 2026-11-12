# S4 output templates

One Confluence page titled `[Partner] – Use-Case Fit`. Order on the page: § 4 business
summary, § 5 G3 decisions, then § 1, § 2, § 3, § 6. Business readers stop after § 5.

## Contents
- [§ 1 Brand context](#-1-brand-context)
- [§ 2 Use-case coverage matrix](#-2-use-case-coverage-matrix)
- [§ 3 Workaround costing](#-3-workaround-costing)
- [§ 4 Business summary](#-4-business-summary)
- [§ 5 G3 decisions](#-5-g3-decisions)
- [§ 6 Scope handoff to S5](#-6-scope-handoff-to-s5)

---

## § 1 Brand context

```markdown
## Brand context

| # | Question | Answer | Source |
|---|---|---|---|
| B1 | Brands and channels | | [user / tracker / date] |

### Priorities for "Varies" use cases
| Use case | Library priority | Resolved priority | Reason | Confirmed by |
|---|---|---|---|---|
| UC-01 | Varies | Not needed | Single warehouse at partner (B2) | [PIC name, date] |
```

---

## § 2 Use-case coverage matrix

```markdown
## Use-case coverage

**Cross-cutting issues:** [🔴 items from L-37, L-38, L-40, L-42, or "None"]

| ID | Use case | Priority | Support | How it works with this partner | Evidence | Gap / workaround note | Proposed scope |
|---|---|---|---|---|---|---|---|
| UC-09 | Send customer orders for fulfillment | Must | ✅ | Order created via API when confirmed on channel; partner returns its order code | S2 #14 = 5; L-04 ✅, L-39 ✅; TC-S05 Pass | | Phase 1 |
| UC-16 | Get return results | Should | 🔁 | No return detail endpoint, no return webhook | S2 #24 = 0, #31 = 0; L-29 🔴 | Ops enters received qty from partner's daily email (W-01) | Phase 1 with workaround |

**Totals:** ✅ [n] · 🟡 [n] · 🔁 [n] · ❌ [n] · ➖ [n] · ❓ [n]

### Changed since evaluation (S2)
| S2 row | S2 score | S4 finding | Could the S2 band change? |
|---|---|---|---|
```

---

## § 3 Workaround costing

```markdown
## Workarounds

| W | Use case | Who | What they do | Trigger / frequency | Effort (hrs/week) | Scales with volume? | Risk if missed |
|---|---|---|---|---|---|---|---|
| W-01 | UC-16 | Ops | Copy returned quantities from the partner's daily email into PowerSell | Per return, ~40/week (assumption) | 3 min × 40 = 2.0 | Yes: **not viable long-term** | Returned stock not resellable in PowerSell |

**Total manual effort at current volume:** [x] hrs/week · **On a campaign day (× [n]):** [y] hrs
```

---

## § 4 Business summary

Plain language. No endpoint names, field names or use-case IDs in the bullets.

```markdown
# [Partner] – What brands and teams can expect

**In short:** [2–3 sentences: overall fit, the biggest limit, the decision needed]

### ✅ Works automatically
- New products are created in the warehouse without anyone typing them in.
- …

### 🔁 Needs manual work
- **Returns:** ops copies returned quantities from the partner's daily email. About 2
  hours a week now; more during campaigns.

### ❌ Won't work in Phase 1
- **Instant orders can't be prioritised.** Same-day orders are picked in normal order,
  so some may miss the cut-off. Affects: [brands].

### Who is affected
| Team | What changes for them |
|---|---|
| Ops | |
| Brand team | |
| CS | |
```

---

## § 5 G3 decisions

```markdown
### Gate G3 – Scope agreed: decisions needed

| # | Decision | Recommendation | Approver | Decision | Date | Conditions |
|---|---|---|---|---|---|---|
| D1 | Phase 1 scope = [list of UC IDs] | Approve | Business stakeholder: [name] | | | |
| D2 | Accept workaround W-01 (returns entered manually, ~2 hrs/week) | Approve with review after 30 days live | Module owner, Order & Return Management | | | |
| D3 | Descope UC-10 (priority orders) to Later | Approve | Business stakeholder + module owner, Order & Return Management | | | |
```

G3 passes only when every row has a decision.

---

## § 6 Scope handoff to S5

```markdown
## Scope for API mapping (S5)

### In scope (Phase 1)
| Flow group | Use cases | Endpoints / webhooks | S3 mapping notes to apply |
|---|---|---|---|
| Product | UC-02, UC-04 | Create product; get inventory; stock webhook | L-01 barcode key; L-09 cm → mm |

### Out of scope
| Flow / endpoint | Reason |
|---|---|
| Get carriers, get locations | WMS doesn't deliver for these brands (B3) |
```
