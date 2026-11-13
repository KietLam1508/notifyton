# Boxme – System Logic Notes

| | |
|---|---|
| **API doc version** | Boxme Open API v2, developers.boxme.asia (latest changelog 11-06-2026) |
| **Staging tested on** | Not yet. No staging; tests will use a Boxme test seller account on production |
| **Last updated** | 2026-11-13 |
| **Tracker** | `Boxme-WMS-Integration-Tracker.md` |

## G2 readiness – Logic understood

**Status:** Not ready. 11 checks wait on Boxme's answers (14 blocking questions), and no
smoke test has run yet: the test account and the test-order process with Boxme ops are
still to be arranged (Q-05, Q-35).

| # | Condition | Met? | Note |
|---|---|---|---|
| 1 | No ❓ logic check in must-have flows | ❌ | 11 open: L-04, L-05, L-09, L-12, L-14, L-21, L-23, L-25, L-26, L-28, L-31 |
| 2 | All blocking partner questions answered | ❌ | Q-02, Q-07, Q-08, Q-21, Q-22, Q-24 to Q-31, Q-35 |
| 3 | Smoke tests passed for product, inbound, outbound, cancel outbound, return | ❌ | Not run. Needs test account (Q-05) and test-order plan (Q-35) |
| 4 | Every must-have partner status maps to one PowerSell status, or is a listed gap | ✅ | Unmapped order statuses listed as R-07 |
| 5 | Every 🔴 gap is in Risks & gaps with an owner | ❌ | R-01, R-07, R-08 listed; owners [TBD] |

**Logic checks:** ✅ (doc) 12 · ✅ (PIC) 1 · 🟡 15 · 🔴 3 · ❓ 11 · ➖ 0

**Biggest findings:**
1. **The marketplace order flow is reversed compared with most WMS partners.**
   - Elsewhere, the WMS packs first, and its "packed" event triggers Ready To Ship on the
     channel.
   - With Boxme, PowerSell must get the marketplace AWB first, then call Order Pack with
     the label. Boxme only starts picking after that.
   - Instant orders are the exception: pack first, confirm on the channel after Ready to
     ship (L-24).
2. **Boxme has only two storage conditions** (Normal, Air-con). Chilled and frozen
   products have no match (L-15).
3. **No way to cancel part of an order** is documented (L-32).
4. **6 order statuses have no PowerSell meaning yet** (L-22).

---

## 1. System logic notes

### 1.1 How the partner models things

| Topic | Partner behaviour | Source |
|---|---|---|
| Warehouse / client / brand structure | One API key per seller account (oms.boxme.asia). Warehouses are identified by `pickup_id`; the same "pickup" list also holds seller pickup addresses (`warehouse_code` seems to tell them apart) | Authentication; Get Pickup List; Q-23 |
| Product (SKU) identity | Our `seller_sku` is kept. Boxme assigns its own ID `bsin` (e.g. `BSN33152982758216`). Multiple barcodes as a comma-separated `barcode_manufacturer`. Products may need Boxme ops approval | Create / Update Product; Q-11 |
| Order identity | We send `referral.order_number` (our number) and `referral.store_order_id` (marketplace number). Boxme returns `tracking_number` (`BM…`), the key for every later call. One order = one parcel in practice (`shipments.parcels[]`), splits not documented | Create B2C Order |
| Inbound identity | We send `po_number` (unique; duplicates rejected). Boxme returns `shipment_code` (`SM-VN-…`). Receipts read from the receiving note (GRN) as rows per SKU / condition / batch, with no separate GRN number | Create ASN; Get Receiving Note |
| Return identity | Created against the original Boxme `tracking_number`, plus our return number and the courier tracking number. Boxme returns `return_tracking_number` (`BM…RT`). Boxme-delivered failed deliveries return inside the order lifecycle (420 → 600) without a separate return | Create Returns Order; Order status flow |

### 1.2 Lifecycles

