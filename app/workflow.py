"""Luồng chính Tờ trình → UNC (mục 6 PRD): trạng thái, điểm kiểm soát, biểu quyết, xác nhận ký."""
import hashlib
import re

from . import audit, clock, notify, rules
from . import settings as S
from .constants import BQL_DOC_TYPES, BQT_DOC_TYPES, DOC_TYPES, STATUS
from .db import UPLOAD_DIR, insert, q, q1, row_dict, update


class WorkflowError(Exception):
    """Lỗi nghiệp vụ hiển thị được cho người dùng."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.details = details or []


def _require(cond, msg):
    if not cond:
        raise WorkflowError(msg)


def get_sub(conn, sub_id) -> dict:
    s = row_dict(q1(conn, "SELECT * FROM submissions WHERE id = ?", (sub_id,)))
    _require(s, "Không tìm thấy tờ trình")
    return s


def is_bqt(user):
    return user["role"] == "bqt"


def is_signer(conn, user, fund_code) -> bool:
    return q1(conn, "SELECT 1 FROM fund_signers WHERE fund_code = ? AND user_id = ?", (fund_code, user["id"])) is not None


def set_status(conn, sub, new_status, user_id, note=None, extra=None):
    data = {"status": new_status, **(extra or {})}
    update(conn, "submissions", "id", sub["id"], data)
    insert(conn, "status_history", {"submission_id": sub["id"], "from_status": sub["status"], "to_status": new_status,
                                    "at": clock.now(conn), "by_user": user_id, "note": note})
    audit.log(conn, user_id, f"Chuyển trạng thái: {STATUS[sub['status']]} → {STATUS[new_status]}", "submission",
              sub["id"], {"status": sub["status"]}, data)
    sub.update(data)


def link(sub):
    return f"/to-trinh/{sub['id']}"


# ---------- Lưu file ---------------------------------------------------------------------

def save_file(content: bytes, filename: str) -> tuple[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", filename)[-80:] or "file"
    folder = UPLOAD_DIR / digest[:2]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{digest[:16]}_{safe}"
    if not path.exists():
        path.write_bytes(content)
    return str(path), digest


# ---------- F-02 Tạo tờ trình ---------------------------------------------------------------

def next_code(conn) -> str:
    year = clock.today(conn).year
    n = conn.execute("SELECT COUNT(DISTINCT code) FROM submissions WHERE code LIKE ?", (f"TT-{year}-%",)).fetchone()[0]
    return f"TT-{year}-{n + 1:03d}"


FIELDS = ("fund_code", "plan_item_code", "is_emergency", "cost_type", "vendor_id", "contract_id", "installment_id",
          "amount", "payment_method", "beneficiary_account", "is_advance", "is_mgmt_fee", "kpi_month",
          "service_key", "unit_price", "reason")


def _validate(conn, data):
    for key, label in (("fund_code", "quỹ"), ("cost_type", "loại chi"), ("vendor_id", "nhà cung cấp"),
                       ("contract_id", "hợp đồng"), ("payment_method", "hình thức thanh toán"), ("reason", "lý do")):
        _require(data.get(key) not in (None, ""), f"Bắt buộc chọn/nhập {label}")
    _require(data.get("amount") and int(data["amount"]) > 0, "Số tiền phải lớn hơn 0")
    # Không bắt buộc hạng mục ở bước nhập: khoản quỹ bảo trì ngoài kế hoạch sẽ bị R-02 chặn ở CP1 kèm hướng dẫn
    c = q1(conn, "SELECT * FROM contracts WHERE id = ?", (data["contract_id"],))
    _require(c is not None, "Hợp đồng không tồn tại")
    _require(int(c["vendor_id"]) == int(data["vendor_id"]), "Hợp đồng không thuộc nhà cung cấp đã chọn")
    _require(c["fund_code"] == data["fund_code"], "Hợp đồng không thuộc quỹ đã chọn")
    if q(conn, "SELECT 1 FROM contract_installments WHERE contract_id = ?", (c["id"],)):
        _require(data.get("installment_id"), "Bắt buộc chọn đợt thanh toán của hợp đồng")
    if data.get("installment_id"):
        inst = q1(conn, "SELECT * FROM contract_installments WHERE id = ?", (data["installment_id"],))
        _require(inst and inst["contract_id"] == c["id"], "Đợt thanh toán không thuộc hợp đồng")
    if data["fund_code"] == "VH":
        _require(S.get(conn, "vh_bqt_signs") == "1",
                 "Quỹ vận hành đang ở chế độ giám sát báo cáo (BQT không ký UNC quỹ này – Q2)")


def create_submission(conn, user, data: dict) -> dict:
    _require(user["role"] == "bql", "Chỉ BQL được tạo tờ trình")
    data = {k: data.get(k) for k in FIELDS} | {"linked_submission_id": data.get("linked_submission_id") or None}
    _validate(conn, data)
    if data["linked_submission_id"]:
        old = get_sub(conn, data["linked_submission_id"])
        _require(old["status"] == "tu_choi", "Chỉ liên kết được với tờ trình đã bị từ chối")
    elif data.get("installment_id"):
        # Tờ trình nộp lại sau khi bị từ chối bắt buộc liên kết tờ trình cũ
        rej = q1(conn, "SELECT code FROM submissions s WHERE status = 'tu_choi' AND installment_id = ?"
                       " AND NOT EXISTS (SELECT 1 FROM submissions n WHERE n.linked_submission_id = s.id)",
                 (data["installment_id"],))
        _require(rej is None, f"Đợt thanh toán này đã có tờ trình bị từ chối ({rej['code'] if rej else ''}). "
                              "Hãy dùng nút \"Nộp lại\" để liên kết tờ trình cũ")
    row = {**data, "code": next_code(conn), "version": 1, "status": "nhap", "created_by": user["id"],
           "created_at": clock.now(conn)}
    row["amount"] = int(row["amount"])
    for k in ("is_emergency", "is_advance", "is_mgmt_fee"):
        row[k] = 1 if row.get(k) else 0
    sid = insert(conn, "submissions", row)
    insert(conn, "status_history", {"submission_id": sid, "from_status": None, "to_status": "nhap",
                                    "at": row["created_at"], "by_user": user["id"]})
    audit.log(conn, user["id"], "Tạo tờ trình", "submission", sid, None, row)
    return get_sub(conn, sid)


def edit_submission(conn, user, sub_id, data: dict) -> dict:
    sub = get_sub(conn, sub_id)
    _require(user["role"] == "bql", "Chỉ BQL được sửa tờ trình")
    _require(sub["status"] in ("nhap", "yeu_cau_bo_sung"),
             "Chỉ sửa được tờ trình ở trạng thái Nháp hoặc Yêu cầu bổ sung. Sau khi nộp, muốn đổi phải tạo phiên bản mới")
    new = {k: data.get(k) for k in FIELDS}
    _validate(conn, new)
    new["amount"] = int(new["amount"])
    for k in ("is_emergency", "is_advance", "is_mgmt_fee"):
        new[k] = 1 if new.get(k) else 0
    update(conn, "submissions", "id", sub_id, new)
    audit.log(conn, user["id"], "Sửa tờ trình", "submission", sub_id, {k: sub[k] for k in new}, new)
    return get_sub(conn, sub_id)


# ---------- Chứng từ ----------------------------------------------------------------------

def add_document(conn, user, sub_id, doc_type, filename, content: bytes, meta: dict | None = None,
                 replace_id=None) -> int:
    sub = get_sub(conn, sub_id)
    meta = meta or {}
    _require(doc_type in DOC_TYPES, "Loại chứng từ không hợp lệ")
    _require(content, "File rỗng")
    if user["role"] == "bql":
        _require(doc_type in BQL_DOC_TYPES, "BQL không được upload loại chứng từ này")
        _require(sub["status"] in ("nhap", "yeu_cau_bo_sung", "da_nop"),
                 "Đã mở biểu quyết: chứng từ bị khóa. Muốn thay đổi phải tạo phiên bản mới của tờ trình")
    elif user["role"] in ("bqt", "thu_ky"):
        _require(doc_type in BQT_DOC_TYPES, "BQT/thư ký chỉ upload hồ sơ gửi ngân hàng (bản ký)")
        _require(sub["status"] in ("da_duyet", "can_hop"), "Chỉ upload bản ký khi tờ trình Đã duyệt hoặc đang Cần họp")
    else:
        raise WorkflowError("Vai trò này không được upload chứng từ")
    path, digest = save_file(content, filename)
    row = {"submission_id": sub_id, "doc_type": doc_type, "filename": filename, "stored_path": path,
           "sha256": digest, "uploaded_by": user["id"], "uploaded_at": clock.now(conn),
           "invoice_no": meta.get("invoice_no") or None, "seller_tax_code": meta.get("seller_tax_code") or None,
           "amount": int(meta["amount"]) if meta.get("amount") not in (None, "") else None,
           "doc_date": meta.get("doc_date") or None,
           "signed_by_bqt": 1 if meta.get("signed_by_bqt") else 0,
           "signed_by_supervisor": 1 if meta.get("signed_by_supervisor") else 0,
           "contract_signed": 1 if meta.get("contract_signed") else 0,
           "tax_status": meta.get("tax_status") or None}
    did = insert(conn, "documents", row)
    if replace_id:
        old = q1(conn, "SELECT * FROM documents WHERE id = ? AND submission_id = ?", (replace_id, sub_id))
        _require(old is not None, "Chứng từ cần thay không tồn tại")
        conn.execute("UPDATE documents SET superseded_by = ? WHERE id = ?", (did, replace_id))
    audit.log(conn, user["id"], f"Upload chứng từ: {DOC_TYPES[doc_type]}", "document", did, None, row)
    if doc_type in ("de_nghi_ky", "bien_ban_hop_ky") and sub["signed_docs_verified_by"]:
        update(conn, "submissions", "id", sub_id, {"signed_docs_verified_by": None, "signed_docs_verified_at": None})
    # Chứng từ thay đổi sau khi nộp → chạy lại toàn bộ rule CP1
    if sub["status"] == "da_nop":
        alerts = rules.run_checkpoint(conn, sub_id, "CP1")
        if rules.blocking(alerts):
            set_status(conn, sub, "yeu_cau_bo_sung", user["id"], "Chứng từ thay đổi làm phát sinh lỗi Chặn ở CP1")
    return did


def cancel_document(conn, user, doc_id, reason):
    d = q1(conn, "SELECT * FROM documents WHERE id = ?", (doc_id,))
    _require(d is not None, "Không tìm thấy chứng từ")
    sub = get_sub(conn, d["submission_id"])
    _require(d["uploaded_by"] == user["id"], "Chỉ người upload được hủy chứng từ của mình")
    _require(sub["status"] in ("nhap", "yeu_cau_bo_sung", "da_nop", "da_duyet"), "Không hủy được chứng từ ở trạng thái này")
    _require(reason, "Cần ghi lý do hủy")
    conn.execute("UPDATE documents SET cancelled = 1 WHERE id = ?", (doc_id,))
    audit.log(conn, user["id"], f"Hủy chứng từ ({reason})", "document", doc_id, {"cancelled": 0}, {"cancelled": 1})
    if sub["status"] == "da_nop":
        if rules.blocking(rules.run_checkpoint(conn, sub["id"], "CP1")):
            set_status(conn, sub, "yeu_cau_bo_sung", user["id"], "Chứng từ bị hủy làm phát sinh lỗi Chặn ở CP1")


# ---------- CP1: BQL nộp ------------------------------------------------------------------

def submit(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(user["role"] == "bql", "Chỉ BQL được nộp tờ trình")
    _require(sub["status"] in ("nhap", "yeu_cau_bo_sung"), "Tờ trình không ở trạng thái được nộp")
    plan = rules.active_plan(conn, sub["fund_code"], clock.today(conn))
    update(conn, "submissions", "id", sub_id, {"plan_id": plan["id"] if plan else None,
                                                "submitted_at": clock.now(conn)})
    alerts = rules.run_checkpoint(conn, sub_id, "CP1")
    blockers = rules.blocking(alerts)
    sub = get_sub(conn, sub_id)
    if blockers:
        update(conn, "submissions", "id", sub_id, {"submitted_at": None})
        if sub["status"] != "yeu_cau_bo_sung":
            set_status(conn, sub, "yeu_cau_bo_sung", user["id"], "CP1: thiếu hồ sơ / vi phạm rule Chặn")
        audit.log(conn, user["id"], "Nộp tờ trình bị chặn ở CP1", "submission", sub_id, None,
                  {"blockers": [a["message"] for a in blockers]})
        raise WorkflowError("Không nộp được tờ trình. Cần xử lý:", [f"{a['rule_id']}: {a['message']}" for a in blockers])
    set_status(conn, sub, "da_nop", user["id"], "Qua CP1")
    high = [a for a in alerts if a["severity"] == "cao"]
    notify.to_bqt(conn, f"Tờ trình mới {sub['code']} chờ thẩm tra",
                  f"{len(high)} cảnh báo Cao cần xử lý" if high else "Không có cảnh báo Cao", link(sub))
    return sub


def request_more(conn, user, sub_id, reason) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user) or user["role"] == "thu_ky", "Chỉ BQT/thư ký được yêu cầu bổ sung")
    _require(sub["status"] == "da_nop", "Chỉ yêu cầu bổ sung khi tờ trình ở trạng thái Đã nộp")
    _require(reason, "Cần ghi nội dung yêu cầu bổ sung")
    set_status(conn, sub, "yeu_cau_bo_sung", user["id"], reason)
    notify.send(conn, [sub["created_by"]], f"{sub['code']}: BQT yêu cầu bổ sung hồ sơ", reason, link(sub))
    return sub


# ---------- CP2: BQT thẩm tra & mở biểu quyết ----------------------------------------------

def confirm_emergency(conn, user, sub_id, cost_type, note) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user), "Chỉ thành viên BQT được xác nhận tính đột xuất")
    _require(sub["is_emergency"], "Tờ trình không đánh dấu đột xuất")
    _require(sub["status"] == "da_nop", "Chỉ xác nhận khi tờ trình ở trạng thái Đã nộp")
    _require(note, "Cần ghi căn cứ xác nhận tính đột xuất")
    _require(user["id"] not in [p["id"] for p in rules.conflicted_users(conn, sub["vendor_id"])],
             "Người có xung đột lợi ích với nhà cung cấp không được xác nhận")
    data = {"emergency_confirmed_by": user["id"], "emergency_confirmed_at": clock.now(conn), "emergency_note": note,
            "cost_type": cost_type or sub["cost_type"]}
    update(conn, "submissions", "id", sub_id, data)
    audit.log(conn, user["id"], "Xác nhận tính đột xuất", "submission", sub_id,
              {"cost_type": sub["cost_type"]}, data)
    return get_sub(conn, sub_id)


def tally(conn, sub) -> dict:
    tier = rules.tier_for(conn, sub["amount"])
    members = [dict(r) for r in q(conn, "SELECT id, full_name, is_chair FROM users WHERE role = 'bqt' AND active = 1")]
    conflicted = {p["id"] for p in rules.conflicted_users(conn, sub["vendor_id"])}
    eligible = [m for m in members if m["id"] not in conflicted]
    excluded = [m for m in members if m["id"] in conflicted]
    eligible_ids = {m["id"] for m in eligible}
    current = {r["user_id"]: dict(r) for r in q(conn, "SELECT * FROM votes WHERE submission_id = ? AND superseded = 0",
                                                 (sub["id"],)) if r["user_id"] in eligible_ids}
    yes = [u for u, v in current.items() if v["choice"] == "dong_y"]
    no = [u for u, v in current.items() if v["choice"] == "khong_dong_y"]
    pending = [m for m in eligible if m["id"] not in current]
    n = len(eligible)
    if tier is None or tier["rule_type"] == "majority":
        needed = n // 2 + 1
    elif tier["rule_type"] == "all":
        needed = n
    else:
        needed = min(tier["required_count"], n)
    chair = next((m for m in eligible if m["is_chair"]), None)
    chair_needed = bool(tier and tier["require_chair"] and chair)
    chair_ok = (not chair_needed) or (chair["id"] in yes)
    passed = n > 0 and len(yes) >= needed and chair_ok
    impossible = (len(yes) + len(pending) < needed) or (chair_needed and chair["id"] in no)
    quorum = S.get_int(conn, "min_quorum")
    return {"tier": tier, "eligible": eligible, "excluded": excluded, "votes": current, "yes": yes, "no": no,
            "pending": pending, "needed": needed, "passed": passed, "impossible": impossible,
            "quorum": quorum, "quorum_ok": n >= quorum, "chair_needed": chair_needed}


def open_vote(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user) or user["role"] == "thu_ky", "Chỉ BQT/thư ký được mở biểu quyết")
    _require(sub["status"] == "da_nop", "Chỉ mở biểu quyết khi tờ trình ở trạng thái Đã nộp")
    cp1 = rules.run_checkpoint(conn, sub_id, "CP1")
    if rules.blocking(cp1):
        set_status(conn, sub, "yeu_cau_bo_sung", user["id"], "CP1 chạy lại phát sinh lỗi Chặn")
        raise WorkflowError("Tờ trình phát sinh lỗi Chặn ở CP1, đã chuyển Yêu cầu bổ sung",
                            [a["message"] for a in rules.blocking(cp1)])
    cp2 = rules.run_checkpoint(conn, sub_id, "CP2")
    if rules.blocking(cp2):
        raise WorkflowError("Chưa mở được biểu quyết (CP2):", [f"{a['rule_id']}: {a['message']}" for a in rules.blocking(cp2)])
    high = rules.pending_high(conn, sub_id)
    if high:
        raise WorkflowError("Còn cảnh báo Cao chưa được ghi lý do và chủ TK xác nhận:",
                            [f"{a['rule_id']}: {a['message']}" for a in high])
    t = tally(conn, sub)
    today = clock.today(conn)
    deadline = clock.add_business_days(conn, today, S.get_int(conn, "vote_days"))
    extra = {"vote_opened_at": clock.now(conn), "vote_deadline": deadline.isoformat()}
    reasons = []
    if not t["quorum_ok"]:
        reasons.append(f"sau khi loại người có xung đột chỉ còn {len(t['eligible'])} thành viên, dưới mức tối thiểu {t['quorum']}")
    if t["tier"] and t["tier"]["in_person"]:
        reasons.append(f"cấp duyệt {t['tier']['level']} yêu cầu họp trực tiếp")
    if S.get(conn, "online_vote_valid") != "1":
        reasons.append("Quy chế hoạt động BQT không cho biểu quyết trực tuyến thay cuộc họp")
    if reasons:
        set_status(conn, sub, "can_hop", user["id"], "; ".join(reasons), extra)
        notify.send(conn, [m["id"] for m in t["eligible"]], f"{sub['code']}: cần họp BQT trực tiếp",
                    "; ".join(reasons), link(sub))
    else:
        set_status(conn, sub, "cho_bieu_quyet", user["id"], f"Hạn biểu quyết {deadline.strftime('%d/%m/%Y')}", extra)
        notify.send(conn, [m["id"] for m in t["eligible"]], f"{sub['code']}: mời biểu quyết",
                    f"Hạn {deadline.strftime('%d/%m/%Y')}", link(sub))
    return sub


def cast_vote(conn, user, sub_id, choice, note="") -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user), "Chỉ thành viên BQT được biểu quyết")
    _require(choice in ("dong_y", "khong_dong_y"), "Lựa chọn không hợp lệ")
    _require(sub["status"] in ("cho_bieu_quyet", "can_hop"), "Tờ trình không trong thời gian biểu quyết")
    t = tally(conn, sub)
    _require(user["id"] in [m["id"] for m in t["eligible"]],
             "Bạn đã khai báo liên quan đến nhà cung cấp này nên không được biểu quyết")
    if sub["status"] == "cho_bieu_quyet":
        _require(clock.today(conn).isoformat() <= sub["vote_deadline"], "Đã hết hạn biểu quyết")
    old = q1(conn, "SELECT * FROM votes WHERE submission_id = ? AND user_id = ? AND superseded = 0", (sub_id, user["id"]))
    if old:
        conn.execute("UPDATE votes SET superseded = 1 WHERE id = ?", (old["id"],))
    vid = insert(conn, "votes", {"submission_id": sub_id, "user_id": user["id"], "choice": choice, "note": note,
                                 "cast_at": clock.now(conn)})
    audit.log(conn, user["id"], "Biểu quyết" if not old else "Sửa phiếu biểu quyết", "vote", vid,
              dict(old) if old else None, {"choice": choice, "note": note})
    if sub["status"] == "cho_bieu_quyet":
        t = tally(conn, sub)
        if t["passed"]:
            set_status(conn, sub, "da_duyet", user["id"], "Biểu quyết trực tuyến đạt tỷ lệ",
                       {"approval_basis": "online", "decided_at": clock.now(conn)})
            notify.send(conn, [sub["created_by"]], f"{sub['code']} đã được BQT duyệt", "", link(sub))
            notify.to_bqt(conn, f"{sub['code']} đã duyệt – chuẩn bị hồ sơ ngân hàng", "", link(sub), include_secretary=True)
    return get_sub(conn, sub_id)


def reject(conn, user, sub_id, reason) -> dict:
    """BQT chốt một lý do chung; BQL chỉ thấy lý do này, không thấy ý kiến từng người (F-05)."""
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user), "Chỉ thành viên BQT được chốt từ chối")
    _require(reason, "Cần ghi lý do từ chối chung")
    if sub["status"] == "cho_bieu_quyet":
        t = tally(conn, sub)
        _require(t["impossible"], "Chỉ chốt từ chối khi số phiếu không còn khả năng đạt tỷ lệ, hoặc qua họp trực tiếp")
    else:
        _require(sub["status"] == "can_hop", "Không thể từ chối ở trạng thái này")
    set_status(conn, sub, "tu_choi", user["id"], reason, {"rejection_reason": reason, "decided_at": clock.now(conn)})
    notify.send(conn, [sub["created_by"]], f"{sub['code']} bị từ chối", reason, link(sub))
    return sub


def meeting_result(conn, user, sub_id, decision, filename, content, reason="") -> dict:
    """Nhập kết quả họp trực tiếp kèm biên bản (mục 6.2)."""
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user), "Chỉ thành viên BQT được nhập kết quả họp")
    _require(sub["status"] == "can_hop", "Tờ trình không ở trạng thái Cần họp trực tiếp")
    _require(content, "Bắt buộc đính kèm biên bản họp")
    _require(decision in ("duyet", "tu_choi"), "Kết quả họp không hợp lệ")
    _require(decision == "duyet" or reason, "Cần ghi lý do từ chối chung")
    add_document(conn, user, sub_id, "bien_ban_hop_ky", filename, content)
    sub = get_sub(conn, sub_id)
    if decision == "duyet":
        set_status(conn, sub, "da_duyet", user["id"], "Duyệt tại cuộc họp BQT",
                   {"approval_basis": "meeting", "decided_at": clock.now(conn)})
        notify.send(conn, [sub["created_by"]], f"{sub['code']} đã được BQT duyệt", "", link(sub))
    else:
        reject(conn, user, sub_id, reason)
    return get_sub(conn, sub_id)


def new_version(conn, user, sub_id, amount=None) -> dict:
    """Số tiền khóa từ khi mở biểu quyết; muốn đổi phải tạo phiên bản mới và biểu quyết lại (F-02)."""
    sub = get_sub(conn, sub_id)
    _require(user["role"] == "bql", "Chỉ BQL được tạo phiên bản mới")
    _require(sub["status"] in ("da_nop", "cho_bieu_quyet", "can_hop", "da_duyet", "san_sang_ky"),
             "Không tạo phiên bản mới ở trạng thái này")
    row = {k: sub[k] for k in FIELDS} | {"code": sub["code"], "version": sub["version"] + 1, "status": "nhap",
                                         "linked_submission_id": sub["linked_submission_id"],
                                         "created_by": user["id"], "created_at": clock.now(conn)}
    if amount:
        row["amount"] = int(amount)
    nid = insert(conn, "submissions", row)
    for d in q(conn, "SELECT * FROM documents WHERE submission_id = ? AND cancelled = 0 AND superseded_by IS NULL"
                     " AND doc_type IN (" + ",".join("?" for _ in BQL_DOC_TYPES) + ")", (sub_id, *BQL_DOC_TYPES)):
        dd = dict(d)
        dd.pop("id")
        dd["submission_id"] = nid
        insert(conn, "documents", dd)
    insert(conn, "status_history", {"submission_id": nid, "from_status": None, "to_status": "nhap",
                                    "at": row["created_at"], "by_user": user["id"],
                                    "note": f"Phiên bản {row['version']} thay cho v{sub['version']}"})
    set_status(conn, sub, "huy", user["id"], f"Thay bằng phiên bản {row['version']}", {"superseded_by": nid})
    audit.log(conn, user["id"], "Tạo phiên bản mới", "submission", nid, None, row)
    return get_sub(conn, nid)


def cancel(conn, user, sub_id, reason) -> dict:
    sub = get_sub(conn, sub_id)
    _require(reason, "Cần ghi lý do hủy")
    _require((user["role"] == "bql" and sub["status"] in ("nhap", "yeu_cau_bo_sung", "da_nop"))
             or (is_bqt(user) and sub["status"] in ("nhap", "yeu_cau_bo_sung", "da_nop", "cho_bieu_quyet", "can_hop",
                                                     "da_duyet", "san_sang_ky")),
             "Không hủy được tờ trình ở trạng thái này (đã ký thì không hủy)")
    set_status(conn, sub, "huy", user["id"], reason)
    return sub


# ---------- CP3: hồ sơ ngân hàng & sẵn sàng ký ----------------------------------------------

def verify_signed_docs(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user) or user["role"] == "thu_ky", "Chỉ BQT/thư ký được kiểm tra bản ký")
    _require(sub["status"] == "da_duyet", "Tờ trình chưa ở trạng thái Đã duyệt")
    docs = q(conn, "SELECT * FROM documents WHERE submission_id = ? AND doc_type IN ('de_nghi_ky','bien_ban_hop_ky')"
                   " AND cancelled = 0 AND superseded_by IS NULL", (sub_id,))
    _require(len({d["doc_type"] for d in docs}) == 2 or sub["fund_code"] == "VH",
             "Cần upload đủ văn bản đề nghị chuyển tiền và biên bản họp đã ký")
    _require(all(d["uploaded_by"] != user["id"] for d in docs),
             "Người kiểm tra phải khác người upload bản ký")
    data = {"signed_docs_verified_by": user["id"], "signed_docs_verified_at": clock.now(conn)}
    update(conn, "submissions", "id", sub_id, data)
    audit.log(conn, user["id"], "Xác nhận bản ký khớp số tiền, nhà cung cấp", "submission", sub_id, None, data)
    return get_sub(conn, sub_id)


def check_ready(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user) or user["role"] == "thu_ky", "Chỉ BQT/thư ký được chạy kiểm tra CP3")
    _require(sub["status"] == "da_duyet", "Tờ trình chưa ở trạng thái Đã duyệt")
    cp3 = rules.run_checkpoint(conn, sub_id, "CP3")
    problems = [f"{a['rule_id']}: {a['message']}" for a in rules.blocking(cp3)]
    problems += [f"{a['rule_id']}: {a['message']} (cảnh báo Cao chưa xử lý)" for a in rules.pending_high(conn, sub_id)]
    if problems:
        raise WorkflowError("Chưa qua CP3:", problems)
    set_status(conn, sub, "san_sang_ky", user["id"], "Qua CP3", {"ready_at": clock.now(conn)})
    notify.send(conn, notify.account_holder_ids(conn, sub["fund_code"]), f"{sub['code']} sẵn sàng ký UNC",
                f"Ghi mã {sub['code']} vào nội dung chuyển khoản", link(sub))
    return sub


def confirm_sign(conn, user, sub_id, unc_ref, unc_amount, filename, content) -> dict:
    """F-06: chủ TK xác nhận đã ký UNC trên ngân hàng."""
    sub = get_sub(conn, sub_id)
    if not is_signer(conn, user, sub["fund_code"]):
        audit.log(conn, user["id"], "R-06: xác nhận ký bị chặn", "submission", sub_id)
        raise WorkflowError("R-06: Bạn không thuộc danh sách chủ tài khoản đã đăng ký của quỹ này")
    _require(sub["status"] == "san_sang_ky", "Chỉ xác nhận ký khi tờ trình ở trạng thái Sẵn sàng ký")
    _require(unc_ref, "Bắt buộc nhập số tham chiếu ngân hàng")
    _require(content, "Bắt buộc đính kèm UNC")
    _require(int(unc_amount or 0) == sub["amount"],
             f"Số tiền UNC phải bằng số tiền tờ trình đã duyệt ({sub['amount']:,} đ)".replace(",", "."))
    path, digest = save_file(content, filename)
    did = insert(conn, "documents", {"submission_id": sub_id, "doc_type": "unc", "filename": filename,
                                     "stored_path": path, "sha256": digest, "uploaded_by": user["id"],
                                     "uploaded_at": clock.now(conn), "amount": int(unc_amount)})
    audit.log(conn, user["id"], "Upload UNC", "document", did)
    set_status(conn, sub, "da_ky", user["id"], f"UNC {unc_ref}",
               {"signed_at": clock.now(conn), "signed_by": user["id"], "unc_ref": unc_ref, "unc_amount": int(unc_amount)})
    notify.to_bqt(conn, f"{sub['code']} đã ký UNC", f"Tham chiếu {unc_ref}", link(sub))
    return sub


def close(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user) or user["role"] == "thu_ky", "Chỉ BQT/thư ký được đóng hồ sơ")
    _require(sub["status"] == "da_doi_soat", "Chỉ đóng hồ sơ đã đối soát")
    set_status(conn, sub, "dong", user["id"], "Đóng hồ sơ", {"closed_at": clock.now(conn)})
    return sub


def mark_reported(conn, user, sub_id) -> dict:
    sub = get_sub(conn, sub_id)
    _require(is_bqt(user), "Chỉ BQT được đánh dấu")
    _require(sub["is_emergency"], "Không phải khoản đột xuất")
    update(conn, "submissions", "id", sub_id, {"reported_to_assembly_at": clock.now(conn)})
    audit.log(conn, user["id"], "Đánh dấu đã báo cáo Hội nghị khoản đột xuất", "submission", sub_id)
    return get_sub(conn, sub_id)


# ---------- Cảnh báo Cao: ghi lý do + chủ TK xác nhận ----------------------------------------

def _alert_fund(conn, alert):
    if alert["submission_id"]:
        return get_sub(conn, alert["submission_id"])["fund_code"]
    if alert["statement_txn_id"]:
        r = q1(conn, "SELECT s.fund_code FROM statement_txns t JOIN statements s ON s.id = t.statement_id WHERE t.id = ?",
               (alert["statement_txn_id"],))
        return r["fund_code"] if r else None
    return None


def accept_alert(conn, user, alert_id, reason, false_positive=False) -> dict:
    a = row_dict(q1(conn, "SELECT * FROM alerts WHERE id = ?", (alert_id,)))
    _require(a, "Không tìm thấy cảnh báo")
    _require(a["severity"] == "cao", "Chỉ cảnh báo mức Cao mới được chấp nhận có lý do. Mức Chặn không bỏ qua được")
    _require(a["status"] == "open", "Cảnh báo đã được xử lý")
    _require(is_bqt(user), "Chỉ thành viên BQT được chấp nhận cảnh báo")
    _require(reason and reason.strip(), "Bắt buộc ghi lý do")
    data = {"accepted_by": user["id"], "accept_reason": reason.strip(), "accepted_at": clock.now(conn),
            "false_positive": 1 if false_positive else 0}
    fund = _alert_fund(conn, a)
    if is_signer(conn, user, fund) if fund else user["is_account_holder"]:
        data |= {"confirmed_by": user["id"], "confirmed_at": clock.now(conn), "status": "accepted"}
    update(conn, "alerts", "id", alert_id, data)
    audit.log(conn, user["id"], f"Chấp nhận cảnh báo {a['rule_id']}", "alert", alert_id, a, data)
    if data.get("status") != "accepted":
        notify.send(conn, notify.account_holder_ids(conn, fund), f"Cần chủ TK xác nhận cảnh báo {a['rule_id']}",
                    reason, f"/to-trinh/{a['submission_id']}" if a["submission_id"] else "/canh-bao")
    return data


def confirm_alert(conn, user, alert_id) -> None:
    a = row_dict(q1(conn, "SELECT * FROM alerts WHERE id = ?", (alert_id,)))
    _require(a and a["status"] == "open" and a["accept_reason"], "Cảnh báo chưa có lý do để xác nhận")
    fund = _alert_fund(conn, a)
    _require(is_signer(conn, user, fund) if fund else user["is_account_holder"],
             "Chỉ chủ tài khoản được xác nhận cảnh báo Cao")
    data = {"confirmed_by": user["id"], "confirmed_at": clock.now(conn), "status": "accepted"}
    update(conn, "alerts", "id", alert_id, data)
    audit.log(conn, user["id"], f"Chủ TK xác nhận cảnh báo {a['rule_id']}", "alert", alert_id, a, data)
