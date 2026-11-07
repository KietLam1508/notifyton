"""F-10 Dashboard quỹ, chỉ số thành công (mục 12) và chạy thử rule trên dữ liệu lịch sử (F-04)."""
from collections import defaultdict
from datetime import date
from statistics import mean

from . import clock, rules
from . import settings as S
from .constants import COMMITTED, STATUS
from .db import q, q1


def fund_summary(conn):
    out = []
    for f in q(conn, "SELECT * FROM funds ORDER BY code"):
        st = q1(conn, "SELECT * FROM statements WHERE fund_code = ? ORDER BY period_to DESC LIMIT 1", (f["code"],))
        balance = st["closing_balance"] if st else f["opening_balance"]
        deposits = conn.execute("SELECT COALESCE(SUM(amount),0) FROM term_deposits WHERE fund_code = ? AND status = 'active'",
                                (f["code"],)).fetchone()[0]
        out.append({"fund": dict(f), "balance": balance, "balance_date": st["period_to"] if st else f["opening_date"],
                    "deposits": deposits, "interest": f["interest_unused"],
                    "total": balance + deposits + f["interest_unused"]})
    return out


def budget_table(conn, fund_code):
    plan = rules.active_plan(conn, fund_code, clock.today(conn))
    if not plan:
        return None, []
    pct = S.get_float(conn, "r08_over_pct")
    rows = []
    for it in q(conn, "SELECT * FROM plan_items WHERE plan_id = ? ORDER BY code", (plan["id"],)):
        since = rules.item_spent(conn, fund_code, it["code"], plan["year"])
        total = it["spent_before_golive"] + since
        ratio = total * 100 / it["budget"] if it["budget"] else 0
        level = "danger" if ratio > 100 + pct else "warn" if ratio >= 100 else "ok"
        rows.append({**dict(it), "since": since, "total": total, "ratio": ratio, "level": level})
    return dict(plan), rows


def status_counts(conn):
    counts = {k: 0 for k in STATUS}
    for r in q(conn, "SELECT status, COUNT(*) n FROM submissions GROUP BY status"):
        counts[r["status"]] = r["n"]
    return counts


def emergency_pending(conn):
    marks = ",".join("?" for _ in COMMITTED)
    return [dict(r) for r in q(conn, f"SELECT * FROM submissions WHERE is_emergency = 1 AND reported_to_assembly_at IS NULL"
                                     f" AND status IN ({marks}) ORDER BY id", COMMITTED)]


def alert_counts(conn):
    out = {"chan": 0, "cao": 0, "tb": 0, "nhac": 0}
    for r in q(conn, "SELECT a.severity, COUNT(*) n FROM alerts a LEFT JOIN submissions s ON s.id = a.submission_id"
                     " WHERE a.status = 'open' AND (s.id IS NULL OR s.status <> 'huy') GROUP BY a.severity"):
        out[r["severity"]] = r["n"]
    return out


def metrics(conn):
    """Một số chỉ số ở mục 12 tính được từ dữ liệu trong công cụ."""
    today = clock.today(conn)
    month = today.isoformat()[:7]
    r21 = conn.execute("SELECT COUNT(*) FROM alerts WHERE rule_id = 'R-21' AND substr(created_at,1,7) = ?",
                       (month,)).fetchone()[0]
    accepted = q(conn, "SELECT false_positive FROM alerts WHERE severity = 'cao' AND status = 'accepted'")
    fp = (sum(1 for a in accepted if a["false_positive"]) * 100 / len(accepted)) if accepted else None
    txns = q(conn, "SELECT match_status FROM statement_txns")
    explained = (sum(1 for t in txns if t["match_status"] in ("da_khop", "da_phan_loai")) * 100 / len(txns)) if txns else None
    durations = []
    for s in q(conn, "SELECT submitted_at, signed_at FROM submissions WHERE signed_at IS NOT NULL AND submitted_at IS NOT NULL"):
        durations.append((clock.to_date(s["signed_at"]) - clock.to_date(s["submitted_at"])).days)
    returned = conn.execute("SELECT COUNT(*) FROM status_history WHERE to_status = 'yeu_cau_bo_sung' AND substr(at,1,7) = ?",
                            (month,)).fetchone()[0]
    votes_total = votes_on_time = 0
    for s in q(conn, "SELECT id, vote_deadline FROM submissions WHERE vote_deadline IS NOT NULL AND status <> 'huy'"):
        for v in q(conn, "SELECT cast_at FROM votes WHERE submission_id = ? AND superseded = 0", (s["id"],)):
            votes_total += 1
            votes_on_time += v["cast_at"][:10] <= s["vote_deadline"]
    return {"r21_month": r21, "false_positive_pct": fp, "explained_pct": explained,
            "avg_days_to_sign": mean(durations) if durations else None, "returned_month": returned,
            "votes_on_time_pct": (votes_on_time * 100 / votes_total) if votes_total else None}


