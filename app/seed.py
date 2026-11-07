"""Dữ liệu khởi tạo (F-00) và dữ liệu demo.

    python -m app.seed            # tạo DB demo tại data/skyline.db (xóa DB cũ)

Mọi con số dưới đây là dữ liệu giả lập để demo, không phải số liệu thật của Skyline.
"""
import os
import sys

from . import audit, clock, reconcile, workflow as wf
from . import settings as S
from .auth import hash_password
from .db import connect, db_path, init_db, insert, q1

DEMO_PASSWORD = "skyline123"

USERS = [
    # username, họ tên, vai trò, trưởng ban, chủ TK
    ("truongban", "Nguyễn Văn An (Trưởng ban)", "bqt", 1, 1),
    ("phoban", "Trần Thị Bình (Phó ban)", "bqt", 0, 1),
    ("tv_cuong", "Lê Văn Cường", "bqt", 0, 0),
    ("tv_dung", "Phạm Thị Dung", "bqt", 0, 0),
    ("tv_em", "Hoàng Văn Em", "bqt", 0, 0),
    ("thuky", "Võ Thị Giang (Thư ký BQT)", "thu_ky", 0, 0),
    ("bql", "Đặng Văn Hùng (BQL Skyline Services)", "bql", 0, 0),
    ("quantri", "Bùi Văn Khoa (Quản trị hệ thống)", "admin", 0, 0),
]

COST_TYPES = [
    ("bao_tri_thiet_bi", "Bảo trì, sửa chữa thiết bị chung (thang máy, bơm, máy phát…)", 0, 1),
    ("pccc", "Bảo trì hệ thống phòng cháy chữa cháy", 0, 1),
    ("ket_cau", "Sửa chữa kết cấu, chống thấm, sơn ngoài", 0, 0),
    ("luong_bao_ve", "Lương / dịch vụ bảo vệ", 1, 0),
    ("ve_sinh", "Dịch vụ vệ sinh", 1, 0),
    ("dien_nuoc_chung", "Điện nước khu vực chung", 1, 0),
    ("van_phong_pham", "Văn phòng phẩm", 1, 0),
    ("phi_qlvh", "Phí quản lý vận hành", 1, 0),
]

TIERS = [
    (1, 0, "count", 2, 1, 0, "Dưới 20 triệu: Trưởng ban + 1 thành viên (ví dụ, chờ Q1)"),
    (2, 20_000_000, "majority", 0, 0, 0, "20 – dưới 200 triệu: quá bán thành viên BQT (ví dụ, chờ Q1)"),
    (3, 200_000_000, "all", 0, 0, 1, "Từ 200 triệu: toàn bộ BQT, họp trực tiếp (ví dụ, chờ Q1)"),
]


def pdf(label: str) -> bytes:
    return f"%PDF-1.4\n% Tai lieu demo: {label}\n%%EOF\n".encode()


def set_day(conn, d: str):
    S.set_raw(conn, "demo_today", d)


