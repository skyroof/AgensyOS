import os
import sys
import paramiko
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_recovery():
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
        
        print("✅ Connected! Running recovery script...")
        
        # Command to run recovery script inside the container
        # We need to make sure the script is available in the container
        # Since we just deployed, it should be there.
        # We use 'bot' service context.
        
        commands = [
            "cd /root/bot",
            "docker compose run --rm bot python scripts/recover_sessions.py"
        ]
        
        full_command = " && ".join(commands)
        
        # Execute command
        # We use exec_command to stream output
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
    run_recovery()
