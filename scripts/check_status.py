import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
KEY_PATH = os.getenv("SSH_KEY_PATH", r"C:\Users\ilayt\.ssh\id_rsa")

def check_status():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    password = os.getenv("SSH_PASSWORD")
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        if password:
            client.connect(hostname=HOST, username=USER, password=password)
        else:
            client.connect(hostname=HOST, username=USER, key_filename=KEY_PATH)
        
        stdin, stdout, stderr = client.exec_command("docker ps")
        print("\n🐳 Docker Containers:")
        print(stdout.read().decode())
        
        stdin, stdout, stderr = client.exec_command("docker logs --tail 100 diagnostic-bot")
        print("\n📜 Last 100 logs from diagnostic-bot:")
        print(stdout.read().decode())
        print(stderr.read().decode()) # docker logs often go to stderr
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_status()
