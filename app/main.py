"""Web app (FastAPI + Jinja2, render phía server, ưu tiên điện thoại)."""
import csv
import io
import json
import os
import secrets
import zipfile
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import audit, clock, config_changes, docgen, jobs, reconcile, reports, rules
from . import settings as S
from . import workflow as wf
from .auth import check_password
from .constants import (BQL_DOC_TYPES, BQT_DOC_TYPES, DOC_TYPES, FUNDS, MATCH_STATUS, PAYMENT_METHOD, ROLES, SEVERITY,
                        SOURCE, STATUS, TIER_RULE, TXN_CATEGORY)
from .db import connect, init_db, insert, q, q1, row_dict

APP_DIR = Path(__file__).parent
app = FastAPI(title="Skyline BQT – Giám sát tài chính")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SKYLINE_SECRET", secrets.token_hex(32)),
                   same_site="lax", max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")
DEMO = os.environ.get("SKYLINE_DEMO", "1") == "1"


def money(n):
    if n is None:
        return "—"
    return f"{int(n):,}".replace(",", ".") + " đ"


def vn_date(s):
    if not s:
        return "—"
    s = str(s)
    d = s[:10].split("-")
    out = f"{d[2]}/{d[1]}/{d[0]}" if len(d) == 3 else s
    return out + (" " + s[11:16] if len(s) > 10 else "")


templates.env.filters["money"] = money
templates.env.filters["vndate"] = vn_date
templates.env.globals.update(STATUS=STATUS, DOC_TYPES=DOC_TYPES, SEVERITY=SEVERITY, SOURCE=SOURCE, ROLES=ROLES,
                             FUNDS=FUNDS, PAYMENT_METHOD=PAYMENT_METHOD, TXN_CATEGORY=TXN_CATEGORY,
                             MATCH_STATUS=MATCH_STATUS, TIER_RULE=TIER_RULE, RULES=rules.RULES, DEMO=DEMO,
                             BQL_DOC_TYPES=BQL_DOC_TYPES, BQT_DOC_TYPES=BQT_DOC_TYPES)


class NotLoggedIn(Exception):
    pass


class Forbidden(Exception):
    pass


@app.exception_handler(NotLoggedIn)
async def _nl(request, exc):
    return RedirectResponse("/dang-nhap", 303)


@app.exception_handler(Forbidden)
async def _fb(request, exc):
    return HTMLResponse("<h3>Bạn không có quyền xem trang này.</h3><a href='/'>Về trang chủ</a>", 403)


@app.middleware("http")
async def db_session(request: Request, call_next):
    conn = connect()
    init_db(conn)
    request.state.conn = conn
    try:
        if not request.url.path.startswith("/static"):
            jobs.run_daily(conn)
        response = await call_next(request)
        conn.commit()
        return response
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def current_user(request: Request, *roles) -> dict:
    uid = request.session.get("uid")
    if not uid:
        raise NotLoggedIn()
    u = q1(request.state.conn, "SELECT * FROM users WHERE id = ? AND active = 1", (uid,))
    if not u:
        request.session.clear()
        raise NotLoggedIn()
    u = dict(u)
    if roles and u["role"] not in roles:
        raise Forbidden()
    return u


def flash(request, kind, msg, details=None):
    request.session.setdefault("flash", []).append({"kind": kind, "msg": msg, "details": details or []})


def render(request, name, **ctx):
    conn = request.state.conn
    user = ctx.get("user")
    unread = 0
    if user:
        unread = conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                              (user["id"],)).fetchone()[0]
    messages = request.session.pop("flash", [])
    return templates.TemplateResponse(request, name, {"today": clock.today(conn), "unread": unread,
                                                      "messages": messages, **ctx})


def back(url):
    return RedirectResponse(url, 303)


async def form_data(request):
    form = await request.form()
    data, files = {}, {}
    for k, v in form.multi_items():
        if hasattr(v, "read"):
            content = await v.read()
            if content:
                files[k] = (v.filename, content)
        else:
            data[k] = v.strip() if isinstance(v, str) else v
    return data, files


def act(request, fn, ok_msg, url):
    """Gọi một thao tác nghiệp vụ; lỗi nghiệp vụ hiển thị thành thông báo (dữ liệu đã ghi vẫn được lưu)."""
    try:
        fn()
        flash(request, "ok", ok_msg)
    except wf.WorkflowError as e:
        request.state.conn.commit()
        flash(request, "error", str(e), e.details)
    return back(url)


# ---------- Đăng nhập ---------------------------------------------------------------------

@app.get("/dang-nhap", response_class=HTMLResponse)
def login_page(request: Request):
    users = q(request.state.conn, "SELECT username, full_name, role FROM users WHERE active = 1 ORDER BY id") if DEMO else []
    return render(request, "login.html", demo_users=users)


