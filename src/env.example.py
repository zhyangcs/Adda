import os
import math

proj_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
# rag_model_id_or_path = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
rag_model_id_or_path = "Qwen/Qwen2-0.5B-Instruct"

# LLM API configuration
openai_api_key = "your-api-key-here"
openai_base_url = "https://api.deepseek.com/v1"
default_model = "deepseek-chat"

# PostgreSQL configuration
pg_user = "myuser"
pg_db = "mydb"
pg_port = 5431


def update_llm_model(model):
    global default_model
    default_model = model
    print(f"LLM model updated to: {default_model}")
