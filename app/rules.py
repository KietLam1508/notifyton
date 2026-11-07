"""F-04: Rule engine chạy theo điểm kiểm soát (CP1–CP4), mục 6 và mục 8 của PRD.

Mỗi rule là một hàm nhận `Ctx` và trả về danh sách phát hiện. Một phát hiện là chuỗi thông báo
hoặc bộ (thông báo, mức) khi rule cần mức khác mặc định.

Căn cứ pháp lý ghi ở đây là bản nháp: chuyên viên pháp lý cần xác nhận số điều khoản trước go-live.
"""
from dataclasses import dataclass, field
from statistics import mean

from . import clock
from . import settings as S
from .constants import COMMITTED, IN_FLOW, SEVERITY_ORDER
from .db import q, q1, row_dict

LUAT_NHA_O = "Luật Nhà ở 2023 (sửa đổi bởi Luật 43/2024/QH15); NĐ 95/2024/NĐ-CP"
QUY_CHE_BXD = "Quy chế quản lý, sử dụng nhà chung cư kèm TT 05/2024/TT-BXD (sửa đổi bởi TT 09/2025/TT-BXD)"
QUY_CHE_SKYLINE = "Quy chế thu chi tài chính BQT Skyline (chờ Q1)"
HOAT_DONG_SKYLINE = "Quy chế hoạt động BQT Skyline (chờ Q5)"
THUC_HANH = "Khuyến nghị kiểm soát nội bộ"
CHE_TAI = "Chế tài: NĐ 339/2026/NĐ-CP (cần pháp lý xác nhận điều khoản)"


@dataclass
class Rule:
    id: str
    title: str
    severity: str  # chan | cao | tb | nhac
    sources: tuple  # ('L',) ('Q','T') ...
    checkpoints: tuple
    basis: str
    basis_date: str
    derived: bool = False  # [L]* – suy ra từ nghĩa vụ luật định
    fn: object = field(default=None, repr=False)

    @property
    def toggleable(self) -> bool:
        """Chỉ rule thuần [T] được bật/tắt, và chỉ qua quy trình thay đổi cấu hình (F-01)."""
        return set(self.sources) == {"T"}

    @property
    def source_label(self) -> str:
        return "".join(f"[{s}]" for s in self.sources) + ("*" if self.derived else "")


RULES: dict[str, Rule] = {}


def rule(id, title, severity, sources, checkpoints, basis, basis_date, derived=False):
    def deco(fn):
        RULES[id] = Rule(id, title, severity, tuple(sources), tuple(checkpoints), basis, basis_date, derived, fn)
        return fn
    return deco


def register_meta(id, title, severity, sources, checkpoints, basis, basis_date, derived=False):
    """Rule chạy ở module khác (đối soát, lịch, cấu hình) – chỉ khai báo metadata để hiển thị/cấu hình."""
    RULES[id] = Rule(id, title, severity, tuple(sources), tuple(checkpoints), basis, basis_date, derived, None)


def digits(s) -> str:
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def fmt(n) -> str:
    return f"{int(n or 0):,}".replace(",", ".") + " đ"


class Ctx:
    """Toàn bộ dữ liệu một tờ trình cần để chạy rule."""

    def __init__(self, conn, sub_id: int):
        self.conn = conn
        self.sub = row_dict(q1(conn, "SELECT * FROM submissions WHERE id = ?", (sub_id,)))
        s = self.sub
        self.fund = row_dict(q1(conn, "SELECT * FROM funds WHERE code = ?", (s["fund_code"],)))
        self.contract = row_dict(q1(conn, "SELECT * FROM contracts WHERE id = ?", (s["contract_id"],)))
        self.vendor = row_dict(q1(conn, "SELECT * FROM vendors WHERE id = ?", (s["vendor_id"],)))
        self.cost_type = row_dict(q1(conn, "SELECT * FROM cost_types WHERE code = ?", (s["cost_type"],)))
        self.docs = [dict(r) for r in q(conn, "SELECT * FROM documents WHERE submission_id = ? AND cancelled = 0"
                                              " AND superseded_by IS NULL ORDER BY id", (sub_id,))]
        self.today = clock.today(conn)

    def docs_of(self, doc_type):
        return [d for d in self.docs if d["doc_type"] == doc_type]

    @property
    def is_bt(self):
        return self.sub["fund_code"] == "BT"

    @property
    def ref_date(self):
        return clock.to_date(self.sub["submitted_at"] or clock.now(self.conn))

    def setting_int(self, key):
        return S.get_int(self.conn, key)

    def setting_float(self, key):
        return S.get_float(self.conn, key)