def seed_catalog(conn) -> dict:
    """F-00 + F-01: danh mục nền, số dư, hợp đồng, kế hoạch, lịch sử. Trả về map id tiện dùng."""
    ids = {}
    set_day(conn, "2026-10-01")
    for username, name, role, chair, holder in USERS:
        ids[username] = insert(conn, "users", {"username": username, "full_name": name, "role": role, "is_chair": chair,
                                               "is_account_holder": holder, "password_hash": hash_password(DEMO_PASSWORD),
                                               "email": f"{username}@skyline.example"})
    for code, name, op, emer in COST_TYPES:
        insert(conn, "cost_types", {"code": code, "name": name, "is_operational": op, "emergency_allowed": emer})
    for t in TIERS:
        insert(conn, "approval_tiers", dict(zip(("level", "min_amount", "rule_type", "required_count", "require_chair",
                                                 "in_person", "description"), t)))
    insert(conn, "funds", {"code": "BT", "name": "Quỹ bảo trì", "bank": "Vietcombank – CN Sài Gòn",
                           "account_no": "0071000888999", "account_locked": 1, "opening_balance": 12_500_000_000,
                           "opening_date": "2026-10-01", "interest_unused": 0})
    insert(conn, "funds", {"code": "VH", "name": "Quỹ vận hành", "bank": "BIDV – CN Bến Thành",
                           "account_no": "31410007776666", "account_locked": 0, "opening_balance": 850_000_000,
                           "opening_date": "2026-10-01", "interest_unused": 0})
    for fund in ("BT", "VH"):
        for u in ("truongban", "phoban"):
            insert(conn, "fund_signers", {"fund_code": fund, "user_id": ids[u]})
    insert(conn, "term_deposits", {"fund_code": "BT", "bank": "Vietcombank", "amount": 2_000_000_000, "rate": 4.8,
                                   "start_date": "2026-05-13", "maturity_date": "2026-11-13"})
    insert(conn, "term_deposits", {"fund_code": "BT", "bank": "Vietcombank", "amount": 3_000_000_000, "rate": 5.2,
                                   "start_date": "2026-04-20", "maturity_date": "2027-04-20"})

    bt = insert(conn, "plans", {"fund_code": "BT", "year": 2026, "version": 1, "resolution_no": "01/2026/NQ-HNNCC",
                                "resolution_date": "2026-03-20", "effective_from": "2026-03-20"})
    for code, name, budget, spent in (
        ("BT-01", "Bảo trì hệ thống thang máy", 800_000_000, 320_000_000),
        ("BT-02", "Bảo trì hệ thống PCCC", 600_000_000, 480_000_000),
        ("BT-03", "Chống thấm, sơn mái khối A", 1_200_000_000, 0),
        ("BT-04", "Bảo trì máy phát điện", 250_000_000, 100_000_000),
        ("BT-05", "Bảo trì hệ thống bơm, cấp thoát nước", 300_000_000, 90_000_000),
    ):
        insert(conn, "plan_items", {"plan_id": bt, "code": code, "name": name, "budget": budget,
                                    "spent_before_golive": spent})
    vh = insert(conn, "plans", {"fund_code": "VH", "year": 2026, "version": 1, "resolution_no": "01/2026/NQ-HNNCC",
                                "resolution_date": "2026-03-20", "effective_from": "2026-03-20"})
    for code, name, budget, spent in (
        ("VH-01", "Phí quản lý vận hành", 1_800_000_000, 1_350_000_000),
        ("VH-02", "Vệ sinh khu vực chung", 600_000_000, 450_000_000),
        ("VH-03", "An ninh, bảo vệ", 900_000_000, 675_000_000),
    ):
        insert(conn, "plan_items", {"plan_id": vh, "code": code, "name": name, "budget": budget,
                                    "spent_before_golive": spent})

    v = {}
    for key, name, tax, bank, acc in (
        ("thangmay", "Công ty TNHH Thang máy Phương Nam", "0312345678", "Vietcombank", "0071000111222"),
        ("pccc", "Công ty CP PCCC An Toàn", "0309876543", "Techcombank", "19035555666012"),
        ("nuoc", "Công ty TNHH Kỹ thuật Nước Sài Gòn", "0315556667", "ACB", "88812345"),
        ("son", "Công ty TNHH Sơn Việt", "0316667778", "Sacombank", "060112233445"),
        ("qlvh", "Công ty CP Skyline Services (BQL)", "0301112223", "BIDV", "31410001112223"),
    ):
        v[key] = insert(conn, "vendors", {"name": name, "tax_code": tax, "bank_name": bank, "bank_account": acc})
    ids["vendors"] = v
    c = {}
    c["thangmay"] = insert(conn, "contracts", {"vendor_id": v["thangmay"], "fund_code": "BT", "contract_no": "HĐ-TM-01/2026",
                                               "title": "Bảo trì thang máy năm 2026", "value": 480_000_000,
                                               "signed_date": "2026-01-10", "beneficiary_account": "0071000111222",
                                               "paid_before_golive": 240_000_000})
    c["pccc"] = insert(conn, "contracts", {"vendor_id": v["pccc"], "fund_code": "BT", "contract_no": "HĐ-PCCC-02/2026",
                                           "title": "Bảo trì hệ thống PCCC năm 2026", "value": 360_000_000,
                                           "signed_date": "2026-02-15", "beneficiary_account": "19035555666012",
                                           "advance_pct": 30, "paid_before_golive": 240_000_000})
    c["nuoc"] = insert(conn, "contracts", {"vendor_id": v["nuoc"], "fund_code": "BT", "contract_no": "HĐ-DX-03/2026",
                                           "title": "Thay bơm cấp nước sinh hoạt bị hỏng (đột xuất)", "value": 85_000_000,
                                           "signed_date": "2026-11-03", "beneficiary_account": "88812345"})
    c["son"] = insert(conn, "contracts", {"vendor_id": v["son"], "fund_code": "BT", "contract_no": "HĐ-SON-04/2026",
                                          "title": "Chống thấm, sơn mái khối A", "value": 1_150_000_000,
                                          "signed_date": "2026-10-20", "beneficiary_account": "060112233445",
                                          "advance_pct": 20})
    c["qlvh"] = insert(conn, "contracts", {"vendor_id": v["qlvh"], "fund_code": "VH", "contract_no": "HĐ-QLVH-2025",
                                           "title": "Dịch vụ quản lý vận hành 2025–2026", "value": 3_600_000_000,
                                           "signed_date": "2025-01-01", "beneficiary_account": "31410001112223",
                                           "paid_before_golive": 3_150_000_000, "is_mgmt_contract": 1,
                                           "kpi_threshold": 80})
    ids["contracts"] = c
    inst = {}
    for i in range(1, 5):
        inst[f"tm{i}"] = insert(conn, "contract_installments", {"contract_id": c["thangmay"], "seq": i,
                                                                "name": f"Quý {i}/2026", "amount": 120_000_000})
    for i in range(1, 4):
        inst[f"pc{i}"] = insert(conn, "contract_installments", {"contract_id": c["pccc"], "seq": i,
                                                                "name": f"Đợt {i}", "amount": 120_000_000})
    ids["inst"] = inst
    insert(conn, "conflicts", {"user_id": ids["tv_em"], "vendor_id": v["son"], "note": "Em ruột là cổ đông",
                               "declared_at": "2026-10-01"})
    for month, name in (("2026-08", 86), ("2026-09", 82)):
        insert(conn, "kpi_scores", {"month": month, "self_score": name + 4, "bqt_score": name})
    insert(conn, "kpi_scores", {"month": "2026-10", "self_score": 85, "bqt_score": 78,
                                "note": "Vệ sinh tầng hầm không đạt 3 lần kiểm tra"})
    # Lịch sử chi 12 tháng (rút gọn)
    for row in (
        ("BT", "Công ty TNHH Thang máy Phương Nam", "0312345678", "BT-01", 120_000_000, "2026-04-05", "0000812", "bt-thang-may-quy", 120_000_000),
        ("BT", "Công ty TNHH Thang máy Phương Nam", "0312345678", "BT-01", 120_000_000, "2026-07-06", "0001021", "bt-thang-may-quy", 120_000_000),
        ("BT", "Công ty CP PCCC An Toàn", "0309876543", "BT-02", 120_000_000, "2026-03-10", "0000345", None, None),
        ("BT", "Công ty CP PCCC An Toàn", "0309876543", "BT-02", 120_000_000, "2026-06-12", "0000590", None, None),
        ("BT", "Công ty TNHH Kỹ thuật Nước Sài Gòn", "0315556667", "BT-05", 45_000_000, "2026-02-18", "0000077", None, None),
        ("BT", "Công ty TNHH Kỹ thuật Nước Sài Gòn", "0315556667", "BT-05", 45_000_000, "2026-08-20", "0000143", None, None),
        ("BT", "Công ty TNHH Máy phát Đông Á", "0317778889", "BT-04", 9_000_000, "2026-05-02", "0000210", None, None),
        ("BT", "Công ty TNHH Máy phát Đông Á", "0317778889", "BT-04", 9_500_000, "2026-05-16", "0000231", None, None),
        ("BT", "Công ty TNHH Máy phát Đông Á", "0317778889", "BT-04", 8_000_000, "2026-05-28", "0000250", None, None),
    ):
        insert(conn, "history_payments", dict(zip(("fund_code", "vendor_name", "vendor_tax_code", "plan_item_code",
                                                   "amount", "pay_date", "invoice_no", "service_key", "unit_price"), row)))
    insert(conn, "golive_signoff", {"user_id": ids["thuky"], "signed_at": "2026-10-01 09:00:00",
                                    "note": "Đối chiếu số dư với xác nhận ngân hàng"})
    insert(conn, "golive_signoff", {"user_id": ids["phoban"], "signed_at": "2026-10-01 10:00:00",
                                    "note": "Đối chiếu độc lập"})
    audit.log(conn, ids["quantri"], "Khởi tạo dữ liệu F-00", "system", None)
    conn.commit()
    return ids


