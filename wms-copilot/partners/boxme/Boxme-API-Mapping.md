# Boxme – API Mapping (PowerSell × Boxme WMS)

> **DRAFT v0.1 — not approved.** Built before gate G3 (scope) and before any smoke test. Every `[TBD: Q-xx]` waits on Boxme's answer (tracker Q&A log); every `[CONFIRM: Cx / Sx]` waits on PowerSell dev confirmation of the reference data model. **Do not build from rows marked `[TBD]` or `[CONFIRM]`.**

---

# Document control

| | |
|---|---|
| **Ideal launching date** | [TBD] |
| **Epic** | [TBD: Jira epic] |
| **Document owner** | [TBD] |
| **Stakeholder** | PowerSell dev lead (approver, G4); WMS partner PIC |

# Revision History

| **Version** | **Updated by** | **Description** | **Stakeholder** |
|---|---|---|---|
| v0.1 | WMS integration copilot, 2026-11-14 | Initial draft from Boxme Open API v2 (doc export 2026-11-13), S3 logic notes and S4 Phase 1 scope | |

# Table of contents

- [✍️ Reference documents](#reference-documents)
- [Authentication and technical rules](#authentication-and-technical-rules)
- [Flow overview](#flow-overview)
- [🔖 1. Config](#1-config)
- [🔖 2. Product management](#2-product-management)
- [🔖 3. Inbound (ASN)](#3-inbound-asn)
- [🔖 4. Outbound](#4-outbound)
- [🔖 5. Return management](#5-return-management)
- [🔖 6. Webhooks](#6-webhooks-boxme--powersell)
- [🚫 Out of scope](#out-of-scope)
- [❓ Open questions](#open-questions)

---

# ✍️ Reference documents

- Boxme Open API v2: https://developers.boxme.asia/doc-393601 (export of all 103 pages, latest changelog 11-06-2026)
- PowerSell: Boxme – WMS Integration Tracker; Boxme – API Evaluation Scorecard (96); Boxme – System Logic Notes (S3); Boxme – Use-Case Fit (S4)

## Staging credentials
- **No staging environment.** Boxme provides a test seller account on **production** with no financial cost.
- Test account URL: https://oms.boxme.asia — login and API key are held by the WMS partner PIC (**not stored in this document**).

## API credentials
- BaseURL (production, also used for tests): `https://s.boxme.asia`
- API key: one per brand (seller account), created in oms.boxme.asia → Settings → API Integration. **Mask in all documents.**
- Postman collection: "Boxme – S3 smoke tests (Batch B)" (PIC's Postman workspace)

# User stories

[TBD: Jira epic JQL filter]

---

# Authentication and technical rules

| Topic | Rule |
|---|---|
| Header | `Authorization: Token <API_KEY>` on every request. HTTPS only. `Content-Type: application/json` |
| Credentials | One API key per brand / Boxme seller account. Max lifetime **365 days** (since 25/07/2026): store the expiry date and alert 30 days before |
| IP whitelist | Boxme accepts calls only from registered, approved server IPs (oms.boxme.asia → Setting). **Re-confirm every 180 days.** Non-whitelisted IP → HTTP 403 |
| Auth errors | Missing / invalid key returns **HTTP 403** `authentication_failed` (doc says 401, D-09). Treat 401 and 403 + `authentication_failed` as "credential problem": stop syncing that brand and alert |
| Rate limits | **Per IP**: Create Order 2 / sec; Get Shipping Option 2 / sec; Create Product, Get Stock, Get Products, Get Order List 1 / sec (list endpoints also 30 / min); Get Order 60 / min. Over limit → HTTP 503 `traffic_limit` / `quota_limit`: retry with backoff. All brands share the limit (R-01) |
| Response envelope | `{ "data", "error", "error_code", "messages", "request_id" }`; 4xx may add `error_data`, `additional_infos` |
| Error display | `WMS error: <messages>` (store `request_id` in logs) |
| Dates | Unix timestamp (seconds). Convert from / to the brand's local time |
| Units | Weight grams (integer). Volume text `LxWxH` (unit `[TBD: Q-21]`). Shelf life months; expiry thresholds unit `[TBD: Q-08]`. Money in market currency; TH COD integer |
| Webhooks | URL set per brand by the brand's business user in oms.boxme.asia, from the PowerSell Boxme connection user guide. Header `Authorization: <WEBHOOK_TOKEN>`: verify. Reply **HTTP 200 within 3 s** and process asynchronously; retries after 2 min, 30 min, 3 h. Deduplicate on `request_id`; ignore events older than the last processed `update_time` |
| Duplicate protection | Product `seller_sku_existed`, ASN `po_number_duplicated`, order `DUPLICATED_ORDER`. For product and ASN, take the existing ID from `additional_infos` and treat as success |

---

# Flow overview

| Flow | Sequence |
|---|---|
| Product | 2.3 Create product → (Boxme approval `[TBD: Q-11]`) → 6.3 Product update push; 2.4 on changes |
| Stock | 6.2 Available stock change push (real time) + 2.6 Get stock available (daily reconciliation) |
| Inbound | 3.1 Create ASN → (3.2 + 3.3 booking if status `12`) → 6.1 ASN status push → on `11` / `6`: 3.6 Get receiving note → 3.4 Cancel ASN when needed |
| Order – marketplace delivery | 4.2 Create order (`BM_DBS`, status `110`) → PowerSell arranges shipment on channel and gets AWB → 4.3 Order pack (label + tracking) → 6.4 Order status push (`201` … `211` Ready to ship … `300` Shipped → `801` Fulfilled) |
| Order – instant (marketplace) | 4.2 Create order with `fulfill_now: true` → 4.3 Order pack (`fulfill_type: now`, tracking = marketplace order no.) → 6.4 `211` Ready to ship → PowerSell confirms order on channel → carrier picks up |
| Order – Boxme delivery | 4.1 Get shipping option → 4.2 Create order (`delivery_service` = chosen `service_code`, COD if any) → 6.4 status push through delivery (`304`, `310`, `800` Delivered or `400` → `420` → `600` Returned) |
| Which delivery per order | `[TBD: R-13]` Proposed: marketplace orders → marketplace logistics; webstore / other → Boxme delivery |
| Cancel | 4.5 Cancel order (before shipping); 4.6 Request cancel delivery (Boxme delivery, after shipping) |
| Return | 5.1 Create return (marketplace returns / failed deliveries of marketplace-delivered orders) → 6.6 Return status push → on `600`: 5.3 Get returns receive; 5.4 Cancel return |

---

# 🔖 1. Config

## 1.1 Get warehouse list (Get Pickup List)

#### Purpose

Import the brand's Boxme warehouses into PowerSell warehouse mapping.

**When PowerSell calls it:** When the brand connects Boxme, and on a "refresh warehouses" action.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/sellers/pickup
```
Boxme reference: https://developers.boxme.asia/api-5002019

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/sellers/pickup' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `page` | query | N |  | N/A |  |
| `page_size` | query | N |  | N/A |  |

#### Response

*No sample response in Boxme doc.*

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A | Paging |
| `data.pickup` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.pickup[].pickup_id` | Integer | N |  | `wms_warehouse.partner_warehouse_id` | Boxme warehouse ID. Used as `pickup_id` on every product, ASN, order and return call |
| `data.pickup[].country` | String | N |  | N/A | Use to filter warehouses by the brand's country |
| `data.pickup[].warehouse_code` | String | N |  | `wms_warehouse.reference_code` | Entries **with** a warehouse_code are Boxme warehouses; entries without are seller pickup addresses and are **not** imported `[TBD: Q-23]` |
| `data.pickup[].pickup_name` | String | N |  | `wms_warehouse.partner_warehouse_name` |  |
| `data.pickup[].contact_name` | String | N |  | `wms_warehouse.contact_name` |  |
| `data.pickup[].contact_phone` | String | N |  | `wms_warehouse.contact_phone` |  |
| `data.pickup[].address` | String | N |  | `wms_warehouse.address` | Concatenate with sub-district, district and province names for display |
| `data.pickup[].province_id` | Integer | N |  | N/A | Display only |
| `data.pickup[].province_name` | String | N |  | N/A | Display only |
| `data.pickup[].district_id` | Integer | N |  | N/A | Display only |
| `data.pickup[].district_name` | String | N |  | N/A | Display only |
| `data.pickup[].sub_district_id` | Integer | N |  | N/A | Display only |
| `data.pickup[].sub_district_name` | String | N |  | N/A | Display only |
| `data.pickup[].zipcode` | String | N |  | N/A | Display only |
| `data.pickup[].lat` | String | N |  | N/A | Display only |
| `data.pickup[].lng` | String | N |  | N/A | Display only |
| `data.pickup[].active` | Integer | N |  | `wms_warehouse.status` | 1 = active, 0 = inactive |
| `data.pickup[].created_time` | Integer | N |  | N/A | Display only |
| `data.pickup[].updated_time` | Integer | N |  | N/A | Display only |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.2 Get provinces

#### Purpose

Build the Boxme location mapping (province level).

**When PowerSell calls it:** Once per country, then monthly or on demand. Vietnam location database changed 25/10/2025.

#### Endpoint

```
GET https://s.boxme.asia/api/v3/location/{country_code}/provinces/
```
Boxme reference: https://developers.boxme.asia/api-4888023

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v3/location/{country_code}/provinces/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `country_code` | path | **Y** |  | N/A | VN / TH / PH |
| `is_new_address` | query | N | set to True to get new administrative in VN | N/A |  |

#### Response

```json
{
  "data": {
    "total_count": 63,
    "provinces": [
      {
        "id": 1,
        "code": "HNI",
        "country_code": "VN",
        "province_name": "Hà Nội",
        "province_name_local": "Hà Nội"
      },
      {
        "id": 2,
        "code": "HGG",
        "country_code": "VN",
        "province_name": "Hà Giang",
        "province_name_local": "Hà Giang"
      },
      {
        "id": 4,
        "code": "CBG",
        "country_code": "VN",
        "province_name": "Cao Bằng",
        "province_name_local": "Cao Bằng"
      },
      {
        "id": 6,
        "code": "BKN",
        "country_code": "VN",
        "province_name": "Bắc Kạn",
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.provinces` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.provinces[].id` | Integer | **Y** |  | [TBD] | Boxme province ID. Store in the Boxme location mapping table `[TBD: Q-32]`, matched to PowerSell `location.*` by name |
| `data.provinces[].code` | String | **Y** |  | N/A |  |
| `data.provinces[].country_code` | String | **Y** |  | N/A |  |
| `data.provinces[].province_name` | String | **Y** |  | N/A | Match key to `location.city` `[CONFIRM: C9]` |
| `data.provinces[].province_name_local` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.3 Get districts

#### Purpose

Location mapping, district level.

**When PowerSell calls it:** With 1.2.

#### Endpoint

```
GET https://s.boxme.asia/api/v3/location/{country_code}/provinces/{province_id}/districts/
```
Boxme reference: https://developers.boxme.asia/api-4888582

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v3/location/{country_code}/provinces/{province_id}/districts/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `country_code` | path | **Y** |  | N/A | VN / TH / PH |
| `province_id` | path | **Y** |  | N/A | From 1.2 |

#### Response

```json
{
  "data": {
    "total_count": 707,
    "districts": [
      {
        "id": 19,
        "code": "",
        "country_code": "VN",
        "province_id": 1,
        "district_name": "Quận Nam Từ Liêm",
        "district_name_local": "Quận Nam Từ Liêm"
      },
      {
        "id": 20,
        "code": "",
        "country_code": "VN",
        "province_id": 1,
        "district_name": "Huyện Thanh Trì",
        "district_name_local": "Huyện Thanh Trì"
      },
      {
        "id": 21,
        "code": "",
        "country_code": "VN",
        "province_id": 1,
        "district_name": "Quận Bắc Từ Liêm",
        "district_name_local": "Quận Bắc Từ Liêm"
      },
      {
        "id": 250,
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.districts` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.districts[].id` | Integer | **Y** |  | [TBD] | Boxme district ID. Store in the Boxme location mapping table `[TBD: Q-32]`, matched to PowerSell `location.*` by name |
| `data.districts[].code` | String | **Y** |  | N/A |  |
| `data.districts[].country_code` | String | **Y** |  | N/A |  |
| `data.districts[].province_id` | Integer | **Y** |  | N/A |  |
| `data.districts[].district_name` | String | **Y** |  | N/A | Match key to `location.district` `[CONFIRM: C9]` |
| `data.districts[].district_name_local` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.4 Get sub-districts

#### Purpose

Location mapping, sub-district level.

**When PowerSell calls it:** With 1.2.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/sellers/locations/{country_code}/provinces/{province_id}/districts/{district_id}/sub-districts
```
Boxme reference: https://developers.boxme.asia/api-4888583

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/sellers/locations/{country_code}/provinces/{province_id}/districts/{district_id}/sub-districts' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `country_code` | path | **Y** |  | N/A | VN / TH / PH |
| `province_id` | path | **Y** |  | N/A | From 1.2 |
| `district_id` | path | **Y** |  | N/A | From 1.3 |

#### Response

```json
{
  "data": {
    "total_count": 10729,
    "subdistricts": [
      {
        "id": 592,
        "province_id": 1,
        "district_id": 19,
        "country_code": "VN",
        "sub_district_name": "Phường Cầu Diễn",
        "sub_district_local": "Phường Cầu Diễn"
      },
      {
        "id": 595,
        "province_id": 1,
        "district_id": 21,
        "country_code": "VN",
        "sub_district_name": "Phường Thượng Cát",
        "sub_district_local": "Phường Thượng Cát"
      },
      {
        "id": 598,
        "province_id": 1,
        "district_id": 21,
        "country_code": "VN",
        "sub_district_name": "Phường Liên Mạc",
        "sub_district_local": "Phường Liên Mạc"
      },
      {
        "id": 601,
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.subdistricts` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.subdistricts[].id` | Integer | **Y** |  | [TBD] | Boxme sub-district ID. Store in the Boxme location mapping table `[TBD: Q-32]`, matched to PowerSell `location.*` by name |
| `data.subdistricts[].province_id` | Integer | **Y** |  | N/A |  |
| `data.subdistricts[].district_id` | Integer | **Y** |  | N/A |  |
| `data.subdistricts[].country_code` | String | **Y** |  | N/A |  |
| `data.subdistricts[].sub_district_name` | String | **Y** |  | N/A | Match key to ward `[CONFIRM: C9]` |
| `data.subdistricts[].sub_district_local` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.5 Lookup zipcode

#### Purpose

Find province / district by postal code (TH, PH).

**When PowerSell calls it:** When an address has a postal code but no matched IDs. **Doc path shows `/pi/v2/…`; probably `/api/v2/…` (Q-10).**

#### Endpoint

```
GET https://s.boxme.asia/pi/v2/sellers/locations/{country_code}/zipcodes
```
Boxme reference: https://developers.boxme.asia/api-4888680

#### Request

```bash
curl -X GET 'https://s.boxme.asia/pi/v2/sellers/locations/{country_code}/zipcodes' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `country_code` | path | **Y** |  | N/A | VN / TH / PH |
| `zipcode` | query | N |  | N/A |  |

#### Response

```json
{
  "data": {
    "total_count": 1,
    "zipcodes": [
      {
        "id": 788785,
        "country_code": "TH",
        "province_id": 190,
        "province_name": "Bangkok",
        "province_name_local": "กรุงเทพมหานคร",
        "district_id": 3356,
        "district_name": "Lad Krabang",
        "district_name_local": "เขตลาดกระบัง",
        "zipcode": "10520",
        "to_zipcode": "10520",
        "is_remote": 0
      }
    ]
  },
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": 1703235643
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.zipcodes` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.zipcodes[].id` | Integer | N |  | N/A |  |
| `data.zipcodes[].country_code` | String | N |  | N/A |  |
| `data.zipcodes[].province_id` | Integer | N |  | N/A | Alternative lookup by postal code (TH / PH) |
| `data.zipcodes[].province_name` | String | N |  | N/A |  |
| `data.zipcodes[].province_name_local` | String | N |  | N/A |  |
| `data.zipcodes[].district_id` | Integer | N |  | N/A |  |
| `data.zipcodes[].district_name` | String | N |  | N/A |  |
| `data.zipcodes[].district_name_local` | String | N |  | N/A |  |
| `data.zipcodes[].zipcode` | String | N |  | N/A |  |
| `data.zipcodes[].to_zipcode` | String | N |  | N/A |  |
| `data.zipcodes[].is_remote` | Boolean | N |  | N/A | Remote area flag (may add surcharge with Boxme delivery) |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.6 Get courier list

#### Purpose

Courier names accepted in Order Pack.

**When PowerSell calls it:** Once at setup, to build the carrier mapping table.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/courier/names
```
Boxme reference: https://developers.boxme.asia/api-5266298

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/courier/names' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `courier_name` | query | N |  | N/A |  |

#### Response

```json
{
  "data": [
    "Best Express",
    "Boxme Express",
    "DPEX Express",
    "Grab Express",
    "J&T Express",
    "Selly Express",
    "Shopee Express",
    "Snappy Express",
    "Tiki Express",
    "Vietpost Express",
    "ZTO Express"
  ],
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "65a9f686b778e5b71085c901"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Array[String] | **Y** |  | N/A | List of courier names accepted in Order Pack `self_shipment.courier_name`. Map each PowerSell `shipment_provider.name` to one value `[TBD]` (mapping table in connection settings) |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 1.7 Get courier services

#### Purpose

Boxme delivery service codes.

**When PowerSell calls it:** Setup reference for Boxme delivery (UC-14).

#### Endpoint

```
GET https://s.boxme.asia/api/v2/courier/services
```
Boxme reference: https://developers.boxme.asia/api-5100313

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/courier/services' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `keyword` | query | N | Filter by courier name, service name | N/A |  |

#### Response

```json
{
  "data": {
    "total_count": 48,
    "services": [
      {
        "courier_name": "Boxme Express",
        "courier_logo": "https://app.omisell.com/assets/customize/images/courier/Boxme_EXPRESS.svg",
        "service_code": "BM_RE",
        "service_name": "Return Parcel"
      },
      {
        "courier_name": "Boxme Express",
        "courier_logo": "https://app.omisell.com/assets/customize/images/courier/Boxme_EXPRESS.svg",
        "service_code": "BM_DBS",
        "service_name": "Self-Delivery"
      },
      {
        "courier_name": "Boxme Express",
        "courier_logo": "https://app.omisell.com/assets/customize/images/courier/Boxme_EXPRESS.svg",
        "service_code": "BM_TRUCK_1000",
        "service_name": "Xe tải 1,000 kg"
      },
      {
        "courier_name": "Boxme Express",
        "courier_logo": "https://app.omisell.com/assets/customize/images/courier/Boxme_EXPRESS.svg",
        "service_code": "BM_TRUCK_500",
        "service_name": "Xe tải 500 kg"
      },
      {
        "courier_name": "Boxme Express",
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.services` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.services[].courier_name` | String | **Y** |  | N/A |  |
| `data.services[].courier_logo` | String | **Y** |  | N/A |  |
| `data.services[].service_code` | String | **Y** |  | N/A | Boxme delivery service codes (used in Create Order `config.delivery_service`) |
| `data.services[].service_name` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

---

# 🔖 2. Product management

## 2.1 Get category tree

#### Purpose

Boxme product categories for `category_id`.

**When PowerSell calls it:** Setup: build category mapping.

#### Endpoint

```
GET https://s.boxme.asia/api/v2.1/sellers/products/categories/
```
Boxme reference: https://developers.boxme.asia/api-5002022

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2.1/sellers/products/categories/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

#### Response

```json
{
  "data": {
    "total_count": 37,
    "categories": [
      {
        "id": 128,
        "name": "PaperBag"
      },
      {
        "id": 127,
        "name": "Services"
      },
      {
        "id": 126,
        "name": "Spare Parts"
      },
      {
        "id": 125,
        "name": "Wellness/Personal Care"
      },
      {
        "id": 109,
        "name": "Food & Beverages"
      },
      {
        "id": 108,
        "name": "Footwear"
      },
      {
        "id": 107,
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.categories` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.categories[].id` | Integer | **Y** |  | [TBD] | Boxme category ID. Map PowerSell `product_category.name` → id in a category mapping table `[TBD: Q-33]`. Fallback: 23 (Other) `[CONFIRM]` |
| `data.categories[].name` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.2 Get product units

#### Purpose

Reference list of units of measure.

**When PowerSell calls it:** Reference only.

#### Endpoint

```
GET https://s.boxme.asia/api/v2.1/sellers/products/uom
```
Boxme reference: https://developers.boxme.asia/api-5032586

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2.1/sellers/products/uom' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

#### Response

```json
{
  "data": [
    {
      "uom": "PC",
      "name": "PC"
    },
    {
      "uom": "PAC",
      "name": "PAC"
    },
    {
      "uom": "SET",
      "name": "SET"
    },
    {
      "uom": "PAIR",
      "name": "PAIR"
    },
    {
      "uom": "BOX",
      "name": "BOX"
    }
  ],
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "6618fa3f97b604a170328256"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data[].uom` | Integer | **Y** |  | N/A | Reference only. PowerSell always sends `PC` (bundles are split into components) |
| `data[].name` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.3 Create product

#### Purpose

Create a PowerSell SKU at Boxme (UC-02).

**When PowerSell calls it:** When a SKU is assigned to a Boxme warehouse, or the user clicks "Sync to WMS". Rate limit 1 / sec / IP. Boxme may need to approve the product before first inbound (Q-11).

#### Endpoint

```
POST https://s.boxme.asia/api/v2.1/sellers/products/create/
```
Boxme reference: https://developers.boxme.asia/api-5002021

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2.1/sellers/products/create/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"name": "Sản Phẩm 01", "seller_sku": "SP00012001", "barcode_manufacturer": "WH23454808", "category_id": 3, "brand": "Test Brand", "description": "Enter when there is a QC request for the product before warehouse entry.", "price": 1000000, "sale_price": 1200000, "wholesale_price": 0, "is_digital": false, "min_quantity": 1, "warehouse_condition": 1, "pack_with_bubble": false, "pack_material": 2, "weight": 3000, "volume": "27x36x11", "images": [], "manage_by_serial_number": false, "managed_by_gs1": false, "require_expire": true, "outbound_strategy": "FEFO", "shelf_life": 12, "expiry_threshold": 3, "min_inbound_shelf_life": 6, "is_fragile": true, "use_shredded_paper": true, "batch_control": false, "uom": "PC", "protective_packaging_inbound": false, "allow_breakdown": false}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `name` | String | **Y** | Product name | `product.name` |  |
| `seller_sku` | String | **Y** | SKU | `product.inventory_sku` | Main product key at Boxme. Must be unique per seller |
| `barcode_manufacturer` | String | **Y** | Manufacture barcode, separate by commas | `product.barcode`, `product.backup_barcode` | Comma-separated: main barcode first, then backup barcodes |
| `category_id` | Integer | **Y** | Product category. Refer to Category API | [TBD] | From category mapping table (see 2.1) `[TBD: Q-33]` |
| `description` | String | **Y** | Product description | `product.name` | PowerSell has no description field; send product name |
| `price` | Number | **Y** | Listed price | `product.retail_price` |  |
| `is_digital` | Boolean | **Y** | Physical product. Default is false | N/A | Default `false` |
| `min_quantity` | Integer | **Y** | Threshold number | `product.info.min_stock_alert` | Default `0` when empty `[CONFIRM: Q-33]` |
| `warehouse_condition` | Integer | **Y** | 1. Normal, 2. Aircond | `product.storage_type` | Ambient → `1`; Air-conditioning → `2`; Chilled / Freezer → **no Boxme value: block product sync and show `WMS error: Boxme does not support chilled / frozen storage`** (R-09) |
| `pack_with_bubble` | Boolean | **Y** | Require bubble wrap | N/A | Default `false` `[CONFIRM: Q-33]` |
| `pack_material` | Integer | **Y** |  | N/A | Default `[TBD: Q-33]` (Product API overview: 1 bag, 2 carton, 3 bubble wrap, 4 none, 5 branded carton, 6 branded bag, 7 other, 8 plastic wrap) |
| `weight` | Integer | **Y** | Item weight (grams) | `product.package_weight` `[CONFIRM: C5]` | Grams, integer. PowerSell grams sent as-is |
| `volume` | String | **Y** | Item volume. LxWxH | `product.package_length` × `product.package_width` × `product.package_height` | Text `"{L}x{W}x{H}"`. PowerSell cm; Boxme unit `[TBD: Q-21]` (if mm, multiply by 10) |
| `manage_by_serial_number` | Boolean | **Y** | Product require aftersale service by serial number. | `product.serial_imei_management` | `1` → `true`, else `false` |
| `managed_by_gs1` | Boolean | **Y** | Product use GS1 to manage product information. It is global standard | N/A | Default `false` |
| `require_expire` | Boolean | **Y** | Product require manage exp. | `product.expiration_time` | `true` when `expiration_time` is not NULL, else `false` |
| `outbound_strategy` | String | **Y** | FIFO, FEFO, LIFO | `product.valuation_method` | FIFO / FEFO / LIFO sent as-is. FMFO or empty → `FEFO` if require_expire, else `FIFO` `[CONFIRM]` |
| `shelf_life` | Integer | **Y** | Shelf life. Exp:12,18,36 months | `product.expiration_time` | Months. `0` when NULL |
| `expiry_threshold` | Integer | **Y** | Expire time threshold (day). | `product.info.expiry_threshold` `[CONFIRM: C4]` | Minimum remaining shelf life to ship. Unit: days in Create Product, months in Update / Get `[TBD: Q-08]` |
| `min_inbound_shelf_life` | Integer | **Y** | Min inbound expire time (day) | `product.info.reject_shelf_life` `[CONFIRM: C4]` | Minimum remaining shelf life to accept at inbound. Unit `[TBD: Q-08]` |
| `is_fragile` | Boolean | **Y** | Fragile item | `product.info.is_fragile` `[CONFIRM: C5]` | Default `false` |
| `use_shredded_paper` | Boolean | **Y** |  | N/A | Default `false` |
| `batch_control` | Boolean | **Y** | Batch LOT control | N/A | Default `false` `[CONFIRM: Q-33]` (consider `true` when require_expire) |
| `uom` | String | **Y** | PAC, PC, SET, PAIR, BOX | N/A | Default `PC` |
| `protective_packaging_inbound` | Boolean | **Y** | Require prepack before inbound | N/A | Default `false` |
| `allow_breakdown` | Boolean | **Y** | Allow automate breakdown | N/A | Default `false` |
| `brand` | String | N | Brand name. | `product.brand` | Optional |
| `images` | Array[String] | N | Product Images: https://imag.png | `product_media.url` | All images, oldest first |
| `sale_price` | Number | **Y** | Retail price (RSP) | `product.retail_price` |  |
| `wholesale_price` | Number | **Y** | Wholesale price (B2B) | N/A | Default `0` `[CONFIRM: Q-33]` |

#### Response

```json
{
  "data": {
    "bsin": "BSN83477384388434"
  },
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": 1703470457
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.bsin` | String | **Y** |  | `wms_product.partner_id` `[CONFIRM: C1]` | Boxme product ID. Used in Update Product path |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.4 Update product

#### Purpose

Update a product at Boxme.

**When PowerSell calls it:** When synced product fields change in PowerSell. After Boxme approval only some fields can change, and the product may be re-approved; name can change only before the first ASN.

#### Endpoint

```
PUT https://s.boxme.asia/api/v2.1/sellers/products/update/{bsin}/
```
Boxme reference: https://developers.boxme.asia/api-5002026

#### Request

```bash
curl -X PUT 'https://s.boxme.asia/api/v2.1/sellers/products/update/{bsin}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"seller_sku": "SKU012132", "category_id": 1, "brand": "No Band", "price": 100000, "sale_price": 120000, "wholesale_price": 80000}'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `bsin` | path | **Y** |  | `wms_product.partner_id` |  |

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `name` | String | N | Product name. Can be edit before create ASN | `product.name` |  |
| `seller_sku` | String | N | SKU. It can be edited after the product is approved. | `product.inventory_sku` | Main product key at Boxme. Must be unique per seller |
| `barcode_manufacturer` | String | N | Manufacture barcode, separate by commas | `product.barcode`, `product.backup_barcode` | Comma-separated: main barcode first, then backup barcodes |
| `category_id` | Integer | N | Product category. Refer to Category API. It can be edited after the product is approved. | [TBD] | From category mapping table (see 2.1) `[TBD: Q-33]` |
| `description` | String | N | Product description. It can be edited after the product is approved | `product.name` | PowerSell has no description field; send product name |
| `price` | Integer | N | Listed price. It can be edited after the product is approved | `product.retail_price` |  |
| `is_digital` | Boolean | N | Physical product. Default is false | N/A | Default `false` |
| `min_quantity` | Integer | N | Threshold number. It can be edited after the product is approved | `product.info.min_stock_alert` | Default `0` when empty `[CONFIRM: Q-33]` |
| `warehouse_condition` | Integer | N | 1. Normal, 2. Aircond | `product.storage_type` | Ambient → `1`; Air-conditioning → `2`; Chilled / Freezer → **no Boxme value: block product sync and show `WMS error: Boxme does not support chilled / frozen storage`** (R-09) |
| `pack_with_bubble` | Boolean | N | Packaging require bubble wrap | N/A | Default `false` `[CONFIRM: Q-33]` |
| `pack_material` | Integer | N |  | N/A | Default `[TBD: Q-33]` (Product API overview: 1 bag, 2 carton, 3 bubble wrap, 4 none, 5 branded carton, 6 branded bag, 7 other, 8 plastic wrap) |
| `weight` | Integer | N | Item weight. | `product.package_weight` `[CONFIRM: C5]` | Grams, integer. PowerSell grams sent as-is |
| `volume` | String | N | Item volume. | `product.package_length` × `product.package_width` × `product.package_height` | Text `"{L}x{W}x{H}"`. PowerSell cm; Boxme unit `[TBD: Q-21]` (if mm, multiply by 10) |
| `manage_by_serial_number` | Boolean | N | Product require aftersale service by serial number. | `product.serial_imei_management` | `1` → `true`, else `false` |
| `managed_by_gs1` | Boolean | N | Product use GS1 to manage product information. It is global standard | N/A | Default `false` |
| `require_expire` | Boolean | N | Product require manage exp. | `product.expiration_time` | `true` when `expiration_time` is not NULL, else `false` |
| `outbound_strategy` | String | N | FIFO, FEFO, LIFO | `product.valuation_method` | FIFO / FEFO / LIFO sent as-is. FMFO or empty → `FEFO` if require_expire, else `FIFO` `[CONFIRM]` |
| `expiry_threshold` | Integer | N | Expire time threshold month. | `product.info.expiry_threshold` `[CONFIRM: C4]` | Minimum remaining shelf life to ship. Unit: days in Create Product, months in Update / Get `[TBD: Q-08]` |
| `min_inbound_shelf_life` | Integer | N | Min inbound expire time (month) | `product.info.reject_shelf_life` `[CONFIRM: C4]` | Minimum remaining shelf life to accept at inbound. Unit `[TBD: Q-08]` |
| `is_fragile` | Boolean | N | Fragile item | `product.info.is_fragile` `[CONFIRM: C5]` | Default `false` |
| `use_shredded_paper` | Boolean | N |  | N/A | Default `false` |
| `batch_control` | Boolean | N | Batch LOT control | N/A | Default `false` `[CONFIRM: Q-33]` (consider `true` when require_expire) |
| `uom` | String | N | PAC, PC, SET, PAIR, | N/A | Default `PC` |
| `protective_packaging_inbound` | Boolean | N | Require prepack before inbound | N/A | Default `false` |
| `allow_breakdown` | Boolean | N | Allow automate breakdown | N/A | Default `false` |
| `shelf_life` | Integer | N | Shelf life. Exp:12,18,36 months | `product.expiration_time` | Months. `0` when NULL |
| `images` | Array[String] | N |  | `product_media.url` | All images, oldest first |
| `brand` | String | N | Product's brand. It can be edited after the product is approved. | `product.brand` | Optional |
| `wholesale_price` | Integer | N | Wholesale price. It can be edited after the product is approved | N/A | Default `0` `[CONFIRM: Q-33]` |
| `sale_price` | Integer | N | Retail price. It can be edited after the product is approved | `product.retail_price` |  |

#### Response

```json
{
  "data": {
    "bsin": "BSN33152982758216",
    "name": "Sản Phẩm 01",
    "seller_sku": "SP00012001",
    "barcode_manufacturer": "WH23454808",
    "category_id": 3,
    "brand": "Test Brand",
    "description": "Enter when there is a QC request for the product before warehouse entry.",
    "sale_price": 1200000,
    "price": 1000000,
    "wholesale_price": 0,
    "is_digital": false,
    "min_quantity": 1,
    "warehouse_condition": 1,
    "pack_with_bubble": false,
    "pack_material": 2,
    "weight": 3000,
    "volume": "27x36x11",
    "images": [],
    "manage_by_serial_number": false,
    "managed_by_gs1": false,
    "require_expire": true,
    "outbound_strategy": "FEFO",
    "shelf_life": 12,
    "expiry_threshold": 3,
    "min_inbound_shelf_life": 6,
    "is_fragile": true,
    "use_shredded_paper": true,
    "batch_control": false,
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.bsin` | String | **Y** | Boxme's Product ID. | `wms_product.partner_id` | Echo |
| `data.name` | String | **Y** | Product Name | N/A |  |
| `data.seller_sku` | String | **Y** | Seller SKU | N/A |  |
| `data.barcode_manufacturer` | String | **Y** |  | N/A |  |
| `data.category_id` | Integer | **Y** | Refer to Product Category | N/A |  |
| `data.brand` | String | **Y** | Brand name | N/A |  |
| `data.description` | String | **Y** | Product description | N/A |  |
| `data.price` | Integer | **Y** |  | N/A |  |
| `data.is_digital` | Boolean | **Y** |  | N/A |  |
| `data.min_quantity` | Integer | **Y** |  | N/A |  |
| `data.warehouse_condition` | Integer | **Y** |  | N/A |  |
| `data.pack_with_bubble` | Boolean | **Y** |  | N/A |  |
| `data.pack_material` | Integer | **Y** |  | N/A |  |
| `data.weight` | Integer | **Y** |  | N/A |  |
| `data.volume` | String | **Y** |  | N/A |  |
| `data.images` | Array[String] | **Y** |  | N/A |  |
| `data.manage_by_serial_number` | Boolean | **Y** |  | N/A |  |
| `data.managed_by_gs1` | Boolean | **Y** |  | N/A |  |
| `data.require_expire` | Boolean | **Y** |  | N/A |  |
| `data.outbound_strategy` | String | **Y** |  | N/A |  |
| `data.shelf_life` | Integer | **Y** |  | N/A |  |
| `data.expiry_threshold` | Integer | **Y** |  | N/A |  |
| `data.min_inbound_shelf_life` | Integer | **Y** |  | N/A |  |
| `data.is_fragile` | Boolean | **Y** |  | N/A |  |
| `data.use_shredded_paper` | Boolean | **Y** |  | N/A |  |
| `data.batch_control` | Boolean | **Y** |  | N/A |  |
| `data.uom` | String | **Y** | Refer to product UOM | N/A |  |
| `data.protective_packaging_inbound` | Boolean | **Y** |  | N/A |  |
| `data.allow_breakdown` | Boolean | **Y** |  | N/A |  |
| `data.active` | Boolean | **Y** |  | N/A |  |
| `data.approve` | Boolean | **Y** |  | N/A |  |
| `data.sale_price` | Integer | **Y** |  | N/A |  |
| `data.wholesale_price` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.5 Get products

#### Purpose

Verify / back-fill Boxme product IDs (UC-03).

**When PowerSell calls it:** On demand. Rate limit 1 / sec and 30 / min / IP.

#### Endpoint

```
GET https://s.boxme.asia/api/v2.1/sellers/products/list
```
Boxme reference: https://developers.boxme.asia/api-5002023

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2.1/sellers/products/list' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `page` | query | N |  | N/A |  |
| `page_size` | query | N |  | N/A |  |
| `is_active` | query | N |  | N/A |  |
| `keyword` | query | N |  | `product.inventory_sku` |  |
| `is_approved` | query | N |  | N/A |  |
| `approved_time_from` | query | N |  | N/A |  |
| `approved_time_to` | query | N |  | N/A |  |

#### Response

*No sample response in Boxme doc.*

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.next` | Null | **Y** |  | N/A |  |
| `data.previous` | Null | **Y** |  | N/A |  |
| `data.results` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.results[].bsin` | String | N | Boxme Serial Indentify Number | `wms_product.partner_id` | Verification / back-fill only |
| `data.results[].name` | String | N | Product name | N/A |  |
| `data.results[].seller_sku` | String | N | Seller SKU | `product.inventory_sku` | Match key |
| `data.results[].barcode_manufacturer` | String | N | Manufacture barcode | N/A |  |
| `data.results[].category_id` | Integer | N | Category ID, refer to GetCategory API | N/A |  |
| `data.results[].description` | String | N | Product Description | N/A |  |
| `data.results[].price` | Integer | N | Listed price | N/A |  |
| `data.results[].is_digital` | Boolean | N | Physical/Digital product | N/A |  |
| `data.results[].min_quantity` | Integer | N | Low stock threshold quantity | N/A |  |
| `data.results[].warehouse_condition` | Integer | N | 1. Normal, 2. Aircond | N/A |  |
| `data.results[].pack_with_bubble` | Boolean | N | Bubble wrap require | N/A |  |
| `data.results[].pack_material` | Integer | N | Refer to Material Define | N/A |  |
| `data.results[].weight` | Integer | N | Item weight | N/A |  |
| `data.results[].volume` | String | N | Item volume | N/A |  |
| `data.results[].images` | Array[String] | N | Product photo | N/A |  |
| `data.results[].manage_by_serial_number` | Boolean | N | Require manage by serial number | N/A |  |
| `data.results[].managed_by_gs1` | Boolean | N | Require manage by GS1 Code | N/A |  |
| `data.results[].require_expire` | Boolean | N | Require manage by expiry date | N/A |  |
| `data.results[].outbound_strategy` | String | N | FIFO, FEFO, LIFO | N/A |  |
| `data.results[].shelf_life` | Integer | N | Month | N/A |  |
| `data.results[].expiry_threshold` | Integer | N | Expiry month threshold | N/A |  |
| `data.results[].min_inbound_shelf_life` | Integer | N | Min inbound threshold month | N/A |  |
| `data.results[].is_fragile` | Boolean | N | Fragile product | N/A |  |
| `data.results[].use_shredded_paper` | Boolean | N | Request use Shredded paper | N/A |  |
| `data.results[].batch_control` | Boolean | N | Batch Lot control | N/A |  |
| `data.results[].uom` | String | N | PC, BOX, PAIR, PACK, SET. Refer to get Product Unit API | N/A |  |
| `data.results[].protective_packaging_inbound` | Boolean | N | Request special protect when inbound | N/A |  |
| `data.results[].allow_breakdown` | Boolean | N | Allow Item auto breakdown | N/A |  |
| `data.results[].active` | Boolean | N | Selling status | N/A |  |
| `data.results[].approve` | Boolean | N | Approval inbound status | N/A |  |
| `data.results[].sale_price` | Integer | N | Sale Price | N/A |  |
| `data.results[].wholesale_price` | Integer | N | B2B price | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.6 Get stock available

#### Purpose

Pull stock per warehouse (UC-04 reconciliation).

**When PowerSell calls it:** Daily reconciliation and on demand; day-to-day updates come from webhook 6.2. Max 20 SKUs per call.

#### Endpoint

```
POST https://s.boxme.asia/api/v2.1/sellers/products/get_stock/
```
Boxme reference: https://developers.boxme.asia/api-5166027

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2.1/sellers/products/get_stock/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"seller_skus": ["TEST-0002"]}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `seller_skus` | Array[String] | **Y** |  | `product.inventory_sku` | Max **20** SKUs per call; 1 request / sec / IP. Batch for reconciliation |

#### Response

```json
{
  "data": {
    "inventory": [
      {
        "bsin": "BSN33152905437334",
        "seller_sku": "KIEN_TEST_1",
        "total_stock_quantity": 100,
        "total_awaiting_quantity": 0,
        "total_reserved_quantity": 0,
        "total_available_quantity": 100,
        "total_incoming_quantity": 0,
        "total_damaged_stock_quantity": 0,
        "total_damaged_awaiting_quantity": 0,
        "total_damaged_available_quantity": 0,
        "warehouse_inventory": [
          {
            "pickup_id": 345185,
            "stock_quantity": 100,
            "awaiting_quantity": 0,
            "reserved_quantity": 0,
            "available_quantity": 100,
            "incoming_quantity": 0,
            "damaged_stock_quantity": 0,
            "damaged_awaiting_quantity": 0,
            "damaged_available_quantity": 0,
            "damaged_details": [
              {
                "condition_level": "D3",
                "stock_quantity": 20,
                "awaiting_quantity": 0,
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.inventory` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.inventory[].bsin` | String | N |  | N/A |  |
| `data.inventory[].seller_sku` | String | N |  | `product.inventory_sku` | Match key |
| `data.inventory[].total_stock_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_awaiting_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_reserved_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_available_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_incoming_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_damaged_stock_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_damaged_awaiting_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].total_damaged_available_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory` | Array[Object] | N |  | N/A | Parent object: see child rows |
| `data.inventory[].warehouse_inventory[].pickup_id` | Integer | N |  | `wms_warehouse.partner_warehouse_id` | Stock is per warehouse |
| `data.inventory[].warehouse_inventory[].stock_quantity` | Integer | N |  | `wms_product.stock_quantity` | Physical on-hand |
| `data.inventory[].warehouse_inventory[].awaiting_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory[].reserved_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory[].available_quantity` | Integer | N |  | `wms_product.available_quantity` → `product_stock.open_stock` | Sellable stock (condition A) = stock − reserved − awaiting |
| `data.inventory[].warehouse_inventory[].incoming_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_stock_quantity` | Integer | N |  | N/A | PowerSell does not store damaged stock |
| `data.inventory[].warehouse_inventory[].damaged_awaiting_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_available_quantity` | Integer | N |  | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_details` | Array[Object] | N |  | N/A | Parent object: see child rows |
| `data.inventory[].warehouse_inventory[].damaged_details[].condition_level` | String | **Y** | D1, D2, D3 | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_details[].stock_quantity` | Integer | **Y** |  | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_details[].awaiting_quantity` | Integer | **Y** |  | N/A |  |
| `data.inventory[].warehouse_inventory[].damaged_details[].available_quantity` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 2.7 Get stock report (V3)

#### Purpose

Stock by batch and expiry date.

**When PowerSell calls it:** Optional: reconciliation of near-expiry stock. Not required for Phase 1 sync.

#### Endpoint

```
POST https://s.boxme.asia/api/v3/public/inventory/report-stocks/
```
Boxme reference: https://developers.boxme.asia/api-44502283

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v3/public/inventory/report-stocks/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"seller_skus": ["345000330341", "SKU14", "223000340232"], "warehouse_code": "BMPH_PDC_TEST", "condition_goods": "A", "page": 1, "page_size": 10}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `seller_skus` | Array[String] | N |  | `product.inventory_sku` |  |
| `warehouse_code` | String | N |  | N/A | Not sent |
| `condition_goods` | String | N |  | N/A | Not sent |
| `page` | Integer | **Y** |  | N/A | Start at `1` |
| `page_size` | Integer | **Y** |  | N/A | Default `100` |

#### Response

```json
{
  "data": {
    "count": 3,
    "results": [
      {
        "warehouse_id": 17,
        "product_id": 553521,
        "bsin": "BSN33152965517712",
        "condition_goods": "A",
        "batch_lot": null,
        "stock_date": "2022-09-16",
        "expire_date": "2022-12-30",
        "quantity": 10,
        "product_name": "Bánh Bibica hộp 20 chiếc",
        "seller_sku": "345000330341",
        "warehouse_code": "BMPH_PDC_TEST",
        "warehouse_name": "Testing Warehouse"
      },
      {
        "warehouse_id": 17,
        "product_id": 553521,
        "bsin": "BSN33152965517712",
        "condition_goods": "A",
        "batch_lot": null,
        "stock_date": "2022-09-16",
        "expire_date": null,
        "quantity": 990,
        "product_name": "Bánh Bibica hộp 20 chiếc",
        "seller_sku": "345000330341",
        "warehouse_code": "BMPH_PDC_TEST",
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.count` | Integer | **Y** |  | N/A |  |
| `data.results` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.results[].warehouse_id` | Integer | **Y** |  | N/A |  |
| `data.results[].product_id` | Integer | **Y** |  | N/A |  |
| `data.results[].bsin` | String | **Y** |  | N/A |  |
| `data.results[].condition_goods` | String | **Y** |  | N/A |  |
| `data.results[].batch_lot` | Null | **Y** |  | N/A |  |
| `data.results[].stock_date` | String | **Y** |  | N/A |  |
| `data.results[].expire_date` | String | **Y** |  | N/A | Reference for near-expiry checks; not stored in Phase 1 |
| `data.results[].quantity` | Integer | **Y** |  | N/A |  |
| `data.results[].product_name` | String | **Y** |  | N/A |  |
| `data.results[].seller_sku` | String | **Y** |  | N/A |  |
| `data.results[].warehouse_code` | String | **Y** |  | N/A |  |
| `data.results[].warehouse_name` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `message` | String | **Y** |  | N/A |  |
| `detail` | Object | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

---

# 🔖 3. Inbound (ASN)

## 3.1 Create inbound shipment (ASN)

#### Purpose

Send an ASN to Boxme (UC-05, UC-06).

**When PowerSell calls it:** When the user confirms an ASN to a Boxme warehouse.

#### Endpoint

```
POST https://s.boxme.asia/api/v2/sellers/shipments/
```
Boxme reference: https://developers.boxme.asia/api-5002029

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/sellers/shipments/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"pickup_id": 7347389, "po_number": "PO000001", "package_option": "single", "shipment_type": "inbound", "vas": {"inspection": true, "priority_inbound": false, "unloading": false, "reject_damaged_goods": true}, "products": [{"seller_sku": "DLGLASS0001", "quantity_per_box": 12, "quantity": 1200, "line_no": "10000", "auto_merge": false}, {"seller_sku": "TEST-0002", "quantity_per_box": 6, "quantity": 60, "line_no": "10000", "auto_merge": false}], "inspection_note": "", "note": "Ghi chú", "estimate_arrived_time": "21/12/2023", "documents": ["https://storage.googleapis.com/boxme/warehouse/2023/12/hfEzUM_202312.jpg"]}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `po_number` | String | **Y** | Purchase Order Number | `wms_purchase_order.code` / `wms_asn.code` | PO code when the ASN has a PO, else ASN code. Unique: duplicates rejected (`po_number_duplicated`) |
| `package_option` | String | N | single: Single SKU/Box, multi: Mix SKU/Box | N/A | Default `multi` (PowerSell does not hold quantity per carton) |
| `vas` | Object | **Y** |  | N/A | Parent object: see child rows |
| `vas.inspection` | Boolean | **Y** | Require Inspection service when shipment received | `wms_asn.vas_info` | Default `false` `[TBD]` field inside vas_info |
| `vas.priority_inbound` | Boolean | **Y** | Inbound within 2h | `wms_asn.is_priority` | `true` / `false` |
| `vas.unloading` | Boolean | **Y** | Require unloading service for high truck | `wms_asn.vas_info` | Default `false` `[TBD]` |
| `vas.reject_damaged_goods` | Boolean | **Y** | Reject damage item when shipment receive & inspection with driver | `wms_asn.vas_info` | Default `false` `[TBD]` |
| `products` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `products[].seller_sku` | String | **Y** | Seller SKU | `product.inventory_sku` |  |
| `products[].quantity_per_box` | Integer | N | Quantity Per Carton Box. Require when package_option is single | N/A | Not sent (package_option `multi`) |
| `products[].quantity` | Integer | **Y** | Total quantity | `wms_asn_detail.quantity` | Expected quantity |
| `products[].line_no` | String | N | Line number of ERP | `wms_asn_detail.id` | Line reference; echoed in receiving note `[CONFIRM]` |
| `products[].auto_merge` | Boolean | N | Auto convert pcs to box. Apply for special client. | N/A | Default `false` |
| `products[].quantity_of_box` | Integer | N | Total box quantity. Require when package_option is single | N/A | Not sent |
| `inspection_note` | String | N | Inspection Note for inspector | N/A | Empty |
| `note` | String | **Y** | Note for receiver | `wms_asn.special_instruction` | Mandatory: send `""` when empty |
| `estimate_arrived_time` | Integer | **Y** | Estimate arrival Time (Timestamp) | `wms_asn.delivery_date` | Unix timestamp (seconds), converted from local time. Doc example shows text "21/12/2023" (D-08) |
| `documents` | Array[String] | N | Document support for ASN | N/A | Not sent |
| `pickup_id` | String | **Y** | Boxme's warehouse ID (to receive goods) | `wms_warehouse.partner_warehouse_id` | From `wms_asn.wms_warehouse_id` |
| `pickup_service` | Boolean | N | Boxme will arrange pickup service, When | N/A | Default `false` |
| `pickup_from` | Object | N | It's mandatory if you want Boxme to arrange for pickup | N/A | Not sent |
| `pickup_from.customer_code` | String | N | Customer Code, refer to customer list | N/A | Not sent |
| `pickup_from.default_address` | Boolean | N | Default delivery address of customer | N/A | Not sent |
| `shipment_type` | String | **Y** | Values: inbound, internal_transfer, sales_return, restock | N/A | Default `inbound` |

#### Response

```json
{
  "data": {
    "shipment_code": "SM-VN-331529-16537311",
    "po_number": "ASN02324221",
    "created_time": 1714637312
  },
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "663349ff0bfeb065f4150d12"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.shipment_code` | String | **Y** |  | `wms_asn.partner_asn_id` | Boxme ASN code (e.g. `SM-VN-…`). Key for cancel, detail, receiving note |
| `data.po_number` | String | **Y** |  | N/A | Echo |
| `data.created_time` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 3.2 Get ASN available timeslot

#### Purpose

List delivery timeslots when the warehouse requires booking (ASN status `12` Awaiting Reservation).

**When PowerSell calls it:** Optional in Phase 1: booking can be done in the Boxme portal. Automating it in PowerSell is `[TBD]`.

#### Endpoint

```
POST https://s.boxme.asia/api/v2/sellers/shipments/booking/get-time-slots/
```
Boxme reference: https://developers.boxme.asia/api-6615091

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/sellers/shipments/booking/get-time-slots/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"shipment_codes": ["SM-VN-331529-26869855"], "estimate_arrival_time": 1713556203}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `shipment_codes` | Array[String] | **Y** | List of ASN to bookings | `wms_asn.partner_asn_id` |  |
| `estimate_arrival_time` | Integer | **Y** | Estimated datetime (Unix Timestamp) of arrival at the warehouse. | `wms_asn.delivery_date` | Unix timestamp |

#### Response

```json
{
  "data": [
    {
      "label": "00:00 - 00:30",
      "time_slot_id": 1713459600,
      "out_of_working_time": true
    },
    {
      "label": "00:30 - 01:00",
      "time_slot_id": 1713461400,
      "out_of_working_time": true
    },
    {
      "label": "01:00 - 01:30",
      "time_slot_id": 1713463200,
      "out_of_working_time": true
    },
    {
      "label": "01:30 - 02:00",
      "time_slot_id": 1713465000,
      "out_of_working_time": true
    }
  ],
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "661ceab8a922c2c1f916212b"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data[].label` | String | **Y** |  | N/A | Show to user to choose a slot `[TBD]` |
| `data[].out_of_working_time` | Boolean | **Y** |  | N/A |  |
| `data[].time_slot_id` | Integer | **Y** |  | N/A | Pass to Create ASN Booking |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 3.3 Create ASN booking

#### Purpose

Book a timeslot for one or more ASNs.

**When PowerSell calls it:** Same as 3.2.

#### Endpoint

```
POST https://s.boxme.asia/api/v2/sellers/shipments/booking/create/
```
Boxme reference: https://developers.boxme.asia/api-6615089

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/sellers/shipments/booking/create/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"shipment_codes": ["SM-VN-331529-26869855"], "time_slot_id": 1713582000}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `shipment_codes` | Array[String] | **Y** | List of ASN to bookings | `wms_asn.partner_asn_id` |  |
| `time_slot_id` | Integer | **Y** | Call: Get ASN Available to get slot | N/A | From 3.2 |

#### Response

```json
{
  "data": [
    {
      "shipment_code": "SM-VN-331529-26869855",
      "status": 2,
      "status_name": "Ready to ship",
      "booking_id": 20561,
      "booking_status": "Delivering",
      "time_slot_id": 1713465000,
      "out_of_working_time": true
    }
  ],
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "661ceaffa922c2c1f916212c"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data[].shipment_code` | String | N |  | N/A |  |
| `data[].status` | Integer | N |  | `wms_asn.status` | See 3.7 |
| `data[].status_name` | String | N |  | N/A |  |
| `data[].booking_id` | Integer | N |  | [TBD] | Needed only to cancel a booking |
| `data[].booking_status` | String | N |  | N/A |  |
| `data[].time_slot_id` | Integer | N |  | N/A |  |
| `data[].out_of_working_time` | Boolean | N |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 3.4 Cancel ASN

#### Purpose

Cancel an ASN (UC-07).

**When PowerSell calls it:** When the user cancels the ASN in PowerSell. On success set ASN status Closed; on error show `WMS error: <messages>` (`wms_asn.last_error`). Cancel window `[TBD: Q-07]`.

#### Endpoint

```
POST https://s.boxme.asia/api/v2/sellers/shipments/cancel/{shipment_code}/
```
Boxme reference: https://developers.boxme.asia/api-5002035

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/sellers/shipments/cancel/{shipment_code}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `shipment_code` | path | **Y** |  | `wms_asn.partner_asn_id` |  |

#### Response

```json
{
  "data": {},
  "error": false,
  "error_code": "",
  "messages": "Shipment SM-VN-331529-20732681 has been cancelled",
  "request_id": 1703237531
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 3.5 Get shipment detail

#### Purpose

Read ASN status (fallback to webhook 6.1).

**When PowerSell calls it:** Polling fallback only.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/sellers/shipments/{shipment_code}/
```
Boxme reference: https://developers.boxme.asia/api-5002036

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/sellers/shipments/{shipment_code}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `shipment_code` | path | **Y** |  | `wms_asn.partner_asn_id` |  |

#### Response

```json
{
  "data": {
    "id": 223407,
    "country": "VN",
    "pickup_id": 409223,
    "shipment_code": "SM-VN-331529-20732681",
    "po_number": "DLGLASS0001",
    "package_option": "single",
    "shipment_type": "inbound",
    "vas": {
      "inspection": true,
      "priority_inbound": false,
      "unloading": false,
      "reject_damaged_goods": true
    },
    "products": [
      {
        "bsin": "BSN33152982758216",
        "seller_sku": "TEST-0002",
        "name": "TEST-0002",
        "weight": 350,
        "volume": "18x15x11",
        "quantity_per_box": 100,
        "quantity_of_box": 10,
        "quantity": 1000,
        "line_no": "10000",
        "auto_merge": false
      },
      {
        "bsin": "BSN33152992878894",
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.id` | Integer | **Y** |  | N/A |  |
| `data.country` | String | **Y** |  | N/A |  |
| `data.pickup_id` | Integer | **Y** | Pickup ID | N/A |  |
| `data.shipment_code` | String | **Y** |  | `wms_asn.partner_asn_id` | Match key |
| `data.po_number` | String | **Y** | PO/TO number | N/A |  |
| `data.package_option` | String | **Y** |  | N/A |  |
| `data.vas` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.vas.inspection` | Boolean | **Y** |  | N/A |  |
| `data.vas.priority_inbound` | Boolean | **Y** |  | N/A |  |
| `data.vas.unloading` | Boolean | **Y** |  | N/A |  |
| `data.vas.reject_damaged_goods` | Boolean | **Y** |  | N/A |  |
| `data.products` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.products[].bsin` | String | **Y** |  | N/A |  |
| `data.products[].seller_sku` | String | **Y** |  | N/A |  |
| `data.products[].name` | String | **Y** |  | N/A |  |
| `data.products[].weight` | Integer | **Y** |  | N/A |  |
| `data.products[].volume` | String | **Y** |  | N/A |  |
| `data.products[].quantity_per_box` | Integer | **Y** |  | N/A |  |
| `data.products[].quantity_of_box` | Integer | **Y** |  | N/A |  |
| `data.products[].quantity` | Integer | **Y** |  | N/A | Expected quantity (echo). **No received quantity here** despite the doc description (D-02): use 3.6 |
| `data.products[].line_no` | String | **Y** |  | N/A |  |
| `data.products[].auto_merge` | Boolean | **Y** |  | N/A |  |
| `data.documents` | Array[String] | **Y** |  | N/A |  |
| `data.note` | String | **Y** |  | N/A |  |
| `data.inspection_note` | String | **Y** |  | N/A |  |
| `data.status` | Integer | **Y** |  | `wms_asn.status` | See 3.7 status mapping |
| `data.status_display` | String | **Y** |  | N/A |  |
| `data.estimate_arrived_time` | Integer | **Y** |  | N/A |  |
| `data.received_time` | Integer | **Y** |  | N/A | Arrival at warehouse (not completion) |
| `data.completed_time` | Integer | **Y** |  | `wms_asn.received_date` | Unix → local time. Only when status `6` Completed |
| `data.created_by` | Integer | **Y** |  | N/A |  |
| `data.created_time` | Integer | **Y** |  | N/A |  |
| `data.updated_by` | Integer | **Y** |  | N/A |  |
| `data.updated_time` | Integer | **Y** |  | N/A |  |
| `data.shipment_type` | String | **Y** | Values: inbound, internal_transfer, sales_return | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 3.6 Get receiving note (GRN)

#### Purpose

Received quantities per SKU and condition (UC-08).

**When PowerSell calls it:** When webhook 6.1 reports `11` Partial inspection or `6` Completed. Paged (default 100).

#### Endpoint

```
GET https://s.boxme.asia/api/v2/sellers/shipments/receiving/{shipment_code}/
```
Boxme reference: https://developers.boxme.asia/api-5286407

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/sellers/shipments/receiving/{shipment_code}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `shipment_code` | path | **Y** |  | `wms_asn.partner_asn_id` |  |
| `keyword` | query | N | Filter with: bsin, seller_sku | N/A |  |
| `condition_level` | query | N | A, D1, D2, D3, L, DE | N/A | Leave empty (all conditions) |
| `batch_lot` | query | N |  | N/A |  |
| `expiry_date` | query | N | Unix timestamp EXP date | N/A |  |
| `page` | query | N | Default is 1 | N/A |  |
| `page_size` | query | N | Default is 100 | N/A |  |

#### Response

```json
{
  "data": {
    "total_count": 3,
    "inspections": [
      {
        "seller_sku": "SUATHTRUEMILK",
        "bsin": "BSN33152937466714",
        "product_name": "Sữa tươi TH true milk (hộp)",
        "quantity": 180,
        "condition_level": "A",
        "batch_lot": "331529-26083198",
        "expiry_date": 1709226000,
        "note": "Test check",
        "line_no": "101001",
        "created_time": 1707982450
      },
      {
        "seller_sku": "SUATHTRUEMILK",
        "bsin": "BSN33152937466714",
        "product_name": "Sữa tươi TH true milk (hộp)",
        "quantity": 300,
        "condition_level": "A",
        "batch_lot": "331529-26083198",
        "expiry_date": 1709226000,
        "note": "Test check",
        "line_no": "201001",
        "created_time": 1707981365
      },
      {
        "seller_sku": "SUATHTRUEMILK",
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.inspections` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.inspections[].seller_sku` | String | **Y** |  | `product.inventory_sku` | Match key |
| `data.inspections[].bsin` | String | **Y** |  | N/A |  |
| `data.inspections[].product_name` | String | **Y** |  | N/A |  |
| `data.inspections[].quantity` | Integer | **Y** |  | `wms_asn_detail.quantity_received` `[CONFIRM: C11]` | Sum of rows with `condition_level` = `A` per SKU `[TBD: Q-25]` (per-receipt or total rows) |
| `data.inspections[].condition_level` | String | **Y** |  | N/A | `A` = good; `D1`–`D3` = damaged (not stored); `L`, `DE` `[TBD: Q-28]` |
| `data.inspections[].batch_lot` | String | **Y** |  | N/A |  |
| `data.inspections[].expiry_date` | Integer | **Y** |  | N/A |  |
| `data.inspections[].note` | String | **Y** |  | N/A |  |
| `data.inspections[].line_no` | String | **Y** |  | `wms_asn_detail.id` | Line match when the same SKU appears twice |
| `data.inspections[].created_time` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

### 3.7 ASN status mapping

| **Boxme status** | **PowerSell status** | **Note** |
|---|---|---|
| `1` New | Pending Receipt | Or "New" `[CONFIRM: S4]` |
| `12` Awaiting Reservation | Pending Receipt | Booking needed (3.2 / 3.3) |
| `2` Ready-to-ship | Pending Receipt | |
| `4` In-transit | Pending Receipt | |
| `10` Received | Pending Receipt | Arrived, not yet put away |
| `11` Partial inspection | Pending Receipt | Pull 3.6 and stock (2.6) for the ASN's SKUs |
| `6` Completed | Completed **only if** received = expected; else Pending Receipt | `[TBD: Q-24]` short receipts |
| `5` Cancelled | Closed | |
| `7` Cancelled by operator | Closed | |

---

# 🔖 4. Outbound

## 4.1 Get shipping option (Boxme delivery)

#### Purpose

Get Boxme delivery services and fees for an order (UC-14).

**When PowerSell calls it:** Boxme-delivered orders only, right before 4.2. Rate limit 2 / sec / IP. Item field is `sku` here, `seller_sku` in 4.2 (D-10).

#### Endpoint

```
POST https://s.boxme.asia/api/v2/courier/pricing/calculate
```
Boxme reference: https://developers.boxme.asia/api-4893907

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/courier/pricing/calculate' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"ship_from": {"country": "VN", "pickup_id": 409223}, "ship_to": {"address": "18 Tam Trinh", "subdistrict": 8980, "contact_name": "Thịnh NV", "country": "VN", "district": 250, "phone": "84032999292", "province": 1, "zipcode": ""}, "shipments": {"delivery_note": "", "parcels": [{"items": [{"quantity": 1, "sku": "TEST-0004"}, {"quantity": 1, "sku": "TEST-0005"}]}]}, "config": {"insurance": "N", "currency": "VND", "unit_metric": "metric", "sort_mode": "best_price", "auto_approve": "Y", "order_type": "b2c", "include_distance_service": "Y"}, "payment": {"cod_amount": 24000}, "referral": {"order_number": "SO092921232"}, "fulfillment_vas": {"fulfill_now": "N", "priority_fulfill": "N"}}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `ship_from` | Object | **Y** |  | N/A | Parent object: see child rows |
| `ship_from.country` | String | **Y** |  | [TBD] | Country of the Boxme warehouse (VN / TH / PH) |
| `ship_from.pickup_id` | Integer | **Y** |  | `wms_warehouse.partner_warehouse_id` | From `wms_sale_order.wms_warehouse_id` |
| `ship_to` | Object | **Y** |  | N/A | Parent object: see child rows |
| `ship_to.address` | String | **Y** |  | `order_customer.address` `[CONFIRM: C9]` | Masked addresses: `[TBD: Q-31]` |
| `ship_to.subdistrict` | Integer | **Y** |  | [TBD] | Boxme sub-district ID from location mapping (1.2–1.5) `[TBD: Q-32]` |
| `ship_to.contact_name` | String | **Y** |  | `order_customer.name` `[CONFIRM: C9]` |  |
| `ship_to.country` | String | **Y** |  | `order_customer.country` `[CONFIRM: C9]` | ISO-2 |
| `ship_to.district` | Integer | **Y** |  | [TBD] | Boxme district ID `[TBD: Q-32]` |
| `ship_to.phone` | String | **Y** |  | `order_customer.phone` `[CONFIRM: C9]` | Masked phone: `[TBD: Q-31]` |
| `ship_to.province` | Integer | **Y** |  | [TBD] | Boxme province ID `[TBD: Q-32]` |
| `ship_to.zipcode` | String | **Y** |  | `order_customer.postal_code` `[CONFIRM: C9]` |  |
| `shipments` | Object | **Y** |  | N/A | Parent object: see child rows |
| `shipments.delivery_note` | String | **Y** |  | N/A | Mandatory: send `""` |
| `shipments.parcels` | Array[Object] | **Y** |  | N/A | One parcel per order |
| `shipments.parcels[].items` | Array[Object] | N |  | N/A | Only lines fulfilled by Boxme; never dropship lines. Bundles split into component SKUs |
| `shipments.parcels[].items[].quantity` | Integer | **Y** |  | `order_item.quantity` | Component quantity after bundle split |
| `shipments.parcels[].items[].sku` | String | **Y** |  | `product.inventory_sku` | Named `sku` here but `seller_sku` in Create Order (D-10) |
| `config` | Object | **Y** |  | N/A | Parent object: see child rows |
| `config.insurance` | String | **Y** |  | N/A | Default `false` |
| `config.currency` | String | **Y** |  | `platform.currency` |  |
| `config.unit_metric` | String | **Y** |  | N/A | Default `metric` |
| `config.sort_mode` | String | **Y** |  | N/A | Default `best_price` |
| `config.auto_approve` | String | **Y** |  | N/A | Marketplace delivery: `false` (per Boxme doc). Boxme delivery: `true` `[CONFIRM]` |
| `config.order_type` | String | **Y** |  | N/A | Default `b2c` |
| `config.include_distance_service` | String | **Y** |  | N/A | Default `false` |
| `payment` | Object | **Y** |  | N/A | Parent object: see child rows |
| `payment.cod_amount` | Integer | **Y** |  | `order_item.info.cod_line_total` + `order.shipping_fee` | Marketplace delivery: `0`. Boxme delivery with `payment_method.master_name` = `cod`: sum of line COD + shipping fee; else `0`. TH: integer (round up) |
| `referral` | Object | **Y** |  | N/A | Parent object: see child rows |
| `referral.order_number` | String | **Y** |  | `order.order_number` `[CONFIRM: C2]` | Duplicate check field `[TBD: Q-22]` |
| `fulfillment_vas` | Object | **Y** |  | N/A | Parent object: see child rows |
| `fulfillment_vas.fulfill_now` | String | **Y** |  | N/A | `true` for instant-delivery orders (TikTok `fulfillment_priority_level` / Shopee instant carrier). Boxme packs within 45 min |
| `fulfillment_vas.priority_fulfill` | String | **Y** |  | N/A | `true` for same-day orders. Boxme packs within 2 h |

#### Response

```json
{
  "data": {
    "couriers": [
      {
        "total_fee": 0,
        "cod_value": 24000,
        "shipping_fee": 0,
        "vas_fee": 0,
        "fulfillment_fee": 0,
        "tax": 0,
        "duty": 0,
        "is_distance_service": false,
        "is_negotiable": false,
        "sorting_hub": "BMPH_PDC_TEST_2",
        "chargeable_weight": 22,
        "min_delivery_time": 1,
        "max_delivery_time": 0,
        "currency": "VND",
        "handover_options": "dropoff, pickup",
        "handover_policy": "Free pickup",
        "courier_name": "Boxme Express",
        "courier_id": 52,
        "courier_logo": "https://app.omisell.com/assets/customize/images/courier/Boxme_EXPRESS.svg",
        "service_id": 57,
        "service_code": "BM_DBS",
        "service_name": "Self-Delivery",
        "insurance_policy": "https://blog.boxme.asia/vi/dieu-khoan-su-dung/",
        "dropoff_point": "https://boxme.asia/en/dropoff/"
      }
    ]
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.couriers` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.couriers[].total_fee` | Integer | N |  | N/A | Not stored in Phase 1 |
| `data.couriers[].cod_value` | Integer | N |  | N/A |  |
| `data.couriers[].shipping_fee` | Integer | N |  | N/A |  |
| `data.couriers[].vas_fee` | Integer | N |  | N/A |  |
| `data.couriers[].fulfillment_fee` | Integer | N |  | N/A |  |
| `data.couriers[].tax` | Integer | N |  | N/A |  |
| `data.couriers[].duty` | Integer | N |  | N/A |  |
| `data.couriers[].is_distance_service` | Boolean | N |  | N/A |  |
| `data.couriers[].is_negotiable` | Boolean | N |  | N/A |  |
| `data.couriers[].sorting_hub` | String | N |  | N/A |  |
| `data.couriers[].chargeable_weight` | Integer | N |  | N/A |  |
| `data.couriers[].min_delivery_time` | Integer | N |  | N/A |  |
| `data.couriers[].max_delivery_time` | Integer | N |  | N/A |  |
| `data.couriers[].currency` | String | N |  | N/A |  |
| `data.couriers[].handover_options` | String | N |  | N/A |  |
| `data.couriers[].handover_policy` | String | N |  | N/A |  |
| `data.couriers[].courier_name` | String | N |  | `shipment_provider.name` | Carrier shown in PowerSell |
| `data.couriers[].courier_id` | Integer | N |  | N/A |  |
| `data.couriers[].courier_logo` | String | N |  | N/A |  |
| `data.couriers[].service_id` | Integer | N |  | N/A |  |
| `data.couriers[].service_code` | String | N |  | N/A | Selected value → Create Order `config.delivery_service`. Selection rule `[TBD]` (proposed: cheapest, `sort_mode: best_price`) |
| `data.couriers[].service_name` | String | N |  | N/A |  |
| `data.couriers[].insurance_policy` | String | N |  | N/A |  |
| `data.couriers[].dropoff_point` | String | N |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 4.2 Create B2C order

#### Purpose

Send a customer order to Boxme (UC-09, UC-10, UC-14).

**When PowerSell calls it:** When the order is confirmed on the channel and assigned to a Boxme warehouse. Rate limit **2 / sec / IP** (R-01): queue requests. Duplicates rejected with `DUPLICATED_ORDER` (field `[TBD: Q-22]`).

#### Endpoint

```
POST https://s.boxme.asia/api/v2/courier/pricing/b2c/create_order
```
Boxme reference: https://developers.boxme.asia/api-4893913

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/courier/pricing/b2c/create_order' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"ship_from": {"country": "VN", "pickup_id": 409223}, "ship_to": {"address": "18 Tam Trinh", "subdistrict": 8980, "contact_name": "Thịnh NV", "country": "VN", "district": 250, "phone": "84032999292", "province": 1, "zipcode": ""}, "shipments": {"delivery_note": "", "parcels": [{"items": [{"quantity": 1, "seller_sku": "TEST-0004"}, {"quantity": 1, "seller_sku": "TEST-0005"}]}]}, "config": {"insurance": false, "currency": "VND", "unit_metric": "metric", "sort_mode": "best_price", "auto_approve": true, "order_type": "b2c", "include_distance_service": false}, "payment": {"cod_amount": 24000}, "referral": {"order_number": "SO092921232", "platform": "shopee", "source": "Primer RMS"}, "fulfillment_vas": {"fulfill_now": false, "priority_fulfill": false}}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `ship_from` | Object | **Y** |  | N/A | Parent object: see child rows |
| `ship_from.country` | String | **Y** |  | [TBD] | Country of the Boxme warehouse (VN / TH / PH) |
| `ship_from.pickup_id` | Integer | **Y** |  | `wms_warehouse.partner_warehouse_id` | From `wms_sale_order.wms_warehouse_id` |
| `ship_to` | Object | **Y** |  | N/A | Parent object: see child rows |
| `ship_to.address` | String | **Y** |  | `order_customer.address` `[CONFIRM: C9]` | Masked addresses: `[TBD: Q-31]` |
| `ship_to.subdistrict` | Integer | **Y** | Refer to Location Database | [TBD] | Boxme sub-district ID from location mapping (1.2–1.5) `[TBD: Q-32]` |
| `ship_to.contact_name` | String | **Y** |  | `order_customer.name` `[CONFIRM: C9]` |  |
| `ship_to.country` | String | **Y** |  | `order_customer.country` `[CONFIRM: C9]` | ISO-2 |
| `ship_to.district` | Integer | **Y** | Refer to Location Database | [TBD] | Boxme district ID `[TBD: Q-32]` |
| `ship_to.phone` | String | **Y** |  | `order_customer.phone` `[CONFIRM: C9]` | Masked phone: `[TBD: Q-31]` |
| `ship_to.province` | Integer | **Y** | Refer to Location Database | [TBD] | Boxme province ID `[TBD: Q-32]` |
| `ship_to.zipcode` | String | N |  | `order_customer.postal_code` `[CONFIRM: C9]` |  |
| `ship_to.subdistrict_name` | String | N | Pass the location name if you want us to recognize it automatically. | `order_customer.ward` `[CONFIRM: C9]` | Always send: lets Boxme auto-match when an ID is missing |
| `ship_to.district_name` | String | N | Pass the location name if you want us to recognize it automatically. | `order_customer.district` `[CONFIRM: C9]` | Always send |
| `ship_to.province_name` | String | N | Pass the location name if you want us to recognize it automatically. | `order_customer.city` `[CONFIRM: C9]` | Always send |
| `shipments` | Object | **Y** |  | N/A | Parent object: see child rows |
| `shipments.delivery_note` | String | **Y** |  | N/A | Mandatory: send `""` |
| `shipments.parcels` | Array[Object] | **Y** |  | N/A | One parcel per order |
| `shipments.parcels[].items` | Array[Object] | N |  | N/A | Only lines fulfilled by Boxme; never dropship lines. Bundles split into component SKUs |
| `shipments.parcels[].items[].quantity` | Integer | **Y** |  | `order_item.quantity` | Component quantity after bundle split |
| `shipments.parcels[].items[].seller_sku` | String | **Y** |  | `product.inventory_sku` |  |
| `shipments.parcels[].items[].discounted_price` | Number | **Y** | The final price after seller discounts (include discount, seller voucher) | `order_item.paid_price` | Unit price after seller discounts and vouchers |
| `shipments.parcels[].items[].use_reserved_stock` | Boolean | N | Outbound from reserved stock | N/A | Default `false` |
| `shipments.parcels[].items[].customs_value` | Number | N | Declare value for insurrance or customs importation. | N/A | Not sent |
| `config` | Object | **Y** |  | N/A | Parent object: see child rows |
| `config.insurance` | Boolean | **Y** |  | N/A | Default `false` |
| `config.currency` | String | **Y** |  | `platform.currency` |  |
| `config.unit_metric` | String | **Y** |  | N/A | Default `metric` |
| `config.sort_mode` | String | **Y** |  | N/A | Default `best_price` |
| `config.auto_approve` | Boolean | **Y** | Set default to N in case delivery by your self or marketplace | N/A | Marketplace delivery: `false` (per Boxme doc). Boxme delivery: `true` `[CONFIRM]` |
| `config.order_type` | String | **Y** |  | N/A | Default `b2c` |
| `config.include_distance_service` | Boolean | **Y** |  | N/A | Default `false` |
| `config.delivery_service` | String | N | Delivery service code, set default to BM_DBS in case delivery by your self or marketplace | N/A | Marketplace delivery: `BM_DBS`. Boxme delivery: `service_code` chosen from Get Shipping Option (4.1). Rule for which orders use which: `[TBD: R-13]` |
| `config.check_stock` | Boolean | **Y** |  | N/A | Default `true` (out-of-stock → status 212 / `NOT_ENOUGH_ITEM`) |
| `config.expiry_guard` | Boolean | N | Expiry guard | N/A | Default `false` |
| `config.is_customize_packaging` | Boolean | N | Customize packaging - additional charges may apply | N/A | Default `false` |
| `payment` | Object | **Y** |  | N/A | Parent object: see child rows |
| `payment.cod_amount` | Number | **Y** | For TH market courier only support integer. If you send as decimal we will automatically round up them. | `order_item.info.cod_line_total` + `order.shipping_fee` | Marketplace delivery: `0`. Boxme delivery with `payment_method.master_name` = `cod`: sum of line COD + shipping fee; else `0`. TH: integer (round up) |
| `referral` | Object | **Y** |  | N/A | Parent object: see child rows |
| `referral.order_number` | String | **Y** | Order number from your system | `order.order_number` `[CONFIRM: C2]` | Duplicate check field `[TBD: Q-22]` |
| `referral.platform` | String | **Y** | Your platform/system name | N/A | Default `PowerSell` |
| `referral.source` | String | **Y** | Sale channel Values: shopee, lazada, tiktok, tiki, web, other | `platform.group` | See enum 4.11: Shopee → `shopee`, Lazada → `lazada`, TikTok Shop → `tiktok`, Tiki → `tiki`, Shopify / webstore → `web`, others → `other` |
| `referral.store_order_id` | String | N | Order number from sales channel | `order.sc_order_number` | Marketplace order number |
| `referral.store_id` | String | N | Marketplace Store Code/ID | [TBD] | Marketplace store code; PowerSell field `[TBD]` |
| `fulfillment_vas` | Object | N |  | N/A | Parent object: see child rows |
| `fulfillment_vas.fulfill_now` | Boolean | N |  | N/A | `true` for instant-delivery orders (TikTok `fulfillment_priority_level` / Shopee instant carrier). Boxme packs within 45 min |
| `fulfillment_vas.priority_fulfill` | Boolean | N |  | N/A | `true` for same-day orders. Boxme packs within 2 h |

#### Response

```json
{
  "data": {
    "label_url": "https://s.boxme.asia/api/v1/orders/awb-label/MzEwZWNmYTktYWY1Zi00OTM2LTk4M2EtYmE2MGM5YmYxN2Ez",
    "tracking_number": "BM65221104356",
    "courier_name": "Boxme Express",
    "service_code": "BM_DBS",
    "service_name": "Self-Delivery",
    "cod_value": 24000
  },
  "error": false,
  "error_code": "",
  "messages": "Create order successfully.",
  "request_id": 1703485822
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.label_url` | String | **Y** |  | `order_billing.info.awb_url` `[CONFIRM: C3]` | Boxme delivery only: Boxme label |
| `data.tracking_number` | String | **Y** |  | `wms_sale_order.partner_so_id` `[CONFIRM: C2]` | Boxme order ID (e.g. `BM…`). Key for pack, cancel, get order, return |
| `data.courier_name` | String | **Y** |  | `shipment_provider.name` | Boxme delivery only |
| `data.service_code` | String | **Y** |  | N/A |  |
| `data.service_name` | String | **Y** |  | N/A |  |
| `data.cod_value` | Integer | **Y** |  | N/A |  |
| `data.sorting_hub` | String | **Y** |  | N/A |  |
| `data.total_fee` | Integer | **Y** |  | N/A |  |
| `data.fee` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.fee.currency` | String | **Y** |  | N/A |  |
| `data.fee.shipping_fee` | Integer | **Y** |  | N/A |  |
| `data.fee.cod_fee` | Integer | **Y** |  | N/A |  |
| `data.fee.insurance_fee` | Integer | **Y** |  | N/A |  |
| `data.fee.discount_detail` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.fee.discount_detail.courier_discount` | Integer | **Y** |  | N/A |  |
| `data.fee.discount_detail.coupon_discount` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.fee.fulfillment.handling` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment.heavy_weight` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment.material` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment.special` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment.handover_fee` | Integer | **Y** |  | N/A |  |
| `data.fee.fulfillment.bubble_wrap_fee` | Integer | **Y** |  | N/A |  |
| `data.fee.special_vas_fees` | Array[String] | **Y** |  | N/A |  |
| `data.fee.material_fees` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.fee.material_fees[].code` | String | N |  | N/A |  |
| `data.fee.material_fees[].value` | Integer | N |  | N/A |  |
| `data.fee.material_fees[].type` | Integer | N |  | N/A |  |
| `data.fee.material_fees[].name` | String | N |  | N/A |  |
| `data.fee.material_fees[].chargeable_value` | Number | N |  | N/A |  |
| `data.fee.material_fees[].chargeable_unit` | String | N |  | N/A |  |
| `data.fee.material_fees[].items` | Null | N |  | N/A |  |
| `data.fee.extra_service_fee` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.fee.extra_service_fee.total` | Integer | **Y** |  | N/A |  |
| `data.fee.extra_service_fee.fees` | Array[String] | **Y** |  | N/A |  |
| `data.fee.remote_fee` | Integer | **Y** |  | N/A |  |
| `data.origin_courier` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.origin_service` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.discount` | Integer | **Y** |  | N/A |  |
| `data.invoice_url` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 4.3 Order pack (send marketplace AWB)

#### Purpose

Give Boxme the marketplace label and tracking number so it can pick and pack (UC-12).

**When PowerSell calls it:** **Marketplace delivery only. Do not call for Boxme delivery.** Standard / same-day: after PowerSell has arranged shipment on the channel and received the AWB — Boxme picks only after this call (R-10). Instant: right after 4.2, with `courier_tracking_code` = marketplace order number; confirm on the channel after Ready to ship (`211`).

#### Endpoint

```
PUT https://s.boxme.asia/api/v2/orders/fulfill/pack/
```
Boxme reference: https://developers.boxme.asia/api-5231045

#### Request

```bash
curl -X PUT 'https://s.boxme.asia/api/v2/orders/fulfill/pack/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"tracking_number": "BM889493738484", "self_shipment": {"courier_tracking_code": "JNT45453434343", "courier_name": "GHN"}, "handover_method": "pickup", "shipping_label": "https://storage.googleapis.com/boxme-cloud/label/2023/11/OWRhYTNmODUtMGViNS00NjYwLWFlYWYtMmRjOGQzYzg3YWFh_gfw.png", "fulfill_type": null, "fulfill_sla_time": 0, "store_created_time": 0}'
```

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `self_shipment` | Object | **Y** |  | N/A | Parent object: see child rows |
| `self_shipment.courier_name` | String | **Y** | Courier name. Refer to API Get Courier List | `shipment_provider.name` | Mapped to a Boxme courier name (1.6) `[TBD]` mapping table |
| `self_shipment.courier_tracking_code` | String | **Y** | Courier tracking code | `order_item.tracking_number` | Marketplace AWB. Instant orders: `order.sc_order_number`. Shopee channels without tracking: `[TBD: Q-30]` |
| `self_shipment.org_courier_name` | String | N | Original Courier name on Marketplace. | `shipment_provider.name` | Original carrier name on the marketplace |
| `handover_method` | String | **Y** | pickup/dropoff | N/A | Default `pickup` `[CONFIRM]` (`dropoff` if the brand drops parcels at carrier) |
| `shipping_label` | String | N | Shipping label 10x15cm. Allow pdf, png | `order_billing.info.awb_url` `[CONFIRM: C3]` | PDF / PNG URL, 10×15 cm. Required for standard and priority orders; not for instant |
| `tracking_number` | String | **Y** | Boxme tracking number | `wms_sale_order.partner_so_id` | Boxme order ID from 4.2 |
| `fulfill_sla_time` | Integer | **Y** | SLA based on marketplace requirement | N/A | Marketplace ship-by time; default `0` `[TBD]` |
| `fulfill_type` | String | N |  | N/A | `now` = instant; `priority` = same-day, or TikTok orders paid 14:00–16:00; else `null` |
| `store_created_time` | Integer | **Y** | Time the order created on the sales channel | `order.order_created_at` | Unix timestamp |

#### Response

```json
{
  "data": {
    "label_url": "https://s.boxme.asia/api/v1/orders/awb-label/MzEwZWNmYTktYWY1Zi00OTM2LTk4M2EtYmE2MGM5YmYxN2Ez",
    "tracking_number": "BM65221104356",
    "courier_name": "J&T Express",
    "service_code": "BM_DBS"
  },
  "error": false,
  "error_code": "",
  "messages": "Update pack order successfully.",
  "request_id": 1703485822,
  "total": 0
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.label_url` | String | **Y** | Shipping URL | N/A |  |
| `data.tracking_number` | String | **Y** | Boxme Tracking number | N/A | Echo |
| `data.courier_name` | String | **Y** | Courier Name | N/A |  |
| `data.service_code` | String | **Y** | Boxme Service Code | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | Integer | **Y** |  | N/A | Log with every call (Boxme support uses it) |
| `total` | Integer | **Y** |  | N/A |  |

## 4.4 Update document

#### Purpose

Re-upload a label, or attach an invoice.

**When PowerSell calls it:** When the AWB changes after 4.3.

#### Endpoint

```
PUT https://s.boxme.asia/api/v2/orders/{tracking_number}/update_document/
```
Boxme reference: https://developers.boxme.asia/api-4893914

#### Request

```bash
curl -X PUT 'https://s.boxme.asia/api/v2/orders/{tracking_number}/update_document/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"documents": [{"document_name": "test.jpg", "quantity": 1, "url": "https://doccument.com/test.jpg"}, {"document_name": "test2.pdf", "quantity": 2, "url": "https://doccument.com/test.pdf"}]}'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** |  | `wms_sale_order.partner_so_id` | Boxme order ID |

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `documents` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `documents[].document_name` | String | **Y** | Doc name like invoice, po, shipping label | N/A | e.g. `shipping label` |
| `documents[].quantity` | Integer | **Y** | Copy | N/A | Default `1` |
| `documents[].url` | String | **Y** | Require pdf, png type. | `order_billing.info.awb_url` `[CONFIRM: C3]` | PDF / PNG |
| `documents[].type` | String | **Y** | Values: invoice, po, label, other, billx80 | N/A | `label` (re-upload AWB) or `invoice` |

#### Response

*No sample response in Boxme doc.*

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.tracking_code` | String | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 4.5 Cancel order

#### Purpose

Cancel an order at Boxme (UC-11).

**When PowerSell calls it:** When the order is cancelled on the channel or in PowerSell. Errors: `not_exists`, `cancelled` (treat as success), `not_allowed` (show `WMS error: <messages>`). Partial cancellation is not supported: cancel the whole order and re-create the remaining lines `[TBD: Q-29]` (W-01).

#### Endpoint

```
POST https://s.boxme.asia/api/v2/orders/cancel/{tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-4893915

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/orders/cancel/{tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** |  | `wms_sale_order.partner_so_id` | Boxme order ID |

#### Response

```json
{
  "data": null,
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "1704262964"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Null | **Y** | Object data response | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** | Error code distinguishing reasons Values: not_exists, cancelled, not_allowed | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** | Request ID to get api call log. | N/A | Log with every call (Boxme support uses it) |

## 4.6 Request cancel delivery

#### Purpose

Stop delivery after the order has shipped (Boxme delivery).

**When PowerSell calls it:** Boxme delivery only; available to limited sellers `[CONFIRM]`.

#### Endpoint

```
POST https://s.boxme.asia/api/v2/orders/cancel-delivery/{tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-9368222

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/orders/cancel-delivery/{tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** | Boxme tracking number | `wms_sale_order.partner_so_id` | Boxme order ID |

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `reason_code` | String | **Y** | Values: CANCEL_BY_CUSTOMER, CANCEL_BY_MARKETPLACE, CANCEL_BY_SELLER, OTHER | N/A | Map from PowerSell cancel reason: buyer → `CANCEL_BY_CUSTOMER`, marketplace → `CANCEL_BY_MARKETPLACE`, seller → `CANCEL_BY_SELLER`, else `OTHER` `[CONFIRM]` |

#### Response

```json
{
  "data": null,
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "1704262964"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Null | **Y** | Object data response | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** | Error code distinguishing reasons | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** | Request ID to get api call log. | N/A | Log with every call (Boxme support uses it) |

## 4.7 Get order

#### Purpose

Read order status (fallback to webhook 6.4).

**When PowerSell calls it:** Polling fallback only: rate limit **60 / min**.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/orders/{tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-4893991

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/orders/{tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** | Boxme tracking number | `wms_sale_order.partner_so_id` | Boxme order ID |

#### Response

*No sample response in Boxme doc.*

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.country` | String | **Y** |  | N/A |  |
| `data.tracking_number` | String | **Y** |  | `wms_sale_order.partner_so_id` | Match key |
| `data.order_number` | String | **Y** |  | `order.order_number` | Echo |
| `data.courier_tracking_code` | String | **Y** |  | `wms_sale_order.tracking_number` | Carrier tracking number |
| `data.pickup_id` | Integer | **Y** | Refer to pickup list | `wms_sale_order.wms_warehouse_id` | Via warehouse mapping |
| `data.order_type` | String | **Y** |  | N/A |  |
| `data.receiver` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.receiver.country` | String | **Y** |  | N/A |  |
| `data.receiver.fullname` | String | **Y** |  | N/A |  |
| `data.receiver.phone` | String | **Y** |  | N/A |  |
| `data.receiver.address` | String | **Y** |  | N/A |  |
| `data.receiver.province_id` | Integer | **Y** |  | N/A |  |
| `data.receiver.province_name` | String | **Y** |  | N/A |  |
| `data.receiver.district_id` | Integer | **Y** |  | N/A |  |
| `data.receiver.district_name` | String | **Y** |  | N/A |  |
| `data.receiver.sub_district_id` | Integer | **Y** |  | N/A |  |
| `data.receiver.sub_district_name` | String | **Y** |  | N/A |  |
| `data.receiver.zipcode` | String | **Y** |  | N/A |  |
| `data.receiver.pickup_id` | String | N | Destination warehouse of transfer order (TO) | N/A |  |
| `data.config` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.config.preview` | Boolean | **Y** |  | N/A |  |
| `data.config.insurance` | Boolean | **Y** |  | N/A |  |
| `data.config.is_fulfill_now` | Boolean | **Y** |  | N/A |  |
| `data.config.is_co_inspection` | Boolean | **Y** |  | N/A |  |
| `data.config.is_priority_fulfill` | Boolean | **Y** |  | N/A |  |
| `data.items` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.items[].bsin` | String | **Y** |  | N/A |  |
| `data.items[].seller_sku` | String | **Y** |  | N/A |  |
| `data.items[].quantity` | Integer | **Y** |  | N/A |  |
| `data.items[].weight` | Integer | **Y** |  | N/A |  |
| `data.items[].dimension` | String | **Y** |  | N/A |  |
| `data.items[].product_name` | String | **Y** |  | N/A |  |
| `data.items[].price` | Integer | **Y** |  | N/A |  |
| `data.items[].discounted_price` | Integer | **Y** |  | N/A |  |
| `data.items[].insurance_price` | Integer | N |  | N/A |  |
| `data.items[].line_no` | String | N |  | N/A |  |
| `data.courier_id` | Integer | **Y** |  | N/A |  |
| `data.service_code` | String | **Y** |  | N/A |  |
| `data.order_value` | Integer | **Y** | Order value | N/A |  |
| `data.cod_amount` | Integer | **Y** | CoD amount | N/A |  |
| `data.currency` | String | **Y** |  | N/A |  |
| `data.status` | Integer | **Y** |  | `wms_sale_order.status` | See 4.9 / 4.10 status mapping |
| `data.status_name` | String | **Y** |  | N/A |  |
| `data.created_time` | Integer | **Y** |  | N/A |  |
| `data.approved_time` | Integer | **Y** |  | N/A |  |
| `data.sla_to_pack` | Integer | **Y** | SLA to pack for priority order | N/A |  |
| `data.sla_to_ship` | Integer | **Y** | Handover SLA to courier (Boxme's commitment) | N/A |  |
| `data.sla_to_fulfill` | Integer | **Y** | Marketplace's Handover SLA | N/A |  |
| `data.sla_to_delivery` | Integer | **Y** | SLA to delivery based on Shipped time. | N/A |  |
| `data.sla_to_cancel` | Integer | **Y** | SLA to cancel | N/A |  |
| `data.rts_time` | Integer | **Y** | This is the time to record the RTS SLA. | N/A |  |
| `data.shipped_time` | Integer | **Y** | This is the time to record the handover SLA. | N/A |  |
| `data.delivery_time` | Integer | **Y** |  | N/A |  |
| `data.sla_commitment_note` | String | N | Note when we do not commit the SLA to ship (Boxme's SLA) | N/A |  |
| `data.sla_commitment` | Boolean | **Y** | Commit SLA to ship (Boxme's SLA) or not (true when commit the SLA else false mean not) | N/A |  |
| `data.store_created_time` | Integer | **Y** |  | N/A |  |
| `data.first_delivery_time` | Integer | **Y** | This is the time to record the delivery SLA. | N/A |  |
| `data.delivery_attempt` | Integer | **Y** | Delivery attempt times | N/A |  |
| `data.delivery_success_time` | Integer | **Y** | Delivery/return successfully time | N/A |  |
| `data.return_reason_code` | String | N | Following https://developers.boxme.asia/doc-393944#return-reasonfail-delivery-reason-type | N/A |  |
| `data.non_committed_sla` | Boolean | **Y** | Add non_committed_sla in cases where the issue is caused by the buyer | N/A |  |
| `data.return_delivery_sla` | Integer | N | Incase order return to sender | N/A |  |
| `data.wms_created_time` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 4.8 Get tracking

#### Purpose

Delivery journey for Boxme-delivered orders.

**When PowerSell calls it:** On demand (order detail screen).

#### Endpoint

```
GET https://s.boxme.asia/api/v2/orders/tracking/{tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-22333180

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/orders/tracking/{tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** |  | `wms_sale_order.partner_so_id` | Boxme order ID |

#### Response

```json
{
  "data": {
    "total_count": 6,
    "journeys": [
      {
        "status": 606,
        "status_name": "Destroy at destination by system",
        "location": "Boxme system",
        "note": "Update by system",
        "created_time": 1729440040,
        "updated_time": 1729440040,
        "courier_time": 1729440040
      },
      {
        "status": 211,
        "status_name": "Ready to ship at warehouse",
        "location": "Bicutan Drive, Barangay Batino, Calamba City, Laguna",
        "note": "",
        "created_time": 1721637417,
        "updated_time": 1721637417,
        "courier_time": 1721637416
      },
      {
        "status": 217,
        "status_name": "Processing at warehouse",
        "location": "Bicutan Drive, Barangay Batino, Calamba City, Laguna",
        "note": "Noted: In-pickup process PK****",
        "created_time": 1721619335,
        "updated_time": 1721619335,
        "courier_time": 1721619090
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.journeys` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.journeys[].status` | Integer | **Y** |  | N/A | Delivery history (Boxme delivery). Display only |
| `data.journeys[].status_name` | String | **Y** |  | N/A |  |
| `data.journeys[].location` | String | **Y** |  | N/A |  |
| `data.journeys[].note` | String | **Y** |  | N/A |  |
| `data.journeys[].created_time` | Integer | **Y** | The time we recorded it in the system | N/A |  |
| `data.journeys[].updated_time` | Integer | **Y** |  | N/A |  |
| `data.journeys[].courier_time` | Integer | **Y** | This is the time to record the delivery SLA. | N/A |  |
| `data.journeys[].fail_delivery_reason_code` | String | N |  | N/A | CR01–CR07 (see 4.11) |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

### 4.9 Order status mapping

| **Boxme status** | **PowerSell display status** | **PowerSell backend status** | **Note** |
|---|---|---|---|
| `110` Awaiting Label | Sent successfully | New | Marketplace delivery: waiting for 4.3 |
| `201` Label generated | Sent successfully | New | |
| `212` Out of stock | Failed to send | Out of stock | Re-send rule `[TBD: Q-22]` |
| `210` Awaiting process at warehouse | Sent successfully | New | |
| `217` Processing at warehouse | Sent successfully | Picking | Boxme does not split picking / packing |
| `211` Ready to ship | Packed | Packed | Instant orders: confirm on channel now |
| `280` Waiting to handover | Packed | Packed | |
| `300`, `301` Shipped | Shipped | Shipped | |
| `801` Fulfilled | Shipped | Shipped | Final for marketplace delivery `[TBD: Q-26]` |
| `700` Cancelled by seller, `701` by operator, `703` by system | Cancelled | Canceled | Display "Cancelled" `[CONFIRM: S10]` |
| `705` Cancelled at warehouse | Cancelled | Canceled | After processing started; re-inbound handling `[TBD: Q-26]` |
| `302` Courier refused | `[TBD: Q-26]` | `[TBD: Q-26]` | Gap (R-07) |
| `704` Pending for audit | `[TBD: Q-26]` | `[TBD: Q-26]` | Gap |
| `706` Waiting for cancellation | `[TBD: Q-26]` | `[TBD: Q-26]` | Gap (proposed: keep previous status) |
| `708` Cancelled by lost item | `[TBD: Q-26]` | `[TBD: Q-26]` | Gap (Canceled or Lost in transit?) |

### 4.10 Delivery status mapping (Boxme delivery)

| **Boxme status** | **PowerSell display status** | **PowerSell backend status** | **Note** |
|---|---|---|---|
| `304` In-transit, `310` Out for delivery | Shipped | Shipped | |
| `400` Out of delivery, `410` Awaiting re-delivery | Shipped | Delivery failed | Reason in `failed_delivery_reason_code` |
| `420` Return processing, `430` Return approved | Shipped | On return | |
| `600` Returned | Shipped | Returned | Create return reconcile record `[TBD]` |
| `800` Delivered | Delivered | Delivered | |
| `605`, `606` Destroy at destination hub | `[TBD: Q-26]` | `[TBD: Q-26]` | Lost / damaged by carrier: Lost in transit? |

### 4.11 Enumerated field values

**referral.source**

| **PowerSell value** | **Boxme value** | **Note** |
|---|---|---|
| Shopee | `shopee` | |
| Lazada | `lazada` | |
| TikTok Shop | `tiktok` | |
| Tiki | `tiki` | |
| Shopify / webstore | `web` | |
| Zalora, Qoo10, others | `other` | |

**warehouse_condition** (from `product.storage_type`)

| **PowerSell value** | **Boxme value** | **Note** |
|---|---|---|
| Ambient | `1` Normal | |
| Air-conditioning | `2` Air conditioner | |
| Chilled, Freezer | — | Not supported (R-09) |

**condition_level** (receiving note, returns)

| **Boxme value** | **PowerSell value** | **Note** |
|---|---|---|
| `A` | Good (accepted) | |
| `D1`, `D2`, `D3` | Damaged | `[CONFIRM: Q-28]` all non-sellable |
| `L`, `DE` | `[TBD: Q-28]` | |

**Failed delivery reason** (`failed_delivery_reason_code`)

| **Boxme value** | **Meaning** |
|---|---|
| `CR01` | Customer refused | 
| `CR02` | Customer rescheduled |
| `CR03` | Customer unreachable |
| `CR04` | Customer not at address |
| `CR05` | Wrong / incomplete address |
| `CR06` | Item / parcel damaged |
| `CR07` | Courier delay / overload |

**Return reason_code** (5.1)

Boxme values: `NOT_RECEIPT`, `WRONG_ITEM`, `ITEM_DAMAGED`, `DIFFERENT_DESCRIPTION`, `MUTUAL_AGREE`, `CHANGE_MIND`, `ITEM_MISSING`, `EXPECTATION_FAILED`, `ITEM_FAKE`, `PHYSICAL_DMG`, `FUNCTIONAL_DMG`, `OTHER`. Mapping from PowerSell / marketplace return reasons `[TBD]`; default `OTHER`.

---

# 🔖 5. Return management

## 5.1 Create returns order

#### Purpose

Announce a return to Boxme (UC-15).

**When PowerSell calls it:** When a marketplace return / failed delivery is accepted and the original order was fulfilled by Boxme. **Not for Boxme-delivered failed deliveries**: those come back inside the order flow (`420` → `600`, see 4.10).

#### Endpoint

```
POST https://s.boxme.asia/api/v2/orders/rma/create/{tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-5002111

#### Request

```bash
curl -X POST 'https://s.boxme.asia/api/v2/orders/rma/create/{tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json' \
  -d '{"pickup_id": 341740, "return_note": "// return reason ", "reason_code": "OTHER", "courier_tracking_number": "xxx", "origin_order_number": "xxx", "waiting_confirmation": false, "items": [{"return_note": "// return reason ", "quantity": 1, "sku": "8809625241353"}, {"return_note": "// return reason ", "quantity": 1, "sku": "8809625241353"}]}'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `tracking_number` | path | **Y** |  | `wms_sale_order.partner_so_id` | Boxme order ID |

##### Request params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `pickup_id` | Integer | **Y** |  | `wms_warehouse.partner_warehouse_id` | Warehouse that fulfilled the original order |
| `reason_code` | String | **Y** |  | `order_return_reconcile_item.detail_reason` `[CONFIRM: C13]` | Map to Boxme return reason codes (4.11); default `OTHER` |
| `waiting_confirmation` | Boolean | **Y** |  | N/A | Default `false` |
| `items` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `items[].quantity` | Integer | **Y** |  | `order_return_reconcile_item.expected_qty` |  |
| `items[].seller_sku` | String | **Y** |  | `product.inventory_sku` | Doc example uses `sku` instead (D-07) |
| `origin_order_number` | String | **Y** | Origin order number | `order.order_number` `[CONFIRM: C2]` |  |
| `return_order_number` | String | **Y** | Return order number generate by platform | `order_return_reconcile.platform_return_request_id` | Marketplace return number; fallback `order_return_reconcile.id` |
| `courier_tracking_number` | String | **Y** | Courier tracking number show on shipping label | `order_return_reconcile_item.return_tracking_id` | Return parcel tracking number |
| `return_note` | String | **Y** |  | N/A | Default `Created by PowerSell` |
| `combine_id` | String | N | Unique number to consolidate multiple dropship order return. | N/A | Not sent |
| `01HTPRXX7CJ3BFGXWQTG275SBB` | String | **Y** |  | [TBD] | Placeholder name in Boxme doc, marked mandatory `[TBD: Q-10]` |
| `order_list` | Array[String] | N | List of Return order number generate by platform | N/A | Not sent |

#### Response

```json
{
  "data": {
    "return_tracking_number": "",
    "order_number": ""
  },
  "error": true,
  "error_code": "string",
  "messages": "string",
  "request_id": 0
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.return_tracking_number` | String | **Y** | Boxme return tracking number | `order_return_reconcile.wms_ref_no` `[CONFIRM: C8]` | Boxme return ID (e.g. `BM…RT`) |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 5.2 Get returns order

#### Purpose

Return status and times.

**When PowerSell calls it:** Polling fallback for webhook 6.6.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/orders/rma/list/
```
Boxme reference: https://developers.boxme.asia/api-5002117

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/orders/rma/list/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `return_tracking_number` | query | N |  | `order_return_reconcile.wms_ref_no` | Boxme return ID |
| `created_from` | query | N |  | N/A |  |
| `created_to` | query | N |  | N/A |  |
| `page_size` | query | **Y** |  | N/A |  |
| `page` | query | N |  | N/A |  |

#### Response

```json
{
  "data": {
    "total_count": 1,
    "orders": [
      {
        "country": "VN",
        "order_id": 6838349,
        "return_tracking_number": "BM881647999599RT",
        "origin_tracking_number": "BM881647999599",
        "order_number": "po_order_code",
        "items": [
          {
            "seller_sku": "HOP_BOXME_01",
            "product_name": "Hộp Boxme 001",
            "return_note": null,
            "quantity": 1,
            "accept_quantity": 0,
            "damage_quantity": 0,
            "lost_quantity": 0,
            "destroy_quantity": 0
          }
        ],
        "courier_name": "Boxme Express",
        "courier_tracking_code": "BM881647999599",
        "order_status": 2,
        "order_status_name": "Received",
        "item_status": 1,
        "item_status_name": "Waiting inspection",
        "return_note": "",
        "proof": [
  ... (truncated, see Boxme doc)
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.orders` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.orders[].country` | String | N |  | N/A |  |
| `data.orders[].order_id` | Integer | N |  | N/A |  |
| `data.orders[].return_tracking_number` | String | N |  | `order_return_reconcile.wms_ref_no` | Match key |
| `data.orders[].origin_tracking_number` | String | N |  | N/A |  |
| `data.orders[].order_number` | String | N |  | N/A |  |
| `data.orders[].items` | Array[Object] | N |  | N/A | Parent object: see child rows |
| `data.orders[].items[].seller_sku` | String | N |  | N/A |  |
| `data.orders[].items[].product_name` | String | N |  | N/A |  |
| `data.orders[].items[].return_note` | Null | N |  | N/A |  |
| `data.orders[].items[].quantity` | Integer | N |  | N/A |  |
| `data.orders[].courier_name` | String | N |  | N/A |  |
| `data.orders[].courier_tracking_code` | String | N |  | N/A |  |
| `data.orders[].order_status` | Integer | N |  | N/A | See 5.5 |
| `data.orders[].order_status_name` | String | N |  | N/A |  |
| `data.orders[].return_note` | String | N |  | N/A |  |
| `data.orders[].proof` | Array[String] | N |  | N/A |  |
| `data.orders[].received_time` | Integer | N |  | `order_return_reconcile.received_at` | Unix → local |
| `data.orders[].complete_time` | Integer | N |  | N/A |  |
| `data.orders[].created_time` | Integer | N |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | Integer | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 5.3 Get order returns receive

#### Purpose

Returned quantities per SKU and condition (UC-16).

**When PowerSell calls it:** When webhook 6.6 reports `600` Returned.

#### Endpoint

```
GET https://s.boxme.asia/api/v2/orders/rma/received/{return_tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-5363310

#### Request

```bash
curl -X GET 'https://s.boxme.asia/api/v2/orders/rma/received/{return_tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `return_tracking_number` | path | **Y** |  | `order_return_reconcile.wms_ref_no` | Boxme return ID |

#### Response

```json
{
  "data": {
    "total_count": 2,
    "received": [
      {
        "bsin": "BSN33152982758216",
        "seller_sku": "TEST-0002",
        "product_name": "TEST-0002",
        "quantity_received": 1,
        "condition_level": "A",
        "batch_lot": "",
        "expiry_date": 0
      },
      {
        "bsin": "BSN33152982758216",
        "seller_sku": "TEST-0002",
        "product_name": "TEST-0002",
        "quantity_received": 1,
        "condition_level": "A",
        "batch_lot": "",
        "expiry_date": 0
      }
    ]
  },
  "error": false,
  "error_code": "",
  "messages": "",
  "request_id": "65e158a0f1c87917a856e7f8"
}
```

##### Response params table

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `data` | Object | **Y** |  | N/A | Parent object: see child rows |
| `data.total_count` | Integer | **Y** |  | N/A |  |
| `data.received` | Array[Object] | **Y** |  | N/A | Parent object: see child rows |
| `data.received[].bsin` | String | **Y** |  | N/A |  |
| `data.received[].seller_sku` | String | **Y** |  | `product.inventory_sku` | Match key |
| `data.received[].product_name` | String | **Y** |  | N/A |  |
| `data.received[].quantity_received` | Integer | **Y** |  | `wms_exchange_order_item.accepted_quantity` / `damaged_quantity` `[CONFIRM: C7]` | Sum rows with `condition_level` `A` → accepted; `D1`–`D3` → damaged; lost = expected − (accepted + damaged). `L`, `DE` `[TBD: Q-28]` |
| `data.received[].condition_level` | String | **Y** |  | N/A | See above |
| `data.received[].batch_lot` | String | **Y** |  | N/A |  |
| `data.received[].expiry_date` | Integer | **Y** |  | N/A |  |

##### Envelope fields

| **Boxme params** | **Data type** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `error` | Boolean | **Y** |  | N/A |  |
| `error_code` | String | **Y** |  | N/A | On error: show `WMS error: <messages>` |
| `messages` | String | **Y** |  | N/A |  |
| `request_id` | String | **Y** |  | N/A | Log with every call (Boxme support uses it) |

## 5.4 Cancel returns order

#### Purpose

Cancel a return announced by mistake (UC-17).

**When PowerSell calls it:** When the return is cancelled in PowerSell. Response not documented `[TBD: Q-27]`. Cancel window `[TBD: Q-07]`.

#### Endpoint

```
DELETE https://s.boxme.asia/api/v2/orders/rma/cancel/{return_tracking_number}/
```
Boxme reference: https://developers.boxme.asia/api-5002118

#### Request

```bash
curl -X DELETE 'https://s.boxme.asia/api/v2/orders/rma/cancel/{return_tracking_number}/' \
  -H 'Authorization: Token {{API_KEY}}' \
  -H 'Content-Type: application/json'
```

##### Path / query params

| **Boxme params** | **In** | **Mandatory** | **Boxme description** | **PowerSell params** | **PowerSell note** |
|---|---|---|---|---|---|
| `return_tracking_number` | path | **Y** |  | `order_return_reconcile.wms_ref_no` | Boxme return ID |

#### Response

*No sample response in Boxme doc.*

### 5.5 Return status mapping

| **Boxme status** | **PowerSell status** | **Note** |
|---|---|---|
| `201` Label generated | Pending receipt | |
| `501` Awaiting to receive | Pending receipt | |
| `502` Received | Pending receipt | |
| `503` Inspected | Pending receipt | |
| `600` Returned | Received (Closed if accepted = expected `[CONFIRM: S3]`) | Then call 5.3 |
| (after Cancel returns order) | Canceled | Boxme status code `[TBD: Q-27]` |

---

# 🔖 6. Webhooks (Boxme → PowerSell)

All webhooks are POSTed by Boxme to the PowerSell webhook URL with the common body `{ country, seller_id, event_type, data, request_id, timestamp }`. Setup and handling rules: see Authentication and technical rules.

## 6.1 Shipment (ASN) status push

#### Purpose

Push Shipment(ASN) status change

Boxme reference: https://developers.boxme.asia/api-5181971

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | `shipment.status.change` | N/A |
| `data` | Object |  | N/A |
| `data.shipment_code` | String |  | Match `wms_asn.partner_asn_id` |
| `data.po_number` | String | PO/TO number | N/A |
| `data.status` | Integer | Refer to Shipment Status List — See 3.7. On `6` Completed → call Get Receiving Note (3.6) for quantities; on `11` Partial inspection → pull stock for the ASN's SKUs | Update `wms_asn.status` |
| `data.status_name` | String |  | N/A |
| `data.received_time` | Integer |  | N/A |
| `data.completed_time` | Integer | When status `6` and received = expected | Set `wms_asn.received_date` |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 331529,
  "event_type": "shipment.status.change",
  "data": {
    "shipment_code": "SM-VN-331529-24632598",
    "po_number": "MY_TRACKING",
    "status": 6,
    "status_name": "Success",
    "received_time": 1615442990,
    "completed_time": 1616484318
  },
  "request_id": "65740c5ecb4eed8c37c8dc89",
  "timestamp": 1702104158
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

## 6.2 Available stock change push

#### Purpose

This hook is used for self-managed inventory OMS systems. 

Boxme reference: https://developers.boxme.asia/api-9244408

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | `product.available.change` | N/A |
| `data` | Object |  | N/A |
| `data.bsin` | String |  | N/A |
| `data.seller_sku` | String |  | Match `product.inventory_sku` |
| `data.condition_level` | String | Process only `A` | Filter |
| `data.stock_quantity` | Integer |  | Set `wms_product.stock_quantity` |
| `data.awaiting_quantity` | Integer |  | N/A |
| `data.reserved_quantity` | Integer |  | N/A |
| `data.prepack_quantity` | Integer |  | N/A |
| `data.available_quantity` | Integer | Use the full value, not `adjust` | Set `wms_product.available_quantity` and `product_stock.open_stock` |
| `data.incoming_quantity` | Integer |  | N/A |
| `data.adjust` | Integer | Delta; log only | N/A |
| `data.pickup_id` | Integer |  | Match warehouse |
| `data.refer_code` | String | Log | N/A |
| `data.refer_type` | String | Log: hold / inbound / return / release / void / abnormal | N/A |
| `data.note` | String |  | N/A |
| `data.update_time` | Integer |  | Ignore event if older than the last processed `update_time` for this SKU + warehouse |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 331529,
  "event_type": "product.available.change",
  "data": {
    "pickup_id": 409223,
    "bsin": "BSN33152982996791",
    "seller_sku": "TEST-0005",
    "condition_level": "A",
    "stock_quantity": 20,
    "adjust": 1,
    "awaiting_quantity": 2,
    "reversed_quantity": 10,
    "available_quantity": 8,
    "incoming_quantity": 100,
    "refer_type": "inbound",
    "refer_code": "SM-VN-331529-54200124",
    "note": "Putaway-SM-VN-331529-54200124",
    "update_time": 1696301501
  },
  "request_id": "657405ca5e492f3c6f4dd838",
  "timestamp": 1702102474
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

## 6.3 Product update push

#### Purpose

Push Product status change

Boxme reference: https://developers.boxme.asia/api-5181972

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | `product.update` | N/A |
| `data` | Object |  | N/A |
| `data.bsin` | String |  | Match `wms_product.partner_id` |
| `data.seller_sku` | String |  | N/A |
| `data.product_name` | String |  | N/A |
| `data.change_values` | Array[Object] | Use to detect Boxme approval `[TBD: Q-11]` | Log |
| `data.change_values[].name` | String |  | N/A |
| `data.change_values[].old` | Integer |  | N/A |
| `data.change_values[].new` | Integer |  | N/A |
| `data.update_time` | Integer |  | N/A |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 331529,
  "event_type": "product.update",
  "data": {
    "bsin": "BSN33152982996791",
    "seller_sku": "TEST-0005",
    "product_name": "TEST-0005",
    "change_values": [
      {
        "name": "weight",
        "old": 500,
        "new": 750
      },
      {
        "name": "approved",
        "old": false,
        "new": true
      },
      {
        "name": "volume",
        "old": "9x13x15",
        "new": "10x13x12"
      }
    ],
    "update_time": 1696301698
  },
  "request_id": "65740507a22fa65d9874d4ed",
  "timestamp": 1702102279
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

## 6.4 Order status push

#### Purpose

Push order status change (Except return orders).

Boxme reference: https://developers.boxme.asia/api-5181959

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | `order.status.change` | N/A |
| `data` | Object |  | N/A |
| `data.tracking_number` | String |  | Match `wms_sale_order.partner_so_id` |
| `data.order_number` | String |  | N/A |
| `data.courier_name` | String |  | Set carrier (`shipment_provider.name`) |
| `data.courier_tracking_code` | String |  | Set `wms_sale_order.tracking_number` |
| `data.order_type` | String | Values: ship, b2b, b2c | N/A |
| `data.status` | Integer | See 4.9 / 4.10 | Update `wms_sale_order.status` (backend) and display status |
| `data.status_name` | String |  | N/A |
| `data.rts_time` | Integer | Log | N/A |
| `data.shipped_time` | Integer | Log | N/A |
| `data.delivery_time` | Integer |  | N/A |
| `data.update_time` | Integer |  | Set `wms_sale_order.updated_at`; ignore older events |
| `data.pickup_id` | Integer |  | N/A |
| `data.note` | String | Journey note for order | N/A |
| `data.failed_delivery_reason_code` | String | Following https://developers.boxme.asia/doc-393944#return-reasonfail-delivery-reason-type — Boxme delivery: CR01–CR07 | Show reason |
| `data.store_created_time` | Integer |  | N/A |
| `data.first_delivery_time` | Integer |  | N/A |
| `data.failed_delivery_reason` | String |  | N/A |
| `data.delivery_attempt` | Integer |  | N/A |
| `data.delivery_success_time` | String | Log | N/A |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 331529,
  "event_type": "order.status.change",
  "data": {
    "tracking_number": "BM61556564658",
    "order_number": "2023113001",
    "courier_name": "Boxme Express",
    "courier_tracking_code": "BM61556564658",
    "order_type": "b2c",
    "status": 210,
    "status_name": "Awaiting process at warehouse",
    "rts_time": 0,
    "shipped_time": 0,
    "delivery_time": 0,
    "update_time": 1701336279
  },
  "request_id": "657408c12367d72792d4f403",
  "timestamp": 1702103233
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

## 6.5 Direct RTS (Lazada)

#### Purpose

Implement this hook to avoid PNR issue.

Boxme reference: https://developers.boxme.asia/api-6243375

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | `order.direct.rts` | N/A |
| `data` | Object |  | N/A |
| `data.tracking_number` | String |  | Match `wms_sale_order.partner_so_id` |
| `data.order_number` | String |  | N/A |
| `data.status` | Integer | Lazada only | Trigger Lazada RTS for the order `[TBD: Q-30]` |
| `data.status_name` | String |  | N/A |
| `data.rts_time` | Integer |  | N/A |
| `data.01HYD3H7Z5KMAEP89ME3QJRPJ6` | String | Placeholder field name in Boxme doc (Q-10) | [TBD] |
| `data.pickup_id` | Integer |  | N/A |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 331529,
  "event_type": "order.direct.rts",
  "data": {
    "tracking_number": "BM61556564658",
    "order_number": "2023113001",
    "status": 280,
    "status_name": "Waiting to handover",
    "rts_time": 0
  },
  "request_id": "657405ca5e492f3c6f4dd838",
  "timestamp": 1702102474
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

## 6.6 Return order status push

#### Purpose

Push returns order status change.

Boxme reference: https://developers.boxme.asia/api-23408484

#### Request params (payload sent TO PowerSell)

| **Field** | **Data type** | **Description** | **PowerSell action** |
|---|---|---|---|
| `country` | String |  | N/A |
| `seller_id` | Integer |  | N/A |
| `event_type` | String | return_order.status.change — `return_order.status.change` | N/A |
| `data` | Object |  | N/A |
| `data.tracking_number` | String |  | Match `order_return_reconcile.wms_ref_no` |
| `data.order_number` | String |  | N/A |
| `data.courier_name` | String |  | N/A |
| `data.courier_tracking_code` | String |  | N/A |
| `data.order_type` | String | Values: return, exchange — `return` / `exchange` | N/A |
| `data.status` | Integer | See 5.5. On `600` Returned → call Get Order Returns Receive (5.3) | Update return status |
| `data.status_name` | String |  | N/A |
| `data.update_time` | Integer |  | N/A |
| `data.pickup_id` | Integer |  | N/A |
| `data.note` | String | Journey note for order | N/A |
| `request_id` | String |  | N/A |
| `timestamp` | Integer |  | N/A |

#### Example payload

```json
{
  "country": "VN",
  "seller_id": 334353,
  "event_type": "return_order.status.change",
  "data": {
    "tracking_number": "BM64438422233RE",
    "order_number": "SV2510202AF3F33F",
    "courier_name": "Boxme Express",
    "courier_tracking_code": "854113389645",
    "order_type": "exchange",
    "pickup_id": 341740,
    "status": 504,
    "status_name": "On hold",
    "note": "On hold: Đơn hàng khiếu nại",
    "update_time": 1761639113
  },
  "request_id": "69007ac97ca0831fd17685a8",
  "timestamp": 1761639114
}
```

#### Response

HTTP 200 (empty body) within 3 seconds.

---

# 🚫 Out of scope

| Flow / endpoint | Reason |
|---|---|
| Create Delivery Order (non-fulfillment) | Boxme ships goods not stored in its warehouse; not a WMS use case |
| Create B2B Order, B2B customers, B2B pickup timeslot | B2B / offline orders not in Phase 1 |
| Reserved Stock | PowerSell does not reserve stock at the WMS |
| COD statements, order fees | Finance; COD reconciliation may be a later request |
| Inventory Change Push, Abnormal Inventory Change Push, Sale Invoice Request | Available Stock Change covers sellable stock; ERP / invoice not in scope |
| Get Inbound Serial List, Get Packed Items, Get Shipment List, Get Order List | Serial / batch tracking not in Phase 1; lists not needed with webhooks |
| Pickup address create / activate | Seller pickup addresses are not used for fulfilment |

# ❓ Open questions

## For Boxme (tracker Q&A log)

| ID | Question | Blocks |
|---|---|---|
| Q-02 | Rate limits per IP or per key; can they be raised for campaign days? | 4.2 volume, R-01 |
| Q-07 | Cancel windows for order, ASN, return | 3.4, 4.5, 5.4 |
| Q-08 | Shelf-life threshold unit: days or months | 2.3, 2.4 |
| Q-10 | Placeholder field names (`01HTPRXX…`, `01HYD3…`), COD paths `/`, zipcode path `/pi/v2/` | 5.1, 6.5, 1.5 |
| Q-11 | Product approval before first inbound | 2.3, 3.1 |
| Q-21 | Volume unit (cm or mm) | 2.3 |
| Q-22 | Duplicate-order field; re-use of order number after cancel | 4.2 |
| Q-23 | Warehouse vs seller pickup address in pickup list | 1.1 |
| Q-24 | ASN final status when received < expected | 3.7 |
| Q-25 | Receiving note rows: per receipt or total | 3.6 |
| Q-26 | Order statuses 302, 605 / 606, 704, 706, 708; 300 vs 801 | 4.9, 4.10 |
| Q-27 | Return status and response after cancel | 5.4, 5.5 |
| Q-28 | Condition levels `L`, `DE`; D1–D3 non-sellable? | 3.6, 5.3 |
| Q-29 | Partial (line) cancellation | 4.5 |
| Q-30 | Boxme picks only after Order Pack; Shopee orders without tracking; Direct RTS timing | 4.3, 6.5 |
| Q-31 | Masked phone / address accepted? | 4.1, 4.2 |
| Q-32 | Location IDs after new VN database; name-only matching | 1.2–1.5, 4.1, 4.2 |
| Q-33 | Default values for product fields PowerSell does not hold | 2.3 |

## For PowerSell dev (reference data model)

| ID | Question | Used in |
|---|---|---|
| C1 | `wms_product.partner_id` vs `partner_key` | 2.3, 2.4 |
| C2 | `so_code` / `partner_so_id`; default order number sent | 4.2, 5.1 |
| C3 | AWB URL field | 4.2, 4.3, 4.4 |
| C4 | Shelf-life field paths | 2.3 |
| C5 | Package vs product weight; fragile path | 2.3 |
| C7 | Return accepted / damaged quantity fields | 5.3 |
| C8 | Return partner reference field | 5.1 |
| C9 | Customer / address field set | 4.1, 4.2 |
| C11 | ASN received quantity field | 3.6 |
| C13 | Return reason field | 5.1 |
| S3, S4, S10 | Return "Closed"; ASN "New"; display "Cancelled" | 3.7, 4.9, 5.5 |

## For PowerSell business / product

| ID | Question | Used in |
|---|---|---|
| R-13 | Which orders use Boxme delivery vs marketplace delivery | 4.1, 4.2 |
| — | Boxme delivery service selection rule (cheapest? fixed per brand?) | 4.1 |
| — | Automate ASN timeslot booking, or book in Boxme portal | 3.2, 3.3 |
| — | Carrier name mapping table owner (PowerSell carrier → Boxme courier name) | 4.3 |