# ---------- dữ liệu dùng chung -------------------------------------------------------------

def active_plan(conn, fund_code: str, on_date) -> dict | None:
    """Phiên bản kế hoạch/dự toán đang hiệu lực tại ngày `on_date`."""
    d = clock.to_date(on_date)
    row = q1(conn, "SELECT * FROM plans WHERE fund_code = ? AND year = ? AND effective_from <= ?"
                   " ORDER BY version DESC LIMIT 1", (fund_code, d.year, d.isoformat()))
    return row_dict(row)


def plan_item(conn, plan_id, code):
    return row_dict(q1(conn, "SELECT * FROM plan_items WHERE plan_id = ? AND code = ?", (plan_id, code)))


def item_spent(conn, fund_code, item_code, year, exclude_code=None) -> int:
    """Lũy kế đã cam kết chi của hạng mục trong năm (không gồm số trước go-live)."""
    marks = ",".join("?" for _ in COMMITTED)
    params = [fund_code, item_code, str(year), *COMMITTED]
    sql = (f"SELECT COALESCE(SUM(amount),0) FROM submissions WHERE fund_code = ? AND plan_item_code = ?"
           f" AND substr(created_at,1,4) = ? AND status IN ({marks})")
    if exclude_code:
        sql += " AND code <> ?"
        params.append(exclude_code)
    return conn.execute(sql, params).fetchone()[0]


def tiers(conn):
    return [dict(r) for r in q(conn, "SELECT * FROM approval_tiers ORDER BY min_amount")]


def tier_for(conn, amount) -> dict | None:
    chosen = None
    for t in tiers(conn):
        if amount >= t["min_amount"]:
            chosen = t
    return chosen


def conflicted_users(conn, vendor_id):
    return [dict(r) for r in q(conn, "SELECT u.id, u.full_name, u.role, c.note FROM conflicts c"
                                     " JOIN users u ON u.id = c.user_id WHERE c.vendor_id = ?", (vendor_id,))]


# ---------- Hồ sơ theo checklist F-03 --------------------------------------------------------

def required_docs(ctx: Ctx) -> list[str]:
    s = ctx.sub
    req = ["to_trinh", "hop_dong", "hoa_don"]
    if ctx.is_bt:
        if not s["is_emergency"]:
            req.append("bao_gia")
        # Biên bản nghiệm thu bắt buộc, trừ khi là tạm ứng theo điều khoản hợp đồng
        if not (s["is_advance"] and ctx.contract and ctx.contract["advance_pct"] > 0):
            req.append("nghiem_thu")
    else:
        req.append("bao_gia")
        if s["is_mgmt_fee"]:
            req.append("kpi")
    return req


@rule("HS-01", "Thiếu hồ sơ bắt buộc theo checklist", "chan", ("L", "Q"), ("CP1",),
      f"Checklist F-03; {QUY_CHE_BXD}; {QUY_CHE_SKYLINE}", "2024-08-01")
def hs01(ctx: Ctx):
    from .constants import DOC_TYPES
    missing = [DOC_TYPES[t] for t in required_docs(ctx) if not ctx.docs_of(t)]
    out = [f"Thiếu {name}" for name in missing]
    if ctx.is_bt and ctx.sub["is_emergency"]:
        hd = ctx.docs_of("hop_dong")
        if hd and not any(d["contract_signed"] for d in hd):
            out.append("Hợp đồng bảo trì đột xuất phải là bản đã ký")
    return out


