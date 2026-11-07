# Hướng dẫn triển khai Skyline BQT lên máy chủ

Dành cho người phụ trách kỹ thuật. Thời gian thực hiện khoảng 1–2 giờ nếu đã quen Linux cơ bản.

## Tóm tắt cho người không chuyên

- Ứng dụng chạy trên **một máy chủ ảo nhỏ** (VPS) thuê theo tháng, truy cập qua một địa chỉ web riêng (ví dụ `bqt.skyline.vn`) có HTTPS.
- Dữ liệu (cơ sở dữ liệu và file chứng từ) nằm **trên ổ đĩa của máy chủ đó**, nên bắt buộc phải **sao lưu hằng ngày ra nơi khác**.
- Tài khoản máy chủ, tên miền và bản sao lưu nên **đứng tên BQT**, không đứng tên cá nhân (mục 10 PRD: dữ liệu thuộc về tòa nhà).

## 1. Chọn nơi đặt máy chủ

| Lựa chọn | Phù hợp khi | Ghi chú |
|---|---|---|
| **VPS + Docker** (khuyến nghị) | Muốn chi phí thấp, dữ liệu nằm trong tay BQT | Nhà cung cấp trong nước (Viettel IDC, FPT Cloud, VNPT, BizFly…) hoặc quốc tế (DigitalOcean, AWS Lightsail – vùng Singapore…). Cấu hình 1–2 vCPU, 2 GB RAM, 20 GB ổ đĩa là đủ cho một tòa nhà |
| Nền tảng PaaS (Render, Railway, Fly.io…) | Không muốn tự quản máy chủ | **Chỉ chọn gói có ổ đĩa bền vững (persistent disk/volume)** gắn vào `/data`. Gói không có ổ đĩa bền vững sẽ **mất toàn bộ dữ liệu** mỗi lần khởi động lại |
| Máy tính trong văn phòng BQL | — | **Không khuyến nghị**: phụ thuộc BQL, khó bảo đảm tách quyền và sao lưu |

Cần hỏi pháp lý (gộp vào Q8): có yêu cầu đặt máy chủ chứa dữ liệu cư dân, tài chính tại Việt Nam không.

Ứng dụng dùng SQLite và **chỉ chạy 1 tiến trình**. Không chạy nhiều bản song song hoặc tự động nhân bản (autoscale).

## 2. Chuẩn bị

1. Một VPS chạy Ubuntu 22.04/24.04, có địa chỉ IP công khai.
2. Một tên miền con, tạo bản ghi DNS loại **A** trỏ về IP của VPS (ví dụ `bqt.skyline.vn → 203.0.113.10`).
3. Mở cổng 80 và 443 trên tường lửa của nhà cung cấp.
4. Quyền đọc repo GitHub `KietLam1508/notifyton` từ máy chủ (repo riêng tư: dùng *deploy key* chỉ đọc).

## 3. Cài đặt

```bash
# Trên VPS
curl -fsSL https://get.docker.com | sh
git clone -b claude/skyline-financial-monitoring-v92f4l git@github.com:KietLam1508/notifyton.git skyline
cd skyline

# Tạo file .env (KHÔNG commit file này)
cat > .env <<EOF
SKYLINE_SECRET=$(openssl rand -hex 32)
DOMAIN=bqt.skyline.vn
EOF
chmod 600 .env

docker compose up -d --build
```

`docker-compose.yml` chạy hai thành phần:
- **skyline**: ứng dụng, chế độ chạy thật (`SKYLINE_DEMO=0`), dữ liệu nằm trong volume `skyline-data`.
- **caddy**: tự xin và gia hạn chứng chỉ HTTPS miễn phí cho tên miền.

Mở `https://bqt.skyline.vn`, trang đăng nhập hiện ra là thành công. Bản chạy thật **không** hiện danh sách tài khoản mẫu, không có thanh đổi ngày.

## 4. Khởi tạo dữ liệu (bước F-00)

