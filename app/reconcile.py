"""F-07: Sao kê & đối soát (CP4) – R-17, R-21, R-22, R-23.

Định dạng file sao kê (tạm thời, chờ Q4 – ngân hàng thật sẽ có parser riêng):

    SKYLINE-BANK-EXPORT,v1
    SoTaiKhoan,0071000888999
    TuNgay,2026-10-01
    DenNgay,2026-10-31
    SoDuDauKy,12500000000
    SoDuCuoiKy,12379990000
    NgayGD,SoThamChieu,NoiDung,TaiKhoanDoiUng,GhiNo,GhiCo,SoDu
    2026-10-12,FT26101200001,TT-2026-001 thanh toan dot 3,0071000111222,120000000,0,12380000000
"""
import csv
import hashlib
import io
import re
from datetime import date, timedelta

from . import audit, clock, notify, rules
from . import settings as S
from .db import insert, q, q1, row_dict, update
from .workflow import WorkflowError, get_sub, is_signer, set_status

SIGNATURE = "SKYLINE-BANK-EXPORT"
HEADER = ["NgayGD", "SoThamChieu", "NoiDung", "TaiKhoanDoiUng", "GhiNo", "GhiCo", "SoDu"]
CODE_RE = re.compile(r"TT[\s\-_.]?(\d{4})[\s\-_.]?(\d{3})", re.IGNORECASE)


def _int(v) -> int:
    v = str(v or "0").strip().replace(".", "").replace(",", "").replace(" ", "")
    return int(v or 0)


def parse(content: bytes) -> tuple[dict, list[dict], list[str]]:
    """Trả về (meta, rows, lỗi định dạng)."""
    errors = []
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {}, [], ["File không phải văn bản UTF-8 xuất từ ngân hàng"]
    lines = list(csv.reader(io.StringIO(text)))
    lines = [l for l in lines if any(c.strip() for c in l)]
    if not lines or lines[0][0].strip() != SIGNATURE:
        return {}, [], ["Không phải file xuất gốc theo định dạng ngân hàng (thiếu dòng nhận diện)"]
    meta = {}
    i = 1
    while i < len(lines) and lines[i][0].strip() != HEADER[0]:
        if len(lines[i]) >= 2:
            meta[lines[i][0].strip()] = lines[i][1].strip()
        i += 1
    for k in ("SoTaiKhoan", "TuNgay", "DenNgay", "SoDuDauKy", "SoDuCuoiKy"):
        if k not in meta:
            errors.append(f"Thiếu thông tin {k}")
    if i >= len(lines) or [c.strip() for c in lines[i]] != HEADER:
        errors.append("Sai dòng tiêu đề cột giao dịch")
        return meta, [], errors
    rows = []
    for n, l in enumerate(lines[i + 1:], start=1):
        if len(l) != len(HEADER):
            errors.append(f"Dòng giao dịch {n}: sai số cột")
            continue
        try:
            d = date.fromisoformat(l[0].strip())
        except ValueError:
            errors.append(f"Dòng giao dịch {n}: ngày không hợp lệ")
            continue
        try:
            debit, credit, bal = _int(l[4]), _int(l[5]), _int(l[6])
        except ValueError:
            errors.append(f"Dòng giao dịch {n}: số tiền không hợp lệ")
            continue
        rows.append({"txn_date": d.isoformat(), "bank_ref": l[1].strip(), "description": l[2].strip(),
                     "counter_account": l[3].strip(), "amount": credit - debit, "balance_after": bal})
    if not errors:
        try:
            meta["opening"] = _int(meta["SoDuDauKy"])
            meta["closing"] = _int(meta["SoDuCuoiKy"])
            meta["from"] = date.fromisoformat(meta["TuNgay"]).isoformat()
            meta["to"] = date.fromisoformat(meta["DenNgay"]).isoformat()
        except ValueError:
            errors.append("Thông tin kỳ sao kê không hợp lệ")
    return meta, rows, errors


