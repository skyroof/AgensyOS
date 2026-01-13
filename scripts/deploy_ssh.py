import os
import sys
import paramiko
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def deploy():
    # Configuration
    host = os.getenv("SSH_HOST", "89.169.47.138")
    user = os.getenv("SSH_USER", "root")
    password = os.getenv("SSH_PASSWORD")
    
    if not password:
        print("❌ Error: SSH_PASSWORD not found in .env file")
        print("Please add SSH_PASSWORD=your_password_here to .env")
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
        
        # Enable keepalive to prevent connection drop during long build
        transport = client.get_transport()
        transport.set_keepalive(30)
        
        print("✅ Connected!")
        
        # Commands to run
        # Use deploy.sh for all logic
        commands = [
            "cd /root/bot",
            "rm -f Dockerfile.watchdog", # Remove conflicting file
            "git reset --hard", 
            "git pull",
            "chmod +x deploy.sh",
            "./deploy.sh"
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
            print("\n✅ Deploy completed successfully!")
        else:
            print(f"\n❌ Deploy failed with exit code {exit_status}")
            sys.exit(exit_status)
            
    except Exception as e:
        print(f"\n❌ Error during deployment: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    deploy()
