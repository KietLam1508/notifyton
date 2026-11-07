"""Kịch bản UAT TC-01 → TC-33 (Phụ lục B của PRD v0.2), chạy tự động.

Mỗi test ghi rõ mã kịch bản để đội QC đối chiếu với buổi nghiệm thu thủ công.
"""
import io
import sqlite3

import pytest
from docx import Document

from app import audit, config_changes, docgen, jobs, reconcile, reports, rules
from app import settings as S
from app import workflow as wf
from app.db import insert, q, q1
from app.seed import set_day, user

PDF = b"%PDF-1.4 test"
BQT = ("truongban", "phoban", "tv_cuong", "tv_dung", "tv_em")


def U(conn, name):
    return user(conn, name)


def make_sub(conn, docs=True, **over):
    """Tờ trình mặc định: thang máy quý 3, quỹ bảo trì, trong kế hoạch, 120 triệu, đủ hồ sơ."""
    ids = conn.ids
    data = {"fund_code": "BT", "plan_item_code": "BT-01", "cost_type": "bao_tri_thiet_bi",
            "vendor_id": ids["vendors"]["thangmay"], "contract_id": ids["contracts"]["thangmay"],
            "installment_id": ids["inst"]["tm3"], "amount": 120_000_000, "payment_method": "chuyen_khoan",
            "beneficiary_account": "0071000111222", "reason": "Bảo trì thang máy quý 3"}
    doc_over = over.pop("doc_over", {})
    skip = over.pop("skip_docs", ())
    data.update(over)
    sub = wf.create_submission(conn, U(conn, "bql"), data)
    if docs:
        vendor = q1(conn, "SELECT * FROM vendors WHERE id = ?", (data["vendor_id"],))
        n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        items = {
            "to_trinh": [{}], "hop_dong": [{"contract_signed": 1}],
            "bao_gia": [{"amount": data["amount"]}, {"amount": data["amount"] + 5_000_000},
                        {"amount": data["amount"] + 9_000_000}],
            "nghiem_thu": [{"signed_by_bqt": 1}],
            "hoa_don": [{"invoice_no": f"INV{n:05d}", "seller_tax_code": vendor["tax_code"], "amount": data["amount"],
                         "doc_date": "2026-11-01"}],
            "tra_cuu_mst": [{"tax_status": "hoat_dong"}],
        }
        for t, metas in items.items():
            if t in skip:
                continue
            for m in metas:
                wf.add_document(conn, U(conn, "bql"), sub["id"], t, f"{t}.pdf", PDF, {**m, **doc_over.get(t, {})})
    return wf.get_sub(conn, sub["id"])


def approve(conn, sid, voters=("truongban", "phoban", "tv_cuong")):
    wf.open_vote(conn, U(conn, "truongban"), sid)
    for v in voters:
        wf.cast_vote(conn, U(conn, v), sid, "dong_y")
    return wf.get_sub(conn, sid)


def make_ready(conn, sid):
    for t in ("de_nghi_ky", "bien_ban_hop_ky"):
        wf.add_document(conn, U(conn, "thuky"), sid, t, f"{t}.pdf", PDF)
    wf.verify_signed_docs(conn, U(conn, "phoban"), sid)
    return wf.check_ready(conn, U(conn, "thuky"), sid)


def sign(conn, sid):
    sub = wf.get_sub(conn, sid)
    return wf.confirm_sign(conn, U(conn, "truongban"), sid, "FT123", sub["amount"], "unc.pdf", PDF)


def alert_ids(conn, sid, status=("open", "accepted")):
    return {a["rule_id"] for a in rules.active_alerts(conn, sid) if a["status"] in status}


def submit_blocked(conn, sid):
    with pytest.raises(wf.WorkflowError) as e:
        wf.submit(conn, U(conn, "bql"), sid)
    return " | ".join(e.value.details)


def statement(conn, txns, frm="2026-10-01", to="2026-11-30", opening=12_500_000_000, fund="BT"):
    acc = q1(conn, "SELECT account_no FROM funds WHERE code = ?", (fund,))["account_no"]
    content = reconcile.build_statement_csv(acc, frm, to, opening, txns)
    return reconcile.import_statement(conn, U(conn, "thuky"), fund, "saoke.csv", content)


