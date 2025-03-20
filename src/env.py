import os
import math

# proj_path = "/home/lpk/udfgen/sigmod-reproduce" # SET YOUR PATH HERE
# proj_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
proj_path = "/home/ubuntu/autofe" # 调试用
print("Current Project Root is ", proj_path)

global_seed = 0
test_save_path = os.path.join(proj_path, "test", "store")
dataset_path = os.path.join(proj_path, "dataset", "task")
udf_path = os.path.join(proj_path, "src", "clib")
model_store_path = os.path.join(udf_path, "models")
TOTAL_RETRY_TIMES = 2
DIVIDE_RETRY_TIMES = 2

topK_rag = 10
diverse_num = 6 # k in the paper
alpha = math.sqrt(2) / 1000.0 # w in the paper

rag_model_id_or_path = "Alibaba-NLP/gte-Qwen2-1.5B-instruct"
openai_api_key = "sk-qC4pmgaIQuCgMqBROVLYMMv9ZuHDeJQafeZeLfWAqxJQaahO"
openai_base_url = "https://chatapi.littlewheat.com/v1"
default_model = "gpt-4o"
pg_user = "myuser"
pg_db = "mydb"
pg_port = 5432

def update_llm_model(model):
    global default_model
    default_model = model
    print(f"LLM model updated to: {default_model}")