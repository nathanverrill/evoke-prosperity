FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# main.py imports absolute (`from evoke.clients import ...`, `from evoke.lms import
# ...`), which requires an importable `evoke` package on the path — not a flat
# COPY into /app. Preserve the package directory instead of flattening it.
COPY . ./evoke/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "evoke.main:app", "--host", "0.0.0.0", "--port", "8000"]