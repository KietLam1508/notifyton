# Ảnh chạy ứng dụng Skyline BQT. Dữ liệu (SQLite + chứng từ) nằm ở /data – PHẢI gắn ổ đĩa bền vững vào đây.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    SKYLINE_DATA=/data SKYLINE_DEMO=0 TZ=Asia/Ho_Chi_Minh

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

RUN useradd --create-home skyline && mkdir -p /data && chown skyline /data
USER skyline
VOLUME ["/data"]
EXPOSE 8000

# 1 worker: SQLite + tác vụ theo lịch chạy trong tiến trình, không chạy nhiều bản song song
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
