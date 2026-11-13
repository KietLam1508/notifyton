# Boxme – What brands and teams can expect

| | |
|---|---|
| **Stage** | S4 Use-case fit — **draft** |
| **Based on** | Boxme API document + S2 scores confirmed by PIC. **No smoke test run yet** (deferred), so every rating is "(doc)" |
| **Brand context** | **Assumed** from the PIC's S2 scores; to be confirmed (§ 1) |
| **Last updated** | 2026-11-13 |

**In short:** Boxme can cover every flow PowerSell needs, and none of the 18 use cases is a
hard "no". But **7 of the 11 must-have use cases are still waiting on Boxme's answers**
(cancel rules, shelf-life unit, duplicate orders, short deliveries, condition codes). The
scope below is a proposal. G3 can't be decided until Boxme replies and the brand setup is
confirmed. Three things need business attention now:
1. **Marketplace orders work in reverse.** Boxme only starts picking after PowerSell sends
   the marketplace shipping label.
2. **Low order limits on campaign days.** About 2 new orders per second across all brands.
3. **Probably no way to cancel one item of an order.** The whole order would be cancelled
   and re-created.

### ✅ Works automatically (from the document)
- Stock in PowerSell stays in line with Boxme, per warehouse, updated on every change.
- New products are created at Boxme with our SKU code and barcodes.
- Inbound shipments are sent to Boxme with all SKUs and quantities. Priority receiving,
  unloading and inspection can be requested on the same shipment.
- Instant and same-day orders can be flagged so Boxme packs them first (45 min / 2 h).
- Returns can be announced to Boxme before they arrive.

### 🟡 Works, with limits
- **Order status tracking:** most Boxme statuses show in PowerSell automatically. Six rare
  ones (e.g. "courier refused", "lost at hub", "pending audit") need a decision on what to
  show.
- **Shipping label handover:** works, but PowerSell must get the label from the marketplace
  **before** Boxme can start picking. Any delay in getting the label delays the parcel.
- **Webhook setup:** done once per brand in Boxme's web portal, not automatically.

### 🔁 Needs manual or extra work (expected)
- **Cancelling one item of an order** (likely): cancel the whole order at Boxme and
  re-create it without that item. Can be automated by dev; otherwise CS does it by hand.
- **Keeping the connection alive:** each brand's Boxme API key expires within a year, and
  PowerSell's server addresses must be re-confirmed with Boxme every 180 days. If anyone
  forgets, every Boxme sync for that brand stops.

### ❓ Not known yet (waiting on Boxme)
Cancelling orders, inbound shipments and returns; receiving results; returned-item results;
sending orders (duplicate rule, masked buyer addresses); registering products (size and
shelf-life units).

### Who is affected
| Team | What changes for them |
|---|---|
| Ops | Set up webhooks and keys per brand in Boxme's portal; renew keys / IP confirmation on a calendar; decide what to show for 6 rare order statuses |
| Brand team | Products may need Boxme approval before first inbound; chilled / frozen products can't be stored at Boxme (Normal / Air-con only) |
| CS | Single-item cancellations may need a full cancel + re-create; campaign-day order delays possible if limits are hit |
| Dev | Queue order sending (rate limits); send label before Boxme picks; fetch quantities after inbound / return webhooks |

---

## G3 – Scope agreed: decisions needed

**Recommendation: Hold.** 7 must-have use cases are pending Boxme's answers, the brand
setup is assumed, and no smoke test has run. The table shows what each decision will be
once those are in.

| # | Decision | Recommendation | Approver | Decision | Date | Conditions |
|---|---|---|---|---|---|---|
| D1 | Confirm brand context and resolved priorities (§ 1) | Confirm or correct | WMS partner PIC | | | |
| D2 | Phase 1 scope = UC-01 to UC-13, UC-15 to UC-18 (UC-14 Boxme delivery → Later) | Approve once ❓ items are answered | Business stakeholder: [name] | | | |
| D3 | Partial cancellation handled as full cancel + re-create (W-01), automated by dev if possible | Approve, if Boxme confirms no partial cancel (Q-29) | Module owner, Order & Return Management | | | |
| D4 | Marketplace orders: PowerSell sends the label before Boxme picks (R-10) | Approve, after checking PowerSell's current Ready-To-Ship timing | Module owner, Order & Return Management | | | |
| D5 | Accept campaign-day rate-limit risk, or require higher limits from Boxme first (R-01) | Require Boxme's answer (Q-02) before go-live | Business stakeholder + module owner, Order & Return Management | | | |
| D6 | Webhook setup per brand in Boxme's portal (W-02) | Approve | Module owner for webhooks: **[TBD]** (UC-18 module not assigned) | | | |
| D7 | Key and IP renewal routine with a named owner (W-03) | Approve, with owner and calendar reminders | Business stakeholder | | | |
| D8 | Boxme delivery (UC-14) → Later | Approve, unless brands need Boxme to deliver | Business stakeholder + module owner, 3PL Management [confirm] | | | |
| D9 | Chilled / frozen products excluded from Boxme (R-09) | Approve if any requesting brand sells them; otherwise N/A | Module owner, Warehouse [confirm] | | | |

