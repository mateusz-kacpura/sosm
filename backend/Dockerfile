FROM python:3.11-slim

WORKDIR /app

# Minimal system dependencies for API server.
# Browser automation (worker) runs on the host via Camoufox.
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FastAPI start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
