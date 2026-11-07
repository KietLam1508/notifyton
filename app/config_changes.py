"""F-01: thay đổi cấu hình qua quy trình đề xuất → duyệt (người đề xuất ≠ người duyệt), R-24."""
import json

from . import audit, clock, notify, rules
from . import settings as S
from .db import insert, q, q1, row_dict, update
from .workflow import WorkflowError, _require

KINDS = {
    "setting": "Đổi ngưỡng",
    "tier": "Đổi cấp duyệt",
    "rule_toggle": "Bật/tắt rule [T]",
    "fund_account": "Đổi số tài khoản quỹ",
    "contract_account": "Đổi tài khoản thụ hưởng hợp đồng",
}


def propose(conn, user, kind, payload: dict, description: str, attachment_path=None) -> int:
    _require(kind in KINDS, "Loại thay đổi không hợp lệ")
    _require(user["role"] in ("admin", "bqt"), "Chỉ quản trị hệ thống hoặc thành viên BQT được đề xuất thay đổi cấu hình")
    # Nguyên tắc tách quyền 1: người cấu hình ngưỡng/rule ≠ người ký UNC
    _require(not user["is_account_holder"], "Chủ tài khoản không được đề xuất thay đổi cấu hình (tách quyền với người ký UNC)")
    if kind == "setting":
        _require(payload.get("key") in S.DEFAULTS, "Ngưỡng không tồn tại")
        _require(str(payload.get("value", "")).strip() != "", "Giá trị không được trống")
    elif kind == "rule_toggle":
        r = rules.RULES.get(payload.get("rule_id"))
        _require(r is not None, "Rule không tồn tại")
        _require(r.toggleable, f"{r.id} có nguồn {r.source_label}: không có nút tắt")
    elif kind == "fund_account":
        fund = q1(conn, "SELECT * FROM funds WHERE code = ?", (payload.get("fund_code"),))
        _require(fund is not None, "Quỹ không tồn tại")
        if fund["account_locked"]:
            _require(attachment_path, "R-24: Đổi tài khoản kinh phí bảo trì đã khóa phải đính kèm văn bản căn cứ "
                                      "(ví dụ thông báo sáp nhập ngân hàng)")
    elif kind == "tier":
        _require(payload.get("rule_type") in ("count", "majority", "all"), "Kiểu tỷ lệ không hợp lệ")
    elif kind == "contract_account":
        _require(q1(conn, "SELECT 1 FROM contracts WHERE id = ?", (payload.get("contract_id"),)), "Hợp đồng không tồn tại")
    cid = insert(conn, "config_changes", {"kind": kind, "description": description or KINDS[kind],
                                          "payload": json.dumps(payload, ensure_ascii=False),
                                          "attachment_path": attachment_path, "proposed_by": user["id"],
                                          "proposed_at": clock.now(conn)})
    audit.log(conn, user["id"], f"Đề xuất thay đổi cấu hình: {KINDS[kind]}", "config_change", cid, None, payload)
    notify.send(conn, [u for u in notify.bqt_ids(conn) if u != user["id"]], "Có đề xuất thay đổi cấu hình chờ duyệt",
                description, "/cau-hinh")
    return cid


def required_approvers(conn, change) -> list[int] | None:
    """None = một thành viên BQT bất kỳ (≠ người đề xuất). R-24: toàn bộ chủ TK của quỹ."""
    if change["kind"] == "fund_account":
        p = json.loads(change["payload"])
        fund = q1(conn, "SELECT * FROM funds WHERE code = ?", (p["fund_code"],))
        if fund["account_locked"]:
            return [r["user_id"] for r in q(conn, "SELECT user_id FROM fund_signers WHERE fund_code = ?", (p["fund_code"],))]
    return None


def decide(conn, user, change_id, decision, note="") -> str:
    ch = row_dict(q1(conn, "SELECT * FROM config_changes WHERE id = ?", (change_id,)))
    _require(ch and ch["status"] == "pending", "Đề xuất không còn chờ duyệt")
    _require(user["role"] == "bqt", "Chỉ thành viên BQT được duyệt thay đổi cấu hình")
    _require(user["id"] != ch["proposed_by"], "Người đề xuất không tự duyệt được")
    _require(decision in ("approve", "reject"), "Quyết định không hợp lệ")
    need = required_approvers(conn, ch)
    if need is not None:
        _require(user["id"] in need, "R-24: chỉ chủ tài khoản của quỹ được duyệt đổi tài khoản")
    _require(not q1(conn, "SELECT 1 FROM config_change_approvals WHERE change_id = ? AND user_id = ?",
                    (change_id, user["id"])), "Bạn đã cho ý kiến")
    insert(conn, "config_change_approvals", {"change_id": change_id, "user_id": user["id"], "decision": decision,
                                             "at": clock.now(conn), "note": note})
    audit.log(conn, user["id"], f"{'Duyệt' if decision == 'approve' else 'Từ chối'} thay đổi cấu hình", "config_change",
              change_id, None, {"note": note})
    if decision == "reject":
        update(conn, "config_changes", "id", change_id, {"status": "rejected", "decided_at": clock.now(conn)})
        return "rejected"
    approved = {r["user_id"] for r in q(conn, "SELECT user_id FROM config_change_approvals WHERE change_id = ?"
                                              " AND decision = 'approve'", (change_id,))}
    if need is not None and not set(need) <= approved:
        return "pending"
    _apply(conn, user, ch)
    update(conn, "config_changes", "id", change_id, {"status": "approved", "decided_at": clock.now(conn)})
    return "approved"


