FROM python:3.11-slim

# Install build dependencies for any packages that require compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first to leverage Docker cache
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the source
COPY . /app

ENV PYTHONUNBUFFERED=1

# Default command: run the bot. Set required env vars at run time.
CMD ["python", "main.py"]