@app.post("/dang-nhap")
async def login(request: Request):
    data, _ = await form_data(request)
    u = q1(request.state.conn, "SELECT * FROM users WHERE username = ? AND active = 1", (data.get("username", ""),))
    if not u or not check_password(data.get("password", ""), u["password_hash"]):
        flash(request, "error", "Sai tên đăng nhập hoặc mật khẩu")
        return back("/dang-nhap")
    request.session["uid"] = u["id"]
    audit.log(request.state.conn, u["id"], "Đăng nhập", "user", u["id"])
    return back("/")


@app.get("/dang-xuat")
def logout(request: Request):
    request.session.clear()
    return back("/dang-nhap")


# ---------- Dashboard F-10 ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    user = current_user(request)
    if user["role"] == "bql":
        return back("/to-trinh")
    conn = request.state.conn
    budgets = {code: reports.budget_table(conn, code) for code in ("BT", "VH")}
    my_votes = []
    if user["role"] == "bqt":
        for s in q(conn, "SELECT * FROM submissions WHERE status = 'cho_bieu_quyet' ORDER BY vote_deadline"):
            t = wf.tally(conn, dict(s))
            if user["id"] in [m["id"] for m in t["pending"]]:
                my_votes.append(dict(s))
    reminders = [dict(r) for r in q(conn, "SELECT * FROM alerts WHERE rule_id = 'R-16' AND status = 'open' ORDER BY id DESC")]
    return render(request, "dashboard.html", user=user, funds=reports.fund_summary(conn), budgets=budgets,
                  counts=reports.status_counts(conn), emergencies=reports.emergency_pending(conn),
                  alert_counts=reports.alert_counts(conn), metrics=reports.metrics(conn),
                  deposits=reports.maturing_deposits(conn), my_votes=my_votes, reminders=reminders)


# ---------- Tờ trình ----------------------------------------------------------------------

def _sub_rows(conn, where="", params=()):
    return [dict(r) for r in q(conn, "SELECT s.*, v.name AS vendor_name FROM submissions s JOIN vendors v ON v.id = s.vendor_id"
                                     f" {where} ORDER BY s.id DESC", params)]


@app.get("/to-trinh", response_class=HTMLResponse)
def submissions(request: Request, status: str = "", fund: str = ""):
    user = current_user(request)
    conn = request.state.conn
    where, params = [], []
    if status:
        where.append("s.status = ?")
        params.append(status)
    elif not request.query_params.get("all"):
        where.append("s.status <> 'huy'")
    if fund:
        where.append("s.fund_code = ?")
        params.append(fund)
    rows = _sub_rows(conn, ("WHERE " + " AND ".join(where)) if where else "", params)
    for r in rows:
        r["alerts"] = rules.active_alerts(conn, r["id"])
    return render(request, "submissions.html", user=user, rows=rows, status=status, fund=fund)


def _catalog(conn):
    return {
        "vendors": [dict(r) for r in q(conn, "SELECT * FROM vendors ORDER BY name")],
        "contracts": [dict(r) for r in q(conn, "SELECT c.*, v.name vendor_name FROM contracts c JOIN vendors v ON v.id = c.vendor_id ORDER BY c.id")],
        "installments": [dict(r) for r in q(conn, "SELECT * FROM contract_installments ORDER BY contract_id, seq")],
        "cost_types": [dict(r) for r in q(conn, "SELECT * FROM cost_types ORDER BY is_operational, name")],
        "items": [dict(r) for r in q(conn, "SELECT i.*, p.fund_code FROM plan_items i JOIN plans p ON p.id = i.plan_id"
                                           " WHERE p.id IN (SELECT MAX(id) FROM plans GROUP BY fund_code) ORDER BY i.code")],
    }


@app.get("/to-trinh/moi", response_class=HTMLResponse)
def new_submission_page(request: Request, resubmit: int = 0):
    user = current_user(request, "bql")
    conn = request.state.conn
    prefill = {}
    if resubmit:
        old = wf.get_sub(conn, resubmit)
        prefill = {k: old[k] for k in wf.FIELDS} | {"linked_submission_id": old["id"], "linked_code": old["code"],
                                                     "rejection_reason": old["rejection_reason"]}
    return render(request, "submission_form.html", user=user, sub=prefill, mode="new", **_catalog(conn))


@app.post("/to-trinh/moi")
async def new_submission(request: Request):
    user = current_user(request, "bql")
    data, _ = await form_data(request)
    try:
        sub = wf.create_submission(request.state.conn, user, data)
    except wf.WorkflowError as e:
        flash(request, "error", str(e), e.details)
        return back("/to-trinh/moi" + (f"?resubmit={data['linked_submission_id']}" if data.get("linked_submission_id") else ""))
    flash(request, "ok", f"Đã tạo {sub['code']}. Hãy upload chứng từ rồi bấm Nộp")
    return back(f"/to-trinh/{sub['id']}")


