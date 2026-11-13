# Boxme – WMS Integration Tracker

| | |
|---|---|
| **Partner** | Boxme |
| **Country** | [TBD] (Boxme operates in Philippines, Thailand, Vietnam) |
| **Overall status** | Active |
| **Current stage** | S3 Validate (waiting on partner) |
| **Next action** | Send question message to Boxme (14 blocking questions); get test account and agree test-order handling with Boxme ops; then run smoke tests |
| **Owner** | [TBD] |
| **Partner contact** | Dedicated contact exists (name [TBD]); doc lists tech@boxme.asia, support@boxme.asia |
| **Brands / ventures requesting** | [TBD] |
| **Target go-live** | [TBD] |
| **Jira epic** | [TBD] |
| **API doc version** | Boxme Open API v2, developers.boxme.asia (103 pages; latest changelog 11-06-2026) |
| **Last updated** | 2026-11-13 |

> Started as a **new partner run** on 2026-11-13. The earlier Boxme V2 mapping (Confluence
> PV 2616950859) was deliberately not used as input.

---

## 🔖 Stage progress

| Stage | Status | Gate | Gate decision | Decided by | Date | Main output |
|---|---|---|---|---|---|---|
| S1 Intake | Done | — | — | — | 2026-11-13 | Endpoint inventory (61 endpoints, below) |
| S2 Evaluate | Done | G1 Go / no-go | Approve | WMS partner PIC | 2026-11-13 | Evaluation scorecard: 96, Proceed |
| S3 Validate | Waiting on partner | G2 Logic understood | | | | System logic notes (42 checks: 13 ✅, 15 🟡, 3 🔴, 11 ❓) |
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
| 2026-11-13 | S2 | "Varies" scores confirmed (rows 5, 7, 8, 9, 11, 13, 17, 19, 21, 22, 24, 27); partner-level rows answered (1, 2, 32, 33, 34). Total 96 | WMS partner PIC | Rows 1, 33, 34 scored by copilot from PIC's facts |
| 2026-11-13 | S2 | Status-only ASN and return webhooks accepted; PowerSell will fetch quantities by API | WMS partner PIC | |
| 2026-11-13 | G1 | **Approve**: proceed to S3 | WMS partner PIC | Score 96. Rate limits (R-01), testing on production (R-03) and IP / key expiry (R-04) carried as risks |

---

## ❓ Partner Q&A log

