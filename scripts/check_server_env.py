import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"

def check_env():
    password = os.getenv("SSH_PASSWORD")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=password)
        
        stdin, stdout, stderr = client.exec_command("docker exec diagnostic-bot env | grep BOT_TOKEN")
        print("\n🤖 Bot Token in container:")
        print(stdout.read().decode())
        
        stdin, stdout, stderr = client.exec_command("docker exec diagnostic-bot env | grep DATABASE_URL")
        print("\n🗄️ DB URL in container:")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_env()
