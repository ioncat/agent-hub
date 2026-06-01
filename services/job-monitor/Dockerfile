FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY monitor.py feeds.example.json config.example.json ./

# Runtime state (seen_jobs.json, monitor.log, monitor.lock) → /app/data
# feeds.json mounted by docker-compose as /app/feeds.json
ENV DATA_DIR=/app/data

CMD ["python", "monitor.py"]