# ---------------------------------------------------------------------------------------------

def test_tc01_full_happy_path(conn):
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    assert wf.get_sub(conn, sub["id"])["status"] == "da_nop"
    assert not [a for a in rules.active_alerts(conn, sub["id"]) if a["severity"] in ("chan", "cao")]
    assert approve(conn, sub["id"])["status"] == "da_duyet"
    assert make_ready(conn, sub["id"])["status"] == "san_sang_ky"
    assert sign(conn, sub["id"])["status"] == "da_ky"
    assert sub["code"] == "TT-2026-001"


def test_tc02_missing_invoice(conn):
    sub = make_sub(conn, skip_docs=("hoa_don",))
    details = submit_blocked(conn, sub["id"])
    assert "Thiếu Hóa đơn VAT" in details
    s = wf.get_sub(conn, sub["id"])
    assert s["status"] == "yeu_cau_bo_sung" and s["submitted_at"] is None


def test_tc03_operational_cost_from_maintenance_fund(conn):
    sub = make_sub(conn, cost_type="luong_bao_ve", reason="Chi lương bảo vệ")
    assert "R-01" in submit_blocked(conn, sub["id"])


def test_tc04_item_not_in_plan(conn):
    sub = make_sub(conn, plan_item_code="")
    details = submit_blocked(conn, sub["id"])
    assert "R-02" in details and "trình Hội nghị bổ sung kế hoạch" in details


def test_tc05_emergency_full_flow(conn):
    set_day(conn, "2026-11-04")
    ids = conn.ids
    sub = make_sub(conn, is_emergency=1, plan_item_code="BT-05", vendor_id=ids["vendors"]["nuoc"],
                   contract_id=ids["contracts"]["nuoc"], installment_id=None, amount=85_000_000,
                   beneficiary_account="88812345", skip_docs=("bao_gia",), reason="Bơm nước hỏng",
                   doc_over={"hoa_don": {"doc_date": "2026-11-04"}})
    wf.submit(conn, U(conn, "bql"), sub["id"])
    wf.confirm_emergency(conn, U(conn, "tv_cuong"), sub["id"], "bao_tri_thiet_bi", "Motor cháy 02/11, mất nước 3 tầng")
    approve(conn, sub["id"])
    plan_doc = Document(io.BytesIO(docgen.build_plan_extract(conn, sub["id"])))
    text = "\n".join(p.text for p in plan_doc.paragraphs)
    assert "HỢP ĐỒNG BẢO TRÌ ĐỘT XUẤT" in text and "HĐ-DX-03/2026" in text
    make_ready(conn, sub["id"])
    assert sign(conn, sub["id"])["status"] == "da_ky"
    assert sub["code"] in [s["code"] for s in reports.emergency_pending(conn)]
    jobs.r16_jobs(conn)
    assert q1(conn, "SELECT 1 FROM alerts WHERE rule_id = 'R-16' AND message LIKE ?", (f"%{sub['code']}%",))


def test_tc06_emergency_not_confirmed(conn):
    set_day(conn, "2026-11-04")
    ids = conn.ids
    sub = make_sub(conn, is_emergency=1, plan_item_code="BT-05", vendor_id=ids["vendors"]["nuoc"],
                   contract_id=ids["contracts"]["nuoc"], installment_id=None, amount=85_000_000,
                   beneficiary_account="88812345", skip_docs=("bao_gia",))
    wf.submit(conn, U(conn, "bql"), sub["id"])
    with pytest.raises(wf.WorkflowError) as e:
        wf.open_vote(conn, U(conn, "truongban"), sub["id"])
    assert "R-25" in " ".join(e.value.details)
    assert wf.get_sub(conn, sub["id"])["status"] == "da_nop"


