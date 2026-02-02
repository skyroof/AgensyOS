import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"

def check_file():
    password = os.getenv("SSH_PASSWORD")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=password)
        
        stdin, stdout, stderr = client.exec_command("docker exec diagnostic-bot cat src/bot/main.py")
        print("\n📄 content of src/bot/main.py in container:")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_file()