def maturing_deposits(conn, days=30):
    today = clock.today(conn)
    rows = []
    for d in q(conn, "SELECT * FROM term_deposits WHERE status = 'active' ORDER BY maturity_date"):
        left = (date.fromisoformat(d["maturity_date"]) - today).days
        rows.append({**dict(d), "days_left": left})
    return rows


# ---------- F-04: chạy thử rule trên dữ liệu lịch sử ------------------------------------------

def backtest(conn) -> dict:
    hist = [dict(r) for r in q(conn, "SELECT * FROM history_payments ORDER BY pay_date")]
    window = S.get_int(conn, "r09_window_days")
    boundaries = [t["min_amount"] for t in rules.tiers(conn) if t["min_amount"] > 0]
    pct = S.get_float(conn, "r11_price_pct")
    out = {"R-09": [], "R-18": [], "R-11": [], "total": len(hist)}
    # R-09: chia nhỏ theo nhà cung cấp
    by_vendor = defaultdict(list)
    for h in hist:
        by_vendor[h["vendor_tax_code"]].append(h)
    seen = set()
    for tax, items in by_vendor.items():
        for i, h in enumerate(items):
            d0 = date.fromisoformat(h["pay_date"])
            group = [x for x in items[: i + 1] if (d0 - date.fromisoformat(x["pay_date"])).days <= window]
            amounts = [x["amount"] for x in group]
            for b in boundaries:
                key = (tax, tuple(x["id"] for x in group))
                if len(group) >= 2 and max(amounts) < b <= sum(amounts) and key not in seen:
                    seen.add(key)
                    out["R-09"].append(f"{h['vendor_name']}: {len(group)} khoản trong {window} ngày "
                                       f"({', '.join(x['pay_date'] for x in group)}), tổng {rules.fmt(sum(amounts))} "
                                       f"vượt ngưỡng {rules.fmt(b)}")
    # R-18: hóa đơn trùng
    inv = defaultdict(list)
    for h in hist:
        if h["invoice_no"]:
            inv[(h["invoice_no"], h["vendor_tax_code"])].append(h)
    for (no, tax), items in inv.items():
        if len(items) > 1:
            out["R-18"].append(f"Hóa đơn {no} (MST {tax}) xuất hiện {len(items)} lần")
    # R-11: đơn giá lệch lịch sử
    by_key = defaultdict(list)
    for h in hist:
        if h["service_key"] and h["unit_price"]:
            by_key[h["service_key"]].append(h)
    for key, items in by_key.items():
        for i, h in enumerate(items[1:], start=1):
            avg = mean(x["unit_price"] for x in items[:i])
            if h["unit_price"] > avg * (1 + pct / 100):
                out["R-11"].append(f"{h['vendor_name']} {h['pay_date']}: đơn giá {rules.fmt(h['unit_price'])} > "
                                   f"trung bình {rules.fmt(avg)} quá {pct:.0f}%")
    return out
