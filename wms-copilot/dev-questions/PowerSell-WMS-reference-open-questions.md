# PowerSell WMS reference – open questions for dev

| | |
|---|---|
| **Owner** | WMS partner PIC |
| **Asked to** | PowerSell dev lead (sections 1–4), module owners (section 5) |
| **Reply by** | [date] |
| **Status** | Waiting on answers |
| **Prepared** | 2026-11-12 |

## Why we're asking

The WMS copilot uses one reference for PowerSell's own fields and statuses. It was built
from 21 existing WMS mapping documents in Confluence (space PV). Those documents disagree
with each other in 23 places, and contain some likely mistakes. Until dev confirms the
correct answer, every new partner mapping either has to guess (risky: guesses flow into
Jira tickets and get built) or stop and ask again.

**One round of answers here removes those questions from every future partner
integration.**

## How to answer

- Fill in the **Answer** column. Where options are listed, writing the option letter is
  enough (e.g. "A"). Add a note if the answer is "it depends".
- **Copilot proposal** is a suggestion based on how many partner docs use each option.
  It is not a confirmed fact. Feel free to overrule it.
- "Don't know / not used any more" is a useful answer too.
- Section 4 is a fix list, not questions: just confirm who updates each page.

## Contents
- [1. Field questions (12)](#1-field-questions)
- [2. Status questions (10)](#2-status-questions)
- [3. Partner statuses with no PowerSell mapping (7 partners)](#3-partner-statuses-with-no-powersell-mapping)
- [4. Fixes needed in existing Confluence pages](#4-fixes-needed-in-existing-confluence-pages)
- [5. Use-case library: for module owners](#5-use-case-library-for-module-owners)

Partner codes: OF Onflow · TN TNSL · BW BoostWare · ES EASYSPAD · IM IM Logistics ·
LEL Lazada MCL · BL BetterLand · FL Flash · TA TitipAja · BM Boxme · MC MyCloud ·
NH N&H · SnT.

---

## 1. Field questions

### Priority order

Answer these first. They affect every partner's product, order and return mapping:
**C2** (order references), **C1** (product IDs), **C9** (customer address), **C8**
(return reference), **C7** (return quantities).

| ID | Question | Options and current usage | Copilot proposal | Answer | Answered by |
|---|---|---|---|---|---|
| C1 | What do `wms_product.partner_id` and `wms_product.partner_key` hold? | **A.** `partner_id` = partner's internal product ID, `partner_key` = partner SKU code (OF, BW, LEL) · **B.** `partner_id` = partner SKU code, `partner_key` = partner internal ID (TN, ES, IM, SnT, TA, NH) · FL has no partner product ID and keys on `product.barcode`. BL contradicts itself | None. Usage is split, and the model doc (OF) differs from the majority | | |
| C2a | What do `wms_sale_order.so_code` and `wms_sale_order.partner_so_id` mean? | `partner_so_id` is used for: the partner's order code (TN, ES, FL), our marketplace order no. (BW), Boxme tracking no. (BM), N&H tracking code (NH), our order number (SnT). `so_code` is used for: our reference (TN, ES, IM), the partner's order ID (BW, BL, FL webhook), the platform order no. (BM) | `so_code` = the reference PowerSell **sends**; `partner_so_id` = the reference the WMS **returns** (fits TN, ES, IM) | | |
| C2b | Which order number is the default to send to a new WMS? | **A.** `order.order_number` (TN, ES, IM, LEL, SnT) · **B.** `order.sc_order_number` (BW, FL, TA) · **C.** both (OF; BL sends `order.id` + `sc_order_number`) | A (5 partners) | | |
| C3 | Which field holds the AWB / shipping label file? | **A.** `order_billing.info.awb_url` (TN, SnT, TA) · **B.** `order_billing.info.url_awb` (ES, IM, BL) · **C.** `auto_processing_order.awb_path` (BW, LEL). Are A/B one field with a typo, and is C a different thing (stored file vs channel URL)? | None. Split 3 / 3 / 2 | | |
| C4 | Shelf-life fields: are they under `product.info.`? (`expiry_threshold`, `reject_shelf_life`, `shelf_life_alert`) | **A.** `product.info.*` (OF, TN, FL) · **B.** `product.*` (BW, LEL) | A (includes the model doc and the most recent docs) | | |
| C5a | `product.package_weight` and `product.product_weight`: two different fields? Which is the default to send? | `package_weight` (OF, TN, ES, IM, FL) · `product_weight` (BW, LEL, BL, FL, TA). FL uses both, for different partner fields | Keep both; default `package_weight` for shipping weight. Please confirm | | |
| C5b | Fragile flag path | **A.** `product.info.is_fragile` (OF) · **B.** `product.is_fragile` (ES) · IM writes `Product.Is_fragile` | None | | |
| C6 | What should `wms_asn.reference_no` hold, and where do goods receipt numbers (GRNs) go? | `reference_no` = partner ref code (TN), partner ASN UUID (BW), partner PO code (OF). GRN in `wms_asn.wms_reference_no` (SnT only). One ASN can have several GRNs | None | | |
| C7 | Which fields store returned quantities (good / damaged)? | **A.** `wms_exchange_order_item.accepted_quantity` / `damaged_quantity` (OF, BW, LEL, BL) · **B.** `total_accepted_quantity` / `total_damaged_quantity` (ES, IM) · **C.** `total_received_quantity` / `total_receipt_quantity` (TN, BL) · **D.** `order_return_reconcile.accepted_qty` / `damaged_qty` (SnT) | A (4 partners). Are B and C aggregates of A? | | |
| C8 | Where is the partner's return reference stored? What is `wms_ref_code`? | **A.** `wms_exchange_order.wms_ref_no` (OF, TN, LEL, BL, NH) · **B.** `order_return_reconcile.wms_ref_no` (BW, SnT, OF). `wms_exchange_order.wms_ref_code` also used (TN, FL, NH) | A (5 partners); `wms_ref_code` = partner's display number? | | |
| C9 | Which customer / address fields should new mappings use? | **A.** `order_customer.*` (BW, ES, IM, BL, FL, TA) · **B.** `customer.*` + `address.*` + `location.*` (OF, TN, SnT) · **C.** `shipping_customer.*` (BM). Which one holds the latest address after a buyer edits it, and which handles masked addresses? | A (6 partners), but the model doc (OF) uses B. Please confirm | | |
| C11 | ASN received quantity field | `wms_asn_detail.quantity_received` (all except LEL) vs `received_quantity` (LEL) | `quantity_received`; LEL doc is a typo | | |
| C12 | ASN notes: header level, line level, or both? | `wms_asn.special_instruction` (most) vs `wms_asn_detail.special_handling_instructions` (LEL) | Header `special_instruction` default; line level only if the DB has it | | |
| C13 | Default field for the return reason | **A.** `order_return_reconcile_item.detail_reason` (TN, BL, NH, SnT) · **B.** `order_return.dispute_reason` (BW) · **C.** `order_return.dispute_text_reason` (LEL) | A for WMS returns. Are B and C the channel's reason, a different thing? | | |

---

## 2. Status questions

| ID | Question | What the docs say | Copilot proposal | Answer | Answered by |
|---|---|---|---|---|---|
| S1 | BoostWare `cancelled` (9000) is mapped to "Sent successfully". Intended? | BW mapping doc | Likely an error: map to Canceled | | |
| S2 | SnT stores the partner's own values as backend status (Process, Ready to ship, Loaded, Cancel). Should they map to PowerSell's backend list? | SnT mapping doc | Yes: Process → Picking, Ready to ship → Packed, Loaded → Shipped, Cancel → Canceled. Please confirm | | |
| S3 | Return status "Closed" (accepted = expected): is it live for all WMS, or only in the cross-WMS return doc? | Return doc only; partner docs use Received | None | | |
| S4 | ASN status "New": real for all WMS, or only BW, TA, ZTO? | BW, TA, ZTO | None | | |
| S5 | Legacy order statuses "Failed to delivery" and "Partial Returned" (2022 doc): still used? | WMS status management (legacy) | Remove from the model if not in the database | | |
| S6 | Flash statuses 120–180: "Being sent" (main doc) or "Sent successfully" (offline order doc)? | Flash main vs offline doc | None | | |
| S7 | LEL `ready_to_shipped` → Shipped. Other partners map "ready to ship" → Packed. Should LEL be Packed? | LEL vs BW, BL, SnT, MC | Packed, unless LEL `ready_to_shipped` means handed to carrier | | |
| S8 | MyCloud maps packing → Packed and delivered → Shipped. Align with other WMS? Is MyCloud live? | MC doc (2024-01, early draft) | Archive the MyCloud mapping if not live | | |
| S9 | TitipAja "Fully Received (40)" → Pending Receipt; only "ASN Closed (99)" → Completed. Intended? | TA doc | None. The general rule is Completed when received = expected | | |
| S10 | Should "Cancelled" be a display status for all WMS? Today only FL shows it; other partners leave cancelled orders unmapped | FL vs all | Yes, make it standard | | |

---

## 3. Partner statuses with no PowerSell mapping

These partner statuses appear in the source docs with no PowerSell status assigned. For
each partner: **is it live**, and if so, which PowerSell status should each map to? If the
answer is "these never happen in practice", say so.

| Partner | Live? | Unmapped statuses | Answer |
|---|---|---|---|
| LEL | | created_failed, inbound, delivery_failed, failed, delivered, canceled, cancel_failed, request_failed, oos, reinbound_* | |
| BM | | ASN Cancelled / Cancelled by operator; return 501–503 | |
| ZTO | | Order shipped (5000) in the main doc; return new / released / partial / received / cancelled | |
| NH | | RETURN_FAIL_RETURN (220) | |
| IM | | Entire return status mapping is empty | |
| BW | | Return cancelled | |
| TN | | `3pl_picked_up_from_seller` (marked TBD) | |

---

## 4. Fixes needed in existing Confluence pages

Likely mistakes in source pages. Please confirm each one and who will fix the page.

| # | Page | Issue | Suggested fix | Confirmed? | Fixed by |
|---|---|---|---|---|---|
| F1 | LEL V2 (2835349505) | Payment mapping looks inverted (COD → `NON_COD`) | Swap the mapping | | |
| F2 | LEL V2 | Dimensions say "convert to gram" | "convert to cm" (or mm, per LEL spec) | | |
| F3 | LEL V2 | `serial_number_flag` mapped from `product.storage_type` | Map from `product.serial_imei_management` | | |
| F4 | BetterLand (2805202946) | Order webhook maps `TrackingNo` → `wms_sale_order.status` | → `wms_sale_order.tracking_number` | | |
| F5 | BetterLand | Product IDs contradict between endpoints | Align after C1 is answered | | |
| F6 | Flash (1287421953) | Shelf-life note mentions "TNSL" (copy-paste) | Remove / correct the note | | |
| F7 | Flash | Create response and webhook disagree on `partner_so_id` / `so_code` | Align after C2a is answered | | |
| F8 | N&H Return (3828482524) | `group_platform` → `wms_exchange_order.wms_ref_no` | Map the partner's return reference instead | | |
| F9 | N&H Return | Expected qty calculated as received − damaged | Expected = quantity announced at return creation | | |
| F10 | IM Logistics – Return (3828776973) | Return status mapping section is empty | Fill in after section 3 is answered | | |
| F11 | BW, ES, IM, BL | Typo `product.inventory sku` | `product.inventory_sku` | | |
| F12 | BL | Typo `product.info.min stock alert` | `product.info.min_stock_alert` | | |
| F13 | IM | `Product.Is_fragile` | Path confirmed in C5b | | |
| F14 | SnT | `wms_asn.special_instrcution` | `wms_asn.special_instruction` | | |
| F15 | FL | `wms_asn.asn_partner_id` | `wms_asn.partner_asn_id` | | |
| F16 | TN | `wms_product.partner.id` | `wms_product.partner_id` | | |
| F17 | BW | `order_return.order_created.at` | `order_return.order_created_at` (confirm) | | |

---

## 5. Use-case library: for module owners

The copilot checks every new partner against 18 business use cases. Priorities were
seeded from the evaluation checklist and are still draft. Please confirm or correct.

**Order & Return Management owner**: UC-09 to UC-17
**Inventory Management owner**: UC-04
**Inbound Shipment (ASN) owner**: UC-05 to UC-08
**Warehouse owner**: UC-01 to UC-03

| UC | Use case | Draft priority | Draft module | Question | Answer |
|---|---|---|---|---|---|
| UC-02 | Register new products in the warehouse | Must | Warehouse [confirm] | Is Warehouse the right module? | |
| UC-03 | Look up product data held by the warehouse | Varies | Warehouse [confirm] | Is Warehouse the right module? | |
| UC-05 | Send an inbound shipment (ASN) | Must | Inbound Shipment (ASN) / Purchase Order [confirm] | Which module owns this, ASN or PO? | |
| UC-10 | Prioritise urgent orders | Should | Order & Return Management | With instant / same-day growth on TikTok Shop and Shopee, should this be Must? | |
| UC-14 | Fulfilment + delivery by the WMS | Should | Order & Return Management / 3PL Management [confirm] | Which module owns this? | |
| UC-18 | Manage webhook settings without the partner | Should | **[TBD]** | Which module owns webhook settings? | |
| All | All 18 priorities | Draft | | Any priority you disagree with? | |