G3 passes only when every row has a decision.

---

## 1. Brand context

**Not answered yet.** Values below are **assumptions** from the PIC's S2 scores.

| # | Question | Answer | Source |
|---|---|---|---|
| B1 | Brands and channels | [TBD]. Assumed marketplace channels (Shopee, Lazada, TikTok Shop); country [TBD] (Boxme: VN, TH, PH) | Assumption |
| B2 | Boxme warehouses per brand | [TBD]. PIC scored warehouse list 2 (useful, not critical) | S2 row 5 |
| B3 | Who delivers | Marketplace logistics confirmed in use (PIC scored AWB upload 5). Boxme delivery: unknown (carriers / delivery scored 2) | S2 rows 17, 20, 21 |
| B4 | COD share | [TBD] | — |
| B5 | Instant / same-day share | [TBD] | — |
| B6 | Daily volumes | [TBD] orders/day, [TBD] inbound/week, [TBD] returns/week | — |
| B7 | Inbound services used | Some value (PIC scored 2) | S2 row 11 |
| B8 | Self-manage webhooks | Some value (PIC scored 2) | S2 row 27 |
| — | Chilled / frozen goods | [TBD] | R-09 |

### Priorities for "Varies" use cases (proposed — waiting on PIC confirmation)

| Use case | Library priority | Proposed priority | Reason | Confirmed by |
|---|---|---|---|---|
| UC-01 Know which warehouses | Varies | Should | Warehouse ID needed on every call, but PIC scored list 2 | |
| UC-03 Look up product data | Varies | Should | Boxme returns its product ID on create; PIC scored list / detail 3 | |
| UC-04 Keep stock in sync | Varies + Should | **Must** (push and pull) | Stock webhook exists; PIC scored stock pull 5 | |
| UC-06 Extra inbound services | Varies | Should | PIC scored 2 | |
| UC-08 Get inbound results | Varies + Should | **Must** (pull) | Inbound webhook carries no quantities, so the pull is the only source | |
| UC-12 Hand over marketplace AWB | Varies | **Must** | Marketplace logistics in use (PIC scored 5) | |
| UC-13 Track status (order list) | Should + Varies | Should | Order status webhook covers tracking; PIC scored list 2 | |
| UC-14 Delivery by Boxme | Should + Varies | Should (proposed Later) | Unknown whether brands want Boxme to deliver | |
| UC-16 Get return results | Varies + Should | **Must** (pull) | Return webhook carries no quantities | |
| UC-18 Manage webhooks | Should + Varies | Should | PIC scored self-config 2 | |

---

## 2. Use-case coverage

**Cross-cutting issues:**
- 🔴 **Rate limits per IP** (L-38, R-01): Create Order 2 / sec, Get Order 60 / min, shared by all brands.
- 🟡 **Key expiry (≤ 365 days) and IP re-confirmation every 180 days** (L-37, R-04).
- 🟡 **Testing happens on production** (L-42, R-03).
- 🟡 **Missing / bad credentials return 403, not 401** (D-09).

