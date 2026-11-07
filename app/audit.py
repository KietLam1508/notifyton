"""F-08: nhật ký kiểm toán dạng chuỗi băm (hash chain).

- Trigger SQLite chặn UPDATE/DELETE trên bảng audit_log (kể cả quản trị qua ứng dụng).
- Mỗi dòng chứa băm của dòng trước; `verify_chain` phát hiện nếu ai đó sửa file DB ngoài ứng dụng.
"""
import hashlib
import json

from . import clock

GENESIS = "0" * 64


def _dump(obj) -> str | None:
    if obj is None:
        return None
    if hasattr(obj, "keys"):
        obj = {k: obj[k] for k in obj.keys()}
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)


def _digest(prev_hash, ts, user_id, action, entity, entity_id, before, after) -> str:
    payload = "|".join(str(x) for x in (prev_hash, ts, user_id, action, entity, entity_id, before, after))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def log(conn, user_id, action: str, entity: str, entity_id=None, before=None, after=None) -> None:
    prev = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    prev_hash = prev[0] if prev else GENESIS
    ts = clock.now(conn)
    b, a = _dump(before), _dump(after)
    eid = None if entity_id is None else str(entity_id)
    h = _digest(prev_hash, ts, user_id, action, entity, eid, b, a)
    conn.execute(
        "INSERT INTO audit_log(ts, user_id, action, entity, entity_id, before_json, after_json, prev_hash, hash)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (ts, user_id, action, entity, eid, b, a, prev_hash, h),
    )


def verify_chain(conn) -> tuple[bool, int | None]:
    """Trả về (hợp lệ, id dòng đầu tiên bị sai)."""
    prev_hash = GENESIS
    for r in conn.execute("SELECT * FROM audit_log ORDER BY id"):
        expect = _digest(prev_hash, r["ts"], r["user_id"], r["action"], r["entity"], r["entity_id"],
                         r["before_json"], r["after_json"])
        if r["prev_hash"] != prev_hash or r["hash"] != expect:
            return False, r["id"]
        prev_hash = r["hash"]
    return True, None