def test_tc07_beneficiary_account_mismatch_cp1_and_cp3(conn):
    bad = make_sub(conn, beneficiary_account="9999999999")
    assert "R-05" in submit_blocked(conn, bad["id"])
    wf.cancel(conn, U(conn, "bql"), bad["id"], "nhập sai")
    good = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), good["id"])
    approve(conn, good["id"])
    # Tài khoản hợp đồng đổi sau khi duyệt (qua quy trình cấu hình) → CP3 phải chặn lại
    cid = config_changes.propose(conn, U(conn, "quantri"), "contract_account",
                                 {"contract_id": conn.ids["contracts"]["thangmay"], "beneficiary_account": "0071000999000"},
                                 "NCC đổi ngân hàng")
    config_changes.decide(conn, U(conn, "tv_cuong"), cid, "approve")
    with pytest.raises(wf.WorkflowError):
        make_ready(conn, good["id"])
    assert "R-05" in {a["rule_id"] for a in rules.active_alerts(conn, good["id"], "CP3")}


def test_tc08_invoice_already_paid(conn):
    # Trùng hóa đơn trong lịch sử trước go-live (F-00)
    sub = make_sub(conn, doc_over={"hoa_don": {"invoice_no": "0001021"}})
    assert "R-18" in submit_blocked(conn, sub["id"])
    wf.cancel(conn, U(conn, "bql"), sub["id"], "trùng hóa đơn")  # nếu không hủy, R-09 sẽ tính cả tờ trình này
    # Trùng hóa đơn với tờ trình đã thanh toán trong công cụ
    a = make_sub(conn, doc_over={"hoa_don": {"invoice_no": "0009999"}})
    wf.submit(conn, U(conn, "bql"), a["id"])
    approve(conn, a["id"])
    make_ready(conn, a["id"])
    sign(conn, a["id"])
    b = make_sub(conn, installment_id=conn.ids["inst"]["tm4"], doc_over={"hoa_don": {"invoice_no": "0009999"}})
    details = submit_blocked(conn, b["id"])
    assert "R-18" in details and a["code"] in details


def test_tc09_installments_exceed_contract_value(conn):
    ids = conn.ids
    sub = make_sub(conn, plan_item_code="BT-02", cost_type="pccc", vendor_id=ids["vendors"]["pccc"],
                   contract_id=ids["contracts"]["pccc"], installment_id=ids["inst"]["pc3"], amount=130_000_000,
                   beneficiary_account="19035555666012")
    details = submit_blocked(conn, sub["id"])
    assert "R-19" in details and "vượt giá trị hợp đồng" in details


def test_tc10_split_payments_high_alert_needs_reason_and_holder(conn):
    subs = []
    for i, day in enumerate(("2026-11-02", "2026-11-09", "2026-11-20")):
        set_day(conn, day)
        s = make_sub(conn, amount=8_000_000, reason=f"Sửa chữa nhỏ {i}")
        wf.submit(conn, U(conn, "bql"), s["id"])
        subs.append(s)
    assert "R-09" not in alert_ids(conn, subs[1]["id"])
    third = subs[2]["id"]
    assert "R-09" in alert_ids(conn, third)
    alert = next(a for a in rules.active_alerts(conn, third) if a["rule_id"] == "R-09")
    with pytest.raises(wf.WorkflowError):
        wf.open_vote(conn, U(conn, "truongban"), third)
    wf.accept_alert(conn, U(conn, "tv_cuong"), alert["id"], "Ba sự cố khác nhau, có biên bản riêng")
    with pytest.raises(wf.WorkflowError):  # chưa có chủ TK xác nhận
        wf.open_vote(conn, U(conn, "truongban"), third)
    with pytest.raises(wf.WorkflowError):  # thành viên thường không xác nhận thay chủ TK
        wf.confirm_alert(conn, U(conn, "tv_dung"), alert["id"])
    wf.confirm_alert(conn, U(conn, "phoban"), alert["id"])
    wf.open_vote(conn, U(conn, "truongban"), third)
    assert wf.get_sub(conn, third)["status"] == "cho_bieu_quyet"