@app.get("/to-trinh/{sid}/sua", response_class=HTMLResponse)
def edit_page(request: Request, sid: int):
    user = current_user(request, "bql")
    return render(request, "submission_form.html", user=user, sub=wf.get_sub(request.state.conn, sid), mode="edit",
                  **_catalog(request.state.conn))


@app.post("/to-trinh/{sid}/sua")
async def edit_submission(request: Request, sid: int):
    user = current_user(request, "bql")
    data, _ = await form_data(request)
    return act(request, lambda: wf.edit_submission(request.state.conn, user, sid, data), "Đã lưu", f"/to-trinh/{sid}")


@app.get("/to-trinh/{sid}", response_class=HTMLResponse)
def submission_detail(request: Request, sid: int):
    user = current_user(request)
    conn = request.state.conn
    sub = wf.get_sub(conn, sid)
    ctx = rules.Ctx(conn, sid)
    is_bql = user["role"] == "bql"
    alerts = rules.active_alerts(conn, sid)
    if is_bql:
        alerts = [a for a in alerts if a["checkpoint"] == "CP1"]
    all_docs = [dict(r) for r in q(conn, "SELECT d.*, u.full_name uploader FROM documents d JOIN users u ON u.id = d.uploaded_by"
                                         " WHERE submission_id = ? ORDER BY d.id", (sid,))]
    required = rules.required_docs(ctx)
    checklist = [{"type": t, "label": DOC_TYPES[t], "ok": bool(ctx.docs_of(t)), "cp": "CP1"} for t in required]
    if sub["fund_code"] == "BT":
        checklist += [{"type": t, "label": DOC_TYPES[t], "ok": bool(ctx.docs_of(t)), "cp": "CP3"}
                      for t in ("de_nghi_ky", "bien_ban_hop_ky")]
    tl = wf.tally(conn, sub)
    names = {r["id"]: r["full_name"] for r in q(conn, "SELECT id, full_name FROM users")}
    vote_history = [dict(r) for r in q(conn, "SELECT * FROM votes WHERE submission_id = ? ORDER BY id", (sid,))] if not is_bql else []
    history = [dict(r) for r in q(conn, "SELECT * FROM status_history WHERE submission_id = ? ORDER BY id", (sid,))]
    versions = [dict(r) for r in q(conn, "SELECT id, version, status FROM submissions WHERE code = ? ORDER BY version", (sub["code"],))]
    linked = wf.get_sub(conn, sub["linked_submission_id"]) if sub["linked_submission_id"] else None
    txns = [dict(r) for r in q(conn, "SELECT * FROM statement_txns WHERE submission_id = ?", (sid,))]
    plan_item = rules.plan_item(conn, sub["plan_id"], sub["plan_item_code"]) if sub["plan_id"] and sub["plan_item_code"] else None
    return render(request, "submission_detail.html", user=user, sub=sub, ctx=ctx, alerts=alerts, docs=all_docs,
                  checklist=checklist, tally=tl, names=names, vote_history=vote_history, history=history,
                  versions=versions, linked=linked, txns=txns, plan_item=plan_item, is_bql=is_bql,
                  is_signer=wf.is_signer(conn, user, sub["fund_code"]),
                  cost_types=_catalog(conn)["cost_types"])


@app.post("/to-trinh/{sid}/chung-tu")
async def upload_doc(request: Request, sid: int):
    user = current_user(request)
    data, files = await form_data(request)
    if "file" not in files:
        flash(request, "error", "Chưa chọn file")
        return back(f"/to-trinh/{sid}")
    name, content = files["file"]
    return act(request, lambda: wf.add_document(request.state.conn, user, sid, data.get("doc_type"), name, content, data,
                                                replace_id=data.get("replace_id") or None),
               "Đã upload chứng từ", f"/to-trinh/{sid}")


@app.get("/chung-tu/{did}")
def download_doc(request: Request, did: int):
    user = current_user(request)
    d = q1(request.state.conn, "SELECT * FROM documents WHERE id = ?", (did,))
    if not d:
        raise Forbidden()
    if user["role"] == "bql" and d["doc_type"] not in BQL_DOC_TYPES:
        raise Forbidden()
    return FileResponse(d["stored_path"], filename=d["filename"])


@app.post("/chung-tu/{did}/huy")
async def cancel_doc(request: Request, did: int):
    user = current_user(request)
    data, _ = await form_data(request)
    d = q1(request.state.conn, "SELECT submission_id FROM documents WHERE id = ?", (did,))
    return act(request, lambda: wf.cancel_document(request.state.conn, user, did, data.get("reason")),
               "Đã hủy chứng từ", f"/to-trinh/{d['submission_id']}")


