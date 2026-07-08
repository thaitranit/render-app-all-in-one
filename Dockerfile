FROM python:3.10-slim

# Cài đặt các công cụ hệ thống và các gói phụ thuộc cho Google Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    curl \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    && rm -rf /var/lib/apt/lists/*

# Tải và cài đặt Google Chrome Stable phiên bản chính thức
RUN curl -sSLL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Thiết lập thư mục làm việc trong Container
WORKDIR /app

# Sao chép file khai báo thư viện và cài đặt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn và thư mục chrome_user_data vào Container
COPY . .

# Khai báo biến môi trường cho Port của Streamlit trên Render
EXPOSE 8501

# Lệnh khởi chạy ứng dụng Web Streamlit
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]