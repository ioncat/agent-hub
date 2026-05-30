FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Default: run the Telegram bot + RSS watcher
# Override with: docker-compose run agent-hub python -m uvicorn web.api:app ...
CMD ["python", "agent.py"]
