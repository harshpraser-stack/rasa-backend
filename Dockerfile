FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# copy requirements first to leverage cache
COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# copy project
COPY . .

# make start script executable
RUN chmod +x /app/start.sh

# expose a default port (Render will set $PORT env)
EXPOSE 8000

# start both actions + rasa
CMD ["bash","/app/start.sh"]