def test_tc11_conflict_of_interest_excluded_from_vote(conn):
    ids = conn.ids
    sub = make_sub(conn, plan_item_code="BT-03", cost_type="ket_cau", vendor_id=ids["vendors"]["son"],
                   contract_id=ids["contracts"]["son"], installment_id=None, amount=100_000_000,
                   beneficiary_account="060112233445")
    wf.submit(conn, U(conn, "bql"), sub["id"])
    r12 = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-12")
    assert r12["severity"] == "cao"
    wf.accept_alert(conn, U(conn, "truongban"), r12["id"], "Đã đấu thầu công khai, người liên quan không tham gia")
    wf.open_vote(conn, U(conn, "truongban"), sub["id"])
    t = wf.tally(conn, wf.get_sub(conn, sub["id"]))
    assert len(t["eligible"]) == 4 and t["needed"] == 3
    with pytest.raises(wf.WorkflowError):
        wf.cast_vote(conn, U(conn, "tv_em"), sub["id"], "dong_y")
    for v in ("truongban", "phoban"):
        wf.cast_vote(conn, U(conn, v), sub["id"], "dong_y")
    assert wf.get_sub(conn, sub["id"])["status"] == "cho_bieu_quyet"
    wf.cast_vote(conn, U(conn, "tv_cuong"), sub["id"], "dong_y")
    assert wf.get_sub(conn, sub["id"])["status"] == "da_duyet"


def test_tc12_vote_reminder_and_deadline(conn):
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    wf.open_vote(conn, U(conn, "truongban"), sub["id"])  # thứ Hai 02/11 → hạn 05/11
    assert wf.get_sub(conn, sub["id"])["vote_deadline"] == "2026-11-05"
    for v in ("truongban", "phoban"):
        wf.cast_vote(conn, U(conn, v), sub["id"], "dong_y")
    set_day(conn, "2026-11-03")
    jobs.run_daily(conn)
    reminded = {r["user_id"] for r in q(conn, "SELECT user_id FROM notifications WHERE title LIKE 'Nhắc biểu quyết%'")}
    assert reminded == {U(conn, n)["id"] for n in ("tv_cuong", "tv_dung", "tv_em")}
    set_day(conn, "2026-11-05")
    jobs.run_daily(conn)
    assert wf.get_sub(conn, sub["id"])["status"] == "cho_bieu_quyet"  # còn trong hạn
    set_day(conn, "2026-11-06")
    jobs.run_daily(conn)
    assert wf.get_sub(conn, sub["id"])["status"] == "can_hop"


def test_tc13_rejection_bql_sees_only_common_reason(conn):
    from fastapi.testclient import TestClient
    from app.main import app
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    wf.open_vote(conn, U(conn, "truongban"), sub["id"])
    for v in ("truongban", "phoban", "tv_cuong"):
        wf.cast_vote(conn, U(conn, v), sub["id"], "khong_dong_y", f"Ý KIẾN RIÊNG CỦA {v.upper()}")
    wf.reject(conn, U(conn, "truongban"), sub["id"], "Thiếu ảnh hiện trường trước/sau bảo trì")
    conn.commit()
    c = TestClient(app)
    c.post("/dang-nhap", data={"username": "bql", "password": "skyline123"})
    html = c.get(f"/to-trinh/{sub['id']}").text
    assert "Thiếu ảnh hiện trường trước/sau bảo trì" in html
    assert "Ý KIẾN RIÊNG" not in html and "Lịch sử phiếu" not in html
    note = q1(conn, "SELECT body FROM notifications WHERE user_id = ? AND title LIKE '%bị từ chối%'", (U(conn, "bql")["id"],))
    assert note["body"] == "Thiếu ảnh hiện trường trước/sau bảo trì"


def test_tc14_non_account_holder_cannot_confirm_sign(conn):
    from fastapi.testclient import TestClient
    from app.main import app
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    approve(conn, sub["id"])
    make_ready(conn, sub["id"])
    conn.commit()
    c = TestClient(app)
    c.post("/dang-nhap", data={"username": "tv_cuong", "password": "skyline123"})
    assert "Xác nhận đã ký UNC" not in c.get(f"/to-trinh/{sub['id']}").text
    c.post("/dang-nhap", data={"username": "truongban", "password": "skyline123"})
    assert "Xác nhận đã ký UNC" in c.get(f"/to-trinh/{sub['id']}").text
    with pytest.raises(wf.WorkflowError) as e:
        wf.confirm_sign(conn, U(conn, "tv_cuong"), sub["id"], "FT1", sub["amount"], "unc.pdf", PDF)
    assert "R-06" in str(e.value)