# ---------- CP1 / CP2 ----------------------------------------------------------------------

@rule("R-01", "Chi quỹ bảo trì cho nội dung thuộc quản lý vận hành", "chan", ("L",), ("CP1", "CP2"),
      f"{LUAT_NHA_O}; {QUY_CHE_BXD} – kinh phí bảo trì chỉ dùng cho bảo trì phần sở hữu chung", "2024-08-01")
def r01(ctx: Ctx, cp="CP1"):
    if cp == "CP2" and not ctx.sub["is_emergency"]:
        return []
    if ctx.is_bt and ctx.cost_type and ctx.cost_type["is_operational"]:
        return [f"Loại chi \"{ctx.cost_type['name']}\" thuộc quản lý vận hành, không được chi từ quỹ bảo trì"]
    return []


@rule("R-02", "Hạng mục không thuộc kế hoạch bảo trì đang hiệu lực", "chan", ("L",), ("CP1",),
      f"{QUY_CHE_BXD} – chi theo kế hoạch bảo trì Hội nghị đã thông qua", "2024-08-01")
def r02(ctx: Ctx):
    s = ctx.sub
    if not ctx.is_bt or s["is_emergency"]:
        return []
    plan = active_plan(ctx.conn, "BT", ctx.ref_date)
    if not plan:
        return ["Chưa có kế hoạch bảo trì năm nay được Hội nghị thông qua. Cần trình Hội nghị trước khi chi"]
    if not s["plan_item_code"] or not plan_item(ctx.conn, plan["id"], s["plan_item_code"]):
        return [f"Hạng mục không có trong kế hoạch bảo trì phiên bản {plan['version']} "
                f"(NQ {plan['resolution_no']}). Cần trình Hội nghị bổ sung kế hoạch; "
                f"nếu là sự cố cần xử lý ngay thì đánh dấu đột xuất"]
    return []


@rule("R-03", "Đột xuất nhưng chưa có hợp đồng đã ký hoặc loại chi không được phép chi đột xuất", "chan",
      ("L",), ("CP1",), f"{QUY_CHE_BXD} – bảo trì đột xuất; {QUY_CHE_SKYLINE}", "2024-08-01")
def r03(ctx: Ctx):
    s = ctx.sub
    if not ctx.is_bt or not s["is_emergency"]:
        return []
    out = []
    if not ctx.contract or not ctx.contract["signed_date"]:
        out.append("Bảo trì đột xuất phải có hợp đồng bảo trì đã ký")
    if ctx.cost_type and not ctx.cost_type["emergency_allowed"]:
        out.append(f"Quy chế thu chi không cho phép chi đột xuất cho loại \"{ctx.cost_type['name']}\"")
    return out


@rule("R-05", "Tài khoản nhận tiền khác tài khoản trong hợp đồng", "chan", ("T",), ("CP1", "CP3"),
      THUC_HANH + " – chống chuyển nhầm, gian lận đổi số tài khoản", "2026-11-07")
def r05(ctx: Ctx):
    s = ctx.sub
    if s["payment_method"] != "chuyen_khoan" or not ctx.contract:
        return []
    if digits(s["beneficiary_account"]) != digits(ctx.contract["beneficiary_account"]):
        return [f"Tài khoản trên tờ trình ({s['beneficiary_account'] or 'trống'}) khác tài khoản thụ hưởng "
                f"trong hợp đồng {ctx.contract['contract_no']} ({ctx.contract['beneficiary_account']})"]
    return []


@rule("R-07", "Chi tiền mặt vượt ngưỡng phải chuyển khoản", "chan", ("Q",), ("CP1",),
      QUY_CHE_SKYLINE + " – ngưỡng Hội nghị quy định", "2026-11-07")
def r07(ctx: Ctx):
    limit = ctx.setting_int("cash_limit")
    if ctx.sub["payment_method"] == "tien_mat" and ctx.sub["amount"] > limit:
        return [f"Khoản chi {fmt(ctx.sub['amount'])} vượt mức chi tiền mặt {fmt(limit)}; bắt buộc chuyển khoản"]
    return []