def user(conn, username):
    return dict(q1(conn, "SELECT * FROM users WHERE username = ?", (username,)))


def seed_demo_flow(conn, ids) -> None:
    bql, thuky = user(conn, "bql"), user(conn, "thuky")
    tb, pb, cuong = user(conn, "truongban"), user(conn, "phoban"), user(conn, "tv_cuong")
    v, c, inst = ids["vendors"], ids["contracts"], ids["inst"]

    def docs(sub_id, items):
        for doc_type, label, meta in items:
            wf.add_document(conn, bql, sub_id, doc_type, f"{label}.pdf", pdf(label), meta)

    # 1) Thang máy quý 3: đi hết luồng tới Đóng
    set_day(conn, "2026-10-05")
    s1 = wf.create_submission(conn, bql, {"fund_code": "BT", "plan_item_code": "BT-01", "cost_type": "bao_tri_thiet_bi",
                                          "vendor_id": v["thangmay"], "contract_id": c["thangmay"], "installment_id": inst["tm3"],
                                          "amount": 120_000_000, "payment_method": "chuyen_khoan",
                                          "beneficiary_account": "0071000111222", "service_key": "bt-thang-may-quy",
                                          "unit_price": 120_000_000,
                                          "reason": "Thanh toán bảo trì thang máy quý 3/2026 theo HĐ-TM-01/2026"})
    docs(s1["id"], [("to_trinh", "to-trinh-thang-may-q3", {}), ("hop_dong", "hd-thang-may", {}),
                    ("bao_gia", "bao-gia-phuong-nam", {"amount": 120_000_000}),
                    ("bao_gia", "bao-gia-thang-may-a", {"amount": 128_000_000}),
                    ("bao_gia", "bao-gia-thang-may-b", {"amount": 131_000_000}),
                    ("nghiem_thu", "nghiem-thu-q3", {"signed_by_bqt": 1}),
                    ("hoa_don", "hoa-don-0001234", {"invoice_no": "0001234", "seller_tax_code": "0312345678",
                                                   "amount": 120_000_000, "doc_date": "2026-10-03"}),
                    ("tra_cuu_mst", "tra-cuu-mst-phuong-nam", {"tax_status": "hoat_dong"})])
    wf.submit(conn, bql, s1["id"])
    wf.open_vote(conn, tb, s1["id"])
    for u in (tb, pb, cuong):
        wf.cast_vote(conn, u, s1["id"], "dong_y")
    set_day(conn, "2026-10-06")
    for t, label in (("de_nghi_ky", "de-nghi-chuyen-tien-da-ky"), ("bien_ban_hop_ky", "bien-ban-hop-da-ky")):
        wf.add_document(conn, thuky, s1["id"], t, f"{label}.pdf", pdf(label))
    wf.verify_signed_docs(conn, pb, s1["id"])
    wf.check_ready(conn, thuky, s1["id"])
    set_day(conn, "2026-10-07")
    wf.confirm_sign(conn, tb, s1["id"], "FT26100700123", 120_000_000, "unc-tt-2026-001.pdf", pdf("unc"))
    conn.commit()

    # Sao kê tháng 10 quỹ bảo trì
    set_day(conn, "2026-11-03")
    csv_bytes = reconcile.build_statement_csv("0071000888999", "2026-10-01", "2026-10-31", 12_500_000_000, [
        ("2026-10-08", "FT26100800456", "TT-2026-001 Thanh toan bao tri thang may Q3", "0071000111222", -120_000_000),
        ("2026-10-15", "SMS2610", "Phi dich vu SMS Banking T10", "", -11_000),
        ("2026-10-20", "FT26102000789", "CK den TK 0123456789 NGUYEN VAN X", "0123456789", -15_000_000),
        ("2026-10-25", "INT2610", "Lai tien gui khong ky han T10", "", 3_250_000),
        ("2026-10-31", "FEE2610", "Phi quan ly tai khoan T10", "", -22_000),
    ])
    reconcile.import_statement(conn, thuky, "BT", "saoke-BT-2026-10.csv", csv_bytes)
    txns = {r["bank_ref"]: r["id"] for r in conn.execute("SELECT id, bank_ref FROM statement_txns")}
    reconcile.classify(conn, thuky, txns["SMS2610"], "phi_ngan_hang")
    reconcile.approve_classification(conn, tb, txns["SMS2610"])
    reconcile.classify(conn, thuky, txns["INT2610"], "lai")
    reconcile.classify(conn, thuky, txns["FEE2610"], "phi_ngan_hang")
    wf.close(conn, thuky, s1["id"])
    conn.commit()

    # 2) PCCC đợt 3: đang chờ biểu quyết
    set_day(conn, "2026-11-04")
    s2 = wf.create_submission(conn, bql, {"fund_code": "BT", "plan_item_code": "BT-02", "cost_type": "pccc",
                                          "vendor_id": v["pccc"], "contract_id": c["pccc"], "installment_id": inst["pc3"],
                                          "amount": 120_000_000, "payment_method": "chuyen_khoan",
                                          "beneficiary_account": "19035555666012",
                                          "reason": "Thanh toán đợt 3 bảo trì PCCC theo HĐ-PCCC-02/2026"})
    docs(s2["id"], [("to_trinh", "to-trinh-pccc-dot3", {}), ("hop_dong", "hd-pccc", {}),
                    ("bao_gia", "bao-gia-pccc-1", {"amount": 120_000_000}),
                    ("bao_gia", "bao-gia-pccc-2", {"amount": 125_000_000}),
                    ("bao_gia", "bao-gia-pccc-3", {"amount": 133_000_000}),
                    ("nghiem_thu", "nghiem-thu-pccc-dot3", {"signed_by_supervisor": 1}),
                    ("hoa_don", "hoa-don-0000871", {"invoice_no": "0000871", "seller_tax_code": "0309876543",
                                                   "amount": 120_000_000, "doc_date": "2026-11-02"}),
                    ("tra_cuu_mst", "tra-cuu-mst-pccc", {"tax_status": "hoat_dong"})])
    wf.submit(conn, bql, s2["id"])
    wf.open_vote(conn, pb, s2["id"])
    wf.cast_vote(conn, tb, s2["id"], "dong_y", "Đã kiểm tra hiện trường")
    wf.cast_vote(conn, cuong, s2["id"], "dong_y")
    conn.commit()

    # 3) Bơm nước hỏng – đột xuất, chờ BQT xác nhận tính đột xuất
    set_day(conn, "2026-11-06")
    s3 = wf.create_submission(conn, bql, {"fund_code": "BT", "is_emergency": 1, "plan_item_code": "BT-05",
                                          "cost_type": "bao_tri_thiet_bi", "vendor_id": v["nuoc"], "contract_id": c["nuoc"],
                                          "amount": 85_000_000, "payment_method": "chuyen_khoan",
                                          "beneficiary_account": "88812345",
                                          "reason": "Thay bơm cấp nước sinh hoạt số 2 bị cháy motor ngày 02/11"})
    docs(s3["id"], [("to_trinh", "to-trinh-bom-nuoc", {}), ("hop_dong", "hd-dx-bom", {"contract_signed": 1}),
                    ("nghiem_thu", "nghiem-thu-bom", {"signed_by_supervisor": 1}),
                    ("hoa_don", "hoa-don-0000199", {"invoice_no": "0000199", "seller_tax_code": "0315556667",
                                                   "amount": 85_000_000, "doc_date": "2026-11-05"}),
                    ("tra_cuu_mst", "tra-cuu-mst-nuoc", {"tax_status": "hoat_dong"})])
    wf.submit(conn, bql, s3["id"])

    # 4) Phí QLVH tháng 10 – quỹ vận hành, KPI dưới ngưỡng (R-15)
    s4 = wf.create_submission(conn, bql, {"fund_code": "VH", "plan_item_code": "VH-01", "cost_type": "phi_qlvh",
                                          "vendor_id": v["qlvh"], "contract_id": c["qlvh"], "amount": 150_000_000,
                                          "payment_method": "chuyen_khoan", "beneficiary_account": "31410001112223",
                                          "is_mgmt_fee": 1, "kpi_month": "2026-10",
                                          "reason": "Phí dịch vụ quản lý vận hành tháng 10/2026"})
    docs(s4["id"], [("to_trinh", "to-trinh-phi-qlvh-t10", {}), ("hop_dong", "hd-qlvh", {}),
                    ("bao_gia", "phu-luc-don-gia-qlvh", {"amount": 150_000_000}),
                    ("nghiem_thu", "bien-ban-nghiem-thu-dich-vu-t10", {"signed_by_bqt": 1}),
                    ("hoa_don", "hoa-don-0002210", {"invoice_no": "0002210", "seller_tax_code": "0301112223",
                                                   "amount": 150_000_000, "doc_date": "2026-11-01"}),
                    ("kpi", "bao-cao-kpi-t10", {}), ("tra_cuu_mst", "tra-cuu-mst-qlvh", {"tax_status": "hoat_dong"})])
    wf.submit(conn, bql, s4["id"])

    # 5) Chống thấm mái – nháp, còn thiếu hóa đơn; nhà cung cấp có liên quan tới 1 thành viên BQT
    set_day(conn, "2026-11-07")
    s5 = wf.create_submission(conn, bql, {"fund_code": "BT", "plan_item_code": "BT-03", "cost_type": "ket_cau",
                                          "vendor_id": v["son"], "contract_id": c["son"], "amount": 230_000_000,
                                          "payment_method": "chuyen_khoan", "beneficiary_account": "060112233445",
                                          "is_advance": 1, "reason": "Tạm ứng 20% hợp đồng chống thấm mái khối A"})
    docs(s5["id"], [("to_trinh", "to-trinh-chong-tham", {}), ("hop_dong", "hd-son", {}),
                    ("bao_gia", "bao-gia-son-viet", {"amount": 1_150_000_000})])
    conn.commit()


def build(path: str | None = None, demo=True):
    path = path or db_path()
    if path != ":memory:" and os.path.exists(path):
        os.remove(path)
    conn = connect(path)
    init_db(conn)
    ids = seed_catalog(conn)
    if demo:
        seed_demo_flow(conn, ids)
    set_day(conn, "2026-11-07")
    conn.commit()
    return conn


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Đã tạo dữ liệu demo tại {db_path()} – mật khẩu chung: {DEMO_PASSWORD}")