def test_tc15_missing_signed_minutes_blocks_cp3(conn):
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    approve(conn, sub["id"])
    wf.add_document(conn, U(conn, "thuky"), sub["id"], "de_nghi_ky", "dn.pdf", PDF)
    with pytest.raises(wf.WorkflowError) as e:
        wf.check_ready(conn, U(conn, "thuky"), sub["id"])
    assert any("R-04" in d and "Biên bản họp" in d for d in e.value.details)


def _signed(conn, **over):
    sub = make_sub(conn, **over)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    approve(conn, sub["id"])
    make_ready(conn, sub["id"])
    sign(conn, sub["id"])
    return wf.get_sub(conn, sub["id"])


def test_tc16_statement_auto_match_by_code(conn):
    sub = _signed(conn)
    set_day(conn, "2026-12-02")
    statement(conn, [("2026-11-03", "FT1", f"{sub['code'].replace('-', '')} thanh toan bao tri", "0071000111222", -120_000_000)])
    assert wf.get_sub(conn, sub["id"])["status"] == "da_doi_soat"
    t = q1(conn, "SELECT * FROM statement_txns")
    assert t["match_status"] == "da_khop" and t["match_method"] == "ma_to_trinh"


def test_tc17_paid_before_ready_r21(conn):
    sub = make_sub(conn)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    approve(conn, sub["id"])
    set_day(conn, "2026-11-05")
    make_ready(conn, sub["id"])
    sign(conn, sub["id"])
    set_day(conn, "2026-12-02")
    statement(conn, [("2026-11-03", "FT1", f"{sub['code']} tra truoc", "0071000111222", -120_000_000)])
    r21 = q1(conn, "SELECT * FROM alerts WHERE rule_id = 'R-21'")
    assert r21 and r21["severity"] == "cao" and "chi trước, duyệt sau" in r21["message"]
    notified = {r["user_id"] for r in q(conn, "SELECT user_id FROM notifications WHERE title LIKE 'R-21%'")}
    assert notified == {U(conn, n)["id"] for n in BQT}


def test_tc18_bank_fee_and_interest_classified(conn):
    set_day(conn, "2026-12-01")
    statement(conn, [("2026-10-15", "SMS", "Phi SMS Banking", "", -11_000),
                     ("2026-10-25", "INT", "Lai tien gui", "", 3_250_000)])
    for t in q(conn, "SELECT * FROM statement_txns"):
        cat = "phi_ngan_hang" if t["amount"] < 0 else "lai"
        reconcile.classify(conn, U(conn, "thuky"), t["id"], cat)
        with pytest.raises(wf.WorkflowError):  # thư ký không tự duyệt
            reconcile.approve_classification(conn, U(conn, "thuky"), t["id"])
        reconcile.approve_classification(conn, U(conn, "truongban"), t["id"])
    set_day(conn, "2026-12-15")
    assert reconcile.check_r17(conn) == 0
    assert {r["match_status"] for r in q(conn, "SELECT match_status FROM statement_txns")} == {"da_phan_loai"}


def test_tc19_unexplained_transaction_after_5_business_days(conn):
    set_day(conn, "2026-12-01")  # thứ Ba
    statement(conn, [("2026-11-20", "FT9", "CK den TK la", "0123456789", -15_000_000)])
    set_day(conn, "2026-12-07")  # 4 ngày làm việc
    assert reconcile.check_r17(conn) == 0
    set_day(conn, "2026-12-08")  # 5 ngày làm việc
    assert reconcile.check_r17(conn) == 1
    a = q1(conn, "SELECT * FROM alerts WHERE rule_id = 'R-17'")
    assert a["severity"] == "cao"
    assert {r["user_id"] for r in q(conn, "SELECT user_id FROM notifications WHERE title LIKE 'R-17%'")} == \
        {U(conn, n)["id"] for n in BQT}


def test_tc20_signed_but_no_transaction_r22(conn):
    sub = _signed(conn)  # ký thứ Hai 02/11; hạn chuyển tiền = 05/11
    set_day(conn, "2026-11-06")  # 4 ngày làm việc sau
    statement(conn, [], to="2026-11-06")
    a = q1(conn, "SELECT * FROM alerts WHERE rule_id = 'R-22' AND submission_id = ?", (sub["id"],))
    assert a and a["severity"] == "tb"


