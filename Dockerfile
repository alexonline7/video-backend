FROM ghcr.io/remotion-dev/base

USER root

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g remotion @remotion/cli react react-dom @remotion/renderer @remotion/bundler

WORKDIR /app

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY PRODUCTION_backend.py .

EXPOSE 5000

CMD ["python3", "PRODUCTION_backend.py"]
