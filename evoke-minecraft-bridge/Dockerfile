FROM python:3.11-slim

WORKDIR /app

# Unbuffered stdout -- without this, every print() in bridge.py sits in a
# block buffer and `docker logs` shows nothing but stderr, which made the
# service undebuggable (loops could fail silently for their whole life).
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir psycopg2-binary kafka-python requests

COPY bridge.py .

CMD ["python", "bridge.py"]