def test_tc21_statement_discontinuous_rejected(conn):
    set_day(conn, "2026-11-03")
    statement(conn, [("2026-10-10", "A", "Phi", "", -10_000)], to="2026-10-31")
    with pytest.raises(wf.WorkflowError) as e:
        statement(conn, [], frm="2026-11-01", opening=12_000_000_000)
    assert any("Số dư đầu kỳ" in d for d in e.value.details)
    assert q1(conn, "SELECT 1 FROM statement_rejections")
    # File bị sửa số dư giữa chừng
    acc = q1(conn, "SELECT account_no FROM funds WHERE code = 'BT'")["account_no"]
    good = reconcile.build_statement_csv(acc, "2026-11-01", "2026-11-30", 12_499_990_000,
                                         [("2026-11-05", "B", "Phi", "", -10_000)])
    tampered = good.replace(b",10000,0,12499980000", b",1000,0,12499980000")
    with pytest.raises(wf.WorkflowError):
        reconcile.import_statement(conn, U(conn, "thuky"), "BT", "sua.csv", tampered)
    with pytest.raises(wf.WorkflowError):  # không phải file xuất gốc
        reconcile.import_statement(conn, U(conn, "thuky"), "BT", "x.csv", b"Ngay,SoTien\n2026-11-01,1\n")


def test_tc22_maintenance_account_locked(conn):
    with pytest.raises(wf.WorkflowError) as e:
        config_changes.direct_fund_account_edit(conn, U(conn, "quantri"), "BT", "123")
    assert "R-24" in str(e.value)
    with pytest.raises(sqlite3.DatabaseError):  # chặn cả ở tầng cơ sở dữ liệu
        conn.execute("UPDATE funds SET account_no = '123' WHERE code = 'BT'")
    with pytest.raises(wf.WorkflowError):  # ngoại lệ phải có văn bản căn cứ
        config_changes.propose(conn, U(conn, "quantri"), "fund_account", {"fund_code": "BT", "account_no": "555"}, "x")
    cid = config_changes.propose(conn, U(conn, "quantri"), "fund_account", {"fund_code": "BT", "account_no": "555"},
                                 "Ngân hàng sáp nhập", attachment_path="/tmp/thong-bao.pdf")
    with pytest.raises(wf.WorkflowError):
        config_changes.decide(conn, U(conn, "tv_cuong"), cid, "approve")  # không phải chủ TK
    assert config_changes.decide(conn, U(conn, "truongban"), cid, "approve") == "pending"
    assert config_changes.decide(conn, U(conn, "phoban"), cid, "approve") == "approved"
    assert q1(conn, "SELECT account_no FROM funds WHERE code = 'BT'")["account_no"] == "555"


def test_tc23_threshold_change_needs_other_bqt_member(conn):
    with pytest.raises(wf.WorkflowError):  # chủ TK không được đề xuất cấu hình
        config_changes.propose(conn, U(conn, "truongban"), "setting", {"key": "r08_over_pct", "value": "30"}, "x")
    cid = config_changes.propose(conn, U(conn, "tv_cuong"), "setting", {"key": "r08_over_pct", "value": "30"}, "Nới ngưỡng")
    with pytest.raises(wf.WorkflowError):
        config_changes.decide(conn, U(conn, "tv_cuong"), cid, "approve")
    assert S.get(conn, "r08_over_pct") == "10"
    config_changes.decide(conn, U(conn, "tv_dung"), cid, "approve")
    assert S.get(conn, "r08_over_pct") == "30"
    assert q1(conn, "SELECT 1 FROM audit_log WHERE action LIKE 'Áp dụng ngưỡng r08_over_pct%'")
    with pytest.raises(wf.WorkflowError):  # rule [L] không tắt được
        config_changes.propose(conn, U(conn, "quantri"), "rule_toggle", {"rule_id": "R-01", "enabled": False}, "x")


