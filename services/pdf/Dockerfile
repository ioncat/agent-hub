FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py render.py ./

# Fonts mounted at runtime via volume (./fonts:/app/fonts in docker-compose)
ENV CAREER_AGENT_FONTS=/app/fonts

EXPOSE 8002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]
