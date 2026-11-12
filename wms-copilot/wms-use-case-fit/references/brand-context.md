# Brand context and "Varies" resolution (S4 Step 1)

## Questions to ask

Ask only what the tracker and Q&A log don't already answer. Group them in one message.

| # | Question | Settles |
|---|---|---|
| B1 | Which brands / ventures will use this WMS, and on which channels (Shopee, Lazada, TikTok Shop, Zalora, Shopify, offline B2B)? | UC-12, UC-14, UAT testers |
| B2 | How many warehouses will these brands use at this partner? | UC-01 |
| B3 | Who delivers to the end customer: marketplace logistics, the WMS's own carriers, or both? | UC-12, UC-14 |
| B4 | Roughly what share of orders is COD? | UC-14, L-34 |
| B5 | Do these brands sell instant / same-day orders? Roughly what share? | UC-10 |
| B6 | Daily volumes: orders, inbound shipments per week, returns per week | Workaround costing |
| B7 | Do brands use inbound services (priority receiving, unloading, inspection)? | UC-06 |
| B8 | Does the PowerSell team need to change webhook URLs without asking the partner? | UC-18 |

## Proposed resolution rules for "Varies" use cases

Each rule gives a **proposal**. Show all of them as a draft and get the WMS partner
PIC's confirmation before rating. Record the confirmed values in the tracker's Decision
log as "S4 priorities confirmed".

| Use case | Library priority | Proposal rule |
|---|---|---|
| UC-01 Know which warehouses a brand uses | Varies | **Must** if B2 > 1 warehouse; **Not needed** if single warehouse (PWS logic handles it) |
| UC-03 Look up product data | Varies | **Should** if the create-product response doesn't return the partner product ID, or if product data can drift (L-16 = no update); otherwise **Not needed** |
| UC-04 Keep stock in sync | Varies (pull) + Should (push) | At least one of pull or push is **Must**: stock must reach PowerSell somehow. If the partner has a stock webhook, pull → Should; if no webhook, pull → Must |
| UC-06 Extra inbound services | Varies | **Should** if B7 = yes; otherwise **Not needed** |
| UC-08 Get inbound results | Varies (pull) + Should (push) | Same as UC-04: at least one of pull or push is Must. If an inbound webhook carries per-SKU received quantities, pull → Not needed |
| UC-12 Hand over marketplace AWB | Varies | **Must** if B3 includes marketplace logistics; **Not needed** if the WMS delivers with its own carriers only |
| UC-13 Track order status (order list part) | Should (+ Varies for order list) | Order list → **Not needed** if an outbound status webhook or per-order detail endpoint covers tracking; otherwise Should |
| UC-14 Fulfillment + delivery by the WMS | Should (+ Varies) | **Not needed** if B3 = marketplace logistics only. If the WMS delivers, carriers / locations → **Must** when the partner requires carrier or location codes on create |
| UC-16 Get return results | Varies (pull) + Should (push) | Same as UC-08 |
| UC-18 Manage webhook settings | Should (+ Varies for self-config) | Self-config → **Should** if B8 = yes; otherwise Not needed |

If the brand context doesn't fit a rule (e.g. a brand mix where only some brands use
marketplace logistics), propose the stricter priority and say why.