| Object | Partner statuses in order | Final statuses | Can cancel until |
|---|---|---|---|
| Inbound (ASN) | 1 New → 12 Awaiting Reservation → 2 Ready-to-ship → 4 In-transit → 10 Received → 11 Partial inspection → 6 Completed | 6 Completed, 5 Cancelled, 7 Cancelled by operator | Not documented (Q-07) |
| Outbound (marketplace-shipped) | 110 Awaiting Label → 201 Label generated → 210 Awaiting process → 217 Processing → 211 Ready to ship → 280 Waiting to handover → 300/301 Shipped → 801 Fulfilled. Side paths: 212 Out of stock, 302 Courier refused | 801 Fulfilled, 705 Cancelled at warehouse, 700/701/703 cancelled, 708 Cancelled by lost item | Flow diagram: seller cancel possible until 210 Awaiting process; after that Boxme cancels "at warehouse" (705). Not stated for the API (Q-07) |
| Outbound (Boxme delivers) | As above, then 304 In-transit → 310 Out for delivery → 800 Delivered, or 400 failed attempt → 410 re-delivery / 420 → 430 → 600 Returned; 605/606 destroyed at hub | 800, 600, 605/606, 705 | After shipped: Request Cancel Delivery (limited sellers) |
| Return | 201 Label generated → 501 Awaiting to receive → 502 Received → 503 Inspected → 600 Returned (put away, stock up) | 600 Returned. No cancelled status documented | Not documented (Q-07, Q-27) |

### 1.3 How updates reach PowerSell

| Update | Webhook? | Polling endpoint? | Real-time or batch? | Payload: full or changed fields |
|---|---|---|---|---|
| Inbound received | Shipment (ASN) Status Push (`shipment.status.change`): status + times only | Get Receiving Note (quantities); Get Shipment Detail | Real-time per status change | Status only; quantities by API (accepted by PIC) |
| Stock change | Available Stock Change Push (`product.available.change`, sellable); Inventory Change Push (`product.stock.change`, physical); Abnormal Inventory Change Push | Get Stock Available (20 SKUs, 1 rps); Stock Report V3 | Real-time per event | Full quantities **and** `adjust` delta, per warehouse and condition |
| Outbound status | Order Status Push (`order.status.change`); Direct RTS (`order.direct.rts`, Lazada) | Get Order (60/min); Get Order List (30/min) | Real-time | Full status + times |
| Return received | Return Order Status Push (`return_order.status.change`): status only | Get Order Returns Receive (quantities) | Real-time | Status only; quantities by API |

### 1.4 Technical rules

| Topic | Behaviour |
|---|---|
| Authentication and token expiry | Static API key per seller account: `Authorization: Token <key>`. No refresh. Max lifetime 365 days (since 25/07/2026). Calling IPs must be whitelisted and re-confirmed every 180 days |
| Rate limit (per shop or per partner?) | **Per IP**: Create Order 2 rps; Create Product, Get Stock, Order Pack-related 1 rps; list endpoints 1 rps and 30/min; Get Order 60/min. Exceeding gives `traffic_limit` / `quota_limit` (503) |
| Pagination | `page` + `page_size` (25 / 50 / 100); `total_count` returned |
| Duplicate protection | Create Order `DUPLICATED_ORDER`; Create ASN `po_number_duplicated`; Create Product `seller_sku_existed` (returns existing `bsin` in `additional_infos`). Webhooks: dedupe on `request_id` |
| Timezone / date format | Unix epoch seconds everywhere; display converted using the record's `country` |
| Units | Weight in grams. Volume as text `LxWxH` (unit not stated, example `27x36x11`). Shelf life in months; expiry thresholds in days **or** months (doc conflict, Q-08). Prices as numbers in the market currency; TH COD integer only |
| Error format and codes | `{error, error_code, messages, request_id, error_data, additional_infos}`. Readable codes (`NOT_ENOUGH_ITEM`, `SHIP_TO_ADDRESS_INVALID`, `not_allowed`…) |
| Webhook retry, signature, ordering | Must answer HTTP 200 within 3 s; retries after 2 min, 30 min, 3 h. Static `Authorization: <WEBHOOK_TOKEN>` header (not a signature over the body). Ordering not documented (Q-34) |

---

## 2. Logic check results

