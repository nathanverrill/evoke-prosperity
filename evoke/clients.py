import os
import json
import boto3
from kafka import KafkaProducer
from opensearchpy import OpenSearch
from openai import OpenAI

# --- Environment Configuration ---
REDPANDA_BROKER = os.getenv("REDPANDA_BROKER", "redpanda:29092")
OPENSEARCH_NODE = os.getenv("OPENSEARCH_NODE", "http://opensearch:9200")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "admin")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "devsecret123")


AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"

# Routed through the same OpenWebUI "billbot" custom model as everywhere
# else in the app (main.py's trigger_ai_review/billbot_chat/post_reflection)
# and the Minecraft mod -- this used to hit raw Ollama directly with a
# generic "empathetic learning coach" persona and a vision model
# (qwen2.5vl:7b) picked for no reason tied to this text-only task. Same
# backend everywhere means one place to fix reasoning-mode timeouts, one
# RAG knowledge base, one voice. OpenWebUI exposes an OpenAI-compatible API
# at /api, so the same OpenAI SDK client just needs pointing at it.
AI_MODEL = "billbot"
OPENWEBUI_URL = os.getenv("OPENWEBUI_URL", "http://open-webui:8080")
OPENWEBUI_API_KEY = os.getenv("OPENWEBUI_API_KEY", "")

ai_client = None

if AI_ENABLED:
    ai_client = OpenAI(
        base_url=f"{OPENWEBUI_URL}/api",
        api_key=OPENWEBUI_API_KEY,
    )

# --- Infrastructure Clients ---
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ROOT_USER,
    aws_secret_access_key=MINIO_ROOT_PASSWORD,
    region_name="us-east-1"
)

os_client = OpenSearch(hosts=[OPENSEARCH_NODE], use_ssl=False, verify_certs=False)

def get_producer():
    return KafkaProducer(
        bootstrap_servers=[REDPANDA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )