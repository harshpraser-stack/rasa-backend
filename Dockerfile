# Dockerfile
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps — small set
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# copy and install python deps
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

# copy project
COPY . .

# expose both ports (Render will map the public PORT)
EXPOSE 5005 5055

# default command — override in Render startCommand
CMD ["bash", "-lc", "PORT=${PORT:-5005}; echo \"Starting Rasa on port $PORT\"; rasa run --enable-api --cors \"*\" --port $PORT --log-file out.log"]