| ID | Check | Result | Partner behaviour | Evidence | Mapping note / action |
|---|---|---|---|---|---|
| L-01 | Product key | ✅ (doc) | Keeps `seller_sku` as the key | Create Product | `product.inventory_sku` → `seller_sku` |
| L-02 | Partner product ID | ✅ (doc) | Returns `bsin`; stable; used in update path | Create / Update Product | Store `bsin` in `wms_product.partner_id` `[CONFIRM: C1]` |
| L-03 | Multiple barcodes | ✅ (doc) | `barcode_manufacturer` comma-separated | Create Product | Join `product.barcode` + `product.backup_barcode` with commas |
| L-04 | Order number accepted / echoed / unique | ❓ | We send `referral.order_number` + `referral.store_order_id`; Boxme key is `tracking_number`. Which field triggers `DUPLICATED_ORDER` isn't stated | Create B2C Order; Error Codes | Q-22. Proposed: `order.order_number` → `referral.order_number`, `order.sc_order_number` → `referral.store_order_id` `[CONFIRM: C2]`; store `tracking_number` in `wms_sale_order.partner_so_id` `[CONFIRM: C2]` |
| L-05 | Re-send after out-of-stock / loss | ❓ | 212 Out of stock → Cancelled by seller; 708 Cancelled by lost item. Re-use of order number after cancel not documented | Order status flow | Q-22 |
| L-06 | Inbound references | 🟡 (doc) | `po_number` (unique) → `shipment_code`; GRN as rows, no GRN number | Create ASN; Get Receiving Note | Send `wms_purchase_order.code` if any, else `wms_asn.code`, as `po_number`; store `shipment_code` in `wms_asn.partner_asn_id`. No GRN number to store `[CONFIRM: C6]` |
| L-07 | Return reference | ✅ (doc) | Needs original `tracking_number`; returns `return_tracking_number` | Create Returns Order | Store `BM…RT` as partner return reference `[CONFIRM: C8]` |
| L-08 | Warehouse model | 🟡 (doc) | `pickup_id` on every call; pickup list mixes Boxme warehouses and seller addresses | Get Pickup List | Map `wms_warehouse.partner_warehouse_id` ← `pickup_id` for entries with `warehouse_code`; Q-23 |
| L-09 | Dimension unit | ❓ | `volume` is a text `LxWxH`, unit not stated | Create Product example `27x36x11` | Q-21. If cm: `"{package_length}x{package_width}x{package_height}"` from PowerSell cm |
| L-10 | Weight unit, which weight | 🟡 (doc) | One `weight`, grams | Create Product | Send PowerSell grams as-is; which PowerSell weight `[CONFIRM: C5]` |
| L-11 | Price / currency | 🟡 (doc) | Number in market currency (`config.currency`); TH COD integers only | Create Order; Create Product | Round TH COD up to integer before sending |
| L-12 | Shelf life | ❓ | `shelf_life` months ✅. `expiry_threshold` and `min_inbound_shelf_life`: **days** in Create, **months** in Update / Get | Create vs Update Product | Q-08. `product.expiration_time` (months) → `shelf_life`; thresholds `[CONFIRM: C4]` |
| L-13 | Timezone / date | 🟡 (doc) | Unix epoch seconds | All endpoints | Convert PowerSell local times to epoch; convert back for display using `country` |
| L-14 | Address format, masked addresses | ❓ | Province / district / sub-district **IDs mandatory**; names accepted for auto-recognition; Vietnam location database changed 25/10/2025. Masked addresses not mentioned | Create B2C Order; Location API; changelog | Q-31, Q-32. Source fields `[CONFIRM: C9]` |
| L-15 | Mandatory product fields PowerSell may not hold | 🟡 (doc) | 27 mandatory fields | Create Product | Defaults needed (Q-33): `category_id` (Boxme tree), `pack_material`, `uom` (PC), `is_digital` false, `wholesale_price`, `managed_by_gs1` false, `use_shredded_paper` false, `protective_packaging_inbound` false, `allow_breakdown` false. `product.storage_type` → `warehouse_condition`: Ambient → 1, Air-con → 2, **Chilled / Freezer → no match** (flag in S4). `product.valuation_method` → `outbound_strategy` (FMFO no match) |
| L-16 | Product update | 🟡 (doc) | Update supported; after Boxme approval only some fields change, then re-approval | Update Product | Name editable only before first ASN. Sync rule needed for approved products |
| L-17 | Stock split | ✅ (doc) | Per `pickup_id` and condition; stock / awaiting / reserved / available / incoming / damaged | Get Stock Available | `wms_product.available_quantity` ← `available_quantity` (condition A) = `product_stock.open_stock` |
| L-18 | Stock change delivery | ✅ (doc) | Webhooks per event, full quantities + delta | Inventory webhook reference | Subscribe to Available Stock Change; use full `available_quantity`, not the delta |
| L-19 | Bundles | ✅ (doc) | Accepts components; UOM `SET` exists | Product API overview | Keep PowerSell rule: split bundles before sending |
| L-20 | Inbound status list | 🟡 (doc) | 9 statuses (see 2.1) | ASN status list | Draft mapping in 2.1 |
| L-21 | Final status when received < expected | ❓ | Completed (6) = "completed putaway all items"; short receipts not described | ASN status list | Q-24. PowerSell rule: Completed only if received = expected |
| L-22 | Outbound status list | 🔴 | 28 status codes; 6 without a clear PowerSell match | Order API overview | Draft mapping in 2.1; Q-26; Risk R-07 |
| L-23 | Cancelled at each outbound stage | ❓ | 700 by seller (before 210), 705 at warehouse (after processing), 706 waiting for cancellation, `not_allowed` error | Order status flow; Cancel Order | Q-07 |
| L-24 | "Ready for carrier" event | 🟡 (doc) | **Reversed flow for marketplace-shipped orders**: PowerSell gets the AWB from the channel first, then calls Order Pack with label + tracking; Boxme picks after that. **Instant** orders: Order Pack with `store_order_id`, confirm on channel after 211 Ready to ship. Lazada: Direct RTS webhook | API Call Flow; Instant Order Flow; Direct RTS | Q-30. S4 must check this against PowerSell's current RTS logic |
| L-25 | Return status list | ❓ | 201, 501, 502, 503, 600; no cancelled status | Returns order status | Q-27. Draft mapping in 2.1 |
| L-26 | Item condition codes | ❓ | A, D1, D2, D3, L, DE | Get Receiving Note filter | Q-28. Draft: A → Good; D1–D3 → Damaged; L, DE unknown |
| L-27 | Delivery statuses (if Boxme delivers) | 🟡 (doc) | 304, 310, 400, 410, 420, 430, 600, 800, 605/606; failed reasons CR01–CR07 | Order status flow; webhook fields | Only if Boxme delivery is in scope (S4). Draft mapping in 2.1 |
| L-28 | Inbound received quantity | ❓ | GRN rows per SKU / condition / batch / expiry; whether rows are per receipt or cumulative isn't stated | Get Receiving Note | Q-25. Proposed: `wms_asn_detail.quantity_received` = sum of condition A rows per SKU `[CONFIRM: C11]` |
| L-29 | Return quantities | 🟡 (doc) | `quantity_received` per SKU and condition | Get Order Returns Receive | Accepted = sum A; damaged = sum D1–D3; lost = expected − (accepted + damaged) `[CONFIRM: C7]` |
| L-30 | Short-ship | 🟡 (doc) | 212 Out of stock at creation (with `config.check_stock`); no partial shipping documented | Order status flow; `NOT_ENOUGH_ITEM` | Send `config.check_stock: true`; 212 → "Failed to send". Re-push: Q-22 |
| L-31 | Cancel windows | ❓ | Not documented for orders, ASNs or returns | Cancel endpoints | Q-07 |
| L-32 | Partial cancellation | 🔴 | No line-level cancel or order update endpoint | Orders API | Q-29. Workaround to discuss in S4: full cancel + re-create. Risk R-08 |
| L-33 | AWB / label | 🟡 (doc) | Order Pack: `shipping_label` URL (PDF / PNG, 10×15 cm), `courier_tracking_code`, `courier_name` from Get Courier List | Order Pack; Update Document | Source of label URL `[CONFIRM: C3]`. Shopee channels without tracking: Q-30 |
| L-34 | COD | ✅ (doc) | `payment.cod_amount` mandatory | Create B2C Order | 0 when marketplace delivers; sum of item COD + shipping when Boxme delivers COD |
| L-35 | Mixed lines | ✅ (doc) | Order carries only the items sent | Create B2C Order | Send only lines fulfilled by Boxme; never dropship |
| L-36 | Priority orders | ✅ (doc) | `fulfillment_vas.fulfill_now` (packed in 45 min), `priority_fulfill` (2 h); Order Pack `fulfill_type` `now` / `priority` | Instant / Same-day flows; TikTok FDR guide | Instant → `fulfill_now`; same-day → `priority_fulfill`; TikTok paid 14:00–16:00 → `priority` |
| L-37 | Authentication | 🟡 (doc) | Static key per seller, max 365 days, IP whitelist | Authentication; Security Upgrade | Store key + expiry date per brand; alert 30 days before expiry and on 401 / 403 |
| L-38 | Rate limit, pagination | 🔴 | 1–2 rps per IP; Get Order 60/min | Endpoint descriptions | Q-02; Risk R-01. Queue creates; use webhooks, not polling |
| L-39 | Duplicate protection | ✅ (doc) | Orders, ASNs, products all reject duplicates | Error Codes; examples | Treat `seller_sku_existed` as success and store returned `bsin` |
| L-40 | Error format | ✅ (doc) | Readable `error_code` + `messages` | Common Errors; Error Codes | Show as `WMS error: <messages>` |
| L-41 | Webhook reliability | 🟡 (doc) | 200 within 3 s; 3 retries; static token; ordering unknown | Webhooks overview | Reply 200 at once, process in background; dedupe on `request_id`; ignore events with older `update_time`. Q-34 |
| L-42 | Staging vs production parity | ✅ (PIC) | No staging; test account on production | PIC 2026-11-13 | Tests must not trigger real warehouse work (Q-35, R-03) |

