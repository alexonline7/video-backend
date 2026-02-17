FROM node:18-bullseye

USER root

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    ffmpeg \
    chromium \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV CHROMIUM_PATH=/usr/bin/chromium

RUN npm install -g remotion @remotion/cli @remotion/renderer @remotion/bundler react react-dom

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY PRODUCTION_backend.py .

EXPOSE 5000

CMD ["python3", "PRODUCTION_backend.py"]
