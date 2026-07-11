FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir psycopg2-binary kafka-python

COPY bridge.py .

CMD ["python", "bridge.py"]
