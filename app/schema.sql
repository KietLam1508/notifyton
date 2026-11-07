-- Skyline BQT – lược đồ dữ liệu (Phụ lục A của PRD v0.2)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('bqt','thu_ky','bql','admin')),
    is_chair INTEGER NOT NULL DEFAULT 0,          -- Trưởng ban
    is_account_holder INTEGER NOT NULL DEFAULT 0, -- chủ / đồng chủ tài khoản
    email TEXT,
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Quỹ (BT = bảo trì, VH = vận hành)
CREATE TABLE IF NOT EXISTS funds (
    code TEXT PRIMARY KEY CHECK (code IN ('BT','VH')),
    name TEXT NOT NULL,
    bank TEXT NOT NULL,
    account_no TEXT NOT NULL,
    account_locked INTEGER NOT NULL DEFAULT 0,
    opening_balance INTEGER NOT NULL DEFAULT 0,   -- F-00: số dư đầu ngày go-live
    opening_date TEXT NOT NULL,
    interest_unused INTEGER NOT NULL DEFAULT 0    -- lãi đã nhận chưa sử dụng (giữ riêng)
);

CREATE TABLE IF NOT EXISTS fund_signers (
    fund_code TEXT NOT NULL REFERENCES funds(code),
    user_id INTEGER NOT NULL REFERENCES users(id),
    PRIMARY KEY (fund_code, user_id)
);

CREATE TABLE IF NOT EXISTS term_deposits (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL REFERENCES funds(code),
    bank TEXT NOT NULL,
    amount INTEGER NOT NULL,
    rate REAL NOT NULL,
    start_date TEXT NOT NULL,
    maturity_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','settled'))
);

-- Kế hoạch bảo trì / dự toán vận hành có phiên bản
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL REFERENCES funds(code),
    year INTEGER NOT NULL,
    version INTEGER NOT NULL,
    resolution_no TEXT NOT NULL,
    resolution_date TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    file_path TEXT,
    UNIQUE (fund_code, year, version)
);

CREATE TABLE IF NOT EXISTS plan_items (
    id INTEGER PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES plans(id),
    code TEXT NOT NULL,           -- mã hạng mục, giữ nguyên qua các phiên bản
    name TEXT NOT NULL,
    budget INTEGER NOT NULL,
    spent_before_golive INTEGER NOT NULL DEFAULT 0,
    UNIQUE (plan_id, code)
);

CREATE TABLE IF NOT EXISTS cost_types (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    is_operational INTEGER NOT NULL DEFAULT 0,  -- thuộc quản lý vận hành → cấm chi từ quỹ bảo trì (R-01)
    emergency_allowed INTEGER NOT NULL DEFAULT 0 -- quy chế thu chi cho phép chi đột xuất (R-03)
);

CREATE TABLE IF NOT EXISTS approval_tiers (
    level INTEGER PRIMARY KEY,
    min_amount INTEGER NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('count','majority','all')),
    required_count INTEGER NOT NULL DEFAULT 0,
    require_chair INTEGER NOT NULL DEFAULT 0,
    in_person INTEGER NOT NULL DEFAULT 0,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    tax_code TEXT NOT NULL,
    bank_name TEXT,
    bank_account TEXT
);

-- Khai báo xung đột lợi ích (BQT hoặc nhân sự BQL)
CREATE TABLE IF NOT EXISTS conflicts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    note TEXT,
    declared_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY,
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    fund_code TEXT NOT NULL REFERENCES funds(code),
    contract_no TEXT NOT NULL,
    title TEXT NOT NULL,
    value INTEGER NOT NULL,
    addendum_value INTEGER NOT NULL DEFAULT 0,
    signed_date TEXT,                         -- NULL = chưa ký
    beneficiary_account TEXT NOT NULL,
    advance_pct REAL NOT NULL DEFAULT 0,      -- điều khoản tạm ứng (% giá trị HĐ); 0 = không có
    paid_before_golive INTEGER NOT NULL DEFAULT 0,
    is_mgmt_contract INTEGER NOT NULL DEFAULT 0, -- hợp đồng QLVH
    kpi_threshold REAL                        -- điểm KPI tối thiểu (HĐ QLVH)
);

CREATE TABLE IF NOT EXISTS contract_installments (
    id INTEGER PRIMARY KEY,
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    seq INTEGER NOT NULL,
    name TEXT NOT NULL,
    amount INTEGER NOT NULL
);

