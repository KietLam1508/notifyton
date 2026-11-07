"""Cấu hình ngưỡng. Giá trị mặc định chỉ là ví dụ – chờ Quy chế thu chi Skyline (Q1, Q5)."""

DEFAULTS: dict[str, tuple[str, str]] = {
    # key: (giá trị mặc định, mô tả)
    "golive_date": ("2026-10-01", "Ngày go-live (F-00)"),
    "r08_over_pct": ("10", "R-08: % vượt dự toán hạng mục thì cảnh báo"),
    "r11_price_pct": ("15", "R-11: % đơn giá cao hơn trung bình báo giá/lịch sử"),
    "quote_threshold": ("50000000", "R-11: khoản chi từ mức này cần đủ số báo giá (đồng)"),
    "min_quotes": ("3", "R-11: số báo giá tối thiểu"),
    "cash_limit": ("5000000", "R-07: mức tối đa được chi tiền mặt (đồng)"),
    "vote_days": ("3", "Hạn biểu quyết (ngày làm việc)"),
    "vote_reminder_days": ("1", "Nhắc biểu quyết sau (ngày làm việc)"),
    "min_quorum": ("3", "Số thành viên BQT tối thiểu được biểu quyết (Q5)"),
    "online_vote_valid": ("1", "Biểu quyết trực tuyến thay được cuộc họp (1 = có, 0 = chỉ ghi nhận ý kiến) – Q5"),
    "vh_bqt_signs": ("1", "BQT ký UNC quỹ vận hành (Q2). 0 = chế độ giám sát báo cáo"),
    "r09_window_days": ("30", "R-09: cửa sổ phát hiện chia nhỏ (ngày)"),
    "r17_days": ("5", "R-17: số ngày làm việc để phân loại giao dịch"),
    "r22_days": ("3", "R-22: số ngày làm việc ngân hàng phải chuyển tiền"),
    "disclosure_dates": ("01-15,07-15", "R-16: hạn công khai 6 tháng (MM-DD, cách nhau dấu phẩy)"),
    "disclosure_remind_days": ("14", "R-16: nhắc trước hạn công khai (ngày)"),
    "next_assembly_date": ("2027-03-15", "R-16: ngày Hội nghị nhà chung cư gần nhất"),
    "deposit_remind_days": ("7", "R-16: nhắc tiền gửi đáo hạn trước (ngày)"),
    "holidays": ("2027-01-01", "Ngày nghỉ lễ (YYYY-MM-DD, cách nhau dấu phẩy)"),
}

# Các khóa không phải ngưỡng nghiệp vụ, không đi qua quy trình duyệt
INTERNAL_PREFIXES = ("_", "demo_today")


def get(conn, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row is not None:
        return row[0]
    if key in DEFAULTS:
        return DEFAULTS[key][0]
    return default


def get_int(conn, key: str) -> int:
    return int(float(get(conn, key) or 0))


def get_float(conn, key: str) -> float:
    return float(get(conn, key) or 0)


def set_raw(conn, key: str, value: str) -> None:
    """Chỉ gọi từ nơi đã qua kiểm soát (áp dụng thay đổi cấu hình đã duyệt, seed, ngày demo)."""
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def rule_enabled(conn, rule_id: str) -> bool:
    return get(conn, f"rule_off:{rule_id}") != "1"