| ID | Question | Category | Blocking? | Asked on | Answer | Answered on | Affects |
|---|---|---|---|---|---|---|---|
| Q-01 | Is there an API to list Boxme warehouses? | API behaviour | N | — | **Answered by doc:** Get Pickup List returns warehouses (`pickup_id`, `warehouse_code`) | 2026-11-13 | S2 #5, UC-01 |
| Q-02 | Rate limits are per IP (Create Order 2 rps, Create Product 1 rps, Get Order 60/min). PowerSell sends for many sellers from the same servers. Are limits per IP or per API key, and can they be raised for PowerSell? What happens on 11.11 when limits are hit (`traffic_limit` 503)? | Rate limit | Y | | | | S2 #4, L-38, UC-09 |
| Q-03 | How do we send the marketplace AWB / label? | API behaviour | N | — | **Answered by doc:** Order Pack (`shipping_label` URL + `courier_tracking_code`); Update Document (`type: label`) | 2026-11-13 | S2 #17, UC-12 |
| Q-04 | How are webhook URLs registered? | Webhook | N | — | **Partly answered by doc:** in the web portal (oms.boxme.asia), per seller account. See Q-12 | 2026-11-13 | S2 #27, UC-18 |
| Q-05 | Is there a staging environment? | Environment | Y | — | **Answered by PIC:** no staging; Boxme provides a test seller account on production with no financial cost. Test account and API key received 2026-11-13 (stored outside this tracker). Still open: how Boxme ops handles test orders and ASNs (Q-35) | 2026-11-13 | S2 #1–2, S3 smoke tests |
| Q-07 | Until which status can we cancel: an order (Cancel Order), an ASN (Cancel ASN), a return (Cancel Returns Order)? | API behaviour | Y | | | | S2 #12, #16, #25, UC-07, UC-11, UC-17 |
| Q-08 | Shelf-life unit: Create Product says `expiry_threshold` and `min_inbound_shelf_life` are in **days**, Update Product and Get Products say **months**. Which is correct? | Data model | Y | | | | L-12, UC-02 |
| Q-09 | The ASN and return webhooks carry status only. Can received quantities be added? | Webhook | N | — | **Not needed:** PIC accepts fetching quantities by API | 2026-11-13 | S2 #28, #31, UC-08, UC-16 |
| Q-10 | Doc fixes: Create Returns Order has a mandatory field named `01HTPRXX7CJ3BFGXWQTG275SBB`; Direct RTS has `01HYD3H7Z5KMAEP89ME3QJRPJ6`; COD statement paths show `/`; zipcode path shows `/pi/v2/…`; Cancel Returns Order has no documented response. What are the correct values? | API behaviour | N | | | | S2 #3 |
| Q-11 | After Create Product, does Boxme ops need to approve the product before it can be used in an ASN or order? How long does it take, and does Product Update Push tell us when it's approved? | API behaviour | N | | | | UC-02, UC-05 |
| Q-12 | Webhooks are set up per seller account in the web portal. Can PowerSell register one webhook for all its sellers (partner app), or by API? | Webhook | N | | | | S2 #27, UC-18 |
| Q-13 | Due diligence 1: How do you handle traffic spikes, especially during peak sessions and mega campaign days (e.g. 6.6, 11.11, 12.12)? | Due diligence | N | | | | |
| Q-14 | Due diligence 2: What is the average uptime percentage over the past 12 months? | Due diligence | N | | | | |
| Q-15 | Due diligence 3: Could you share performance benchmarks on latency, response time, and API concurrency limits? | Due diligence | N | | | | |
| Q-16 | Due diligence 4: Please highlight response time, concurrent load handling, and system scalability. | Due diligence | N | | | | |
| Q-17 | Due diligence 5: What incident response procedures are in place in case of a data breach? | Due diligence | N | | | | |
| Q-18 | Due diligence 6: Please share details about the scalability, error handling, and response efficiency of each API. | Due diligence | N | | | | |
| Q-19 | Due diligence 7: What backup and disaster recovery plans are in place? | Due diligence | N | | Partly in doc: RTO 8 h, RPO 1 min–24 h | | |
| Q-20 | Due diligence 8: How do you handle API downtime, failures, or outages, and what is the incident response time? | Due diligence | N | | | | |
| Q-21 | What unit is product `volume` (LxWxH): cm or mm? | Data model | Y | | | | L-09, UC-02 |
| Q-22 | Which field is checked for duplicate orders (`referral.order_number`, `store_order_id`, both)? Can an order cancelled for out-of-stock be re-created with the same number? | API behaviour | Y | | | | L-04, L-05, UC-09 |
| Q-23 | In Get Pickup List, how do we tell Boxme warehouses from seller pickup addresses? | Data model | N | | | | L-08, UC-01 |
| Q-24 | If fewer items arrive than expected, does the ASN still end in 6 Completed? | Status | Y | | | | L-21, UC-08 |
| Q-25 | Get Receiving Note: one row per receipt, or one total row per SKU / condition / batch? | API behaviour | Y | | | | L-28, UC-08 |
| Q-26 | Meaning and next step for order statuses 302, 605/606, 704, 706, 708; difference between 300 Shipped and 801 Fulfilled | Status | Y | | | | L-22, UC-13 |
| Q-27 | Return status after Cancel Returns Order; response of that endpoint | Status | Y | | | | L-25, UC-17 |
| Q-28 | Meaning of condition levels L and DE; are D1–D3 all non-sellable? | Status | Y | | | | L-26, UC-08, UC-16 |
| Q-29 | Can part of an order (some items) be cancelled? | API behaviour | Y | | | | L-32, UC-11 |
| Q-30 | Confirm Boxme picks only after Order Pack with label; what to send as `courier_tracking_code` for Shopee orders without tracking; when Direct RTS is sent | API behaviour | Y | | | | L-24, L-33, UC-12 |
| Q-31 | Does Create B2C Order accept masked phone / address? What should we send? | Data model | Y | | | | L-14, UC-09 |
| Q-32 | Which location IDs to send after the new Vietnam location database; how reliable is name-only matching? | Data model | N | | | | L-14, UC-09 |
| Q-33 | Recommended default values for required product fields PowerSell may not hold | Data model | N | | | | L-15, UC-02 |
| Q-34 | Can webhooks arrive out of order? Is `update_time` reliable? Is the webhook token the same for all sellers? | Webhook | N | | | | L-41 |
| Q-35 | How should test orders and ASNs on the production test account be handled so the warehouse doesn't process them? | Environment | Y | | | | S3 smoke tests, R-03 |