### 2.1 Draft status mapping – Inbound (ASN)

| Partner status | Partner meaning | PowerSell status | Confidence | Note / Q-ID |
|---|---|---|---|---|
| 1 New | ASN created | Pending Receipt | Doc only | Or "New" `[CONFIRM: S4]` |
| 12 Awaiting Reservation | Waiting for timeslot booking | Pending Receipt | Doc only | Booking step (Create ASN Booking) |
| 2 Ready-to-ship | Seller confirmed shipment | Pending Receipt | Doc only | |
| 4 In-transit | On the way to warehouse | Pending Receipt | Doc only | |
| 10 Received | Arrived at warehouse | Pending Receipt | Doc only | |
| 11 Partial inspection | Partly inspected and put away | Pending Receipt | Doc only | Pull stock for the ASN's SKUs |
| 6 Completed | All items put away | Completed if received = expected; else Pending Receipt | Doc only | Q-24 |
| 5 Cancelled | Cancelled | Closed | Doc only | |
| 7 Cancelled by operator | Cancelled by Boxme | Closed | Doc only | |

### 2.1 Draft status mapping – Outbound

| Partner status | Partner meaning | PowerSell display | PowerSell backend | Confidence | Note / Q-ID |
|---|---|---|---|---|---|
| 110 Awaiting Label | Waiting for label | Sent successfully | New | Doc only | For marketplace orders: waiting for Order Pack |
| 201 Label generated | Label received | Sent successfully | New | Doc only | |
| 212 Out of stock | Missing stock | Failed to send | Out of stock | Doc only | Q-22 (re-push) |
| 210 Awaiting process | Waiting to pick | Sent successfully | New | Doc only | |
| 217 Processing at warehouse | Picking and packing | Sent successfully | Picking | Doc only | Boxme doesn't split picking / packing |
| 211 Ready to ship | Packed | Packed | Packed | Doc only | |
| 280 Waiting to handover | Waiting for carrier | Packed | Packed | Doc only | |
| 300, 301 Shipped | Handed to carrier | Shipped | Shipped | Doc only | |
| 302 Courier refused | Carrier refused pickup | — | — | Gap | Q-26 (Onflow maps a similar case to Canceled) |
| 801 Fulfilled | Final for marketplace-shipped | Shipped | Shipped | Doc only | Q-26: how does it differ from 300? |
| 304 In-transit, 310 Out for delivery | Boxme delivering | Shipped | Shipped | Doc only | Only if Boxme delivers |
| 400 Out of delivery, 410 Awaiting re-delivery | Failed attempt | Shipped | Delivery failed | Doc only | Reason in `failed_delivery_reason_code` |
| 420 Return processing, 430 Return approved | Returning to warehouse | Shipped | On return | Doc only | |
| 600 Returned | Back in warehouse | Shipped | Returned | Doc only | |
| 800 Delivered | Delivered | Delivered | Delivered | Doc only | |
| 605, 606 Destroy at destination hub | Lost / damaged by carrier | — | — | Gap | Q-26: Lost in transit? |
| 700 by seller, 701 by operator, 703 by system | Cancelled | Cancelled | Canceled | Doc only | Display "Cancelled" `[CONFIRM: S10]` |
| 704 Pending for audit | Under verification | — | — | Gap | Q-26 |
| 705 Cancelled at warehouse | Cancelled during processing | Cancelled | Canceled | Doc only | Re-inbound handling? Q-26 |
| 706 Waiting for cancellation | Cancel requested | — | — | Gap | Q-26: keep previous status? |
| 708 Cancelled by lost item | Items lost in warehouse | — | — | Gap | Q-26: Canceled or Lost in transit? |