def validate_continuity(conn, fund, meta, rows, digest) -> list[str]:
    """R-23: sao kê phải là file gốc và liên tục với kỳ trước."""
    errs = []
    if rules.digits(meta["SoTaiKhoan"]) != rules.digits(fund["account_no"]):
        errs.append(f"Số tài khoản trên sao kê ({meta['SoTaiKhoan']}) không phải tài khoản {fund['name']}")
    if q1(conn, "SELECT 1 FROM statements WHERE sha256 = ?", (digest,)):
        errs.append("File này đã được upload trước đó")
    prev = q1(conn, "SELECT * FROM statements WHERE fund_code = ? ORDER BY period_to DESC LIMIT 1", (fund["code"],))
    if prev:
        expect_from = (date.fromisoformat(prev["period_to"]) + timedelta(days=1)).isoformat()
        expect_open = prev["closing_balance"]
        label = f"kỳ trước ({prev['period_from']} → {prev['period_to']})"
    else:
        expect_from = fund["opening_date"]
        expect_open = fund["opening_balance"]
        label = "số dư khởi tạo F-00"
    if meta["from"] != expect_from:
        errs.append(f"Sao kê không liên tục: kỳ bắt đầu {meta['from']}, phải là {expect_from} (nối tiếp {label})")
    if meta["opening"] != expect_open:
        errs.append(f"Số dư đầu kỳ {rules.fmt(meta['opening'])} khác số dư cuối {label} {rules.fmt(expect_open)}")
    if meta["to"] < meta["from"]:
        errs.append("Ngày kết thúc kỳ trước ngày bắt đầu")
    bal = meta["opening"]
    last = meta["from"]
    for n, r in enumerate(rows, start=1):
        if not (meta["from"] <= r["txn_date"] <= meta["to"]):
            errs.append(f"Giao dịch {n} ngày {r['txn_date']} nằm ngoài kỳ sao kê")
        if r["txn_date"] < last:
            errs.append(f"Giao dịch {n} không theo thứ tự ngày")
        last = r["txn_date"]
        bal += r["amount"]
        if bal != r["balance_after"]:
            errs.append(f"Giao dịch {n}: số dư {rules.fmt(r['balance_after'])} không khớp lũy kế {rules.fmt(bal)} – dấu hiệu file bị sửa")
            bal = r["balance_after"]
    if bal != meta["closing"]:
        errs.append(f"Số dư cuối kỳ {rules.fmt(meta['closing'])} không khớp lũy kế giao dịch {rules.fmt(bal)}")
    return errs


def import_statement(conn, user, fund_code, filename, content: bytes) -> dict:
    if user["role"] != "thu_ky":
        raise WorkflowError("Chỉ thư ký/kế toán BQT được upload sao kê")
    fund = row_dict(q1(conn, "SELECT * FROM funds WHERE code = ?", (fund_code,)))
    if not fund:
        raise WorkflowError("Quỹ không tồn tại")
    digest = hashlib.sha256(content).hexdigest()
    meta, rows, errors = parse(content)
    if not errors and rules.is_enabled(conn, "R-23"):
        errors = validate_continuity(conn, fund, meta, rows, digest)
    elif not errors and q1(conn, "SELECT 1 FROM statements WHERE sha256 = ?", (digest,)):
        errors = ["File này đã được upload trước đó"]
    if errors:
        insert(conn, "statement_rejections", {"fund_code": fund_code, "filename": filename, "reasons": "\n".join(errors),
                                              "uploaded_by": user["id"], "uploaded_at": clock.now(conn)})
        audit.log(conn, user["id"], "R-23: từ chối file sao kê", "statement", None, None,
                  {"filename": filename, "errors": errors})
        conn.commit()
        raise WorkflowError("R-23: File sao kê bị từ chối:", errors)
    sid = insert(conn, "statements", {"fund_code": fund_code, "period_from": meta["from"], "period_to": meta["to"],
                                      "opening_balance": meta["opening"], "closing_balance": meta["closing"],
                                      "filename": filename, "sha256": digest, "uploaded_by": user["id"],
                                      "uploaded_at": clock.now(conn)})
    audit.log(conn, user["id"], "Upload sao kê", "statement", sid, None,
              {"fund": fund_code, "from": meta["from"], "to": meta["to"], "rows": len(rows)})
    for r in rows:
        tid = insert(conn, "statement_txns", {"statement_id": sid, **r})
        auto_match(conn, user, tid)
    check_r22(conn, fund_code)
    return {"id": sid, "rows": len(rows)}


