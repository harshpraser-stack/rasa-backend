# Dockerfile (for single-container Rasa + actions)
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install small system deps
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl git rsync \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Copy and install python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel
RUN pip install -r /app/requirements.txt

# Copy project files
COPY . /app

# Make start script executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose a port (Render sets $PORT at runtime)
EXPOSE 8000

# Use start.sh as entrypoint - start both action server & Rasa
CMD ["/app/start.sh"]
