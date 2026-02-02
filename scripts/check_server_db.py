import os
import paramiko
from dotenv import load_dotenv

load_dotenv()

HOST = "89.169.47.138"
USER = "root"

def check_db():
    password = os.getenv("SSH_PASSWORD")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Connecting to {HOST}...")
        client.connect(hostname=HOST, username=USER, password=password)
        
        # Check last 5 sessions
        cmd = 'docker exec diagnostic-db psql -U user -d diagnostic_bot -c "SELECT id, user_id, status, started_at FROM diagnostic_sessions ORDER BY started_at DESC LIMIT 5;"'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("\n📊 Last 5 sessions in DB:")
        print(stdout.read().decode())
        
        # Check if user exists
        cmd = 'docker exec diagnostic-db psql -U user -d diagnostic_bot -c "SELECT id, telegram_id, username FROM users WHERE telegram_id = 785561885;"'
        stdin, stdout, stderr = client.exec_command(cmd)
        print("\n👤 Admin user in DB:")
        print(stdout.read().decode())
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_db()