def _apply(conn, user, ch) -> None:
    p = json.loads(ch["payload"])
    kind = ch["kind"]
    if kind == "setting":
        before = S.get(conn, p["key"])
        S.set_raw(conn, p["key"], p["value"])
        audit.log(conn, user["id"], f"Áp dụng ngưỡng {p['key']}", "setting", p["key"], {"value": before}, {"value": p["value"]})
    elif kind == "rule_toggle":
        S.set_raw(conn, f"rule_off:{p['rule_id']}", "0" if p["enabled"] else "1")
        audit.log(conn, user["id"], f"{'Bật' if p['enabled'] else 'Tắt'} rule {p['rule_id']}", "rule", p["rule_id"])
    elif kind == "tier":
        before = row_dict(q1(conn, "SELECT * FROM approval_tiers WHERE level = ?", (p["level"],)))
        conn.execute("INSERT INTO approval_tiers(level, min_amount, rule_type, required_count, require_chair, in_person,"
                     " description) VALUES (?,?,?,?,?,?,?) ON CONFLICT(level) DO UPDATE SET min_amount = excluded.min_amount,"
                     " rule_type = excluded.rule_type, required_count = excluded.required_count,"
                     " require_chair = excluded.require_chair, in_person = excluded.in_person,"
                     " description = excluded.description",
                     (p["level"], int(p["min_amount"]), p["rule_type"], int(p.get("required_count") or 0),
                      1 if p.get("require_chair") else 0, 1 if p.get("in_person") else 0, p.get("description", "")))
        audit.log(conn, user["id"], f"Áp dụng cấp duyệt {p['level']}", "approval_tier", p["level"], before, p)
    elif kind == "fund_account":
        fund = row_dict(q1(conn, "SELECT * FROM funds WHERE code = ?", (p["fund_code"],)))
        S.set_raw(conn, "_r24_unlock", "1")
        try:
            conn.execute("UPDATE funds SET account_no = ? WHERE code = ?", (p["account_no"], p["fund_code"]))
        finally:
            S.set_raw(conn, "_r24_unlock", "0")
        audit.log(conn, user["id"], "Đổi số tài khoản quỹ (ngoại lệ R-24 đã đủ chủ TK duyệt)", "fund", p["fund_code"],
                  {"account_no": fund["account_no"]}, {"account_no": p["account_no"]})
    elif kind == "contract_account":
        c = row_dict(q1(conn, "SELECT * FROM contracts WHERE id = ?", (p["contract_id"],)))
        conn.execute("UPDATE contracts SET beneficiary_account = ? WHERE id = ?", (p["beneficiary_account"], p["contract_id"]))
        audit.log(conn, user["id"], "Đổi tài khoản thụ hưởng hợp đồng", "contract", p["contract_id"],
                  {"beneficiary_account": c["beneficiary_account"]}, p)


def direct_fund_account_edit(conn, user, fund_code, account_no) -> None:
    """Sửa trực tiếp số tài khoản quỹ (không qua quy trình ngoại lệ) – R-24 chặn với quỹ bảo trì."""
    fund = q1(conn, "SELECT * FROM funds WHERE code = ?", (fund_code,))
    if fund["account_locked"]:
        audit.log(conn, user["id"], "R-24: chặn sửa số tài khoản kinh phí bảo trì", "fund", fund_code, None,
                  {"attempted": account_no})
        conn.commit()
        raise WorkflowError("R-24: Số tài khoản kinh phí bảo trì đã khóa sau khi thiết lập. Chỉ đổi được qua quy trình "
                            "ngoại lệ có văn bản căn cứ và toàn bộ chủ TK xác nhận")
    conn.execute("UPDATE funds SET account_no = ? WHERE code = ?", (account_no, fund_code))
    audit.log(conn, user["id"], "Sửa số tài khoản quỹ", "fund", fund_code, {"account_no": fund["account_no"]},
              {"account_no": account_no})
