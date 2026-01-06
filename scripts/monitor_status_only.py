import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
PASSWORD = os.getenv("SSH_PASSWORD")

def monitor_status():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=PASSWORD)
        
        print("\n🐳 Docker Status:")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && docker compose ps")
        print(stdout.read().decode())
        
        print("\n📜 Last 50 logs:")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && docker compose logs --tail 50 --no-log-prefix bot")
        logs = stdout.read().decode()
        print(logs)
        
        if "PermissionError" in logs:
             print("\n❌ STILL FAILING with PermissionError!")
        elif "ERROR" in logs:
             print("\n❌ Errors found in recent logs!")
        else:
             print("\n✅ No recent errors found. Bot seems healthy.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    monitor_status()
