"""Lệnh quản trị cho lần cài đặt thật (không dùng dữ liệu demo).

    python -m app.manage init
    python -m app.manage create-user <username> "<Họ tên>" <bqt|thu_ky|bql|admin> [--chair] [--account-holder]
    python -m app.manage add-fund <BT|VH> "<Ngân hàng>" <số TK> <số dư đầu ngày go-live> <YYYY-MM-DD go-live>
    python -m app.manage add-signer <BT|VH> <username>
    python -m app.manage set-password <username>
    python -m app.manage run-jobs    # tác vụ theo lịch (nhắc biểu quyết, hết hạn, R-16, R-17, R-22) – chạy hằng ngày
    python -m app.manage backup <đường dẫn file>   # sao lưu an toàn cơ sở dữ liệu khi ứng dụng đang chạy
    python -m app.manage demo        # chỉ dùng cho máy demo: xóa DB và nạp dữ liệu mẫu

Mọi thao tác đều ghi nhật ký kiểm toán.
"""
import argparse
import getpass
import sys

from . import audit, seed
from . import settings as S
from .auth import hash_password
from .db import connect, db_path, init_db, insert, q1


def _conn():
    c = connect()
    init_db(c)
    return c


def cmd_init(args):
    c = _conn()
    if q1(c, "SELECT 1 FROM cost_types"):
        print("Cơ sở dữ liệu đã được khởi tạo trước đó – không làm gì thêm.")
        return
    for code, name, op, emer in seed.COST_TYPES:
        insert(c, "cost_types", {"code": code, "name": name, "is_operational": op, "emergency_allowed": emer})
    for t in seed.TIERS:
        insert(c, "approval_tiers", dict(zip(("level", "min_amount", "rule_type", "required_count", "require_chair",
                                              "in_person", "description"), t)))
    audit.log(c, None, "Khởi tạo cơ sở dữ liệu", "system")
    c.commit()
    print(f"Đã khởi tạo {db_path()}. Loại chi phí và cấp duyệt đang là GIÁ TRỊ MẪU – sửa theo Quy chế thu chi (Q1).")


def cmd_create_user(args):
    c = _conn()
    if args.role not in ("bqt", "thu_ky", "bql", "admin"):
        sys.exit("Vai trò phải là bqt, thu_ky, bql hoặc admin")
    if (args.chair or args.account_holder) and args.role != "bqt":
        sys.exit("Chỉ thành viên BQT mới là Trưởng ban / chủ tài khoản")
    pw = args.password or getpass.getpass("Mật khẩu: ")
    if len(pw) < 10:
        sys.exit("Mật khẩu tối thiểu 10 ký tự")
    uid = insert(c, "users", {"username": args.username, "full_name": args.full_name, "role": args.role,
                              "is_chair": int(args.chair), "is_account_holder": int(args.account_holder),
                              "password_hash": hash_password(pw)})
    audit.log(c, None, "Tạo người dùng (dòng lệnh)", "user", uid, None,
              {"username": args.username, "role": args.role, "account_holder": args.account_holder})
    c.commit()
    print(f"Đã tạo {args.username}")


def cmd_set_password(args):
    c = _conn()
    u = q1(c, "SELECT id FROM users WHERE username = ?", (args.username,))
    if not u:
        sys.exit("Không có người dùng này")
    pw = getpass.getpass("Mật khẩu mới: ")
    if len(pw) < 10:
        sys.exit("Mật khẩu tối thiểu 10 ký tự")
    c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(pw), u["id"]))
    audit.log(c, None, "Đặt lại mật khẩu (dòng lệnh)", "user", u["id"])
    c.commit()
    print("Đã đổi mật khẩu")


def cmd_add_fund(args):
    c = _conn()
    names = {"BT": "Quỹ bảo trì", "VH": "Quỹ vận hành"}
    insert(c, "funds", {"code": args.code, "name": names[args.code], "bank": args.bank, "account_no": args.account_no,
                        "account_locked": 1 if args.code == "BT" else 0, "opening_balance": args.opening_balance,
                        "opening_date": args.golive})
    if args.code == "BT":
        S.set_raw(c, "golive_date", args.golive)
    audit.log(c, None, "Thiết lập tài khoản quỹ (F-00)", "fund", args.code, None, vars(args) | {"func": None})
    c.commit()
    print(f"Đã thêm {names[args.code]}" + (" – số tài khoản đã khóa (R-24)" if args.code == "BT" else ""))


def cmd_add_signer(args):
    c = _conn()
    u = q1(c, "SELECT * FROM users WHERE username = ?", (args.username,))
    if not u or not u["is_account_holder"]:
        sys.exit("Người dùng không tồn tại hoặc chưa được đánh dấu là chủ tài khoản")
    insert(c, "fund_signers", {"fund_code": args.code, "user_id": u["id"]})
    audit.log(c, None, "Đăng ký chủ tài khoản quỹ", "fund", args.code, None, {"username": args.username})
    c.commit()
    print("Đã đăng ký")


def cmd_run_jobs(args):
    from . import jobs
    c = _conn()
    jobs.run_daily(c)
    c.commit()
    print("Đã chạy tác vụ theo lịch")


def cmd_backup(args):
    import sqlite3
    src = connect()
    dst = sqlite3.connect(args.target)
    src.backup(dst)
    dst.close()
    print(f"Đã sao lưu vào {args.target}")


def cmd_demo(args):
    seed.build()
    print(f"Đã nạp dữ liệu demo vào {db_path()} – mật khẩu chung: {seed.DEMO_PASSWORD}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m app.manage")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(func=cmd_init)
    s = sub.add_parser("create-user")
    s.add_argument("username"); s.add_argument("full_name"); s.add_argument("role")
    s.add_argument("--chair", action="store_true"); s.add_argument("--account-holder", action="store_true")
    s.add_argument("--password", help=argparse.SUPPRESS)
    s.set_defaults(func=cmd_create_user)
    s = sub.add_parser("set-password"); s.add_argument("username"); s.set_defaults(func=cmd_set_password)
    s = sub.add_parser("add-fund")
    s.add_argument("code", choices=["BT", "VH"]); s.add_argument("bank"); s.add_argument("account_no")
    s.add_argument("opening_balance", type=int); s.add_argument("golive")
    s.set_defaults(func=cmd_add_fund)
    s = sub.add_parser("add-signer"); s.add_argument("code", choices=["BT", "VH"]); s.add_argument("username")
    s.set_defaults(func=cmd_add_signer)
    sub.add_parser("run-jobs").set_defaults(func=cmd_run_jobs)
    s = sub.add_parser("backup"); s.add_argument("target"); s.set_defaults(func=cmd_backup)
    sub.add_parser("demo").set_defaults(func=cmd_demo)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