@rule("R-08", "Lũy kế chi hạng mục vượt dự toán", "cao", ("Q", "T"), ("CP1",),
      QUY_CHE_SKYLINE + "; " + THUC_HANH, "2026-11-07")
def r08(ctx: Ctx):
    s = ctx.sub
    if not s["plan_item_code"]:
        return []
    plan = active_plan(ctx.conn, s["fund_code"], ctx.ref_date)
    if not plan:
        return []
    item = plan_item(ctx.conn, plan["id"], s["plan_item_code"])
    if not item or item["budget"] <= 0:
        return []
    pct = ctx.setting_float("r08_over_pct")
    total = item["spent_before_golive"] + item_spent(ctx.conn, s["fund_code"], s["plan_item_code"], plan["year"],
                                                     exclude_code=s["code"]) + s["amount"]
    ratio = total * 100 / item["budget"]
    if total > item["budget"] * (1 + pct / 100):
        return [f"Lũy kế hạng mục \"{item['name']}\" (gồm {fmt(item['spent_before_golive'])} chi trước go-live) "
                f"sẽ là {fmt(total)} = {ratio:.0f}% dự toán {fmt(item['budget'])}, vượt ngưỡng {pct:.0f}%"]
    return []


@rule("R-09", "Dấu hiệu chia nhỏ khoản chi để lách cấp duyệt", "cao", ("T",), ("CP1",),
      THUC_HANH, "2026-11-07")
def r09(ctx: Ctx):
    s = ctx.sub
    window = ctx.setting_int("r09_window_days")
    ref = ctx.ref_date
    rows = [dict(r) for r in q(ctx.conn,
        "SELECT id, code, amount, vendor_id, plan_item_code, status, COALESCE(submitted_at, created_at) AS d"
        " FROM submissions WHERE code <> ? AND status NOT IN ('huy','nhap') AND fund_code = ?"
        " AND (vendor_id = ? OR (plan_item_code IS NOT NULL AND plan_item_code = ?))",
        (s["code"], s["fund_code"], s["vendor_id"], s["plan_item_code"]))]
    rows = [r for r in rows if abs((clock.to_date(r["d"]) - ref).days) <= window]
    boundaries = [t["min_amount"] for t in tiers(ctx.conn) if t["min_amount"] > 0]
    for label, group in (("cùng nhà cung cấp", [r for r in rows if r["vendor_id"] == s["vendor_id"]]),
                         ("cùng hạng mục", [r for r in rows if s["plan_item_code"]
                                            and r["plan_item_code"] == s["plan_item_code"]])):
        if not group:
            continue
        amounts = [r["amount"] for r in group] + [s["amount"]]
        total = sum(amounts)
        for b in boundaries:
            if max(amounts) < b <= total:
                codes = ", ".join(r["code"] + (" (đã từ chối)" if r["status"] == "tu_choi" else "") for r in group)
                return [f"{len(amounts)} tờ trình {label} trong {window} ngày ({codes} và tờ trình này), "
                        f"mỗi khoản dưới ngưỡng cấp duyệt {fmt(b)} nhưng tổng {fmt(total)} vượt ngưỡng"]
    return []


@rule("R-10", "Thanh toán khi chưa nghiệm thu / tạm ứng vượt tỷ lệ hợp đồng", "cao", ("T",), ("CP1",),
      THUC_HANH, "2026-11-07")
def r10(ctx: Ctx):
    s, c = ctx.sub, ctx.contract
    if not c:
        return []
    out = []
    if s["is_advance"]:
        if c["advance_pct"] <= 0:
            out.append(f"Hợp đồng {c['contract_no']} không có điều khoản tạm ứng")
        else:
            cap = (c["value"] + c["addendum_value"]) * c["advance_pct"] / 100
            if s["amount"] > cap:
                out.append(f"Tạm ứng {fmt(s['amount'])} vượt {c['advance_pct']:.0f}% giá trị hợp đồng ({fmt(cap)})")
    elif not ctx.docs_of("nghiem_thu"):
        out.append("Đề nghị thanh toán khi chưa có biên bản nghiệm thu và không phải tạm ứng theo hợp đồng")
    return out