```bash
alias sk='docker compose exec skyline python -m app.manage'

sk init                                    # loại chi phí, cấp duyệt (giá trị mẫu)

# Tài khoản – mỗi lệnh sẽ hỏi mật khẩu (tối thiểu 10 ký tự)
sk create-user nguyenvanan "Nguyễn Văn An" bqt --chair --account-holder
sk create-user tranthibinh "Trần Thị Bình" bqt --account-holder
sk create-user levancuong "Lê Văn Cường" bqt
sk create-user thuky "Võ Thị Giang" thu_ky
sk create-user bql01 "Đặng Văn Hùng" bql
sk create-user quantri "Bùi Văn Khoa" admin   # KHÔNG phải người ký UNC

# Tài khoản quỹ: mã, ngân hàng, số TK, số dư đầu ngày go-live, ngày go-live
sk add-fund BT "Vietcombank – CN Sài Gòn" 0071000888999 12500000000 2026-12-01
sk add-fund VH "BIDV – CN Bến Thành" 31410007776666 850000000 2026-12-01
sk add-signer BT nguyenvanan
sk add-signer BT tranthibinh
sk add-signer VH nguyenvanan
```

Số tài khoản quỹ bảo trì **bị khóa ngay khi tạo** (R-24). Kiểm tra kỹ trước khi chạy lệnh.

Phần còn lại, thư ký hoặc quản trị nhập trên giao diện, mục **Danh mục**:
- tiền gửi có kỳ hạn
- kế hoạch bảo trì, dự toán vận hành (kèm lũy kế đã chi trước go-live)
- nhà cung cấp, hợp đồng (kèm số đã trả trước go-live)
- khai báo xung đột lợi ích, lịch sử chi 12 tháng

Ngưỡng và cấp duyệt sửa ở mục **Cấu hình**, theo quy chế thu chi (Q1).

Theo F-00, dữ liệu khởi tạo phải được **hai người đối chiếu với xác nhận số dư của ngân hàng** trước khi go-live.

## 5. Tác vụ hằng ngày (cron trên VPS)

```bash
crontab -e
```

```cron
# 07:05 – nhắc biểu quyết, chuyển hết hạn sang "Cần họp", R-16, R-17, R-22
5 7 * * *  cd /root/skyline && docker compose exec -T skyline python -m app.manage run-jobs >> /var/log/skyline-jobs.log 2>&1
# 01:30 – sao lưu cơ sở dữ liệu + chứng từ, giữ 30 ngày
30 1 * * * cd /root/skyline && docker compose exec -T skyline python -m app.manage backup /data/backup.db && docker compose cp skyline:/data /root/backup/skyline-$(date +\%F) && find /root/backup -maxdepth 1 -name 'skyline-*' -mtime +30 -exec rm -rf {} +
```

**Bản sao lưu phải được chép ra ngoài VPS** (ổ lưu trữ đám mây của BQT, hoặc dịch vụ sao lưu của nhà cung cấp). Nếu VPS hỏng, bản sao lưu nằm trên chính VPS đó cũng mất.

Nên **thử khôi phục từ bản sao lưu ít nhất một lần** trước go-live.

## 6. Cập nhật phiên bản mới

```bash
cd skyline && git pull && docker compose up -d --build
```

Dữ liệu nằm trong volume nên không mất khi cập nhật. Vẫn nên sao lưu thủ công ngay trước khi cập nhật.

## 7. Việc phải làm trước khi cho BQT dùng thật

- [ ] Bổ sung **xác thực 2 lớp** cho chủ tài khoản và quản trị (mục 10 PRD, chưa có trong bản này)
- [ ] Bổ sung **gửi email/Zalo** (hiện chỉ có thông báo trong ứng dụng)
- [ ] Viết bộ đọc **định dạng sao kê thật** của ngân hàng (Q4)
- [ ] Cập nhật ngưỡng, cấp duyệt theo quy chế (Q1, Q2, Q5)
- [ ] Pháp lý rà soát danh mục rule và căn cứ (Q8)
- [ ] Thử khôi phục từ bản sao lưu
- [ ] Bàn giao: tài khoản VPS, tên miền, nơi lưu sao lưu đứng tên BQT; ghi lại quy trình bàn giao khi đổi nhiệm kỳ

## Biến môi trường

| Biến | Ý nghĩa | Mặc định |
|---|---|---|
| `SKYLINE_SECRET` | Khóa ký phiên đăng nhập. **Bắt buộc** khi chạy thật; đổi khóa sẽ đăng xuất mọi người | — |
| `SKYLINE_DEMO` | `1` = demo (danh sách tài khoản mẫu, đổi ngày hệ thống); `0` = chạy thật (cookie chỉ qua HTTPS) | `1` khi chạy trực tiếp, `0` trong Docker |
| `SKYLINE_DATA` | Thư mục dữ liệu (cơ sở dữ liệu + chứng từ) | `/data` trong Docker |
