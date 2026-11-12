# Logic checks (S3)

42 fixed checks. Run **all** of them for every partner, in order. Don't add or drop checks
for one partner. If a check doesn't apply, rate it ➖ N/A with a reason.

Each check says what PowerSell expects (with the reference-pack section to read) and why
it matters (where it went wrong before). "Verify by" says whether the document is enough
or a smoke test is needed.

Partner codes: OF Onflow · TN TNSL · BW BoostWare · ES EASYSPAD · IM IM Logistics ·
LEL Lazada MCL · BL BetterLand · FL Flash · TA TitipAja · BM Boxme · NH N&H.

## Contents
- [A. Identity and references (L-01 to L-08)](#a-identity-and-references)
- [B. Units and formats (L-09 to L-14)](#b-units-and-formats)
- [C. Product and stock (L-15 to L-19)](#c-product-and-stock)
- [D. Lifecycles and statuses (L-20 to L-27)](#d-lifecycles-and-statuses)
- [E. Quantities and order handling (L-28 to L-36)](#e-quantities-and-order-handling)
- [F. Technical behaviour (L-37 to L-42)](#f-technical-behaviour)

---

## A. Identity and references

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-01 | What is the product key at the partner? | Partner keeps our `product.inventory_sku` as its SKU code (data-model § Product) | FL keys products by barcode, so a SKU with no barcode can't be created | Doc + create product test |
| L-02 | Does the partner return its own product ID, and is it stable? | Stored in `wms_product.partner_id` / `partner_key` `[CONFIRM: C1]` | Partners differ on which ID goes where; TN is the reverse of BW and LEL | Doc + create/get product test |
| L-03 | Can one SKU have several barcodes? | Main `product.barcode` plus `product.backup_barcode` | Brands relabel; a second barcode not registered means goods are rejected at receiving | Doc |
| L-04 | Which order number does the partner accept and echo back, and must it be unique? | One clear reference per order `[CONFIRM: C2]` | Five different conventions exist across partners; mismatches break status updates | Doc + create/get outbound test |
| L-05 | Can an order be re-sent after the WMS reports out-of-stock or loss? | Re-push is possible (LEL adds suffix `_PWS-1`, `_PWS-2`…) | If the reference can't be reused, a re-push needs a suffix rule agreed up front | Doc + question |
| L-06 | What inbound references exist (ASN, PO, GRN)? | We send `wms_asn.code` (or PO code), store partner ASN ID; GRN location `[CONFIRM: C6]` | Multiple GRNs per ASN are common; the place to store them is unresolved | Doc + create/get inbound test |
| L-07 | Does a return need the original order reference, and what return ID comes back? | Return linked to the original WMS order; partner ref stored `[CONFIRM: C8]` | Returns are only sent to the WMS that fulfilled the order | Doc + create return test |
| L-08 | How is the warehouse / client / brand structure modelled? | `wms_warehouse.partner_warehouse_id` on every inbound, outbound, stock and return call | Multi-warehouse partners need warehouse mapping (UC-01); BL has damage warehouses to exclude | Doc + get warehouse test |

## B. Units and formats

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-09 | Dimension unit | cm (data-model § Product) | BW and FL use mm; a missing conversion gives 10× wrong volumes and storage fees | Doc + get product test |
| L-10 | Weight unit, and which weight (package or product) | grams; which weight `[CONFIRM: C5]` | FL uses both weights for different fields | Doc + get product test |
| L-11 | Price and currency format | Decimal in channel currency | FL expects price × 100 (satang) | Doc |
| L-12 | Shelf-life unit and the three thresholds (reject at inbound, block shipping, alert) | Months in PowerSell (× 30 for days); field paths `[CONFIRM: C4]` | Wrong unit = good stock rejected at receiving, or near-expiry stock shipped | Doc + question |
| L-13 | Timezone and date format, in requests and in webhooks | Local time for most partners; LEL and BW use UTC | A 7-hour shift moves delivery dates and SLA timers | Doc + any create test |
| L-14 | Address format: free text or location codes? What happens with masked addresses? | `[CONFIRM: C9]` for source fields; masked addresses sent with placeholders (BL: province "00", postal "00000") | Marketplaces mask addresses; a partner that validates strictly rejects these orders | Doc + create outbound test with a masked address |

## C. Product and stock

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-15 | Mandatory product fields that PowerSell may not hold (category code, HS code, storage type, valuation method) | A default rule for every mandatory field PowerSell doesn't hold | Without a default, product create fails for every brand missing the data | Doc |
| L-16 | Can a product be updated after creation (name, barcode, dimensions)? | Updates possible, or a documented manual process | Brands change packaging; without update, the WMS keeps stale data | Doc |
| L-17 | How is stock split (per warehouse, condition, stock type)? | Sellable stock maps to `product_stock.open_stock` = `wms_product.available_quantity`; damaged not stored | Taking on-hand instead of available causes overselling | Doc + get stock test |
| L-18 | How do stock changes reach PowerSell (webhook or polling), full or delta, how often? | Updated soon after any change (UC-04) | Daily batch stock means overselling during campaigns | Doc + webhook test |
| L-19 | Bundles and kits: does the partner accept bundle SKUs or only components? | Bundles split into component SKUs before sending (BM, ZTO) | A partner doing its own kitting conflicts with our split | Doc + question |

## D. Lifecycles and statuses

For L-20, L-22 and L-25, list **every** partner status and map each one to exactly one
PowerSell status from `status-model.md`. Unmatched = 🔴 plus a question.

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-20 | Inbound status list | Draft / Pending Receipt / Completed / Closed / Error (status-model § ASN) | Status gaps leave ASNs stuck in Pending Receipt forever | Doc + get inbound test |
| L-21 | What final status does the partner send when received < expected? | Stays **Pending Receipt**; Completed only when received = expected | TA "Fully Received (40)" vs "ASN Closed (99)" `[CONFIRM: S9]` | Doc + question |
| L-22 | Outbound status list, mapped to display **and** backend status | Both layers (status-model § WMS sales order) | LEL has 10+ statuses still unmapped | Doc + get outbound test |
| L-23 | What does "cancelled" mean at each outbound stage (before pick, after pack, at handover)? | Cancelled → Canceled; after packing → per partner rule (re-inbound) | BW `cancelled` (9000) was mapped to "Sent successfully" `[CONFIRM: S1]` | Doc + cancel tests |
| L-24 | Which partner event means "ready for carrier", so PowerSell can set Ready To Ship on the channel? | One clear event (TN `ready_for_pickup`, BW `picking`, FL `Packed`) | Too early = AWB before packing; too late = missed marketplace SLA. "Ready to ship" means different things `[CONFIRM: S7]` | Doc + question |
| L-25 | Return status list | Pending receipt / Received / Canceled; Closed `[CONFIRM: S3]` | IM had no return status mapping at all | Doc + get return test |
| L-26 | Item condition codes on inbound and return receipt | Good / Damaged; Lost calculated (status-model § Received item condition) | TN uses grades A–F; each code must land in Good or Damaged | Doc + question |
| L-27 | If the partner delivers: delivery statuses (delivered, failed, on return, returned, lost) | Backend statuses Delivered / Delivery failed / On return / Returned / Lost in transit | Without these, failed deliveries don't trigger a return | Doc (➖ if no delivery service) |

## E. Quantities and order handling

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-28 | Inbound received quantity: cumulative or per receipt, good only? | Sum across all GRNs, good / putaway only (`wms_asn_detail.quantity_received` `[CONFIRM: C11]`) | Per-receipt values overwrite each other and under-count stock | Doc + question |
| L-29 | Return quantities: accepted and damaged reported separately? | receipt = accepted + damaged; lost = expected − receipt `[CONFIRM: C7]` | NH calculated expected as received − damaged (source-doc error) | Doc + get return test |
| L-30 | Short-ship: what happens when the WMS lacks stock for an order? | Clear status (Out of stock), then re-push or recreate | BM recreates lost orders; silent partial ships cause customer complaints | Doc + question |
| L-31 | Cancel windows for inbound, outbound and return: until which status? Is the refusal readable? | Cancel while the partner allows it; refusal shown as `WMS error: <reason>` | ES/IM only allow inbound cancel at Arrived; LEL only until Request Accepted | Doc + cancel tests |
| L-32 | Partial cancellation (some lines of an order) | Partial cancel updates the WMS order; full cancel cancels it (BL) | Marketplaces allow per-item cancellation | Doc + question |
| L-33 | AWB / shipping label: needed before packing? Sent as URL, file or number? | Label reaches the WMS before packing (UC-12); source field `[CONFIRM: C3]`; some Shopee channels have no tracking | A parcel packed without the marketplace label ships late | Doc + upload AWB test |
| L-34 | COD amount: which field, and when? | Sum of item COD + shipping fee, only when the WMS also delivers and payment is COD; else 0 | LEL payment mapping looked inverted (source-doc error) | Doc |
| L-35 | Orders with mixed lines (some lines dropship or not for this WMS) | Only WMS-fulfilled lines are sent; dropship never sent | A partner that requires all lines rejects or over-ships | Doc + question |
| L-36 | Priority / urgent orders (instant, same-day) | A flag or service type on outbound create (UC-10) | Instant orders miss their SLA if picked in normal sequence | Doc |

## F. Technical behaviour

| ID | Check | PowerSell expects | Why it matters | Verify by |
|---|---|---|---|---|
| L-37 | Authentication: token type, expiry, refresh, per shop or per partner | Documented refresh; credentials per brand / shop where possible | Expired tokens without refresh stop all syncs silently | Doc + auth test |
| L-38 | Rate limit (per shop or per partner) and pagination on list endpoints | ≥ 60 calls/sec per endpoint, per shop (checklist row 4); stable paging | Per-partner limits throttle all brands during 11.11 | Doc + question |
| L-39 | Duplicate protection: same create request sent twice | Second call rejected or returns the same record (idempotent) | Retries after timeouts otherwise create double orders and double shipments | Duplicate create test |
| L-40 | Error format: codes and messages readable enough for users? | Shown as `WMS error: <plain-language reason>` | Cryptic codes push every failure to the support team | Negative tests |
| L-41 | Webhook reliability: retry policy, signature, ordering, full vs partial payload, reaction to our error reply | Retries with backoff; signed; full state per event, or a timestamp to drop out-of-order events | Out-of-order webhooks move orders backwards (Shipped → Packed) | Doc + webhook tests |
| L-42 | Staging vs production parity: same base logic, statuses and limits? | Staging behaves like production (checklist row 2) | Staging-only behaviour invalidates every test above | Question |
