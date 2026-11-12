# Use case → evidence map (S4 Step 2)

Where to look to rate each use case. Checklist rows are from the S2 scorecard (35-criteria
checklist). Logic checks are from S3 (`wms-partner-logic-validation`, L-01 to L-42).

| Use case | S2 checklist rows | S3 logic checks | Typical endpoints / webhooks |
|---|---|---|---|
| UC-01 Know which warehouses a brand uses | 5 | L-08 | Get warehouse list |
| UC-02 Register new products | 6 | L-01, L-02, L-03, L-09, L-10, L-11, L-12, L-15, L-16 | Create product (update product) |
| UC-03 Look up product data | 7, 8 | L-02 | Get product list, get product detail |
| UC-04 Keep stock in sync | 9, 29 | L-17, L-18, L-19 | Get inventory; stock webhook |
| UC-05 Send an inbound shipment (ASN) | 10 | L-06, L-12, L-13 | Create inbound / ASN / PO |
| UC-06 Extra inbound services | 11 | — | Inbound create options / VAS fields |
| UC-07 Cancel an inbound shipment | 12 | L-31 | Cancel inbound |
| UC-08 Get inbound results | 13, 28 | L-20, L-21, L-26, L-28, L-41 | Get inbound detail; inbound webhook |
| UC-09 Send customer orders | 14 | L-04, L-05, L-13, L-14, L-19, L-30, L-35, L-39 | Create outbound |
| UC-10 Prioritise urgent orders | 15 | L-36 | Outbound priority flag / service type |
| UC-11 Cancel an order before it ships | 16 | L-23, L-31, L-32 | Cancel outbound |
| UC-12 Hand over marketplace AWB | 17 | L-24, L-33 | Upload AWB / label |
| UC-13 Track order fulfilment status | 18, 19, 30 | L-22, L-24, L-30, L-41 | Get order detail / list; outbound status webhook |
| UC-14 Fulfilment + delivery by the WMS | 20, 21, 22 | L-14, L-27, L-34 | Create delivery order; get carriers; get locations |
| UC-15 Announce a return | 23 | L-07 | Create return |
| UC-16 Get return results | 24, 31 | L-25, L-26, L-29, L-41 | Get return detail; return webhook |
| UC-17 Cancel a return | 25 | L-31 | Cancel return |
| UC-18 Manage webhook settings | 26, 27 | L-41 | Webhook registration (API or UI) |

**Cross-cutting** (apply to all use cases; report once at the top of the matrix if 🔴):
L-37 authentication · L-38 rate limit and pagination · L-40 error format ·
L-42 staging vs production parity. Checklist rows 1–4 and 32–35 are partner-level and
are not use-case evidence.

If a logic check result is `🔴` for a use case's check, the use case can be at best 🟡,
or 🔁 if the gap needs manual handling.
