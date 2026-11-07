"""F-05 / mục 6.3: sinh hồ sơ gửi ngân hàng (Word) từ dữ liệu tờ trình và kết quả biểu quyết.

Mẫu dưới đây là mẫu chung; nếu ngân hàng có mẫu riêng (Q12) thì thay nội dung các hàm build_*.
"""
import io

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from . import clock, rules
from .db import q, q1
from .workflow import get_sub, tally


def _num_to_words_hint(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " đồng"


def _header(doc: Document, title: str, today):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập – Tự do – Hạnh phúc")
    r.bold = True
    p = doc.add_paragraph(f"TP. Hồ Chí Minh, ngày {today.day:02d} tháng {today.month:02d} năm {today.year}")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hr = h.add_run(title)
    hr.bold = True
    hr.font.size = Pt(14)


def _ctx(conn, sub_id):
    sub = get_sub(conn, sub_id)
    vendor = q1(conn, "SELECT * FROM vendors WHERE id = ?", (sub["vendor_id"],))
    contract = q1(conn, "SELECT * FROM contracts WHERE id = ?", (sub["contract_id"],))
    fund = q1(conn, "SELECT * FROM funds WHERE code = ?", (sub["fund_code"],))
    return sub, vendor, contract, fund


def _bytes(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_transfer_request(conn, sub_id) -> bytes:
    sub, vendor, contract, fund = _ctx(conn, sub_id)
    doc = Document()
    _header(doc, "VĂN BẢN ĐỀ NGHỊ CHUYỂN TIỀN\n(Rút kinh phí bảo trì phần sở hữu chung)", clock.today(conn))
    doc.add_paragraph(f"Kính gửi: {fund['bank']}")
    doc.add_paragraph("Ban quản trị nhà chung cư Skyline đề nghị Quý Ngân hàng chuyển tiền từ tài khoản "
                      f"{fund['name'].lower()} số {fund['account_no']} như sau:")
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    item = None
    if sub["plan_item_code"] and sub["plan_id"]:
        item = rules.plan_item(conn, sub["plan_id"], sub["plan_item_code"])
    for k, v in (
        ("Mã tờ trình (ghi vào nội dung chuyển khoản)", sub["code"]),
        ("Số tiền", _num_to_words_hint(sub["amount"])),
        ("Bên nhận (đơn vị thực hiện bảo trì)", vendor["name"]),
        ("Mã số thuế", vendor["tax_code"]),
        ("Số tài khoản thụ hưởng", sub["beneficiary_account"] or ""),
        ("Hợp đồng", f"{contract['contract_no']} – {contract['title']}"),
        ("Hạng mục", (item["name"] if item else "") + (" (bảo trì đột xuất)" if sub["is_emergency"] else "")),
        ("Lý do chuyển tiền", sub["reason"]),
    ):
        row = t.add_row().cells
        row[0].text, row[1].text = k, str(v)
    doc.add_paragraph()
    doc.add_paragraph("Hồ sơ kèm theo: Biên bản họp BQT về việc rút kinh phí bảo trì; "
                      + ("Hợp đồng bảo trì đã ký (bảo trì đột xuất)." if sub["is_emergency"]
                         else "Trích kế hoạch bảo trì đã được Hội nghị nhà chung cư thông qua."))
    doc.add_paragraph("\nTM. BAN QUẢN TRỊ\n(Chủ tài khoản ký, ghi rõ họ tên)").alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return _bytes(doc)


def build_meeting_minutes(conn, sub_id) -> bytes:
    sub, vendor, contract, fund = _ctx(conn, sub_id)
    tl = tally(conn, sub)
    doc = Document()
    _header(doc, "BIÊN BẢN HỌP BAN QUẢN TRỊ\nV/v rút kinh phí bảo trì phần sở hữu chung", clock.today(conn))
    doc.add_paragraph(f"Nội dung: xem xét tờ trình {sub['code']} (phiên bản {sub['version']}) – "
                      f"{sub['reason']}; số tiền {_num_to_words_hint(sub['amount'])}; "
                      f"đơn vị nhận: {vendor['name']}.")
    doc.add_paragraph(f"Thành viên có quyền biểu quyết: {len(tl['eligible'])}. "
                      + (f"Không tham gia biểu quyết do xung đột lợi ích: "
                         f"{', '.join(m['full_name'] for m in tl['excluded'])}." if tl["excluded"] else ""))
    t = doc.add_table(rows=1, cols=3)
    t.style = "Table Grid"
    t.rows[0].cells[0].text, t.rows[0].cells[1].text, t.rows[0].cells[2].text = "Thành viên", "Ý kiến", "Ký tên"
    for m in tl["eligible"]:
        v = tl["votes"].get(m["id"])
        row = t.add_row().cells
        row[0].text = m["full_name"]
        row[1].text = {"dong_y": "Đồng ý", "khong_dong_y": "Không đồng ý"}.get(v["choice"], "") if v else "Chưa có ý kiến"
    doc.add_paragraph(f"\nKết quả: {len(tl['yes'])}/{len(tl['eligible'])} đồng ý "
                      f"(yêu cầu tối thiểu {tl['needed']}). "
                      + ("Thông qua việc rút kinh phí bảo trì nêu trên." if tl["passed"] or sub["approval_basis"]
                         else "Chưa đạt tỷ lệ thông qua."))
    alerts = [a for a in q(conn, "SELECT * FROM alerts WHERE submission_id = ? AND status = 'accepted'", (sub_id,))]
    if alerts:
        doc.add_paragraph("Các cảnh báo đã được BQT cân nhắc và chấp nhận:")
        for a in alerts:
            doc.add_paragraph(f"{a['rule_id']}: {a['message']} – Lý do: {a['accept_reason']}", style="List Bullet")
    doc.add_paragraph("\nTHƯ KÝ CUỘC HỌP                                   CHỦ TỌA").alignment = WD_ALIGN_PARAGRAPH.CENTER
    return _bytes(doc)


def build_plan_extract(conn, sub_id) -> bytes:
    sub, vendor, contract, fund = _ctx(conn, sub_id)
    doc = Document()
    if sub["is_emergency"]:
        _header(doc, "THÔNG TIN HỢP ĐỒNG BẢO TRÌ ĐỘT XUẤT", clock.today(conn))
        for line in (f"Hợp đồng số: {contract['contract_no']}", f"Tên: {contract['title']}",
                     f"Ngày ký: {contract['signed_date']}", f"Giá trị: {_num_to_words_hint(contract['value'])}",
                     f"BQT xác nhận tính đột xuất: {sub['emergency_confirmed_at'] or 'CHƯA'} – {sub['emergency_note'] or ''}",
                     "Đính kèm: bản sao hợp đồng đã ký."):
            doc.add_paragraph(line)
        return _bytes(doc)
    plan = q1(conn, "SELECT * FROM plans WHERE id = ?", (sub["plan_id"],))
    _header(doc, "TRÍCH KẾ HOẠCH BẢO TRÌ ĐÃ ĐƯỢC HỘI NGHỊ THÔNG QUA", clock.today(conn))
    if plan:
        doc.add_paragraph(f"Kế hoạch bảo trì năm {plan['year']}, phiên bản {plan['version']}, "
                          f"Nghị quyết số {plan['resolution_no']} ngày {plan['resolution_date']}.")
        item = rules.plan_item(conn, plan["id"], sub["plan_item_code"])
        if item:
            t = doc.add_table(rows=2, cols=3)
            t.style = "Table Grid"
            for i, h in enumerate(("Mã hạng mục", "Tên hạng mục", "Dự toán")):
                t.rows[0].cells[i].text = h
            t.rows[1].cells[0].text = item["code"]
            t.rows[1].cells[1].text = item["name"]
            t.rows[1].cells[2].text = _num_to_words_hint(item["budget"])
    return _bytes(doc)


BUILDERS = {
    "de-nghi-chuyen-tien": ("Van-ban-de-nghi-chuyen-tien", build_transfer_request),
    "bien-ban-hop": ("Bien-ban-hop-BQT", build_meeting_minutes),
    "trich-ke-hoach": ("Trich-ke-hoach-bao-tri", build_plan_extract),
}
