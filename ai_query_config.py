import os, yaml, boto3, json, logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def load_config(path="ai_query_config.yaml"):
    """Load YAML configuration and merge with environment variables."""
    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not read {path}: {e}")
        config = {}

    # Merge with env vars
    env = os.getenv("ENV", config.get("environment", "dev"))
    region = os.getenv("AWS_REGION", config.get("region", "us-east-1"))
    bedrock_model = os.getenv("BEDROCK_MODEL", config.get("bedrock", {}).get("default_model"))

    return {
        "env": env,
        "region": region,
        "bronze_db": os.getenv("BRONZE_DB", config["databases"]["bronze"]),
        "silver_db": os.getenv("SILVER_DB", config["databases"]["silver"]),
        "gold_db": os.getenv("GOLD_DB", config["databases"]["gold"]),
        "athena_output": os.getenv("ATHENA_OUTPUT", config["athena"]["output_bucket"]),
        "athena_workgroup": os.getenv("ATHENA_WORKGROUP", config["athena"].get("workgroup", "primary")),
        "bedrock_model": bedrock_model,
        "bedrock_temp": float(os.getenv("BEDROCK_TEMP", config["bedrock"].get("temperature", 0.3))),
        "bedrock_tokens": int(os.getenv("BEDROCK_TOKENS", config["bedrock"].get("max_tokens", 500))),
    }

def get_bedrock_client(region=None):
    """Create a Bedrock Runtime client."""
    region = region or os.getenv("AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)

