import os
import sys
import paramiko
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_server():
    # Configuration
    host = os.getenv("SSH_HOST", "89.169.47.138")
    user = os.getenv("SSH_USER", "root")
    password = os.getenv("SSH_PASSWORD")
    
    if not password:
        print("❌ Error: SSH_PASSWORD not found in .env file")
        sys.exit(1)

    print(f"🚀 Connecting to {user}@{host}...")
    
    try:
        # Create SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect
        client.connect(
            hostname=host,
            username=user,
            password=password,
            timeout=60
        )
        
        print("✅ Connected! Sending PDF reports to @laitnerbro...")
        
        # Check status
        commands = [
            "cd /root/bot",
            "git pull",
            "docker compose restart bot",
            # "docker cp scripts/send_pdf_reports.py diagnostic-bot:/app/scripts/send_pdf_reports.py",
            # "docker compose exec -T bot python -u scripts/send_pdf_reports.py 19 21 --target-id 785561885"
        ]
        
        full_command = " && ".join(commands)
        
        # Execute command
        stdin, stdout, stderr = client.exec_command(full_command, get_pty=True)
        
        # Stream output
        for line in stdout:
            print(line.strip())
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    check_server()
