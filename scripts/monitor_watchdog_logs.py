import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
PASSWORD = os.getenv("SSH_PASSWORD")

def monitor_watchdog():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=PASSWORD)
        
        print("\n🐶 Watchdog Logs:")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && docker compose logs --tail 50 watchdog")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    monitor_watchdog()
