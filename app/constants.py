"""Nhãn tiếng Việt và hằng số dùng chung."""

STATUS = {
    "nhap": "Nháp",
    "yeu_cau_bo_sung": "Yêu cầu bổ sung",
    "da_nop": "Đã nộp",
    "cho_bieu_quyet": "Chờ biểu quyết",
    "can_hop": "Cần họp trực tiếp",
    "da_duyet": "Đã duyệt",
    "tu_choi": "Từ chối",
    "san_sang_ky": "Sẵn sàng ký",
    "da_ky": "Đã ký",
    "da_doi_soat": "Đã đối soát",
    "dong": "Đóng",
    "huy": "Đã hủy",
}

# Các trạng thái được tính là "đã cam kết chi" (lũy kế dự toán R-08)
COMMITTED = ("da_duyet", "san_sang_ky", "da_ky", "da_doi_soat", "dong")
# Các trạng thái đang trong luồng hoặc đã chi (lũy kế hợp đồng R-19, hóa đơn trùng R-18)
IN_FLOW = ("da_nop", "cho_bieu_quyet", "can_hop") + COMMITTED

ROLES = {
    "bqt": "Thành viên BQT",
    "thu_ky": "Thư ký / kế toán BQT",
    "bql": "Ban quản lý (BQL)",
    "admin": "Quản trị hệ thống",
}

FUNDS = {"BT": "Quỹ bảo trì", "VH": "Quỹ vận hành"}

DOC_TYPES = {
    "to_trinh": "Tờ trình của BQL",
    "hop_dong": "Hợp đồng / đơn đặt hàng",
    "bao_gia": "Báo giá",
    "nghiem_thu": "Biên bản nghiệm thu",
    "hoa_don": "Hóa đơn VAT",
    "kpi": "Báo cáo KPI tháng",
    "tra_cuu_mst": "Ảnh tra cứu mã số thuế",
    "de_nghi_ky": "Văn bản đề nghị chuyển tiền của BQT (bản ký)",
    "bien_ban_hop_ky": "Biên bản họp BQT về việc rút kinh phí (bản ký)",
    "unc": "Uỷ nhiệm chi",
    "khac": "Tài liệu khác",
}
BQL_DOC_TYPES = ("to_trinh", "hop_dong", "bao_gia", "nghiem_thu", "hoa_don", "kpi", "tra_cuu_mst", "khac")
BQT_DOC_TYPES = ("de_nghi_ky", "bien_ban_hop_ky", "khac")

SEVERITY = {"chan": "Chặn", "cao": "Cao", "tb": "Trung bình", "nhac": "Nhắc việc"}
SEVERITY_ORDER = {"chan": 0, "cao": 1, "tb": 2, "nhac": 3}

SOURCE = {"L": "Luật định", "Q": "Quy chế Skyline", "T": "Thực hành tốt"}

PAYMENT_METHOD = {"chuyen_khoan": "Chuyển khoản", "tien_mat": "Tiền mặt"}

TXN_CATEGORY = {
    "phi_ngan_hang": "Phí ngân hàng",
    "lai": "Lãi tiền gửi",
    "gui_ky_han": "Chuyển sang tiền gửi có kỳ hạn",
    "tat_toan_ky_han": "Tất toán tiền gửi có kỳ hạn",
    "thu_khac": "Khoản thu khác",
    "khac": "Khác (ghi rõ)",
}

MATCH_STATUS = {
    "chua_khop": "Chưa giải thích",
    "de_xuat": "Đề xuất khớp – chờ xác nhận",
    "da_khop": "Đã khớp tờ trình",
    "de_xuat_phan_loai": "Đã phân loại – chờ chủ TK duyệt",
    "da_phan_loai": "Đã phân loại",
}

TIER_RULE = {"count": "Số phiếu tối thiểu", "majority": "Quá bán", "all": "Toàn bộ"}