### 2.1 Draft status mapping – Return

| Partner status | Partner meaning | PowerSell status | Confidence | Note / Q-ID |
|---|---|---|---|---|
| 201 Label generated | Return created | Pending receipt | Doc only | |
| 501 Awaiting to receive | Expected at warehouse | Pending receipt | Doc only | |
| 502 Received | Arrived | Pending receipt | Doc only | |
| 503 Inspected | Checked | Pending receipt | Doc only | |
| 600 Returned | Put away, stock increased | Received (Closed if accepted = expected `[CONFIRM: S3]`) | Doc only | Then fetch Get Order Returns Receive |
| (cancelled) | Not documented | Canceled | Gap | Q-27 |

---

## 3. Smoke tests

**Postman collection:** "Boxme – S3 smoke tests (Batch B)" in Kiet Lam's personal Postman workspace (27 requests; TC-S01, S02 read-only parts folded into setup TC-S00a/b). Steps needing Boxme staff (S09, S19, S20, S23) stay as a checklist.

**Environment:** production `https://s.boxme.asia`, Boxme test seller account (no cost) ·
**Run by:** [user / QC] · **Run on:** [date]

> **Before running:** agree with Boxme ops (Q-35) how test ASNs and orders are handled, so
> warehouse staff don't act on them. Use clearly marked SKUs and order numbers
> (e.g. `PS-TEST-…`). Whitelist the calling IP first (R-04).

