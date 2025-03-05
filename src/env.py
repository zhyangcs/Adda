import os
import math

# proj_path = "/home/lpk/udfgen/sigmod-reproduce" # SET YOUR PATH HERE
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
diverse_num = 6 # k in the paper
alpha = math.sqrt(2) / 1000.0 # w in the paper

rag_model_id_or_path = "Alibaba-NLP/gte-Qwen1.5-7B-instruct"
openai_api_key = "YOUR-API-KEY"
default_model = "gpt-4o-2024-08-06"
pg_user = "YOUR_PG_USER_NAME"
pg_db = "YOUR_PG_USER_DATABASE"
pg_port = 5431