-- F-00: lịch sử chi 12 tháng trước go-live
CREATE TABLE IF NOT EXISTS history_payments (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL,
    vendor_name TEXT NOT NULL,
    vendor_tax_code TEXT NOT NULL,
    plan_item_code TEXT,
    amount INTEGER NOT NULL,
    pay_date TEXT NOT NULL,
    invoice_no TEXT,
    service_key TEXT,
    unit_price INTEGER
);

CREATE TABLE IF NOT EXISTS golive_signoff (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    signed_at TEXT NOT NULL,
    note TEXT
);

CREATE TABLE IF NOT EXISTS kpi_scores (
    month TEXT PRIMARY KEY,   -- YYYY-MM
    self_score REAL,
    bqt_score REAL,
    note TEXT
);

-- Tờ trình
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    fund_code TEXT NOT NULL REFERENCES funds(code),
    plan_item_code TEXT,
    plan_id INTEGER REFERENCES plans(id),       -- phiên bản kế hoạch hiệu lực khi nộp
    is_emergency INTEGER NOT NULL DEFAULT 0,
    cost_type TEXT NOT NULL REFERENCES cost_types(code),
    vendor_id INTEGER NOT NULL REFERENCES vendors(id),
    contract_id INTEGER NOT NULL REFERENCES contracts(id),
    installment_id INTEGER REFERENCES contract_installments(id),
    amount INTEGER NOT NULL,
    payment_method TEXT NOT NULL CHECK (payment_method IN ('chuyen_khoan','tien_mat')),
    beneficiary_account TEXT,
    is_advance INTEGER NOT NULL DEFAULT 0,
    is_mgmt_fee INTEGER NOT NULL DEFAULT 0,
    kpi_month TEXT,
    service_key TEXT,
    unit_price INTEGER,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    linked_submission_id INTEGER REFERENCES submissions(id), -- tờ trình bị từ chối trước đó
    superseded_by INTEGER REFERENCES submissions(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    submitted_at TEXT,
    emergency_confirmed_by INTEGER REFERENCES users(id),
    emergency_confirmed_at TEXT,
    emergency_note TEXT,
    reported_to_assembly_at TEXT,
    vote_opened_at TEXT,
    vote_deadline TEXT,
    approval_basis TEXT,            -- 'online' | 'meeting'
    decided_at TEXT,
    rejection_reason TEXT,
    signed_docs_verified_by INTEGER REFERENCES users(id),
    signed_docs_verified_at TEXT,
    ready_at TEXT,
    signed_at TEXT,
    signed_by INTEGER REFERENCES users(id),
    unc_ref TEXT,
    unc_amount INTEGER,
    reconciled_at TEXT,
    closed_at TEXT,
    UNIQUE (code, version)
);

CREATE TABLE IF NOT EXISTS status_history (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    from_status TEXT,
    to_status TEXT NOT NULL,
    at TEXT NOT NULL,
    by_user INTEGER REFERENCES users(id),
    note TEXT
);

-- Chứng từ (không xóa; thay bằng phiên bản mới)
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    doc_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    uploaded_at TEXT NOT NULL,
    invoice_no TEXT,
    seller_tax_code TEXT,
    amount INTEGER,
    doc_date TEXT,
    signed_by_bqt INTEGER NOT NULL DEFAULT 0,
    signed_by_supervisor INTEGER NOT NULL DEFAULT 0,
    contract_signed INTEGER NOT NULL DEFAULT 0,
    tax_status TEXT,                -- 'hoat_dong' | 'ngung_hoat_dong'
    superseded_by INTEGER REFERENCES documents(id),
    cancelled INTEGER NOT NULL DEFAULT 0
);

