"""Luồng đầu-cuối qua giao diện web (form thật), đúng thứ tự các vai trò bấm nút."""
from fastapi.testclient import TestClient

from app import reconcile
from app.db import q1
from app.main import app
from app.seed import set_day

PDF = ("doc.pdf", b"%PDF-1.4 web", "application/pdf")


def login(c, username):
    c.get("/dang-xuat")
    r = c.post("/dang-nhap", data={"username": username, "password": "skyline123"}, follow_redirects=False)
    assert r.status_code == 303


def ok(r):
    assert r.status_code == 200, r.text[-1500:]
    assert 'class="flash error"' not in r.text, r.text[r.text.find('flash error'):][:800]
    return r


def test_end_to_end_via_web(conn):
    ids = conn.ids
    conn.commit()
    c = TestClient(app)

    login(c, "bql")
    r = c.post("/to-trinh/moi", data={
        "fund_code": "BT", "plan_item_code": "BT-01", "cost_type": "bao_tri_thiet_bi",
        "vendor_id": ids["vendors"]["thangmay"], "contract_id": ids["contracts"]["thangmay"],
        "installment_id": ids["inst"]["tm3"], "amount": "120000000", "payment_method": "chuyen_khoan",
        "beneficiary_account": "0071000111222", "reason": "Bảo trì thang máy quý 3"})
    ok(r)
    sid = int(str(r.url).rstrip("/").split("/")[-1])
    # Nộp khi chưa có chứng từ → báo thiếu đúng tên hồ sơ
    r = c.post(f"/to-trinh/{sid}/nop")
    assert "Thiếu Hóa đơn VAT" in r.text
    docs = [("to_trinh", {}), ("hop_dong", {}), ("nghiem_thu", {"signed_by_bqt": "1"}),
            ("tra_cuu_mst", {"tax_status": "hoat_dong"}),
            ("hoa_don", {"invoice_no": "777", "seller_tax_code": "0312345678", "amount": "120000000", "doc_date": "2026-11-01"})]
    docs += [("bao_gia", {"amount": str(a)}) for a in (120_000_000, 125_000_000, 130_000_000)]
    for t, meta in docs:
        ok(c.post(f"/to-trinh/{sid}/chung-tu", data={"doc_type": t, **meta}, files={"file": PDF}))
    ok(c.post(f"/to-trinh/{sid}/nop"))

    login(c, "truongban")
    ok(c.post(f"/to-trinh/{sid}/mo-bieu-quyet"))
    for u in ("truongban", "phoban", "tv_cuong"):
        login(c, u)
        ok(c.post(f"/to-trinh/{sid}/bieu-quyet", data={"choice": "dong_y"}))

    login(c, "thuky")
    for kind in ("de-nghi-chuyen-tien", "bien-ban-hop", "trich-ke-hoach"):
        r = c.get(f"/to-trinh/{sid}/ho-so/{kind}.docx")
        assert r.status_code == 200 and r.content[:2] == b"PK"
    for t in ("de_nghi_ky", "bien_ban_hop_ky"):
        ok(c.post(f"/to-trinh/{sid}/chung-tu", data={"doc_type": t}, files={"file": PDF}))
    login(c, "phoban")
    ok(c.post(f"/to-trinh/{sid}/xac-minh-ban-ky"))
    ok(c.post(f"/to-trinh/{sid}/kiem-tra-cp3"))

    login(c, "truongban")
    r = ok(c.get(f"/to-trinh/{sid}"))
    assert "Xác nhận đã ký UNC" in r.text and "TT-2026-001" in r.text
    ok(c.post(f"/to-trinh/{sid}/xac-nhan-ky", data={"unc_ref": "FT1", "unc_amount": "120000000"}, files={"file": PDF}))

    set_day(conn, "2026-12-02")
    conn.commit()
    csv_bytes = reconcile.build_statement_csv("0071000888999", "2026-10-01", "2026-11-30", 12_500_000_000,
                                              [("2026-11-03", "FT1", "TT-2026-001 tt", "0071000111222", -120_000_000)])
    login(c, "thuky")
    ok(c.post("/sao-ke", data={"fund_code": "BT"}, files={"file": ("sk.csv", csv_bytes, "text/csv")}))
    assert q1(conn, "SELECT status FROM submissions WHERE id = ?", (sid,))["status"] == "da_doi_soat"
    ok(c.post(f"/to-trinh/{sid}/dong"))
    assert q1(conn, "SELECT status FROM submissions WHERE id = ?", (sid,))["status"] == "dong"

    # Các trang tổng hợp vẫn hiển thị sau khi có dữ liệu
    login(c, "truongban")
    for page in ("/", "/canh-bao", "/sao-ke/1", "/nhat-ky", "/chay-thu", "/cau-hinh", "/danh-muc"):
        ok(c.get(page))