# ---------- So khớp ----------------------------------------------------------------------

def _latest_by_code(conn, code):
    return row_dict(q1(conn, "SELECT * FROM submissions WHERE code = ? AND status <> 'huy' ORDER BY version DESC LIMIT 1",
                       (code,)))


def auto_match(conn, user, txn_id) -> None:
    t = row_dict(q1(conn, "SELECT t.*, s.fund_code FROM statement_txns t JOIN statements s ON s.id = t.statement_id"
                          " WHERE t.id = ?", (txn_id,)))
    if t["amount"] >= 0:
        return  # khoản thu: chỉ phân loại
    amount = -t["amount"]
    # (1) Mã tờ trình trong nội dung chuyển khoản
    m = CODE_RE.search(t["description"] or "")
    if m:
        sub = _latest_by_code(conn, f"TT-{m.group(1)}-{m.group(2)}")
        if sub and sub["fund_code"] == t["fund_code"] and not _already_matched(conn, sub["id"]):
            if sub["amount"] == amount:
                apply_match(conn, user, txn_id, sub["id"], "ma_to_trinh")
            else:
                update(conn, "statement_txns", "id", txn_id, {"match_status": "de_xuat", "submission_id": sub["id"],
                                                               "match_method": "ma_to_trinh",
                                                               "category_note": "Có mã tờ trình nhưng số tiền khác"})
            return
    # (2) Số tiền + tài khoản thụ hưởng + khoảng ngày từ Sẵn sàng ký đến N ngày làm việc sau
    n = S.get_int(conn, "r22_days")
    cands = []
    for s in q(conn, "SELECT * FROM submissions WHERE fund_code = ? AND amount = ? AND status IN ('san_sang_ky','da_ky')",
               (t["fund_code"], amount)):
        if _already_matched(conn, s["id"]) or not s["ready_at"]:
            continue
        start = clock.to_date(s["ready_at"])
        end = clock.add_business_days(conn, s["signed_at"] or s["ready_at"], n)
        if rules.digits(s["beneficiary_account"]) == rules.digits(t["counter_account"]) and \
                start <= clock.to_date(t["txn_date"]) <= end:
            cands.append(s)
    if len(cands) == 1:
        apply_match(conn, user, txn_id, cands[0]["id"], "tu_dong")
    elif len(cands) > 1:
        update(conn, "statement_txns", "id", txn_id, {"match_status": "de_xuat", "submission_id": cands[0]["id"],
                                                       "category_note": f"{len(cands)} tờ trình phù hợp – cần chọn"})


def _already_matched(conn, sub_id) -> bool:
    return q1(conn, "SELECT 1 FROM statement_txns WHERE submission_id = ? AND match_status = 'da_khop'", (sub_id,)) is not None


def apply_match(conn, user, txn_id, sub_id, method) -> None:
    t = row_dict(q1(conn, "SELECT * FROM statement_txns WHERE id = ?", (txn_id,)))
    sub = get_sub(conn, sub_id)
    update(conn, "statement_txns", "id", txn_id, {"match_status": "da_khop", "submission_id": sub_id,
                                                   "match_method": method})
    audit.log(conn, user["id"], f"Khớp giao dịch với {sub['code']} ({method})", "statement_txn", txn_id)
    # R-21: chi trước, duyệt sau
    if rules.is_enabled(conn, "R-21") and (not sub["ready_at"] or t["txn_date"] < sub["ready_at"][:10]):
        msg = (f"Giao dịch ngày {t['txn_date']} ({rules.fmt(-t['amount'])}) khớp {sub['code']} nhưng tờ trình "
               + (f"chỉ đạt Sẵn sàng ký ngày {sub['ready_at'][:10]}" if sub["ready_at"] else
                  f"chưa đạt Sẵn sàng ký (đang: {sub['status']})") + " – chi trước, duyệt sau")
        conn.execute("INSERT INTO alerts(submission_id, statement_txn_id, rule_id, severity, checkpoint, message, created_at)"
                     " VALUES (?,?,?,?,?,?,?)", (sub_id, txn_id, "R-21", "cao", "CP4", msg, clock.now(conn)))
        notify.to_bqt(conn, f"R-21: chi trước, duyệt sau – {sub['code']}", msg, f"/to-trinh/{sub_id}")
    if sub["status"] == "da_ky":
        set_status(conn, sub, "da_doi_soat", user["id"], f"Khớp giao dịch sao kê {t['bank_ref']}",
                   {"reconciled_at": clock.now(conn)})
    _resolve_txn_alerts(conn, txn_id)


