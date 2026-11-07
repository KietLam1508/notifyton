# Skyline BQT – Công cụ giám sát tài chính & chất lượng dịch vụ

Bản prototype chạy được theo **PRD v0.2** (07/11/2026). Công cụ nội bộ cho Ban quản trị chung cư Skyline:
kiểm soát **trước khi ký UNC** và phát hiện **sau khi chi** qua đối soát sao kê.

> Công cụ **không** chuyển tiền, không kết nối ngân hàng, không đưa ra kết luận pháp lý (mục 3 PRD).
> Mọi ngưỡng, cấp duyệt và căn cứ pháp lý trong bản này là **giá trị mẫu**: còn chờ Q1, Q2, Q5 và chờ rà soát pháp lý.

## Chạy thử

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed                 # tạo dữ liệu demo tại data/skyline.db
.venv/bin/uvicorn app.main:app --port 8000   # mở http://localhost:8000
.venv/bin/python -m pytest                   # 34 test: TC-01 → TC-33 + luồng web đầu-cuối
```

Tài khoản demo (mật khẩu chung `skyline123`): `truongban`, `phoban` (chủ TK) · `tv_cuong`, `tv_dung`, `tv_em`
(thành viên BQT; `tv_em` có khai báo liên quan tới Công ty Sơn Việt) · `thuky` · `bql` · `quantri`.

Thanh vàng "Ngày hệ thống" (chỉ có ở bản demo, tắt bằng `SKYLINE_DEMO=0`) cho phép tua ngày để thử hạn biểu quyết, R-16, R-17, R-22.

### Dữ liệu demo có sẵn

| Mã | Tình huống | Trạng thái |
|---|---|---|
| TT-2026-001 | Thang máy quý 3: đi hết luồng, đã khớp sao kê tháng 10 | Đóng |
| TT-2026-002 | PCCC đợt 3: đã có 2/3 phiếu cần thiết | Chờ biểu quyết |
| TT-2026-003 | Bơm nước hỏng – **đột xuất**, chờ BQT xác nhận (R-25) | Đã nộp |
| TT-2026-004 | Phí QLVH tháng 10 – KPI 78 < 80 (R-15), thiếu báo giá (R-11) | Đã nộp |
| TT-2026-005 | Tạm ứng chống thấm – thiếu hóa đơn, NCC liên quan thành viên BQT | Nháp |

Sao kê tháng 10 quỹ bảo trì có 1 giao dịch lạ 15 triệu chưa giải thích (sẽ thành R-17 sau 5 ngày làm việc).

## Phạm vi đã làm

| PRD | Nội dung | Vị trí code |
|---|---|---|
| F-00 | Số dư, tiền gửi kỳ hạn, hợp đồng + lũy kế, lũy kế hạng mục, lịch sử chi 12 tháng, xác nhận 2 người | `app/seed.py`, trang Danh mục |
| F-01 | Danh mục, kế hoạch có phiên bản, đề xuất → duyệt cấu hình (người đề xuất ≠ người duyệt), rule [L] không tắt được, khóa TK quỹ bảo trì (R-24) | `app/config_changes.py` |
| F-02 | Mã `TT-YYYY-NNN`, khóa số tiền khi mở biểu quyết, phiên bản mới, bắt buộc liên kết khi nộp lại | `app/workflow.py` |
| F-03, F-04 | Checklist hồ sơ + rule engine theo CP1–CP4, mỗi cảnh báo có mức, nguồn, căn cứ, ngày hiệu lực | `app/rules.py` |
| F-04 | Chạy thử rule trên dữ liệu lịch sử (R-09, R-11, R-18) | `app/reports.py`, trang Chạy thử rule |
| F-05 | Cấp duyệt, biểu quyết (loại người xung đột, hạn, nhắc, họp trực tiếp), sinh Word: văn bản đề nghị chuyển tiền, biên bản họp, trích kế hoạch | `app/workflow.py`, `app/docgen.py` |
| F-06 | Chỉ chủ TK xác nhận ký, bắt buộc số tham chiếu + UNC, số tiền phải khớp | `workflow.confirm_sign` |
| F-07 | Sao kê: kiểm tra file gốc & liên tục (R-23), khớp theo mã → số tiền+TK+ngày → đề xuất, phân loại (thư ký) / duyệt (chủ TK), R-17, R-21, R-22 | `app/reconcile.py` |
| F-08 | Nhật ký chuỗi băm, trigger DB chặn sửa/xóa; tờ trình, chứng từ chỉ hủy | `app/audit.py`, `app/schema.sql` |
| F-09 | Thông báo trong ứng dụng | `app/notify.py` |
| F-10 | Dashboard quỹ, lũy kế dự toán, khoản đột xuất chờ báo cáo, chỉ số mục 12 | `app/reports.py` |
| R-15 | KPI tháng (rút gọn từ F-13, P1) | Danh mục → KPI |

**Chưa làm** (cần quyết định/thông tin thêm): xác thực 2 lớp; email/Zalo (F-15); định dạng sao kê thật của ngân hàng (Q4 – hiện dùng định dạng mẫu, tải ở trang Sao kê); mẫu văn bản riêng của ngân hàng (Q12); F-11 → F-20.

## Cấu trúc

```
app/
  schema.sql      lược đồ dữ liệu (Phụ lục A) + trigger chống sửa/xóa
  rules.py        danh mục rule & rule engine theo điểm kiểm soát
  workflow.py     luồng tờ trình → UNC (mục 6)
  reconcile.py    sao kê & đối soát
  config_changes.py, jobs.py, docgen.py, reports.py, audit.py, notify.py
  main.py         web (FastAPI + Jinja2), templates/, static/
tests/test_uat.py   TC-01 → TC-33 (Phụ lục B)
tests/test_web.py   luồng đầy đủ qua giao diện
```