| ID | Use case | Priority | Support | How it works with Boxme | Evidence | Gap / workaround note | Proposed scope |
|---|---|---|---|---|---|---|---|
| UC-01 | Know which warehouses a brand uses | Should | 🟡 (doc) | Get Pickup List returns Boxme warehouses (`pickup_id`, `warehouse_code`) | S2 #5 = 2; L-08 🟡 | List mixes warehouses and seller addresses (Q-23) | Phase 1 |
| UC-02 | Register new products | Must | ❓ Pending | Create Product keeps our SKU and barcodes; returns `bsin` | S2 #6 = 3; L-01 ✅, L-03 ✅, L-09 ❓, L-12 ❓, L-15 🟡, L-16 🟡 | Waiting on Q-21 (size unit), Q-08 (shelf-life unit). 27 mandatory fields need defaults (Q-33). Possible Boxme approval step (Q-11). Chilled / frozen not supported (R-09) | Phase 1 |
| UC-03 | Look up product data | Should | ✅ (doc) | Product list with keyword filter; Product Update webhook | S2 #7 = 3, #8 = 3; L-02 ✅ | No dedicated detail endpoint | Phase 1 |
| UC-04 | Keep stock in sync | Must | ✅ (doc) | Available Stock Change webhook per event; stock lookup per warehouse and condition | S2 #9 = 5, #29 = 2; L-17 ✅, L-18 ✅, L-19 ✅ | Lookup max 20 SKUs / call (R-02). Must + doc only → confirm by test | Phase 1 |
| UC-05 | Send an inbound shipment (ASN) | Must | 🟡 (doc) | Create ASN with all SKUs; Boxme returns `shipment_code`; duplicate PO rejected | S2 #10 = 5; L-06 🟡, L-13 🟡 | Some warehouses need a separate timeslot booking step. Arrival time format conflict in doc (D-08) | Phase 1 |
| UC-06 | Extra inbound services | Should | ✅ (doc) | `vas.priority_inbound`, `unloading`, `inspection`, `reject_damaged_goods` on Create ASN | S2 #11 = 2 | | Phase 1 |
| UC-07 | Cancel an inbound shipment | Must | ❓ Pending | Cancel ASN endpoint | S2 #12 = 4; L-31 ❓ | Cancel window unknown (Q-07) | Phase 1 |
| UC-08 | Get inbound results | Must | ❓ Pending | Receiving note (GRN): quantity per SKU, condition, batch, expiry; fetched when ASN webhook says Completed | S2 #13 = 4, #28 = 1; L-20 🟡, L-21 ❓, L-26 ❓, L-28 ❓ | Waiting on Q-24 (short receipts), Q-25 (row meaning), Q-28 (condition codes). Status-only webhook accepted by PIC | Phase 1 |
| UC-09 | Send customer orders | Must | ❓ Pending | Create B2C Order (`BM_DBS`), Boxme returns `tracking_number`; duplicates rejected | S2 #14 = 5; L-04 ❓, L-05 ❓, L-14 ❓, L-30 🟡, L-35 ✅, L-39 ✅ | Waiting on Q-22 (duplicate rule / re-send), Q-31 (masked addresses). Rate limit R-01 | Phase 1 |
| UC-10 | Prioritise urgent orders | Should | ✅ (doc) | `fulfill_now` (packed in 45 min), `priority_fulfill` (2 h); TikTok cut-off guidance | S2 #15 = 2; L-36 ✅ | Needs PowerSell's instant / same-day detection (exists per data-model) | Phase 1 |
| UC-11 | Cancel an order before it ships | Must | ❓ Pending (likely 🔁) | Cancel Order endpoint; errors `not_allowed`, `cancelled` | S2 #16 = 4; L-23 ❓, L-31 ❓, L-32 🔴 | Cancel window unknown (Q-07). No single-item cancel (Q-29) → W-01 | Phase 1 with workaround |
| UC-12 | Hand over marketplace AWB | Must | 🟡 (doc) | Order Pack with label URL + tracking number; Update Document | S2 #17 = 5; L-24 🟡, L-33 🟡 | Reversed flow (R-10). Shopee orders without tracking: Q-30 | Phase 1 |
| UC-13 | Track order fulfilment status | Should | 🟡 (doc) | Order Status webhook with times, attempts, failure reasons | S2 #18 = 2, #19 = 2, #30 = 2; L-22 🔴, L-24 🟡, L-41 🟡 | 6 statuses unmapped (Q-26, R-07). Get Order only 60 / min: use webhook | Phase 1 |
| UC-14 | Fulfilment + delivery by Boxme | Should | 🟡 (doc) | Create order with Boxme delivery service; carriers, locations, delivery statuses, COD | S2 #20 = 2, #21 = 2, #22 = 5; L-14 ❓, L-27 🟡, L-34 ✅ | Only if brands want Boxme to deliver (B3) | Later |
| UC-15 | Announce a return | Must | ✅ (doc) | Create Returns Order against the original Boxme order | S2 #23 = 3; L-07 ✅ | Doc conflict on request body (D-07). Must + doc only → confirm by test | Phase 1 |
| UC-16 | Get return results | Must | ❓ Pending | Get Order Returns Receive: quantity per SKU and condition; fetched when return webhook says Returned | S2 #24 = 5, #31 = 1; L-25 ❓, L-26 ❓, L-29 🟡 | Waiting on Q-28 (condition codes). Status-only webhook accepted by PIC | Phase 1 |
| UC-17 | Cancel a return | Must | ❓ Pending | Cancel Returns Order endpoint | S2 #25 = 2; L-31 ❓, L-25 ❓ | Cancel window and response unknown (Q-07, Q-27) | Phase 1 |
| UC-18 | Manage webhook settings | Should | 🟡 (doc) | Set in Boxme's web portal per seller account | S2 #26 = 2, #27 = 2; L-41 🟡 | Not by API; one-time manual per brand (W-02, Q-12) | Phase 1 with manual setup |

