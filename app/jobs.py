"""Tác vụ theo lịch: nhắc/hết hạn biểu quyết (6.2), R-16, R-17, R-22.

Chạy idempotent: mỗi việc có khóa trong bảng job_runs nên chạy lại nhiều lần trong ngày không gửi trùng.
"""
from datetime import date, timedelta

from . import clock, notify, reconcile, rules
from . import settings as S
from .db import q, q1
from .workflow import get_sub, set_status, tally


def _once(conn, key) -> bool:
    if q1(conn, "SELECT 1 FROM job_runs WHERE job_key = ?", (key,)):
        return False
    conn.execute("INSERT INTO job_runs(job_key, ran_at) VALUES (?, ?)", (key, clock.now(conn)))
    return True


def _reminder_alert(conn, msg):
    if not q1(conn, "SELECT 1 FROM alerts WHERE rule_id = 'R-16' AND message = ? AND status = 'open'", (msg,)):
        conn.execute("INSERT INTO alerts(rule_id, severity, checkpoint, message, created_at) VALUES ('R-16','nhac','Lịch',?,?)",
                     (msg, clock.now(conn)))


def vote_jobs(conn) -> None:
    today = clock.today(conn)
    remind_after = S.get_int(conn, "vote_reminder_days")
    for row in q(conn, "SELECT id FROM submissions WHERE status = 'cho_bieu_quyet'"):
        sub = get_sub(conn, row["id"])
        t = tally(conn, sub)
        if today.isoformat() > sub["vote_deadline"]:
            set_status(conn, sub, "can_hop", None,
                       f"Hết hạn biểu quyết, mới có {len(t['yes']) + len(t['no'])}/{len(t['eligible'])} phiếu")
            notify.send(conn, [m["id"] for m in t["eligible"]], f"{sub['code']}: hết hạn biểu quyết – cần họp trực tiếp",
                        "", f"/to-trinh/{sub['id']}")
            continue
        if clock.business_days_between(conn, sub["vote_opened_at"], today) >= remind_after and \
                _once(conn, f"vote-remind:{sub['id']}"):
            notify.send(conn, [m["id"] for m in t["pending"]], f"Nhắc biểu quyết {sub['code']}",
                        f"Hạn {date.fromisoformat(sub['vote_deadline']).strftime('%d/%m/%Y')}", f"/to-trinh/{sub['id']}")


def r16_jobs(conn) -> None:
    today = clock.today(conn)
    # 1) Hạn công khai chi tiêu quỹ bảo trì 6 tháng
    remind = S.get_int(conn, "disclosure_remind_days")
    for part in (S.get(conn, "disclosure_dates") or "").split(","):
        part = part.strip()
        if not part:
            continue
        mm, dd = (int(x) for x in part.split("-"))
        for y in (today.year, today.year + 1):
            due = date(y, mm, dd)
            if today <= due <= today + timedelta(days=remind):
                msg = f"Sắp đến hạn công khai chi tiêu quỹ bảo trì 6 tháng: {due.strftime('%d/%m/%Y')}"
                _reminder_alert(conn, msg)
                if _once(conn, f"r16-disclosure:{due}"):
                    notify.to_bqt(conn, "R-16: hạn công khai 6 tháng", msg, "/", include_secretary=True)
    # 2) Khoản đột xuất chưa báo cáo Hội nghị
    pending = q(conn, "SELECT code FROM submissions WHERE is_emergency = 1 AND reported_to_assembly_at IS NULL"
                      " AND status IN ('da_duyet','san_sang_ky','da_ky','da_doi_soat','dong')")
    if pending:
        assembly = S.get(conn, "next_assembly_date")
        msg = (f"{len(pending)} khoản bảo trì đột xuất chưa báo cáo Hội nghị ({', '.join(r['code'] for r in pending)})."
               f" Hội nghị gần nhất: {assembly}")
        _reminder_alert(conn, msg)
        if _once(conn, f"r16-emergency:{today.isoformat()[:7]}:{len(pending)}"):
            notify.to_bqt(conn, "R-16: khoản đột xuất chờ báo cáo Hội nghị", msg, "/")
    # 3) Tiền gửi có kỳ hạn sắp đáo hạn
    days = S.get_int(conn, "deposit_remind_days")
    for d in q(conn, "SELECT * FROM term_deposits WHERE status = 'active'"):
        mat = date.fromisoformat(d["maturity_date"])
        if today <= mat <= today + timedelta(days=days):
            msg = (f"Tiền gửi có kỳ hạn {rules.fmt(d['amount'])} tại {d['bank']} ({d['fund_code']}) "
                   f"đáo hạn ngày {mat.strftime('%d/%m/%Y')}")
            _reminder_alert(conn, msg)
            if _once(conn, f"r16-deposit:{d['id']}:{d['maturity_date']}"):
                notify.to_bqt(conn, "R-16: tiền gửi sắp đáo hạn", msg, "/", include_secretary=True)


def run_daily(conn, force=False) -> bool:
    key = f"daily:{clock.today(conn).isoformat()}"
    if not force and not _once(conn, key):
        return False
    vote_jobs(conn)
    r16_jobs(conn)
    reconcile.check_r17(conn)
    reconcile.check_r22(conn)
    conn.commit()
    return True
