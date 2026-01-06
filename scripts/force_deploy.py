import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
PASSWORD = os.getenv("SSH_PASSWORD")

def force_deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=PASSWORD)
        
        # Combine commands into one shell execution or chain them with cd
        chain = "cd /root/bot && docker compose down && docker rmi -f bot-bot bot-watchdog || true && git pull && docker compose up -d --build --remove-orphans"
        
        print(f"\n🏃 Running chain: {chain}")
        stdin, stdout, stderr = client.exec_command(chain)
        
        # Read output in real-time or wait
        # exec_command returns channels. reading stdout blocks until finished.
        
        print("Stdout:")
        print(stdout.read().decode())
        print("Stderr:")
        print(stderr.read().decode())
                
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    force_deploy()