def confirm_match(conn, user, txn_id, sub_id) -> None:
    t = row_dict(q1(conn, "SELECT t.*, s.uploaded_by FROM statement_txns t JOIN statements s ON s.id = t.statement_id"
                          " WHERE t.id = ?", (txn_id,)))
    if not t or t["match_status"] not in ("de_xuat", "chua_khop"):
        raise WorkflowError("Giao dịch không ở trạng thái chờ xác nhận")
    if user["role"] not in ("bqt", "thu_ky"):
        raise WorkflowError("Không có quyền xác nhận khớp")
    if user["id"] == t["uploaded_by"]:
        raise WorkflowError("Người xác nhận khớp phải khác người upload sao kê")
    sub = get_sub(conn, sub_id)
    if -t["amount"] != sub["amount"]:
        raise WorkflowError("Số tiền giao dịch khác số tiền tờ trình")
    apply_match(conn, user, txn_id, sub_id, "xac_nhan")


def classify(conn, user, txn_id, category, note="") -> None:
    from .constants import TXN_CATEGORY
    if user["role"] != "thu_ky":
        raise WorkflowError("Chỉ thư ký đề xuất phân loại giao dịch")
    if category not in TXN_CATEGORY:
        raise WorkflowError("Loại phân loại không hợp lệ")
    if category == "khac" and not note:
        raise WorkflowError("Loại \"Khác\" cần ghi rõ nội dung")
    t = q1(conn, "SELECT * FROM statement_txns WHERE id = ?", (txn_id,))
    if t["match_status"] in ("da_khop", "da_phan_loai"):
        raise WorkflowError("Giao dịch đã được giải thích")
    data = {"match_status": "de_xuat_phan_loai", "category": category, "category_note": note,
            "classified_by": user["id"], "classified_at": clock.now(conn)}
    update(conn, "statement_txns", "id", txn_id, data)
    audit.log(conn, user["id"], "Đề xuất phân loại giao dịch", "statement_txn", txn_id, dict(t), data)


def approve_classification(conn, user, txn_id, approve=True) -> None:
    t = row_dict(q1(conn, "SELECT t.*, s.uploaded_by, s.fund_code FROM statement_txns t"
                          " JOIN statements s ON s.id = t.statement_id WHERE t.id = ?", (txn_id,)))
    if t["match_status"] != "de_xuat_phan_loai":
        raise WorkflowError("Giao dịch không chờ duyệt phân loại")
    if not is_signer(conn, user, t["fund_code"]):
        raise WorkflowError("Chỉ chủ tài khoản được duyệt phân loại")
    if user["id"] in (t["uploaded_by"], t["classified_by"]):
        raise WorkflowError("Người duyệt phân loại phải khác người upload sao kê và người đề xuất")
    if approve:
        data = {"match_status": "da_phan_loai", "approved_by": user["id"], "approved_at": clock.now(conn)}
    else:
        data = {"match_status": "chua_khop", "category": None, "classified_by": None, "classified_at": None}
    update(conn, "statement_txns", "id", txn_id, data)
    audit.log(conn, user["id"], "Duyệt phân loại" if approve else "Trả lại phân loại", "statement_txn", txn_id, t, data)
    if approve:
        _resolve_txn_alerts(conn, txn_id)


def _resolve_txn_alerts(conn, txn_id):
    conn.execute("UPDATE alerts SET status = 'resolved', resolved_at = ? WHERE statement_txn_id = ? AND rule_id = 'R-17'"
                 " AND status = 'open'", (clock.now(conn), txn_id))