@rule("R-11", "Thiếu báo giá hoặc đơn giá cao bất thường", "cao", ("Q", "T"), ("CP1",),
      QUY_CHE_SKYLINE + "; " + THUC_HANH, "2026-11-07")
def r11(ctx: Ctx):
    s = ctx.sub
    out = []
    quotes = [d for d in ctx.docs_of("bao_gia")]
    need = ctx.setting_int("min_quotes")
    threshold = ctx.setting_int("quote_threshold")
    pct = ctx.setting_float("r11_price_pct")
    # Đột xuất: báo giá "nếu kịp" (F-03) nên không bắt buộc đủ số lượng, vẫn so đơn giá nếu có
    if s["amount"] >= threshold and len(quotes) < need and not s["is_emergency"]:
        out.append(f"Khoản chi từ {fmt(threshold)} cần {need} báo giá, hiện có {len(quotes)}")
    amounts = [d["amount"] for d in quotes if d["amount"]]
    if amounts:
        avg = mean(amounts)
        if s["amount"] > avg * (1 + pct / 100):
            out.append(f"Số tiền {fmt(s['amount'])} cao hơn trung bình báo giá {fmt(avg)} quá {pct:.0f}%")
    if s["service_key"] and s["unit_price"]:
        hist = [r[0] for r in q(ctx.conn, "SELECT unit_price FROM history_payments WHERE service_key = ?"
                                          " AND unit_price IS NOT NULL", (s["service_key"],))]
        marks = ",".join("?" for _ in COMMITTED)
        hist += [r[0] for r in q(ctx.conn, f"SELECT unit_price FROM submissions WHERE service_key = ? AND code <> ?"
                                           f" AND unit_price IS NOT NULL AND status IN ({marks})",
                                 (s["service_key"], s["code"], *COMMITTED))]
        if hist:
            avg = mean(hist)
            if s["unit_price"] > avg * (1 + pct / 100):
                out.append(f"Đơn giá {fmt(s['unit_price'])} cao hơn trung bình lịch sử {fmt(avg)} quá {pct:.0f}%")
    return out


@rule("R-12", "Nhà cung cấp có liên quan đến thành viên BQT / nhân sự BQL", "cao", ("T",), ("CP1", "CP2"),
      THUC_HANH + " – khai báo xung đột lợi ích", "2026-11-07")
def r12(ctx: Ctx, cp="CP1"):
    people = conflicted_users(ctx.conn, ctx.sub["vendor_id"])
    if not people:
        return []
    names = ", ".join(f"{p['full_name']} ({'BQT' if p['role'] == 'bqt' else p['role'].upper()})" for p in people)
    bqt = [p["full_name"] for p in people if p["role"] == "bqt"]
    if cp == "CP2":
        # Ở CP2 chỉ thông báo việc loại phiếu; cảnh báo Cao đã xử lý ở CP1
        return [(f"Loại khỏi biểu quyết do xung đột lợi ích: {', '.join(bqt)}", "tb")] if bqt else []
    msg = f"{ctx.vendor['name']} có liên quan đến: {names}"
    if bqt:
        msg += f". Người liên quan thuộc BQT sẽ bị loại khỏi biểu quyết: {', '.join(bqt)}"
    return [msg]


@rule("R-13", "Mã số thuế nhà cung cấp không hoạt động", "cao", ("T",), ("CP1",),
      THUC_HANH + " – MVP: tra cứu tay, đính kèm ảnh", "2026-11-07")
def r13(ctx: Ctx):
    lookups = ctx.docs_of("tra_cuu_mst")
    if not lookups:
        return [("Chưa đính kèm ảnh tra cứu trạng thái mã số thuế nhà cung cấp", "tb")]
    if any(d["tax_status"] == "ngung_hoat_dong" for d in lookups):
        return [f"Ảnh tra cứu cho thấy MST {ctx.vendor['tax_code']} không ở trạng thái hoạt động"]
    return []