def test_tc24_audit_log_immutable(conn):
    make_sub(conn)
    conn.commit()
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM audit_log WHERE id = 1")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("UPDATE audit_log SET action = 'x' WHERE id = 1")
    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM submissions")
    assert audit.verify_chain(conn) == (True, None)
    # Giả lập sửa file DB bên ngoài ứng dụng → chuỗi băm phát hiện
    conn.execute("DROP TRIGGER audit_no_update")
    conn.execute("UPDATE audit_log SET action = 'sửa lén' WHERE id = 2")
    assert audit.verify_chain(conn) == (False, 2)


def test_tc25_golive_midyear_cumulative_budget(conn):
    ids = conn.ids
    cid = insert(conn, "contracts", {"vendor_id": ids["vendors"]["pccc"], "fund_code": "BT", "contract_no": "HĐ-PCCC-PL",
                                     "title": "Mở rộng PCCC", "value": 300_000_000, "signed_date": "2026-10-10",
                                     "beneficiary_account": "19035555666012"})
    sub = make_sub(conn, plan_item_code="BT-02", cost_type="pccc", vendor_id=ids["vendors"]["pccc"], contract_id=cid,
                   installment_id=None, amount=210_000_000, beneficiary_account="19035555666012")
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-08")
    assert a["severity"] == "cao" and "115%" in a["message"] and "480.000.000" in a["message"]


def test_tc26_term_deposit_in_total_and_reminder(conn):
    set_day(conn, "2026-11-07")
    bt = next(f for f in reports.fund_summary(conn) if f["fund"]["code"] == "BT")
    assert bt["deposits"] == 5_000_000_000 and bt["total"] == 12_500_000_000 + 5_000_000_000
    jobs.r16_jobs(conn)
    assert q1(conn, "SELECT 1 FROM alerts WHERE rule_id = 'R-16' AND message LIKE '%2.000.000.000 đ%13/11/2026%'")


def test_tc27_cash_over_limit(conn):
    sub = make_sub(conn, amount=10_000_000, payment_method="tien_mat")
    assert "R-07" in submit_blocked(conn, sub["id"])


def test_tc28_payment_without_acceptance(conn):
    ids = conn.ids
    sub = make_sub(conn, fund_code="VH", plan_item_code="VH-02", cost_type="ve_sinh", vendor_id=ids["vendors"]["qlvh"],
                   contract_id=ids["contracts"]["qlvh"], installment_id=None, amount=30_000_000,
                   beneficiary_account="31410001112223", skip_docs=("nghiem_thu",))
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-10")
    assert a["severity"] == "cao"


def test_tc29_single_quote_above_threshold(conn):
    sub = make_sub(conn, skip_docs=("bao_gia",))
    wf.add_document(conn, U(conn, "bql"), sub["id"], "bao_gia", "bg.pdf", PDF, {"amount": 120_000_000})
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-11")
    assert a["severity"] == "cao" and "hiện có 1" in a["message"]


def test_tc30_acceptance_without_bqt_or_supervisor(conn):
    sub = make_sub(conn, doc_over={"nghiem_thu": {"signed_by_bqt": 0}})
    wf.submit(conn, U(conn, "bql"), sub["id"])
    assert "R-20" in alert_ids(conn, sub["id"])


def test_tc31_invoice_amount_mismatch(conn):
    sub = make_sub(conn, doc_over={"hoa_don": {"amount": 125_000_000}})
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-14")
    assert a["severity"] == "cao"


def test_tc32_inactive_tax_code(conn):
    sub = make_sub(conn, doc_over={"tra_cuu_mst": {"tax_status": "ngung_hoat_dong"}})
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-13")
    assert a["severity"] == "cao"


def test_tc33_management_fee_low_kpi(conn):
    ids = conn.ids
    sub = make_sub(conn, fund_code="VH", plan_item_code="VH-01", cost_type="phi_qlvh", vendor_id=ids["vendors"]["qlvh"],
                   contract_id=ids["contracts"]["qlvh"], installment_id=None, amount=150_000_000,
                   beneficiary_account="31410001112223", is_mgmt_fee=1, kpi_month="2026-10")
    wf.add_document(conn, U(conn, "bql"), sub["id"], "kpi", "kpi.pdf", PDF)
    wf.submit(conn, U(conn, "bql"), sub["id"])
    a = next(a for a in rules.active_alerts(conn, sub["id"]) if a["rule_id"] == "R-15")
    assert a["severity"] == "tb" and "78" in a["message"]
