# PowerSell status model (for WMS mappings)

**Status: DRAFT — filled from all 21 WMS mapping and integration docs on 2026-10-29. Not yet confirmed by dev.**

Every partner status must map to exactly one PowerSell status. A partner status with no
match is a mapping gap: raise it as an open question, don't force it into the nearest
PowerSell status.

**Partner codes:** OF Onflow · TN TNSL · BW BoostWare · ES EASYSPAD · IM IM Logistics ·
LEL Lazada MCL · BL BetterLand · FL Flash · SnT · TA TitipAja · BM Boxme · ZTO ·
MC MyCloud · NH N&H.

## Contents
- [Inbound shipment (ASN)](#inbound-shipment-asn)
- [Purchase order and transfer order](#purchase-order-and-transfer-order)
- [WMS sales order](#wms-sales-order)
- [Return and failed delivery](#return-and-failed-delivery)
- [Received item condition](#received-item-condition)
- [Error messages](#error-messages)
- [Sales channel order status (context only)](#sales-channel-order-status-context-only)
- [Known mapping gaps](#known-mapping-gaps)
- [Conflicts to resolve](#conflicts-to-resolve)

---

## Inbound shipment (ASN)

| PowerSell ASN status | Meaning | Typical partner statuses | Final? | Seen in |
|---|---|---|---|---|
| Draft | Created in PowerSell, not sent | — | N | Most |
| New | Created, before sending | — | N | BW, TA, ZTO |
| Pending Receipt | Sent; in transit, arrived, receiving, inspecting, partially received | new, released, approved, arrived, receiving, partial | N | All |
| Completed | Fully received: received = expected | completed / closed / fulfilled, **only if** received = expected | Y | All |
| Closed | Cancelled or rejected | cancelled, voided, rejected by warehouse | Y | All |
| Error | Partner rejected the ASN at creation | failed | Y | TN |

Rules seen across docs:
- Partner final status with received < expected stays **Pending Receipt**.
- Partial receipt triggers a stock pull for the ASN's SKUs (BW, ZTO, BM, LEL).
- Cancel returning "not found" 3 times sets the ASN to Closed (BW, FL).
- Cancel is only possible while the partner allows it (e.g. ES/IM only at Arrived; LEL
  until Request Accepted). The partner's reason is shown as `WMS error: …`.
- Some partners need extra inbound steps: booking a time slot (TN, LEL reservation) or a
  receiving reservation; the ASN waits until it's done.

## Purchase order and transfer order

| Object | PowerSell statuses | Seen in |
|---|---|---|
| Purchase order (follows its ASNs) | Confirmed → Pending Receipt → Completed | TA |
| Transfer order (outbound DO + inbound ASN) | Draft → Pending Approval → Approved / Rejected → Pending Fulfillment → Pending Receipt → Completed | Transfer order doc (BM, FL, TA) |

## WMS sales order

PowerSell keeps **two layers** of WMS order status: a display status users see, and a
detailed backend status. SnT names them "PWS WMS FE status" and "PWS WMS BE status".

### Display status (shown to users)

| PowerSell WMS status (display) | Meaning | Seen in |
|---|---|---|
| Being sent | PowerSell is sending, or the WMS hasn't started work | TN, BW, ES, IM, BL, FL |
| Failed to send | WMS rejected the order (incl. out of stock at WMS) | BW, BL |
| Won't send | Not sent by design (manual handling or fulfilled by platform) | BW |
| Sent successfully | WMS accepted and is processing | All |
| Packed | Packed, waiting for carrier | All |
| Shipped | Handed to carrier | All |
| Delivered | Delivered (mainly when WMS also delivers) | FL, SnT |
| Cancelled | Cancelled at WMS | FL |

### Backend status (stored detail)

| PowerSell WMS status (backend) | Meaning | Seen in |
|---|---|---|
| New | Created at the WMS | OF, TN, TA, MC, BM, SnT |
| Picking | Being picked | OF, TN, MC, BM |
| Picked | Picking done | TN, TA |
| Packing | Being packed | OF, TN |
| Packed | Packed, ready for handover | OF, TN, TA, MC, BM |
| Shipped | Handed to carrier | All |
| Delivered | Delivered | OF, TN, BM, SnT |
| Delivery failed | Delivery attempt failed | BM |
| On return | Returning to the warehouse | TN, BM |
| Returned | Back at the warehouse | OF, TN, BM |
| Canceled | Cancelled at the WMS | OF, TN, TA, BM |
| Out of stock | WMS can't fulfil due to stock | BM |
| Lost in transit | Items lost; order is recreated | BM |

Rules seen across docs:
- **WMS events drive the sales channel**: TN `ready_for_pickup`, BW `picking` (Shopee,
  TikTok Shop) and FL `Packed` trigger Ready To Ship on the channel to get the AWB, which
  is then pushed to the WMS.
- **Re-push on WMS stock-out or loss**: LEL re-pushes with suffix `_PWS-1`, `_PWS-2`…;
  BM recreates the order with fulfil-now when items are lost.
- **Cancel after packing**: partner "cancelled after packing" or "carrier rejected pickup"
  → Canceled (OF); cancelled at the handover gate → re-inbound (TN); cancelled after
  ready-to-ship but before channel shipped → failed-delivery re-inbound (LEL).
- PowerSell pushes "Shipped" back to the WMS when the channel shows shipped (ES, IM).
- Cancelled items are ignored when syncing WMS fulfilment status to Shopify (all WMS).

## Return and failed delivery

| PowerSell return status | Meaning | Final? | Seen in |
|---|---|---|---|
| Pending receipt | Sent to WMS; waiting, in transit, arrived or inspecting | N | All |
| Received | Completed at WMS (accepted < expected, or partner's final status) | Y | OF, TN, BW, BL, BM, ZTO, NH, Return doc |
| Closed | Completed with accepted = expected | Y | Return doc only |
| Canceled | Return cancelled | Y | OF, TN, NH |

Return types: `FAILED_DELIVERY` and `CUSTOMER_RETURN` (BL).

Rules seen across docs:
- PowerSell only sends a return to the WMS that fulfilled the original order.
- When a return turns Received, PowerSell pulls item receipt (accepted / damaged) (BW).
- Zalora and TikTok Shop partial returns are grouped and delayed before sending (Return doc).

## Received item condition

| PowerSell condition | Meaning | Seen in |
|---|---|---|
| Good (accepted) | Resellable | All |
| Damaged | Not resellable | All |
| Lost (calculated) | Expected − (accepted + damaged) | ES, IM, ZTO |

Partner codes are mapped per partner (e.g. TNSL grades A–F, OD = Damaged; N, NE, IC =
Good; GLINK `GOOD` / `DAMAGE`; LEL inventory type 1 = good, 101 = defective).

## Error messages

| Pattern | Use | Seen in |
|---|---|---|
| `WMS error: <plain-language reason>` | WMS rejected create / cancel; stored in `wms_asn.last_error` (LEL) | TN, BW, LEL, FL |
| `DUP_TRACKING_NO` | Return rejected: duplicated tracking number | Return doc |
| `WMS_OTHER_ERROR` | Any other WMS return error | Return doc |

## Sales channel order status (context only)

Not a WMS status, but WMS events change it. Stored at order item level:
Unverified · Pending · RTS · In Cancel · Shipped · Delivered · Failed to deliver ·
Returned · Canceled. Offline (B2B) orders also use Confirmed (FL).
Source: "PowerSell_W Order Status & Definition".

---

## Known mapping gaps

Partner statuses left unmapped in the source docs. Each needs a decision:

| Partner | Unmapped statuses |
|---|---|
| LEL | created_failed, inbound, delivery_failed, failed, delivered, canceled, cancel_failed, request_failed, oos, reinbound_* |
| BM | ASN Cancelled / Cancelled by operator; return 501–503 |
| ZTO | Order shipped (5000) in the main doc; return new / released / partial / received / cancelled |
| NH | RETURN_FAIL_RETURN (220) |
| IM | Entire return status mapping |
| BW | Return cancelled |
| TN | `3pl_picked_up_from_seller` (TBD) |

---

## Conflicts to resolve

| ID | Topic | What the docs say | Question for dev |
|---|---|---|---|
| S1 | BoostWare "cancelled" | BW maps `cancelled` (9000) to "Sent successfully" | Intended, or Canceled? |
| S2 | SnT backend values | SnT stores partner values (Process, Ready to ship, Loaded, Cancel) | Map to PowerSell's backend list? |
| S3 | Return Received vs Closed | Return doc adds Closed when accepted = expected; partner docs only use Received | Is Closed live for all WMS? |
| S4 | ASN "New" | Listed by BW, TA, ZTO only | Real status for all WMS? |
| S5 | Legacy statuses | 2022 doc had Failed to delivery and Partial Returned | Still used? |
| S6 | Flash main vs offline doc | Flash 120–180 → "Being sent" (main) vs "Sent successfully" (offline doc) | Which is current? |
| S7 | "Ready to ship" meaning | LEL `ready_to_shipped` → Shipped; BW, BL, SnT, MC ready-to-ship → Packed | Should LEL be Packed? |
| S8 | MyCloud | packing → Packed; delivered → Shipped | Align with other WMS (Packing; Delivered)? |
| S9 | TitipAja fully received | "Fully Received (40)" → Pending Receipt; only "ASN Closed (99)" can complete | Intended? |
| S10 | Display status "Cancelled" | Only FL shows Cancelled as a display status; others leave cancelled orders unmapped | Should Cancelled be a display status for all? |
