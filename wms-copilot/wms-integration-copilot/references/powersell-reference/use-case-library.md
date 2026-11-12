# PowerSell WMS use-case library

**Status: DRAFT.** Seeded from the 35-criteria evaluation checklist. Confirm priorities and
module owners before treating this as final.

Every partner is checked against **all** use cases below (stage S4), and every Phase 1
use case gets a UAT scenario (stage S7).

## Priority meaning

| Priority | Meaning | Source |
|---|---|---|
| **Must** | Without it, the process is blocked or needs heavy manual work | Checklist max score 3–5 |
| **Should** | Brings clear benefit to daily operations, but not blocking | Checklist max score 2 |
| **Varies** | Depends on the brand's setup (e.g. single-warehouse, webhook already covers it). Decide per partner and confirm with the WMS partner PIC | Checklist "varies" rows |

## Use cases

| ID | Use case | Flow group | PowerSell module (draft) | Priority | Checklist # | Supported means |
|---|---|---|---|---|---|---|
| UC-01 | Know which warehouses a brand uses at the partner | Config | Warehouse | Varies | 5 | PowerSell can list the brand's warehouses at the partner and map them. Not needed for single-warehouse setups. |
| UC-02 | Register new products in the warehouse | Product | Warehouse [confirm] | Must | 6 | A new SKU in PowerSell is created in the WMS with the same SKU code and the details the WMS needs, without manual entry. |
| UC-03 | Look up product data held by the warehouse | Product | Warehouse [confirm] | Varies | 7, 8 | PowerSell can read back product list and details from the WMS to check they match. |
| UC-04 | Keep stock in sync | Product / Webhook | Inventory Management | Varies (pull) + Should (push) | 9, 29 | Stock in PowerSell matches the WMS per warehouse, split by condition and stock type, updated soon after any change. |
| UC-05 | Send an inbound shipment (ASN) to the warehouse | Inbound | Inbound Shipment (ASN) / Purchase Order [confirm] | Must | 10 | An inbound shipment created in PowerSell is created in the WMS with all SKUs and expected quantities, and PowerSell gets the WMS reference back. |
| UC-06 | Request extra inbound services (priority, unloading, inspection) | Inbound | Inbound Shipment (ASN) | Varies | 11 | PowerSell can request these services together with the inbound shipment. |
| UC-07 | Cancel an inbound shipment | Inbound | Inbound Shipment (ASN) | Must | 12 | Cancelling in PowerSell cancels it in the WMS before receiving starts; after that, the WMS gives a clear reason. |
| UC-08 | Get inbound results (received quantity, condition) | Inbound / Webhook | Inbound Shipment (ASN) | Varies (pull) + Should (push) | 13, 28 | PowerSell receives actual received quantities per SKU and condition, without anyone typing them in. A webhook can replace the detail endpoint. |
| UC-09 | Send customer orders for fulfillment | Outbound | Order & Return Management | Must | 14 | A confirmed marketplace order is sent to the WMS automatically and the WMS confirms it with its own reference. |
| UC-10 | Prioritise urgent orders (e.g. instant / same-day) | Outbound | Order & Return Management | Should | 15 | Orders flagged as urgent are picked ahead of standard orders. |
| UC-11 | Cancel an order before it ships | Outbound | Order & Return Management | Must | 16 | Cancelling in PowerSell stops the order in the WMS if not yet shipped; otherwise the WMS clearly says it's too late. |
| UC-12 | Hand over the marketplace shipping label (AWB) | Outbound | Order & Return Management | Varies | 17 | The marketplace AWB reaches the WMS before packing, so the parcel ships with the right label. |
| UC-13 | Track order fulfillment status | Outbound / Webhook | Order & Return Management | Should (+ Varies for order list) | 18, 19, 30 | Each order's warehouse status shows in PowerSell without anyone checking the WMS manually. |
| UC-14 | Fulfillment + delivery by the WMS (own last-mile) | Outbound | Order & Return Management / 3PL Management [confirm] | Should (+ Varies for carriers, locations) | 20, 21, 22 | Only if the partner offers delivery. PowerSell can send the delivery order with carrier and address in the partner's location format. |
| UC-15 | Announce a return (failed delivery, customer return) | Return | Order & Return Management | Must | 23 | PowerSell can tell the WMS about an incoming return before it arrives. |
| UC-16 | Get return results (received quantity, condition) | Return / Webhook | Order & Return Management | Varies (pull) + Should (push) | 24, 31 | PowerSell receives returned quantities and condition per SKU, without manual entry. |
| UC-17 | Cancel a return | Return | Order & Return Management | Must | 25 | A return announced by mistake can be cancelled before it arrives. |
| UC-18 | Manage webhook settings without the partner's help | Webhook | [TBD] | Should (+ Varies for self-config) | 26, 27 | The PowerSell team can register and change webhook URLs directly. |

## Not covered by use cases (scored in evaluation only)

Checklist rows 1–4 (staging environment, staging/production consistency, documentation
quality, rate limits) and 32–35 (dedicated contact, response rate, bug fixing,
enhancements) describe the partner, not a business flow. They feed the S2 score and the
S3 logic notes, not the S4 matrix.

## Change log

| Date | Change | By |
|---|---|---|
| | Initial draft from the evaluation checklist | |
