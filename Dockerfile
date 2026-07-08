FROM python:3.10-slim

# 1. Cài đặt các công cụ hệ thống thiết yếu
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 2. Tải và cấu hình khóa xác thực Google Chrome chuẩn bảo mật mới (Thay thế apt-key)
RUN curl -fSsL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# 3. Thiết lập thư mục làm việc trong Server
WORKDIR /app

# 4. Sao chép và cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Sao chép toàn bộ mã nguồn và thư mục profile cookie vào Server
COPY . .

# Khai báo cổng chạy ứng dụng cho Render
EXPOSE 8501

# Lệnh khởi chạy ứng dụng Web Streamlit
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]