# ---------- R-17 / R-22 ------------------------------------------------------------------

def check_r17(conn) -> int:
    if not rules.is_enabled(conn, "R-17"):
        return 0
    days = S.get_int(conn, "r17_days")
    today = clock.today(conn)
    created = 0
    for t in q(conn, "SELECT t.*, s.uploaded_at FROM statement_txns t JOIN statements s ON s.id = t.statement_id"
                     " WHERE t.match_status NOT IN ('da_khop','da_phan_loai')"):
        if clock.business_days_between(conn, t["uploaded_at"], today) < days:
            continue
        if q1(conn, "SELECT 1 FROM alerts WHERE statement_txn_id = ? AND rule_id = 'R-17'", (t["id"],)):
            continue
        msg = (f"Giao dịch {t['bank_ref']} ngày {t['txn_date']} ({rules.fmt(t['amount'])}): \"{t['description']}\" "
               f"chưa khớp tờ trình và chưa được phân loại sau {days} ngày làm việc")
        conn.execute("INSERT INTO alerts(statement_txn_id, rule_id, severity, checkpoint, message, created_at)"
                     " VALUES (?,?,?,?,?,?)", (t["id"], "R-17", "cao", "CP4", msg, clock.now(conn)))
        notify.to_bqt(conn, "R-17: giao dịch chưa giải thích được", msg, f"/sao-ke/{t['statement_id']}")
        created += 1
    return created


def check_r22(conn, fund_code=None) -> int:
    """Đã xác nhận ký quá N ngày làm việc mà sao kê (đã phủ tới thời điểm đó) chưa có giao dịch."""
    if not rules.is_enabled(conn, "R-22"):
        return 0
    n = S.get_int(conn, "r22_days")
    created = 0
    sql = "SELECT * FROM submissions WHERE status = 'da_ky'"
    params = ()
    if fund_code:
        sql += " AND fund_code = ?"
        params = (fund_code,)
    for s in q(conn, sql, params):
        due = clock.add_business_days(conn, s["signed_at"], n)
        covered = conn.execute("SELECT MAX(period_to) FROM statements WHERE fund_code = ?", (s["fund_code"],)).fetchone()[0]
        today = clock.today(conn)
        if not covered or covered < due.isoformat() or today <= due:
            continue
        if q1(conn, "SELECT 1 FROM alerts WHERE submission_id = ? AND rule_id = 'R-22' AND status IN ('open','accepted')",
              (s["id"],)):
            continue
        msg = (f"{s['code']} xác nhận ký ngày {s['signed_at'][:10]} nhưng sau {n} ngày làm việc "
               f"(đến {due.isoformat()}) sao kê chưa có giao dịch tương ứng")
        conn.execute("INSERT INTO alerts(submission_id, rule_id, severity, checkpoint, message, created_at)"
                     " VALUES (?,?,?,?,?,?)", (s["id"], "R-22", "tb", "CP4", msg, clock.now(conn)))
        notify.to_bqt(conn, f"R-22: {s['code']} chưa thấy tiền chuyển", msg, f"/to-trinh/{s['id']}")
        created += 1
    return created


def build_statement_csv(account_no, period_from, period_to, opening, txns) -> bytes:
    """Tiện ích sinh file mẫu (seed/kiểm thử). txns: list (ngày, ref, nội dung, tk đối ứng, số tiền có dấu)."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    bal = opening
    body = []
    for d, ref, desc, acc, amt in txns:
        bal += amt
        body.append([d, ref, desc, acc, -amt if amt < 0 else 0, amt if amt > 0 else 0, bal])
    w.writerow([SIGNATURE, "v1"])
    w.writerow(["SoTaiKhoan", account_no])
    w.writerow(["TuNgay", period_from])
    w.writerow(["DenNgay", period_to])
    w.writerow(["SoDuDauKy", opening])
    w.writerow(["SoDuCuoiKy", bal])
    w.writerow(HEADER)
    w.writerows(body)
    return out.getvalue().encode("utf-8")