@rule("R-14", "Hóa đơn lệch số tiền, MST hoặc ngày so với tờ trình/hợp đồng", "cao", ("T",), ("CP1",),
      THUC_HANH, "2026-11-07")
def r14(ctx: Ctx):
    s, c, v = ctx.sub, ctx.contract, ctx.vendor
    invoices = ctx.docs_of("hoa_don")
    if not invoices:
        return []
    out = []
    total = sum(d["amount"] or 0 for d in invoices)
    if total != s["amount"]:
        out.append(f"Tổng hóa đơn {fmt(total)} khác số tiền tờ trình {fmt(s['amount'])}")
    for d in invoices:
        if d["seller_tax_code"] and digits(d["seller_tax_code"]) != digits(v["tax_code"]):
            out.append(f"Hóa đơn {d['invoice_no']}: MST người bán {d['seller_tax_code']} khác MST nhà cung cấp {v['tax_code']}")
        if c and c["signed_date"] and d["doc_date"] and d["doc_date"] < c["signed_date"]:
            out.append(f"Hóa đơn {d['invoice_no']} ngày {d['doc_date']} trước ngày ký hợp đồng {c['signed_date']}")
    return out


@rule("R-15", "Thanh toán phí QLVH trong tháng KPI dưới ngưỡng hợp đồng", "tb", ("Q",), ("CP1",),
      "Hợp đồng QLVH Skyline (chờ Q6)", "2026-11-07")
def r15(ctx: Ctx):
    s, c = ctx.sub, ctx.contract
    if not s["is_mgmt_fee"] or not c or c["kpi_threshold"] is None:
        return []
    if not s["kpi_month"]:
        return ["Chưa chọn tháng KPI cho đề nghị thanh toán phí QLVH"]
    k = q1(ctx.conn, "SELECT * FROM kpi_scores WHERE month = ?", (s["kpi_month"],))
    score = None if k is None else (k["bqt_score"] if k["bqt_score"] is not None else k["self_score"])
    if score is None:
        return [f"Chưa có điểm KPI tháng {s['kpi_month']}"]
    if score < c["kpi_threshold"]:
        return [f"Điểm KPI tháng {s['kpi_month']} là {score:g}, dưới ngưỡng hợp đồng {c['kpi_threshold']:g}"]
    return []


@rule("R-18", "Hóa đơn đã được thanh toán trước đó", "chan", ("T",), ("CP1", "CP3"),
      THUC_HANH + " – chống thanh toán trùng", "2026-11-07")
def r18(ctx: Ctx):
    out = []
    marks = ",".join("?" for _ in IN_FLOW)
    for d in ctx.docs_of("hoa_don"):
        if not d["invoice_no"]:
            continue
        tax = d["seller_tax_code"] or ctx.vendor["tax_code"]
        dup = q1(ctx.conn,
                 f"SELECT s.code FROM documents d JOIN submissions s ON s.id = d.submission_id"
                 f" WHERE d.doc_type = 'hoa_don' AND d.cancelled = 0 AND d.superseded_by IS NULL"
                 f" AND d.invoice_no = ? AND COALESCE(d.seller_tax_code, '') IN (?, '') AND s.code <> ?"
                 f" AND s.status IN ({marks})", (d["invoice_no"], tax, ctx.sub["code"], *IN_FLOW))
        if dup:
            out.append(f"Hóa đơn số {d['invoice_no']} (MST {tax}) đã nằm trong tờ trình {dup['code']}")
            continue
        hist = q1(ctx.conn, "SELECT pay_date FROM history_payments WHERE invoice_no = ? AND vendor_tax_code = ?",
                  (d["invoice_no"], tax))
        if hist:
            out.append(f"Hóa đơn số {d['invoice_no']} (MST {tax}) đã được thanh toán ngày {hist['pay_date']} (dữ liệu trước go-live)")
    return out


