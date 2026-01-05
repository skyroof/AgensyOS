import os
import sys
import paramiko
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_status():
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
            timeout=30
        )
        print("✅ Connected!")
        
        # Commands to check status
        commands = [
            "cd /root/bot",
            "echo '=== CURRENT COMMIT ==='",
            "git log -1 --oneline",
            "echo '=== DOCKER CONTAINERS ==='",
            "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"
        ]
        
        full_command = " && ".join(commands)
        
        print(f"🔄 Executing: {full_command}")
        
        # Execute command
        stdin, stdout, stderr = client.exec_command(full_command, get_pty=True)
        
        # Stream output
        for line in stdout:
            print(line.strip())
            
        # Check exit status
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("\n✅ Status check completed!")
        else:
            print(f"\n❌ Status check failed with exit code {exit_status}")
            sys.exit(exit_status)
            
    except Exception as e:
        print(f"\n❌ Error during status check: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    check_status()