(Q-06 merged into Q-02.)

---

## ⚠️ Risks & gaps

| ID | Risk / gap | Use case | Workaround | Owner | Status |
|---|---|---|---|---|---|
| R-01 | Rate limits per IP (Create Order 2 rps ≈ 7,200 orders/hour across **all** PowerSell sellers on Boxme; Get Order 60/min) | UC-09, UC-13 | Queue order creation; use Order Status Push instead of polling; ask for higher limits (Q-02) | [TBD] | Open |
| R-02 | Get Stock Available: max 20 SKUs per call, 1 rps (≈ 2 min for a 2,000-SKU full check) | UC-04 | Use Available Stock Change Push day to day; full check only for reconciliation | [TBD] | Open |
| R-03 | No staging: testing uses a test seller account on production. Test orders and ASNs may enter the real warehouse queue | All | Agree a test plan with Boxme ops (which test orders get cancelled, who watches the queue) before S3 smoke tests | [TBD] | Open |
| R-04 | Since 25/07/2026: IP whitelist (re-confirm every 180 days) and API keys expire after max 365 days. If missed, all calls fail (403 / 401) | All | Calendar reminders; alert on 401 / 403; one owner per seller account | [TBD] | Open |
| R-05 | ASN and return webhooks carry no quantities | UC-08, UC-16 | Fetch receiving note (GRN) / returns-receive when status is Completed / Returned | [TBD] | Accepted by PIC 2026-11-13 |
| R-07 | 6 Boxme order statuses have no PowerSell match (302, 605/606, 704, 706, 708; 801 vs 300 unclear) | UC-13 | Decide mapping after Q-26 | [TBD] | Open |
| R-08 | No partial (line-level) order cancellation documented | UC-11 | Full cancel and re-create (to discuss in S4) after Q-29 | [TBD] | Open |
| R-09 | Boxme storage conditions are Normal or Air-con only; chilled / frozen products have no match | UC-02 | Check in S4 whether requesting brands sell chilled / frozen goods | [TBD] | Open |
| R-10 | Marketplace orders: Boxme picks only after PowerSell sends the AWB (Order Pack), the reverse of most WMS. Delays in getting the AWB delay picking | UC-09, UC-12 | Confirm (Q-30); check against PowerSell RTS logic in S4 | [TBD] | Open |
| R-06 | Create Product needs 27 mandatory fields, some of which PowerSell may not hold (Boxme category ID, packing material, wholesale price, GS1 flag) | UC-02 | Default rules per field (S3 check L-15) | [TBD] | Open |

---

## ✍️ Artifacts