@rule("R-19", "Lũy kế thanh toán vượt giá trị hợp đồng và phụ lục", "chan", ("T",), ("CP1",),
      THUC_HANH, "2026-11-07")
def r19(ctx: Ctx):
    c = ctx.contract
    if not c:
        return []
    marks = ",".join("?" for _ in IN_FLOW)
    paid = ctx.conn.execute(f"SELECT COALESCE(SUM(amount),0) FROM submissions WHERE contract_id = ? AND code <> ?"
                            f" AND status IN ({marks})", (c["id"], ctx.sub["code"], *IN_FLOW)).fetchone()[0]
    total = c["paid_before_golive"] + paid + ctx.sub["amount"]
    cap = c["value"] + c["addendum_value"]
    if total > cap:
        return [f"Lũy kế thanh toán hợp đồng {c['contract_no']} sẽ là {fmt(total)}, vượt giá trị hợp đồng "
                f"và phụ lục {fmt(cap)}"]
    return []


@rule("R-20", "Biên bản nghiệm thu bảo trì thiếu xác nhận của BQT / tư vấn giám sát", "cao", ("L",), ("CP1",),
      f"{QUY_CHE_BXD} – trách nhiệm giám sát bảo trì của BQT", "2024-08-01", derived=True)
def r20(ctx: Ctx):
    if not ctx.is_bt:
        return []
    acc = ctx.docs_of("nghiem_thu")
    if acc and not any(d["signed_by_bqt"] or d["signed_by_supervisor"] for d in acc):
        return ["Biên bản nghiệm thu chỉ có chữ ký BQL/nhà cung cấp, thiếu xác nhận của BQT hoặc tư vấn giám sát"]
    return []


@rule("R-25", "Tờ trình đột xuất chưa được BQT xác nhận tính đột xuất", "chan", ("L",), ("CP2",),
      f"{QUY_CHE_BXD} – bảo trì đột xuất", "2024-08-01", derived=True)
def r25(ctx: Ctx):
    if ctx.sub["is_emergency"] and not ctx.sub["emergency_confirmed_by"]:
        return ["BQT chưa xác nhận tính đột xuất của khoản chi"]
    return []


# ---------- CP3 ---------------------------------------------------------------------------

@rule("R-04", "Thiếu bản ký hồ sơ gửi ngân hàng hoặc biểu quyết chưa đạt", "chan", ("L", "Q"), ("CP3",),
      f"{QUY_CHE_BXD} – hồ sơ rút kinh phí bảo trì; {HOAT_DONG_SKYLINE}", "2024-08-01")
def r04(ctx: Ctx):
    from .constants import DOC_TYPES
    s = ctx.sub
    out = []
    if not s["approval_basis"]:
        out.append("Biểu quyết chưa đạt tỷ lệ thông qua")
    if ctx.is_bt:
        for t in ("de_nghi_ky", "bien_ban_hop_ky"):
            if not ctx.docs_of(t):
                out.append(f"Chưa upload {DOC_TYPES[t]}")
        if not s["signed_docs_verified_by"] and ctx.docs_of("de_nghi_ky") and ctx.docs_of("bien_ban_hop_ky"):
            out.append("Chưa có người kiểm tra xác nhận số tiền, tên nhà cung cấp trên bản ký khớp tờ trình")
    return out


register_meta("R-06", "Người xác nhận ký không thuộc danh sách chủ tài khoản", "chan", ("L", "Q"), ("CP3",),
              f"{QUY_CHE_BXD}; {QUY_CHE_SKYLINE} – người đứng tên tài khoản", "2024-08-01")
register_meta("R-16", "Nhắc hạn công khai 6 tháng, khoản đột xuất chưa báo cáo Hội nghị, tiền gửi sắp đáo hạn",
              "nhac", ("L", "Q"), ("Lịch",), f"{QUY_CHE_BXD} – công khai 6 tháng; {QUY_CHE_SKYLINE}", "2024-08-01")