SIMPLE_ACTIONS = {
    "nop": (lambda c, u, s, d: wf.submit(c, u, s), "Đã nộp tờ trình (qua CP1)"),
    "yeu-cau-bo-sung": (lambda c, u, s, d: wf.request_more(c, u, s, d.get("reason")), "Đã gửi yêu cầu bổ sung cho BQL"),
    "xac-nhan-dot-xuat": (lambda c, u, s, d: wf.confirm_emergency(c, u, s, d.get("cost_type"), d.get("note")),
                          "Đã xác nhận tính đột xuất"),
    "mo-bieu-quyet": (lambda c, u, s, d: wf.open_vote(c, u, s), "Đã qua CP2 và mở biểu quyết"),
    "bieu-quyet": (lambda c, u, s, d: wf.cast_vote(c, u, s, d.get("choice"), d.get("note", "")), "Đã ghi nhận phiếu"),
    "tu-choi": (lambda c, u, s, d: wf.reject(c, u, s, d.get("reason")), "Đã chốt từ chối"),
    "phien-ban-moi": (lambda c, u, s, d: wf.new_version(c, u, s, d.get("amount") or None), "Đã tạo phiên bản mới"),
    "huy": (lambda c, u, s, d: wf.cancel(c, u, s, d.get("reason")), "Đã hủy tờ trình"),
    "xac-minh-ban-ky": (lambda c, u, s, d: wf.verify_signed_docs(c, u, s), "Đã xác nhận bản ký khớp tờ trình"),
    "kiem-tra-cp3": (lambda c, u, s, d: wf.check_ready(c, u, s), "Qua CP3 – tờ trình Sẵn sàng ký"),
    "dong": (lambda c, u, s, d: wf.close(c, u, s), "Đã đóng hồ sơ"),
    "da-bao-cao-hoi-nghi": (lambda c, u, s, d: wf.mark_reported(c, u, s), "Đã đánh dấu đã báo cáo Hội nghị"),
}


@app.post("/to-trinh/{sid}/xac-nhan-ky")
async def confirm_sign(request: Request, sid: int):
    user = current_user(request)
    data, files = await form_data(request)
    name, content = files.get("file", ("", b""))
    return act(request, lambda: wf.confirm_sign(request.state.conn, user, sid, data.get("unc_ref"),
                                                data.get("unc_amount", "0").replace(".", ""), name, content),
               "Đã xác nhận ký UNC", f"/to-trinh/{sid}")


@app.post("/to-trinh/{sid}/ket-qua-hop")
async def meeting(request: Request, sid: int):
    user = current_user(request)
    data, files = await form_data(request)
    name, content = files.get("file", ("", b""))
    return act(request, lambda: wf.meeting_result(request.state.conn, user, sid, data.get("decision"), name, content,
                                                  data.get("reason", "")),
               "Đã nhập kết quả họp", f"/to-trinh/{sid}")


@app.post("/to-trinh/{sid}/{action}")
async def simple_action(request: Request, sid: int, action: str):
    user = current_user(request)
    if action not in SIMPLE_ACTIONS:
        raise Forbidden()
    fn, msg = SIMPLE_ACTIONS[action]
    data, _ = await form_data(request)
    target = f"/to-trinh/{sid}"
    result = {}

    def run():
        result["sub"] = fn(request.state.conn, user, sid, data)

    resp = act(request, run, msg, target)
    if action == "phien-ban-moi" and result.get("sub"):
        return back(f"/to-trinh/{result['sub']['id']}")
    return resp


@app.get("/to-trinh/{sid}/ho-so/{kind}.docx")
def bank_doc(request: Request, sid: int, kind: str):
    user = current_user(request, "bqt", "thu_ky")
    if kind not in docgen.BUILDERS:
        raise Forbidden()
    sub = wf.get_sub(request.state.conn, sid)
    fname, fn = docgen.BUILDERS[kind]
    content = fn(request.state.conn, sid)
    audit.log(request.state.conn, user["id"], f"Sinh hồ sơ ngân hàng: {fname}", "submission", sid)
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{sub["code"]}-{fname}.docx"'})


# ---------- Cảnh báo -----------------------------------------------------------------------

@app.get("/canh-bao", response_class=HTMLResponse)
def alerts_page(request: Request, show: str = "open"):
    user = current_user(request, "bqt", "thu_ky", "admin")
    sql = ("SELECT a.*, s.code, s.status sub_status FROM alerts a LEFT JOIN submissions s ON s.id = a.submission_id"
           " WHERE (s.id IS NULL OR s.status <> 'huy')")
    if show == "open":
        sql += " AND a.status = 'open'"
    rows = [dict(r) for r in q(request.state.conn, sql + " ORDER BY a.id DESC LIMIT 300")]
    names = {r["id"]: r["full_name"] for r in q(request.state.conn, "SELECT id, full_name FROM users")}
    return render(request, "alerts.html", user=user, rows=rows, show=show, names=names)