| TC | Step | Request (endpoint + key inputs) | What to check | Proves | Result | Evidence |
|---|---|---|---|---|---|---|
| TC-S01 | Auth | `GET /api/v2/sellers/pickup` with `Authorization: Token <key>` | 200; list returned. Then call with a wrong key: 401 `authentication_failed` | L-37 | Not run | |
| TC-S02 | Get warehouses | `GET /api/v2/sellers/pickup` | Which entries are Boxme warehouses vs seller addresses (`warehouse_code`) | L-08 | Not run | |
| TC-S03 | Create product | `POST /api/v2.1/sellers/products/create/` with 2 barcodes, `volume` `10x20x30` | `bsin` returned; approval status; volume unit shown in the Boxme web portal | L-01, L-02, L-03, L-09, L-15 | Not run | |
| TC-S04 | Create same product again | Same body | `seller_sku_existed` with existing `bsin` | L-39 | Not run | |
| TC-S05 | Get product / stock | `GET …/products/list?keyword=`; `POST …/get_stock/` | Shelf-life fields come back in days or months (send 30 and compare); stock per `pickup_id` | L-12, L-17 | Not run | |
| TC-S06 | Create ASN | `POST /api/v2/sellers/shipments/` | `shipment_code` returned; status 1 New or 12 Awaiting Reservation | L-06, L-20 | Not run | |
| TC-S07 | Create ASN again | Same `po_number` | `po_number_duplicated` | L-39 | Not run | |
| TC-S08 | Cancel ASN | `POST /api/v2/sellers/shipments/cancel/{code}/` | Cancelled (5); webhook received | L-31 | Not run | |
| TC-S09 | Receive ASN (Boxme ops, short by 1 unit) | Boxme receives test ASN with 1 unit missing and 1 unit damaged | Final status (6 or other); GRN rows (per receipt or summed?); conditions used | L-21, L-26, L-28 | Not run | Needs Boxme ops |
| TC-S10 | Create B2C order (marketplace-shipped) | `POST /api/v2/courier/pricing/b2c/create_order`, `delivery_service: BM_DBS`, masked phone / address | Accepted; `tracking_number`; status 110 | L-04, L-14, L-34 | Not run | |
| TC-S11 | Create same order again | Same `referral.order_number` | `DUPLICATED_ORDER`. Repeat with same `order_number`, different `store_order_id` | L-04, L-39 | Not run | |
| TC-S12 | Order Pack | `PUT /api/v2/orders/fulfill/pack/` with label URL + tracking | Status 201 → 210; webhooks received in order | L-24, L-33, L-41 | Not run | |
| TC-S13 | Cancel order at 210 | `POST /api/v2/orders/cancel/{tn}/` | Success → 700 | L-23, L-31 | Not run | |
| TC-S14 | Cancel order after 211 Ready to ship | Same, on an order Boxme packed | `not_allowed`, or 706 → 705? | L-23, L-31 | Not run | Needs Boxme ops |
| TC-S15 | Order for out-of-stock SKU | Create with quantity above stock, `check_stock: true` | `NOT_ENOUGH_ITEM` error or 212 status; re-create with same order number after cancel | L-05, L-30 | Not run | |
| TC-S16 | Instant order | Create with `fulfill_now: true`; Order Pack `fulfill_type: now` | Accepted; status flow to 211 | L-36, L-24 | Not run | |
| TC-S17 | Create return | `POST /api/v2/orders/rma/create/{tn}/` | `return_tracking_number`; which fields are really mandatory (the doc's placeholder field) | L-07 | Not run | |
| TC-S18 | Cancel return | `DELETE /api/v2/orders/rma/cancel/{rt}/` | Response body; status after cancel (webhook) | L-25, L-31 | Not run | |
| TC-S19 | Return received (Boxme ops) | Boxme receives return, 1 good + 1 damaged | 600 Returned; Get Order Returns Receive conditions | L-29, L-26 | Not run | Needs Boxme ops |
| TC-S20 | Webhook check | Register test URL in oms.boxme.asia; trigger each event | Token header; retry after returning 500; `request_id`; order of events | L-41 | Not run | |
| TC-S21 | Negative: missing mandatory field | Create Order without `ship_to.phone` | Readable error | L-40 | Not run | |
| TC-S22 | Negative: unknown SKU | Create Order with SKU not at Boxme | `PRODUCT_INVALID` (not silent drop) | L-40 | Not run | |
| TC-S23 | Negative: webhook for unknown order | Ask Boxme to push an event for an order PowerSell doesn't know; reply 404 | Does Boxme retry, then stop? | L-41 | Not run | Needs Boxme |

---

## 4. Doc vs reality

No staging results yet. Inconsistencies **inside the document**, to confirm during testing:

| # | Endpoint | Document says | Staging actually does | Impact | Check | Q-ID |
|---|---|---|---|---|---|---|
| D-01 | Create vs Update Product | `expiry_threshold`, `min_inbound_shelf_life` in **days** (create) / **months** (update, get) | Not tested | Wrong unit = stock rejected at inbound or near-expiry stock shipped | L-12 | Q-08 |
| D-02 | Get Shipment Detail | Description: "included quantity inbound by SKU" | Schema has no received quantity | Received quantities must come from the receiving note (GRN) | L-28 | Q-25 |
| D-03 | Create Returns Order | Mandatory field named `01HTPRXX7CJ3BFGXWQTG275SBB` | Not tested | Unclear request body | L-07 | Q-10 |
| D-04 | Direct RTS webhook | Field named `01HYD3H7Z5KMAEP89ME3QJRPJ6` | Not tested | Unclear payload | L-24 | Q-10 |
| D-05 | Lookup zipcode | Path `/pi/v2/…` | Not tested | Likely `/api/v2/…` | L-14 | Q-10 |
| D-06 | Changelog 11-06-2026 | "Test against the staging environment" | No staging exists (PIC) | — | L-42 | — |
| D-07 | Create Returns Order | Schema: items use `seller_sku`; requires `return_order_number`, `courier_tracking_number` | Doc example uses `sku` and omits those fields | Unclear which body Boxme accepts; tested in TC-S17 | L-07 | Q-10 |
| D-08 | Create ASN | Schema: `estimate_arrived_time` is an integer timestamp | Doc example sends `"21/12/2023"` (text) | Wrong format may be rejected; TC-S06 sends a timestamp | L-13 | Q-10 |

---

## 5. Partner question message (draft)

**Draft only. Not sent.**

```markdown
Subject: Boxme x PowerSell integration – questions on API behaviour (13 Nov 2026)

Hi [Boxme contact],

Thank you for your support. We have reviewed the Boxme Open API v2 documentation and are
preparing tests. Before we start, we need your help with the questions below. Questions
marked **(priority)** block our next step. Could you reply by [date]?

**Test account**
- Q-05 (priority): Please share a test seller account and API key on production, with no
  financial cost.
- Q-35 (priority): How should test orders and inbound shipments be handled so that your
  warehouse team does not process them? Can the test account be flagged, or should we
  agree on a naming rule (e.g. "PS-TEST-")?

**Limits and access**
- Q-02 (priority): Rate limits are per IP (Create Order 2 per second, Get Order 60 per
  minute). We send requests for many sellers from the same servers. Are limits per IP or
  per API key? Can they be raised for us, especially for campaign days (11.11, 12.12)?

**Products**
- Q-21 (priority): What unit is "volume" (LxWxH) in: cm or mm?
- Q-08 (priority): "expiry_threshold" and "min_inbound_shelf_life" are in days in Create
  Product, but in months in Update Product and Get Products. Which is correct?
- Q-11: After Create Product, does your team need to approve the product before it can be
  used in an inbound shipment or order? How long does it take, and does the Product
  Update webhook tell us when it is approved?
- Q-33: For required product fields we may not have (category, packing material, unit,
  wholesale price), can we use fixed default values? Which values do you recommend?

**Orders**
- Q-22 (priority): Which field is checked for duplicate orders: "referral.order_number",
  "referral.store_order_id", or both? If an order is cancelled because of out-of-stock,
  can we create it again with the same order number?
- Q-07 (priority): Until which status can we cancel an order, an inbound shipment and a
  return order by API?
- Q-29 (priority): Can we cancel only some items of an order? If not, what do you
  recommend when a buyer cancels one item?
- Q-30 (priority): For marketplace-shipped orders, please confirm that your warehouse only
  starts picking after we call Order Pack with the label. For Shopee orders that have no
  tracking number, what should we send as "courier_tracking_code"? When is the Direct RTS
  webhook sent, and only for Lazada?
- Q-31 (priority): Marketplaces often mask the buyer's phone and address. Will Create B2C
  Order accept masked values? What should we send?
- Q-32: After the new Vietnam location database (25/10/2025), which IDs should we send for
  province / district / sub-district? How reliable is matching by name only?
- Q-26 (priority): What happens next, and what should we show the seller, for these
  statuses: 302 Courier refused, 605/606 Destroy at destination hub, 704 Pending for
  audit, 706 Waiting for cancellation, 708 Cancelled by lost item? What is the difference
  between 300 Shipped and 801 Fulfilled?

**Inbound**
- Q-24 (priority): If fewer items arrive than expected, does the inbound shipment still
  end in 6 Completed? Or does it stay open?
- Q-25 (priority): In Get Receiving Note, is there one row per receipt, or one row per SKU,
  condition and batch in total?
- Q-28 (priority): What do condition levels "L" and "DE" mean? Are D1, D2 and D3 all not
  sellable?

**Returns**
- Q-27 (priority): Which status does a return order get after Cancel Returns Order? What
  does Cancel Returns Order return?

**Webhooks**
- Q-12: Can we register one webhook for all our sellers, or must each seller account set
  it up in oms.boxme.asia?
- Q-34: Can webhook events arrive out of order? Is "update_time" reliable for ignoring
  older events? Is the webhook token the same for all sellers?

**Documentation**
- Q-10: Create Returns Order has a required field named "01HTPRXX7CJ3BFGXWQTG275SBB", and
  Direct RTS has "01HYD3H7Z5KMAEP89ME3QJRPJ6". What are the correct field names? COD
  statement paths show "/" and the zipcode path shows "/pi/v2/...". Could you correct
  these?

**General (operations)**
- Q-13 to Q-20: [8 due-diligence questions from the tracker: peak traffic, uptime,
  performance benchmarks, scalability, data-breach response, error handling, backup and
  disaster recovery (we have read your RTO / RPO page), outage handling and response time]

Thank you,
[name]
```