| Artifact | Link | Version / date | Status |
|---|---|---|---|
| Partner API document | https://developers.boxme.asia/doc-393601 (full export uploaded by user) | Latest changelog 11-06-2026 | Current |
| Endpoint inventory | Below | 2026-11-13 | Current |
| Evaluation scorecard | `Boxme-API-Evaluation-Scorecard.md` (Confluence: [TBD]) | 2026-11-13, confirmed | Current |
| System logic notes | `Boxme-System-Logic-Notes.md` (Confluence: [TBD]) | 2026-11-13, from doc only | Current: smoke tests not run |

---

## 🗒️ Activity log

| Date | What happened |
|---|---|
| 2026-11-13 | New partner run started. Doc host blocked from the copilot's environment; user uploaded llms.txt index, then a full export of all 103 pages |
| 2026-11-13 | S1 done: 61 endpoints inventoried (44 good, 9 partial, 8 missing samples) |
| 2026-11-13 | S2 draft scorecard: 72 / Proceed with caveats. Waiting on PIC to confirm 13 "varies" rows and score rows 1, 2, 32, 33, 34 before G1 |
| 2026-11-13 | PIC confirmed scores; total 96 / Proceed. G1 presented for decision |
| 2026-11-13 | G1 approved by PIC. S3 started: logic notes, 42 checks, draft status mappings, 23-step smoke test plan, partner question message drafted (not sent). Waiting on Boxme answers and test account |
| 2026-11-13 | Boxme test seller account and API key received (production, no cost). Credentials kept out of this tracker. Copilot environment cannot reach `s.boxme.asia` (blocked network, and Boxme requires a whitelisted calling IP), so smoke tests will run from a whitelisted machine |

---

# Appendix – Endpoint inventory – Boxme Open API v2

Base URL (production only, as documented): `https://s.boxme.asia`. Auth header:
`Authorization: Token <API key>` (key created per seller account in oms.boxme.asia).
Error cases are documented centrally (Common Errors, Order Error Codes). Only Create
Product and Create ASN show an error example on the endpoint itself.

| # | Flow group | Endpoint name | Method | Path | Direction | Doc quality | Note |
|---|---|---|---|---|---|---|---|
| 1 | Config | Province | GET | `/api/v3/location/{country_code}/provinces/` | PowerSell → Partner | Good |  |
| 2 | Config | District | GET | `/api/v3/location/{country_code}/provinces/{province_id}/districts/` | PowerSell → Partner | Good |  |
| 3 | Config | Sub-district | GET | `/api/v2/sellers/locations/{country_code}/provinces/{province_id}/districts/{district_id}/sub-districts` | PowerSell → Partner | Good |  |
| 4 | Config | Lookup zipcode | GET | `/pi/v2/sellers/locations/{country_code}/zipcodes` | PowerSell → Partner | Partial | Path typo `/pi/v2/` in doc |
| 5 | Config | Get Pickup List | GET | `/api/v2/sellers/pickup` | PowerSell → Partner | Missing samples | Lists Boxme warehouses (`pickup_id`, `warehouse_code`) |
| 6 | Config | Create Pickup Address | POST | `/api/v2/sellers/pickup/create` | PowerSell → Partner | Good |  |
| 7 | Config | Active / Deactive Pickup | PUT | `/api/v2/sellers/pickup/{pickup_id}/toggle-active` | PowerSell → Partner | Good |  |
| 8 | Product | Create Product | POST | `/api/v2.1/sellers/products/create/` | PowerSell → Partner | Good | 27 mandatory fields; 1 rps |
| 9 | Product | Get Category Tree | GET | `/api/v2.1/sellers/products/categories/` | PowerSell → Partner | Good |  |
| 10 | Product | Get Products | GET | `/api/v2.1/sellers/products/list` | PowerSell → Partner | Missing samples | 1 rps, 30/min |
| 11 | Product | Get Product Units | GET | `/api/v2.1/sellers/products/uom` | PowerSell → Partner | Good |  |
| 12 | Product | Deactive Product | PUT | `/api/v2.1/sellers/products/selling/` | PowerSell → Partner | Partial |  |
| 13 | Product | Update Product | PUT | `/api/v2.1/sellers/products/update/{bsin}/` | PowerSell → Partner | Good |  |
| 14 | Product | Get Stock Available | POST | `/api/v2.1/sellers/products/get_stock/` | PowerSell → Partner | Good | Max 20 SKUs; 1 rps |
| 15 | Product | Reserved Stock | PUT | `/api/v2.1/sellers/products/update_reserve/` | PowerSell → Partner | Partial | Max 20 SKUs |
| 16 | Product | Get Stock Report | POST | `/api/v2/sellers/wms/products/report/stocks/` | PowerSell → Partner | Good | Batch / expiry; 1 rps, 30/min |
| 17 | Product | Get Stock Report (V3) | POST | `/api/v3/public/inventory/report-stocks/` | PowerSell → Partner | Good |  |
| 18 | Inbound | Create Inbound Shipment (ASN) | POST | `/api/v2/sellers/shipments/` | PowerSell → Partner | Good | Duplicate PO rejected |
| 19 | Inbound | Cancel ASN | POST | `/api/v2/sellers/shipments/cancel/{shipment_code}/` | PowerSell → Partner | Good |  |
| 20 | Inbound | Get Shipment Detail | GET | `/api/v2/sellers/shipments/{shipment_code}/` | PowerSell → Partner | Good |  |
| 21 | Inbound | Get Receiving Note (GRN) | GET | `/api/v2/sellers/shipments/receiving/{shipment_code}/` | PowerSell → Partner | Good |  |
| 22 | Inbound | Get Inbound Serial List | GET | `/api/v2/sellers/shipments/receiving_serial/{shipment_code}/` | PowerSell → Partner | Good |  |
| 23 | Inbound | Create ASN Booking | POST | `/api/v2/sellers/shipments/booking/create/` | PowerSell → Partner | Good | Timeslot booking |
| 24 | Inbound | Get ASN Available Timeslot | POST | `/api/v2/sellers/shipments/booking/get-time-slots/` | PowerSell → Partner | Good |  |
| 25 | Inbound | Cancel ASN Booking | POST | `/api/v2/sellers/shipments/booking/cancel/{booking_id}/` | PowerSell → Partner | Good |  |
| 26 | Inbound | Get Shipment List | GET | `/api/v2/sellers/shipments/` | PowerSell → Partner | Good |  |
| 27 | Outbound | Get Shipping Option (Fulfillment) | POST | `/api/v2/courier/pricing/calculate` | PowerSell → Partner | Good |  |
| 28 | Outbound | Get Shipping Option (Dropship) | POST | `/api/v2/courier/pricing/calculate` | PowerSell → Partner | Good |  |
| 29 | Outbound | Create B2C Order | POST | `/api/v2/courier/pricing/b2c/create_order` | PowerSell → Partner | Good | 2 rps/IP; `BM_DBS` for marketplace shipping |
| 30 | Outbound | Create Delivery Order | POST | `/api/v2/courier/pricing/ship/create_order` | PowerSell → Partner | Good |  |
| 31 | Outbound | Create B2B Order | POST | `/api/v2/courier/pricing/b2b/create_order` | PowerSell → Partner | Good |  |
| 32 | Outbound | Update Document | PUT | `/api/v2/orders/{tracking_number}/update_document/` | PowerSell → Partner | Partial | Label / invoice / PO upload |
| 33 | Outbound | Request Cancel Delivery Order | POST | `/api/v2/orders/cancel-delivery/{tracking_number}/` | PowerSell → Partner | Partial | After shipped; limited sellers |
| 34 | Outbound | Cancel Order | POST | `/api/v2/orders/cancel/{tracking_number}/` | PowerSell → Partner | Good |  |
| 35 | Outbound | Get Order | GET | `/api/v2/orders/{tracking_number}/` | PowerSell → Partner | Missing samples | 60 req/min |
| 36 | Outbound | Get Order List | GET | `/api/v2/orders/list` | PowerSell → Partner | Missing samples | 1 rps, 30/min |
| 37 | Outbound | Get Courier List | GET | `/api/v2/courier/names` | PowerSell → Partner | Good |  |
| 38 | Outbound | Get Courier Service | GET | `/api/v2/courier/services` | PowerSell → Partner | Good |  |
| 39 | Outbound | Get Packed Items | GET | `/api/v2/orders/pack/{tracking_number}/` | PowerSell → Partner | Missing samples |  |
| 40 | Outbound | Order Pack | PUT | `/api/v2/orders/fulfill/pack/` | PowerSell → Partner | Good | Label + courier tracking for marketplace shipping; `fulfill_type` priority / now |
| 41 | Outbound | Get B2B Pickup TimeSlot | GET | `/api/v2/courier/pricing/b2b/pickup-time-slots` | PowerSell → Partner | Good |  |
| 42 | Outbound | Get Tracking | GET | `/api/v2/orders/tracking/{tracking_number}/` | PowerSell → Partner | Good |  |
| 43 | Return | Create Returns Order | POST | `/api/v2/orders/rma/create/{tracking_number}/` | PowerSell → Partner | Partial | Placeholder mandatory field `01HTPRXX…` in doc |
| 44 | Return | Get Returns Order | GET | `/api/v2/orders/rma/list/` | PowerSell → Partner | Partial |  |
| 45 | Return | Get Order Returns Receive | GET | `/api/v2/orders/rma/received/{return_tracking_number}/` | PowerSell → Partner | Partial |  |
| 46 | Return | Cancel Returns Order | DELETE | `/api/v2/orders/rma/cancel/{return_tracking_number}/` | PowerSell → Partner | Missing samples | Response not documented |
| 47 | Other | Create B2B Customer | POST | `/api/v2/orders/customers/create/` | PowerSell → Partner | Good |  |
| 48 | Other | Get Customer | GET | `/api/v2/orders/customers/list/` | PowerSell → Partner | Good |  |
| 49 | Other | Update Customer | PUT | `/api/v2/orders/customers/update/{customer_id}/` | PowerSell → Partner | Good |  |
| 50 | Other | Get COD Statements List | GET | `/` | PowerSell → Partner | Missing samples | Path shown as `/` |
| 51 | Other | Get COD Statement Transactions | GET | `/` | PowerSell → Partner | Missing samples | Path shown as `/` |
| 52 | Other | Get Order Fee | POST | `/host/api/v2/orders/finance/order_fees/{tracking_number}/` | PowerSell → Partner | Good |  |
| 53 | Webhook | Shipment (ASN) Status Push | POST (to our URL) | — | Partner → PowerSell | Good | Status only, no quantities |
| 54 | Webhook | Available Stock Change Push | POST (to our URL) | — | Partner → PowerSell | Good | Sellable stock |
| 55 | Webhook | Inventory Change Push | POST (to our URL) | — | Partner → PowerSell | Good | Physical stock |
| 56 | Webhook | Order Status Push | POST (to our URL) | — | Partner → PowerSell | Good | Excludes returns |
| 57 | Webhook | Return Order Status Push | POST (to our URL) | — | Partner → PowerSell | Good | Status only, no quantities |
| 58 | Webhook | Product Update Push | POST (to our URL) | — | Partner → PowerSell | Good |  |
| 59 | Webhook | Direct RTS | POST (to our URL) | — | Partner → PowerSell | Partial | Lazada RTS; placeholder field `01HYD3…` in doc |
| 60 | Webhook | Sale Invoice Request | POST (to our URL) | — | Partner → PowerSell | Good | ERP invoice request |
| 61 | Webhook | Abnormal Inventory Change Push | POST (to our URL) | — | Partner → PowerSell | Good | Damage / loss / cycle count reason |