@app.post("/canh-bao/{aid}/chap-nhan")
async def accept_alert(request: Request, aid: int):
    user = current_user(request)
    data, _ = await form_data(request)
    return act(request, lambda: wf.accept_alert(request.state.conn, user, aid, data.get("reason"),
                                                bool(data.get("false_positive"))),
               "Đã ghi lý do chấp nhận cảnh báo", data.get("next") or "/canh-bao")


@app.post("/canh-bao/{aid}/xac-nhan")
async def confirm_alert(request: Request, aid: int):
    user = current_user(request)
    data, _ = await form_data(request)
    return act(request, lambda: wf.confirm_alert(request.state.conn, user, aid), "Chủ TK đã xác nhận",
               data.get("next") or "/canh-bao")


# ---------- Sao kê & đối soát F-07 --------------------------------------------------------

@app.get("/sao-ke", response_class=HTMLResponse)
def statements(request: Request):
    user = current_user(request, "bqt", "thu_ky", "admin")
    conn = request.state.conn
    rows = [dict(r) for r in q(conn, "SELECT st.*, (SELECT COUNT(*) FROM statement_txns t WHERE t.statement_id = st.id) n,"
                                     " (SELECT COUNT(*) FROM statement_txns t WHERE t.statement_id = st.id"
                                     "  AND t.match_status NOT IN ('da_khop','da_phan_loai')) pending"
                                     " FROM statements st ORDER BY st.id DESC")]
    rejected = [dict(r) for r in q(conn, "SELECT * FROM statement_rejections ORDER BY id DESC LIMIT 10")]
    return render(request, "statements.html", user=user, rows=rows, rejected=rejected)


@app.post("/sao-ke")
async def upload_statement(request: Request):
    user = current_user(request)
    data, files = await form_data(request)
    if "file" not in files:
        flash(request, "error", "Chưa chọn file sao kê")
        return back("/sao-ke")
    name, content = files["file"]
    res = {}

    def run():
        res.update(reconcile.import_statement(request.state.conn, user, data.get("fund_code"), name, content))

    resp = act(request, run, "Đã nhận sao kê và tự động đối soát", "/sao-ke")
    return back(f"/sao-ke/{res['id']}") if res else resp


