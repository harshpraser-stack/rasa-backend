# Dockerfile
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# Copy project
COPY . .

# Render exposes this port
EXPOSE 8000

# Use shell form so ${PORT} expands correctly
CMD bash -lc "rasa run --enable-api --cors '*' --model models --port ${PORT}"