register_meta("R-17", "Giao dịch sao kê không khớp và chưa phân loại sau N ngày làm việc", "cao", ("T",), ("CP4",),
              THUC_HANH, "2026-11-07")
register_meta("R-21", "Chi trước, duyệt sau", "cao", ("T",), ("CP4",), THUC_HANH, "2026-11-07")
register_meta("R-22", "Đã xác nhận ký nhưng chưa thấy giao dịch trên sao kê", "tb", ("L",), ("CP4",),
              f"{QUY_CHE_BXD} – thời hạn ngân hàng chuyển tiền", "2024-08-01", derived=True)
register_meta("R-23", "Sao kê không liên tục hoặc không đúng định dạng xuất gốc", "chan", ("T",), ("CP4",),
              THUC_HANH + " – chống sửa sao kê", "2026-11-07")
register_meta("R-24", "Sửa số tài khoản kinh phí bảo trì", "chan", ("L",), ("Cấu hình",),
              f"{QUY_CHE_BXD} – không thay đổi tài khoản kinh phí bảo trì đã lập", "2024-08-01")

CHECKPOINT_RULES = {
    "CP1": ["HS-01", "R-01", "R-02", "R-03", "R-05", "R-07", "R-08", "R-09", "R-10", "R-11", "R-12", "R-13",
            "R-14", "R-15", "R-18", "R-19", "R-20"],
    "CP2": ["R-01", "R-12", "R-25"],
    "CP3": ["R-04", "R-05", "R-18"],
}


def is_enabled(conn, rule_id: str) -> bool:
    r = RULES[rule_id]
    if not r.toggleable:
        return True  # [L], [Q] không tắt được
    return S.rule_enabled(conn, rule_id)


def run_checkpoint(conn, sub_id: int, cp: str) -> list[dict]:
    """Chạy toàn bộ rule của điểm kiểm soát, đồng bộ bảng alerts, trả về các cảnh báo đang hiệu lực."""
    ctx = Ctx(conn, sub_id)
    ts = clock.now(conn)
    for rid in CHECKPOINT_RULES[cp]:
        r = RULES[rid]
        findings = []
        if is_enabled(conn, rid):
            res = r.fn(ctx, cp) if rid in ("R-01", "R-12") else r.fn(ctx)
            for f in res:
                findings.append(f if isinstance(f, tuple) else (f, r.severity))
        existing = q(conn, "SELECT * FROM alerts WHERE submission_id = ? AND rule_id = ? AND checkpoint = ?"
                           " AND status IN ('open','accepted')", (sub_id, rid, cp))
        current = {(m, sev) for m, sev in findings}
        for a in existing:
            if (a["message"], a["severity"]) not in current:
                conn.execute("UPDATE alerts SET status = 'resolved', resolved_at = ? WHERE id = ?", (ts, a["id"]))
        have = {(a["message"], a["severity"]) for a in existing}
        for m, sev in findings:
            if (m, sev) not in have:
                conn.execute("INSERT INTO alerts(submission_id, rule_id, severity, checkpoint, message, created_at)"
                             " VALUES (?,?,?,?,?,?)", (sub_id, rid, sev, cp, m, ts))
    return active_alerts(conn, sub_id, cp)


def active_alerts(conn, sub_id: int, cp: str | None = None) -> list[dict]:
    sql = "SELECT * FROM alerts WHERE submission_id = ? AND status IN ('open','accepted')"
    params = [sub_id]
    if cp:
        sql += " AND checkpoint = ?"
        params.append(cp)
    rows = [dict(r) for r in q(conn, sql, params)]
    rows.sort(key=lambda a: (SEVERITY_ORDER[a["severity"]], a["rule_id"]))
    return rows


def blocking(alerts: list[dict]) -> list[dict]:
    return [a for a in alerts if a["severity"] == "chan" and a["status"] == "open"]


def pending_high(conn, sub_id: int) -> list[dict]:
    """Cảnh báo Cao chưa được ghi lý do + chủ TK xác nhận."""
    return [a for a in active_alerts(conn, sub_id) if a["severity"] == "cao" and a["status"] == "open"]