@app.get("/sao-ke/mau.csv")
def sample_statement(request: Request):
    current_user(request)
    fund = q1(request.state.conn, "SELECT * FROM funds WHERE code = 'BT'")
    content = reconcile.build_statement_csv(fund["account_no"], "2026-11-01", "2026-11-30", 0,
                                            [("2026-11-10", "FT0001", "TT-2026-002 thanh toan", "19035555666012", -120_000_000)])
    return Response(content, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="mau-sao-ke.csv"'})


@app.get("/sao-ke/{stid}", response_class=HTMLResponse)
def statement_detail(request: Request, stid: int):
    user = current_user(request, "bqt", "thu_ky", "admin")
    conn = request.state.conn
    st = row_dict(q1(conn, "SELECT * FROM statements WHERE id = ?", (stid,)))
    txns = [dict(r) for r in q(conn, "SELECT t.*, s.code sub_code FROM statement_txns t LEFT JOIN submissions s"
                                     " ON s.id = t.submission_id WHERE statement_id = ? ORDER BY t.id", (stid,))]
    candidates = _sub_rows(conn, "WHERE s.status IN ('san_sang_ky','da_ky') AND s.fund_code = ?", (st["fund_code"],))
    names = {r["id"]: r["full_name"] for r in q(conn, "SELECT id, full_name FROM users")}
    return render(request, "statement_detail.html", user=user, st=st, txns=txns, candidates=candidates, names=names,
                  is_signer=wf.is_signer(conn, user, st["fund_code"]))


@app.post("/giao-dich/{tid}/{action}")
async def txn_action(request: Request, tid: int, action: str):
    user = current_user(request)
    data, _ = await form_data(request)
    conn = request.state.conn
    t = q1(conn, "SELECT statement_id FROM statement_txns WHERE id = ?", (tid,))
    url = f"/sao-ke/{t['statement_id']}"
    fns = {
        "phan-loai": (lambda: reconcile.classify(conn, user, tid, data.get("category"), data.get("note", "")),
                      "Đã đề xuất phân loại – chờ chủ TK duyệt"),
        "duyet-phan-loai": (lambda: reconcile.approve_classification(conn, user, tid, True), "Đã duyệt phân loại"),
        "tra-lai": (lambda: reconcile.approve_classification(conn, user, tid, False), "Đã trả lại phân loại"),
        "xac-nhan-khop": (lambda: reconcile.confirm_match(conn, user, tid, int(data.get("submission_id") or 0)),
                          "Đã xác nhận khớp"),
    }
    if action not in fns:
        raise Forbidden()
    return act(request, fns[action][0], fns[action][1], url)


# ---------- Danh mục F-00 / F-01 ----------------------------------------------------------

@app.get("/danh-muc", response_class=HTMLResponse)
def catalog(request: Request, tab: str = "quy"):
    user = current_user(request, "bqt", "thu_ky", "admin")
    conn = request.state.conn
    data = _catalog(conn)
    data.update(
        funds=[dict(r) for r in q(conn, "SELECT * FROM funds")],
        signers=[dict(r) for r in q(conn, "SELECT f.fund_code, u.full_name FROM fund_signers f JOIN users u ON u.id = f.user_id")],
        deposits=[dict(r) for r in q(conn, "SELECT * FROM term_deposits ORDER BY maturity_date")],
        plans=[dict(r) for r in q(conn, "SELECT * FROM plans ORDER BY fund_code, year, version")],
        all_items=[dict(r) for r in q(conn, "SELECT * FROM plan_items ORDER BY plan_id, code")],
        conflicts=[dict(r) for r in q(conn, "SELECT c.*, u.full_name, u.role, v.name vendor_name FROM conflicts c"
                                            " JOIN users u ON u.id = c.user_id JOIN vendors v ON v.id = c.vendor_id")],
        users=[dict(r) for r in q(conn, "SELECT * FROM users ORDER BY id")],
        history=[dict(r) for r in q(conn, "SELECT * FROM history_payments ORDER BY pay_date DESC")],
        kpis=[dict(r) for r in q(conn, "SELECT * FROM kpi_scores ORDER BY month DESC")],
        signoffs=[dict(r) for r in q(conn, "SELECT g.*, u.full_name FROM golive_signoff g JOIN users u ON u.id = g.user_id")],
    )
    return render(request, "catalog.html", user=user, tab=tab, **data)


CATALOG_FORMS = {
    "nha-cung-cap": ("vendors", ("name", "tax_code", "bank_name", "bank_account"), "nha-cung-cap"),
    "hop-dong": ("contracts", ("vendor_id", "fund_code", "contract_no", "title", "value", "addendum_value", "signed_date",
                               "beneficiary_account", "advance_pct", "paid_before_golive", "is_mgmt_contract",
                               "kpi_threshold"), "nha-cung-cap"),
    "dot-thanh-toan": ("contract_installments", ("contract_id", "seq", "name", "amount"), "nha-cung-cap"),
    "xung-dot": ("conflicts", ("user_id", "vendor_id", "note"), "xung-dot"),
    "tien-gui": ("term_deposits", ("fund_code", "bank", "amount", "rate", "start_date", "maturity_date"), "quy"),
    "kpi": ("kpi_scores", ("month", "self_score", "bqt_score", "note"), "kpi"),
}


@app.post("/danh-muc/ke-hoach")
async def add_plan(request: Request):
    """Kế hoạch bảo trì/dự toán phiên bản mới, kèm nghị quyết Hội nghị (mục 6.5)."""
    user = current_user(request, "thu_ky", "admin")
    conn = request.state.conn
    data, files = await form_data(request)
    try:
        path = None
        if "file" in files:
            path, _ = wf.save_file(files["file"][1], files["file"][0])
        wf._require(data.get("resolution_no") and data.get("resolution_date"), "Bắt buộc nhập số và ngày nghị quyết Hội nghị")
        version = (conn.execute("SELECT MAX(version) FROM plans WHERE fund_code = ? AND year = ?",
                                (data["fund_code"], int(data["year"]))).fetchone()[0] or 0) + 1
        pid = insert(conn, "plans", {"fund_code": data["fund_code"], "year": int(data["year"]), "version": version,
                                     "resolution_no": data["resolution_no"], "resolution_date": data["resolution_date"],
                                     "effective_from": data.get("effective_from") or data["resolution_date"],
                                     "file_path": path})
        n = 0
        for row in csv.reader(io.StringIO(data.get("items", ""))):
            if len(row) >= 3 and row[0].strip():
                insert(conn, "plan_items", {"plan_id": pid, "code": row[0].strip(), "name": row[1].strip(),
                                            "budget": int(row[2].strip().replace(".", "")),
                                            "spent_before_golive": int(row[3].strip().replace(".", "")) if len(row) > 3 and row[3].strip() else 0})
                n += 1
        wf._require(n > 0, "Kế hoạch phải có ít nhất một hạng mục")
        audit.log(conn, user["id"], f"Thêm kế hoạch {data['fund_code']} {data['year']} v{version}", "plan", pid, None, data)
        flash(request, "ok", f"Đã lưu phiên bản {version} với {n} hạng mục")
    except (wf.WorkflowError, ValueError, KeyError) as e:
        conn.rollback()
        flash(request, "error", f"Không lưu được kế hoạch: {e}")
    return back("/danh-muc?tab=ke-hoach")


@app.post("/danh-muc/{kind}")
async def add_catalog(request: Request, kind: str):
    user = current_user(request, "thu_ky", "admin")
    if kind not in CATALOG_FORMS:
        raise Forbidden()
    table, fields, tab = CATALOG_FORMS[kind]
    data, _ = await form_data(request)
    row = {f: (data.get(f) if data.get(f) not in ("",) else None) for f in fields}
    if kind == "xung-dot":
        row["declared_at"] = clock.now(request.state.conn)
    if kind == "hop-dong":
        row["is_mgmt_contract"] = 1 if row.get("is_mgmt_contract") else 0
        for k in ("addendum_value", "advance_pct", "paid_before_golive"):
            row[k] = row.get(k) or 0
    try:
        if kind == "kpi":
            request.state.conn.execute("INSERT OR REPLACE INTO kpi_scores(month, self_score, bqt_score, note) VALUES (?,?,?,?)",
                                       (row["month"], row["self_score"], row["bqt_score"], row["note"]))
            rid = row["month"]
        else:
            rid = insert(request.state.conn, table, row)
        audit.log(request.state.conn, user["id"], f"Thêm danh mục {table}", table, rid, None, row)
        flash(request, "ok", "Đã lưu")
    except Exception as e:  # lỗi ràng buộc dữ liệu
        request.state.conn.rollback()
        flash(request, "error", f"Không lưu được: {e}")
    return back(f"/danh-muc?tab={tab}")


@app.post("/danh-muc/nhap/lich-su")
async def import_history(request: Request):
    user = current_user(request, "thu_ky", "admin")
    data, _ = await form_data(request)
    n = 0
    for row in csv.reader(io.StringIO(data.get("rows", ""))):
        if len(row) >= 7 and row[0].strip():
            insert(request.state.conn, "history_payments", {
                "fund_code": row[0].strip(), "vendor_name": row[1].strip(), "vendor_tax_code": row[2].strip(),
                "plan_item_code": row[3].strip() or None, "amount": int(row[4].strip()), "pay_date": row[5].strip(),
                "invoice_no": row[6].strip() or None})
            n += 1
    audit.log(request.state.conn, user["id"], f"Nhập {n} dòng lịch sử chi F-00", "history_payments")
    flash(request, "ok", f"Đã nhập {n} dòng lịch sử")
    return back("/danh-muc?tab=lich-su")


# ---------- Cấu hình F-01 -----------------------------------------------------------------

@app.get("/cau-hinh", response_class=HTMLResponse)
def config_page(request: Request):
    user = current_user(request, "bqt", "thu_ky", "admin")
    conn = request.state.conn
    changes = []
    for c in q(conn, "SELECT * FROM config_changes ORDER BY id DESC LIMIT 50"):
        c = dict(c)
        c["payload_obj"] = json.loads(c["payload"])
        c["approvals"] = [dict(r) for r in q(conn, "SELECT * FROM config_change_approvals WHERE change_id = ?", (c["id"],))]
        c["need"] = config_changes.required_approvers(conn, c)
        changes.append(c)
    names = {r["id"]: r["full_name"] for r in q(conn, "SELECT id, full_name FROM users")}
    settings_rows = [{"key": k, "value": S.get(conn, k), "desc": d} for k, (_, d) in S.DEFAULTS.items()]
    rule_rows = [{"rule": r, "enabled": rules.is_enabled(conn, r.id)} for r in sorted(rules.RULES.values(), key=lambda r: r.id)]
    return render(request, "config.html", user=user, changes=changes, names=names, settings_rows=settings_rows,
                  rule_rows=rule_rows, tiers=rules.tiers(conn), kinds=config_changes.KINDS,
                  funds=[dict(r) for r in q(conn, "SELECT * FROM funds")],
                  contracts=_catalog(conn)["contracts"])


@app.post("/cau-hinh/de-xuat")
async def propose_change(request: Request):
    user = current_user(request)
    data, files = await form_data(request)
    kind = data.get("kind")
    payload = {
        "setting": lambda: {"key": data.get("key"), "value": data.get("value")},
        "rule_toggle": lambda: {"rule_id": data.get("rule_id"), "enabled": data.get("enabled") == "1"},
        "tier": lambda: {k: data.get(k) for k in ("level", "min_amount", "rule_type", "required_count", "require_chair",
                                                  "in_person", "description")},
        "fund_account": lambda: {"fund_code": data.get("fund_code"), "account_no": data.get("account_no")},
        "contract_account": lambda: {"contract_id": int(data.get("contract_id") or 0),
                                     "beneficiary_account": data.get("beneficiary_account")},
    }.get(kind, dict)()
    attachment = None
    if "file" in files:
        attachment, _ = wf.save_file(files["file"][1], files["file"][0])
    return act(request, lambda: config_changes.propose(request.state.conn, user, kind, payload,
                                                       data.get("description", ""), attachment),
               "Đã gửi đề xuất – chờ thành viên BQT khác duyệt", "/cau-hinh")


@app.post("/cau-hinh/{cid}/quyet-dinh")
async def decide_change(request: Request, cid: int):
    user = current_user(request)
    data, _ = await form_data(request)
    res = {}

    def run():
        res["r"] = config_changes.decide(request.state.conn, user, cid, data.get("decision"), data.get("note", ""))

    return act(request, run, "Đã ghi nhận ý kiến", "/cau-hinh")


@app.post("/cau-hinh/sua-tai-khoan-quy")
async def direct_fund_edit(request: Request):
    user = current_user(request, "admin", "thu_ky", "bqt")
    data, _ = await form_data(request)
    return act(request, lambda: config_changes.direct_fund_account_edit(request.state.conn, user, data.get("fund_code"),
                                                                        data.get("account_no")),
               "Đã sửa số tài khoản", "/cau-hinh")


# ---------- Nhật ký, thông báo, chạy thử, hệ thống ----------------------------------------

@app.get("/nhat-ky", response_class=HTMLResponse)
def audit_page(request: Request, page: int = 1):
    user = current_user(request, "bqt", "thu_ky", "admin")
    conn = request.state.conn
    rows = [dict(r) for r in q(conn, "SELECT * FROM audit_log ORDER BY id DESC LIMIT 100 OFFSET ?", ((page - 1) * 100,))]
    ok, bad = audit.verify_chain(conn)
    names = {r["id"]: r["full_name"] for r in q(conn, "SELECT id, full_name FROM users")}
    total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
    return render(request, "audit.html", user=user, rows=rows, ok=ok, bad=bad, names=names, page=page, total=total)


@app.get("/thong-bao", response_class=HTMLResponse)
def notifications(request: Request):
    user = current_user(request)
    rows = [dict(r) for r in q(request.state.conn, "SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 100",
                               (user["id"],))]
    return render(request, "notifications.html", user=user, rows=rows)


@app.post("/thong-bao/doc-het")
def read_all(request: Request):
    user = current_user(request)
    request.state.conn.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
                               (clock.now(request.state.conn), user["id"]))
    return back("/thong-bao")


