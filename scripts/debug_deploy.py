import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
PASSWORD = os.getenv("SSH_PASSWORD")

def debug_deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=PASSWORD)
        
        print("\n📂 Checking git status...")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && git status")
        print(stdout.read().decode())
        
        print("\n⬇️ Running git pull...")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && git pull")
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print("\n📜 Checking main.py content (logging part)...")
        stdin, stdout, stderr = client.exec_command("cd /root/bot && grep -C 5 'FileHandler' src/bot/main.py")
        out = stdout.read().decode()
        if out:
            print("❌ FileHandler still found in main.py:")
            print(out)
        else:
            print("✅ FileHandler NOT found in main.py (Good!)")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    debug_deploy()
