import os
import math

proj_path = os.environ.get("PROJ_PATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("Current Project Root is ", proj_path)

global_seed = 0
test_save_path = os.path.join(proj_path, "test", "store")
dataset_path = os.path.join(proj_path, "dataset", "task")
udf_path = os.path.join(proj_path, "src", "clib")
model_store_path = os.path.join(udf_path, "models")
TOTAL_RETRY_TIMES = 2
DIVIDE_RETRY_TIMES = 2

topK_rag = 10
diverse_num = 3  # k in the paper
alpha = math.sqrt(2) / 1000.0  # w in the paper

# RAG model: HuggingFace model ID or local path
rag_model_id_or_path = os.environ.get("RAG_MODEL_ID", "Qwen/Qwen2-0.5B-Instruct")

# LLM API configuration (set via environment variables)
openai_api_key = os.environ.get("OPENAI_API_KEY", "your-api-key-here")
openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
default_model = os.environ.get("DEFAULT_MODEL", "deepseek-chat")

# PostgreSQL configuration (set via environment variables)
pg_user = os.environ.get("PG_USER", "myuser")
pg_password = os.environ.get("PG_PASSWORD", "")
pg_db = os.environ.get("PG_DB", "mydb")
pg_host = os.environ.get("PG_HOST", "localhost")
pg_port = int(os.environ.get("PG_PORT", "5432"))


def update_llm_model(model):
    global default_model
    default_model = model
    print(f"LLM model updated to: {default_model}")
