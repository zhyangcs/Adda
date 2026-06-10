import psycopg2
import sys

try:
    # 替换成你的密码，如果没有密码就把 password 参数去掉
    conn = psycopg2.connect(
        database="mydb",
        user="myuser",
        password="your_password", 
        host="localhost",
        port="5431"
    )
    print("✅ 连接成功！psycopg2 工作正常。")
    conn.close()
except ImportError:
    print("❌ 错误：缺少 psycopg2 模块。请运行 pip install psycopg2-binary")
except Exception as e:
    print(f"❌ 连接失败，具体错误信息：\n{e}")