FROM node:18-bullseye

RUN apt-get update && \
    apt-get install -y python3 python3-pip ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --break-system-packages -r requirements.txt

COPY PRODUCTION_backend.py .

EXPOSE 5000

CMD ["python3", "PRODUCTION_backend.py"]