**Totals:** ✅ 5 · 🟡 6 · 🔁 0 · ❌ 0 · ➖ 0 · ❓ 7 (all 7 are Must use cases)

### Changed since evaluation (S2)
| S2 row | S2 score | S4 finding | Could the S2 band change? |
|---|---|---|---|
| 16 Cancel outbound | 4 | Single-item cancel not documented (L-32) | No. Even −4 leaves 92 |
| 12, 16, 25 Cancel rows | 4, 4, 2 | Cancel windows unknown (Q-07) | No |

S2 total stays well above 75. The scorecard is not stale.

---

## 3. Workarounds

| W | Use case | Who | What they do | Trigger / frequency | Effort (hrs/week) | Scales with volume? | Risk if missed |
|---|---|---|---|---|---|---|---|
| W-01 | UC-11 | CS (or automated by dev) | Cancel the whole order at Boxme and re-create it without the cancelled item | Per partially cancelled order, [TBD] / week | [TBD] × 5 min (assumption). **0 if automated** | Yes: **not viable long-term if manual** | Cancelled item is shipped anyway |
| W-02 | UC-18 | Ops | Register PowerSell's webhook URL in each brand's Boxme portal account | Once per brand, and when URLs change | 10 min × [n] brands, one-off (assumption) | No | Brand gets no status / stock updates |
| W-03 | All (R-04) | Ops / dev, named owner | Renew each brand's API key (≤ 365 days); re-confirm PowerSell server IPs with Boxme (every 180 days) | Every 6 months | ~15 min × [n] brands per 6 months (assumption) | No | **All Boxme syncs for the brand stop** |

**Total manual effort at current volume:** [TBD], depending on volumes (B6) and whether W-01 is automated.

---

## 4. Scope for API mapping (S5)

### In scope (Phase 1, proposed)
| Flow group | Use cases | Endpoints / webhooks | S3 mapping notes to apply |
|---|---|---|---|
| Config | UC-01 | Get Pickup List | L-08 warehouse vs seller address; L-37 key per brand |
| Product | UC-02, UC-03, UC-04 | Create Product, Update Product, Get Products, Get Category Tree, Get Product Units, Get Stock Available, Stock Report V3; Available Stock Change Push, Product Update Push | L-01 SKU key; L-03 barcodes comma-joined; L-09 volume `LxWxH` (unit Q-21); L-10 grams; L-12 shelf life (Q-08); L-15 defaults + storage condition mapping; L-17 available = condition A |
| Inbound | UC-05, UC-06, UC-07, UC-08 | Create ASN, Create ASN Booking, Get ASN Available Timeslot, Cancel ASN, Get Shipment Detail, Get Receiving Note; Shipment (ASN) Status Push | L-06 references; L-13 epoch time; L-20 / L-21 status rules; L-28 sum condition A |
| Outbound | UC-09, UC-10, UC-11, UC-12, UC-13 | Create B2C Order, Order Pack, Update Document, Cancel Order, Get Order, Get Courier List, Location API (provinces / districts / sub-districts); Order Status Push, Direct RTS | L-04 references; L-14 location IDs; L-24 reversed flow; L-30 out of stock; L-33 label; L-34 COD 0; L-36 priority flags; L-39 duplicates; L-41 webhook handling; status mapping drafts (S3 § 2.1) |
| Return | UC-15, UC-16, UC-17 | Create Returns Order, Get Returns Order, Get Order Returns Receive, Cancel Returns Order; Return Order Status Push | L-07 reference; L-29 quantities; return status mapping draft |
| Webhook | UC-18 | Portal setup per brand (no API) | L-41 reply in 3 s, dedupe `request_id`, ignore older `update_time` |

### Out of scope
| Flow / endpoint | Reason |
|---|---|
| Create B2C Order with Boxme delivery, Get Shipping Option, Get Courier Service, Create Delivery Order, Request Cancel Delivery | UC-14 proposed Later |
| Create B2B Order, B2B customers, B2B pickup timeslot | B2B / offline orders not in the use-case library |
| Reserved Stock | PowerSell doesn't reserve stock at the WMS |
| COD statements, order fees | Finance, not a WMS use case |
| Inventory Change Push, Abnormal Inventory Change Push, Sale Invoice Request | Available Stock Change covers sellable stock; ERP / invoice not in scope |
| Get Inbound Serial List, Get Packed Items | Serial / batch tracking not in Phase 1 use cases |
