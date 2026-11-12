# PowerSell data model (for WMS mappings)

**Status: DRAFT — filled from all 21 WMS mapping and integration docs on 2026-10-29. Not yet confirmed by dev.**

Every field below appears in the "PowerSell params" column of at least one mapping
document. Where documents disagree, the field is flagged and listed under
[Conflicts to resolve](#conflicts-to-resolve). Don't use a flagged field in a new mapping
until dev confirms it.

**Partner codes used below:** OF Onflow · TN TNSL · BW BoostWare · ES EASYSPAD · IM IM
Logistics · LEL Lazada MCL · BL BetterLand · FL Flash · SnT · TA TitipAja · BM Boxme ·
ZTO · NH N&H. Older docs (TA, BM, ZTO, MyCloud, offline-order doc) mostly use UI labels
instead of field paths, so they appear less often.

## Contents
- [Warehouse](#warehouse)
- [Product (SKU)](#product-sku)
- [Inventory](#inventory)
- [Inbound (PO / ASN)](#inbound-po--asn)
- [Sales order (sent to WMS)](#sales-order-sent-to-wms)
- [WMS sales order (WMS side record)](#wms-sales-order-wms-side-record)
- [Customer and address](#customer-and-address)
- [Shipping (AWB, carrier, package)](#shipping-awb-carrier-package)
- [Return and failed delivery](#return-and-failed-delivery)
- [Cross-partner rules](#cross-partner-rules)
- [Conflicts to resolve](#conflicts-to-resolve)
- [Errors found in source docs](#errors-found-in-source-docs)

---

## Warehouse

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `wms_warehouse.partner_warehouse_id` | Warehouse ID at the partner | Used on every inbound, outbound, stock and return call | All |
| `wms_warehouse.partner_warehouse_name` | Warehouse name at the partner | | OF, TN, BW, ES, IM, LEL, BL, FL |
| `wms_warehouse.reference_code` | Warehouse code, when the partner has both an ID and a code | | BL, FL |
| `wms_warehouse.address` | Warehouse address | ES concatenates address parts; IM only gets country; BW uses a fixed default | OF, TN, BW, ES, IM, BL, FL |
| `wms_warehouse.status` | Active / inactive | | BW, BL |
| `wms_warehouse.contact_name` / `contact_email` / `contact_phone` | Warehouse contact | | BW, ES, FL |

Rules: BL only pulls main warehouses (type M), not damage warehouses. ZTO and BW create
the PowerSell warehouse automatically from the merchant profile on connection.

## Product (SKU)

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `product.inventory_sku` | PowerSell inventory SKU code | Main product key for most WMS; FL uses barcode instead | All |
| `product.name` | Product name | Also used as description when required | All |
| `product.barcode` | Main barcode | FL's product key; first value when a list is accepted | All |
| `product.backup_barcode` | Extra barcodes | FL accepts up to 5 | OF, BW, ES, SnT, FL |
| `product.brand` / `product_brand.name` / `brand.name` | Brand | Three sources in use | TN, BL, FL / SnT / OF |
| `product_category.name` | Category | Special characters and spaces removed (ES, IM) | ES, IM, SnT |
| `product.package_height` / `package_width` / `package_length` | Package dimensions | PowerSell unit cm; BW, FL convert to mm | OF, TN, BW, ES, IM, LEL, BL, FL |
| `product.package_weight` | Package weight (g) | **See C5** | OF, TN, ES, IM, FL |
| `product.product_weight` | Product weight (g) | **See C5** | BW, LEL, BL, FL, TA |
| `product.retail_price` | Selling price | FL sends × 100 (satang) | OF, TN, LEL, BL, FL, SnT |
| `product.cost_price` | Cost price | | SnT, FL |
| `product.expiration_time` | Shelf life (months) | × 30 = days; NULL = no expiry control | OF, TN, ES, LEL, FL, SnT |
| `product.info.reject_shelf_life` | Minimum shelf life to accept at inbound | **See C4** | OF, TN, LEL |
| `product.info.expiry_threshold` | Minimum shelf life to ship | **See C4** | OF, TN, BW, LEL, FL |
| `product.info.shelf_life_alert` | Near-expiry warning | **See C4** | LEL, FL |
| `product.serial_imei_management` | Serial / IMEI tracking | 1 = tracked | OF, TN, ES |
| `product.storage_type` | Storage condition | Ambient / Air-conditioning / Chilled / Freezer | OF, BW, LEL, ZTO, BM |
| `product.valuation_method` | Stock discharge rule | FIFO / FEFO / LIFO / FMFO | BW, ZTO, BM |
| `product.product_model_type` | Outbound / picking strategy | | OF, SnT |
| `product.is_gift` | Gift item | 1 = Gift, 0 = Sellable | OF, SnT |
| `product.info.is_fragile` | Fragile | **See C5** | OF, ES, IM |
| `product.info.min_stock_alert` | Low-stock threshold | | OF, BL |
| `product.info.udf1` … `udf4` | Packaging instructions | Onflow-specific | OF |
| `product.feature_status` | Active / inactive | | ES |
| `product.img_url` / `product_media.url` | Product images | Oldest image first | ES, IM / TN, FL |

## Inventory

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `wms_product.partner_id` | Product identifier at the partner | **See C1** | All |
| `wms_product.partner_key` | Second product identifier at the partner | **See C1** | TN, BW, LEL, BL |
| `wms_product.available_quantity` | Sellable stock at the WMS | Always equals `product_stock.open_stock` | TN, BW, LEL, FL |
| `wms_product.stock_quantity` | On-hand stock at the WMS | | BW |
| `product_stock.open_stock` | PowerSell open (sellable) stock | Only good / salable stock; PowerSell does not store damaged stock | All |

## Inbound (PO / ASN)

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `wms_purchase_order.code` | PO number | Sent when the ASN has a PO, else ASN code | OF, TN, BL |
| `wms_asn.id` | ASN internal ID | | ES, IM |
| `wms_asn.code` | PowerSell ASN number | Main reference sent to most WMS | All |
| `wms_asn.partner_asn_id` | ASN number at the partner | From the create response | All |
| `wms_asn.reference_no` | Partner's secondary ASN reference | **See C6** | OF, TN, BW |
| `wms_asn.wms_reference_no` | Goods receipt number (GRN) | **See C6** | SnT |
| `wms_asn.status` | ASN status | See `status-model.md` | BL |
| `wms_asn.last_error` | Last WMS error, shown as "WMS error: …" | | LEL |
| `wms_asn.created_at` | ASN creation date | | BW, BL, SnT |
| `wms_asn.delivery_date` | Expected arrival | Local timezone; required in UI when TN or BL warehouse | All |
| `wms_asn.shipping_date` / `shipping_info` | Arrival window start / vehicle plate | | FL |
| `wms_asn.received_date` | Receiving or putaway completed | Only when partner reports completion | All |
| `wms_asn.special_instruction` | Notes to warehouse | **See C12** | OF, TN, ES, IM, BL, SnT |
| `wms_asn.is_priority` | Priority inbound | | TN, BM |
| `wms_asn.vas_info` | Value-added services | | OF |
| `wms_asn.wms_warehouse_id` | Destination warehouse | | OF |
| `wms_asn_detail.quantity` | Expected quantity per SKU | | All |
| `wms_asn_detail.quantity_received` | Received quantity per SKU | Sum across GRNs; good / putaway only. **See C11** | All except LEL |
| `wms_asn_detail.serial_number` | Serial numbers | | TN |
| `wms_asn_detail.carton_height` / `width` / `length` / `weight` | Carton dimensions | | OF, TN |
| `wms_supplier.name` | Supplier | | SnT |

## Sales order (sent to WMS)

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `order.id` | PowerSell internal order ID | | OF, BL, SnT |
| `order.order_number` | PowerSell order number | **See C2** | OF, TN, ES, IM, LEL, SnT |
| `order.sc_order_number` | Marketplace order number | | BW, ES, IM, LEL, BL, FL, TA, SnT |
| `order.order_created_at` | Order time on channel | Local timezone (most) or UTC (LEL, BW) | All |
| `order.order_updated_at` | Last status change | Proof-of-delivery date | SnT |
| `order.shipping_fee` | Shipping fee | | TN, ES, IM, BL, FL |
| `order.total_price` | Order total | Needed when WMS also delivers | SnT |
| `platform.id` | Channel ID | 8 Lazada, 15 Shopee, 54 Qoo10, 56 Zalora, 74 Shopify, 404 TikTok | OF, BW, TA |
| `platform.name` / `platform.group` / `platform.country_code` | Channel name, group, country | LEL sends `GROUP_CC` (e.g. LAZADA_VN) | OF, TN, LEL, FL, BM, SnT |
| `platform.currency` | Channel currency | | LEL, BM, SnT |
| `shop.name` | Store name | | TN |
| `order_item.quantity` | Ordered quantity | Bundles split into component SKUs (BM, ZTO) | All |
| `order_item.unit_price` / `order_item.paid_price` | Unit price / paid price | | TN, SnT / LEL, FL |
| `order_item.voucher_amount` | Item discount | | SnT |
| `order_item.info.cod_line_total` | COD amount per line | COD = sum of lines + shipping fee | OF, TN |
| `payment_method.master_name` | Payment method | `cod` triggers COD amount | TN, LEL |
| `order_item.cancel_reason` | Cancellation reason | First cancelled item | TN, BW, LEL |

## WMS sales order (WMS side record)

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `wms_sale_order.partner_so_id` | Order reference at the partner | **See C2** | OF, TN, BW, ES, FL, BM, NH, SnT |
| `wms_sale_order.so_code` | Order code used with the WMS | **See C2** | TN, BW, ES, IM, BL, FL, BM |
| `wms_sale_order.org_order_id` | Original order ID | | ES, IM, BL, BM |
| `wms_sale_order.sc_order_number` | Marketplace order number on the WMS record | | ES, IM, BL |
| `wms_sale_order.status` | WMS order status (backend) | See `status-model.md` | ES, IM, BL |
| `wms_sale_order.tracking_number` | Tracking number from WMS | | TN, ES, IM, BL, SnT |
| `wms_sale_order.package_code` | Package ID from WMS | Used to upload AWB (LEL) | LEL, SnT |
| `wms_sale_order.wms_warehouse_id` | Fulfilling warehouse | | LEL |
| `wms_sale_order.total_amount` | COD amount sent | | BM |
| `wms_sale_order.updated_at` | Last WMS status update | | SnT |
| `wms_sale_order_detail.quantity` / `price` / `product_id` | Line on the WMS record | | TN, BM, SnT |

## Customer and address

**See C9** — three field sets are in use.

| PowerSell field | Meaning | Seen in |
|---|---|---|
| `customer.name` / `phone` / `country` + `address.address` + `location.city` / `district` / `postal_code` | Recipient via customer and address tables | OF, TN, SnT, LEL (returns) |
| `order_customer.name` / `phone` / `address` / `city` / `district` / `ward` / `country` / `postal_code` | Recipient stored on the order | BW, ES, IM, BL, FL, TA |
| `shipping_customer.name` + `customer.phone` + `address.*` (encrypted) | Recipient via shipping customer | BM |
| `order.shipping_address_id` / `order.shipping_customer_id` | Links to address / customer | OF, LEL |

## Shipping (AWB, carrier, package)

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `order_item.tracking_number` | AWB / tracking number | Blank for Shopee channels 70123–70126 (BL tag `#no_tracking`) | All |
| `order_item.package_number` | Marketplace package ID | | BW, SnT |
| `order_billing.info.awb_url` | Shipping label URL | **See C3** | TN, SnT, TA |
| `shipment_provider.id` / `shipment_provider.name` / `order.shipment_provider` | Carrier | BW maps carrier IDs to its courier list; seller-delivery stores need a carrier code per store (IM, ES) | TN, BW, ES, IM, FL, SnT |

Delivery speed (instant, same-day, next-day) is read from channel data, not a PowerSell
field: TikTok `fulfillment_priority_level` and Shopee carrier / `logistics_channel_id`.
See the Shopee and TikTok Shop detection PRDs.

## Return and failed delivery

| PowerSell field | Meaning | Rules seen in mappings | Seen in |
|---|---|---|---|
| `order_return_reconcile.id` | PowerSell return reference | Sent as return number | OF, TN, ES, IM, BL, SnT |
| `order_return_reconcile.return_type` | `FAILED_DELIVERY` or `CUSTOMER_RETURN` | | BL |
| `order_return_reconcile.wms_ref_no` | Return reference at the partner | **See C8** | OF, BW, SnT |
| `order_return_reconcile.wms_display_no` | Partner's readable return number | | BW |
| `order_return_reconcile.platform_return_request_id` | Channel return request ID | | TN, BL, FL |
| `order_return_reconcile.customer_name` | Returning customer | | TN, BL, NH |
| `order_return_reconcile.return_created_at` / `received_at` | Return created / received | | BL, SnT |
| `order_return_reconcile_item.expected_qty` | Expected quantity per SKU | | OF, TN, ES, IM, BL, NH, SnT |
| `order_return_reconcile_item.return_tracking_id` | Return tracking number | | OF, TN, ES, IM, BL, SnT |
| `order_return_reconcile_item.detail_reason` | Reason per item | **See C13**; default "Created by PowerSell" | TN, BL, NH, SnT |
| `order_return.id` / `currency` / `sc_return_number` / `order_id` | Channel return record | | LEL |
| `order_item_return.sc_return_item_number` / `quantity` / `unit_price` / `tracking_number` | Channel return item | | LEL, BW |
| `wms_exchange_order.wms_ref_no` | Return / failed-delivery reference at the partner | **See C8** | OF, TN, LEL, BL, NH |
| `wms_exchange_order.received_at` / `created_at` | Received / created | | OF, TN, BW, ES, IM, BL |
| `wms_exchange_order_item.original_quantity` | Expected quantity on WMS record | | BW, ES, IM, BL |
| `wms_exchange_order_item.accepted_quantity` / `damaged_quantity` | Good / damaged quantity | **See C7** | OF, BW, LEL, BL |

---

## Cross-partner rules

These rules repeat across several docs and should be the default for new partners:

- **Received quantity** = sum across all receipts (GRNs), counting good / putaway stock only.
- **ASN completion**: Completed only when received = expected; otherwise Pending Receipt.
- **Return quantities**: receipt = accepted + damaged; lost = expected − receipt.
- **Returns** are sent to a WMS only if that WMS fulfilled the original order.
- **Dropship items** are never sent to a WMS (BM, FL, TA, ZTO, offline doc).
- **Bundles** are broken into component SKUs before sending (BM, ZTO).
- **COD amount** = sum of item COD + shipping fee, only when the WMS also delivers and
  payment is COD; otherwise 0 (offline doc, TN).
- **Masked addresses** from channels: send placeholder values (BL: province "00", postal
  "00000").
- **Partial cancellation** updates the WMS order; full cancellation cancels it (BL).
- **Errors** shown to users as `WMS error: <reason>`.

---

## Conflicts to resolve

| ID | Topic | What the docs say | Question for dev |
|---|---|---|---|
| C1 | Partner product ID vs SKU | `partner_id` = partner's internal product ID in OF, BW, LEL; = partner SKU in TN, ES, IM, SnT, TA, NH. FL has no partner product ID and uses `product.barcode` as the key. TN stores partner ID in `partner_key` (reverse of BW, LEL). BL contradicts itself inside one doc | Canonical rule for `partner_id` vs `partner_key`? |
| C2 | Order references | `partner_so_id` = partner order code (TN, ES, FL create), our marketplace order no. (BW), Boxme tracking no. (BM), N&H tracking code (NH), our order number (SnT). `so_code` = our reference (TN, ES, IM), partner order ID (BW, BL, FL webhook), platform order no. (BM). Order number sent: `order.order_number` (TN, ES, IM, LEL, SnT), `order.sc_order_number` (BW, FL, TA), `order.id` + `sc_order_number` (BL), both (OF) | What do `so_code` and `partner_so_id` mean, and which order number is the default to send? |
| C3 | AWB file URL | `order_billing.info.awb_url` (TN, SnT, TA) vs `order_billing.info.url_awb` (ES, IM, BL) vs `auto_processing_order.awb_path` (BW, LEL) | Which is correct? |
| C4 | Shelf-life fields | With `.info.` (OF, TN, FL) vs without (BW, LEL) for `expiry_threshold`, `reject_shelf_life`, `shelf_life_alert` | Which paths are correct? |
| C5 | Weight and fragile | `package_weight` vs `product_weight` (FL uses both, for different partner fields). Fragile: `product.info.is_fragile` (OF), `product.is_fragile` (ES), `Product.Is_fragile` (IM) | Are these two weights different fields, and which is the default? Which fragile path? |
| C6 | ASN secondary reference | `wms_asn.reference_no` = partner ref code (TN), partner ASN UUID (BW), partner PO code (OF); GRN in `wms_asn.wms_reference_no` (SnT) | What should `reference_no` hold, and where do GRNs go? |
| C7 | Return received quantities | `wms_exchange_order_item.accepted_quantity` / `damaged_quantity` (OF, BW, LEL, BL) vs `total_accepted_quantity` / `total_damaged_quantity` (ES, IM) vs `total_received_quantity` / `total_receipt_quantity` (TN, BL) vs `order_return_reconcile.accepted_qty` / `damaged_qty` (SnT) | Canonical fields? |
| C8 | Return partner reference | `wms_exchange_order.wms_ref_no` (OF, TN, LEL, BL, NH) vs `order_return_reconcile.wms_ref_no` (BW, SnT, OF); `wms_exchange_order.wms_ref_code` also used (TN, FL, NH) | Which table and field? |
| C9 | Customer and address | `customer.*` + `address.*` + `location.*` (OF, TN, SnT) vs `order_customer.*` (BW, ES, IM, BL, FL, TA) vs `shipping_customer.*` (BM). FL mixes `order_customer.*` with `address.address` | Which set should new mappings use? |
| C10 | Typos in source docs | `product.inventory sku` (BW, ES, IM, BL), `product.info.min stock alert` (BL), `Product.Is_fragile` (IM), `wms_asn.special_instrcution` (SnT), `wms_asn.asn_partner_id` (FL), `wms_product.partner.id` (TN), `order_return.order_created.at` (BW) | Fix in source pages |
| C11 | ASN received quantity | `wms_asn_detail.quantity_received` (all) vs `wms_asn_detail.received_quantity` (LEL) | Confirm `quantity_received` |
| C12 | ASN notes | `wms_asn.special_instruction` (most) vs `wms_asn_detail.special_handling_instructions` (LEL) | Header or line level? |
| C13 | Return reason | `order_return_reconcile_item.detail_reason` (TN, BL, NH, SnT) vs `order_return.dispute_reason` (BW) vs `order_return.dispute_text_reason` (LEL) | Which field is the default? |

## Errors found in source docs

Likely mistakes, not design conflicts. Fix in the source pages:

| Doc | Issue |
|---|---|
| LEL V2 | Payment mapping looks inverted (COD → `NON_COD`); dimensions say "convert to gram"; `serial_number_flag` mapped from `product.storage_type` |
| BetterLand | Order webhook maps `TrackingNo` → `wms_sale_order.status`; product IDs contradict between endpoints |
| Flash | Shelf-life note mentions "TNSL" (copy-paste); create response vs webhook disagree on `partner_so_id` / `so_code` |
| N&H Return | `group_platform` → `wms_exchange_order.wms_ref_no`; expected qty calculated as received − damaged |
| IM Logistics - Return | Return status mapping section is empty |
