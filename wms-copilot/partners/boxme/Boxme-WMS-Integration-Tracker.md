# Boxme – WMS Integration Tracker

| | |
|---|---|
| **Partner** | Boxme |
| **Country** | [TBD] (doc mentions Philippines, Thailand, Vietnam warehouse network) |
| **Overall status** | Active |
| **Current stage** | S1 Intake |
| **Next action** | Get full API page content (only the doc index has been read) |
| **Owner** | [TBD] |
| **Partner contact** | [TBD] |
| **Brands / ventures requesting** | [TBD] |
| **Target go-live** | [TBD] |
| **Jira epic** | [TBD] |
| **API doc version** | Boxme Open API, developers.boxme.asia (latest changelog entry 11-06-2026) |
| **Last updated** | 2026-11-13 |

> Started as a **new partner run** on 2026-11-13. The earlier Boxme V2 mapping (Confluence
> PV 2616950859) was deliberately not used as input.

---

## 🔖 Stage progress

| Stage | Status | Gate | Gate decision | Decided by | Date | Main output |
|---|---|---|---|---|---|---|
| S1 Intake | In progress | — | — | — | | Endpoint inventory (index only) |
| S2 Evaluate | Not started | G1 Go / no-go | | | | Evaluation scorecard |
| S3 Validate | Not started | G2 Logic understood | | | | System logic notes |
| S4 Use-case fit | Not started | G3 Scope agreed | | | | Use-case fit page |
| S5 API mapping | Not started | G4 Mapping approved | | | | API mapping document |
| S6 Dev & testing | Not started | — | — | — | | Jira stories, QC test cases |
| S7 UAT | Not started | G5 UAT sign-off | | | | UAT script |
| S8 Launch | Not started | G6 Go-live | | | | Go-live checklist |
| S9 Adoption | Not started | — | — | — | | Adoption metrics |

---

## ✅ Decision log

| Date | Stage / gate | Decision | Decided by | Conditions / reason |
|---|---|---|---|---|
| 2026-11-13 | S1 | Run Boxme as a new partner, without reusing the old Boxme V2 mapping | WMS partner PIC | Test of the updated copilot |

---

## ❓ Partner Q&A log

| ID | Question | Category | Blocking? | Asked on | Answer | Answered on | Affects |
|---|---|---|---|---|---|---|---|
| Q-01 | Is there an API to list Boxme warehouses available to a seller? None appears in the doc index | API behaviour | N | | | | S2 #5, UC-01 |
| Q-02 | "Get Order" is limited to 60 requests per **minute**. What are the limits for other endpoints, and are they per seller or per partner? | Rate limit | Y | | | | S2 #4, L-38 |
| Q-03 | Is "Update Document" the way to send the marketplace AWB / shipping label? | API behaviour | N | | | | S2 #17, UC-12 |
| Q-04 | How are webhook URLs registered: by API, in the seller portal, or by Boxme support? | Webhook | N | | | | S2 #27, UC-18 |

---

## ⚠️ Risks & gaps

| ID | Risk / gap | Use case | Workaround | Owner | Status |
|---|---|---|---|---|---|
| R-01 | Get Order rate limit 60 req/min, far below the 60 calls/sec checklist bar | UC-13 | Rely on Order Status Push webhook instead of polling | [TBD] | Open (from doc index only) |
| R-02 | Get Stock Available accepts max 20 SKUs per call | UC-04 | Batch calls; rely on Inventory Change Push webhook | [TBD] | Open (from doc index only) |

---

## ✍️ Artifacts

| Artifact | Link | Version / date | Status |
|---|---|---|---|
| Partner API document | https://developers.boxme.asia/doc-393601 | Latest changelog 11-06-2026 | Current (index read; page content not yet read) |
| Endpoint inventory | Below | 2026-11-13 | Draft: names only |

---

## 🗒️ Activity log

| Date | What happened |
|---|---|
| 2026-11-13 | New partner run started. Doc host blocked from the copilot's environment; user uploaded llms.txt index. Draft endpoint inventory built from page titles only. Waiting on full page content |

---

# Appendix – Endpoint inventory – Boxme Open API (draft from doc index)

Method, path and doc quality are filled in once the pages are read.