@app.get("/chay-thu", response_class=HTMLResponse)
def backtest(request: Request):
    user = current_user(request, "bqt", "thu_ky", "admin")
    return render(request, "backtest.html", user=user, result=reports.backtest(request.state.conn))


@app.post("/he-thong/ngay")
async def set_demo_day(request: Request):
    user = current_user(request)
    if not DEMO:
        raise Forbidden()
    data, _ = await form_data(request)
    conn = request.state.conn
    before = S.get(conn, "demo_today")
    S.set_raw(conn, "demo_today", data.get("day"))
    audit.log(conn, user["id"], "Đổi ngày hệ thống (demo)", "setting", "demo_today", {"value": before}, {"value": data.get("day")})
    jobs.run_daily(conn)
    flash(request, "ok", f"Ngày hệ thống: {vn_date(data.get('day'))}. Đã chạy tác vụ theo lịch")
    return back(request.headers.get("referer") or "/")


@app.post("/he-thong/chay-lich")
def run_jobs(request: Request):
    current_user(request, "bqt", "thu_ky", "admin")
    jobs.run_daily(request.state.conn, force=True)
    flash(request, "ok", "Đã chạy tác vụ theo lịch (nhắc biểu quyết, hết hạn, R-16, R-17, R-22)")
    return back(request.headers.get("referer") or "/")


@app.get("/xuat-du-lieu")
def export_all(request: Request):
    """Quyền sở hữu dữ liệu (mục 10): xuất toàn bộ dữ liệu dạng CSV."""
    user = current_user(request, "bqt", "admin")
    conn = request.state.conn
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            cur = conn.execute(f"SELECT * FROM {table}")
            if table == "users":
                cur = conn.execute("SELECT id, username, full_name, role, is_chair, is_account_holder, email, active FROM users")
            s = io.StringIO()
            w = csv.writer(s)
            w.writerow([d[0] for d in cur.description])
            w.writerows(cur.fetchall())
            z.writestr(f"{table}.csv", s.getvalue().encode("utf-8-sig"))
    audit.log(conn, user["id"], "Xuất toàn bộ dữ liệu", "system")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="skyline-du-lieu-{clock.today(conn)}.zip"'})
