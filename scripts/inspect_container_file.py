import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"
PASSWORD = os.getenv("SSH_PASSWORD")

def inspect_file():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=PASSWORD)
        
        print("\n🔍 Checking file content inside the IMAGE (bot-bot)...")
        # Try to run a temporary container from the image to cat the file
        cmd = "docker run --rm bot-bot cat /app/src/bot/main.py | grep FileHandler"
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        
        if out:
            print("❌ FileHandler FOUND in image:")
            print(out)
        else:
            print("✅ FileHandler NOT found in image.")
            
        if err:
             print(f"⚠️ Stderr: {err}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    inspect_file()