| # | Flow group | Endpoint name | Method | Path | Direction | Doc quality | Note |
|---|---|---|---|---|---|---|---|
| 1 | Config | Province | ? | ? | PowerSell → Partner | Not read | Location codes by country |
| 2 | Config | District | ? | ? | PowerSell → Partner | Not read | |
| 3 | Config | Sub-district | ? | ? | PowerSell → Partner | Not read | |
| 4 | Config | Lookup zipcode | ? | ? | PowerSell → Partner | Not read | VN new location database (changelog 25/10/2025) |
| 5 | Config | Get Pickup List | ? | ? | PowerSell → Partner | Not read | Seller pickup addresses, not warehouses |
| 6 | Config | Create Pickup Address | ? | ? | PowerSell → Partner | Not read | |
| 7 | Config | Active / Deactive Pickup | ? | ? | PowerSell → Partner | Not read | |
| 8 | Product | Create Product | ? | ? | PowerSell → Partner | Not read | |
| 9 | Product | Get Category Tree | ? | ? | PowerSell → Partner | Not read | |
| 10 | Product | Get Products | ? | ? | PowerSell → Partner | Not read | |
| 11 | Product | Get Product Units | ? | ? | PowerSell → Partner | Not read | |
| 12 | Product | Deactive Product | ? | ? | PowerSell → Partner | Not read | |
| 13 | Product | Update Product | ? | ? | PowerSell → Partner | Not read | |
| 14 | Product | Get Stock Available | ? | ? | PowerSell → Partner | Not read | Max 20 SKUs per call |
| 15 | Product | Reserved Stock | ? | ? | PowerSell → Partner | Not read | Max 20 SKUs, per warehouse |
| 16 | Product | Get Stock Report | ? | ? | PowerSell → Partner | Not read | Expiry date, batch / lot |
| 17 | Product | Get Stock Report (V3) | ? | ? | PowerSell → Partner | Not read | |
| 18 | Inbound | Create Inbound Shipment (ASN) | ? | ? | PowerSell → Partner | Not read | |
| 19 | Inbound | Cancel ASN | ? | ? | PowerSell → Partner | Not read | |
| 20 | Inbound | Get Shipment Detail | ? | ? | PowerSell → Partner | Not read | Inbound qty by SKU, proof of delivery |
| 21 | Inbound | Get Receiving Note (GRN) | ? | ? | PowerSell → Partner | Not read | |
| 22 | Inbound | Get Inbound Serial List | ? | ? | PowerSell → Partner | Not read | |
| 23 | Inbound | Create ASN Booking | ? | ? | PowerSell → Partner | Not read | Timeslot booking |
| 24 | Inbound | Get ASN Available Timeslot | ? | ? | PowerSell → Partner | Not read | |
| 25 | Inbound | Cancel ASN Booking | ? | ? | PowerSell → Partner | Not read | |
| 26 | Inbound | Get Shipment List | ? | ? | PowerSell → Partner | Not read | |
| 27 | Outbound | Get Shipping Option (Fulfillment) | ? | ? | PowerSell → Partner | Not read | |
| 28 | Outbound | Get Shipping Option (Dropship) | ? | ? | PowerSell → Partner | Not read | Non-fulfillment |
| 29 | Outbound | Create B2C Order | ? | ? | PowerSell → Partner | Not read | |
| 30 | Outbound | Create Delivery Order | ? | ? | PowerSell → Partner | Not read | Non-fulfillment |
| 31 | Outbound | Create B2B Order | ? | ? | PowerSell → Partner | Not read | |
| 32 | Outbound | Update Document | ? | ? | PowerSell → Partner | Not read | AWB upload? (Q-03) |
| 33 | Outbound | Request Cancel Delivery Order | ? | ? | PowerSell → Partner | Not read | After shipped; limited sellers |
| 34 | Outbound | Cancel Order | ? | ? | PowerSell → Partner | Not read | |
| 35 | Outbound | Get Order | ? | ? | PowerSell → Partner | Not read | 60 req/min |
| 36 | Outbound | Get Order List | ? | ? | PowerSell → Partner | Not read | By time or status |
| 37 | Outbound | Get Courier List | ? | ? | PowerSell → Partner | Not read | |
| 38 | Outbound | Get Courier Service | ? | ? | PowerSell → Partner | Not read | |
| 39 | Outbound | Get Packed Items | ? | ? | PowerSell → Partner | Not read | Packed qty, expiry, batch; from RTS |
| 40 | Outbound | Order Pack | ? | ? | PowerSell → Partner | Not read | Confirm ready to pack |
| 41 | Outbound | Get B2B Pickup TimeSlot | ? | ? | PowerSell → Partner | Not read | |
| 42 | Outbound | Get Tracking | ? | ? | PowerSell → Partner | Not read | |
| 43 | Return | Create Returns Order | ? | ? | PowerSell → Partner | Not read | |
| 44 | Return | Get Returns Order | ? | ? | PowerSell → Partner | Not read | Qty accepted, proof of delivery |
| 45 | Return | Get Order Returns Receive | ? | ? | PowerSell → Partner | Not read | |
| 46 | Return | Cancel Returns Order | ? | ? | PowerSell → Partner | Not read | |
| 47 | Other | Create B2B Customer | ? | ? | PowerSell → Partner | Not read | |
| 48 | Other | Get Customer | ? | ? | PowerSell → Partner | Not read | |
| 49 | Other | Update Customer | ? | ? | PowerSell → Partner | Not read | |
| 50 | Other | Get COD Statements List | ? | ? | PowerSell → Partner | Not read | Finance |
| 51 | Other | Get COD Statement Transactions | ? | ? | PowerSell → Partner | Not read | Finance |
| 52 | Other | Get Order Fee | ? | ? | PowerSell → Partner | Not read | Finance |
| 53 | Webhook | Shipment (ASN) Status Push | — | — | Partner → PowerSell | Not read | |
| 54 | Webhook | Available Stock Change Push | — | — | Partner → PowerSell | Not read | For self-managed inventory OMS |
| 55 | Webhook | Inventory Change Push | — | — | Partner → PowerSell | Not read | |
| 56 | Webhook | Order Status Push | — | — | Partner → PowerSell | Not read | Excludes return orders |
| 57 | Webhook | Return Order Status Push | — | — | Partner → PowerSell | Not read | |
| 58 | Webhook | Product Update Push | — | — | Partner → PowerSell | Not read | |
| 59 | Webhook | Direct RTS | — | — | Partner → PowerSell | Not read | "Avoid PNR issue" |
| 60 | Webhook | Sale Invoice Request | — | — | Partner → PowerSell | Not read | ERP invoice |
| 61 | Webhook | Abnormal Inventory Change Push | — | — | Partner → PowerSell | Not read | |

**Not seen in the index (to confirm once pages are read):** get warehouse list (Q-01).