-- Phiếu biểu quyết (giữ lịch sử: phiếu cũ đánh dấu superseded)
CREATE TABLE IF NOT EXISTS votes (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES submissions(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    choice TEXT NOT NULL CHECK (choice IN ('dong_y','khong_dong_y')),
    note TEXT,
    cast_at TEXT NOT NULL,
    superseded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    submission_id INTEGER REFERENCES submissions(id),
    statement_txn_id INTEGER REFERENCES statement_txns(id),
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    checkpoint TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','accepted','resolved')),
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    accepted_by INTEGER REFERENCES users(id),
    accept_reason TEXT,
    accepted_at TEXT,
    confirmed_by INTEGER REFERENCES users(id),
    confirmed_at TEXT,
    false_positive INTEGER
);

CREATE TABLE IF NOT EXISTS statements (
    id INTEGER PRIMARY KEY,
    fund_code TEXT NOT NULL REFERENCES funds(code),
    period_from TEXT NOT NULL,
    period_to TEXT NOT NULL,
    opening_balance INTEGER NOT NULL,
    closing_balance INTEGER NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS statement_rejections (
    id INTEGER PRIMARY KEY,
    fund_code TEXT,
    filename TEXT NOT NULL,
    reasons TEXT NOT NULL,
    uploaded_by INTEGER NOT NULL REFERENCES users(id),
    uploaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS statement_txns (
    id INTEGER PRIMARY KEY,
    statement_id INTEGER NOT NULL REFERENCES statements(id),
    txn_date TEXT NOT NULL,
    bank_ref TEXT,
    description TEXT NOT NULL,
    counter_account TEXT,
    amount INTEGER NOT NULL,          -- âm = ghi nợ (chi), dương = ghi có (thu)
    balance_after INTEGER NOT NULL,
    match_status TEXT NOT NULL DEFAULT 'chua_khop'
        CHECK (match_status IN ('chua_khop','de_xuat','da_khop','de_xuat_phan_loai','da_phan_loai')),
    match_method TEXT,                -- 'ma_to_trinh' | 'tu_dong' | 'xac_nhan'
    submission_id INTEGER REFERENCES submissions(id),
    category TEXT,
    category_note TEXT,
    classified_by INTEGER REFERENCES users(id),
    classified_at TEXT,
    approved_by INTEGER REFERENCES users(id),
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    link TEXT,
    read_at TEXT
);

-- Yêu cầu thay đổi cấu hình (người đề xuất ≠ người duyệt)
CREATE TABLE IF NOT EXISTS config_changes (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    description TEXT NOT NULL,
    payload TEXT NOT NULL,
    attachment_path TEXT,
    proposed_by INTEGER NOT NULL REFERENCES users(id),
    proposed_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS config_change_approvals (
    change_id INTEGER NOT NULL REFERENCES config_changes(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    decision TEXT NOT NULL CHECK (decision IN ('approve','reject')),
    at TEXT NOT NULL,
    note TEXT,
    PRIMARY KEY (change_id, user_id)
);

CREATE TABLE IF NOT EXISTS job_runs (
    job_key TEXT PRIMARY KEY,
    ran_at TEXT NOT NULL
);

-- F-08: nhật ký kiểm toán, chuỗi băm, không sửa/xóa được
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    ts TEXT NOT NULL,
    user_id INTEGER,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id TEXT,
    before_json TEXT,
    after_json TEXT,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Nhật ký kiểm toán không được sửa'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Nhật ký kiểm toán không được xóa'); END;

-- Tờ trình, chứng từ, phiếu, sao kê: chỉ hủy, không xóa
CREATE TRIGGER IF NOT EXISTS submissions_no_delete BEFORE DELETE ON submissions
BEGIN SELECT RAISE(ABORT, 'Tờ trình chỉ được hủy, không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS documents_no_delete BEFORE DELETE ON documents
BEGIN SELECT RAISE(ABORT, 'Chứng từ chỉ được hủy, không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS votes_no_delete BEFORE DELETE ON votes
BEGIN SELECT RAISE(ABORT, 'Phiếu biểu quyết không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS statements_no_delete BEFORE DELETE ON statements
BEGIN SELECT RAISE(ABORT, 'Sao kê không được xóa'); END;
CREATE TRIGGER IF NOT EXISTS txns_no_delete BEFORE DELETE ON statement_txns
BEGIN SELECT RAISE(ABORT, 'Giao dịch sao kê không được xóa'); END;
-- Chứng từ đã nộp không sửa nội dung
CREATE TRIGGER IF NOT EXISTS documents_immutable BEFORE UPDATE OF stored_path, sha256, amount, invoice_no, seller_tax_code, doc_date ON documents
BEGIN SELECT RAISE(ABORT, 'Chứng từ đã nộp không sửa được, chỉ thay bằng phiên bản mới'); END;
-- R-24: số tài khoản quỹ bảo trì khóa sau khi thiết lập (chỉ mở qua quy trình ngoại lệ)
CREATE TRIGGER IF NOT EXISTS fund_account_locked BEFORE UPDATE OF account_no ON funds
WHEN OLD.account_locked = 1 AND NEW.account_no <> OLD.account_no
     AND (SELECT value FROM settings WHERE key = '_r24_unlock') IS NOT '1'
BEGIN SELECT RAISE(ABORT, 'R-24: số tài khoản kinh phí bảo trì đã khóa'); END;
