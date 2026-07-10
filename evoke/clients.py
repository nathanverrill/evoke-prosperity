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

AI_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "local-dev-key")

ai_client = None

if AI_ENABLED:
    ai_client = OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key=OLLAMA_API_KEY,
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

ai_client = OpenAI(
    base_url=OLLAMA_BASE_URL,
    api_key=OLLAMA_API_KEY
)

def get_producer():
    return KafkaProducer(
        bootstrap_servers=[REDPANDA_BROKER],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )