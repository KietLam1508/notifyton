# Boxme API Evaluation Scorecard

**Recommendation: Proceed** (to be decided at G1)
**Total score: 96 — Band: >75**

Boxme's API covers every PowerSell flow. Stock, outbound, instant / same-day and order
status features are strong. All "varies" rows and partner-level rows were confirmed by the
WMS partner PIC on 2026-11-13. Caveats to carry into S3:
- **Rate limits are low and counted per IP address.** Create Order is 2 requests per
  second; Get Order is 60 per minute. All PowerSell brands share them. This is the only
  row scored 0.
- **No staging environment.** Testing uses a Boxme test account on production (no cost).
- **Inbound and return webhooks carry status only.** Quantities need an extra call;
  the PIC accepts this.

Even if every partner-level row (1, 2, 32, 33, 34) were 0, the total would be 85, still
above 75. The band is not sensitive to these judgement calls.

| | |
|---|---|
| **Spec evaluated** | Boxme Open API v2, developers.boxme.asia (103 pages; latest changelog 11-06-2026) |
| **Evaluated on** | 2026-11-13 |
| **Evaluated by** | WMS integration copilot (draft for WMS partner PIC) |

---

## Scorecard

| Group | No. | Scope | Yes/No? | API Ref | Score | Note |
|:-:|:-:|:-|:-:|:-|:-:|:-|
| **API Docs** | | | | | **96** | **WMS meets most of PowerSell's key flow requirements: Proceed** |
| **Webpage** | | | | | **5** | |
| | 1 | Staging environment | No, test account on production | — | 2 | No staging. Boxme provides a test seller account **on production** with no financial cost (PIC, 2026-11-13). Risk: test orders and ASNs enter the real warehouse queue, so tests must be coordinated with Boxme ops |
| | 2 | UI/UX & functionality consistency staging vs production | Yes (same environment) | — | 3 | Tests run on production itself, so behaviour is identical |
| **API** | | | | | **5** | |
| | 3 | API documentation clearly describes every endpoint with real sample request/response | Yes, partial | All 61 endpoints in OpenAPI format | 3 | Good: OpenAPI per endpoint, flow diagrams, full status lists, active changelog. Deductions: 10 endpoints lack a sample response; only 2 show an error example; a mandatory field in Create Returns is named `01HTPRXX7CJ3BFGXWQTG275SBB` (placeholder); COD statement paths are `/`; zipcode path typo `/pi/v2/…`; shelf-life unit is days in Create Product but months in Update Product |
| | 4 | API call limit ≥ 60 calls/sec per endpoint, per shop | No | — | 0 | Limits are **per IP**: Create Order 2 rps, Create Product 1 rps, Get Stock 1 rps, Get Products / Order List 1 rps and 30 per min, **Get Order 60 per min**. Every PowerSell brand calls from the same servers, so they all share one limit |
| | 5 | Get warehouse list | Yes | `GET /api/v2/sellers/pickup` | 2 *(confirmed)* | The "pickup list" includes Boxme warehouses (`pickup_id`, `warehouse_code`). `pickup_id` is used on every ASN, order, stock and return call |
| **API - Product** | | | | | **14** | |
| | 6 | Create products | Yes | `POST /api/v2.1/sellers/products/create/` | 3 | Keeps our `seller_sku`. 27 mandatory fields, including Boxme category ID, packing material and wholesale price. Products may need Boxme ops approval before use. 1 rps |
| | 7 | Get product list | Yes | `GET /api/v2.1/sellers/products/list` | 3 *(confirmed)* | Paged; filters on active, approved, keyword |
| | 8 | Get product detail | Yes, via list | `GET /api/v2.1/sellers/products/list?keyword=` | 3 *(confirmed)* | No separate detail endpoint. The Product Update Push webhook covers changes |
| | 9 | Get inventory: per warehouse, stock conditions, stock types | Yes | `POST /api/v2.1/sellers/products/get_stock/` | 5 *(confirmed)* | Excellent breakdown: per warehouse; condition A / D1–D3; stock, awaiting, reserved, available, incoming, damaged. Max 20 SKUs per call, 1 rps. Batch and expiry stock via Stock Report V3 |
| **API - Inbound** | | | | | **15** | |
| | 10 | Create inbound shipment | Yes | `POST /api/v2/sellers/shipments/` | 5 | Rejects duplicate PO numbers (`po_number_duplicated`). Some warehouses need a separate timeslot booking step (Create ASN Booking) |
| | 11 | VAS for inbound: priority inbound, unload, inspection | Yes | `vas.priority_inbound` / `unloading` / `inspection` / `reject_damaged_goods` | 2 *(confirmed)* | All three services supported, plus reject damaged goods at receiving |
| | 12 | Cancel inbound shipment | Yes | `POST /api/v2/sellers/shipments/cancel/{shipment_code}/` | 4 | Doesn't say until which ASN status cancelling is allowed (Q-07) |
| | 13 | Get inbound detail: received quantity, conditions | Yes | `GET /api/v2/sellers/shipments/{code}/` + `GET …/receiving/{code}/` (GRN) | 4 *(confirmed)* | The receiving note (GRN) gives quantity per SKU per condition, plus batch and expiry. **Needed**: the ASN webhook has no quantities |
| **API - Outbound** | | | | | **29** | |
| | 14 | Create outbound (fulfillment only) | Yes | `POST /api/v2/courier/pricing/b2c/create_order` + `PUT /api/v2/orders/fulfill/pack/` | 5 | Two steps for marketplace-shipped orders: create (`delivery_service: BM_DBS`), then Order Pack with the label. Province / district / sub-district IDs are mandatory, but names are accepted for auto-matching. Rejects duplicate orders (`DUPLICATED_ORDER`) |
| | 15 | VAS for outbound: priority | Yes | `fulfillment_vas.fulfill_now` / `priority_fulfill`; Order Pack `fulfill_type` | 2 | Instant (packed within 45 min) and priority (packed within 2 h) flows are documented, including TikTok Shop dispatch-rate guidance |
| | 16 | Cancel outbound | Yes | `POST /api/v2/orders/cancel/{tracking_number}/` | 4 | Error codes `not_exists` / `cancelled` / `not_allowed`. Cancel window can be inferred from the status flow but isn't stated (Q-07). Cancel after shipping: limited sellers only |
| | 17 | Upload AWB | Yes | Order Pack `shipping_label`, `self_shipment.courier_tracking_code`; `PUT /api/v2/orders/{tn}/update_document/` (`type: label`) | 5 *(confirmed)* | Label URL (PDF / PNG, 10×15 cm) is required on Order Pack for marketplace-shipped orders |
| | 18 | Get order detail | Yes | `GET /api/v2/orders/{tracking_number}/` | 2 | Rich fields (status, SLAs, timestamps). No sample response. 60 per min: Boxme advises using webhooks instead |
| | 19 | Get order list | Yes | `GET /api/v2/orders/list` | 2 *(confirmed)* | Filter by time and status; 30 per min |
| | 20 | Create outbound (fulfillment + delivery) | Yes | Create B2C Order with `delivery_service` from Get Shipping Option | 2 | Boxme delivery with COD. Also non-fulfillment Create Delivery Order |
| | 21 | Get carriers | Yes | `GET /api/v2/courier/names`, `/courier/services`, `POST /courier/pricing/calculate` | 2 *(confirmed)* | Only needed if Boxme delivers |
| | 22 | Get locations | Yes | `/api/v3/location/{cc}/provinces/`, districts, sub-districts, zipcodes | 5 *(confirmed)* | **Needed even for fulfillment only**: `ship_to` province / district / sub-district IDs are mandatory. New Vietnam location database since 25/10/2025 |
| **API - Return** | | | | | **10** | |
| | 23 | Create return: failed delivery, customer return | Yes | `POST /api/v2/orders/rma/create/{tracking_number}/` | 3 | Linked to the original Boxme order. 12 reason codes. Placeholder mandatory field in doc (see #3). Failed deliveries Boxme itself delivered come back inside the order flow (420 → 600) |
| | 24 | Get return: received quantity, conditions | Yes | `GET /api/v2/orders/rma/list/` + `GET /api/v2/orders/rma/received/{rt}/` | 5 *(confirmed)* | Quantity per SKU with condition, batch and expiry. **Needed**: the return webhook has no quantities |
| | 25 | Cancel return | Yes | `DELETE /api/v2/orders/rma/cancel/{rt}/` | 2 | Response not documented at all; cancel window not stated |
| **Webhook** | | | | | **10** | |
| | 26 | Webhook available | Yes | 9 events | 2 | Signed with a token; retries after 2 min, 30 min and 3 h; `request_id` for duplicate detection; reply 200 within 3 s |
| | 27 | Users can self-configure webhook URL | Yes, in the Boxme web portal | oms.boxme.asia | 2 *(confirmed)* | Set up in the web portal per seller account, not by API (Q-12) |
| | 28 | Inbound status & item receipt update | Partial | Shipment (ASN) Status Push | 1 | Status and received / completed time only. No per-SKU quantities: fetch the receiving note (GRN) on Completed. **Accepted by PIC** |
| | 29 | Inventory (stock) quantity update | Yes | Inventory Change Push; Available Stock Change Push | 2 | Real-time, per warehouse and condition, with change amount and source document. Available Stock Change suits sellable-stock sync |
| | 30 | Outbound status update | Yes | Order Status Push | 2 | Every status change, plus delivery attempts, failure reasons and SLA timestamps |
| | 31 | Return status & item receipt update | Partial | Return Order Status Push | 1 | Status only. Quantities via Get Order Returns Receive. **Accepted by PIC** |
| **Communication channel** | | | | | **4** | |
| | 32 | Has dedicated resource? | Yes | — | 2 | Dedicated contact confirmed by PIC from experience |
| | 33 | Response rate | Yes, moderate | — | 2 | Usually within 2 working days (PIC). Slow for live incidents on campaign days: agree an urgent channel before go-live |
| **System changes flexibility** | | | | | **4** | |
| | 34 | Bug fixing | Yes, case by case | — | 2 *(confirmed)* | Bug reports acknowledged quickly; fix time case by case (PIC) |
| | 35 | System enhancement | Yes (evidence in doc) | Changelog 2024–2026 | 2 | Steady releases: new order fields, inventory webhooks, instant / same-day flows, security upgrade |

---

## Scoring reference

| Score | Meaning |
|:-:|:-|
| 0 | Not supported / No |
| 1 | Nice to have, no impact to daily operational / implementation |
| 2 | Nice to have, brings benefit to daily operational / implementation |
| 3 | Must have, impacts daily operational / implementation; workaround exists short-term |
| 4 | Must have, large impact; workaround exists but wastes human effort, not viable long-term |
| 5 | Must have, critical impact; process completely blocked if missing |

| Total score | Result |
|:-:|:-|
| > 75 | Meets most of PowerSell's key flow requirements: **Proceed** |
| 60–75 | Can adapt some key flows; manual workarounds still needed: **Proceed with caveats** |
| < 60 | Disqualified: **Do not proceed** |

---

## Confirmation record

All "varies" rows and partner-level rows were confirmed by the WMS partner PIC on
2026-11-13.

| No. | Scope | Copilot proposal | Confirmed | Basis |
|:-:|:-|:-:|:-:|:-|
| 1 | Staging environment | 0 | 2 | Test account on production, no cost |
| 2 | Staging vs production consistency | 0 | 3 | Same environment |
| 5 | Get warehouse list | 2 | 2 | |
| 7 | Get product list | 1 | 3 | PIC |
| 8 | Get product detail | 1 | 3 | PIC |
| 9 | Get inventory | 3 | 5 | PIC |
| 11 | Inbound VAS | 2 | 2 | |
| 13 | Get inbound detail | 4 | 4 | |
| 17 | Upload AWB | 5 | 5 | |
| 19 | Get order list | 1 | 2 | PIC |
| 21 | Get carriers | 1 | 2 | PIC |
| 22 | Get locations | 3 | 5 | PIC |
| 24 | Get return detail | 3 | 5 | PIC |
| 27 | Self-configure webhook | 1 | 2 | PIC |
| 32 | Dedicated resource | 0 | 2 | Dedicated contact exists |
| 33 | Response rate | 0 | 2 | Usually within 2 working days |
| 34 | Bug fixing | 0 | 2 | Reports acknowledged fast; fixes case by case |

Rows 1, 33 and 34: the PIC described the facts, and the copilot turned them into
scores. Change them if you see it differently. They can't move the band.

---

## Due-diligence questions for partner

| No. | Question | Answer |
|:-:|:-|:-|
| 1 | How do you handle traffic spikes, especially during peak sessions and mega campaign days (e.g. 6.6, 11.11, 12.12)? | |
| 2 | What is the average uptime percentage over the past 12 months? | |
| 3 | Could you share performance benchmarks on latency, response time, and API concurrency limits? | |
| 4 | Please highlight response time, concurrent load handling, and system scalability. | |
| 5 | What incident response procedures are in place in case of a data breach? | |
| 6 | Please share details about the scalability, error handling, and response efficiency of each API. | |
| 7 | What backup and disaster recovery plans are in place? | *Partly answered in doc: RTO 8 h; RPO 1 min (application / database failure) to 24 h (cloud datacenter failure); AWS / GCP* |
| 8 | How do you handle API downtime, failures, or outages, and what is the incident response time? | |

---

## Next step

Gate G1 (go / no-go) can be decided now. If approved, S3 starts: validating how Boxme's
system really behaves, using the Boxme test account on production. The first blocking
questions are rate limits (Q-02), cancel windows (Q-07) and the shelf-life unit (Q-08).
