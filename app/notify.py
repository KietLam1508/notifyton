"""F-09: thông báo trong ứng dụng (kênh MVP). Email/Zalo cắm vào hàm `_deliver_external` sau."""
from . import clock
from .db import q


def send(conn, user_ids, title: str, body: str = "", link: str = "") -> None:
    ts = clock.now(conn)
    for uid in sorted(set(user_ids)):
        conn.execute(
            "INSERT INTO notifications(user_id, created_at, title, body, link) VALUES (?,?,?,?,?)",
            (uid, ts, title, body, link),
        )


def bqt_ids(conn) -> list[int]:
    return [r["id"] for r in q(conn, "SELECT id FROM users WHERE role = 'bqt' AND active = 1")]


def role_ids(conn, *roles) -> list[int]:
    marks = ",".join("?" for _ in roles)
    return [r["id"] for r in q(conn, f"SELECT id FROM users WHERE active = 1 AND role IN ({marks})", roles)]


def account_holder_ids(conn, fund_code: str | None = None) -> list[int]:
    if fund_code:
        rows = q(conn, "SELECT u.id FROM users u JOIN fund_signers f ON f.user_id = u.id"
                       " WHERE f.fund_code = ? AND u.active = 1", (fund_code,))
    else:
        rows = q(conn, "SELECT id FROM users WHERE is_account_holder = 1 AND active = 1")
    return [r["id"] for r in rows]


def to_bqt(conn, title, body="", link="", include_secretary=False):
    ids = bqt_ids(conn)
    if include_secretary:
        ids += role_ids(conn, "thu_ky")
    send(conn, ids, title, body, link)
